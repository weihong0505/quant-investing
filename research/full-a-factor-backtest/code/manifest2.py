# -*- coding: utf-8 -*-
"""manifest2.py — 修正版清单（-z 空字符分隔以正确处理中文路径）+ 密钥精确定位"""
import io, sys, os, subprocess, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

V = r'g:\股市探究\quant-investing'
raw = subprocess.run(['git', '-C', V, 'ls-files', '-z'], capture_output=True).stdout
files = [x.decode('utf-8') for x in raw.split(b'\x00') if x]

print(f'  已跟踪 {len(files)} 个文件（-z 解析，中文路径正确）\n')

# 精确定位密钥所在文件
print('  === 密钥/私钥精确定位（逐文件内容扫描）===')
SECRET = re.compile(r'"apiKey"\s*:\s*"[A-Za-z0-9]{24,}"|-----BEGIN [A-Z ]*PRIVATE KEY-----', re.I)
secret_files = []
for f in files:
    p = os.path.join(V, f.replace('/', os.sep))
    if not os.path.isfile(p) or os.path.getsize(p) > 8_000_000:
        continue
    try:
        t = open(p, encoding='utf-8', errors='ignore').read()
    except Exception:
        continue
    m = SECRET.search(t)
    if m:
        secret_files.append((f, os.path.getsize(p), m.group(0)[:44]))
for f, sz, s in secret_files:
    print(f'    ⚠ {f}  ({sz/1024:.1f} KB)  → {s}')
if not secret_files:
    print('    ✓ 无')

EXCLUDE_SUBSTR = ('/plugins/obsidian-local-rest-api/',)
EXCLUDE_PREFIX = ('.obsidian/', 'ai/', 'data/', 'output/', '_inbox/', '_hermes_out/')

up, ex = [], []
for f in files:
    p = os.path.join(V, f.replace('/', os.sep))
    sz = os.path.getsize(p) if os.path.isfile(p) else 0
    reason = None
    if any(s in '/' + f for s in EXCLUDE_SUBSTR):
        reason = 'Obsidian Local REST API 插件（含明文 apiKey/私钥）'
    elif f.startswith(EXCLUDE_PREFIX):
        reason = '目录排除（本机状态/数据/可再生产物）'
    elif f.endswith('.env'):
        reason = '凭据文件'
    (ex if reason else up).append((f, sz, reason or ''))

print(f'\n  === 汇总 ===')
print(f'  上传 {len(up)} 个 / {sum(s for _, s, _ in up)/1e6:.2f} MB'
      f'   |   排除 {len(ex)} 个 / {sum(s for _, s, _ in ex)/1e6:.2f} MB')

from collections import defaultdict
g = defaultdict(lambda: [0, 0])
for f, sz, _ in up:
    top = f.split('/')[0] if '/' in f else '(根目录)'
    g[top][0] += 1; g[top][1] += sz
print('\n  === 会上传（按顶层）===')
for k in sorted(g, key=lambda x: -g[x][1]):
    print(f'    {k:14} {g[k][0]:4d} 个  {g[k][1]/1e6:8.3f} MB')

ge = defaultdict(lambda: [0, 0, set()])
for f, sz, r in ex:
    top = f.split('/')[0] if '/' in f else '(根目录)'
    ge[top][0] += 1; ge[top][1] += sz; ge[top][2].add(r)
print('\n  === 会排除（按顶层）===')
for k in sorted(ge, key=lambda x: -ge[x][1]):
    print(f'    {k:14} {ge[k][0]:4d} 个  {ge[k][1]/1e6:8.3f} MB   {"/".join(sorted(ge[k][2]))}')

print('\n  === 排除明细（逐文件）===')
for f, sz, r in sorted(ex):
    print(f'    {sz:9d} B  {f}')

# 抽检：上传清单里是否有个人/敏感性质内容
print('\n  === 上传内容关键词抽检（个人/敏感）===')
KW = ['微信', '聊天记录', '密码', '身份证', '手机号', '银行卡', '家庭', '住址', 'apiKey', 'token', 'secret']
hit = defaultdict(list)
for f, sz, _ in up:
    p = os.path.join(V, f.replace('/', os.sep))
    if not os.path.isfile(p) or sz > 3_000_000:
        continue
    try:
        t = open(p, encoding='utf-8', errors='ignore').read()
    except Exception:
        continue
    for k in KW:
        if k in t:
            hit[k].append(f)
for k, v in hit.items():
    print(f'    {k}: {len(v)} 个文件  例: {v[:3]}')
if not hit:
    print('    ✓ 未命中')
