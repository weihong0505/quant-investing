# -*- coding: utf-8 -*-
"""
滚动窗口描述统计 rolling_stats.py
=================================
注意：本模块是**滚动窗口描述统计**，不是 walk-forward 验证——
它对一条已算好的月收益序列做滑动窗口的均值/夏普/累计收益统计，
不做训练段选参、不在测试段重跑策略。
状态标注：C7 方案B 已验收（2026-08-22，由 walk_forward.py 改名去伪）；描述统计工具非策略判定依据——未审批/未检验（实验）

真正的 walk-forward（训练段定参 → 测试段跑一次 → 一次确认制）需要策略函数
参与，本模块不提供；防过拟合红线见 SOP §3.3-5，判定只能由 v3 主判定线
（signed NW-t）给出，见 ic_monitor.ICAlerts。

结构与 v3 §3-5 样本划分条款对齐：
  主判定样本 2017+ / 主回测 2019+ / 训练段=检验日−24m / 最近24m=样本外确认段
  （样本外一次确认见 one_time_confirmation）
"""
import sys

import numpy as np
import pandas as pd


def rolling_window_stats(monthly_returns: pd.Series,
                         train_months: int = 36,
                         test_months: int = 12,
                         ) -> pd.DataFrame:
    """
    滚动窗口描述统计（非 walk-forward）。

    对 monthly_returns 按 train_months+test_months 窗口滑动切分，每个窗口输出
    训练段/测试段的均值、夏普、测试段累计收益等描述统计量。
    只做统计，不做任何参数选择或策略重跑。

    参数:
      monthly_returns: 策略月收益（或超额月收益）
      train_months: 窗口前段月数（默认 36 月，与 v3 滚动窗口一致）
      test_months: 窗口后段月数（默认 12 月）

    返回 DataFrame: [window_id, train_start, train_end, test_start, test_end,
                     train_mean, train_sharpe, test_mean, test_sharpe, test_cumret]
    """
    returns = monthly_returns.dropna()
    n = len(returns)
    if n < train_months + test_months:
        raise ValueError(f'样本不足: n={n} < {train_months}+{test_months}')

    rows = []
    start = 0
    while start + train_months + test_months <= n:
        train = returns.iloc[start:start + train_months]
        test = returns.iloc[start + train_months:start + train_months + test_months]
        rows.append({
            'window_id': len(rows) + 1,
            'train_start': train.index[0],
            'train_end': train.index[-1],
            'test_start': test.index[0],
            'test_end': test.index[-1],
            'train_mean': train.mean(),
            'train_sharpe': train.mean() / train.std(ddof=1) * np.sqrt(12) if train.std(ddof=1) > 0 else np.nan,
            'test_mean': test.mean(),
            'test_sharpe': test.mean() / test.std(ddof=1) * np.sqrt(12) if test.std(ddof=1) > 0 else np.nan,
            'test_cumret': (1 + test).prod() - 1,
        })
        start += test_months
    return pd.DataFrame(rows)


def _evidence_strength(oos_months: int) -> str:
    """证据强度分级（非'通过/观察'判定）。

    项目实测（backtest_engineering_spec 审查）：90 月回测检出功效仅 20.3%
    （3% 超额 @ TE10%），短于 90 月的样本功效更低——任何分级都不构成
    '策略有效'的判定，只描述统计证据的相对充分程度：
      - 'none'  : OOS 样本 < 24 月，不足以形成任何方向性结论
      - 'weak'  : 24 月 ≤ OOS < 90 月，低于项目功效参考线（90 月 / 20.3%）
      - 'strong': OOS ≥ 90 月，达到项目功效参考样本量；检出功效仍仅 ~20.3%，
                  结论必须声明样本功效限制
    """
    if oos_months < 24:
        return 'none'
    if oos_months < 90:
        return 'weak'
    return 'strong'


def rolling_stats_summary(wf: pd.DataFrame, test_months: int = 12) -> dict:
    """
    滚动窗口统计汇总（只报告统计量 + 证据强度分级，不做"通过/观察"判定）。

    输出:
      windows: 窗口数
      oos_months: 样本外总月数（windows × test_months）
      oos_win_rate: 测试段均值 > 0 的窗口比例（描述性，非判定线）
      oos_cum_return: 全部测试段拼接的累计收益（描述性）
      train_test_consistency: 训练段与测试段均值符号一致的窗口比例（报告项）
      verdict: 证据强度分级 'strong'/'weak'/'none'（按 OOS 样本量，
               不是"通过/失败"式策略判定）
      power_warning: 样本功效警示，报告引用任何统计量时必须随附声明

    注意: 本项目实测 90 月回测检出功效仅 20.3%（3% 超额 @ TE10%），
    短样本上统计量功效有限，一律不作"通过/观察"判定；
    判定只能由 v3 主判定线（signed NW-t）给出，见 ic_monitor.ICAlerts。
    """
    n = len(wf)
    if n == 0:
        return {
            'windows': 0,
            'oos_months': 0,
            'verdict': 'none',
            'power_warning': ('样本功效警示: 无样本外窗口，无任何结论依据; '
                              '项目实测 90 月回测检出功效仅 20.3%（3% 超额 @ TE10%），'
                              '报告时必须声明样本功效限制。'),
        }
    oos_months = n * test_months
    oos_win = (wf['test_mean'] > 0).mean()
    oos_cum = (1 + wf['test_cumret']).prod() - 1
    consistency = ((wf['train_mean'] > 0) == (wf['test_mean'] > 0)).mean()
    verdict = _evidence_strength(oos_months)
    power_warning = (
        f'样本功效警示: 项目实测 90 月回测检出功效仅 20.3%（3% 超额 @ TE10%，'
        f'见 backtest_engineering_spec 审查）; 本汇总 OOS 仅 {oos_months} 月'
        f'（{n} 窗 × {test_months} 月），证据强度 {verdict} 只描述统计充分性，'
        f'不构成策略有效/无效判定; 引用本报告任何统计量时必须同时声明此样本功效限制。'
    )
    return {
        'windows': n,
        'oos_months': oos_months,
        'oos_win_rate': oos_win,
        'oos_cum_return': oos_cum,
        'train_test_consistency': consistency,
        'verdict': verdict,
        'power_warning': power_warning,
    }


def one_time_confirmation(train_returns: pd.Series,
                          test_returns: pd.Series,
                          threshold: float = 0.0) -> dict:
    """
    一次确认制（v3 §3-5）：训练段定参数 → 测试段只跑一次 → 确认失败即降级，
    禁止回训调参后重报。
    """
    train_mean = train_returns.mean()
    test_mean = test_returns.mean()
    confirmed = test_mean > threshold and train_mean > threshold
    return {
        'train_mean': train_mean,
        'test_mean': test_mean,
        'confirmed': bool(confirmed),
        'rule': '确认失败 → 降级观察，禁止回训重报（一次确认制）',
    }


if __name__ == '__main__':
    # ---- 冒烟测试 ----
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    np.random.seed(7)
    # 合成: 前 60 月有 alpha，后 36 月衰减
    dates = pd.date_range('2018-01-31', periods=96, freq='ME')
    r1 = np.random.normal(0.008, 0.04, 60)
    r2 = np.random.normal(-0.002, 0.04, 36)
    rets = pd.Series(np.concatenate([r1, r2]), index=dates)

    stats = rolling_window_stats(rets, train_months=36, test_months=12)
    print('滚动窗口描述统计 (rolling_stats.py):')
    print(stats.round(4).to_string())
    summary = rolling_stats_summary(stats, test_months=12)
    print('\n汇总(统计量 + 证据强度分级):')
    for k, v in summary.items():
        print(f'  {k}: {v if k != "power_warning" else v}')
    assert summary['windows'] == 5, '窗口数应为 5'
    assert summary['oos_months'] == 60, 'OOS 总月数应为 60'
    assert summary['verdict'] in ('strong', 'weak', 'none'), 'verdict 必须是证据强度分级'
    assert summary['verdict'] == 'weak', '96 月合成数据 OOS=60 月(<90) 应为 weak'
    assert '通过' not in str(summary['verdict']), 'verdict 不得含"通过"式判定措辞'
    assert 'power_warning' in summary and '20.3%' in summary['power_warning'], \
        '必须附样本功效警示并引用 90 月/20.3% 实测结论'
    assert 'train_test_consistency' in summary, 'train_test_consistency 保留为报告项'

    # 一次确认制示例
    train = rets.iloc[:60]
    test = rets.iloc[60:]
    oc = one_time_confirmation(train, test)
    print('\n一次确认制:', {k: (round(v, 4) if isinstance(v, float) else v)
                           for k, v in oc.items()})
    # 预期: 测试段均值为负 → confirmed=False（策略衰减被正确识别）
    assert oc['confirmed'] is False, '衰减未被识别'

    # 证据强度分级边界: 90 月以上才到 strong
    assert _evidence_strength(23) == 'none' and _evidence_strength(24) == 'weak'
    assert _evidence_strength(89) == 'weak' and _evidence_strength(90) == 'strong'
    print('\n冒烟测试通过: 滚动窗口统计正常输出; 衰减策略被一次确认制正确拦截; '
          'verdict 为证据强度分级(无通过/观察判定), 附 20.3% 功效警示')
