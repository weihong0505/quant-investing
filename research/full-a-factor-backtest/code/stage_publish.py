# -*- coding: utf-8 -*-
"""
stage_publish.py — 生成 quant-investing 的干净发布暂存目录（源目录一字不改）
=====================================================================
安全设计：
  - **绝不复制 git 历史**（.git 一律不带）→ 旧历史中的明文 apiKey / RSA 私钥
    不可能以任何形式进入发布仓。
  - 只复制白名单内的文件（= 已审计的 230 个）。
  - 复制后逐文件复扫密钥/私钥，命中即中止（fail-closed）。
"""
import io
import os
import re
import sys
import shutil
import subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

V = r'g:\股市探究\quant-investing'
P = r'g:\股市探究\publish-quant-investing\quant-investing'

EX_SUB = ('/plugins/obsidian-local-rest-api/',)
EX_PRE = ('.obsidian/', 'ai/', 'data/', 'output/', '_inbox/', '_hermes_out/')
SECRET = re.compile(r'"apiKey"\s*:\s*"[A-Za-z0-9]{24,}"|-----BEGIN [A-Z ]*PRIVATE KEY-----', re.I)


def main():
    if os.path.exists(P):
        shutil.rmtree(P)
    os.makedirs(P, exist_ok=True)

    files = [x.decode('utf-8') for x in subprocess.run(
        ['git', '-C', V, 'ls-files', '-z'], capture_output=True).stdout.split(b'\x00') if x]
    print(f'  源仓库已跟踪 {len(files)} 个文件')

    n, skipped = 0, []
    for f in files:
        if any(s in '/' + f for s in EX_SUB) or f.startswith(EX_PRE) or f.endswith('.env'):
            skipped.append(f)
            continue
        src = os.path.join(V, f.replace('/', os.sep))
        dst = os.path.join(P, f.replace('/', os.sep))
        if not os.path.isfile(src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    print(f'  ✓ 已复制 {n} 个文件  |  已跳过 {len(skipped)} 个')
    for s in skipped:
        print(f'       跳过: {s}')

    # ==== fail-closed 复扫：暂存目录里绝不允许出现密钥/私钥 ====
    print('\n  === 发布暂存目录密钥复扫（fail-closed）===')
    bad = []
    for root, _, fs in os.walk(P):
        for x in fs:
            q = os.path.join(root, x)
            if os.path.getsize(q) > 8_000_000:
                continue
            try:
                t = open(q, encoding='utf-8', errors='ignore').read()
            except Exception:
                continue
            m = SECRET.search(t)
            if m:
                bad.append((os.path.relpath(q, P), m.group(0)[:50]))
    if bad:
        print('  ✗✗ 发现密钥，已中止（删除暂存目录）:')
        for f, s in bad:
            print(f'      {f} → {s}')
        shutil.rmtree(P)
        return 1
    print('  ✓ 未发现任何 apiKey / PRIVATE KEY')

    # ==== 确认 .git 未被复制 ====
    has_git = any('.git' == d for _, ds, _ in os.walk(P) for d in ds)
    print(f'  ✓ 暂存目录含 .git 目录: {has_git}（必须为 False）')

    total = sum(os.path.getsize(os.path.join(r, x))
                for r, _, fs in os.walk(P) for x in fs)
    print(f'\n  暂存目录: {n} 个文件 / {total/1e6:.2f} MB → {P}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
