# -*- coding: utf-8 -*-
"""verify_remote.py — 从 GitHub 实际拉回内容做密钥扫描（验证远端本身）"""
import io, os, sys, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

R = r'g:\股市探究\publish-quant-investing\remote-verify'
URL = 'https://github.com/weihong0505/quant-investing.git'
KEYS = [b'29556b9a95455c5e9964aa7900494051e9b15db2',
        b'71ff191a5531956390f102edacb6a4e71adcb34db',
        b'PRIVATE KEY', b'"apiKey"']


def sh(*a, cwd=None):
    return subprocess.run(a, cwd=cwd, capture_output=True)


if os.path.exists(R):
    import shutil
    shutil.rmtree(R)
print('  1) 从 GitHub 全新克隆 ...')
r = sh('git', 'clone', '--quiet', URL, R)
print(f'     {"✓ 克隆成功" if r.returncode == 0 else "✗ " + r.stderr.decode("utf-8", "replace")[:200]}')

print('\n  2) 拉下来的文件数')
z = sh('git', '-C', R, 'ls-files', '-z').stdout
files = [x.decode('utf-8') for x in z.split(b'\x00') if x]
print(f'     {len(files)} 个文件')

print('\n  3) 工作树内容密钥扫描')
hits = []
for f in files:
    q = os.path.join(R, f.replace('/', os.sep))
    if not os.path.isfile(q):
        continue
    d = open(q, 'rb').read()
    for k in KEYS:
        if k in d:
            hits.append((f, k.decode()[:26]))
print(f'     命中 {len(hits)} 处')
for f, k in hits:
    print(f'       ⚠ {f} → {k}')

print('\n  4) 全部 git 历史对象内容扫描（远端 clone 的完整历史）')
out = sh('git', '-C', R, 'cat-file', '--batch-all-objects', '--batch').stdout
blob_hits, n, pos = [], 0, 0
while pos < len(out):
    nl = out.find(b'\n', pos)
    if nl < 0:
        break
    h = out[pos:nl].split()
    if len(h) != 3:
        break
    sha, typ, size = h[0].decode(), h[1].decode(), int(h[2])
    body = out[nl + 1:nl + 1 + size]
    n += 1
    if typ == 'blob':
        for k in KEYS:
            if k in body:
                blob_hits.append((sha[:10], k.decode()[:26], size))
    pos = nl + 1 + size + 1
print(f'     远端对象总数 {n}；blob 命中 {len(blob_hits)} 处: {blob_hits[:5]}')

print('\n  5) 提交数 / 分支')
print(f'     {sh("git","-C",R,"rev-list","--count","HEAD").stdout.decode().strip()} 个提交')

ok = not hits and not blob_hits
print('\n  ' + ('✓✓ 远端验证通过：GitHub 上的仓不含任何密钥' if ok else '✗✗ 远端含密钥，需立即处理'))
sys.exit(0 if ok else 1)
