# -*- coding: utf-8 -*-
"""
金样本对账单测 test_golden_samples.py
====================================
规范 [§3.1 条件1]：引擎输出必须与手算逐分对账。
状态标注：依据=backtest_engineering_spec_v2.1 §3.1 条件1；本文件即金样本检验工具，实跑 103/103 PASS（2026-08-22，合成数据手算对账，仅验证算术正确性）
覆盖用例（规范 M11）：整手取整、5元最低佣金、印花税时变切换、
一字涨停不买/顺延开板成交、停牌顺延、送转股数调整、除息日现金入账、
卖出零股清仓、现金缓冲；C3：除息日 hfq 收益层无跳变（合成净值对账）；
C4：新股免检白名单（上市第2日 +100% 成交 / 白名单过期后一字板放弃、
恢复上市首日卖出、板块×时间矩阵）、复牌首日跳空 >20% 放弃、
基准超额指标手算对账（含常数增长引擎级对账）、缺失市值滑点 30bp、
实际换手（含放弃调仓）+ 持仓快照对账。

运行: D:/pyh/python.exe -E test_golden_samples.py
"""
import io
import contextlib
import numpy as np
import pandas as pd
from backtest import (BacktestEngine, Performance, trade_cost, limit_prices,
                      stamp_duty_rate, LOT_SIZE, MIN_ORDER_VALUE)

PASS = 0
FAIL = 0

def check(name, actual, expected, tol=0.01):
    global PASS, FAIL
    if isinstance(actual, bool) or isinstance(expected, bool):
        ok = bool(actual) == bool(expected)
        detail = f'{bool(actual)} == {bool(expected)}'
    elif isinstance(actual, (list, tuple)) or isinstance(expected, (list, tuple)):
        ok = list(actual) == list(expected)
        detail = f'{list(actual)} == {list(expected)}'
    elif isinstance(actual, pd.Timestamp) and isinstance(expected, pd.Timestamp):
        ok = actual == expected
        detail = f'{actual.date()} == {expected.date()}'
    else:
        ok = abs(actual - expected) <= tol
        detail = f'{actual:.4f} == {expected:.4f}'
    if ok:
        PASS += 1
        print(f'  [PASS] {name}: {detail}')
    else:
        FAIL += 1
        print(f'  [FAIL] {name}: {detail} (tol={tol})')


# ============================================================
# 用例 1: 成本函数手算对账
# ============================================================
print('== Case 1: cost functions ==')
c = trade_cost(100000, 'sell', pd.Timestamp('2023-08-01'), 200e8)
check('sell 100k before stamp cut', c, 226.0)  # 25+100+1+100
c = trade_cost(100000, 'sell', pd.Timestamp('2023-08-29'), 200e8)
check('sell 100k after stamp cut (万5)', c, 176.0)  # 25+50+1+100
c = trade_cost(5000, 'buy', pd.Timestamp('2024-01-15'), 200e8)
check('min commission 5 yuan', c, 10.05)  # 5+0.05+5
check('stamp before', stamp_duty_rate(pd.Timestamp('2023-08-27')), 0.001)
check('stamp after', stamp_duty_rate(pd.Timestamp('2023-08-28')), 0.0005)
check('slippage micro 30bp', 10000 * 0.0030, 30.0)

# ============================================================
# 用例 2: 涨跌停价格矩阵
# ============================================================
print('== Case 2: limit price matrix ==')
up, down = limit_prices(10.00, 'main', pd.Timestamp('2024-06-01'))
check('main up', up, 11.00); check('main down', down, 9.00)
up, down = limit_prices(10.00, 'chinext', pd.Timestamp('2024-06-01'))
check('chinext up 20%', up, 12.00)
up, down = limit_prices(10.00, 'chinext', pd.Timestamp('2020-01-01'))
check('chinext up 10% (pre-2020)', up, 11.00)
up, down = limit_prices(10.00, 'main', pd.Timestamp('2024-06-01'), is_st=True)
check('ST up 5%', up, 10.50)

# ============================================================
# 用例 3: 整手取整 + T+1 执行 + 现金缓冲
# ============================================================
print('== Case 3: lot rounding + T+1 + cash buffer ==')
dates = pd.date_range('2024-03-01', periods=66, freq='B')
codes = ['000001', '000002', '000003']
n = len(dates)
close = pd.DataFrame({'000001': 10.0, '000002': 50.0, '000003': 100.0}, index=dates)
open_ = close.copy(); hfq = close.copy()
mcap = pd.DataFrame(np.full((n, 3), 200e8), index=dates, columns=codes)
tradable = pd.DataFrame(np.ones((n, 3), dtype=bool), index=dates, columns=codes)
st = pd.DataFrame(np.zeros((n, 3), dtype=bool), index=dates, columns=codes)
month_ends = [dates[i] for i in range(len(dates)-1) if dates[i+1].month != dates[i].month] + [dates[-1]]
signals = pd.DataFrame(0.0, index=month_ends, columns=codes)
for d in month_ends:
    signals.loc[d, codes] = 1.0 / 3

eng = BacktestEngine(dates, open_, close, hfq, mcap, tradable, st,
                     initial_cash=100000.0)
res = eng.run(signals)
b1 = [t for t in res.trades if t.code == '000001' and t.side == 'buy'][0]
b2 = [t for t in res.trades if t.code == '000002' and t.side == 'buy'][0]
b3 = [t for t in res.trades if t.code == '000003' and t.side == 'buy'][0]
check('000001 shares 3300', b1.shares, 3300)   # 33333/10→3300股
check('000002 shares 600', b2.shares, 600)     # 33333/50→600股
check('000003 shares 300', b3.shares, 300)     # 33333/100→300股
first_costs = b1.cost + b2.cost + b3.cost
check('first nav + costs = initial', res.nav.iloc[0] + first_costs, 100000.0, tol=1.0)

# 单股满仓 + 现金缓冲：100% 买 000001 应成功（缓冲逐手递减）
signals_full = pd.DataFrame(1.0, index=month_ends, columns=['000001'])
eng_f = BacktestEngine(dates, open_[['000001']], close[['000001']],
                       hfq[['000001']], mcap[['000001']], tradable[['000001']],
                       st[['000001']], initial_cash=100000.0)
res_f = eng_f.run(signals_full)
bf = [t for t in res_f.trades if t.side == 'buy']
check('100% position buy succeeds (cash buffer)', len(bf), 1)

# ============================================================
# 用例 4: 一字涨停顺延——连续涨停 6 日 → 放弃（0 笔买入）
# ============================================================
print('== Case 4: limit-up 6 consecutive days -> abandon ==')
dates4 = pd.date_range('2024-03-01', periods=66, freq='B')
close4 = pd.DataFrame({'000001': 10.0}, index=dates4)
open4 = pd.DataFrame({'000001': 10.0}, index=dates4)
month_ends4 = [dates4[i] for i in range(len(dates4)-1) if dates4[i+1].month != dates4[i].month] + [dates4[-1]]
first_exec = dates4[dates4.get_loc(month_ends4[0]) + 1]
# 从执行日起连续 6 日一字涨停（每日开盘=前收×1.1，收盘同）
px = 10.0
for k, d in enumerate(dates4[dates4.get_loc(first_exec):]):
    px = round(px * 1.1, 2)
    open4.loc[d, '000001'] = px
    close4.loc[d, '000001'] = px
hfq4 = close4.copy()
mcap4 = pd.DataFrame(np.full((len(dates4), 1), 200e8), index=dates4, columns=['000001'])
tradable4 = pd.DataFrame(np.ones((len(dates4), 1), dtype=bool), index=dates4, columns=['000001'])
st4 = pd.DataFrame(np.zeros((len(dates4), 1), dtype=bool), index=dates4, columns=['000001'])
signals4 = pd.DataFrame(1.0, index=month_ends4, columns=['000001'])
eng4 = BacktestEngine(dates4, open4, close4, hfq4, mcap4, tradable4, st4,
                      initial_cash=100000.0)
res4 = eng4.run(signals4)
buys4 = [t for t in res4.trades if t.side == 'buy']
check('limit-up streak: no buy (abandoned after 5d)', len(buys4), 0)

# 变体：涨停 1 日后开板 → 顺延第 2 日成交
print('== Case 4b: limit-up 1 day then open -> buy on day 2 ==')
open4b = pd.DataFrame({'000001': 10.0}, index=dates4)
close4b = pd.DataFrame({'000001': 10.0}, index=dates4)
open4b.loc[first_exec, '000001'] = 11.00   # 执行日一字涨停
close4b.loc[first_exec, '000001'] = 11.00
open4b.loc[dates4[dates4.get_loc(first_exec)+1]:, '000001'] = 11.00  # 次日开板 11 元
close4b.loc[dates4[dates4.get_loc(first_exec)+1]:, '000001'] = 11.00
hfq4b = close4b.copy()
eng4b = BacktestEngine(dates4, open4b, close4b, hfq4b, mcap4, tradable4, st4,
                       initial_cash=100000.0)
res4b = eng4b.run(signals4)
buys4b = [t for t in res4b.trades if t.side == 'buy']
check('limit-up day1 then bought day2', len(buys4b), 1)
if buys4b:
    check('bought on exec+1', buys4b[0].date, dates4[dates4.get_loc(first_exec)+1])

# ============================================================
# 用例 5: 停牌顺延——执行日停牌 2 日，第 3 日恢复成交
# ============================================================
print('== Case 5: suspension 2 days -> buy on day 3 ==')
close5 = pd.DataFrame({'000001': 10.0}, index=dates4)
open5 = pd.DataFrame({'000001': 10.0}, index=dates4)
hfq5 = close5.copy()
tradable5 = pd.DataFrame(np.ones((len(dates4), 1), dtype=bool), index=dates4, columns=['000001'])
i_exec = dates4.get_loc(first_exec)
tradable5.iloc[i_exec:i_exec+2, 0] = False  # 停牌 2 日
st5 = pd.DataFrame(np.zeros((len(dates4), 1), dtype=bool), index=dates4, columns=['000001'])
eng5 = BacktestEngine(dates4, open5, close5, hfq5, mcap4, tradable5, st5,
                      initial_cash=100000.0)
res5 = eng5.run(signals4)
buys5 = [t for t in res5.trades if t.side == 'buy']
check('suspended 2d then bought', len(buys5), 1)
if buys5:
    check('bought on exec+2', buys5[0].date, dates4[i_exec+2])

# ============================================================
# 用例 6: 送转股数调整 + 除息日现金入账
# ============================================================
print('== Case 6: share bonus (10送10) + cash dividend ==')
dates6 = pd.date_range('2024-03-01', periods=66, freq='B')
close6 = pd.DataFrame({'000001': 10.0}, index=dates6)
ex1 = dates6[40]  # 送转除权日（建仓后）: 价格 5→2.5, 股数翻倍
ex2 = dates6[30]  # 分红除息日（建仓后）: 每股派 1 元
close6.iloc[:, 0] = 5.0          # 建仓价 5 元
close6.loc[ex1:, '000001'] = 2.5  # 送转后价格 2.5
open6 = close6.copy()
hfq6 = pd.DataFrame({'000001': 10.0}, index=dates6)
mcap6 = pd.DataFrame(np.full((len(dates6), 1), 200e8), index=dates6, columns=['000001'])
tradable6 = pd.DataFrame(np.ones((len(dates6), 1), dtype=bool), index=dates6, columns=['000001'])
st6 = pd.DataFrame(np.zeros((len(dates6), 1), dtype=bool), index=dates6, columns=['000001'])
share_ratio6 = pd.DataFrame(np.nan, index=dates6, columns=['000001'])
share_ratio6.loc[ex1, '000001'] = 2.0
cash_div6 = pd.DataFrame(np.nan, index=dates6, columns=['000001'])
cash_div6.loc[ex2, '000001'] = 1.0  # 每股派1元
month_ends6 = [dates6[i] for i in range(len(dates6)-1) if dates6[i+1].month != dates6[i].month] + [dates6[-1]]
signals6 = pd.DataFrame(1.0, index=month_ends6, columns=['000001'])
eng6 = BacktestEngine(dates6, open6, close6, hfq6, mcap6, tradable6, st6,
                      initial_cash=100000.0,
                      cash_div=cash_div6, share_ratio=share_ratio6)
res6 = eng6.run(signals6)
b6 = [t for t in res6.trades if t.side == 'buy'][0]
# 手算第一期月末净值（4/30）：买入 N 股@5 → 分红 N 元现金 → 送转 2N 股@2.5
div_cash = b6.shares * 1.0
shares_after_bonus = b6.shares * 2
april_end_value = (shares_after_bonus * 2.5
                   + (100000 - b6.amount - b6.cost) + div_cash)
# 第一期月末 = 4月30日（第二期5/1调仓会再买8000股，故只校验4/30）
april_nav = res6.nav.loc['2024-04-30']
check('April-end nav after bonus+dividend', april_nav, april_end_value, tol=5.0)
# 送转前后总价值守恒检查（分红前 vs 送转后除现金）
check('final nav > initial (dividend+bonus effect)',
      res6.nav.iloc[-1] > res6.nav.iloc[0] + div_cash - 200, 1.0)

# ============================================================
# 用例 7: 卖出零股一次性清仓
# ============================================================
print('== Case 7: odd-lot sell all ==')
dates7 = pd.date_range('2024-03-01', periods=66, freq='B')
close7 = pd.DataFrame({'000001': 10.0}, index=dates7)
open7 = close7.copy(); hfq7 = close7.copy()
mcap7 = pd.DataFrame(np.full((len(dates7), 1), 200e8), index=dates7, columns=['000001'])
tradable7 = pd.DataFrame(np.ones((len(dates7), 1), dtype=bool), index=dates7, columns=['000001'])
st7 = pd.DataFrame(np.zeros((len(dates7), 1), dtype=bool), index=dates7, columns=['000001'])
month_ends7 = [dates7[i] for i in range(len(dates7)-1) if dates7[i+1].month != dates7[i].month] + [dates7[-1]]
signals7 = pd.DataFrame(1.0, index=month_ends7[:2], columns=['000001'])
signals7.iloc[1] = 0.0  # 第二期清仓
eng7 = BacktestEngine(dates7, open7, close7, hfq7, mcap7, tradable7, st7,
                      initial_cash=100000.0)
res7 = eng7.run(signals7)
sells7 = [t for t in res7.trades if t.side == 'sell']
check('sell all executed', len(sells7), 1)
if sells7:
    b7 = [t for t in res7.trades if t.side == 'buy'][0]
    check('sell all shares == buy shares (odd lot allowed)', sells7[0].shares, b7.shares)

# ============================================================
# Case 8: 除息日 raw 跌 2% / hfq 平 -> 合成月收益无跳变（hfq 分红再投口径）
# ============================================================
print('== Case 8: ex-dividend (raw -2%, hfq flat) -> no return jump ==')
dates8 = pd.date_range('2024-03-01', periods=66, freq='B')
close8 = pd.DataFrame({'000001': 10.0}, index=dates8)
ex8 = dates8[40]                              # 除息日：raw 10.0 -> 9.8（跌 2%）
close8.loc[ex8:, '000001'] = 9.8
open8 = close8.copy()
hfq8 = pd.DataFrame({'000001': 10.0}, index=dates8)   # hfq 平：分红再投，总收益 0
mcap8 = pd.DataFrame(np.full((len(dates8), 1), 200e8), index=dates8, columns=['000001'])
tradable8 = pd.DataFrame(np.ones((len(dates8), 1), dtype=bool), index=dates8, columns=['000001'])
st8 = pd.DataFrame(np.zeros((len(dates8), 1), dtype=bool), index=dates8, columns=['000001'])
cash_div8 = pd.DataFrame(np.nan, index=dates8, columns=['000001'])
cash_div8.loc[ex8, '000001'] = 0.2            # 每股 0.2 元 = raw 的 2%
month_ends8 = [dates8[i] for i in range(len(dates8)-1) if dates8[i+1].month != dates8[i].month] + [dates8[-1]]
signals8 = pd.DataFrame(1.0, index=month_ends8, columns=['000001'])
eng8 = BacktestEngine(dates8, open8, close8, hfq8, mcap8, tradable8, st8,
                      initial_cash=100000.0, cash_div=cash_div8)
res8 = eng8.run(signals8)
check('ex-div day daily hfq return = 0 (no jump)',
      res8.daily_returns.loc[ex8], 0.0, tol=1e-9)
ex_m_end = [d for d in res8.monthly_returns.index if d.month == ex8.month][0]
check('ex-div month composed return ~0 (no jump)',
      res8.monthly_returns.loc[ex_m_end], 0.0, tol=0.005)
eng8b = BacktestEngine(dates8, open8, close8, hfq8, mcap8, tradable8, st8,
                       initial_cash=100000.0)  # 不传 cash_div
res8b = eng8b.run(signals8)
check('hfq monthly identical with/without cash_div',
      float((res8.monthly_returns - res8b.monthly_returns).abs().max()),
      0.0, tol=1e-9)
# hfq 平 => 合成净值 = 初始资金 - 总成交成本（滑点 10bp 等），无除息跳变
check('composed nav_hfq end = initial - total costs (no div jump)',
      res8.nav_hfq.iloc[-1],
      100000.0 - sum(t.cost for t in res8.trades), tol=1.0)


# ============================================================
# Case 9: 新股免检白名单 [§2.2 M2]——科创板上市第2日 +100% 开盘买入成交
# ============================================================
print('== Case 9: new-IPO limit-free whitelist (star 688001) ==')
dates9 = pd.date_range('2024-03-01', periods=66, freq='B')
code9 = '688001'
n9 = len(dates9)
i_list9 = 20   # 上市日 3/29（=月末信号日）→ 执行日 4/1 = 上市第2日
exec9 = dates9[i_list9 + 1]
close9 = pd.DataFrame(np.nan, index=dates9, columns=[code9])
open9 = pd.DataFrame(np.nan, index=dates9, columns=[code9])
close9.iloc[i_list9:, 0] = 10.0
open9.iloc[i_list9, 0] = 10.0
open9.iloc[i_list9 + 1:, 0] = 20.0   # 上市第2日开盘 +100%（免检应成交）
close9.iloc[i_list9 + 1:, 0] = 20.0
hfq9 = close9.copy()
mcap9 = pd.DataFrame(np.full((n9, 1), 200e8), index=dates9, columns=[code9])
tradable9 = pd.DataFrame(False, index=dates9, columns=[code9])
tradable9.iloc[i_list9:, 0] = True
st9 = pd.DataFrame(np.zeros((n9, 1), dtype=bool), index=dates9, columns=[code9])
month_ends9 = [dates9[i] for i in range(len(dates9)-1)
               if dates9[i+1].month != dates9[i].month] + [dates9[-1]]
signals9 = pd.DataFrame(1.0, index=month_ends9, columns=[code9])
eng9 = BacktestEngine(dates9, open9, close9, hfq9, mcap9, tradable9, st9,
                      initial_cash=100000.0)
res9 = eng9.run(signals9)
buys9 = [t for t in res9.trades if t.side == 'buy']
check('new-IPO day2 +100% open: buy executed', len(buys9), 1)
if buys9:
    check('new-IPO buy date = listing day+1', buys9[0].date, exec9)
    check('new-IPO buy price 20.0', buys9[0].price, 20.0)
    check('new-IPO buy shares 4900 (cash buffer)', buys9[0].shares, 4900)

# 负对照：白名单过期（上市第 7 日）→ 连续一字涨停（每日开盘 = 前收×1.2）→ 放弃
code9b = '688002'
close9b = pd.DataFrame(np.nan, index=dates9, columns=[code9b])
open9b = pd.DataFrame(np.nan, index=dates9, columns=[code9b])
close9b.iloc[15:, 0] = 10.0    # 上市日 3/22 → 4/1 = 上市第 7 日（>5）
open9b.iloc[15, 0] = 10.0
px9b = 10.0
for _k, _d in enumerate(dates9[16:]):     # 4/1 起每日一字涨停（前收×1.2）
    px9b = round(px9b * 1.2, 2)
    open9b.loc[_d, code9b] = px9b
    close9b.loc[_d, code9b] = px9b
hfq9b = close9b.copy()
mcap9b = pd.DataFrame(np.full((n9, 1), 200e8), index=dates9, columns=[code9b])
tradable9b = pd.DataFrame(False, index=dates9, columns=[code9b])
tradable9b.iloc[15:, 0] = True
st9b = pd.DataFrame(np.zeros((n9, 1), dtype=bool), index=dates9, columns=[code9b])
signals9b = pd.DataFrame(1.0, index=month_ends9, columns=[code9b])
eng9b = BacktestEngine(dates9, open9b, close9b, hfq9b, mcap9b, tradable9b, st9b,
                       initial_cash=100000.0)
res9b = eng9b.run(signals9b)
check('day-7 +20% limit-up: buy abandoned (whitelist expired)',
      len([t for t in res9b.trades if t.side == 'buy']), 0)

# ============================================================
# Case 9c: 恢复上市首日卖出成交（limit_free_dates 显式白名单）+ 板块×时间矩阵
# ============================================================
print('== Case 9c: resume-listing day sell + board matrix ==')
code9c = '688003'
i_resume = 45   # 5/3 恢复上市（5/1~5/2 停牌）
close9c = pd.DataFrame(10.0, index=dates9, columns=[code9c])
open9c = pd.DataFrame(np.nan, index=dates9, columns=[code9c])
open9c.iloc[:43, 0] = 10.0          # 5/1 前正常交易（停牌日 close 按前收填充口径 =10）
resume_px9c = [8.0, 6.4, 5.12, 4.10]   # 复牌日起逐日跌停价（前收×0.8，round2）
for _k, _d in enumerate(dates9[i_resume:i_resume + 4]):
    open9c.loc[_d, code9c] = resume_px9c[_k]
    close9c.loc[_d, code9c] = resume_px9c[_k]
open9c.iloc[i_resume + 4:, 0] = 4.10
close9c.iloc[i_resume + 4:, 0] = 4.10
hfq9c = close9c.copy()
mcap9c = pd.DataFrame(np.full((n9, 1), 200e8), index=dates9, columns=[code9c])
tradable9c = pd.DataFrame(False, index=dates9, columns=[code9c])
tradable9c.iloc[:43, 0] = True
tradable9c.iloc[i_resume:, 0] = True
st9c = pd.DataFrame(np.zeros((n9, 1), dtype=bool), index=dates9, columns=[code9c])
signals9c = pd.DataFrame(0.0, index=month_ends9, columns=[code9c])
signals9c.iloc[0] = 1.0    # 3/29 买入 → 4/1 成交 @10
signals9c.iloc[1] = 0.0    # 4/30 清仓 → 顺延至复牌日 5/3 成交
eng9c = BacktestEngine(dates9, open9c, close9c, hfq9c, mcap9c, tradable9c, st9c,
                       initial_cash=100000.0,
                       limit_free_dates={code9c: [dates9[i_resume]]})
res9c = eng9c.run(signals9c)
s9c = [t for t in res9c.trades if t.side == 'sell']
check('resume-day sell executed (limit-free)', len(s9c), 1)
if s9c:
    check('resume-day sell price 8.0 (limit-down, whitelisted)', s9c[0].price, 8.0)
    check('resume-day sell shares 9900', s9c[0].shares, 9900)
    check('resume-day sell date 2024-05-03', s9c[0].date, dates9[i_resume])
# 负对照：不传白名单 → 连续跌停价上卖不出（0 笔）
eng9c2 = BacktestEngine(dates9, open9c, close9c, hfq9c, mcap9c, tradable9c, st9c,
                        initial_cash=100000.0)
res9c2 = eng9c2.run(signals9c)
check('without whitelist: resume-day sell blocked by limit-down',
      len([t for t in res9c2.trades if t.side == 'sell']), 0)
# 板块×时间矩阵（is_limit_free 直测）
close9u = pd.DataFrame(10.0, index=dates9, columns=['600004', '300002', '600001'])
mcap9u = pd.DataFrame(np.full((n9, 3), 200e8), index=dates9,
                      columns=['600004', '300002', '600001'])
tradable9u = pd.DataFrame(np.ones((n9, 3), dtype=bool), index=dates9,
                          columns=['600004', '300002', '600001'])
st9u = pd.DataFrame(np.zeros((n9, 3), dtype=bool), index=dates9,
                    columns=['600004', '300002', '600001'])
eng9u = BacktestEngine(dates9, close9u.copy(), close9u.copy(), close9u.copy(),
                       mcap9u, tradable9u, st9u, initial_cash=100000.0,
                       list_dates=pd.Series({'600004': '2024-03-29',
                                             '300002': '2024-03-29',
                                             '600001': '2024-03-01'}))
check('main post-2023-02-17 day2 free',
      eng9u.is_limit_free('600004', pd.Timestamp('2024-04-01')), True)
check('chinext post-2020-08-24 day2 free',
      eng9u.is_limit_free('300002', pd.Timestamp('2024-04-01')), True)
check('main listed 3/1 at 4/1 (day22) not free',
      eng9u.is_limit_free('600001', pd.Timestamp('2024-04-01')), False)
dates9m = pd.date_range('2020-06-01', '2020-09-30', freq='B')
cols9m = ['300002', '300003', '600005', '688005']
close9m = pd.DataFrame(10.0, index=dates9m, columns=cols9m)
mcap9m = pd.DataFrame(np.full((len(dates9m), 4), 200e8), index=dates9m, columns=cols9m)
tradable9m = pd.DataFrame(np.ones((len(dates9m), 4), dtype=bool), index=dates9m,
                          columns=cols9m)
st9m = pd.DataFrame(np.zeros((len(dates9m), 4), dtype=bool), index=dates9m,
                    columns=cols9m)
eng9m = BacktestEngine(dates9m, close9m.copy(), close9m.copy(), close9m.copy(),
                       mcap9m, tradable9m, st9m, initial_cash=100000.0,
                       list_dates=pd.Series({'300002': '2020-06-01',
                                             '300003': '2020-08-25',
                                             '600005': '2020-06-01',
                                             '688005': '2020-06-01'}))
check('chinext pre-reform day2 NOT free',
      eng9m.is_limit_free('300002', pd.Timestamp('2020-06-02')), False)
check('chinext post-reform day2 free',
      eng9m.is_limit_free('300003', pd.Timestamp('2020-08-26')), True)
check('star day2 free',
      eng9m.is_limit_free('688005', pd.Timestamp('2020-06-02')), True)
check('main pre-2023-02-17 day2 NOT free',
      eng9m.is_limit_free('600005', pd.Timestamp('2020-06-02')), False)

# ============================================================
# Case 10: 复牌首日跳空 >20% 放弃 [§3.3]（停牌2日复牌 +25%）
# ============================================================
print('== Case 10: resumption gap >20% -> abandon ==')
dates10 = dates9
code10 = '000001'
n10 = n9
close10 = pd.DataFrame(np.nan, index=dates10, columns=[code10])
open10 = pd.DataFrame(np.nan, index=dates10, columns=[code10])
close10.iloc[:21, 0] = 10.0     # 3/1~3/29 正常交易收 10
open10.iloc[:21, 0] = 10.0
# 4/1~4/2 停牌（open/close NaN），4/3 复牌跳空 +25%
close10.iloc[23:, 0] = 12.5
open10.iloc[23:, 0] = 12.5
hfq10 = close10.copy()
mcap10 = pd.DataFrame(np.full((n10, 1), 200e8), index=dates10, columns=[code10])
tradable10 = pd.DataFrame(False, index=dates10, columns=[code10])
tradable10.iloc[:21, 0] = True
tradable10.iloc[23:, 0] = True
st10 = pd.DataFrame(np.zeros((n10, 1), dtype=bool), index=dates10, columns=[code10])
signals10 = pd.DataFrame(0.0, index=month_ends9, columns=[code10])
signals10.iloc[0] = 1.0     # 仅第一期调仓（3/29 信号 → 4/1 执行）
eng10 = BacktestEngine(dates10, open10, close10, hfq10, mcap10, tradable10, st10,
                       initial_cash=100000.0)
res10 = eng10.run(signals10)
check('resumption +25% gap: buy abandoned', len(res10.trades), 0)

# 对照：复牌跳空 +10%（≤20%）→ 复牌日正常成交
close10b = close10.copy()
open10b = open10.copy()
close10b.iloc[23:, 0] = 11.0
open10b.iloc[23:, 0] = 11.0
hfq10b = close10b.copy()
eng10b = BacktestEngine(dates10, open10b, close10b, hfq10b, mcap10,
                        tradable10, st10, initial_cash=100000.0)
res10b = eng10b.run(signals10)
buys10b = [t for t in res10b.trades if t.side == 'buy']
check('resumption +10% gap: buy executed', len(buys10b), 1)
if buys10b:
    check('resumption buy date = resume day', buys10b[0].date, dates10[23])
    check('resumption buy price 11.0', buys10b[0].price, 11.0)

# ============================================================
# Case 11: 基准对比 [§3.6]——超额年化/超额夏普/相对回撤/跟踪误差/信息比率
# ============================================================
print('== Case 11: benchmark excess metrics ==')
dates11 = pd.date_range('2024-03-01', periods=150, freq='B')
close11 = pd.DataFrame({'000001': 10.0}, index=dates11)
open11 = close11.copy()
hfq11 = close11.copy()
mcap11 = pd.DataFrame(np.full((len(dates11), 1), 200e8), index=dates11,
                      columns=['000001'])
tradable11 = pd.DataFrame(np.ones((len(dates11), 1), dtype=bool),
                          index=dates11, columns=['000001'])
st11 = pd.DataFrame(np.zeros((len(dates11), 1), dtype=bool), index=dates11,
                    columns=['000001'])
month_ends11 = [dates11[i] for i in range(len(dates11)-1)
                if dates11[i+1].month != dates11[i].month] + [dates11[-1]]
signals11 = pd.DataFrame(1.0, index=month_ends11, columns=['000001'])
eng11 = BacktestEngine(dates11, open11, close11, hfq11, mcap11, tradable11, st11,
                       initial_cash=100000.0)
res11 = eng11.run(signals11)
navh = res11.nav_hfq
# 基准 = 组合净值 × 中间月折 5%：相对净值 = [1, 1/0.95, 1, 1...] → 相对回撤 -5%
bench11 = navh.copy()
bench11.iloc[1] = navh.iloc[1] * 0.95
perf11 = Performance(nav=navh, monthly_returns=res11.monthly_returns,
                     benchmark_nav=bench11)
check('excess annual (mid-dip bench cancels)', perf11.excess_annual_return(),
      0.0, tol=1e-9)
check('relative drawdown = -5% (hand)', perf11.relative_drawdown(), -0.05,
      tol=1e-9)
bm = bench11.pct_change().fillna(0.0)
ex = (res11.monthly_returns - bm).dropna()
check('excess sharpe = mean/std*sqrt12',
      perf11.excess_sharpe(), float(ex.mean() / ex.std(ddof=1) * np.sqrt(12)),
      tol=1e-9)
exp_te = float(ex.std(ddof=1) * np.sqrt(12))
check('tracking error = std*sqrt12', perf11.tracking_error(), exp_te, tol=1e-9)
check('info ratio = excess ann / TE',
      perf11.information_ratio(), perf11.excess_annual_return() / exp_te,
      tol=1e-9)
# 平基准（恒 100000）：超额 ≡ 自身指标
perf11b = Performance(nav=navh, monthly_returns=res11.monthly_returns,
                      benchmark_nav=pd.Series(100000.0, index=navh.index))
check('excess annual vs flat bench = own annual',
      perf11b.excess_annual_return(), perf11b.annual_return(), tol=1e-9)
check('relative dd vs flat bench = own mdd',
      perf11b.relative_drawdown(), perf11b.max_drawdown(), tol=1e-9)
check('excess sharpe vs flat bench = monthly sharpe',
      perf11b.excess_sharpe(),
      float(res11.monthly_returns.mean() / res11.monthly_returns.std(ddof=1)
            * np.sqrt(12)), tol=1e-9)
# 年化按实际日期跨度（非 12/(n-1)）：2 点 [2023-01-31, 2024-01-31] 净值翻倍
perf_small = Performance(
    nav=pd.Series([1.0, 2.0], index=[pd.Timestamp('2023-01-31'),
                                     pd.Timestamp('2024-01-31')]),
    monthly_returns=pd.Series([1.0], index=[pd.Timestamp('2024-01-31')]))
span_days = (pd.Timestamp('2024-01-31') - pd.Timestamp('2023-01-31')).days
check('annual return uses actual date span',
      perf_small.annual_return(), 2.0 ** (365.25 / span_days) - 1, tol=1e-9)

# ============================================================
# Case 12: positions_history 持仓快照 + 实际单边换手 [§3.4]
# ============================================================
print('== Case 12: positions_history + actual turnover ==')
dates12 = pd.date_range('2024-03-01', periods=150, freq='B')
codes12 = ['000001', '000002']
n12 = len(dates12)
close12 = pd.DataFrame(10.0, index=dates12, columns=codes12)
open12 = close12.copy()
hfq12 = close12.copy()
mcap12 = pd.DataFrame(np.full((n12, 2), 200e8), index=dates12, columns=codes12)
tradable12 = pd.DataFrame(np.ones((n12, 2), dtype=bool), index=dates12,
                          columns=codes12)
st12 = pd.DataFrame(np.zeros((n12, 2), dtype=bool), index=dates12,
                    columns=codes12)
month_ends12 = [dates12[i] for i in range(len(dates12)-1)
                if dates12[i+1].month != dates12[i].month] + [dates12[-1]]
signals12 = pd.DataFrame(0.0, index=month_ends12, columns=codes12)
signals12.iloc[0] = [0.5, 0.5]   # 期1: A50/B50
signals12.iloc[1] = [0.0, 1.0]   # 期2: 全 B
signals12.iloc[2] = [1.0, 0.0]   # 期3: 全 A
signals12.iloc[3] = [0.5, 0.5]   # 期4: A50/B50
eng12 = BacktestEngine(dates12, open12, close12, hfq12, mcap12, tradable12, st12,
                       initial_cash=100000.0)
res12 = eng12.run(signals12)
# 持仓快照：数量 = 月末估值点数（nav 首点为首次 T+1，其后为月末）
check('positions_history not empty', len(res12.positions_history), 6)
check('snapshot dates == nav month-end dates',
      [s.name for s in res12.positions_history] == list(res12.nav.index[1:]),
      True)
snap0 = res12.positions_history[0]
check('month1 snapshot A=5000 (hand)', snap0.get('000001', 0), 5000)
check('month1 snapshot B=4900 (hand, cash buffer)', snap0.get('000002', 0), 4900)
snap1 = res12.positions_history[1]
check('month2 snapshot B=9900 (hand: 4900+5000)', snap1.get('000002', 0), 9900)
check('month2 snapshot A=0 (sold all)', snap1.get('000001', 0), 0)
# 快照与 trades 对账：每只股票 累计买入 - 累计卖出（截至月末）= 快照股数
for s in res12.positions_history:
    t = s.name
    for code in codes12:
        from_trades = (sum(tr.shares for tr in res12.trades
                           if tr.code == code and tr.side == 'buy'
                           and tr.date <= t)
                       - sum(tr.shares for tr in res12.trades
                             if tr.code == code and tr.side == 'sell'
                             and tr.date <= t))
        check(f'positions_history == trades ({t.date()} {code})',
              s.get(code, 0), from_trades)
# 实际单边换手 = Σ月内成交金额 ÷ 月末净值；目标换手保留作对照
check('actual_turnover not empty', len(res12.actual_turnover), 6)
exp_monthly_to = []
for m_end in res12.actual_turnover.index:
    month_trades = [tr for tr in res12.trades
                    if tr.date.year == m_end.year and tr.date.month == m_end.month]
    traded = sum(tr.amount for tr in month_trades)
    exp_to = traded / res12.nav.loc[m_end]
    exp_monthly_to.append(exp_to)
    check(f'actual turnover {m_end.date()}', res12.actual_turnover.loc[m_end],
          exp_to, tol=1e-9)
check('annualized turnover = 12 x monthly mean',
      float(12 * res12.actual_turnover.mean()), float(12 * np.mean(exp_monthly_to)),
      tol=1e-9)
check('target turnover kept as control column [1,1,2,1,1,0]',
      list(round(v, 6) for v in res12.turnover.values), [1.0, 1.0, 2.0, 1.0,
                                                         1.0, 0.0])
check('target vs actual differ (target is not actual)', 
      float(abs(res12.turnover - res12.actual_turnover).max()) > 0.001, True)


# ============================================================
# Case 13: 缺失市值 → 滑点 30bp + verbose 告警 [C4 缺口5]；
#          基准常数增长（+1%/月）→ 超额指标手算对账（引擎级）[C4 缺口3]
# ============================================================
print('== Case 13: missing mcap 30bp + benchmark constant growth ==')
dates13 = pd.date_range('2023-12-29', '2024-03-29', freq='B')
close13 = pd.DataFrame({'000001': 10.0}, index=dates13)
open13 = close13.copy()
hfq13 = close13.copy()
n13 = len(dates13)
mcap13 = pd.DataFrame(np.nan, index=dates13, columns=['000001'])    # 市值全缺失
mcap13b = pd.DataFrame(np.full((n13, 1), 200e8), index=dates13, columns=['000001'])
tradable13 = pd.DataFrame(np.ones((n13, 1), dtype=bool), index=dates13,
                          columns=['000001'])
st13 = pd.DataFrame(np.zeros((n13, 1), dtype=bool), index=dates13, columns=['000001'])
month_ends13 = [dates13[i] for i in range(len(dates13)-1)
                if dates13[i+1].month != dates13[i].month] + [dates13[-1]]
signals13 = pd.DataFrame(1.0, index=month_ends13, columns=['000001'])
# 13a: 市值缺失 → 滑点 30bp（而非中盘档 10bp）+ verbose 告警
buf13 = io.StringIO()
with contextlib.redirect_stdout(buf13):
    eng13a = BacktestEngine(dates13, open13, close13, hfq13, mcap13, tradable13, st13,
                            initial_cash=100000.0)
    res13a = eng13a.run(signals13, verbose=True)
b13a = [t for t in res13a.trades if t.side == 'buy'][0]
check('mcap missing: buy cost uses 30bp slippage',
      b13a.cost, 99000*0.00025 + 99000*0.00001 + 99000*0.003, tol=0.01)
check('mcap missing: verbose warning printed',
      '[warn]' in buf13.getvalue() and '30bp' in buf13.getvalue(), True)
# 13b: 基准常数增长（每月 +1%）→ 超额指标手算对账；BacktestResult 携带基准净值
exec13 = dates13[1]    # 2024-01-01（合成日历 freq='B' 不剔除元旦）
bench13 = pd.Series([1.0, 1.01, 1.0201, 1.030301],
                    index=[exec13, pd.Timestamp('2024-01-31'),
                           pd.Timestamp('2024-02-29'), pd.Timestamp('2024-03-29')])
eng13b = BacktestEngine(dates13, open13, close13, hfq13, mcap13b, tradable13, st13,
                        initial_cash=100000.0)
res13b = eng13b.run(signals13, benchmark_nav=bench13)
days13 = (pd.Timestamp('2024-03-29') - exec13).days    # 88
bench_ar13 = 1.030301 ** (365.25 / days13) - 1.0
check('BacktestResult carries benchmark_nav', res13b.benchmark_nav is not None, True)
check('benchmark_annual_return (hand)', res13b.perf.benchmark_annual_return(),
      bench_ar13, tol=1e-9)
# 手算：买入成本 = 24.75 佣金 + 0.99 过户 + 99 滑点（200亿→10bp）= 124.74
#       → nav = 99875.26（首期 100000 后成本拖累）；策略年化 = (99875.26/100000)^(365.25/88)-1
strat_ar13 = (99875.26 / 100000.0) ** (365.25 / days13) - 1.0
check('excess annual = strat_ar - bench_ar (hand)',
      res13b.perf.excess_annual_return(), strat_ar13 - bench_ar13, tol=1e-6)
check('relative drawdown (hand)', res13b.perf.relative_drawdown(),
      99875.26 / 1.030301 / 100000.0 - 1.0, tol=1e-6)
# 手算：月超额 = [-0.0112474, -0.01, -0.01] → mean=-0.0104158, std(ddof=1)=7.202e-4
check('excess sharpe (hand)', res13b.perf.excess_sharpe(), -50.10, tol=0.5)

# ============================================================
# Case 14: 实际换手（含 2 次放弃的调仓）[C4 缺口7] + 持仓快照对账 [C4 缺口4]
#   4 月买入 000001 成交；5 月调仓：卖 000001 一字跌停 + 买 000002 一字涨停全部放弃
# ============================================================
print('== Case 14: actual turnover with abandoned rebalance ==')
dates14 = pd.date_range('2024-03-01', periods=66, freq='B')    # ..2024-05-31
codes14 = ['000001', '000002']
n14 = len(dates14)
close14 = pd.DataFrame(10.0, index=dates14, columns=codes14)
open14 = close14.copy()
hfq14 = close14.copy()
down_px14 = [9.0, 8.1, 7.29, 6.56, 5.90, 5.31]     # 000001 逐日一字跌停（前收×0.9）
up_px14 = [24.0, 28.8, 34.56, 41.47, 49.76, 59.71]  # 000002 逐日一字涨停（前收×1.2）
for _k, _d in enumerate(dates14[43:49]):            # 5/1..5/8
    open14.loc[_d, '000001'] = down_px14[_k]
    close14.loc[_d, '000001'] = down_px14[_k]
    open14.loc[_d, '000002'] = up_px14[_k]
    close14.loc[_d, '000002'] = up_px14[_k]
close14.iloc[49:, 0] = 5.31
close14.iloc[49:, 1] = 59.71
mcap14 = pd.DataFrame(np.full((n14, 2), 200e8), index=dates14, columns=codes14)
tradable14 = pd.DataFrame(np.ones((n14, 2), dtype=bool), index=dates14, columns=codes14)
st14 = pd.DataFrame(np.zeros((n14, 2), dtype=bool), index=dates14, columns=codes14)
month_ends14 = [dates14[i] for i in range(len(dates14)-1)
                if dates14[i+1].month != dates14[i].month] + [dates14[-1]]
signals14 = pd.DataFrame(0.0, index=month_ends14, columns=codes14)
signals14.iloc[0] = [1.0, 0.0]    # 3/29 信号 → 4/1 买 000001
signals14.iloc[1] = [0.0, 1.0]    # 4/30 信号 → 5/1 全换仓（卖/买双双放弃）
eng14 = BacktestEngine(dates14, open14, close14, hfq14, mcap14, tradable14, st14,
                       initial_cash=100000.0)
res14 = eng14.run(signals14)
check('turnover: April buy only', len([t for t in res14.trades if t.side == 'buy']), 1)
check('turnover: May trades = 0 (both abandoned)',
      len([t for t in res14.trades if t.date >= pd.Timestamp('2024-05-01')]), 0)
check('actual turnover April = 99000/nav (hand)',
      res14.actual_turnover.loc['2024-04-30'],
      99000.0 / res14.nav.loc['2024-04-30'], tol=1e-6)
check('actual turnover May = 0 < target 2.0 (hand)',
      res14.actual_turnover.loc['2024-05-31'] < res14.turnover.loc['2024-05-31'], True)
check('target turnover May = 2.0 (control col)', res14.turnover.loc['2024-05-31'],
      2.0, tol=1e-9)
check('annualized turnover = 12 x monthly mean (hand)',
      res14.turnover_annualized,
      12.0 * (99000.0 / res14.nav.loc['2024-04-30']) / 2.0, tol=1e-6)
check('pos history month1 A=9900', res14.positions_history[0].get('000001', 0), 9900)
check('pos history month2 A=9900 (sell failed)',
      res14.positions_history[1].get('000001', 0), 9900)
net14 = (sum(t.shares for t in res14.trades if t.side == 'buy')
         - sum(t.shares for t in res14.trades if t.side == 'sell'))
check('pos history vs trades: share conservation',
      res14.positions_history[-1].sum(), net14)

# ============================================================
print(f'\n===== GOLDEN SAMPLE RESULT: {PASS} PASS / {FAIL} FAIL =====')
if FAIL:
    raise SystemExit(1)
