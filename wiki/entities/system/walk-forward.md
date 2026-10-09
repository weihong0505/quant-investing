---
title: 滚动窗口统计 rolling_stats.py（非 walk-forward）
created: 2026-08-21
updated: 2026-08-25
type: entity
tags: [system, tool, backtest]
sources: [G:/股市探究/quant-investing/code/rolling_stats.py]
confidence: 80
---

# 滚动窗口统计 rolling_stats.py（非 walk-forward）

## 概述
滚动窗口**描述统计**工具：对一条已算好的月收益序列做滑动窗口的均值/夏普/累计收益统计。
**不是 walk-forward 验证**——不做训练段选参、不在测试段重跑策略。
防过拟合判定只能由 v3 主判定线（signed NW-t）给出，见 ic_monitor.ICAlerts。

> 改名背景：原 walk_forward.py 自称 walk-forward 实为窗口描述统计（复盘 C7），
> 已按方案 B 改名为 rolling_stats.py 并去除伪判定，见
> docs/review_2026-08/C7_walk_forward名不副实.md。

## 代码位置
`G:/股市探究/quant-investing/code/rolling_stats.py`

## 核心函数
| 函数 | 功能 |
|------|------|
| `rolling_window_stats(returns, train_months, test_months)` | 滚动切分并输出各窗描述统计（默认 36+12 月） |
| `rolling_stats_summary(wf, test_months)` | 汇总统计量 + 证据强度分级（strong/weak/none），附样本功效警示 |
| `one_time_confirmation(train, test)` | **一次确认制**（v3 §3-5）：确认失败即降级，禁止回训重报 |

## 统计口径
- 默认窗口：训练 36 月（与 v3 滚动窗口一致）+ 测试 12 月，滑动步长 = test_months
- 每窗输出：train/test 均值、夏普（年化 ×√12）、测试段累计收益
- 汇总输出（仅报告，不作"通过/观察"判定）：
  - `oos_win_rate`：测试段均值 > 0 的窗口比例（描述性）
  - `oos_cum_return`：全部测试段拼接累计收益（描述性）
  - `train_test_consistency`：训练/测试段均值符号一致的窗口比例（报告项）
  - `verdict`：证据强度分级 `strong`/`weak`/`none`（按 OOS 总月数：
    <24 → none；24~89 → weak；≥90 → strong）——**非策略通过判定**
  - `power_warning`：样本功效警示，引用任何统计量时必须随附声明

## 样本功效限制（必读）
项目实测：**90 月回测检出功效仅 20.3%**（3% 超额 @ TE10%，见
backtest_engineering_spec 审查）。短于 90 月的滑动窗口上，
任何方向性结论均受样本功效限制；本工具输出的 verdict 只描述统计证据的
相对充分程度，**不构成"策略有效/通过"的判定**。报告时必须声明此限制。

## 冒烟验证
- 合成数据：前 60 月有 alpha、后 36 月衰减 → 5 窗统计正常输出，
  verdict=weak（OOS 60 月 <90），power_warning 附 20.3% 实测结论
- 一次确认制：衰减策略测试段均值为负 → confirmed=False 正确拦截
- 验证输出：docs/review_2026-08/C7_validation_output.txt

## 相关页面
- [[factor-testing-methodology]] — 样本划分条款（§3-5）
- [[backtest-engineering-spec]] — 防过拟合红线（signed NW-t 主判定线）
