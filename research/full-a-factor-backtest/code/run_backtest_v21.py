# -*- coding: utf-8 -*-
"""
run_backtest_v21.py — v2.1 §4.4 七条判定（含基准与 2x 成本）
==========================================================
在 §3.2 回测基础上补齐判定所需全部输入：
  - 基准：510300 / 510500 ETF 不复权价（主，真实可交易）+ 沪深300/中证500 价格指数（辅）
  - 2x 成本：引擎 TradeRecord.cost 含真实成本金额 → 逐月成本作为 NAV 拖累剔除后
             再按 2× 扣除，**精确重算**净值（不改引擎，遵守 v2.1「不修改引擎」）
  - 换手：引擎 actual_turnover / turnover_annualized

七条判定（v2.1 §4.4）：
  1 主段净超额>0（两级标签：≥3% 达标 / 0~3% 边际）
  2 2x 成本下净超额>0；观察线 1x 成本拖累 ≤ 毛超额 50%
  3 最大回撤不劣于同段双基准
  4 引擎一致性：Top30 净收益落在各因子 v3 分层 Q4~Q5（±1pp 月均）—— 本轮以
    composites 分层 Q5 年化 +12.70% 为参照做**近似**判定并声明
  5 结构稳定性：滚动 36m 超额无断点
  6 制度段切分：三段分别报净超额
  7 因子级证据链：入池因子全部通过 v3 检验（EP/BP 为淘汰/观察 → 不满足）

用法：D:/pyh/python.exe -E run_backtest_v21.py
输出：reports/backtest_v21/{report.md, metrics.json}
"""
import os
import sys
import json
import time
import datetime as dt

import numpy as np
import pandas as pd

sys.path.insert(0, r'g:\股市探究\quant-investing\code')
sys.stdout.reconfigure(encoding='utf-8')
from backtest import BacktestEngine            # noqa: E402

TASK = r'g:\股市探究\fullA-检验与回测'
ENG = os.path.join(TASK, 'data', 'engine')
WN = os.path.join(TASK, 'data', 'wide_n')
OUT = os.path.join(TASK, 'reports', 'backtest_v21')
TOP_N, INIT_CASH = 30, 10_000_000.0
SEGMENTS = {'2019-01~2020-08': ('2019-01-01', '2020-08-31'),
            '2020-08~2023-02': ('2020-09-01', '2023-02-28'),
            '2023-02~今': ('2023-03-01', '2030-01-01')}


def perf(nav, per_year=12):
    if nav is None or len(nav) < 2:
        return {}
    tot = nav.iloc[-1] / nav.iloc[0] - 1
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    ann = (1 + tot) ** (1 / yrs) - 1 if yrs > 0 else np.nan
    m = nav.pct_change().dropna()
    vol = m.std(ddof=1) * np.sqrt(per_year)
    dd = float((nav / nav.cummax() - 1).min())
    return {'total': float(tot), 'annual': float(ann), 'vol': float(vol),
            'sharpe': float(ann / vol) if vol else np.nan, 'max_dd': dd,
            'calmar': float(ann / abs(dd)) if dd else np.nan, 'months': int(len(nav) - 1)}


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    print('=== v2.1 §4.4 七条判定 ===')

    # ---- 引擎输入 ----
    ro = pd.read_parquet(os.path.join(ENG, 'raw_open.parquet'))
    rc = pd.read_parquet(os.path.join(ENG, 'raw_close.parquet'))
    hc = pd.read_parquet(os.path.join(ENG, 'hfq_close.parquet'))
    mc = pd.read_parquet(os.path.join(ENG, 'mcap.parquet'))
    tr = pd.read_parquet(os.path.join(ENG, 'tradable.parquet'))
    cal = pd.DatetimeIndex(sorted(rc.index))
    common = sorted(set(ro) & set(rc) & set(hc) & set(mc) & set(tr))
    ro, rc, hc, mc, tr = (x[common] for x in (ro, rc, hc, mc, tr))
    st = pd.DataFrame(False, index=rc.index, columns=common)
    print(f'  输入就绪 {len(common)} 只 / {len(cal)} 天')

    # ---- 信号 ----
    Z = {f: pd.read_parquet(os.path.join(WN, f'{f}.parquet')) for f in ['EP', 'BP']}
    cols = sorted(set(Z['EP'].columns) & set(Z['BP'].columns) & set(common))
    score = 0.5 * Z['EP'].reindex(columns=cols).fillna(0.0) + \
            0.5 * Z['BP'].reindex(columns=cols).fillna(0.0)
    me = pd.DatetimeIndex(sorted(pd.Series(cal).groupby([cal.year, cal.month]).max().values))
    sig = {}
    for d in me:
        if d not in score.index:
            continue
        s = score.loc[d].dropna()
        if d in tr.index:
            live = tr.loc[d]
            s = s[[c for c in s.index if bool(live.get(c, False))]]
        if len(s) < TOP_N:
            continue
        sig[d] = pd.Series(1.0 / TOP_N, index=s.nlargest(TOP_N).index)
    signals = pd.DataFrame(sig).T.fillna(0.0)
    signals.index = pd.DatetimeIndex(signals.index)
    print(f'  信号 {signals.shape}  {signals.index.min().date()}~{signals.index.max().date()}')

    # ---- 跑引擎 ----
    eng = BacktestEngine(cal, ro, rc, hc, mc, tr, st, initial_cash=INIT_CASH)
    res = eng.run(signals, verbose=False)
    nav1 = (res.nav_hfq if res.nav_hfq is not None else res.nav).dropna()
    print(f'  引擎完成 ({time.time()-t0:.0f}s)  NAV {len(nav1)} 点')

    # ---- 逐月成本 → 2x 成本净值 ----
    tdf = pd.DataFrame([{'date': t.date, 'cost': t.cost, 'amount': t.amount}
                        for t in res.trades])
    tdf['ym'] = pd.to_datetime(tdf['date']).dt.to_period('M')
    cost_m = tdf.groupby('ym')['cost'].sum() if len(tdf) else pd.Series(dtype=float)
    nav_ym = pd.Series(nav1.values, index=pd.DatetimeIndex(nav1.index)).copy()
    nav_ym.index = nav_ym.index.to_period('M')
    # 成本占当月期初净值比例
    drag = (cost_m / nav_ym.shift(1)).dropna() if len(cost_m) else pd.Series(dtype=float)
    r1 = nav1.pct_change().dropna()
    r1p = r1.copy(); r1p.index = r1p.index.to_period('M')
    extra = drag.reindex(r1p.index).fillna(0.0)
    r2 = r1p - extra.values          # 2x = 再扣一份成本
    # ⚠️ 2026-10-09 由独立对抗性审查抓出的致命 bug：
    #    旧写法 `nav2.index = nav1.index[:len(nav2)]` —— nav2 由 pct_change 后
    #    的收益序列构造，长度比 nav1 少 1，却被贴上 nav1 的**前** N 个索引，
    #    导致 2x 净值整体**早标一个月**：主段窗口从 2019-01-31 变成 2019-02-28，
    #    **丢掉 2019 年 2 月的 +22.0%**（NAV 6.5814M→8.0298M）。
    #    后果：主段 2x 年化被低估 2.75pp，并直接伪造出「vs 510500 转负」的伪结论。
    #    修法：2x 的日收益序列应**跳过首月**（因 pct_change 丢掉第一点），
    #    故索引取 nav1.index[1:1+len(nav2)]，与 1x 的收益序列同起点。
    # 构造 2x 净值：r2 是 116 期收益（对应 nav1 的第 2..117 期），
    # 首期补一个 0 收益（首日无收益），使长度与 nav1 一致 → 索引直接用 nav1.index。
    # ⚠️ 不可用 pd.concat([单元素Series, r2])：会触发 pandas 的 NaN 对齐把首点吃掉。
    assert len(r2) == len(nav1) - 1, f'r2 长度应为 {len(nav1)-1}，实为 {len(r2)}'
    nav2 = pd.Series(np.concatenate([[nav1.iloc[0]], (1 + r2.values).cumprod() * nav1.iloc[0]]),
                     index=pd.DatetimeIndex(nav1.index))
    total_cost = float(tdf['cost'].sum()) if len(tdf) else 0.0
    assert len(nav2) == len(nav1), f'2x 与 1x 长度须一致（{len(nav2)} vs {len(nav1)}）'
    assert nav2.index[0] == nav1.index[0] and nav2.index[-1] == nav1.index[-1], \
        '2x 与 1x 起止点必须一致'
    print(f'  成本合计 {total_cost:,.0f} 元 | 月数含成本 {len(drag)} | '
          f'2x 窗口 {nav2.index[0].date()}~{nav2.index[-1].date()}（与 1x 一致）')

    # ---- 基准（对齐到 NAV 月末日）----
    benches = {}
    for nm, f in [('510300ETF', 'bench_510300.parquet'), ('510500ETF', 'bench_510500.parquet'),
                  ('沪深300指数', 'bench_hs300_index.parquet'), ('中证500指数', 'bench_zz500_index.parquet')]:
        p = os.path.join(ENG, f)
        if not os.path.exists(p):
            continue
        b = pd.read_parquet(p)
        b['date'] = pd.to_datetime(b['date'])
        s = b.set_index('date')['close'].sort_index()
        s = s.reindex(nav1.index, method='ffill').dropna()
        if len(s) >= 2:
            benches[nm] = s / s.iloc[0] * nav1.iloc[0]

    # ---- 七条判定 ----
    ev = {}
    for seg, (a, b) in [('主段', ('2019-01-01', '2030-01-01')),
                        ('核心段', ('2021-02-01', '2030-01-01'))]:
        n1 = nav1[nav1.index >= a]
        n2 = nav2[nav2.index >= a]
        row = {'strategy_1x': perf(n1), 'strategy_2x': perf(n2)}
        for nm, s in benches.items():
            bs = s[s.index >= a]
            if len(bs) < 2:
                continue
            bp = perf(bs)
            row[f'excess_vs_{nm}_1x'] = row['strategy_1x']['annual'] - bp['annual']
            row[f'excess_vs_{nm}_2x'] = row['strategy_2x']['annual'] - bp['annual']
            row[f'bench_{nm}'] = bp
        ev[seg] = row

    # ---- 基准分红修正（ETF 不复权 → 全收益）----
    # 东财 push2his 被代理拦截，拿不到 ETF hfq。用 fund_etf_fund_info_em 的
    # **累计净值**(含分红再投) 与 **单位净值** 的年化差，精确量化分红拖累，
    # 加回基准年化后再算超额。实测：510300 +1.29%/年、510500 +1.99%/年。
    DIV_ADJ = {'510300ETF': 0.0129, '510500ETF': 0.0199}
    for seg, row in ev.items():
        for nm, adj in DIV_ADJ.items():
            k1, k2 = f'excess_vs_{nm}_1x', f'excess_vs_{nm}_2x'
            if k1 in row:
                row[k1 + '_corrected'] = row[k1] - adj
            if k2 in row:
                row[k2 + '_corrected'] = row[k2] - adj

    dd_strategy = perf(nav1[nav1.index >= '2019-01-01'])['max_dd']
    c3 = {}
    for nm, s in benches.items():
        ss = s[s.index >= '2019-01-01']
        if len(ss) >= 2:
            c3[nm] = {'bench_max_dd': perf(ss)['max_dd'],
                      'pass': bool(dd_strategy >= perf(ss)['max_dd'])}

    # 5 结构稳定性：滚动 36m 超额（vs 510300）
    c5 = {}
    for nm, s in benches.items():
        ex = (nav1.pct_change() - s.pct_change()).dropna()
        roll = ex.rolling(36).apply(lambda x: (1 + x).prod() - 1)
        rr = roll.dropna()
        if len(rr):
            c5[nm] = {'last_36m_excess': float(rr.iloc[-1]),
                      'min_36m_excess': float(rr.min()),
                      'neg_months': int((ex < 0).sum()), 'total_months': int(len(ex)),
                      'pass': bool(rr.iloc[-1] > 0 and rr.min() > -0.20)}
    # 6 制度段
    c6 = {}
    for nm, s in benches.items():
        d = {}
        for seg, (a, b) in SEGMENTS.items():
            n1 = nav1[(nav1.index >= a) & (nav1.index <= b)]
            bs = s[(s.index >= a) & (s.index <= b)]
            if len(n1) < 3 or len(bs) < 3:
                continue
            d[seg] = {'strategy': perf(n1)['annual'], 'bench': perf(bs)['annual'],
                      'excess': perf(n1)['annual'] - perf(bs)['annual']}
        c6[nm] = d

    # 2 成本拖累占毛超额
    c2 = {}
    for seg, row in ev.items():
        g = row['strategy_1x']['annual']
        n2 = row['strategy_2x']['annual']
        c2[seg] = {'cost_drag': g - n2, 'gross_excess_max': max(
            [v for k, v in row.items() if k.startswith('excess_vs_') and k.endswith('_1x')] or [np.nan]),
            'pass_2x_positive': bool(n2 > 0)}

    m = {'frozen_at': dt.datetime.now().isoformat(),
         'portfolio': f'Top{TOP_N} 等权月频，信号=中性化 EP/BP',
         'nav_points': int(len(nav1)), 'nav_start': str(nav1.index[0].date()),
         'nav_end': str(nav1.index[-1].date()),
         'total_cost_yuan': total_cost, 'trades': int(len(tdf)),
         'actual_turnover_annualized': float(getattr(res, 'turnover_annualized', 0.0) or 0.0),
         'benchmarks': list(benches.keys()),
         'excess': ev, 'c2_cost': c2, 'c3_drawdown': c3, 'c5_stability': c5, 'c6_segments': c6,
         'criterion_4': {'status': '近似判定', 'note': '用组合层分层 Q5 年化 +12.70% 作参照（±1pp 月均容差未严格实施）'},
         'criterion_7': {'status': '不满足', 'note': 'EP 淘汰 / BP 观察，均非「通过」'},
         'benchmark_caveat': 'ETF 为不复权价（东财 hfq 被代理拦截），除息分红未再投 → 基准略被低估、超额略被高估'}
    with open(os.path.join(OUT, 'metrics.json'), 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2, default=str)

    print('\n  === 超额（年化，含基准分红修正）===')
    for seg, row in ev.items():
        print(f'    {seg}:  策略1x {row["strategy_1x"]["annual"]:>7.2%}  '
              f'2x {row["strategy_2x"]["annual"]:>7.2%}')
        for nm in ['510300ETF', '510500ETF', '沪深300指数', '中证500指数']:
            a1 = row.get(f'excess_vs_{nm}_1x')
            a2 = row.get(f'excess_vs_{nm}_2x')
            c1 = row.get(f'excess_vs_{nm}_1x_corrected')
            if a1 is None:
                continue
            tail = f'  修正后 {c1:>+7.2%}' if c1 is not None else ''
            print(f'      vs {nm:12} 1x {a1:>+7.2%}  2x {a2:>+7.2%}{tail}')
    print(f'\n  报告 → {OUT}/metrics.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
