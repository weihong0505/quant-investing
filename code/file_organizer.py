# -*- coding: utf-8 -*-
"""
文件整理代理 — 依据 FILE-MANAGEMENT-STANDARD.md 自动归类文件
============================================================
职责：
  1. 扫描「待整理区」（inbox）与库根散落文件
  2. 用规则引擎 + 本地AI (Qwen2.5) 按规范决策树判断归属
  3. 自动移动到规范目录（命名不规范则重命名）
  4. 每次操作记录到 wiki/log.md

用法：
  D:/pyh/python.exe -E G:/股市探究/quant-investing/code/file_organizer.py --dry-run   # 预演
  D:/pyh/python.exe -E G:/股市探究/quant-investing/code/file_organizer.py             # 执行
"""
import os
import re
import sys
import json
import shutil
import datetime
import argparse
import urllib3

urllib3.disable_warnings()

# 修复 Windows GBK 控制台编码问题
import io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================
# 路径配置
# ============================================================
ROOT = r'G:\股市探究\quant-investing'
INBOX = os.path.join(ROOT, '_inbox')          # 待整理区
WIKI_LOG = os.path.join(ROOT, 'wiki', 'log.md')
OBSIDIAN_API = 'https://localhost:27124'
# ⚠️ 2026-10-09 安全修复：原先此处硬编码了 Obsidian Local REST API 的明文 apiKey。
#    该密钥已泄漏于本地 git 历史，任何进入版本控制/发布的副本都必须不含字面值。
#    现改为运行时解析：环境变量 → 凭据文件 → 空（并给出提示）。
def _resolve_obsidian_key():
    k = os.environ.get('OBSIDIAN_API_KEY')
    if k:
        return k.strip()
    for p in (os.environ.get('OBSIDIAN_KEY_FILE'),
              os.path.join(os.path.expanduser('~'), '.obsidian_api_key'),
              r'G:\deeeseek\secrets\obsidian-api.env'):
        try:
            if p and os.path.isfile(p):
                for line in open(p, encoding='utf-8', errors='ignore'):
                    line = line.strip()
                    if line.startswith('OBSIDIAN_API_KEY='):
                        return line.split('=', 1)[1].strip()
                    if line and '=' not in line:
                        return line
        except Exception:
            pass
    return ''


OBSIDIAN_KEY = _resolve_obsidian_key()
OLLAMA_BASE = 'http://localhost:11434'

# 规范目标目录
DEST_DIRS = {
    'code': os.path.join(ROOT, 'code'),
    'docs': os.path.join(ROOT, 'docs'),
    'docs_factor': os.path.join(ROOT, 'docs', 'factor_docs'),
    'docs_research': os.path.join(ROOT, 'docs', 'research'),
    'data_cache': os.path.join(ROOT, 'data', 'cache'),
    'output': os.path.join(ROOT, 'output'),
    'output_picks': os.path.join(ROOT, 'output', 'picks'),
    'wiki_raw_articles': os.path.join(ROOT, 'wiki', 'raw', 'articles'),
    'wiki_raw_papers': os.path.join(ROOT, 'wiki', 'raw', 'papers'),
    'wiki_raw_transcripts': os.path.join(ROOT, 'wiki', 'raw', 'transcripts'),
    'wiki_raw_assets': os.path.join(ROOT, 'wiki', 'raw', 'assets'),
    'wiki_entities': os.path.join(ROOT, 'wiki', 'entities'),
    'wiki_concepts': os.path.join(ROOT, 'wiki', 'concepts'),
    'wiki_comparisons': os.path.join(ROOT, 'wiki', 'comparisons'),
    'wiki_queries': os.path.join(ROOT, 'wiki', 'queries'),
    'ai_models': os.path.join(ROOT, 'ai', 'models'),
    'review': os.path.join(ROOT, 'docs', 'review_2026-08'),
}

# 确保目录存在
for d in DEST_DIRS.values():
    os.makedirs(d, exist_ok=True)
os.makedirs(INBOX, exist_ok=True)

# ============================================================
# 规则引擎：基于扩展名/命名模式快速判断（本地AI的兜底）
# ============================================================
RULE_CACHE = {}


def rule_classify(filename):
    """规则快速分类 → 返回 (目标目录键, 建议新名) 或 None"""
    ext = os.path.splitext(filename)[1].lower()
    base = os.path.splitext(filename)[0]

    # --- 明确排除/删除类 ---
    if filename in ('wikilink.md', '0') and os.path.getsize(os.path.join(ROOT, filename)) == 0:
        return ('DELETE', None)
    if filename.endswith('.base') or re.match(r'untitled-session-.*\.json', filename):
        return ('DELETE', None)
    if filename == 'FILE-MANAGEMENT-STANDARD.md' or filename in ('SOP.md',):
        return ('KEEP', None)

    # --- 代码类 ---
    if ext == '.py':
        if base.startswith('_') and 'verify' not in base:
            return ('code', filename)  # 临时脚本，保留在 code/
        return ('code', filename)
    if ext == '.bat':
        return ('code', filename)
    if ext == '.exe' or ext == '.msi':
        return ('DELETE', None)  # 安装包用完删除

    # --- 数据缓存 ---
    if ext == '.parquet':
        return ('data_cache', filename)

    # --- 选股/回测输出 ---
    if ext == '.csv':
        if base.startswith('pick'):
            return ('output_picks', filename)
        return ('output', filename)
    if ext == '.html':
        return ('output', filename)
    if ext == '.png' or ext == '.jpg':
        return ('wiki_raw_assets', filename)

    # --- 文档类 ---
    if ext == '.md':
        low = base.lower()
        if 'factor' in low and ('v1' in low or 'v2' in low or 'v3' in low):
            return ('docs_factor', filename)
        if 'spec' in low or 'methodology' in low or 'review' in low:
            return ('docs_factor', filename)
        if low.startswith(('c1_', 'c2_', 'm1_', 's1_', 'w1_')) or 'review' in low:
            return ('review', filename)
        return ('docs_research', filename)  # 默认研究笔记

    # --- 模型文件 ---
    if ext in ('.gguf', '.bin', '.safetensors'):
        return ('ai_models', filename)

    # --- 办公文档类（Word/Excel/PPT → 原始资料，知识化会提取内容） ---
    if ext in ('.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt'):
        return ('wiki_raw_articles', filename)

    # --- 文本类（文章/转录） ---
    if ext in ('.txt', '.text'):
        return ('wiki_raw_articles', filename)
    if ext == '.pdf':
        return ('wiki_raw_papers', filename)

    return None  # 无法判定 → 交给 AI


# ============================================================
# 本地 AI 分类（规则无法判定时）
# ============================================================
SYSTEM_CLASSIFY = """你是量化投资仓库的文件管理员。依据 FILE-MANAGEMENT-STANDARD.md 规范判断文件归属。
只输出一个 JSON，不要其他内容：
{"dest": "目标目录键", "newname": "建议文件名（含扩展名，保持原样可填空串）", "reason": "一句话理由"}

可选 dest 键：
- code: 可执行代码
- docs_factor: 因子方案/审批/检验报告
- docs_research: 研究笔记/阅读清单
- data_cache: 数据缓存
- output: 可再生结果
- output_picks: 选股表
- wiki_raw_articles: 原始文章
- wiki_raw_papers: 论文
- wiki_raw_transcripts: 转录
- wiki_raw_assets: 图片图表
- wiki_entities: 实体页
- wiki_concepts: 概念页
- wiki_comparisons: 对比页
- wiki_queries: 查询结果
- ai_models: 模型权重
- review: 复盘发现
- DELETE: 应删除的临时/0字节文件
"""


def ai_classify(filename, filepath):
    """调用本地 AI 判断归属"""
    try:
        import requests
        # 读取文件头（前2000字符）辅助判断
        preview = ''
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                preview = f.read(2000)
        except Exception:
            pass

        prompt = f"""文件名: {filename}
文件头预览: {preview[:800]}

请判断该文件应放入哪个目录。"""
        r = requests.post(
            f'{OLLAMA_BASE}/api/chat',
            json={
                'model': 'qwen2.5:7b',
                'messages': [
                    {'role': 'system', 'content': SYSTEM_CLASSIFY},
                    {'role': 'user', 'content': prompt},
                ],
                'stream': False,
                'options': {'temperature': 0.1, 'num_predict': 300},
            },
            timeout=120
        )
        r.raise_for_status()
        text = r.json()['message']['content']
        # 提取 JSON
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except Exception as e:
        print(f'  [AI分类失败] {type(e).__name__}: {e}')
    return None


# ============================================================
# 日志写入（wiki/log.md）
# ============================================================
def append_log(entries):
    """entries: list of {action, subject, reason, files}"""
    today = datetime.date.today().isoformat()
    lines = []
    for e in entries:
        lines.append(f'\n## [{today}] {e["action"]} | {e["subject"]}')
        lines.append(f'- 操作者: AI (文件整理代理)')
        lines.append(f'- 原因: {e["reason"]}')
        lines.append(f'- 影响: {e["files"]}')
        lines.append(f'- 备注: 依据 FILE-MANAGEMENT-STANDARD.md 自动执行')

    try:
        import requests
        with open(WIKI_LOG, 'r', encoding='utf-8') as f:
            current = f.read()
        # 通过 API 写入
        new_content = current + '\n'.join(lines)
        r = requests.put(
            f'{OBSIDIAN_API}/vault/log.md',
            headers={'Authorization': f'Bearer {OBSIDIAN_KEY}', 'Content-Type': 'text/markdown'},
            data=new_content.encode('utf-8'),
            verify=False,
            timeout=10
        )
        if r.status_code in (200, 204):
            print(f'  ✅ 日志已写入 wiki/log.md ({len(entries)} 条)')
        else:
            print(f'  ⚠️ 日志写入失败 HTTP {r.status_code}，本地追加')
            with open(WIKI_LOG, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines))
    except Exception as e:
        print(f'  ⚠️ 日志写入异常: {e}，本地追加')
        try:
            with open(WIKI_LOG, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines))
        except Exception:
            pass


# ============================================================
# 主整理流程
# ============================================================
def collect_targets():
    """收集需要处理的文件 —— 仅两个来源：
    1. _inbox/      用户放入的待整理文件
    2. _hermes_out/ Hermes 产出的文件（Hermes 运行后放置）
    """
    targets = []

    # 1. inbox 中的文件（用户放入）
    if os.path.isdir(INBOX):
        for f in os.listdir(INBOX):
            fp = os.path.join(INBOX, f)
            if os.path.isfile(fp) and not f.startswith('.'):
                targets.append((fp, 'user'))

    # 2. hermes_out 中的文件（Hermes 产出）
    hermes_out = os.path.join(ROOT, '_hermes_out')
    if os.path.isdir(hermes_out):
        for f in os.listdir(hermes_out):
            fp = os.path.join(hermes_out, f)
            if os.path.isfile(fp) and not f.startswith('.'):
                targets.append((fp, 'hermes'))

    return targets


def process_file(filepath, origin, dry_run):
    """处理单个文件 → (action, dest_path)"""
    filename = os.path.basename(filepath)
    fsize = os.path.getsize(filepath)

    # 规则分类
    rule = rule_classify(filename)
    dest_key = None
    newname = filename
    reason = ''

    if rule:
        dest_key, newname_rule = rule
        if dest_key == 'DELETE':
            return ('DELETE', None, f'规则判定：{filename} 为临时/0字节文件')
        if dest_key == 'KEEP':
            return ('KEEP', None, f'规范文件，不动')
        if newname_rule:
            newname = newname_rule

    if dest_key is None:
        # AI 分类
        print(f'  🤖 本地AI分类: {filename}')
        ai = ai_classify(filename, filepath)
        if ai and ai.get('dest') in DEST_DIRS:
            dest_key = ai['dest']
            if ai.get('newname'):
                newname = ai['newname']
            reason = f'AI分类: {ai.get("reason", "")}'
        else:
            return ('SKIP', None, f'无法分类：{filename}，留给人工')

    dest_dir = DEST_DIRS[dest_key]
    # 避免重名
    dest_path = os.path.join(dest_dir, newname)
    if os.path.exists(dest_path) and os.path.abspath(dest_path) != os.path.abspath(filepath):
        base, ext = os.path.splitext(newname)
        dest_path = os.path.join(dest_dir, f'{base}_{datetime.date.today().strftime("%Y%m%d")}{ext}')

    if os.path.abspath(dest_path) == os.path.abspath(filepath):
        return ('KEEP', None, f'{filename} 已在正确位置')

    if not dry_run:
        shutil.move(filepath, dest_path)
    return ('MOVE', dest_path, reason)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='预演，不实际移动')
    args = parser.parse_args()

    print('=' * 60)
    print('  文件整理代理 (FILE-MANAGEMENT-STANDARD.md)')
    print(f'  模式: {"预演 DRY-RUN" if args.dry_run else "执行"}')
    print('=' * 60)

    targets = collect_targets()
    if not targets:
        print('\n✅ 没有需要整理的文件')
        return

    print(f'\n发现 {len(targets)} 个文件待处理:\n')

    log_entries = []
    for filepath, origin in targets:
        filename = os.path.basename(filepath)
        print(f'📄 {filename} (来自: {origin})')

        action, dest, reason = process_file(filepath, origin, args.dry_run)

        if action == 'MOVE':
            print(f'  → 移动到: {os.path.relpath(dest, ROOT)}')
            log_entries.append({
                'action': 'update',
                'subject': f'文件整理: {filename}',
                'reason': reason or '按规范归位',
                'files': f'{filename} → {os.path.relpath(dest, ROOT)}',
            })
            # 知识化：原始资料类文件（移到 wiki/raw/ 下的）自动生成串联笔记
            dest_lower = dest.lower()
            if ('wiki' + os.sep + 'raw' + os.sep) in dest_lower or 'wiki/raw/' in dest_lower:
                print(f'  🤖 检测到原始资料，调用知识化模块生成 Obsidian 笔记...')
                try:
                    import subprocess
                    wcmd = ['D:/pyh/python.exe', '-E',
                            os.path.join(ROOT, 'code', 'file_to_wiki.py'), dest]
                    wenv = dict(os.environ)
                    wenv['PYTHONIOENCODING'] = 'utf-8'
                    wr = subprocess.run(wcmd, capture_output=True, text=True,
                                        encoding='utf-8', errors='ignore',
                                        timeout=300, env=wenv)
                    if wr.stdout:
                        print(wr.stdout[-600:])
                    if wr.stderr:
                        print(f'  [知识化stderr] {wr.stderr[-300:]}')
                except Exception as e:
                    print(f'  ⚠️ 知识化调用失败: {e}')
        elif action == 'DELETE':
            if not args.dry_run:
                try:
                    os.remove(filepath)
                    print(f'  → 已删除（临时/0字节）')
                except Exception as e:
                    print(f'  → 删除失败: {e}')
            else:
                print(f'  → [预演] 将删除')
            log_entries.append({
                'action': 'delete',
                'subject': f'清理: {filename}',
                'reason': reason,
                'files': filename,
            })
        elif action == 'KEEP':
            print(f'  → 保持不动')
        else:
            print(f'  → ⚠️ {reason}')

    # 写日志
    if log_entries and not args.dry_run:
        print()
        append_log(log_entries)
    elif log_entries and args.dry_run:
        print(f'\n[预演] 将记录 {len(log_entries)} 条日志')

    print('\n' + '=' * 60)
    print(f'  完成。处理 {len(targets)} 个文件，{len(log_entries)} 次变更')
    print('=' * 60)


if __name__ == '__main__':
    main()
