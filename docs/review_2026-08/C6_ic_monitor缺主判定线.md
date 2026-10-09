# C6 — ic_monitor.py 未实现 v3 主判定线（signed NW-t / Bonferroni）

> ✅ 已验收 2026-08-22 操作者: AI-C6

> 来源：项目复盘 2026-08-22 第 C6 项（Wiki 全文：G:\quant-investing\wiki\comparisons\project-review-2026-08.md）
> 严重度：🟠 重大　|　任务性质：代码修复　|　涉及文件：code/ic_monitor.py
> 依赖：无　|　建议优先级：第五批

## 1. 问题现状

IC 监控模块自述"按因子检验方法论 v3 实现生产环境的持续监控"，但实际上只实现了 v3 的**观察线**（ICIR 0.3/0.5 分档、滚动 36m 观察），v3 的**主判定线**完全缺失——监控器永远无法给出"淘汰/通过"的判定结论。

## 2. 证据

- `code/ic_monitor.py` `ICAlerts.check()`：只有 `icir < 0.3 → 淘汰 / ≤0.5 → 观察` + 滚动 36m ICIR 末端 <0.3 + 连续 12 月负 IC——全部是观察档逻辑
- v3 定稿 `factor_testing_methodology_v3.md` L165：主判定线 = **预登记方向 signed NW-t ≥ max(3.0, Bonferroni(N', 单侧α=0.05))**；L170 明确"必须 signed，|t| 会放行符号与预登记相反的强因子"
- 监控器中没有：Newey-West t 值计算、Bonferroni 阈值、预期符号参数与检查

## 3. 为什么是错

1. 生产监控与定稿方法论脱节：监控器给出的最高结论只是"观察"，因子真失效（t 显著为负）时无法自动触发淘汰判定
2. v3 明确警告过"|t| 会放行反向强因子"——如果未来补一个 naive t 却不做 signed 检查，会重复 v3 已经纠正过的错误
3. "与 v3 判定线一致"的 docstring 声明（模块头）是假的

## 4. 修改要求

1. 在 `ic_monitor.py` 增加：
   - `nw_t(ic: pd.Series) -> float`：Newey-West t 值。带宽 `floor(4×(N/100)^(2/9))`（NW 1994，与 statsmodels cov_hac 一致）；N=60→lag3、N=120→lag4；T+1~T+3 重叠收益用 `max(3, 公式值)`。可用 statsmodels `OLS(...).fit(cov_type='HAC', cov_kwds={'maxlags': L}).tvalues[0]` 或手写协方差阵
   - `bonf_threshold(n_star: int, alpha: float = 0.05) -> float`：单侧 Bonferroni z 值
   - `check(ic, expected_sign=+1, n_star=1)` 增加参数：**signed** t = expected_sign × NW-t；判定线 `signed_t >= max(3.0, bonf_threshold(n_star))`；signed_t ≤ −3.0 且符号与预期相反 → 淘汰（防反向强因子）
2. `ic_summary` 增加 `nw_t`、`signed_t` 字段；`report` 输出列同步
3. docstring 区分两条线：主判定线（signed NW-t）与观察线（ICIR 分档）——后者只是辅助监控，不是判定
4. 参考文件：`docs/factor_docs/factor_testing_methodology_v3.md` 全文；统计细节可直接采用项目已实测过的数值结论（NW 带宽、Bonf 档位表，见方法论 v3 与 skill a-share-factor-stats）

## 5. 验收标准

- [x] 合成数据用例：构造 IC 序列（mean>0 强相关）→ signed_t ≥ 3.0 判定"通过"；纯噪声 → 不通过；构造**反向**强 IC（expected_sign=+1 但真实为负）→ 判定淘汰（这是 signed 检查的核心用例）
- [x] NW-t 与手算/`statsmodels` HAC 结果一致（误差 <1e-6，实测 diff≈1e-15）
- [x] 冒烟测试保持通过，报告表含新列（nw_t / signed_t；22/22 用例通过，输出见 C6_validation_output.txt）
- [x] docstring 不再声称"与 v3 判定线一致"但实际缺失（主判定线/观察线已分开写明，且与 v3 §9/§8 真实一致）

## 6. 修改后需同步的文档

- wiki/entities/system/ic-monitor.md（判定线说明更新）
