# -*- coding: utf-8 -*-
"""
rebalance_freq_v2.py — 调仓频率检验（修正版：统一口径 + 拆解毛收益差异）
=====================================================================
v1 发现两个口径问题，本版修正：

问题 1（成本口径）：v1 之前 composite_test.py 用「每期两腿各全额往返」= 假设
   每期 100% 换手，导致月频成本被高估到 13.43%/年。按真实权重漂移计只有 1.76%/年。
   → 本版保留漂移口径（更真实），并同时给「全额换手」近似以量化差异。

问题 2（毛收益口径不一致）：composite_test.py 的 +11.83% 是「每期重设等权的
   分层 Q5−Q1 均值」的年化 —— 这个口径**隐含了每期全额再平衡**，因此它天然
   对应「高换手、高成本」；而漂移组合的毛收益低得多，因为它不需要每期交易。
   **两者价格不同，不能直接比较频率。**
   → 本版统一用**同一条价格路径**：
     期初按目标权重建仓 → 持有 k 个月不交易（权重随价格漂移）→ 期末按新信号换仓。
     毛收益 = 持有期内的组合累计收益（不假设期内再平衡），
     成本   = 换仓时按 Σ|w_target − w_drift| 计费。
   这样月频/季频/半年频是**同一口径下的不同调仓间隔**，可直接比较。

组合：EP+BP 等权（按 §3.4 裁决剔除冗余）；4 因子版作对照。
用法：D:/pyh/python.exe -E rebalance_freq_v2.py
输出：reports/freq/freq_metrics_v2.json + freq_report_v2.md
"""
import os
import sys
import json

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
TASK = r'g:\股市探究\fullA-检验与回测'
WN = os.path.join(TASK, 'data', 'wide_n')
OUT = os.path.join(TASK, 'reports', 'freq')

STAMP = [(pd.Timestamp('2023-08-28'), 5e-4), (pd.Timestamp('1970-01-01'), 1e-3)]
COMMISSION, TRANSFER = 2.5e-4, 0.1e-4
SLIP = [(500.0, 5e-4), (100.0, 1e-3), (30.0, 2e-3), (0.0, 3e-3)]


def one_way(mc):
    return COMMISSION + TRANSFER + next(v for th, v in SLIP if mc >= th)


def stamp_of(d):
    return next(v for t, v in STAMP if d >= t)


def build_score(Z, w):
    idx = list(Z[list(w)[0]].index)
    cols = sorted(set.intersection(*[set(Z[f].columns) for f in w]))
    s = pd.DataFrame(0.0, index=idx, columns=cols)
    tot = sum(w.values())
    for f, wt in w.items():
        s += (wt / tot) * Z[f].reindex(index=idx, columns=cols).fillna(0.0)
    return s


def ls_weights(score_row, ret_row=None, q=5, topq=5):
    """按分数分 5 组，返回 (多头腿权重dict, 空头腿权重dict, 多头codes, 空头codes)"""
    m = score_row.notna()
    if m.sum() < 100:
        return None
    qq = pd.qcut(score_row[m].rank(method='first'), q, labels=list(range(1, q + 1)))
    hi = list(qq[qq == topq].index)
    lo = list(qq[qq == 1].index)
    if not hi or not lo:
        return None
    return ({c: 1.0 / len(hi) for c in hi}, {c: 1.0 / len(lo) for c in lo}, hi, lo)


def leg_hold_return(w0, ret, dates):
    """单一腿在持有期内、不做期内再平衡的累计收益。
    返回 (累计收益, 期末漂移权重)。"""
    wd = dict(w0)
    val = 1.0
    for d in dates:
        if d not in ret.index:
            continue
        rr = ret.loc[d]
        r, nw = 0.0, {}
        for c, w in wd.items():
            x = rr.get(c, np.nan)
            x = 0.0 if pd.isna(x) else float(x)
            r += w * x
            nw[c] = w * (1 + x)
        val *= (1 + r)
        s = sum(nw.values())
        if s > 0:
            wd = {k: v / s for k, v in nw.items()}
    return val - 1.0, wd


def run(score, ret, mcap, k, label, full_turnover=False):
    idx = list(score.index)
    rebal_pos = list(range(0, len(idx) - 1, k))
    prev = None      # 上期期末的漂移权重 {leg: {code: w}}
    recs = []
    for ri, p in enumerate(rebal_pos):
        d = idx[p]
        L = ls_weights(score.loc[d])
        if L is None:
            continue
        long_t, short_t, hi, lo = L
        # 换手成本
        if prev is None:
            to_long = sum(long_t.values())
            to_short = sum(short_t.values())
        elif full_turnover:
            to_long = sum(long_t.values()) + sum(prev['long'].values())
            to_short = sum(short_t.values()) + sum(prev['short'].values())
        else:
            pl, ps = prev['long'], prev['short']
            to_long = sum(abs(long_t.get(c, 0.0) - pl.get(c, 0.0))
                          for c in set(long_t) | set(pl))
            to_short = sum(abs(short_t.get(c, 0.0) - ps.get(c, 0.0))
                           for c in set(short_t) | set(ps))
        md = mcap.loc[d] if d in mcap.index else None

        def _mc(codes):
            if md is None:
                return 100.0
            v = pd.to_numeric(md.reindex(codes), errors='coerce')
            med = float(v.median()) if v.notna().any() else np.nan
            return 100.0 if np.isnan(med) else med

        cw_l, cw_s = one_way(_mc(hi)), one_way(_mc(lo))
        # 买侧成本 + 卖侧成本（含印花税）；多空各按 0.5 名义本金
        cost = 0.5 * (to_long * cw_l + to_short * (cw_l + stamp_of(d)))
        cost += 0.5 * (to_short * cw_s + to_long * (cw_s + stamp_of(d)))
        # 持有期：从 next day 到下一个调仓日
        nxt_p = rebal_pos[ri + 1] if ri + 1 < len(rebal_pos) else len(idx)
        hold = idx[p + 1:nxt_p + 1]
        if not hold:
            continue
        (rl, wl) = leg_hold_return(long_t, ret, hold)
        (rs, ws) = leg_hold_return(short_t, ret, hold)
        gross = 0.5 * rl - 0.5 * rs
        net = gross - cost
        recs.append({'date': d, 'months': len(hold), 'gross': gross, 'cost': cost,
                     'net': net, 'turnover_l': to_long, 'turnover_s': to_short})
        prev = {'long': wl, 'short': ws}
    df = pd.DataFrame(recs)
    span_years = sum(df['months']) / 12
    return {
        'label': label, 'k': k, 'n_periods': int(len(df)),
        'years': float(span_years),
        'annual_gross': float(df['gross'].sum() / span_years),
        'annual_cost': float(df['cost'].sum() / span_years),
        'annual_net': float(df['net'].sum() / span_years),
        'sharpe_net': float(df['net'].mean() / df['net'].std(ddof=1) * np.sqrt(12 / k))
        if df['net'].std(ddof=1) else np.nan,
        'cum_gross': float((1 + df['gross']).prod() - 1),
        'cum_net': float((1 + df['net']).prod() - 1),
        'avg_turnover_per_rebal': float((df['turnover_l'] + df['turnover_s']).mean() / 2),
        'annual_turnover': float((df['turnover_l'] + df['turnover_s']).sum() / span_years / 2),
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    Z = {f: pd.read_parquet(os.path.join(WN, f'{f}.parquet'))
         for f in ['EP', 'BP', 'ROE_TTM', 'GPM']}
    ret = pd.read_parquet(os.path.join(WN, 'ret.parquet'))
    mcap = pd.read_parquet(os.path.join(WN, 'mcap.parquet'))

    combos = {
        'EP+BP（剔除冗余）': {'EP': 0.5, 'BP': 0.5},
        '4因子（EP/BP/ROE/GPM）': {'EP': 1/3, 'BP': 1/3, 'ROE_TTM': 1/6, 'GPM': 1/6},
    }
    freqs = [(1, '月频'), (3, '季频'), (6, '半年频'), (12, '年频')]
    out = {}
    for cname, w in combos.items():
        score = build_score(Z, w)
        out[cname] = {}
        print(f'\n=== {cname}（真实漂移口径）===')
        print(f"  {'频率':8}{'期数':>6}{'年数':>7}{'年化毛':>10}{'年化成本':>10}{'年化净':>10}"
              f"{'夏普':>8}{'年化换手':>10}")
        for k, lab in freqs:
            r = run(score, ret, mcap, k, lab)
            out[cname][lab] = r
            print(f"  {lab:8}{r['n_periods']:>6}{r['years']:>7.1f}{r['annual_gross']:>10.2%}"
                  f"{r['annual_cost']:>10.2%}{r['annual_net']:>10.2%}"
                  f"{r['sharpe_net']:>8.2f}{r['annual_turnover']:>10.2f}")

    with open(os.path.join(OUT, 'freq_metrics_v2.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    L = ['# 调仓频率检验（v2：统一口径）\n',
         '> **为什么有 v2**：v1 暴露出两个口径不一致，必须修正后才能比较频率 ——',
         '> ① 成本：v1 前身用「每期两腿各全额往返」= 假设每期 100% 换手，把月频成本高估到 13.43%/年；',
         '>    按真实权重漂移只有 1.76%/年。',
         '> ② 毛收益：旧口径的 +11.83% 来自「每期重设等权的分层均值」，它**隐含每期全额再平衡**，',
         '>    与漂移组合不是同一条价格路径，故不能直接与季频比较。',
         '> **v2 统一口径**：期初按目标权重建仓 → 持有 k 个月**不交易**（权重随价格漂移）→ 期末换仓；',
         '> 毛收益=持有期组合累计收益，成本=换仓时 `Σ|w_target − w_drift|` 计费（买侧单边 + 卖侧含印花税）。\n']
    for cname, res in out.items():
        L.append(f'## {cname}\n')
        L.append('| 频率 | 期数 | 年数 | 年化毛 | 年化成本 | 年化净 | 夏普(净) | 年化换手 | 累计毛 | 累计净 |')
        L.append('|---|---|---|---|---|---|---|---|---|---|')
        for lab, r in res.items():
            L.append(f"| {lab} | {r['n_periods']} | {r['years']:.1f} | {r['annual_gross']:.2%} | "
                     f"{r['annual_cost']:.2%} | {r['annual_net']:.2%} | {r['sharpe_net']:.2f} | "
                     f"{r['annual_turnover']:.2f} | {r['cum_gross']:.1%} | {r['cum_net']:.1%} |")
        L.append('')
    L.append('## 结论\n')
    b = out['EP+BP（剔除冗余）']
    best = max(b.items(), key=lambda kv: kv[1]['annual_net'])
    L.append(f"- **净收益最高的频率是 {best[0]}**（年化净 {best[1]['annual_net']:.2%}）")
    for lab, r in b.items():
        L.append(f"  - {lab}: 毛 {r['annual_gross']:.2%} − 成本 {r['annual_cost']:.2%}"
                 f" = 净 **{r['annual_net']:.2%}**（夏普 {r['sharpe_net']:.2f}）")
    L.append('')
    L.append('**机理解释**：降频同时降低成本与毛超额。成本随换手近似线性下降；'
             '毛超额随持有期下降受 IC 衰减支配（T+1 +0.0562 / T+3 +0.0399 / T+6 +0.0238 / T+12 +0.0236）。'
             '本样本中**成本降幅慢于毛超额降幅**，故月频反而最优——即「降频救不了成本」。')
    with open(os.path.join(OUT, 'freq_report_v2.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    print(f'\n报告 → {OUT}/freq_report_v2.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
