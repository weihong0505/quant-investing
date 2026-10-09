# -*- coding: utf-8 -*-
"""
知识化模块 — 将原始文件转化为 Obsidian 笔记并串联现有 Wiki
============================================================
流程：
  1. 原始文件保留到 wiki/raw/{articles|papers|transcripts}/
  2. 本地 AI (Qwen2.5) 阅读原文，生成概念/实体知识页
  3. 知识页自动带 [[wikilinks]] 串联现有页面（基于 index.md 页面清单）
  4. 更新 index.md + log.md

用法：
  D:/pyh/python.exe -E G:/股市探究/quant-investing/code/file_to_wiki.py <文件路径> [--dry-run]
"""
import os
import re
import sys
import io
import json
import shutil
import datetime
import argparse
import urllib3

urllib3.disable_warnings()

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = r'G:\股市探究\quant-investing'
WIKI = os.path.join(ROOT, 'wiki')
INDEX = os.path.join(WIKI, 'index.md')
LOG = os.path.join(WIKI, 'log.md')
RAW_DIRS = {
    'articles': os.path.join(WIKI, 'raw', 'articles'),
    'papers': os.path.join(WIKI, 'raw', 'papers'),
    'transcripts': os.path.join(WIKI, 'raw', 'transcripts'),
}
OLLAMA_BASE = 'http://localhost:11434'
MODEL = 'qwen2.5:7b'
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


def ai_chat(prompt, system=None, temperature=0.3, max_tokens=2048):
    import requests
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    r = requests.post(
        f'{OLLAMA_BASE}/api/chat',
        json={'model': MODEL, 'messages': messages, 'stream': False,
              'options': {'temperature': temperature, 'num_predict': max_tokens}},
        timeout=180
    )
    r.raise_for_status()
    return r.json()['message']['content']


def read_index():
    """读取 index.md 提取现有页面清单（用于串联）"""
    try:
        with open(INDEX, encoding='utf-8') as f:
            text = f.read()
        pages = re.findall(r'\[\[([a-z0-9\-]+)\]\]', text)
        return sorted(set(pages))
    except Exception:
        return []


# ============================================================
# 办公格式文本提取
# ============================================================
OFFICE_EXTS = {'.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.pdf', '.txt', '.md', '.csv', '.html'}


def extract_text(filepath):
    """从任意常见办公格式提取文本内容"""
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)
    fsize = os.path.getsize(filepath)
    # 大文件截断保护（>2MB 只取前部分）
    max_bytes = 2 * 1024 * 1024

    try:
        # --- Word ---
        if ext == '.docx':
            from docx import Document
            doc = Document(filepath)
            parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    parts.append(para.text.strip())
            for table in doc.tables:
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    parts.append(' | '.join(cells))
            text = '\n'.join(parts)
            return f'[Word文档: {filename}]\n\n{text[:8000]}'

        # --- Excel ---
        if ext == '.xlsx':
            from openpyxl import load_workbook
            wb = load_workbook(filepath, read_only=True, data_only=True)
            parts = []
            for ws in wb.worksheets:
                parts.append(f'## 工作表: {ws.title}')
                for row in ws.iter_rows(values_only=True, max_row=50):
                    cells = [str(c) if c is not None else '' for c in row]
                    if any(cells):
                        parts.append(' | '.join(cells))
            text = '\n'.join(parts)
            return f'[Excel表格: {filename}]\n\n{text[:8000]}'

        # --- PPT ---
        if ext == '.pptx':
            from pptx import Presentation
            prs = Presentation(filepath)
            parts = []
            for i, slide in enumerate(prs.slides, 1):
                parts.append(f'## 幻灯片 {i}')
                for shape in slide.shapes:
                    if hasattr(shape, 'text') and shape.text.strip():
                        parts.append(shape.text.strip())
            text = '\n'.join(parts)
            return f'[PPT演示: {filename}]\n\n{text[:8000]}'

        # --- PDF ---
        if ext == '.pdf':
            import fitz  # pymupdf
            doc = fitz.open(filepath)
            parts = []
            for page in doc:
                parts.append(page.get_text())
            text = '\n'.join(parts)
            return f'[PDF文档: {filename}]\n\n{text[:8000]}'

        # --- 纯文本类 ---
        if ext in ('.txt', '.md', '.csv', '.html'):
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(8000)

        # --- 其他 ---
        if fsize <= max_bytes:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(8000)
        return f'[未支持的格式: {ext}，文件大小 {fsize} 字节]'

    except Exception as e:
        return f'[提取失败: {type(e).__name__}: {e}]'


def classify_raw_type(filename):
    """判断原始资料类型 → raw 子目录"""
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        return 'papers'
    if ext in ('.mp3', '.wav', '.m4a'):
        return 'transcripts'
    if ext in ('.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt'):
        return 'articles'
    return 'articles'  # .txt .md .html 默认文章


def copy_to_raw(src_path, dry_run=False):
    """复制原始文件到 raw/（保留原文件）"""
    filename = os.path.basename(src_path)
    raw_type = classify_raw_type(filename)
    dest_dir = RAW_DIRS[raw_type]
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, filename)
    if os.path.abspath(dest) == os.path.abspath(src_path):
        return raw_type, dest, '已在raw目录'
    if not dry_run:
        shutil.copy2(src_path, dest)
    return raw_type, dest, f'复制到 wiki/raw/{raw_type}/（原文件保留在 {os.path.dirname(src_path)}）'


# ============================================================
# AI 生成知识页
# ============================================================
SYSTEM_WIKI = """你是量化投资知识库编辑。将原始资料转化为 Obsidian 笔记页。

硬性要求：
1. 输出严格的 Markdown，含 YAML frontmatter：
   ---
   title: 页面标题
   created: YYYY-MM-DD
   updated: YYYY-MM-DD
   type: concept | entity | comparison
   tags: [来自受控词表]
   sources: [raw/xxx/文件名]
   confidence: 50   # 0-100 整数，越高越可信
   ---
2. 正文用中文，结构化（定义/要点/结论/相关页面）
3. 必须包含「相关页面」一节，用 [[wikilink]] 链接现有页面（只能链接清单里存在的页面）
4. 标签只能用：factor, value, quality, momentum, liquidity, size, sentiment, backtest, factor-test, regime, correlation, decay, data-source, pipeline, system, tool, decision, weight-change, market-event, policy, macro, research
5. 不要编造清单外的页面链接

现有页面清单（只能链接这些）：
{page_list}"""


def generate_wiki_page(filename, src_path, raw_type, page_list, dry_run=False):
    """AI 生成知识页"""
    # 用格式提取器读取原文（支持 docx/xlsx/pptx/pdf/txt 等）
    preview = extract_text(src_path)

    if not preview or preview.startswith('[提取失败]') or preview.startswith('[未支持'):
        return None, preview or '无法读取原文内容'

    today = datetime.date.today().isoformat()
    prompt = f"""请将以下资料转化为一篇 Obsidian 知识库笔记。

资料文件名: {filename}
资料类型: {raw_type}
原文:
{preview}

生成要求：
- 标题简洁，反映核心主题
- 提取 3-8 个关键要点
- 给出该资料与量化价值投资的相关性结论
- 相关页面链接现有清单中的页面（3-6个）
- slug（文件名）用 kebab-case"""

    system = SYSTEM_WIKI.format(page_list=', '.join(page_list) if page_list else '(无)')
    try:
        content = ai_chat(prompt, system=system, temperature=0.3, max_tokens=2500)
    except Exception as e:
        return None, f'AI生成失败: {type(e).__name__}: {e}'

    return content, None


def extract_slug(content, filename):
    """从 AI 输出提取文件名 slug"""
    # 尝试从 title 提取
    m = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
    title = m.group(1).strip() if m else os.path.splitext(filename)[0]
    # 转 kebab-case
    slug = re.sub(r'[^\w\u4e00-\u9fff]+', '-', title).strip('-').lower()
    slug = re.sub(r'-{2,}', '-', slug)
    return slug or 'untitled'


def postprocess_page(content, page_list, raw_type, raw_dest, filename):
    """修正 AI 输出的质量问题：日期、sources、无效链接"""
    today = datetime.date.today().isoformat()

    # 1. 修正日期（AI 可能幻觉）
    content = re.sub(r'^created:.*$', f'created: {today}', content, flags=re.MULTILINE)
    content = re.sub(r'^updated:.*$', f'updated: {today}', content, flags=re.MULTILINE)

    # 2. 修正 sources 为正确的 raw 相对路径
    raw_rel = os.path.relpath(raw_dest, WIKI).replace('\\', '/')
    content = re.sub(
        r'^sources:.*$',
        f'sources: [{raw_rel}]',
        content,
        flags=re.MULTILINE,
    )

    # 3. 剔除清单外链接：只保留存在于 page_list 的 [[wikilinks]]
    valid = set(page_list)
    def _fix_link(m):
        slug = m.group(1).strip()
        if slug in valid:
            return m.group(0)
        return slug  # 降级为纯文本（不加 [[]]）
    content = re.sub(r'\[\[([^\]]+)\]\]', _fix_link, content)

    # 4. 移除末尾 AI 追加的 slug: 行（避免与文件名不一致）
    content = re.sub(r'\n?slug:\s*\S+\s*$', '', content.strip())
    return content.strip() + '\n'


def write_wiki_page(content, page_list, raw_type, raw_dest, filename, dry_run=False):
    """写入知识页到 concepts/ 或 entities/，更新 index.md"""
    # 后处理：修正日期/来源/无效链接
    content = postprocess_page(content, page_list, raw_type, raw_dest, filename)

    slug = extract_slug(content, filename)
    # 判断类型：frontmatter type
    m = re.search(r'^type:\s*(\w+)', content, re.MULTILINE)
    ptype = m.group(1).strip() if m else 'concept'

    if ptype == 'entity':
        dest_dir = os.path.join(WIKI, 'entities', 'system')
    elif ptype == 'comparison':
        dest_dir = os.path.join(WIKI, 'comparisons')
    else:
        dest_dir = os.path.join(WIKI, 'concepts')
    os.makedirs(dest_dir, exist_ok=True)

    # 避免与现有页面重名
    dest = os.path.join(dest_dir, f'{slug}.md')
    n = 1
    while os.path.exists(dest):
        slug2 = f'{slug}-{n}'
        dest = os.path.join(dest_dir, f'{slug2}.md')
        n += 1

    if not dry_run:
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  ✅ 知识页已创建: wiki/{os.path.relpath(dest, WIKI)}')
    else:
        print(f'  [预演] 将创建: wiki/{os.path.relpath(dest, WIKI)}')

    return dest, slug


def update_index(new_page_path, dry_run=False):
    """更新 index.md 添加新页面条目"""
    rel = os.path.relpath(new_page_path, WIKI).replace('\\', '/')
    filename = os.path.basename(new_page_path)
    slug = os.path.splitext(filename)[0]
    today = datetime.date.today().isoformat()

    try:
        with open(INDEX, encoding='utf-8') as f:
            idx = f.read()
    except Exception:
        idx = ''

    # 已存在则不重复
    if f'[[{slug}]]' in idx:
        return False

    # 找到合适的分组（根据目录）
    if 'entities/' in rel:
        section = '## Entities — System'
    elif 'comparisons/' in rel:
        section = '## Comparisons'
    else:
        section = '## Concepts'

    entry = f'- [[{slug}]] — 由本地AI自动生成（{today}），来源: {rel}'
    if section in idx:
        # 在分组标题后插入（放在第一个条目后）
        lines = idx.split('\n')
        new_lines = []
        inserted = False
        in_section = False
        for line in lines:
            new_lines.append(line)
            if line.strip() == section:
                in_section = True
                continue
            if in_section and line.strip().startswith('- [[') and not inserted:
                new_lines.append(entry)
                inserted = True
            if in_section and line.strip().startswith('## ') and line.strip() != section:
                if not inserted:
                    new_lines.append(entry)
                break
        if not inserted:
            new_lines.append(entry)
        idx = '\n'.join(new_lines)
    else:
        idx += f'\n\n{section}\n\n{entry}\n'

    # 更新计数
    m = re.search(r'Total pages: (\d+)', idx)
    if m:
        idx = idx.replace(f'Total pages: {m.group(1)}', f'Total pages: {int(m.group(1)) + 1}')

    if not dry_run:
        with open(INDEX, 'w', encoding='utf-8') as f:
            f.write(idx)
        print(f'  ✅ index.md 已更新: [[{slug}]]')
    return True


def append_log(raw_type, raw_dest, page_dest, dry_run=False):
    """记录操作日志"""
    today = datetime.date.today().isoformat()
    entry = f"""
## [{today}] ingest | {os.path.basename(raw_dest)} 知识化
- **操作者**: AI (本地AI知识化)
- **原因**: 用户提供文件，转化为 Obsidian 笔记并串联 Wiki
- **影响**: 原始文件保留 {raw_dest}；知识页 {page_dest}；index.md 更新
- **备注**: 原文件未删除，知识页通过 [[wikilinks]] 与现有页面串联
"""
    if dry_run:
        return
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(entry)
        print('  ✅ log.md 已更新')
    except Exception as e:
        print(f'  ⚠️ 日志写入失败: {e}')


# ============================================================
# 主流程
# ============================================================
def process_file(src_path, dry_run=False):
    filename = os.path.basename(src_path)
    print(f'\n📄 处理: {filename}')

    # 1. 保留原文件到 raw/
    raw_type, raw_dest, raw_note = copy_to_raw(src_path, dry_run)
    print(f'  [1/4] 原文件: {raw_note}')

    # 2. 读取现有页面清单
    page_list = read_index()
    print(f'  [2/4] 现有可链接页面: {len(page_list)} 个')

    # 3. AI 生成知识页
    print(f'  [3/4] 本地AI阅读并生成知识页...')
    content, err = generate_wiki_page(filename, src_path, raw_type, page_list, dry_run)
    if err or not content:
        print(f'  ❌ {err or "生成失败"}')
        return False

    # 4. 写入 + 更新索引
    page_dest, slug = write_wiki_page(content, page_list, raw_type, raw_dest, filename, dry_run)
    if not dry_run:
        update_index(page_dest, dry_run)
    append_log(raw_type, raw_dest, page_dest, dry_run)

    print(f'  [4/4] 完成')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+', help='要知识化的文件路径')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    print('=' * 60)
    print('  文件知识化 → Obsidian 笔记串联')
    print(f'  模式: {"预演" if args.dry_run else "执行"}')
    print('=' * 60)

    for f in args.files:
        if not os.path.isfile(f):
            print(f'❌ 文件不存在: {f}')
            continue
        process_file(f, args.dry_run)

    print('\n' + '=' * 60)
    print('  完成')
    print('=' * 60)


if __name__ == '__main__':
    main()
