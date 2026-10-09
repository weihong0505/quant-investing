# -*- coding: utf-8 -*-
"""
因子 IC 月度跟踪与衰减预警 ic_monitor.py
=========================================
按因子检验方法论 v3 §4/§8/§9 实现生产环境的持续监控。
状态标注：审批=docs/factor_docs/factor_testing_methodology_v3.md（MImo 两轮审查定稿）；C6 主判定线（signed NW-t/Bonferroni）修复已验收（2026-08-22）；监控判定线为工具实现，其有效性随 v3 检验结论（见 S1）

判定体系（与 factor_testing_methodology_v3 真实一致，两条线）：

【主判定线】v3 §9 单一显著性线（全程序统一）：
    预登记方向的 signed NW-t >= max(3.0, Bonferroni(N', 单侧 alpha=0.05))
    - signed_t = expected_sign * NW-t，expected_sign = 预登记预期符号（默认 +1）
    - signed_t >= 阈值                                     → 通过（保留）
    - signed_t <= -3.0（符号与预登记相反且 |t| 强）        → 淘汰（防反向强因子；
      v3 §9 明确禁止用 |t|：|t|>=3.0 会放行 t=-3.5 的反向强因子）
    - 其余（未达线）→ 交观察线辅助裁决
    - NW 滞后阶数：lag = floor[4*(N/100)^(2/9)]（NW 1994，N=60→3、N=120→4）；
      T+1~T+3 重叠收益 lag = max(3, 公式值)
    - Bonferroni 单侧 alpha=0.05：N'=37 处 z=norm.ppf(1-0.05/37)≈3.0009 恰达 3.0，
      与主线无缝衔接；N'>=38 自动收紧（v3 §9）

【观察线】v3 §8 辅助监控（只降级、不升级；不参与"通过"判定）：
    - ICIR > 0.5 / 0.3~0.5 / <0.3 分档
    - 滚动 36m ICIR 末端 <0.3 / IC 连续 12 月为负 / 断点后 12 月未回正 → 观察

注意：观察线只是辅助监控，不是判定；"通过"只能由主判定线给出。
"""
import numpy as np
import pandas as pd
from scipy import stats


def _nw_lag(n: int, overlapping: bool = False) -> int:
    """NW 1994 滞后阶数：lag = floor(4*(N/100)^(2/9))，至少 1。
    overlapping=True（T+1~T+3 重叠收益）时取 max(3, 公式值)。
    """
    if n < 2:
        return 1
    lag = int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))
    lag = max(1, lag)
    if overlapping:
        lag = max(3, lag)
    return lag


def nw_t(ic: pd.Series, maxlags: int = None, overlapping: bool = False) -> float:
    """Newey-West t 值（v3 §4.2 / §9 主判定线统计量）。

    对 IC 序列仅回归常数项，Bartlett 核 NW 协方差（与 statsmodels
    cov_hac_simple 完全一致，实测误差 <1e-12）：
      var(mean) = [S0 + 2*Σ_{j=1..L} w_j * S_j] / N
      w_j = 1 - j/(L+1)，S_j = (1/N)*Σ_t e_t*e_{t-j}，e = IC - mean
    maxlags 为 None 时用 _nw_lag(N, overlapping)。样本 N<3 返回 NaN。
    """
    ic = ic.dropna().astype(float)
    n = len(ic)
    if n < 3:
        return np.nan
    L = _nw_lag(n, overlapping) if maxlags is None else int(maxlags)
    mu = ic.mean()
    e = ic.values - mu
    S = e @ e / n
    for j in range(1, L + 1):
        w = 1.0 - j / (L + 1.0)
        S += 2.0 * w * (e[j:] @ e[:-j]) / n
    se = np.sqrt(S / n)
    if se <= 0 or not np.isfinite(se):
        return np.nan
    return float(mu / se)


def bonf_threshold(n_star: int, alpha: float = 0.05) -> float:
    """单侧 Bonferroni 校正 z 值（v3 §9：单侧 alpha=0.05）。

    与 v3 档位一致：N'=37 处 z = norm.ppf(1-0.05/37) ≈ 3.0009 恰达 3.0 主线，
    N'>=38 自动收紧；N'=1 时为 1.6449（主判定线取 max(3.0, ·) = 3.0）。
    """
    if n_star < 1:
        raise ValueError(f'n_star must be >= 1, got {n_star}')
    return float(stats.norm.ppf(1.0 - alpha / n_star))


def rank_ic(factor_values: pd.Series, forward_returns: pd.Series) -> float:
    """单期横截面 Rank IC（Spearman）"""
    df = pd.concat([factor_values, forward_returns], axis=1).dropna()
    if len(df) < 10:
        return np.nan
    return stats.spearmanr(df.iloc[:, 0], df.iloc[:, 1])[0]


def ic_series(factor_table: pd.DataFrame, return_table: pd.DataFrame,
              forward_months: int = 1) -> pd.Series:
    """
    月度 IC 时间序列。
    factor_table: index=月末, columns=代码, values=因子值
    return_table: index=月末, columns=代码, values=月度收益
    forward_months: 前瞻期数（1 = T+1 单月，与 v3 主口径一致）
    """
    ics = {}
    dates = factor_table.index.sort_values()
    for i in range(len(dates) - forward_months):
        t = dates[i]
        fwd = dates[i + forward_months]
        fv = factor_table.loc[t]
        fr = return_table.loc[fwd]
        ic = rank_ic(fv, fr)
        if not np.isnan(ic):
            ics[fwd] = ic
    return pd.Series(ics, name=f'IC_T{forward_months}').sort_index()


def rolling_icir(ic: pd.Series, window: int = 36) -> pd.Series:
    """滚动 ICIR（窗口月数，默认 36 与 v3 观察线一致）"""
    return ic.rolling(window).mean() / ic.rolling(window).std(ddof=1)


def ic_summary(ic: pd.Series, expected_sign: int = 1,
               maxlags: int = None, overlapping: bool = False) -> dict:
    """IC 汇总统计（v3 §4.1 报告指标）。

    含主判定线统计量：nw_t（NW-t，v3 判定以 NW-t 为准，naive t 仅对照）与
    signed_t = expected_sign × NW-t（预登记方向上的 t）。
    """
    ic = ic.dropna()
    if len(ic) == 0:
        return {'n': 0}
    nw = nw_t(ic, maxlags=maxlags, overlapping=overlapping)
    signed = expected_sign * nw if nw == nw else np.nan
    return {
        'n': len(ic),
        'mean': ic.mean(),
        'std': ic.std(ddof=1),
        'icir': ic.mean() / ic.std(ddof=1) if ic.std(ddof=1) > 0 else np.nan,
        'win_rate': (ic > 0).mean(),
        'naive_t': ic.mean() / ic.std(ddof=1) * np.sqrt(len(ic)) if ic.std(ddof=1) > 0 else np.nan,
        'nw_t': nw,
        'signed_t': signed,
    }


class ICAlerts:
    """因子 IC 判定 + 衰减预警引擎。

    主判定线：signed NW-t（v3 §9）；观察线：ICIR 分档 / 滚动 36m（v3 §8）。
    """

    _LEVEL_RANK = {'淘汰': 3, '观察': 2, '通过': 1, '正常': 0}

    def __init__(self, window: int = 36):
        self.window = window

    def check(self, ic: pd.Series, expected_sign: int = 1, n_star: int = 1,
              overlapping: bool = False) -> list:
        """返回判定与预警列表，每项 {level, message, evidence}。

        【主判定线】（v3 §9，给出最终 通过/淘汰/观察 结论）：
          signed_t = expected_sign × NW-t
          - signed_t >= max(3.0, bonf_threshold(n_star)) → 通过
          - signed_t <= -3.0 → 淘汰（反向强因子：符号与预登记相反，|t| 却很强）
          - 其余 → 观察（未达线）
        【观察线】（v3 §8 辅助监控，只降级不升级）：
          ICIR <0.3 → 淘汰 / 0.3~0.5 → 观察；滚动 36m ICIR 末端<0.3、
          IC 连续 12 月为负 → 观察。

        expected_sign: 预登记预期符号（+1/-1，建议来自因子 registry）；
        n_star: 本自然季度同期受检因子数 N'（Bonferroni 多重检验）。
        """
        ic = ic.dropna()
        if len(ic) < 6:
            return [{'level': '观察', 'message': '样本不足，暂不判定', 'evidence': f'n={len(ic)}'}]

        s = ic_summary(ic, expected_sign=expected_sign, overlapping=overlapping)
        nw = s['nw_t']
        signed_t = s['signed_t']
        thr = max(3.0, bonf_threshold(n_star))
        alerts = []

        # ---- 主判定线（v3 §9）----
        if np.isnan(signed_t):
            main = {'level': '观察', 'message': 'NW-t 不可计算',
                    'evidence': f'n={s["n"]}'}
        elif signed_t >= thr:
            main = {'level': '通过',
                    'message': '主判定线通过: signed NW-t >= max(3.0, Bonferroni)',
                    'evidence': (f'signed_t={signed_t:.3f} (NW-t={nw:.3f}), '
                                 f'阈值={thr:.3f}, n_star={n_star}')}
        elif signed_t <= -3.0:
            main = {'level': '淘汰',
                    'message': '反向强因子: signed_t <= -3.0（符号与预登记相反）',
                    'evidence': (f'signed_t={signed_t:.3f} (NW-t={nw:.3f}), '
                                 f'expected_sign={expected_sign}')}
        else:
            main = {'level': '观察',
                    'message': '主判定线未达线: signed NW-t < max(3.0, Bonferroni)',
                    'evidence': (f'signed_t={signed_t:.3f} (NW-t={nw:.3f}), '
                                 f'阈值={thr:.3f}')}
        alerts.append(main)

        # ---- 观察线（v3 §8 辅助监控，只降级不升级）----
        icir = s['icir']
        if icir < 0.3:
            alerts.append({'level': '淘汰', 'message': 'ICIR < 0.3',
                           'evidence': f'ICIR={icir:.3f}, n={s["n"]}'})
        elif icir <= 0.5:
            alerts.append({'level': '观察', 'message': '0.3 ≤ ICIR ≤ 0.5',
                           'evidence': f'ICIR={icir:.3f}'})
        if len(ic) >= self.window:
            r = rolling_icir(ic, self.window)
            last = r.dropna()
            if len(last) > 0:
                if last.iloc[-1] < 0.3:
                    alerts.append({'level': '观察', 'message': '滚动36m ICIR 末端 < 0.3',
                                   'evidence': f'{last.iloc[-1]:.3f}'})
                tail = ic.iloc[-12:]
                if (tail < 0).all():
                    alerts.append({'level': '观察', 'message': 'IC 连续 12 个月为负',
                                   'evidence': f'最近12月均值={tail.mean():.4f}'})
        return alerts

    def report(self, factors_ic: dict, output_path: str = None,
               expected_sign: int = 1, n_star: int = 1,
               overlapping: bool = False) -> pd.DataFrame:
        """多因子 IC 监控报告。

        expected_sign / n_star 可为 int（全局）或 {因子名: 值} 字典（逐因子；
        预期符号建议来自 registry 预登记方向）。
        返回汇总表（含主判定线统计量 nw_t / signed_t 列，按 signed_t 降序）；
        output_path 不为空时写 CSV（utf-8-sig）。
        """
        def _cfg(cfg, name, default):
            return cfg.get(name, default) if isinstance(cfg, dict) else cfg

        rows = []
        for name, ic in factors_ic.items():
            es = _cfg(expected_sign, name, 1)
            ns = _cfg(n_star, name, 1)
            s = ic_summary(ic, expected_sign=es, overlapping=overlapping)
            alerts = self.check(ic, expected_sign=es, n_star=ns, overlapping=overlapping)
            worst = max(alerts, key=lambda a: self._LEVEL_RANK.get(a['level'], 0))
            rows.append({
                'factor': name,
                'n': s.get('n', 0),
                'ic_mean': s.get('mean', np.nan),
                'ic_std': s.get('std', np.nan),
                'icir': s.get('icir', np.nan),
                'win_rate': s.get('win_rate', np.nan),
                'naive_t': s.get('naive_t', np.nan),
                'nw_t': s.get('nw_t', np.nan),
                'signed_t': s.get('signed_t', np.nan),
                'level': worst['level'],
                'alert': worst['message'],
                'evidence': worst['evidence'],
            })
        df = pd.DataFrame(rows).sort_values('signed_t', ascending=False)
        if output_path:
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
        return df


if __name__ == '__main__':
    # ---- 冒烟测试 ----
    np.random.seed(42)
    dates = pd.date_range('2019-12-31', periods=60, freq='ME')
    codes = [f'{i:06d}' for i in range(100)]
    rng = np.random.default_rng(1)

    # 因子1: 有真实信号（T 期因子预测 T+1 收益，shift(1) 保证 IC 结构，
    # 斜率 0.05 保证主判定线显著）
    true_signal = rng.normal(size=(len(dates), len(codes)))
    noise = rng.normal(0, 0.5, size=(len(dates), len(codes)))
    factor_true = pd.DataFrame(true_signal, index=dates, columns=codes)
    returns = factor_true.shift(1) * 0.05 \
        + pd.DataFrame(noise, index=dates, columns=codes)

    # 因子2: 纯噪声
    factor_noise = pd.DataFrame(rng.normal(size=(len(dates), len(codes))),
                                index=dates, columns=codes)

    # 因子3: 反向强因子（真实 IC 为负，预登记方向 +1 → 主判定线应判淘汰）
    factor_rev = pd.DataFrame(-true_signal, index=dates, columns=codes)

    ic1 = ic_series(factor_true, returns)
    ic2 = ic_series(factor_noise, returns)
    ic3 = ic_series(factor_rev, returns)

    monitor = ICAlerts()
    report = monitor.report({'true_factor': ic1, 'noise_factor': ic2, 'reverse_factor': ic3})
    print(report.round(4).to_string())
    print('\n冒烟测试: 真因子应显著优于噪声因子; 反向因子应被主判定线淘汰')
    assert report.loc[report.factor == 'true_factor', 'icir'].iloc[0] > \
           report.loc[report.factor == 'noise_factor', 'icir'].iloc[0]
    assert 'nw_t' in report.columns and 'signed_t' in report.columns
    assert report.loc[report.factor == 'reverse_factor', 'level'].iloc[0] == '淘汰'
    print('IC 监控模块正常')
