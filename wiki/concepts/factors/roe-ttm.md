---
title: ROE_TTM因子 — 滚动净资产收益率
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, quality, roe]
sources: [multi_factor_value.py, quality_factors_v2.md]
confidence: 35
contested: true
---

# ROE_TTM因子 — 滚动净资产收益率

## 定义
ROE_TTM = EPS_TTM / 每股净资产，反映股东权益的盈利效率。

## 计算公式
```python
# TTM计算（逐股PIT最新报告期）
EPS_TTM = ttm_value(code, latest_period, eps_map)
ROE_TTM = EPS_TTM / BPS  # BPS = 每股净资产
```
- 数据来源：akshare `stock_yjbb_em`（8期）+ `stock_zcfz_em`（4期）
- TTM = 去年年报 + 最新期累计 − 去年同期累计
- PIT（Point-in-Time）：只用公告日期 ≤ 今日的数据

## 当前配置
| 项目 | 值 |
|------|-----|
| 权重 | 0.12 (12%) |
| 方向 | +1（越高越好） |
| 处理 | **行业内** winsorize ±3σ → z-score |
| 中性化 | 是（按行业分组；金融股强制置0） |

## 特殊处理
- **负利润保护**：EPS_TTM ≤ 0 → ROE_TTM 强制设为 -3.0（最低分）
- **金融股中性化**：银行/保险/证券/多元金融/信托 → 强制置 0
- **行业内标化**：非金融股按行业分组做 z-score（min_group=5，小行业回退全市场）

## 经济逻辑
- 巴菲特最看重的指标之一
- 高 ROE = 公司用较少的净资产创造了较多利润
- 行业中性化消除行业间差异（银行ROE天然高于科技）

## 已知问题
- ROE 可通过高杠杆人为抬高 → 需配合 [[lev-factor]] 使用
- 负利润保护的 -3.0 阈值是否最优？（待回测验证）
- TTM 计算依赖历史数据完整性，次新股可能年化近似

## 待决事项（contested）

- **先验待验**：仅通过设计审批，无 v3 统计检验证据（S1 未完成）——confidence 按 SCHEMA 标 low；检验结果回填本页。
- "负利润保护 −3.0 阈值是否最优"为**未验证**的设计问题——ROE_TTM 未经 v3 统计检验（复盘 S1），阈值对横截面排序的影响从未回测验证。
- **指向任务**：复盘 S1（因子零检验：ROE_TTM 补检 + 参数敏感性）→ M2（检验与策略脱节：因子参数须以检验证据定档）。检验结果回填本页。

## 相关页面
- [[cfo-ni-ttm]] — ROE 的现金流验证，防止"纸面利润"
- [[lev-factor]] — ROE 的杠杆拆解（杜邦分析）
- [[gpm-factor]] — ROE 的利润率拆解
- [[industry-neutralization]] — 行业中性化逻辑
- [[factor-direction-map]] — 权重与方向一览

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化，权重0.12 | v2策略MImo审查后定稿，通过quality_factors_v2.md审查 |
