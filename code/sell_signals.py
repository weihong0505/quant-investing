# -*- coding: utf-8 -*-
"""
卖出信号模块 sell_signals.py
=============================
在月度调仓信号（Top N 选股）之上叠加卖出规则，生成最终目标权重矩阵。
按 SOP §4 协作规范：卖出规则参数由用户拍板金融逻辑，本模块提供可配置实现。
状态标注：无独立审批报告——卖出规则由用户拍板（SOP §4）；C5 三处逻辑问题修复已验收（2026-08-22）；未审批/未检验（实验）

三类卖出信号（用户指定方向）：
  1. 时间止盈（time exit）：持有满 N 个月强制卖出
  2. 信号衰减（signal decay）：综合得分排名跌出 Top N（top_n）→ 卖出
  3. 止损（stop loss）：持仓浮亏超过阈值 → 卖出

口径声明（2026-08-22 C5 修复，与回测引擎 v2.1 对齐）：
  - 信号衰减阈值与 top_n 联动：keep_rank = top_n，排名跌出 top_n 即卖。
    不再有独立 keep_rank 参数；旧持仓跌出 top_n 一律走 signal_decay 卖出
    路径（记录卖出原因 + 进入冷却期），不存在"权重归零绕过冷却期"的第二条路径。
  - 止损基准价 = T+1 开盘价（成交价）：引擎按 T 日收盘信号 → T+1 开盘价成交
    [规范 §3.3]，买入记账价取成交价（见 generate_signals 的 exec_price_table
    参数；未传成交价表时回退信号日价格口径——docstring 明确声明其局限性）。
  - 等权口径：w = 1.0 / len(candidates)。候选不足 top_n 时剩余权重按现有
    候选等比放大，总权重恒为 1.0（不产生现金拖累）。

设计原则：
  - 纯逻辑层，输入 = 每期打分表 + 每期价格，输出 = 目标权重矩阵
  - 与 BacktestEngine 解耦：本模块产出 signals DataFrame，引擎负责执行
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class SellRules:
    """卖出规则参数（可配置）。

    参数：
      hold_months:   时间止盈：持有满 N 月强制卖出（默认 6）
      stop_loss:     止损：持仓收益 ≤ 阈值卖出（默认 -0.15，即 -15%）
      max_rebuy_gap: 卖出后 N 个月内不重新买入（防频繁进出，默认 3）

    注：信号衰减阈值不单独配置——keep_rank 与 top_n 联动（keep_rank = top_n），
        排名跌出 top_n 即卖（C5 修复 2026-08-22，方案 1）。
    """
    hold_months: int = 6
    stop_loss: float = -0.15
    max_rebuy_gap: int = 3


def _entry_price_at(date, code, prices, exec_price_table):
    """买入记账价解析（C5 修复：止损基准价 = T+1 开盘价）。

    优先级：
      1. 提供 exec_price_table（成交价表）时：取信号日 date 对应的 T+1 开盘价
         （成交价，与引擎 §3.3 "T+1 开盘价成交"口径一致）；该股当日无数据
         （停牌/缺数）→ NaN → 止损暂停（宁可不触发，不误杀）。
      2. 未提供 exec_price_table（调用方传的是收盘价表）：取信号日价格
         （收盘价口径——docstring 已声明：与真实 T+1 成交口径不一致，跳空时
         止损触发点漂移，仅用于无成交价表时的近似/调试）。
    """
    if exec_price_table is not None and date in exec_price_table.index:
        row = exec_price_table.loc[date]
        v = row[code] if code in row.index else np.nan
        return float(v) if pd.notna(v) else np.nan
    if prices is not None and code in prices.index and pd.notna(prices[code]):
        return float(prices[code])
    return np.nan


def generate_signals(score_table: pd.DataFrame,
                     price_table: pd.DataFrame,
                     top_n: int = 30,
                     rules: SellRules = None,
                     exec_price_table: pd.DataFrame = None,
                     sell_log: list = None) -> pd.DataFrame:
    """
    生成月度目标权重矩阵（含卖出信号）。

    参数:
      score_table: DataFrame，index=月末交易日，columns=股票代码，
                   values=综合得分 SCORE（越大越好）
      price_table: DataFrame，index=交易日，columns=股票代码，
                   values=不复权价格（raw 口径 [§2.1]）。用途：
                   ① 止损判定时的当前市价（信号日取值）
                   ② 未传 exec_price_table 时，作为买入记账价的回退口径
                   —— 此时按"收盘价表"口径计算止损（记账价 = 信号日价格），
                   与引擎 T+1 开盘成交口径不一致（跳空缺口下触发点漂移），
                   仅用于无成交价表时的近似/调试
      exec_price_table: 可选。成交价表（index=月末信号日，与 score_table
                   对齐；columns=股票代码；values=该期信号在 T+1 开盘成交的
                   成交价）。传入时买入记账价 = 该表信号日取值（T+1 开盘价
                   口径，与引擎 §3.3 一致）；该股当日缺数 → 记账价 NaN →
                   止损暂停（不误杀）
      top_n: 每期持仓数量；同时作为信号衰减阈值——排名跌出 top_n 即卖
             （keep_rank 与 top_n 联动，keep_rank = top_n）
      rules: SellRules（卖出规则参数，见 SellRules docstring）
      sell_log: 可选。传入 list 时，每次卖出追加一条记录：
               {'date': 信号日, 'code': 代码, 'reason': 卖出原因,
                'cooldown': 本次卖出进入的冷却月数}
               用于卖出路径口径校验（signal_decay 等卖出原因必须记录在案，
               保证"权重归零"不再绕过冷却期与原因记录）

    返回:
      signals: DataFrame，index=月末交易日，columns=代码，values=目标权重
               （等权 1/len(candidates)：候选不足 top_n 时按现有候选等比放大，
               总权重恒为 1.0；被卖出信号过滤或处于冷却期的股票权重为 0；
               极端情形下无候选时该期空仓，权重全 0）
    """
    if rules is None:
        rules = SellRules()

    dates = pd.DatetimeIndex(score_table.index).sort_values()
    signals = pd.DataFrame(index=dates, columns=score_table.columns,
                           dtype=float)

    holdings: dict = {}   # code -> (entry_date, entry_price)
    cooldown: dict = {}   # code -> 剩余冷却月数

    for i, date in enumerate(dates):
        scores = score_table.loc[date].dropna()
        if scores.empty:
            continue
        # 当前市场价格（信号日）
        prices = price_table.loc[date] if date in price_table.index else None

        # 每只股票的排名（rank 1 = 最好；rank >= top_n+1 即跌出 Top N）
        ranked = scores.sort_values(ascending=False)

        # ---- 卖出判定（唯一卖出路径：记录卖出原因 + 进入冷却期）----
        valid = {}
        for code in list(holdings.keys()):
            entry_date, entry_price = holdings[code]
            months_held = len(dates[(dates > entry_date) & (dates <= date)])

            sell_reason = None
            # 1) 时间止盈
            if months_held >= rules.hold_months:
                sell_reason = f'time_exit({months_held}m)'
            # 2) 信号衰减：排名跌出 top_n 即卖（keep_rank = top_n，C5 修复）
            elif code not in ranked.index or \
                    ranked.index.get_loc(code) >= top_n:
                sell_reason = 'signal_decay'
            # 3) 止损：浮亏超阈值（记账价 = T+1 开盘价口径，见 _entry_price_at）
            elif prices is not None and code in prices.index and \
                    pd.notna(entry_price) and pd.notna(prices[code]) and \
                    entry_price > 0:
                pnl = prices[code] / entry_price - 1
                if pnl <= rules.stop_loss:
                    sell_reason = f'stop_loss({pnl:.1%})'

            if sell_reason:
                del holdings[code]
                cooldown[code] = rules.max_rebuy_gap
                if sell_log is not None:
                    sell_log.append({'date': date, 'code': code,
                                     'reason': sell_reason,
                                     'cooldown': rules.max_rebuy_gap})
            else:
                valid[code] = holdings[code]

        # ---- 冷却期递减 ----
        for code in list(cooldown.keys()):
            cooldown[code] -= 1
            if cooldown[code] <= 0:
                del cooldown[code]

        # ---- 买入判定：从 Top N 中剔除冷却期股票，按排名补齐 ----
        candidates = []
        for code in ranked.index:
            if code in valid:
                candidates.append(code)
            elif code in cooldown:
                continue  # 冷却期内不买
            else:
                candidates.append(code)
            if len(candidates) >= top_n:
                break

        # ---- 记录持仓与权重（等权 1/len(candidates)，总权重恒为 1.0）----
        if not candidates:
            continue  # 极端情形（候选全在冷却期）：本期空仓，权重全 0
        w = 1.0 / len(candidates)
        for code in candidates[:top_n]:
            signals.at[date, code] = w
            if code not in valid:
                entry_price = _entry_price_at(date, code, prices,
                                              exec_price_table)
                holdings[code] = (date, entry_price)

    return signals.fillna(0.0)


def score_ranking(score_table: pd.DataFrame) -> pd.DataFrame:
    """得分表 → 排名表（1=最好），供信号衰减与调试用"""
    return score_table.rank(axis=1, ascending=False, method='first')


if __name__ == '__main__':
    # ---- 冒烟测试：合成数据（C5 修复后含 3 组针对性断言）----
    PASS, FAIL = 0, 0

    def check(name, cond, detail=''):
        global PASS, FAIL
        if cond:
            PASS += 1
            print(f'  [PASS] {name}: {detail}')
        else:
            FAIL += 1
            print(f'  [FAIL] {name}: {detail}')

    # --- 原冒烟场景：随机数据主流程 ---
    np.random.seed(42)
    dates = pd.date_range('2024-01-31', periods=12, freq='ME')
    codes = [f'{i:06d}' for i in range(100, 140)]
    rng = np.random.default_rng(7)
    scores = pd.DataFrame(rng.normal(size=(len(dates), len(codes))),
                          index=dates, columns=codes)
    prices = pd.DataFrame(100 * np.exp(rng.normal(0, 0.05,
                          size=(len(dates), len(codes))).cumsum(axis=0)),
                          index=dates, columns=codes)

    sig = generate_signals(scores, prices, top_n=10)
    print('== smoke: random-data main flow ==')
    print('signal matrix shape:', sig.shape)
    print('holdings per period:',
          sig.astype(bool).sum(axis=1).tolist())
    row_sums = sig.sum(axis=1)
    check('every period weight sum == 1.0',
          np.allclose(row_sums, 1.0),
          f'max dev={float((row_sums - 1.0).abs().max()):.2e}')

    # --- 针对性断言 1：止损基准价 = T+1 开盘价（C5 子项 1，方案 B）---
    # 信号日收盘 10.0、T+1 开盘 9.5、后续跌到 8.4：
    # 真实浮亏 = 8.4/9.5-1 = -11.6% > -15% → 不触发止损；
    # 按信号日收盘口径 = 8.4/10-1 = -16% ≤ -15% → 会误触发（旧行为）。
    print('== targeted 1: stop-loss base = T+1 open price ==')
    d1, d2 = pd.Timestamp('2024-01-31'), pd.Timestamp('2024-02-29')
    codes3 = ['000001', '000002', '000003']
    sc3 = pd.DataFrame([[10.0, 9.0, 8.0], [10.0, 9.0, 8.0]],
                       index=[d1, d2], columns=codes3)
    px3 = pd.DataFrame([[10.0, 50.0, 100.0], [8.4, 50.0, 100.0]],
                       index=[d1, d2], columns=codes3)
    exec3 = pd.DataFrame([[9.5, 50.0, 100.0], [8.4, 50.0, 100.0]],
                         index=[d1, d2], columns=codes3)
    log = []
    sig_b = generate_signals(sc3, px3, top_n=3, exec_price_table=exec3,
                             sell_log=log)
    check('T+1 caliber: A NOT stopped (-11.6% > -15%)',
          sig_b.loc[d2, '000001'] > 0,
          f"w(A,d2)={sig_b.loc[d2, '000001']:.3f}")
    check('T+1 caliber: no sell recorded', len(log) == 0, f'sell_log={log}')
    # 回退口径（不传成交价表，收盘价表）：按 10.0 记账 → -16% → 触发止损
    log2 = []
    sig_legacy = generate_signals(sc3, px3, top_n=3, sell_log=log2)
    check('close caliber (legacy): A stopped (-16% <= -15%)',
          sig_legacy.loc[d2, '000001'] == 0,
          f"w(A,d2)={sig_legacy.loc[d2, '000001']:.3f}, "
          f"reason={[e['reason'] for e in log2]}")

    # --- 针对性断言 2：keep_rank 与 top_n 联动 + 卖出原因记录 + 冷却期 ---
    # 持仓股排名 40（top_n=30 之外）→ signal_decay；卖出进入冷却期，
    # 下期排名回到第 1 也在冷却期内不买（keep_rank=60 时代不会卖出）。
    # 注：000130 于 d2 补入（排名 30），d3 跌到排名 40 也会 signal_decay，
    #     属预期行为，故只断言 000100 的事件。
    print('== targeted 2: keep_rank = top_n (decay outside top_n) ==')
    check('SellRules has no independent keep_rank param',
          not hasattr(SellRules(), 'keep_rank'), '')
    n40 = 40
    c40 = [f'{100 + i:06d}' for i in range(n40)]
    d3 = pd.Timestamp('2024-03-31')
    sc40 = pd.DataFrame(index=[d1, d2, d3], columns=c40, dtype=float)
    # d1: 000100 得分 100（排名 1）；d2: 000100 跌到 60（排名 40）；
    # d3: 000100 回到 100（排名 1），但仍在冷却期
    sc40.loc[d1] = [100.0 - i for i in range(n40)]
    sc40.loc[d2] = [60.0] + [100.0 - i for i in range(1, n40)]
    sc40.loc[d3] = [100.0 - i for i in range(n40)]
    px40 = pd.DataFrame(10.0, index=[d1, d2, d3], columns=c40)
    log40 = []
    sig40 = generate_signals(sc40, px40, top_n=30, sell_log=log40)
    decays = [e for e in log40 if e['code'] == '000100']
    check('rank 40 (outside top 30) -> signal_decay recorded',
          len(decays) == 1
          and decays[0]['reason'] == 'signal_decay'
          and decays[0]['date'] == d2 and decays[0]['cooldown'] == 3,
          f'{decays}')
    check('decay sell goes through cooldown path (no weight-zero bypass)',
          sig40.loc[d2, '000100'] == 0,
          f"w(000100,d2)={sig40.loc[d2, '000100']}")
    check('cooldown blocks rebuy at d3 (rank 1 but still cooling)',
          sig40.loc[d3, '000100'] == 0,
          f"w(000100,d3)={sig40.loc[d3, '000100']}")

    # --- 针对性断言 3：候选不足 top_n 时权重等比放大，合计恒为 1.0 ---
    # 12 只股票、top_n=10：d2 前两只跌出 → 冷却；d3 再两只跌出 →
    # 候选 = 8（6 只旧持仓 + 2 只新补）< 10 → 每只 w = 1/8，合计 = 1.0；
    # d4 冷却期满 → 补回 10 只，合计仍 = 1.0。
    # 注：跌出者得分必须互异（-2/-3/-4/-5），否则同分并列时 pandas
    #     sort_values 不稳定排序会改变谁跌出，断言结果不确定。
    print('== targeted 3: weight scaling when candidates < top_n ==')
    c12 = [f'{i:06d}' for i in range(1, 13)]
    d4 = pd.Timestamp('2024-04-30')
    sc12 = pd.DataFrame(index=[d1, d2, d3, d4], columns=c12, dtype=float)
    sc12.loc[d1] = [12.0 - i for i in range(12)]          # 全排名 1..12
    # d2: 000001/000002 跌出 top 10（排名 11/12）→ signal_decay
    sc12.loc[d2] = [-100.0, -99.0] + [12.0 - i for i in range(2, 12)]
    # d3: 000003/000004 也跌出（排名 11/12）→ 与 000001/000002 同处冷却期
    sc12.loc[d3] = [-2.0, -3.0, -4.0, -5.0] + [8.0 - i for i in range(8)]
    sc12.loc[d4] = sc12.loc[d3].copy()
    px12 = pd.DataFrame(10.0, index=[d1, d2, d3, d4], columns=c12)
    sig12 = generate_signals(sc12, px12, top_n=10)
    s1, s2_, s3_, s4_ = (sig12.loc[d1], sig12.loc[d2],
                         sig12.loc[d3], sig12.loc[d4])
    check('full 10 candidates -> w = 1/10 each, sum == 1.0',
          np.allclose(s1[s1 > 0], 1.0 / 10) and abs(s1.sum() - 1.0) < 1e-9,
          f'sum={s1.sum():.4f}')
    check('d2: decay + refill keeps 10 candidates, sum == 1.0',
          abs(s2_.sum() - 1.0) < 1e-9, f'sum={s2_.sum():.4f}')
    check('8 candidates -> w = 1/8 each, sum == 1.0',
          np.allclose(s3_[s3_ > 0], 1.0 / 8) and abs(s3_.sum() - 1.0) < 1e-9,
          f"w={sorted(s3_[s3_ > 0].round(4).tolist())}, sum={s3_.sum():.4f}")
    check('d4: cooldown expired -> refill to 10, sum still == 1.0',
          abs(s4_.sum() - 1.0) < 1e-9, f'sum={s4_.sum():.4f}')

    print(f'\n===== SELL SIGNALS SMOKE RESULT: {PASS} PASS / {FAIL} FAIL =====')
    if FAIL:
        raise SystemExit(1)
