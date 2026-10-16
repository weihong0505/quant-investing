# -*- coding: utf-8 -*-
"""prescan.py — 上传 GitHub 前的密钥/隐私/体积审计（只读）"""
import io, sys, os, re, subprocess, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r'e:\股市探究'
VAULT = os.path.join(ROOT, 'quant-investing')


def git(cwd, *args):
    return subprocess.run(['git', '-C', cwd, *args], capture_output=True,
                          text=True, encoding='utf-8', errors='replace').stdout


PATTERNS = [
    ('Obsidian Local REST API key', r'"apiKey"\s*:\s*"([A-Za-z0-9]{24,})"'),
    ('OpenAI/Ark 风格 sk- key', r'sk-[A-Za-z0-9]{20,}'),
    ('ARK_API_KEY 赋值', r'ARK_API_KEY\s*[=:]\s*\S+'),
    ('通用 api_key/secret 赋值', r'(api[_-]?key|secret|token|password|passwd)\s*[=:]\s*["\']?[A-Za-z0-9\-_\.]{16,}'),
    ('Bearer token', r'Bearer\s+[A-Za-z0-9\-_\.]{30,}'),
    ('私钥块', r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
]

print('=' * 74)
print('  上传 GitHub 前审计')
print('=' * 74)

for name, path in [('workspace', ROOT), ('vault(嵌套)', VAULT)]:
    files = [f for f in git(path, 'ls-files').split('\n') if f.strip()]
    print(f'\n--- {name}: 已跟踪 {len(files)} 个文件')
    hits = {}
    for f in files:
        fp = os.path.join(path, f)
        if not os.path.isfile(fp) or os.path.getsize(fp) > 3_000_000:
            continue
        try:
            t = open(fp, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        for nm, p in PATTERNS:
            m = re.search(p, t, re.I)
            if m:
                hits.setdefault(nm, []).append((f, m.group(0)[:60]))
    if hits:
        print('  ⚠ 命中:')
        for nm, v in hits.items():
            print(f'    {nm}: {len(v)} 个文件')
            for f, s in v[:5]:
                print(f'       {f}')
                print(f'         → {s}')
    else:
        print('  ✓ 已跟踪文件中未发现明文密钥')

    obs = [f for f in files if '.obsidian' in f]
    print(f'  已跟踪的 .obsidian 文件: {len(obs)} 个')
    for f in obs[:10]:
        print(f'    {f}')

# 历史中是否含密钥（即使当前已删）
print('\n--- 历史扫描（--all，查是否曾提交过密钥）')
for nm, p in PATTERNS[:2]:
    out = git(VAULT, 'log', '--all', '--oneline', f'-S{ p }', '--', '.obsidian/')
    print(f'  {nm}: {"命中 " + out.strip()[:80] if out.strip() else "无"}')

# 未跟踪的大文件（若 add -A 会被带入）
print('\n--- 未跟踪的大文件（>50MB，add -A 会带入）')
for name, path in [('workspace', ROOT), ('vault', VAULT)]:
    st = git(path, 'status', '--short', '--untracked-files=all').split('\n')
    big = []
    for line in st:
        if line.startswith('??'):
            rel = line[3:].strip().strip('"')
            fp = os.path.join(path, rel.replace('/', os.sep))
            if os.path.isfile(fp) and os.path.getsize(fp) > 50 * 1024 * 1024:
                big.append((os.path.getsize(fp) / 1e6, rel))
            elif os.path.isdir(fp):
                for r, d, fs in os.walk(fp):
                    for x in fs:
                        q = os.path.join(r, x)
                        try:
                            sz = os.path.getsize(q)
                        except Exception:
                            continue
                        if sz > 50 * 1024 * 1024:
                            big.append((sz / 1e6, os.path.relpath(q, path)))
    big.sort(reverse=True)
    print(f'  [{name}] {len(big)} 个')
    for sz, rel in big[:12]:
        print(f'    {sz:9.1f} MB  {rel}')

# 未跟踪文件总数
print('\n--- 未跟踪文件总数（add -A 的影响面）')
for name, path in [('workspace', ROOT), ('vault', VAULT)]:
    st = git(path, 'status', '--short', '--untracked-files=all').split('\n')
    n = sum(1 for l in st if l.startswith('??'))
    print(f'  [{name}] {n} 条未跟踪条目')
