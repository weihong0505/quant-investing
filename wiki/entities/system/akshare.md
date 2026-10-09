---
title: akshare 数据源
created: 2026-08-21
updated: 2026-08-25
type: entity
tags: [data-source, tool]
sources: [multi_factor_value.py, quant-a-share-workflow]
confidence: 80
---

# akshare 数据源

## 概述
A 股免费数据接口，无 token 要求，是本项目的主要数据源。

## 使用的接口

| 接口 | 用途 | 稳定性 | 备注 |
|------|------|--------|------|
| `stock_zh_a_spot_em` | 全市场行情+估值 | ⚠️ 易限流 | 70页分页，东财限流 |
| `stock_yjbb_em` | 业绩报表 | ✅ 稳定 | 质量因子主源，8期 |
| `stock_zcfz_em` | 资产负债表 | ✅ 稳定 | LEV因子源，4期 |
| `stock_zh_a_hist` | 历史K线 | ⚠️ 限流 | 回测用，需控制频率 |

## 限流问题
- `stock_zh_a_spot_em` 最容易触发东财限流
- 症状：`RemoteDisconnected` / `Connection aborted`（≠代理问题！）
- 解决：等待 10+ 分钟冷却，或使用 `data_cache/` parquet 缓存
- 请求间隔 ≥ 0.3s，重试3次退避

## 缓存策略
- 所有数据落盘 `data_cache/` 目录，parquet 格式
- 命名：`{接口名}_{日期}.parquet`
- 命中缓存时跳过网络请求

## 代理问题
- 本机 Clash Verge 会拦截 Python 请求
- 必须在 `import requests` 之前执行三件套（见 [[sop-v1.1]]）

## 相关页面
- [[multi-factor-v2]] — 使用 akshare 的主系统
- [[sop-v1.1]] — 代理处理和限流判断树

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | Wiki中初始化记录 | 搭建Wiki知识库 |
