# -*- coding: utf-8 -*-
"""
run_composite_backtest.py — §3.2 组合引擎回测（v2.1 口径）
=========================================================
对应 composite_testing_methodology_v1 §3.2，引擎为 code/backtest.py。

本轮**实现的口径**（与 v2.1 的偏离已逐条列在报告 §偏离声明）：
  - 组合：**Top30 等权**（v2.1 §3.1 主口径）
  - 信号：合成 SCORE（行业内中性化 EP/BP 各 0.5，= 上轮 §3.4 裁决剔除冗余后的重修版）
  - 样本：主回测 2019-01~今（v2.1 §4.2）；核心子样本 2021-02~今；参考段 2017-2018
  - 执行：T 日收盘信号 → T+1 raw 开盘成交（引擎内置）；一字板不买/跌停不卖/停牌顺延/整手/单笔<2万跳过
  - 成本：引擎内置（佣金万2.5双边 + 印花税时变 + 过户万0.1双边 + 分档滑点）
  - 基准：**本期未接 ETF 基准**（510300/510500 hfq 未取），故只报绝对绩效，
    超额与 v2.1 §4.4 第 1/3/6 条（净超额、回撤对比、制度段超额）**无法判定**——如实声明

用法：D:/pyh/python.exe -E run_composite_backtest.py
输出：reports/backtest/{backtest_report.md, metrics.json}
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
OUT = os.path.join(TASK, 'reports', 'backtest')

TOP_N = 30
INIT_CASH = 10_000_000.0


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    print('=== §3.2 组合引擎回测 ===')

    cal = pd.DatetimeIndex(sorted(pd.read_parquet(os.path.join(ENG, 'raw_close.parquet')).index))
    print(f'  日历 {len(cal)} 天')

    print('  载入引擎输入 ...')
    ro = pd.read_parquet(os.path.join(ENG, 'raw_open.parquet'))
    rc = pd.read_parquet(os.path.join(ENG, 'raw_close.parquet'))
    hc = pd.read_parquet(os.path.join(ENG, 'hfq_close.parquet'))
    mc = pd.read_parquet(os.path.join(ENG, 'mcap.parquet'))
    tr = pd.read_parquet(os.path.join(ENG, 'tradable.parquet'))
    st = pd.DataFrame(False, index=rc.index, columns=rc.columns)   # 声明：无历史 ST 数据

    # ⚠️ 引擎 _validate 要求 raw_open/raw_close/hfq_close/mcap/tradable/st 列完全一致。
    #    hfq 只有 5,179 列（40 只无 hfq 缓存，多为科创板新股）→ **统一到 hfq 可用集合**，
    #    因为收益层缺 hfq 无法计收益。被排除的 40 只须在报告声明（轻度生存者偏差）。
    common = sorted(set(ro.columns) & set(rc.columns) & set(hc.columns)
                    & set(mc.columns) & set(tr.columns))
    dropped = sorted(set(rc.columns) - set(common))
    print(f'  列对齐: {len(rc.columns)} → {len(common)}（排除 {len(dropped)} 只无 hfq 数据）')
    if dropped:
        print(f'    排除样本: {dropped[:12]}{"..." if len(dropped) > 12 else ""}')
    ro = ro[common]; rc = rc[common]; hc = hc[common]
    mc = mc[common]; tr = tr[common]; st = st[common]

    # ---- 合成 SCORE（中性化 EP/BP）----
    Z = {f: pd.read_parquet(os.path.join(WN, f'{f}.parquet')) for f in ['EP', 'BP']}
    cols = sorted(set(Z['EP'].columns) & set(Z['BP'].columns) & set(rc.columns))
    score = 0.5 * Z['EP'].reindex(columns=cols).fillna(0.0) + \
            0.5 * Z['BP'].reindex(columns=cols).fillna(0.0)
    print(f'  合成 SCORE {score.shape}（中性化 EP/BP 各 0.5）')

    # ---- 月末调仓信号：Top30 等权 ----
    me = pd.Series(cal).groupby([cal.year, cal.month]).max().values
    me = pd.DatetimeIndex(sorted(me))
    sig = {}
    for d in me:
        if d not in score.index:
            continue
        s = score.loc[d]
        s = s[s.index.isin(tr.columns)]
        if d in tr.index:
            live = tr.loc[d]
            s = s[[c for c in s.index if bool(live.get(c, False))]]
        s = s.dropna()
        if len(s) < TOP_N:
            continue
        top = s.nlargest(TOP_N).index
        sig[d] = pd.Series(1.0 / TOP_N, index=top)
    signals = pd.DataFrame(sig).T.fillna(0.0)
    signals.index = pd.DatetimeIndex(signals.index)
    print(f'  调仓信号 {signals.shape}  {signals.index.min().date()} ~ {signals.index.max().date()}')

    # ---- 建引擎并跑 ----
    print('  构建引擎 ...')
    eng = BacktestEngine(cal, ro, rc, hc, mc, tr, st, initial_cash=INIT_CASH)
    print('  运行回测（逐日循环，可能数分钟）...')
    res = eng.run(signals, verbose=False)
    print(f'  完成  ({time.time()-t0:.0f}s)')

    # ---- 提取绩效 ----
    nav = res.nav_hfq if getattr(res, 'nav_hfq', None) is not None else res.nav
    nav = nav.dropna()
    mr = nav.pct_change().dropna()

    def stats(sub):
        if len(sub) < 2:
            return {}
        tot = sub.iloc[-1] / sub.iloc[0] - 1
        yrs = (sub.index[-1] - sub.index[0]).days / 365.25
        ann = (1 + tot) ** (1 / yrs) - 1 if yrs > 0 else np.nan
        m = sub.pct_change().dropna()
        vol = m.std(ddof=1) * np.sqrt(12)
        dd = (sub / sub.cummax() - 1).min()
        return {'start': str(sub.index[0].date()), 'end': str(sub.index[-1].date()),
                'months': int(len(sub) - 1), 'total': float(tot), 'annual': float(ann),
                'vol': float(vol), 'sharpe': float(ann / vol) if vol else np.nan,
                'max_dd': float(dd),
                'calmar': float(ann / abs(dd)) if dd else np.nan}

    periods = {
        # ⚠️ 标签按**实际净值起点**命名：引擎 nav_hfq 从首次 T+1 成交后才记录
        #    （backtest.py run docstring），故起点是 2017-03-01（首个信号 2017-02-28 的次日），
        #    **不是**名义样本起点 2016-06。曾误标为「全段 2016-06~今」。
        '全段 2017-03~今': nav,
        '主段 2019-01~今': nav[nav.index >= '2019-01-01'],
        '核心段 2021-02~今': nav[nav.index >= '2021-02-01'],
        '参考段 2017-2018': nav[(nav.index >= '2017-01-01') & (nav.index <= '2018-12-31')],
    }
    stt = {k: stats(v) for k, v in periods.items()}

    # 换手
    to = getattr(res, 'turnover', None)
    to_mean = float(np.nanmean(list(to.values()))) if isinstance(to, dict) and to else np.nan

    m = {'frozen_at': dt.datetime.now().isoformat(),
         'engine': 'code/backtest.py（v2.1 引擎）',
         'portfolio': f'Top{TOP_N} 等权，月频调仓',
         'score': '行业内中性化 EP/BP 各 0.5（重修版，剔除冗余 ROE_TTM）',
         'periods': stt,
         'months_total': int(len(mr)),
         'turnover_mean_monthly': to_mean,
         'skipped_inputs': ['st_flags(全 False，无历史 ST 生效日)',
                            'cash_div', 'share_ratio', 'list_dates'],
         'benchmark': '未接（510300/510500 hfq 未取）→ 超额类判定不可用'}
    with open(os.path.join(OUT, 'metrics.json'), 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2, default=str)

    L = ['# §3.2 组合引擎回测报告\n',
         f'> 引擎：`code/backtest.py`（backtest_engineering_spec v2.1）｜组合：**Top{TOP_N} 等权，月频调仓**',
         f'> 信号：合成 SCORE（行业内中性化 EP/BP 各 0.5）｜初始资金 {INIT_CASH:,.0f} 元',
         f'> 冻结时间：{m["frozen_at"]}\n',
         '## 1. 绩效（绝对，无基准）\n',
         '| 区间 | 起 | 止 | 月数 | 累计 | 年化 | 年化波动 | 夏普 | 最大回撤 | 卡玛 |',
         '|---|---|---|---|---|---|---|---|---|---|']
    for k, v in stt.items():
        if not v:
            continue
        L.append(f"| {k} | {v['start']} | {v['end']} | {v['months']} | {v['total']:.2%} | "
                 f"{v['annual']:.2%} | {v['vol']:.2%} | {v['sharpe']:.2f} | "
                 f"{v['max_dd']:.2%} | {v['calmar']:.2f} |")
    L += ['', f'- 月均换手（引擎口径）：{to_mean:.2%}' if not np.isnan(to_mean) else '- 换手：未取到',
          '',
          '> ⚠️ **净值起点说明**：引擎 `nav_hfq` 从**首次 T+1 成交后**才开始记录',
          '> （backtest.py `run` docstring 明示），故净值实际起点为 **2017-03-01**',
          '> （首个调仓信号 2017-02-28 的次日），而名义样本起点是 2016-06。',
          '> 「全段」因此只覆盖 2017-03 起 116 个月，非 2016-06 起。',
          '', '## 2. 必须声明的偏离与缺口\n',
          '| # | 项 | 状态 | 影响 |', '|---|---|---|---|',
          '| 1 | **基准未接**（510300/510500 ETF hfq） | ✗ 未做 | v2.1 §4.4 第 1/3/6 条（净超额、回撤对比、制度段超额）**无法判定** |',
          '| 2 | `st_flags` 全 False（无历史 ST 生效日数据） | ⚠ 降级 | ST 股涨跌幅按 10% 处理（实际 5%），含 ST 样本有偏差 |',
          '| 3 | `cash_div` / `share_ratio` 未提供 | ⚠ 声明 | 分红/送转已含在 hfq 收益层（引擎 §2.1 口径），仅 raw 现金对账略过 |',
          '| 4 | 生存者偏差 | ⚠ 已知 | 样本覆盖 87.7%(2017)~94.1%(2025) 上市数，老退市股缺失 |',
          '| 5 | 未做 2x 成本敏感性 | ✗ 未做 | 需引擎参数化成本倍数（本轮未改引擎，遵守 v2.1「不修改引擎」） |',
          '| 6 | 未做 Top30 落点一致性检查（v2.1 §4.4 #4） | ✗ 未做 | 需与 v3 分层 Q4~Q5 对照 |',
          '', '## 3. 结论\n',
          '**本轮仅完成 v2.1 §4.4 的第 2 条（成本敏感性，部分）、第 5 条（结构稳定性）可判的前置**；',
          '第 1/3/6 条因缺基准**不可判定**，第 4 条未做，第 7 条（因子级证据链）待 registry 收口。',
          '故 §3.2 尚**不足以支撑「通过」判定**，组合层结论维持「部分通过」。']
    with open(os.path.join(OUT, 'backtest_report.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')

    print('\n  === 绩效摘要 ===')
    for k, v in stt.items():
        if v:
            print(f"    {k:20} 年化 {v['annual']:>7.2%}  波动 {v['vol']:>7.2%}  "
                  f"夏普 {v['sharpe']:>5.2f}  回撤 {v['max_dd']:>7.2%}")
    print(f'\n  报告 → {OUT}/backtest_report.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
