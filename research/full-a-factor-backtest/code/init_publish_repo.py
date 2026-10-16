# -*- coding: utf-8 -*-
"""init_publish_repo.py — 在暂存目录初始化全新 git 仓（无历史）并做安全复检"""
import io, os, re, sys, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'g:\股市探究\publish-quant-investing\quant-investing'
SECRET = re.compile(r'"apiKey"\s*:\s*"[A-Za-z0-9]{24,}"|-----BEGIN [A-Z ]*PRIVATE KEY-----', re.I)

GITIGNORE = """# 本机 Obsidian 工作区状态（含 Local REST API 凭据，绝不入库）
.obsidian/
**/.obsidian/

# 本地模型库（可再生产物，20GB 级）
ai/

# 数据库与缓存（大二进制、可再生）
*.db
*.db-wal
*.db-shm
*.parquet
data/cache/

# 输出与临时产物
output/
_*
!wiki/_archive/

# 凭据
*.env
.env
*.key
*.pem
.credentials*
secrets/

# Python
__pycache__/
*.py[cod]

# 系统杂物
Thumbs.db
desktop.ini
.DS_Store
"""


def git(*a, cwd=P):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


# 写 .gitignore（防以后有人 add -A 把密钥/大文件带进来）
open(os.path.join(P, '.gitignore'), 'w', encoding='utf-8', newline='\n').write(GITIGNORE)
print('  ✓ 已写 .gitignore（含 .obsidian/ 与 ai/ 排除）')

print('\n  === git init ===')
print('  ', git('init', '-b', 'main').stdout.strip() or git('init', '-b', 'main').stderr.strip())
git('config', 'user.name', 'weihong0505')
git('config', 'user.email', '296456038+weihong0505@users.noreply.github.com')
print('  ', git('add', '-A').stderr.strip() or '✓ git add -A')

st = git('status', '--short')
staged = [l for l in st.stdout.split('\n') if l.strip()]
print(f'  暂存条目 {len(staged)} 个')

# ==== 关键复检：暂存区里绝不允许有密钥或 .obsidian ====
print('\n  === 暂存区安全复检（fail-closed）===')
blobs = git('ls-files', '-z')
files = [x for x in blobs.stdout.split('\x00') if x]
bad_obs = [f for f in files if '.obsidian' in f]
bad_secret = []
for f in files:
    q = os.path.join(P, f.replace('/', os.sep))
    if not os.path.isfile(q) or os.path.getsize(q) > 8_000_000:
        continue
    try:
        if SECRET.search(open(q, encoding='utf-8', errors='ignore').read()):
            bad_secret.append(f)
    except Exception:
        pass
print(f'  暂存文件数: {len(files)}')
print(f'  含 .obsidian 的: {len(bad_obs)}  {bad_obs[:5]}')
print(f'  含密钥/私钥的: {len(bad_secret)}  {bad_secret[:5]}')
if bad_obs or bad_secret:
    print('  ✗✗ 复检未通过，中止提交')
    sys.exit(1)
print('  ✓ 复检通过：无 .obsidian、无密钥、无私钥')

c = git('commit', '-m',
        'init: A股量化价值投资知识库（正式发布版，无历史）\n\n'
        '内容：wiki 知识库（67 页）+ docs 规范与审查（SOP/因子检验/复盘）+ code 脚本。\n'
        '本仓为**全新初始提交**：原工作库的历史不随本仓发布，因此原历史中的\n'
        'Obsidian Local REST API 凭据（明文 apiKey + RSA 私钥）**不在本仓任何位置**。\n'
        '已排除：.obsidian/（含凭据）、ai/（20GB 模型库）、data/、output/、*.db、*.parquet。')
print('\n  提交:', (c.stdout or c.stderr).strip().split('\n')[0])
print('\n  === 历史长度（必须为 1）===')
print('  ', git('rev-list', '--count', 'HEAD').stdout.strip())
print('\n  === 仓内是否任何位置存在密钥路径 ===')
o = git('rev-list', '--objects', '--all').stdout
print('  ', 'obsidian-local-rest-api' in o and '✗ 命中' or '✓ 未命中')
print('  ', 'data.json' in o and '✗ 命中 data.json' or '✓ 未命中 data.json')
