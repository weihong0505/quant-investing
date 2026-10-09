---
title: 卖出信号模块 sell_signals.py
created: 2026-08-21
updated: 2026-08-25
type: entity
tags: [system, tool, decision]
sources: [G:/股市探究/quant-investing/code/sell_signals.py]
confidence: 80
---

# 卖出信号模块 sell_signals.py

## 概述
在月度调仓信号之上叠加卖出规则，生成最终目标权重矩阵。
纯逻辑层：输入=每期打分表+每期价格，输出=目标权重矩阵（供 [[backtest-engine]] 执行）。

## 代码位置
`G:/股市探究/quant-investing/code\sell_signals.py`

## 三类卖出信号（默认参数，可配置）
| 信号 | 规则 | 默认 |
|------|------|------|
| 时间止盈 | 持有满 N 月强制卖出 | 6 个月 |
| 信号衰减 | 排名跌出 Top N（top_n）即卖（keep_rank 与 top_n 联动） | top_n（默认 30，与持仓数一致） |
| 止损 | 持仓浮亏超阈值卖出 | -15% |
| 冷却期 | 卖出后 N 月内不重新买入 | 3 个月 |

## 设计要点
- 与引擎解耦：本模块产出 signals DataFrame，引擎负责执行
- 卖出信号参数按 SOP §4 协作规范由用户拍板金融逻辑

## 口径（2026-08-22 C5 修复，与回测引擎 v2.1 对齐）
- **止损基准价 = T+1 开盘价**：`generate_signals` 新增 `exec_price_table`（成交价表，
  index=信号日，values=T+1 开盘价），买入记账价取该表信号日取值；未传时回退信号日
  收盘价口径（docstring 明确声明：与 T+1 成交不一致，仅近似/调试用）
- **信号衰减阈值 = top_n**：`SellRules` 删除独立 `keep_rank` 参数，排名跌出 top_n 即卖；
  旧持仓跌出 top_n 一律走 signal_decay 卖出路径（记录卖出原因 + 进入冷却期），
  不存在"权重归零绕过冷却期"路径；卖出原因可通过 `sell_log` 参数收集
- **等权 = 1/len(candidates)**：候选不足 top_n 时剩余权重按现有候选等比放大，
  总权重恒为 1.0（无现金拖累）；极端情形无候选时该期空仓（权重全 0）

## 相关页面
- [[backtest-engine]] — 信号的下游消费者
- [[weighted-scoring]] — 打分表的上游生产者
