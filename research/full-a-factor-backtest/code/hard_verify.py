# -*- coding: utf-8 -*-
"""hard_verify.py — 发布仓的字节级硬校验（含 git 历史对象内容）
要点：**逐个 blob 解出内容再扫**，不依赖路径名匹配。"""
import io, os, re, sys, subprocess, zlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'g:\股市探究\publish-quant-investing\quant-investing'
KEYS = [b'29556b9a95455c5e9964aa7900494051e9b15db2',   # wiki vault 的 apiKey 前缀
        b'71ff191a5531956390f102edacb6a4e71adcb34db',   # 顶层 vault 的 apiKey 前缀
        b'PRIVATE KEY']


def run(*a):
    return subprocess.run(['git', '-C', P, *a], capture_output=True).stdout


print('  1) 工作树文件内容扫描（白名单 216 个）')
files = [x.decode('utf-8') for x in run('ls-files', '-z').split(b'\x00') if x]
wt_hits = []
for f in files:
    q = os.path.join(P, f.replace('/', os.sep))
    if not os.path.isfile(q):
        continue
    d = open(q, 'rb').read()
    for k in KEYS:
        if k in d:
            wt_hits.append((f, k.decode()[:24]))
print(f'     命中 {len(wt_hits)} 处: {wt_hits}')

print('\n  2) git 历史全部 blob 内容扫描（cat-file --batch-all-objects）')
out = subprocess.run(['git', '-C', P, 'cat-file', '--batch-all-objects', '--batch'],
                     capture_output=True).stdout
blob_hits = []
n = 0
# 解析 batch 输出：header 'sha type size\n' 后跟 size 字节内容 + '\n'
pos = 0
while pos < len(out):
    nl = out.find(b'\n', pos)
    if nl < 0:
        break
    header = out[pos:nl].split()
    if len(header) != 3:
        break
    sha, typ, size = header[0].decode(), header[1].decode(), int(header[2])
    body = out[nl + 1:nl + 1 + size]
    n += 1
    if typ == 'blob':
        for k in KEYS:
            if k in body:
                blob_hits.append((sha[:10], k.decode()[:24], size))
    pos = nl + 1 + size + 1
print(f'     对象总数 {n}；blob 命中 {len(blob_hits)} 处: {blob_hits[:5]}')

print('\n  3) 排除路径是否出现在任何提交中')
paths = [x.decode('utf-8') for x in run('ls-tree', '-r', '--name-only', '-z', 'HEAD').split(b'\x00') if x]
bad = [p for p in paths if '.obsidian' in p]
print(f'     HEAD 树中含 .obsidian 的路径: {len(bad)} {bad[:5]}')

print('\n  4) 汇总')
ok = (not wt_hits) and (not blob_hits) and (not bad)
print(f'     工作树密钥命中 {len(wt_hits)} | blob 密钥命中 {len(blob_hits)} | .obsidian 路径 {len(bad)}')
print('     ' + ('✓✓ 硬校验通过：发布仓任何位置都不含密钥' if ok else '✗✗ 未通过，禁止推送'))
sys.exit(0 if ok else 1)
