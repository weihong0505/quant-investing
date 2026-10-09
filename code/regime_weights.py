# -*- coding: utf-8 -*-
"""
⚠️ 状态标注（C8a 复核）：设计稿 P2 审批已于 2026-08-22 完成——结论=有条件通过（研究验证工具，禁实盘），正式审批报告见 factor_docs/regime_weights_review_20260822.md；C8a 原冻结标注（基于"审批未完成、函数未实现"前提）因并行任务已审批并实现而撤销
Regime-based 因子权重动态调整 regime_weights.py
================================================
设计文档: research/regime_based_weights.md
审批报告: factor_docs/regime_weights_review_20260822.md（2026-08-22 有条件通过）

定位：**研究验证工具**——用于评估季度调权相对固定权重的增量价值（设计文档 §5）。
禁止在以下条件满足前将其输出用于实盘权重（SOP §3.0.2 先检验后集成）：
  1) 因子通过 v3 统计检验 + 共线性闸门
  2) 调权增益（净成本）验证为正且 2x 成本敏感性稳健
  3) 参数敏感性（floor/max_dev/ic_window ±20%）与同簇因子同步顶限检查完成

方案 A：滚动 36m ICIR 调权（与 v3 滚动观察线复用同一统计量）
  - 季度调权、PIT 严格（调权日只用截至当日的历史数据）
  - 单因子权重偏离基准 ≤ ±50%
  - 地板 max(icir, 0.1) 防归零
"""
import numpy as np
import pandas as pd


def regime_weights(base_weights: dict,
                   factors_ic: dict,
                   floor: float = 0.1,
                   max_dev: float = 0.5) -> dict:
    """
    按滚动 36m ICIR 调权（单期）。

    参数:
      base_weights: {因子: 基准权重}
      factors_ic: {因子: 该因子 IC 时间序列}（由 ic_monitor.ic_series 产出）
      floor: ICIR 地板（防归零，默认 0.1）
      max_dev: 单因子相对基准权重的最大偏离（默认 0.5 = ±50%）

    返回:
      {因子: 调整后权重}（已归一化）
    """
    w = {}
    raw = {}
    for f, b in base_weights.items():
        if f not in factors_ic:
            w[f] = b
            continue
        ic = factors_ic[f].dropna()
        if len(ic) < 12:  # 样本不足不调整
            w[f] = b
            continue
        icir = ic.mean() / ic.std(ddof=1) if ic.std(ddof=1) > 0 else 0.0
        raw[f] = max(icir, floor)
        w[f] = b * raw[f]

    # 相对缩放（按 ICIR 强弱，而非绝对值）
    mean_raw = np.mean(list(raw.values())) if raw else 1.0
    for f in raw:
        w[f] = base_weights[f] * raw[f] / mean_raw

    # 幅度上限约束 + 归一化交替迭代（先约束后归一化会突破上限，须收敛）
    for _ in range(50):
        for f in w:
            b = base_weights[f]
            w[f] = min(max(w[f], b * (1 - max_dev)), b * (1 + max_dev))
        total = sum(w.values())
        w = {f: v / total for f, v in w.items()}

    return w


def regime_weight_history(base_weights: dict,
                          factors_ic: dict,
                          quarterly_dates: pd.DatetimeIndex,
                          ic_window: int = 36,
                          floor: float = 0.1,
                          max_dev: float = 0.5) -> pd.DataFrame:
    """
    生成季度调权权重历史（严格 PIT：每个调权日只用其之前的数据）。

    对每个调权日 qd：取各因子 IC 序列中 index <= qd 的最近 ic_window 个月
    （不足 ic_window 则用全部可用历史；可用样本 <12 个月视为不足，保持基准
    权重），计算 ICIR = mean/std，交给 regime_weights() 完成相对缩放 +
    ±50% 约束 + 归一化。因此每行权重与
    regime_weights(base_weights, {f: ic_f.loc[:qd].iloc[-ic_window:]}) 完全一致。

    IC 序列由 ic_monitor.ic_series 产出（index=月末，值在当月末已知），
    故调权日 qd 可用 index <= qd 的全部 IC——无未来函数。

    参数:
      base_weights: {因子: 基准权重}
      factors_ic: {因子: 该因子全历史月度 IC 序列}（Dict[str, pd.Series]）
      quarterly_dates: 调权日列表（季末，DatetimeIndex）
      ic_window: ICIR 计算窗口（月，默认 36 与 v3 观察线一致）
      floor: ICIR 地板（防归零，默认 0.1）
      max_dev: 单因子相对基准权重的最大偏离（默认 0.5 = ±50%）

    返回:
      DataFrame: index=调权日, columns=因子, values=权重（每行已归一化）
    """
    rows = {}
    for qd in quarterly_dates:
        # PIT: 每个调权日只取 index <= qd 的 IC，且只用最近 ic_window 个月
        window_ic = {}
        for f in base_weights:
            ic = factors_ic.get(f)
            if ic is None:
                continue
            hist = ic.dropna()
            hist = hist[hist.index <= qd]
            if len(hist) == 0:
                continue
            window_ic[f] = hist.iloc[-ic_window:]
        rows[qd] = regime_weights(base_weights, window_ic, floor=floor,
                                  max_dev=max_dev)
    return pd.DataFrame(rows).T


if __name__ == '__main__':
    # ---- 冒烟测试: 单点调权逻辑 ----
    np.random.seed(3)
    dates = pd.date_range('2020-01-31', periods=48, freq='ME')
    base = {'EP': 0.2, 'BP': 0.2, 'ROE': 0.12, 'GPM': 0.06, 'MOM': 0.15,
            'TURN': 0.1, 'MCAP': 0.05, 'VOLR': 0.05, 'CFO': 0.05, 'LEV': 0.02}

    # 构造 IC 序列: MOM 强(0.05均值), 其他弱
    factors_ic = {}
    for f in base:
        mu = 0.05 if f == 'MOM' else 0.02
        factors_ic[f] = pd.Series(np.random.normal(mu, 0.10, 47), index=dates[1:])

    w_new = regime_weights(base, factors_ic)
    total = sum(w_new.values())
    print('调整后权重（归一化）:')
    for f, v in sorted(w_new.items(), key=lambda x: -x[1]):
        marker = ' ▲' if v > base[f] else (' ▼' if v < base[f] else '')
        print(f'  {f:6s} {v:.4f} (基准 {base[f]:.4f}){marker}')
    print(f'  合计: {total:.4f}')
    assert abs(total - 1.0) < 1e-9, '权重未归一化'
    assert w_new['MOM'] > base['MOM'], '强因子应上调'
    assert w_new['MOM'] <= base['MOM'] * 1.5 + 1e-9, '违反幅度上限'

    # ---- 冒烟测试: 季度权重历史 (PIT) ----
    hist_dates = pd.date_range('2022-03-31', periods=4, freq='QE')
    hist = regime_weight_history(base, factors_ic, hist_dates)
    print('\n季度调权权重历史（PIT）:')
    print(hist.round(4).to_string())
    # 每行归一化
    assert np.allclose(hist.sum(axis=1), 1.0, atol=1e-9), '权重历史未归一化'
    # PIT: 篡改调权日之后的数据不影响该日权重
    factors_ic_future = {f: s.copy() for f, s in factors_ic.items()}
    for f in factors_ic_future:
        factors_ic_future[f].iloc[-3:] = 9.9  # 污染 2023Q3+ 的"未来"IC
    hist2 = regime_weight_history(base, factors_ic_future, hist_dates)
    pd.testing.assert_frame_equal(hist, hist2)
    print('冒烟测试通过: 单点调权 + 季度权重历史 PIT（未来数据不影响历史权重）')
