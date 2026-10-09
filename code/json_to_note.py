# -*- coding: utf-8 -*-
"""
JSON → 笔记 脚本 — 用本地 AI 把 JSON 数据转化为 Wiki 笔记（type: query）
用法: python json_to_note.py <文件.json> [主题]
输出: wiki/queries/{slug}_{YYYYMMDD}.md

说明：文件名、落点、frontmatter 骨架由本脚本确定性生成（遵循
G:/股市探究/quant-investing/FILE-MANAGEMENT-STANDARD.md），AI 只负责正文、标签与置信度。
"""
import os
import sys
import json
import datetime
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import local_ai

# Wiki 配置（与 wiki_ingest.py 一致）
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

# 防小模型上下文溢出：JSON 序列化后截断到该字符数
MAX_JSON_CHARS = 4000


def load_json_text(file_path):
    """读取 JSON 文件并序列化为紧凑文本。返回 (text, truncated)。"""
    with open(file_path, encoding='utf-8-sig') as f:
        data = json.load(f)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    truncated = len(text) > MAX_JSON_CHARS
    return text[:MAX_JSON_CHARS], truncated


def slugify(text):
    """主题/标题转安全 slug（kebab-case，去非法字符）。"""
    s = text.strip().replace(' ', '-').replace('/', '-').replace('\\', '-')
    s = ''.join(c for c in s if c not in ':*?"<>|')
    return s[:40] or 'note'


def _yaml_str(s):
    """清洗字符串，避免破坏 YAML。"""
    return s.replace('\n', ' ').replace('"', '').replace("'", '')


def build_note(note, source_path, today_str, truncated):
    """由代码确定性组装 frontmatter + 正文。"""
    title = _yaml_str(note['title']) or 'note'
    src = _yaml_str(source_path.replace('\\', '/'))
    tags = ', '.join(_yaml_str(t) for t in note['tags'] if t)
    head = (
        '---\n'
        f'title: "{title}"\n'
        f'created: {today_str}\n'
        f'updated: {today_str}\n'
        'type: query\n'
        f'tags: [{tags}]\n'
        f'sources: ["{src}"]\n'
        f"confidence: {note['confidence']}\n"
        '---\n\n'
    )
    content = head + note['body'].strip() + '\n'
    if truncated:
        content += (
            f'\n> ⚠️ 源 JSON 超过 {MAX_JSON_CHARS} 字符，已截断，'
            f'本笔记仅覆盖前段数据。完整数据见源文件：`{src}`\n'
        )
    return content


def wiki_write(path, content):
    """通过 Obsidian Local REST API 写入，失败返回 False。"""
    try:
        r = requests.put(
            f'{OBSIDIAN_API}/vault/{path}',
            headers={'Authorization': f'Bearer {OBSIDIAN_KEY}', 'Content-Type': 'text/markdown'},
            data=content.encode('utf-8'),
            verify=False, timeout=10,
        )
        return r.status_code in (200, 204)
    except Exception:
        return False


def convert(file_path, topic):
    """把单个 JSON 文件转化为 Wiki 查询笔记，返回写入路径。"""
    today = datetime.date.today()
    today_str = today.isoformat()      # YYYY-MM-DD，用于 frontmatter
    stamp = today.strftime('%Y%m%d')   # YYYYMMDD，用于文件名

    print(f'[1/4] 读取 JSON: {file_path}')
    json_text, truncated = load_json_text(file_path)
    print(f'  序列化长度: {len(json_text)} 字符' + ('（已截断）' if truncated else ''))

    print('[2/4] 本地 AI 解读并结构化...')
    note = local_ai.json_to_note(json_text, topic)
    print(f"  标题: {note['title']}")
    print(f"  标签: {note['tags']}")
    print(f"  置信度: {note['confidence']}")

    print('[3/4] 组装笔记（代码确定性生成 frontmatter）...')
    filename = f'{slugify(note["title"])}_{stamp}.md'
    content = build_note(note, file_path, today_str, truncated)

    path = f'queries/{filename}'
    print(f'[4/4] 写入 Wiki: {path}')
    if wiki_write(path, content):
        print(f'  ✅ 已写入 {path}')
    else:
        local_path = os.path.join(WIKI_PATH, 'queries', filename)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  已写入本地: {local_path}')
    return path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python json_to_note.py <文件.json> [主题]')
        print('示例: python json_to_note.py docs/factor_docs/_tx_crosscheck.json 腾讯-新浪行情交叉验证')
        sys.exit(1)
    fpath = sys.argv[1]
    topic = sys.argv[2] if len(sys.argv) > 2 else '量化研究'
    convert(fpath, topic)
