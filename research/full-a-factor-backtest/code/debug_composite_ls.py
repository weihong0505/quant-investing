# -*- coding: utf-8 -*-
"""debug_composite_ls.py — 查「合成 IC 正 但 净多空为负」的矛盾"""
import os, sys
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
TASK = r'g:\股市探究\fullA-检验与回测'
WN = os.path.join(TASK, 'data', 'wide_n')

Z = {f: pd.read_parquet(os.path.join(WN, f'{f}.parquet')) for f in ['EP','BP','ROE_TTM','GPM']}
ret = pd.read_parquet(os.path.join(WN, 'ret.parquet'))
mcap = pd.read_parquet(os.path.join(WN, 'mcap.parquet'))
W = {'EP':0.30/0.90,'BP':0.30/0.90,'ROE_TTM':0.15/0.90,'GPM':0.15/0.90}
idx = Z['EP'].index
cols = sorted(set.intersection(*[set(Z[f].columns) for f in W]))
score = pd.DataFrame(0.0, index=idx, columns=cols)
for f,w in W.items():
    score += w * Z[f].reindex(index=idx, columns=cols).fillna(0.0)

# 逐月明细：用 3 个月诊断
print('  逐月分层明细（抽 3 个月）:')
for d in [idx[10], idx[50], idx[100]]:
    i = list(idx).index(d)
    if i+1 >= len(idx): continue
    nxt = idx[i+1]
    sc, rr = score.loc[d], ret.loc[nxt]
    m = sc.notna() & rr.notna()
    print(f'\n  --- {d.date()} → 次月 {nxt.date()}  可比股票 {int(m.sum())}')
    if m.sum() < 100:
        print('      样本不足'); continue
    q = pd.qcut(sc[m].rank(method='first'), 5, labels=[1,2,3,4,5])
    for k in [1,2,3,4,5]:
        sel = q[q==k].index
        print(f'      Q{k}: n={len(sel):5d}  次月均收益 {rr[sel].mean():+.4%}')
    hi, lo = q[q==5].index, q[q==1].index
    print(f'      毛多空 = {rr[hi].mean()-rr[lo].mean():+.4%}')
    mc_h = np.nanmedian(mcap.reindex(columns=cols).loc[d].reindex(hi))
    mc_l = np.nanmedian(mcap.reindex(columns=cols).loc[d].reindex(lo))
    print(f'      Q5 中位市值 {mc_h:.1f} 亿 | Q1 中位市值 {mc_l:.1f} 亿')

# 关键：rank IC 与 分层收益 是否应一致
print('\n  === 一致性检验：正 IC 应给出正的分层价差 ===')
for d in [idx[10], idx[50], idx[100]]:
    i = list(idx).index(d)
    nxt = idx[i+1]
    sc, rr = score.loc[d], ret.loc[nxt]
    m = sc.notna() & rr.notna()
    ic = sc[m].rank().corr(rr[m].rank())
    q = pd.qcut(sc[m].rank(method='first'), 5, labels=[1,2,3,4,5])
    hi, lo = q[q==5].index, q[q==1].index
    ls = rr[hi].mean()-rr[lo].mean()
    print(f'    {d.date()}: rank IC={ic:+.4f}  毛多空={ls:+.4%}  -> {"一致" if (ic>0)==(ls>0) else "★不一致★"}')
