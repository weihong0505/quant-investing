---
title: 本地股票数据库（quant.db）
created: 2026-08-29
updated: 2026-09-13
type: entity
tags: [data-source, pipeline, system]
sources: [docs/trading/本地股票数据库执行流程.md, code/init_db.py, code/update_db.py, conversation-archive 对话-20260829_011504]
confidence: 80
---

# 本地股票数据库（quant.db）

## 概述

SQLite 本地库，目标是把散落的 parquet 缓存收成可定期更新的单一数据层，供初筛与价值投资管线消费。

- 路径：`G:/股市探究/quant-investing/data/quant.db`（单文件，复制即备份）
- 建库：`code/init_db.py`；更新：`code/update_db.py`
- 消费方：`run_screen.py`（可选改造）、`value_investing.py`（规划）
- 定时：Windows 任务计划 `QuantDBUpdate`，每日 18:30，`--tables spot,fin,mcap`
- 执行说明：`docs/trading/本地股票数据库执行流程.md`

## 表结构

| 表 | 内容 | 首灌（2026-08-29） |
|---|---|---|
| `stock_master` | 主表/可交易池 | 5548 |
| `quarterly_fin` | 财务多期 | 173632 × 37 期（2015Q3→2026Q2） |
| `valuation_daily` | PE/PB 历史 | 16804（仅约 8 只，全市场未灌） |
| `dividends` | 分红 | 26（仅 600000） |
| `mcap_snapshot` | 市值快照 | 5550 |
| `daily_bars` | 日线 | 0（东财 push2 封禁） |
| `meta_updates` | 更新日志 | 有；曾因缺 commit 丢失 |

## 能支撑什么（审计结论）

| 消费场景 | 判定 | 依据 |
|---|---|---|
| 股票池 / 主表 | 可用 | 5548，时效正常 |
| 质量门槛（最新一期 ROE/GPM/LEV/CFO） | 可用 | 最新报告期财务 |
| EP / BP / ROE_TTM | 数据基础已具备 | 37 期财务多期已灌 |
| PE_PCTL / PB_PCTL | **不可用** | 估值历史仅候选池 8 只 |
| DY 股息率 | **不可用** | 分红仅 1 只 |
| FCF_YIELD | **不可用** | 现金流 0 行 |
| 行情因子 / 真实回测 | **不可用** | `daily_bars` 0 行 |

结论（2026-08-29）：**管道建成，内容残缺**。撑不起价值投资 v2.1 的 4 个新因子；空架子≠可选股。

## 补齐成本（未执行，待拍板）

| 缺口 | 预估 | 数据源 |
|---|---|---|
| dividends 全市场 | ~30–60 min | 东财 fhps 逐只 |
| FCF 全市场 | ~30–60 min | 东财现金流量表 |
| valuation_daily 全市场 | 2–3 h | 东财 RPT_VALUEANALYSIS_DET |
| daily_bars | 暂无解 | 东财 push2 封禁；需新浪分页等替代 |

## 首灌踩坑（已修回脚本）

1. **dividends 中文列名**：缓存列是中文，原按英文列绑定 → SQL 报错；已做列名映射。
2. **残缺缓存**：中断抓取留下 yjbb 3876 / zcfz 1475 行残缺文件；已重抓全量并 `.bak_incomplete` 备份。
3. **`load_latest_cache` 选文件**：历史期文件行数可能更多，**不能按行数选**；按报告期最新 + 同期取带日期后缀版。
4. **东财 yjbb 含新三板**：须滤到 `stock_master` 池。
5. **报告期列缺失**：从文件名解析（`20260630` → `2026-06-30`）。
6. **`meta_updates` 缺 `commit()`**：单表运行日志随 `close()` 回滚；已修，否则「查 meta_updates 定位失败」不可用。

## 相关页面

- [[akshare]] — 主数据源与限流
- [[multi-factor-v2]] — 价值投资决策系统 v3（消费方）
- [[pe-pctl]] / [[pb-pctl]] / [[dy-factor]] / [[fcf-yield]] — 依赖本库补齐的因子
- [[sop-v1.1]] — 环境与数据源 SOP

## 待办

- [ ] dividends / FCF / valuation_daily 全市场补齐（用户拍板后）
- [ ] `run_screen.py` 改从 DB 读（可选）
- [ ] `daily_bars` 替代方案（新浪分页或其他源）
