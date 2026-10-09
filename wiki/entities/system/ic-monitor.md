---

title: IC 跟踪与衰减预警 ic_monitor.py

created: 2026-08-21

updated: 2026-08-25

type: entity

tags: [system, tool, factor-test, decay]

sources: [G:/股市探究/quant-investing/code/ic_monitor.py]

confidence: 80

---



# IC 跟踪与衰减预警 ic_monitor.py



## 概述

生产环境的因子持续监控：月度 Rank IC / ICIR / 胜率滚动更新 + 衰减预警。

判定线与 [[factor-testing-methodology]] v3 一致。



## 代码位置

`G:/股市探究/quant-investing/code\ic_monitor.py`



## 判定线（两条线，与 v3 §9/§8 真实一致）

**主判定线（v3 §9 单一显著性线，给出最终 通过/淘汰/观察 结论）**：
```
预登记方向的 signed NW-t ≥ max(3.0, Bonferroni(N', 单侧 α=0.05))
```
- signed_t = expected_sign × NW-t（expected_sign = 预登记预期符号，默认 +1）
- signed_t ≥ 阈值 → 通过；signed_t ≤ −3.0（符号与预登记相反）→ 淘汰（防反向强因子，禁止用 |t|）
- 其余 → 观察（未达线）
- NW 滞后：lag = floor[4×(N/100)^(2/9)]（NW 1994，N=60→3、N=120→4）；T+1~T+3 重叠收益 max(3, 公式值)
- Bonferroni 单侧 α=0.05：N'=37 处 z≈2.9997，max(3.0,·) 后与主线无缝衔接；N'≥38 自动收紧

**观察线（v3 §8 辅助监控，只降级不升级，不参与"通过"判定）**：
| 档位 | 标准 |
|------|------|
| 保留 | ICIR > 0.5 |
| 观察 | 0.3 ≤ ICIR ≤ 0.5 |
| 淘汰 | ICIR < 0.3 |

- 滚动 36m：末端 ICIR < 0.3 / IC 连续 12 月为负 / 断点后 12 月未回正 → 任一触发降级观察

## 接口
- `rank_ic(factor_values, forward_returns)` — 单期横截面 Spearman
- `ic_series(factor_table, return_table)` — 月度 IC 时间序列（T+1 主口径）
- `nw_t(ic, maxlags=None, overlapping=False)` — Newey-West t（与 statsmodels HAC 一致）
- `bonf_threshold(n_star, alpha=0.05)` — 单侧 Bonferroni z 值
- `ic_summary(ic, expected_sign=1, ...)` — 汇总（含 nw_t / signed_t 字段）
- `ICAlerts.check(ic, expected_sign=1, n_star=1)` / `ICAlerts.report(factors_ic, expected_sign, n_star)` — 判定与多因子报告（报告表含 nw_t / signed_t 列）

## 相关页面

- [[factor-testing-methodology]] — 判定线出处

- [[factor-decay]] — 衰减现象概念

- [[regime-weights]] — IC 数据流的下游消费者（调权）

