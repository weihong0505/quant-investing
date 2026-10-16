# -*- coding: utf-8 -*-
"""
prep_wide.py — 把长面板转成 factor_test_suite 要的宽表 + 覆盖率体检
====================================================================
factor_test_suite.run_pipeline 的输入契约（读源码确认）：
  factor_table / ret_table / mcap_table : 宽表，index=月末 DatetimeIndex，columns=股票代码
  fin_table : 财务长表（用于行业映射，可空）

本脚本：
  1) 面板 → 4 个因子宽表（ROE_TTM / GPM / EP / BP）+ ret / mcap 宽表
  2) **覆盖率体检**：逐月末对比「面板股票数」与「A 股当期应有上市数」，
     缺口说明抓取失败造成的生存者偏差敞口 —— 不体检就报 IC 等于不知道样本是谁
  3) 输出到 data/wide/

用法：D:/pyh/python.exe -E prep_wide.py
"""
import os
import sys
import json

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
TASK = r'g:\股市探究\fullA-检验与回测'
WIDE = os.path.join(TASK, 'data', 'wide')

# A 股各年末上市公司数（公开常识口径，用于覆盖率对账；仅作量级锚点，非精确值）
LISTED_ANCHOR = {2017: 3485, 2018: 3584, 2019: 3777, 2020: 4154,
                 2021: 4685, 2022: 5079, 2023: 5346, 2024: 5386, 2025: 5400}

FACTORS = ['ROE_TTM', 'GPM', 'EP', 'BP']


def main():
    p = pd.read_parquet(os.path.join(TASK, 'data', 'panel_fullA.parquet'))
    p['date'] = pd.to_datetime(p['date'])
    print(f'面板 {p.shape} | 股票 {p.code.nunique():,} | 月份 {p.date.nunique()}')

    os.makedirs(WIDE, exist_ok=True)
    for f in FACTORS:
        w = p.pivot_table(index='date', columns='code', values=f, aggfunc='last')
        w.to_parquet(os.path.join(WIDE, f'{f}.parquet'))
        print(f'  {f:9} 宽表 {w.shape}  非空率 {w.notna().mean().mean():6.1%}')

    for nm, col in [('ret', 'ret_1m'), ('mcap', 'mcap')]:
        w = p.pivot_table(index='date', columns='code', values=col, aggfunc='last')
        w.to_parquet(os.path.join(WIDE, f'{name_of(nm)}.parquet'))
        print(f'  {nm:9} 宽表 {w.shape}  非空率 {w.notna().mean().mean():6.1%}')

    # 财务长表（行业映射用）：code, report_date, 行业列暂无 → 用空表占位并声明
    fin = p[['code', 'report_date']].drop_duplicates()
    fin.to_parquet(os.path.join(WIDE, 'fin.parquet'), index=False)
    print(f'  fin      长表 {fin.shape}（无行业列，行业中性化需另接申万映射）')

    # ---- 覆盖率体检 ----
    print('\n=== 覆盖率体检（防生存者偏差敞口不明）===')
    cnt = p.groupby('date')['code'].nunique()
    rows = []
    for yr, anchor in LISTED_ANCHOR.items():
        sub = cnt[(cnt.index >= f'{yr}-01-01') & (cnt.index <= f'{yr}-12-31')]
        if len(sub) == 0:
            continue
        med = int(sub.median())
        rows.append({'year': yr, 'panel_median': med, 'anchor': anchor,
                     'cover': med / anchor})
        print(f'  {yr}  面板中位 {med:5d} 只 / 参考上市数 {anchor:5d}  → 覆盖 {med/anchor:6.1%}')
    cov = pd.DataFrame(rows)
    cov.to_csv(os.path.join(TASK, 'output', 'coverage.csv'), index=False, encoding='utf-8-sig')

    # 逐月股票数（首尾）
    print('\n  逐月股票数（末 6 月）:')
    print('   ', cnt.tail(6).to_dict())

    worst = cov['cover'].min() if len(cov) else float('nan')
    print(f'\n  最低覆盖年: {worst:.1%}')
    if worst < 0.80:
        print('  ⚠ 覆盖不足 80% —— 生存者偏差敞口显著，IC 结论须标注为"覆盖不全"')
        print('    未覆盖部分主要是退市股（新浪/腾讯不服务早期退市股）')
    print(f'\n✓ 宽表 → {WIDE}')
    return 0


def name_of(x):
    return x


if __name__ == '__main__':
    sys.exit(main())
