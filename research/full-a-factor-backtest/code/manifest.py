# -*- coding: utf-8 -*-
"""manifest.py — 生成 quant-investing 的上传清单（只读）"""
import io, sys, os, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

V = r'g:\股市探究\quant-investing'
files = [f for f in subprocess.run(['git', '-C', V, 'ls-files'], capture_output=True,
                                   text=True, encoding='utf-8', errors='replace').stdout.split('\n') if f.strip()]

EXCLUDE_PREFIX = ('.obsidian/', 'ai/', 'data/', 'output/', '_inbox/', '_hermes_out/')
EXCLUDE_EXACT = ('.env',)
EXCLUDE_SUBSTR = ('/plugins/obsidian-local-rest-api/',)

up, ex = [], []
for f in files:
    p = os.path.join(V, f.replace('/', os.sep))
    sz = os.path.getsize(p) if os.path.isfile(p) else 0
    reason = None
    if f.startswith(EXCLUDE_PREFIX):
        reason = '目录排除'
    elif f in EXCLUDE_EXACT:
        reason = '凭据'
    elif any(s in '/' + f for s in EXCLUDE_SUBSTR):
        reason = '含明文 apiKey + RSA 私钥'
    elif f.endswith('.env'):
        reason = '凭据'
    (ex if reason else up).append((f, sz, reason or ''))

print('=' * 78)
print('  quant-investing 上传清单')
print('=' * 78)
print(f'\n  已跟踪 {len(files)} 个文件  →  上传 {len(up)} 个 / 排除 {len(ex)} 个')
print(f'  上传内容合计 {sum(s for _, s, _ in up)/1e6:.2f} MB')
print(f'  .git 历史     {sum(os.path.getsize(os.path.join(r, x)) for r, d, fs in os.walk(os.path.join(V, ".git")) for x in fs if os.path.isfile(os.path.join(r, x)))/1e6:.1f} MB')
print()

# 按顶层分组
from collections import defaultdict
g = defaultdict(lambda: [0, 0])
for f, sz, _ in up:
    top = f.split('/')[0] if '/' in f else '(根)'
    g[top][0] += 1
    g[top][1] += sz
print('  === 会上传（按顶层目录）===')
for k in sorted(g, key=lambda x: -g[x][1]):
    print(f'    {k:22} {g[k][0]:4d} 个  {g[k][1]/1e6:8.2f} MB')

print('\n  === 会排除 ===')
ge = defaultdict(lambda: [0, 0, set()])
for f, sz, r in ex:
    top = f.split('/')[0] if '/' in f else '(根)'
    ge[top][0] += 1
    ge[top][1] += sz
    ge[top][2].add(r)
for k in sorted(ge, key=lambda x: -ge[x][1]):
    print(f'    {k:22} {ge[k][0]:4d} 个  {ge[k][1]/1e6:8.2f} MB  原因: {"/".join(sorted(ge[k][2]))}')

print('\n  === 排除明细（密钥相关，逐文件）===')
for f, sz, r in ex:
    if 'apiKey' in r or '凭据' in r:
        print(f'    {f}   ({sz} B)  ← {r}')

print('\n  === 上传文件全清单 ===')
for f, sz, _ in sorted(up):
    print(f'    {sz:8d} B  {f}')
