# -*- coding: utf-8 -*-
"""
C5 修复验证脚本 validate_c5_fix.py
===================================
对 sell_signals.py 三处逻辑修复做合成数据实测：
  1. 止损基准价 = T+1 开盘价（方案 B，exec_price_table 成交价表）
  2. keep_rank 与 top_n 联动（删除独立参数，排名跌出 top_n 即卖；
     卖出原因必记录，冷却期不可绕过）
  3. 候选不足 top_n 时权重等比放大（w = 1.0/len(candidates)，总权重恒 1.0）

运行: D:/pyh/python.exe -E validate_c5_fix.py
输出: 控制台 + docs/review_2026-08/C5_validation_output.txt
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from sell_signals import generate_signals, SellRules, _entry_price_at

PASS, FAIL = 0, 0


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  [PASS] {name}: {detail}')
    else:
        FAIL += 1
        print(f'  [FAIL] {name}: {detail}')


d1 = pd.Timestamp('2024-01-31')
d2 = pd.Timestamp('2024-02-29')
d3 = pd.Timestamp('2024-03-31')
d4 = pd.Timestamp('2024-04-30')

# ============================================================
# 1. 止损基准价 = T+1 开盘价（C5 子项 1，方案 B）
# ============================================================
print('== 1. stop-loss base = T+1 open price ==')

# 1a. 信号日收盘 10.0、T+1 开盘 9.5、后续 8.4：真实浮亏 -11.6% > -15%
#     → 不触发；收盘口径 -16% ≤ -15% → 误触发（旧行为）
codes3 = ['000001', '000002', '000003']
sc = pd.DataFrame([[10.0, 9.0, 8.0], [10.0, 9.0, 8.0]],
                  index=[d1, d2], columns=codes3)
px = pd.DataFrame([[10.0, 50.0, 100.0], [8.4, 50.0, 100.0]],
                  index=[d1, d2], columns=codes3)
exec_px = pd.DataFrame([[9.5, 50.0, 100.0], [8.4, 50.0, 100.0]],
                       index=[d1, d2], columns=codes3)

log = []
sig = generate_signals(sc, px, top_n=3, exec_price_table=exec_px, sell_log=log)
check('1a T+1 caliber: NOT stopped at -11.6% (> -15%)',
      sig.loc[d2, '000001'] > 0 and len(log) == 0,
      f"w(A,d2)={sig.loc[d2, '000001']:.3f}, sell_log={log}")

log2 = []
sig2 = generate_signals(sc, px, top_n=3, sell_log=log2)
check('1a close caliber (legacy fallback): stopped at -16% (<= -15%)',
      sig2.loc[d2, '000001'] == 0
      and len(log2) == 1 and log2[0]['reason'] == 'stop_loss(-16.0%)',
      f"w(A,d2)={sig2.loc[d2, '000001']:.3f}, reason={log2[0]['reason']}")

# 1b. 真实止损触发：8.0 / 9.5 - 1 = -15.8% ≤ -15% → 必须触发（T+1 口径）
px_b = px.copy()
px_b.loc[d2, '000001'] = 8.0
logb = []
sig_b = generate_signals(sc, px_b, top_n=3, exec_price_table=exec_px,
                         sell_log=logb)
check('1b T+1 caliber: stopped at -15.8% (<= -15%)',
      sig_b.loc[d2, '000001'] == 0
      and len(logb) == 1 and logb[0]['reason'] == 'stop_loss(-15.8%)',
      f"w(A,d2)={sig_b.loc[d2, '000001']:.3f}, reason={logb[0]['reason']}")

# 1c. T+1 停牌缺数：exec 表当日 NaN → 记账价 NaN → 止损暂停（暴跌也不卖）
exec_sus = exec_px.copy()
exec_sus.loc[d1, '000001'] = np.nan
logc = []
sig_c = generate_signals(sc, px_b, top_n=3, exec_price_table=exec_sus,
                         sell_log=logc)
check('1c suspended on T+1: entry NaN -> stop-loss paused (no false kill)',
      sig_c.loc[d2, '000001'] > 0 and len(logc) == 0,
      f"w(A,d2)={sig_c.loc[d2, '000001']:.3f} (px 8.0 = -50% vs entry NaN)")

# 1d. 买入记账价解析单元测试
check('1d entry price: exec table T+1 open preferred',
      _entry_price_at(d1, '000001', px.loc[d1], exec_px) == 9.5, '9.5')
check('1d entry price: fallback to signal-day close (close table)',
      _entry_price_at(d1, '000001', px.loc[d1], None) == 10.0, '10.0')
check('1d entry price: missing code in exec table -> NaN',
      np.isnan(_entry_price_at(d1, '999999', px.loc[d1], exec_px)), 'NaN')

# ============================================================
# 2. keep_rank 与 top_n 联动（C5 子项 2，方案 1）
# ============================================================
print('== 2. keep_rank = top_n, decay outside top_n ==')

check('2a SellRules has no independent keep_rank param',
      not hasattr(SellRules(), 'keep_rank'), '')
check('2a SellRules fields',
      SellRules().hold_months == 6 and SellRules().stop_loss == -0.15
      and SellRules().max_rebuy_gap == 3, str(SellRules()))

# 验收原始用例：持仓股排名 35（keep_rank=60 内、top_n=30 外）→ 卖出
n40 = 40
c40 = [f'{100 + i:06d}' for i in range(n40)]
sc40 = pd.DataFrame(index=[d1, d2, d3], columns=c40, dtype=float)
sc40.loc[d1] = [100.0 - i for i in range(n40)]          # 000100 rank 1
# d2: 000100 得分 65 → 排名 35（其余 99..61 不变）
sc40.loc[d2] = [65.0] + [100.0 - i for i in range(1, n40)]
sc40.loc[d3] = [100.0 - i for i in range(n40)]          # 000100 rank 1 again
px40 = pd.DataFrame(10.0, index=[d1, d2, d3], columns=c40)
log40 = []
sig40 = generate_signals(sc40, px40, top_n=30, sell_log=log40)
dec = [e for e in log40 if e['code'] == '000100']
check('2b rank 35 (outside top 30, inside old keep_rank 60) -> signal_decay',
      len(dec) == 1 and dec[0]['reason'] == 'signal_decay'
      and dec[0]['date'] == d2 and dec[0]['cooldown'] == 3,
      f'{dec}')
check('2b sold via cooldown path (no weight-zero bypass)',
      sig40.loc[d2, '000100'] == 0, f"w(000100,d2)={sig40.loc[d2, '000100']}")
check('2b cooldown blocks rebuy next month (rank 1 but cooling)',
      sig40.loc[d3, '000100'] == 0, f"w(000100,d3)={sig40.loc[d3, '000100']}")

# 2c. 卖出路径不变量：任何"上期持有、本期权重为 0"的股票，本期必有卖出记录
np.random.seed(42)
rdates = pd.date_range('2024-01-31', periods=12, freq='ME')
rcodes = [f'{i:06d}' for i in range(100, 140)]
rng = np.random.default_rng(7)
rscores = pd.DataFrame(rng.normal(size=(len(rdates), len(rcodes))),
                       index=rdates, columns=rcodes)
rprices = pd.DataFrame(100 * np.exp(rng.normal(0, 0.05,
                       size=(len(rdates), len(rcodes))).cumsum(axis=0)),
                       index=rdates, columns=rcodes)
rlog = []
rsig = generate_signals(rscores, rprices, top_n=10, sell_log=rlog)
events = {(e['date'], e['code']) for e in rlog}
inv_bad = 0
prev_row = None
for date in rdates:
    if prev_row is not None:
        gone = set(prev_row[prev_row > 0].index) - \
            set(rsig.loc[date][rsig.loc[date] > 0].index)
        unrecorded = [c for c in gone if (date, c) not in events]
        if unrecorded:
            inv_bad += 1
            print(f'    [info] unrecorded sells at {date.date()}: {unrecorded}')
    prev_row = rsig.loc[date]
check('2c invariant: every disappeared position has a sell_log record',
      inv_bad == 0, f'12 periods scanned, {len(rlog)} sell events, 0 unrecorded')

# ============================================================
# 3. 候选不足 top_n 时权重等比放大（C5 子项 3，方案一）
# ============================================================
print('== 3. weight scaling when candidates < top_n ==')

# 3a. 12 只、top_n=10：d2 两只跌出（冷却），d3 再两只跌出 → 候选 8 → 1/8
c12 = [f'{i:06d}' for i in range(1, 13)]
sc12 = pd.DataFrame(index=[d1, d2, d3, d4], columns=c12, dtype=float)
sc12.loc[d1] = [12.0 - i for i in range(12)]
sc12.loc[d2] = [-100.0, -99.0] + [12.0 - i for i in range(2, 12)]
sc12.loc[d3] = [-2.0, -3.0, -4.0, -5.0] + [8.0 - i for i in range(8)]
sc12.loc[d4] = sc12.loc[d3].copy()
px12 = pd.DataFrame(10.0, index=[d1, d2, d3, d4], columns=c12)
sig12 = generate_signals(sc12, px12, top_n=10)
for date, n_cand, w_exp in [(d1, 10, 1.0 / 10), (d2, 10, 1.0 / 10),
                            (d3, 8, 1.0 / 8), (d4, 10, 1.0 / 10)]:
    row = sig12.loc[date]
    nz = row[row > 0]
    check(f'3a {date.date()}: {n_cand} candidates -> w = 1/{n_cand}, sum = 1.0',
          len(nz) == n_cand and np.allclose(nz, w_exp)
          and abs(row.sum() - 1.0) < 1e-9,
          f'w={sorted(nz.round(4).tolist())}, sum={row.sum():.4f}')

# 3b. 极端情形：候选全在冷却期 → 该期空仓（权重全 0），不崩溃
codes2 = ['000005', '000006']
sc2 = pd.DataFrame(index=[d1, d2, d3], columns=codes2, dtype=float)
sc2.loc[d1] = [5.0, 4.0]
sc2.loc[d2] = [5.0, 4.0]   # 排名不变（仅 2 只，永不 decay）
sc2.loc[d3] = [5.0, 4.0]
px2 = pd.DataFrame(10.0, index=[d1, d2, d3], columns=codes2)
sig2 = generate_signals(sc2, px2, top_n=2, rules=SellRules(hold_months=1))
# hold_months=1 → d2 全部 time_exit → 冷却；d3 仍冷却 → 无候选
check('3b all candidates in cooldown -> empty period, sum = 0.0',
      abs(sig2.loc[d3].sum() - 0.0) < 1e-9 and not np.isnan(sig2.loc[d3].sum()),
      f'sum(d3)={sig2.loc[d3].sum():.4f}, no crash')

# 3c. 验证脚本本身：回归——收盘价表（旧调用方式）不传 exec 也能跑
sig_old_style = generate_signals(sc, px, top_n=3)
check('3c backward compat: close-price table call still works',
      sig_old_style.shape == (2, 3), str(sig_old_style.shape))

print(f'\n===== C5 VALIDATION RESULT: {PASS} PASS / {FAIL} FAIL =====')
if FAIL:
    raise SystemExit(1)
