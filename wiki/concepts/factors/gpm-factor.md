---
title: GPM因子 — 销售毛利率
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, quality, gpm]
sources: [multi_factor_value.py, quality_factors_v2.md]
confidence: 35
contested: true
---

# GPM因子 — 销售毛利率 (Gross Profit Margin)

## 定义
GPM = (营业收入 - 营业成本) / 营业收入，反映产品/服务的定价能力和成本控制。

## 计算公式
```python
GPM = pd.to_numeric(r['销售毛利率'], errors='coerce')
```
- 数据来源：akshare `stock_yjbb_em`
- 取最新公告的报告期数据

## 当前配置
| 项目 | 值 |
|------|-----|
| 权重 | 0.06 (6%) |
| 方向 | +1（越高越好） |
| 处理 | **行业内** winsorize ±3σ → z-score |
| 中性化 | 是（按行业分组；金融股强制置0） |

## 特殊处理
- **负利润保护**：EPS_TTM ≤ 0 → GPM 强制设为 -3.0
- **金融股中性化**：金融行业 → 强制置 0

## 经济逻辑
- 高毛利 = 强定价权 / 低生产成本 = 竞争优势
- 护城河的重要体现（品牌、专利、规模效应）

## 待决事项（contested）

- **先验待验**：仅通过设计审批，无 v3 统计检验证据（S1 未完成）——confidence 按 SCHEMA 标 low；检验结果回填本页。
- **口径**：2026-08-22 实测 yjbb「销售毛利率」= 报告期累计（40/40，docs/factor_docs/gpm_caliber_verify_20260822.md）；⚠️ M6 审计表（_m6_audit.py）勾选"已改毛利TTM/营收TTM（lrb）"但 multi_factor_value.py L247 仍取 yjbb 字段、data_fetcher 无 lrb 实现（2026-08-22 核对）——"已改"声明与代码不符（W2 类），待实际落地或回改声明

## 相关页面
- [[roe-ttm]] — GPM 是 ROE 的上游驱动因素
- [[cfo-ni-ttm]] — 毛利能否转化为现金流
- [[industry-neutralization]] — 行业中性化逻辑

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化，权重0.06 | v2策略MImo审查后定稿 |
