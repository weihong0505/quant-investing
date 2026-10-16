import re
p = r'g:\股市探究\quant-investing\docs\factor_docs\factor_registry.md'
t = open(p, encoding='utf-8').read()
lines = t.split('\n')
orig = [l for l in lines if re.match(r'^\| \d+ \|', l)]
back = [l for l in lines if re.match(r'^\| A\d \|', l)]
chg = [l for l in lines if re.match(r'^\| 20\d\d-\d\d-\d\d \|', l)]
print(f'  原始登记表数据行: {len(orig)}  (追加前为 21，应不变)')
print(f'  新增回填行 A1-A4 : {len(back)}')
print(f'  变更日志表行数    : {len(chg)}  (追加前为 5，应 +1)')
print()
secs = [l for l in lines if l.startswith('## ')]
print('  章节结构:')
for s in secs:
    print('   ', s)
print()
# 确认原行内容逐字节未变
open_bak = r'g:\股市探究\backup\migrate-20261009-0030\factor_registry.md.bak'
old = open(open_bak, encoding='utf-8').read()
print(f'  追加内容是否以原文件开头（原内容零改动）: {t.startswith(old.rstrip(chr(10))[:len(old)-30])}')
print(f'  原文件末尾 30 字符: {repr(old[-30:])}')
print(f'  新文件在原文末尾处衔接: {repr(t[len(old)-30:len(old)+40])}')
