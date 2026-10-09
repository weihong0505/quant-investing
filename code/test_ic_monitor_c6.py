# -*- coding: utf-8 -*-
"""
C6 验收测试: ic_monitor.py v3 主判定线（signed NW-t / Bonferroni）
运行: D:/pyh/python.exe -E test_ic_monitor_c6.py
验收标准:
  ① 构造 IC 序列（mean>0 强相关）→ signed_t >= 3.0 判定"通过"
  ② 纯噪声 → 不通过
  ③ 反向强 IC（expected_sign=+1 但真实为负）→ 判定"淘汰"（核心用例）
  ④ NW-t 与 statsmodels HAC 结果一致（误差 <1e-6）
  ⑤ 冒烟测试保持通过，报告表含新列（nw_t / signed_t）
"""
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

import ic_monitor as icm


def ar1_ic(n, mu, rho, seed):
    """AR(1) 自相关 IC 序列（均值 mu，自相关 rho），模拟有自相关的月度 IC"""
    rng = np.random.default_rng(seed)
    e = rng.normal(0, 1, n)
    x = np.empty(n)
    x[0] = e[0]
    for t in range(1, n):
        x[t] = rho * x[t - 1] + e[t]
    return pd.Series(x + mu, name='IC')


def main():
    results = []
    ok_all = True

    def check(name, cond, detail=''):
        nonlocal ok_all
        status = 'PASS' if cond else 'FAIL'
        if not cond:
            ok_all = False
        results.append((status, name, detail))
        print(f'[{status}] {name}  {detail}')

    # ---- ④ NW-t vs statsmodels HAC（不同 N/自相关/符号）----
    for n, mu, rho, seed in [(120, 0.3, 0.3, 7), (60, 0.2, 0.0, 11), (36, -0.25, 0.5, 13)]:
        ic = ar1_ic(n, mu, rho, seed)
        L = icm._nw_lag(n)
        X = np.ones((n, 1))
        t_sm = sm.OLS(ic.values, X).fit(cov_type='HAC',
                                        cov_kwds={'maxlags': L}).tvalues[0]
        t_my = icm.nw_t(ic)
        check(f'④ NW-t == statsmodels HAC (n={n}, rho={rho})',
              abs(t_sm - t_my) < 1e-6, f'diff={abs(t_sm - t_my):.2e}')

    # ---- 带宽公式（v3 §4.2）----
    check('带宽 N=60 -> lag 3', icm._nw_lag(60) == 3, f'got {icm._nw_lag(60)}')
    check('带宽 N=120 -> lag 4', icm._nw_lag(120) == 4, f'got {icm._nw_lag(120)}')
    check('重叠收益 max(3, 公式值)', icm._nw_lag(20, overlapping=True) == 3
          and icm._nw_lag(120, overlapping=True) == 4,
          f'20->{icm._nw_lag(20, overlapping=True)}, 120->{icm._nw_lag(120, overlapping=True)}')

    # ---- Bonferroni 档位（v3 §9: N'=37 处 z≈3.0，与主线 max(3.0,·) 无缝衔接）----
    from scipy.stats import norm
    b1, b37, b38 = (icm.bonf_threshold(1), icm.bonf_threshold(37),
                    icm.bonf_threshold(38))
    check('bonf(1) = 1.6449 (单因子不收紧)',
          abs(b1 - norm.ppf(1 - 0.05 / 1)) < 1e-12, f'{b1:.6f}')
    check('bonf(37) ~= 2.9997 恰达主线 (max(3.0,·)=3.0 无缝衔接)',
          abs(b37 - norm.ppf(1 - 0.05 / 37)) < 1e-12
          and max(3.0, b37) == 3.0, f'{b37:.6f}')
    check('bonf(38) > 3.0 自动收紧',
          b38 == norm.ppf(1 - 0.05 / 38) and b38 > 3.0, f'{b38:.6f}')

    # ---- ① 强正 IC → 主判定线通过 ----
    ic_pos = ar1_ic(120, 0.8, 0.3, 42)
    s_pos = icm.ic_summary(ic_pos)
    al_pos = icm.ICAlerts().check(ic_pos)
    check('① 强正 IC: signed_t >= 3.0', s_pos['signed_t'] >= 3.0,
          f'signed_t={s_pos["signed_t"]:.3f} (NW-t={s_pos["nw_t"]:.3f})')
    check('① 判定 = 通过', al_pos[0]['level'] == '通过', al_pos[0]['message'])

    # ---- ② 纯噪声 → 不通过 ----
    ic_noise = ar1_ic(120, 0.0, 0.0, 99)
    s_noise = icm.ic_summary(ic_noise)
    al_noise = icm.ICAlerts().check(ic_noise)
    check('② 纯噪声: |signed_t| < 3.0', abs(s_noise['signed_t']) < 3.0,
          f'signed_t={s_noise["signed_t"]:.3f}')
    check('② 判定 != 通过', al_noise[0]['level'] != '通过',
          f'level={al_noise[0]["level"]} ({al_noise[0]["message"]})')

    # ---- ③ 反向强 IC → 淘汰（核心用例）----
    ic_neg = ar1_ic(120, -0.8, 0.3, 7)
    s_neg = icm.ic_summary(ic_neg, expected_sign=+1)
    al_neg = icm.ICAlerts().check(ic_neg, expected_sign=+1)
    check('③ 反向强 IC: signed_t <= -3.0', s_neg['signed_t'] <= -3.0,
          f'signed_t={s_neg["signed_t"]:.3f} (NW-t={s_neg["nw_t"]:.3f})')
    check('③ 判定 = 淘汰（反向强因子）',
          al_neg[0]['level'] == '淘汰' and '反向强因子' in al_neg[0]['message'],
          al_neg[0]['message'])
    # 对照组: 同一序列若预登记方向为 -1，应判通过（signed 检查不误杀）
    al_neg_ctrl = icm.ICAlerts().check(ic_neg, expected_sign=-1)
    check('③ 对照: expected_sign=-1 时同一序列判通过',
          al_neg_ctrl[0]['level'] == '通过', al_neg_ctrl[0]['message'])

    # ---- ⑤ 报告新列 + 冒烟测试 ----
    dates = pd.date_range('2019-12-31', periods=60, freq='ME')
    codes = [f'{i:06d}' for i in range(100)]
    rng = np.random.default_rng(1)
    sig = rng.normal(size=(len(dates), len(codes)))
    # 收益含 T 期因子对 T+1 收益的预测结构（shift(1)）：IC = corr(factor_T, ret_T+1)
    rets = pd.DataFrame(sig, index=dates, columns=codes).shift(1) * 0.05 \
        + pd.DataFrame(rng.normal(0, 0.5, size=(len(dates), len(codes))),
                       index=dates, columns=codes)
    f_true = pd.DataFrame(sig, index=dates, columns=codes)
    f_noise = pd.DataFrame(rng.normal(size=(len(dates), len(codes))),
                           index=dates, columns=codes)
    f_rev = pd.DataFrame(-sig, index=dates, columns=codes)
    rep = icm.ICAlerts().report({
        'true': icm.ic_series(f_true, rets),
        'noise': icm.ic_series(f_noise, rets),
        'reverse': icm.ic_series(f_rev, rets),
    })
    check('⑤ report 含 nw_t / signed_t 列',
          {'nw_t', 'signed_t'} <= set(rep.columns),
          f'columns={list(rep.columns)}')
    lv = dict(zip(rep.factor, rep.level))
    check('⑤ report: true = 通过', lv['true'] == '通过', lv['true'])
    check('⑤ report: reverse = 淘汰', lv['reverse'] == '淘汰', lv['reverse'])
    check('⑤ report: noise != 通过', lv['noise'] != '通过', lv['noise'])
    check('⑤ report 按 signed_t 降序',
          rep['signed_t'].iloc[0] == rep['signed_t'].max())

    # 冒烟测试（模块 __main__）
    r = subprocess.run([sys.executable, '-E', 'ic_monitor.py'],
                       capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.abspath(__file__)))
    check('⑤ 冒烟测试 exit 0', r.returncode == 0,
          r.stdout[-300:] if r.returncode else 'ok')

    print('\n===== SUMMARY =====')
    n_fail = sum(1 for st, _, _ in results if st == 'FAIL')
    print(f'PASS={len(results) - n_fail}/{len(results)}  FAIL={n_fail}')
    sys.exit(1 if n_fail else 0)


if __name__ == '__main__':
    main()
