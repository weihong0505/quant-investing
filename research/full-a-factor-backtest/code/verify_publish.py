# -*- coding: utf-8 -*-
"""verify_publish.py — 推送前最终核验：路径集合 + 密钥全清 + 加密钥二次扫描"""
import io, os, sys, re, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

V = r'g:\股市探究\quant-investing'
P = r'g:\股市探究\publish-quant-investing\quant-investing'


def git(cwd, *a):
    return subprocess.run(['git', '-C', cwd, *a], capture_output=True,
                          text=True, encoding='utf-8', errors='replace').stdout


src = [x for x in git(V, 'ls-files', '-z').split('\x00') if x]
pub = [x for x in git(P, 'ls-files', '-z').split('\x00') if x]
EX_PRE = ('.obsidian/', 'ai/', 'data/', 'output/', '_inbox/', '_hermes_out/')
EX_SUB = ('/plugins/obsidian-local-rest-api/',)
expect = [f for f in src
          if not f.startswith(EX_PRE) and not any(s in '/' + f for s in EX_SUB)
          and not f.endswith('.env')]
print(f'  源库跟踪      : {len(src)}')
print(f'  应发布(白名单): {len(expect)}')
print(f'  实际入库      : {len(pub)}')

missing = sorted(set(expect) - set(pub))
extra = sorted(set(pub) - set(expect))
print(f'\n  应发但未入库: {len(missing)}')
for f in missing:
    print(f'      {f}')
print(f'  入库但不在白名单: {len(extra)}')
for f in extra:
    print(f'      {f}')

print('\n  === 应当排除的（源库跟踪 + 未跟踪但存在）是否都没进库 ===')
excluded_prefix_hits = [f for f in pub if f.startswith(EX_PRE) or any(s in '/' + f for s in EX_SUB)]
print(f'  入库文件命中排除规则: {len(excluded_prefix_hits)}  {excluded_prefix_hits[:5]}')

# 新库工作区内所有 .obsidian 相关文件（含未跟踪）都不该在暂存目录
obs_on_disk = []
for r, ds, fs in os.walk(P):
    for x in fs:
        q = os.path.join(r, x)
        if '.obsidian' in q:
            obs_on_disk.append(os.path.relpath(q, P))
print(f'  暂存目录磁盘上的 .obsidian 文件: {len(obs_on_disk)}  {obs_on_disk[:5]}')

# 加密钥二次扫描：用更宽的规则
print('\n  === 加密钥二次扫描（宽规则）===')
WIDE = [re.compile(p, re.I) for p in [
    r'"apiKey"\s*:\s*"[A-Za-z0-9\-_]{20,}"',
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    r'sk-[A-Za-z0-9]{20,}',
    r'[A-Za-z0-9+/]{40,}={0,2}',          # 疑似 base64 长串
    r'Bearer\s+[A-Za-z0-9\-_\.]{30,}',
]]
hits = {}
for r, ds, fs in os.walk(P):
    if '.git' in r:
        continue
    for x in fs:
        q = os.path.join(r, x)
        try:
            if os.path.getsize(q) > 5_000_000:
                continue
            t = open(q, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        for i, rx in enumerate(WIDE):
            m = rx.search(t)
            if m and i == 3:
                # base64 宽规则噪音大：仅在含关键词时才报
                if not re.search(r'(key|secret|token|密码|凭据)', t, re.I):
                    continue
            if m:
                hits.setdefault(os.path.relpath(q, P), []).append((i, m.group(0)[:40]))
print(f'  命中文件 {len(hits)} 个')
for f, v in list(hits.items())[:12]:
    print(f'      {f}')
    for i, s in v[:2]:
        print(f'         规则{i}: {s}')
if not hits:
    print('      ✓ 零命中')

print('\n  === git 历史对象里是否含密钥路径 ===')
objs = git(P, 'rev-list', '--objects', '--all')
for kw in ['obsidian-local-rest-api', 'data.json', 'second-brain', 'periodic-notes', '.env']:
    print(f'      {kw:26} {"✗ 命中" if kw in objs else "✓ 未命中"}')
print(f'\n  提交数（应为 1）: {git(P, "rev-list", "--count", "HEAD").strip()}')
