# -*- coding: utf-8 -*-
"""
本地 AI 调用封装 — Ollama + Qwen2.5
用于知识库资料整理、因子研究辅助、Wiki 页面生成
"""
import os
import re
import json
import requests

# 配置
OLLAMA_BASE = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
DEFAULT_MODEL = 'qwen2.5:7b'


def chat(prompt, system=None, model=DEFAULT_MODEL, temperature=0.3, max_tokens=2048):
    """
    调用本地 Ollama 模型
    
    Args:
        prompt: 用户输入
        system: 系统提示词
        model: 模型名称
        temperature: 温度（越低越确定）
        max_tokens: 最大输出长度
    
    Returns:
        模型输出文本
    """
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    
    try:
        r = requests.post(
            f'{OLLAMA_BASE}/api/chat',
            json={
                'model': model,
                'messages': messages,
                'stream': False,
                'options': {
                    'temperature': temperature,
                    'num_predict': max_tokens,
                }
            },
            timeout=120
        )
        r.raise_for_status()
        return r.json()['message']['content']
    except Exception as e:
        return f'[ERROR] {type(e).__name__}: {e}'


def check_model():
    """检查模型是否可用"""
    try:
        r = requests.get(f'{OLLAMA_BASE}/api/tags', timeout=5)
        models = [m['name'] for m in r.json().get('models', [])]
        return models
    except:
        return []


# ============================================================
# 知识库整理任务
# ============================================================

SYSTEM_WIKI_WRITER = """你是一个量化投资知识库编辑。你的任务是将原始资料整理成结构化的 Wiki 页面。
输出必须是严格的 Markdown 格式，包含 YAML frontmatter。
标签必须来自以下体系：factor, value, quality, momentum, liquidity, size, sentiment, backtest, factor-test, regime, correlation, decay, data-source, pipeline, system, tool, decision, weight-change, factor-addition, market-event, policy, sector-rotation, macro"""


SYSTEM_JSON_TO_NOTE = """你是一个量化投资知识库编辑，负责把 JSON 数据整理成结构化笔记。
输入的 JSON 可能是：
1. 检验/验证结果（扁平键值，键名可能晦涩，如 T1_tx_qh_max_abs_diff、T2_sh600401_rows）——需把键名解读成有意义的指标说明并给出结论。
2. 通用数据结构（嵌套对象/数组）——需自动识别结构并整理。

输出必须是严格的 JSON 对象（不要用 markdown 代码围栏包裹，也不要额外解释），包含字段：
{"title": "简洁标题", "tags": ["2-5 个标签"], "confidence": 0-100 的整数, "body": "Markdown 正文"}

confidence 为 0-100 整数，越高越可信：90-100 极高 / 70-89 高 / 50-69 中 / 30-49 低 / 0-29 极低。

body 不含 YAML frontmatter，结构为：## 概述 / ## 关键数据（用表格）/ ## 解读与结论 / ## 来源。

标签只能来自：factor, value, quality, momentum, liquidity, size, sentiment, backtest, factor-test, regime, correlation, decay, data-source, pipeline, system, tool, decision, weight-change, factor-addition, market-event, policy, sector-rotation, macro, query"""


def extract_key_points(raw_text):
    """从原始资料中提取关键要点"""
    prompt = f"""请从以下资料中提取关键要点，每个要点一行，用 - 开头：

{raw_text[:3000]}"""
    return chat(prompt, system=SYSTEM_WIKI_WRITER, temperature=0.2)


def generate_factor_page(factor_name, raw_text):
    """生成因子概念页面"""
    prompt = f"""请为以下因子生成一个 Wiki 概念页面。

因子名称：{factor_name}
原始资料：
{raw_text[:3000]}

请生成包含以下部分的 Markdown 页面：
1. YAML frontmatter（title, created, updated, type:concept, tags, sources, confidence）
2. 定义
3. 计算公式
4. 经济逻辑
5. 已知问题
6. 相关页面链接（用 [[wikilink]] 格式）"""
    return chat(prompt, system=SYSTEM_WIKI_WRITER, temperature=0.3)


def summarize_for_wiki(raw_text, topic="量化投资"):
    """将资料摘要为 Wiki 格式"""
    prompt = f"""请将以下资料整理为 Wiki 摘要页面。

主题：{topic}
原始资料：
{raw_text[:3000]}

要求：
1. 生成 YAML frontmatter
2. 提取核心观点（3-5个）
3. 标注数据来源
4. 标注 confidence 0-100 分值（越高越可信）"""
    return chat(prompt, system=SYSTEM_WIKI_WRITER, temperature=0.3)


def _extract_json(text):
    """从 AI 输出中容错提取 JSON 对象"""
    text = (text or '').strip()
    m = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        s, e = text.find('{'), text.rfind('}')
        if s != -1 and e != -1 and e > s:
            text = text[s:e + 1]
    try:
        return json.loads(text)
    except Exception:
        return None


def _coerce_confidence(val):
    """把 AI 返回的 confidence 收敛为 0-100 整数（兼容数字/字符串/旧命名档位）。"""
    if isinstance(val, bool):
        return 50
    if isinstance(val, (int, float)):
        try:
            return max(0, min(100, int(val)))
        except (TypeError, ValueError):
            return 50
    if isinstance(val, str):
        s = val.strip().lower()
        m = re.search(r'\d+', s)
        if m:
            return max(0, min(100, int(m.group())))
        named = {'very-low': 15, 'low': 35, 'medium': 60, 'high': 80, 'very-high': 90}
        if s in named:
            return named[s]
    return 50


def json_to_note(json_text, topic="量化研究"):
    """把 JSON 数据用本地 AI 转化为结构化笔记。

    Args:
        json_text: 序列化后的 JSON 文本
        topic: 笔记主题

    Returns:
        dict: {title, tags, confidence, body}
    """
    prompt = f"""请把以下 JSON 数据转化为结构化笔记。

主题：{topic}
JSON 数据：
{json_text}

要求：
1. 键名晦涩时（如 T1_tx_qh_max_abs_diff）解读其含义并给出结论
2. 数据较多时用 Markdown 表格呈现关键项
3. 严格按 system 提示的 JSON 格式输出，不要输出额外解释"""
    raw = chat(prompt, system=SYSTEM_JSON_TO_NOTE, temperature=0.3)
    data = _extract_json(raw)
    if data and isinstance(data, dict):
        title = data.get('title') or topic
        tags = data.get('tags') if isinstance(data.get('tags'), list) else ['query']
        tags = [t for t in tags if isinstance(t, str)]
        confidence = _coerce_confidence(data.get('confidence'))
        body = data.get('body') if isinstance(data.get('body'), str) else raw
        return {'title': title, 'tags': tags or ['query'], 'confidence': confidence, 'body': body}
    return {'title': topic, 'tags': ['query'], 'confidence': 50, 'body': raw}


if __name__ == '__main__':
    # 测试
    print("检查本地 AI 模型...")
    models = check_model()
    if models:
        print(f"可用模型: {', '.join(models)}")
        print("\n测试对话...")
        result = chat("用一句话解释什么是市盈率(PE)。")
        print(f"回答: {result}")
    else:
        print("没有可用模型，请先运行: ollama pull qwen2.5:7b")
