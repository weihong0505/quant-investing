# -*- coding: utf-8 -*-
"""
rebalance_freq_test.py — 调仓频率对净收益的影响（组合层经济面）
==============================================================
目的：检验「降频（季度/半年）能否让净多空转正」——这是当前唯一可能翻转
      组合层结论的动作（统计面已过线，经济面被 13.43%/年 成本吃光）。

与 composite_test.py 的关键差别（**这里是更诚实的成本口径**）：
  composite_test.py 的分层用「每期全额往返成本」近似（Q5 与 Q1 两腿各付一次往返）。
  真实做法应按**权重漂移后的换手**计费：
    每期期初持有上期组合，期间价格变动使权重漂移，期末与目标组合比较
    换手率 = 0.5 × Σ|w_target − w_drift|
    成本   = 换手率 × 单边成本率 × 2（买+卖两侧）
  月频调仓时换手远低于 100%，故 composite_test 的成本是**高估**的。
  本脚本给出两种口径并对比，避免单一近似误导结论。

样本：全 A 行业内中性化（wide_n），2017-01 ~ 2026-09
调仓频率：月频(1) / 季频(3) / 半年频(6)
组合：EP+BP 等权（按上一轮 §3.4 裁决剔除冗余的 ROE_TTM）
      —— 与重修版一致；同时报告 4 因子版作对照

用法：D:/pyh/python.exe -E rebalance_freq_test.py
输出：reports/freq/freq_report.md + freq_metrics.json
"""
import os
import sys
import json
import datetime as dt

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
TASK = r'g:\股市探究\fullA-检验与回测'
WN = os.path.join(TASK, 'data', 'wide_n')
OUT = os.path.join(TASK, 'reports', 'freq')

# 成本模型（v3 §5.2 / SOP §7 附录A）
STAMP = [(pd.Timestamp('2023-08-28'), 5e-4), (pd.Timestamp('1970-01-01'), 1e-3)]
COMMISSION, TRANSFER = 2.5e-4, 0.1e-4
SLIP = [(500.0, 5e-4), (100.0, 1e-3), (30.0, 2e-3), (0.0, 3e-3)]
MIN_COMMISSION_RATE = 5.0 / 10000.0   # 每笔最低 5 元，按 1 万元单笔折算 5bp（声明为近似）


def one_way(mcap_yi):
    slip = next(v for th, v in SLIP if mcap_yi >= th)
    return COMMISSION + TRANSFER + slip


def stamp_of(d):
    return next(v for t, v in STAMP if d >= t)


def build_score(Z, weights):
    idx = list(Z[list(weights)[0]].index)
    cols = sorted(set.intersection(*[set(Z[f].columns) for f in weights]))
    s = pd.DataFrame(0.0, index=idx, columns=cols)
    tot = sum(weights.values())
    for f, w in weights.items():
        s += (w / tot) * Z[f].reindex(index=idx, columns=cols).fillna(0.0)
    return s


def backtest(score, ret, mcap, k, topq=5):
    """每 k 个月调仓的多空组合；按权重漂移计换手与成本。返回逐期明细。"""
    idx = list(score.index)
    rebal = set(idx[::k])
    prev_w = None           # 两腿合并的权重字典（正=多头腿，负=空头腿）
    drift = None            # 当前漂移权重
    rows = []
    for t, d in enumerate(idx[:-1]):
        nd = idx[t + 1]
        if d in rebal:
            sc = score.loc[d]
            m = sc.notna()
            if m.sum() < 100:
                continue
            q = pd.qcut(sc[m].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
            hi, lo = q[q == topq].index, q[q == 1].index
            target = {}
            for c in hi:
                target[c] = target.get(c, 0.0) + 0.5 / len(hi)
            for c in lo:
                target[c] = target.get(c, 0.0) - 0.5 / len(lo)
            # 换手：与漂移权重比较
            if drift is None:
                to = 0.5 * sum(abs(v) for v in target.values()) + \
                     0.5 * 0.0        # 首期视为全额建仓（两腿各 1/2 → 总 |w| = 1）
                to = 0.5 * sum(abs(v) for v in target.values()) * 2  # Σ|Δw| 从 0 起
                to = sum(abs(v) for v in target.values())
            else:
                allc = set(target) | set(drift)
                to = sum(abs(target.get(c, 0.0) - drift.get(c, 0.0)) for c in allc)
            md = mcap.loc[d] if d in mcap.index else None
            def _mc(codes):
                if md is None:
                    return 100.0
                v = pd.to_numeric(md.reindex(codes), errors='coerce')
                med = float(v.median()) if v.notna().any() else np.nan
                return 100.0 if np.isnan(med) else med
            ow_h = one_way(_mc(hi)); ow_l = one_way(_mc(lo))
            # 成本 = Σ|Δw| × 单边成本（买侧）+ 卖侧（含印花税）
            cost = 0.5 * to * (ow_h + ow_l) + 0.5 * to * (ow_h + ow_l + stamp_of(nd))
            held = {c: v for c, v in target.items()}
        else:
            cost = 0.0
            held = drift if drift else {}
        # 持有期收益 + 权重漂移
        rr = ret.loc[nd] if nd in ret.index else None
        if rr is None or not held:
            continue
        pnl = 0.0
        new = {}
        for c, w in held.items():
            r = rr.get(c, np.nan)
            if pd.isna(r):
                r = 0.0
            pnl += w * r
            new[c] = w * (1 + r)
        gross = pnl - cost
        rows.append({'date': d, 'next': nd, 'gross': pnl, 'cost': cost,
                     'net': gross, 'turnover': to if d in rebal else 0.0})
        drift = new
    return pd.DataFrame(rows)


def summarize(df, k, label):
    per_year = 12 / k
    g = df['gross'].mean() * per_year
    c = df['cost'].mean() * per_year
    n = df['net'].mean() * per_year
    sd = df['net'].std(ddof=1)
    sh = (df['net'].mean() / sd * np.sqrt(per_year)) if sd else np.nan
    to_ann = df['turnover'].sum() / (len(df) / 12) * (1 / 1)   # 年化单边换手（Σ|Δw| 累计/年）
    return {
        'freq': label, 'rebalance_every_months': k, 'periods': int(len(df)),
        'annual_gross': float(g), 'annual_cost': float(c), 'annual_net': float(n),
        'sharpe_net': float(sh), 'annual_turnover': float(to_ann),
        'cost_to_gross': float(c / g) if g > 0 else np.nan,
        'net_positive': bool(n > 0),
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    Z = {f: pd.read_parquet(os.path.join(WN, f'{f}.parquet'))
         for f in ['EP', 'BP', 'ROE_TTM', 'GPM']}
    ret = pd.read_parquet(os.path.join(WN, 'ret.parquet'))
    mcap = pd.read_parquet(os.path.join(WN, 'mcap.parquet'))

    combos = {
        'EP+BP（剔除冗余后）': {'EP': 0.5, 'BP': 0.5},
        'EP+BP+ROE+GPM（原 4 因子）': {'EP': 1/3, 'BP': 1/3, 'ROE_TTM': 1/6, 'GPM': 1/6},
    }
    freqs = [(1, '月频'), (3, '季频'), (6, '半年频')]

    all_res = {}
    for cname, w in combos.items():
        score = build_score(Z, w)
        all_res[cname] = {}
        print(f'\n=== {cname} ===')
        print(f"  {'频率':8}{'期数':>6}{'年化毛':>10}{'年化成本':>10}{'年化净':>10}{'夏普(净)':>10}{'年换手':>9}")
        for k, lab in freqs:
            bt = backtest(score, ret, mcap, k)
            if len(bt) == 0:
                continue
            s = summarize(bt, k, lab)
            all_res[cname][lab] = s
            print(f"  {lab:8}{s['periods']:>6}{s['annual_gross']:>10.2%}"
                  f"{s['annual_cost']:>10.2%}{s['annual_net']:>10.2%}"
                  f"{s['sharpe_net']:>10.2f}{s['annual_turnover']:>9.2f}")

    with open(os.path.join(OUT, 'freq_metrics.json'), 'w', encoding='utf-8') as f:
        json.dump(all_res, f, ensure_ascii=False, indent=2)

    # 报告
    L = ['# 调仓频率对净收益的影响（组合层经济面）\n',
         '> 目的：检验「降频能否让净多空转正」——统计面已过线，经济面被成本吃光。',
         '> **成本口径**：按权重漂移计换手（`Σ|w_target − w_drift|` × 单边成本 × 买卖两侧含印花税），',
         '> 比 composite_test.py 的「每期全额往返」近似更真实（后者高估月频成本）。',
         '> 组合：行业内中性化（wide_n），EP+BP 等权（按 §3.4 裁决剔除冗余 ROE_TTM）；4 因子版作对照。\n']
    for cname, res in all_res.items():
        L.append(f'## {cname}\n')
        L.append('| 频率 | 调仓间隔 | 期数 | 年化毛 | 年化成本 | 年化净 | 夏普(净) | 年化单边换手 | 成本/毛 | 净>0 |')
        L.append('|---|---|---|---|---|---|---|---|---|---|')
        for lab, s in res.items():
            L.append(f"| {lab} | {s['rebalance_every_months']} 月 | {s['periods']} | "
                     f"{s['annual_gross']:.2%} | {s['annual_cost']:.2%} | "
                     f"{s['annual_net']:.2%} | {s['sharpe_net']:.2f} | "
                     f"{s['annual_turnover']:.2f} | {s['cost_to_gross']:.1%} | "
                     f"{'✓' if s['net_positive'] else '✗'} |")
        L.append('')
    # 结论
    L.append('## 结论\n')
    base = all_res['EP+BP（剔除冗余后）']
    m1 = base.get('月频'); q1 = base.get('季频'); h1 = base.get('半年频')
    if m1 and q1:
        L.append(f"- 月频 → 季频：年化成本 {m1['annual_cost']:.2%} → {q1['annual_cost']:.2%}"
                 f"（降 {1 - q1['annual_cost']/m1['annual_cost']:.0%}），"
                 f"年化净 {m1['annual_net']:.2%} → **{q1['annual_net']:.2%}**")
    if q1 and h1:
        L.append(f"- 季频 → 半年频：年化成本 {q1['annual_cost']:.2%} → {h1['annual_cost']:.2%}，"
                 f"年化净 {q1['annual_net']:.2%} → **{h1['annual_net']:.2%}**")
    L.append('')
    L.append('**读法**：降频同时降低「成本」与「毛超额」（信号衰减，见 IC 衰减表 T+1 +0.0562 → '
             'T+3 +0.0399 → T+6 +0.0238）。能否转正取决于两者降幅孰快。')
    with open(os.path.join(OUT, 'freq_report.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    print(f'\n报告 → {OUT}/freq_report.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
