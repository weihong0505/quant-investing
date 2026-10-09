---
title: Regime 动态调权 regime_weights.py
created: 2026-08-21
updated: 2026-08-25
type: entity
tags: [system, tool, regime, weight-change]
sources: [G:/股市探究/quant-investing/code/regime_weights.py, research/regime_based_weights.md, factor_docs/regime_weights_review_20260822.md]
confidence: 60
---

# Regime 动态调权 regime_weights.py

> ✅ **设计已审（有条件通过，2026-08-22）**。审查报告：`docs/factor_docs/regime_weights_review_20260822.md`（SOP §3.0 存档）。
>
> 定位 = **研究验证工具**：输出仅用于评估季度调权相对固定权重的增量价值（设计文档 §5）。
> ⛔ 未满足以下条件前，禁止用于实盘权重：
> 1. 因子通过 v3 统计检验 + 共线性闸门（先检验后集成，SOP §3.0.2）
> 2. 调权增益（净成本）验证为正且 2x 成本敏感性稳健
> 3. 参数敏感性（floor/max_dev/ic_window ±20%）与同簇因子同步顶限检查完成

## 概述

方案 A：滚动 36m ICIR 季度调权——与 v3 滚动观察线复用同一统计量，无新增过拟合面。
- 季度调权、严格 PIT（调权日只用截至当日的历史数据）
- 单因子权重偏离基准 ≤ ±50%，floor=0.1 防归零
- 约束 + 归一化交替迭代 50 次收敛

## 代码位置

`G:/股市探究/quant-investing/code/regime_weights.py`

设计文档：`research/regime_based_weights.md`　|　审查报告：`factor_docs/regime_weights_review_20260822.md`

## 核心函数

| 函数 | 功能 |
|------|------|
| `regime_weights(base_weights, factors_ic, floor, max_dev)` | 单期调权（ICIR 相对缩放 + ±50% 约束 + 归一化） |
| `regime_weight_history(base_weights, factors_ic, quarterly_dates, ic_window, floor, max_dev)` | 季度权重历史（PIT：每期只用截至调权日最近 ic_window 个月 IC；IC 由 ic_monitor.ic_series 产出） |

## 调权公式

```
w_i = w_i^base × max(icir_i, 0.1) / mean(raw)   # ICIR 相对强弱缩放
约束: 0.5×w_base ≤ w ≤ 1.5×w_base（±50% 幅度上限）
归一化与约束交替迭代 50 次收敛
```

## 红线（审批结论）

1. 调权只作用于已通过 v3 统计检验 + 共线性闸门的因子
2. 权重调整规则样本外确定：公式/参数 2026-08-22 定稿冻结，禁止按回测结果回调（一次确认制）
3. 验证要求：对比固定权重（净成本）+ 2x 成本敏感性 + 参数敏感性 ±20% + 同簇因子同步顶限检查
4. 调权增益（净成本）不稳健 → 方案 A 终止，回设计阶段

## 相关页面

- [[ic-monitor]] — IC/ICIR 数据流上游（ic_series 产出每因子 IC 序列）
- [[weighted-scoring]] — 基准权重的合成逻辑
- [[factor-decay]] — 调权的动机（因子衰减）
