# -*- coding: utf-8 -*-
"""finish_wide_n.py — 补齐 wide_n 的 ret/mcap（中性化样本对齐）

背景：neutralize_industry.py 已写出 panel_neutral.parquet 与四个因子宽表，
但收尾的对齐步骤未完成（进程被终止）。本脚本只补这一步，不重算中性化。
"""
import os
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
TASK = r'g:\股市探究\fullA-检验与回测'
WIDE = os.path.join(TASK, 'data', 'wide')
WIDE_N = os.path.join(TASK, 'data', 'wide_n')

pn = pd.read_parquet(os.path.join(TASK, 'data', 'panel_neutral.parquet'))
codes = set(pn['code'].astype(str))
print(f'  中性化面板: {len(pn):,} 行 | 股票 {len(codes):,}')

for nm, col in [('ret', 'ret_1m'), ('mcap', 'mcap')]:
    dst = os.path.join(WIDE_N, f'{nm}.parquet')
    # 直接从中性化面板重建（最可靠，无需过滤原宽表）
    w = pn.pivot_table(index='date', columns='code', values=col, aggfunc='last')
    w.to_parquet(dst)
    print(f'  {nm:5} 宽表 {w.shape}  非空率 {w.notna().mean().mean():.1%}  → {os.path.basename(dst)}')

print('\n  wide_n 目录内容:')
for f in sorted(os.listdir(WIDE_N)):
    p = os.path.join(WIDE_N, f)
    print(f'    {f:20} {os.path.getsize(p)/1e6:7.2f} MB')
print('\n✓ 完成')
