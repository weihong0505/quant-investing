# -*- coding: utf-8 -*-
"""
C8 验收验证: regime_weight_history 与逐期手算一致 + PIT 无未来函数
================================================================
独立实现调权公式（不复用 regime_weights），对 2 个抽查调权日逐期手算，
与 regime_weight_history 输出对比；并验证篡改未来 IC 不影响历史权重。

运行: D:/pyh/python.exe -E validate_c8_regime.py
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, '.')
from regime_weights import regime_weight_history, regime_weights


def manual_quarter_weights(base_weights, factors_ic, qd, ic_window=36,
                           floor=0.1, max_dev=0.5):
    """逐期手算（独立实现设计文档 §4 公式，与 regime_weights 代码路径无关）:
       icir_i = mean/std(截至qd最近ic_window月IC)
       raw_i = max(icir_i, floor)
       w_i = base_i * raw_i / mean(raw)
       约束 w_i ∈ [base_i*(1-max_dev), base_i*(1+max_dev)] 与归一化交替迭代 50 次
    """
    raw = {}
    w = {}
    for f, b in base_weights.items():
        ic = factors_ic.get(f)
        if ic is None:
            w[f] = b
            continue
        hist = ic.dropna()
        hist = hist[hist.index <= qd]
        if len(hist) < 12:
            w[f] = b
            continue
        win = hist.iloc[-ic_window:]
        sd = win.std(ddof=1)
        icir = win.mean() / sd if sd > 0 else 0.0
        raw[f] = max(icir, floor)
        w[f] = b * raw[f]
    mean_raw = np.mean(list(raw.values())) if raw else 1.0
    for f in raw:
        w[f] = base_weights[f] * raw[f] / mean_raw
    for _ in range(50):  # 与 regime_weights 相同的收敛迭代
        for f in w:
            b = base_weights[f]
            w[f] = min(max(w[f], b * (1 - max_dev)), b * (1 + max_dev))
        total = sum(w.values())
        w = {f: v / total for f, v in w.items()}
    return w


def main():
    np.random.seed(11)
    n_months = 72
    dates = pd.date_range('2018-01-31', periods=n_months, freq='ME')
    base = {'EP': 0.2, 'BP': 0.2, 'ROE': 0.12, 'GPM': 0.06, 'MOM': 0.15,
            'TURN': 0.1, 'MCAP': 0.05, 'VOLR': 0.05, 'CFO': 0.05, 'LEV': 0.02}

    # 合成 IC: MOM/EP 强(0.04/0.035), BP/ROE 中(0.025), 其余弱(0.01~0.02)
    mus = {'EP': 0.035, 'BP': 0.025, 'ROE': 0.025, 'GPM': 0.012, 'MOM': 0.04,
           'TURN': 0.018, 'MCAP': 0.01, 'VOLR': 0.015, 'CFO': 0.012, 'LEV': 0.01}
    factors_ic = {}
    for f, mu in mus.items():
        # 带轻微自相关，让不同窗口 ICIR 有差异
        e = np.random.normal(0, 1, n_months)
        ic = pd.Series(mu + 0.10 * e, index=dates, name=f)
        factors_ic[f] = ic

    qdates = pd.date_range('2020-03-31', periods=12, freq='QE')  # 2020Q1..2022Q4
    hist = regime_weight_history(base, factors_ic, qdates)

    # ---- 检查 1: 抽查 2 个调权日，与逐期手算一致 ----
    checks = [qdates[3], qdates[9]]  # 2020-12-31 与 2022-09-30
    for qd in checks:
        manual = manual_quarter_weights(base, factors_ic, qd)
        got = hist.loc[qd].to_dict()
        ok = all(abs(manual[f] - got[f]) < 1e-12 for f in base)
        print(f'[hand-check] qd={qd.date()} 一致: {ok}')
        assert ok, f'调权日 {qd} 手算不一致: manual={manual} got={got}'
        assert abs(sum(got.values()) - 1.0) < 1e-9, f'调权日 {qd} 未归一化'

    # ---- 检查 2: 抽查 1 个调权日与 regime_weights(窗口化IC) 等价（切片正确性）----
    qd = checks[0]
    window_ic = {f: factors_ic[f].loc[:qd].iloc[-36:] for f in base}
    eq = regime_weights(base, window_ic)
    for f in base:
        assert abs(eq[f] - hist.loc[qd, f]) < 1e-12, f'{f} 与单期函数不一致'
    print(f'[slice-check] qd={qd.date()} 与 regime_weights(截至qd的36m窗口) 等价: True')

    # ---- 检查 3: PIT 无未来函数（篡改 2023Q1+ 的 IC 不影响 2022Q4 及之前权重）----
    factors_ic_future = {f: s.copy() for f, s in factors_ic.items()}
    for f in factors_ic_future:
        factors_ic_future[f].iloc[-12:] = 9.9  # 污染 2023 年数据
    hist2 = regime_weight_history(base, factors_ic_future, qdates)
    pd.testing.assert_frame_equal(hist, hist2)
    print('[pit-check] 篡改调权日之后 IC 后全部历史权重不变: True')

    # ---- 检查 4: 样本不足（<12m 历史）的调权日保持基准权重 ----
    early_q = pd.DatetimeIndex([pd.Timestamp('2018-06-30')])  # 仅 5 个月 IC
    hist3 = regime_weight_history(base, factors_ic, early_q)
    for f in base:
        assert abs(hist3.loc['2018-06-30', f] - base[f]) < 1e-12, f
    print('[short-sample] qd=2018-06-30（<12m 历史）保持基准权重: True')

    print('\nALL C8 CHECKS PASSED (4/4)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
