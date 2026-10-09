# -*- coding: utf-8 -*-
"""
Wiki 资料摄入脚本 — 用本地 AI 整理研报/论文到 Wiki
用法: python wiki_ingest.py <原始文件路径> [主题]
"""
import os
import sys
import datetime
import requests

# 本地 AI 配置
OLLAMA_BASE = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
DEFAULT_MODEL = 'qwen2.5:7b'

# Wiki 配置
WIKI_PATH = os.environ.get('WIKI_PATH', r'G:\股市探究\quant-investing\wiki')

# 凭据读取顺序：环境变量 → G:\deeeseek\secrets\quant-investing-wiki.env → 旧位置 wiki/.env
# （2026-09-18 起密钥移出 vault：FMS 禁止密钥入库、避免被 git/索引收录）
def load_env_file(paths):
    for p in paths:
        if os.path.isfile(p):
            with open(p, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ.setdefault(k.strip(), v.strip())
            return p
    return None


_SECRETS = [r'G:\deeeseek\secrets\quant-investing-wiki.env', os.path.join(WIKI_PATH, '.env')]
load_env_file(_SECRETS)

OBSIDIAN_API = os.environ.get('OBSIDIAN_API_URL', 'https://localhost:27124')
OBSIDIAN_KEY = os.environ.get('OBSIDIAN_API_KEY', '')

# ============================================================
# 本地 AI 调用
# ============================================================

def ai_chat(prompt, system=None, temperature=0.3):
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    r = requests.post(
        f'{OLLAMA_BASE}/api/chat',
        json={'model': DEFAULT_MODEL, 'messages': messages, 'stream': False,
              'options': {'temperature': temperature, 'num_predict': 2048}},
        timeout=120
    )
    r.raise_for_status()
    return r.json()['message']['content']


# ============================================================
# Wiki API 操作
# ============================================================

def wiki_write(path, content):
    """通过 API 写入 Wiki 页面"""
    r = requests.put(
        f'{OBSIDIAN_API}/vault/{path}',
        headers={'Authorization': f'Bearer {OBSIDIAN_KEY}', 'Content-Type': 'text/markdown'},
        data=content.encode('utf-8'),
        verify=False,
        timeout=10
    )
    return r.status_code in (200, 204)


def wiki_read(path):
    """通过 API 读取 Wiki 页面"""
    r = requests.get(
        f'{OBSIDIAN_API}/vault/{path}',
        headers={'Authorization': f'Bearer {OBSIDIAN_KEY}'},
        verify=False,
        timeout=10
    )
    return r.text if r.status_code == 200 else None


# ============================================================
# 资料处理流程
# ============================================================

def ingest_article(file_path, topic="量化投资"):
    """摄入一篇资料到 Wiki"""
    today = datetime.date.today().isoformat()
    
    # 1. 读取原始文件
    print(f"[1/4] 读取文件: {file_path}")
    with open(file_path, encoding='utf-8-sig') as f:
        raw = f.read()
    print(f"  原文长度: {len(raw)} 字符")
    
    # 2. AI 提取关键要点
    print("[2/4] AI 提取关键要点...")
    system = "你是量化投资研究助手。请从资料中提取关键要点，输出结构化摘要。"
    summary = ai_chat(
        f"请从以下资料中提取5-10个关键要点，每个要点一行，用 - 开头。最后给出一段50字以内的核心总结。\n\n资料：\n{raw[:3000]}",
        system=system, temperature=0.2
    )
    print(f"  摘要:\n{summary[:200]}...")
    
    # 3. AI 生成 Wiki 页面
    print("[3/4] AI 生成 Wiki 页面...")
    wiki_system = """你是一个量化投资知识库编辑。输出严格的 Markdown 格式。
YAML frontmatter 必须包含：title, created, updated, type:concept, tags, sources, confidence（0-100 整数，默认 50）
标签只能用：factor, value, quality, momentum, backtest, factor-test, regime, market-event, policy, macro"""

    wiki_content = ai_chat(
        f"""请将以下资料整理为 Wiki 概念页面。

主题：{topic}
原始资料摘要：
{summary}

请生成完整的 Wiki Markdown 页面，包含 YAML frontmatter 和结构化内容。""",
        system=wiki_system, temperature=0.3
    )
    
    # 4. 写入 Wiki
    safe_name = topic.replace(' ', '-').replace('/', '-')[:30]
    wiki_path = f'raw/articles/{safe_name}_{today}.md'
    print(f"[4/4] 写入 Wiki: {wiki_path}")
    
    if wiki_write(wiki_path, wiki_content):
        print(f"  ✅ 已写入 {wiki_path}")
    else:
        print(f"  ❌ 写入失败")
        #  fallback: 写入本地
        local_path = os.path.join(WIKI_PATH, wiki_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(wiki_content)
        print(f"  已写入本地: {local_path}")
    
    return wiki_path, summary


# ============================================================
# 主入口
# ============================================================

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python wiki_ingest.py <原始文件路径> [主题]")
        print("示例: python wiki_ingest.py research.txt 价值投资因子")
        sys.exit(1)
    
    file_path = sys.argv[1]
    topic = sys.argv[2] if len(sys.argv) > 2 else "量化投资研究"
    
    ingest_article(file_path, topic)
