---
title: LEV因子 — 资产负债率
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, quality, leverage]
sources: [multi_factor_value.py, quality_factors_v2.md]
confidence: 35
contested: true
---

# LEV因子 — 资产负债率 (Leverage)

## 定义
LEV = 总负债 / 总资产，反映公司的财务杠杆水平。

## 计算公式
```python
LEV = pd.to_numeric(zlatest['资产负债率'], errors='coerce')
```
- 数据来源：akshare `stock_zcfz_em`（资产负债表，4期）
- PIT 取最新公告日期 ≤ 今日的报告期

## 当前配置
| 项目 | 值 |
|------|-----|
| 权重 | 0.02 (2%) |
| 方向 | **-1**（越低越好） |
| 处理 | **行业内** winsorize ±3σ → z-score |
| 中性化 | 是（按行业分组；金融股强制置0） |

## 特殊处理
- **金融股中性化**：金融行业 → 强制置 0（金融股天生高杠杆，不具可比性）
- 方向为 -1：低负债率的公司得分更高

## 经济逻辑
- 高杠杆 = 高风险（经济下行时更容易暴雷）
- 是 [[roe-ttm]] 的杜邦拆解因子之一：ROE = 净利率 × 周转率 × 杠杆
- 低杠杆公司在熊市中更抗跌

## 已知问题
- 权重仅 0.02，信号较弱——但作为风控因子保留
- 某些行业（如地产）天然高杠杆，行业内中性化可缓解

## 待决事项（contested）

- **先验待验**：仅通过设计审批，无 v3 统计检验证据（S1 未完成）——confidence 按 SCHEMA 标 low；检验结果回填本页。
- **口径**：资产负债率（总负债/总资产，zcfz 最新 PIT）在口径审计表中仍记"待验证"（data_caliber_audit.md）

## 相关页面
- [[roe-ttm]] — 杜邦分析的杠杆项
- [[industry-neutralization]] — 行业中性化逻辑
- [[factor-direction-map]] — 权重与方向一览

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化，权重0.02 | v2策略MImo审查后定稿 |
