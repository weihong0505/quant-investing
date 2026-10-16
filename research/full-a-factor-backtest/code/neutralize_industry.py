# -*- coding: utf-8 -*-
"""
neutralize_industry.py — 申万一级行业内 z-score 中性化（E 步骤）
================================================================
规则来源（项目自身规范，不新造）：
  - value_investing_transition_v2.1 §3.1：估值因子（EP/BP）行业内 z-score，行业口径统一申万一级
  - multi_factor_value.py:18：金融股全部质量因子中性化；非金融 GPM/ROE/LEV 行业内 z-score
  - 复用 multi_factor_value.winsorize_zscore / industry_zscore（min_group=5，小行业回退全市场）
    —— 复用而非重写，避免口径与项目规则漂移

行业来源：yjbb 缓存 `所处行业`（申万二级）→ data_fetcher._SW2_TO_SW1（实测 128/128 = 100% 覆盖）
⚠️ 局限（如实声明）：yjbb 是**当前快照**（2026-06-30 报告期），无行业变更历史；
   历史行业归类变化（如个别公司行业调整）无法回溯。属已知近似。

⚠️ 关键设计决定：**无行业映射的股票直接排除并计数**，而不是填 "未知" 当作第 32 个行业
   —— 后者会让所有无行业股票被"中性化"到同一个伪行业，是真实的分析错误。

用法：D:/pyh/python.exe -E neutralize_industry.py
输出：data/panel_neutral.parquet + data/wide_n/{EP,BP,ROE_TTM,GPM,ret,mcap}.parquet
"""
import os
import sys
import glob

import numpy as np
import pandas as pd

sys.path.insert(0, r'g:\股市探究\quant-investing\code')
sys.stdout.reconfigure(encoding='utf-8')

TASK = r'g:\股市探究\fullA-检验与回测'
CACHE = r'g:\股市探究\quant-investing\code\data_cache'
WIDE = os.path.join(TASK, 'data', 'wide')
WIDE_N = os.path.join(TASK, 'data', 'wide_n')

from data_fetcher import _SW2_TO_SW1                      # noqa: E402
from multi_factor_value import (                          # noqa: E402
    winsorize_zscore, industry_zscore, FIN_KEYWORDS)

EST_FACTORS = ['EP', 'BP']          # 估值：行业内 z-score（含金融）
QUAL_FACTORS = ['ROE_TTM', 'GPM']   # 质量：非金融行业内 z-score；金融置 0


def build_industry_map():
    """从 yjbb 缓存构建 股票代码 → 申万一级。取「最新报告期」文件的映射。"""
    fs = sorted(glob.glob(os.path.join(CACHE, 'yjbb_*.parquet')))
    best = None
    for f in reversed(fs):
        d = pd.read_parquet(f)
        if '所处行业' not in d.columns:
            continue
        d = d[['股票代码', '所处行业']].dropna()
        if len(d) == 0:
            continue
        d = d.copy()
        d['code'] = d['股票代码'].astype(str).str.zfill(6)
        d['sw1'] = d['所处行业'].map(_SW2_TO_SW1)
        d = d[d['sw1'].notna()]
        if len(d) >= 5000:
            best = (os.path.basename(f), dict(zip(d['code'], d['sw1'])))
            break
    if best is None:
        raise SystemExit('✗ 无法从 yjbb 缓存构建行业映射')
    print(f'  行业映射来源: {best[0]} | 股票 {len(best[1]):,} 只 | '
          f'申万一级 {len(set(best[1].values()))} 个')
    return best[1]


def main():
    panel = pd.read_parquet(os.path.join(TASK, 'data', 'panel_fullA.parquet'))
    panel['date'] = pd.to_datetime(panel['date'])
    print(f'  面板 {panel.shape} | 股票 {panel.code.nunique():,}')

    ind = build_industry_map()
    panel['sw1'] = panel['code'].map(ind)
    n_all = panel['code'].nunique()
    n_ind = panel.loc[panel['sw1'].notna(), 'code'].nunique()
    print(f'  行业覆盖: {n_ind:,}/{n_all:,} 只 ({n_ind/n_all:.1%})；'
          f'缺行业 {n_all-n_ind:,} 只 **将排除**（不填"未知"充作行业）')

    # 金融股掩码（质量因子中性化）
    panel['is_fin'] = panel['sw1'].apply(
        lambda x: isinstance(x, str) and any(k in x for k in FIN_KEYWORDS))
    # 统计口径：按「股票」去重计数（同一股票跨月重复，且不可对布尔 Series 用
    # drop_duplicates().sum() —— 那返回的是唯一值个数 True/False=2，不是股票数）
    has_ind = panel[panel['sw1'].notna()]
    n_fin_stock = has_ind.loc[has_ind['is_fin'], 'code'].nunique()
    n_ind_stock = has_ind['code'].nunique()
    print(f'  金融股 {n_fin_stock:,} 只 / 有行业 {n_ind_stock:,} 只 '
          f'({n_fin_stock/max(1,n_ind_stock):.1%}) → 其质量因子置 0（中性化）')

    before = len(panel)
    panel = panel[panel['sw1'].notna()].copy()
    print(f'  排除无行业后: {len(panel):,} 行（-{before-len(panel):,}）')

    # 逐月末行业内中性化
    out = []
    for dt, g in panel.groupby('date'):
        g = g.copy()
        for f in EST_FACTORS:
            if f not in g.columns:
                continue
            g[f + '_N'] = industry_zscore(g, f, 'sw1', min_group=5)
        for f in QUAL_FACTORS:
            if f not in g.columns:
                continue
            z = industry_zscore(g, f, 'sw1', min_group=5)
            z.loc[g['is_fin'].values] = 0.0        # 金融股质量因子中性化
            g[f + '_N'] = z
        out.append(g)
    pn = pd.concat(out, ignore_index=True)
    print(f'  中性化完成: {len(pn):,} 行')

    os.makedirs(WIDE_N, exist_ok=True)
    pn.to_parquet(os.path.join(TASK, 'data', 'panel_neutral.parquet'), index=False)

    # 宽表（供 factor_test_suite）
    for f in EST_FACTORS + QUAL_FACTORS:
        col = f + '_N'
        w = pn.pivot_table(index='date', columns='code', values=col, aggfunc='last')
        w.to_parquet(os.path.join(WIDE_N, f'{f}.parquet'))
        print(f'  {f:9}_N 宽表 {w.shape}  非空率 {w.notna().mean().mean():.1%}')
    for nm, col in [('ret', 'ret_1m'), ('mcap', 'mcap')]:
        src = os.path.join(WIDE, f'{nm}.parquet')
        if os.path.exists(src):
            w = pd.read_parquet(src)
            # 对齐到中性化样本（同一股票集合）
            keep = [c for c in w.columns if c in set(pn['code'])]
            w = w[keep]
            w.to_parquet(os.path.join(WIDE_N, f'{nm}.parquet'))
            print(f'  {nm:9} 宽表 {w.shape}（已对齐中性化样本，{len(keep):,} 只）')

    # 中性化前后对比（量级体检）
    print('\n  中性化前后对比（中位 / 标准差）:')
    for f in EST_FACTORS + QUAL_FACTORS:
        a = pd.to_numeric(pn[f], errors='coerce')
        b = pd.to_numeric(pn[f + '_N'], errors='coerce')
        print(f'    {f:9} 原始 中位 {a.median():9.4f} sd {a.std():8.4f}'
              f'  → 中性化 中位 {b.median():7.4f} sd {b.std():6.4f}')
    print(f'\n✓ 中性化面板 → {TASK}/data/panel_neutral.parquet')
    print(f'✓ 中性化宽表 → {WIDE_N}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
