---
title: CFO_NI_TTM因子 — 经营现金流净利润比
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, quality, cfo]
sources: [multi_factor_value.py, quality_factors_v2.md]
confidence: 35
contested: true
---

# CFO_NI_TTM因子 — 经营现金流/净利润

## 定义
CFO_NI_TTM = 每股经营现金流(TTM) / EPS_TTM，衡量利润的"含金量"——赚到的钱是否真金白银到账。

## 计算公式
```python
CFO_NI_TTM = cfps_ttm / eps_ttm  # 仅当 EPS_TTM > 0 时计算
```
- 数据来源：akshare `stock_yjbb_em`
- CFPS_TTM 同样使用 TTM 口径（去年年报 + 最新期累计 − 去年同期累计）

## 当前配置
| 项目 | 值 |
|------|-----|
| 权重 | 0.05 (5%) |
| 方向 | +1（越高越好） |
| 处理 | 全市场 winsorize ±3σ → z-score |
| 中性化 | 否（但金融股 EPS_TTM ≤ 0 保护仍适用） |

## 特殊处理
- **负利润保护**：EPS_TTM ≤ 0 → CFO_NI_TTM 强制设为 -3.0
- EPS_TTM = 0 时不计算（避免除零）

## 经济逻辑
- 利润可以被会计手段操纵，现金流很难
- CFO_NI > 1：利润全部收回且有超额现金（好）
- CFO_NI < 0.5：利润中大量是应收账款/存货（警告）
- 是 [[roe-ttm]] 的"验真"因子

## 待决事项（contested）

- **先验待验**：仅通过设计审批，无 v3 统计检验证据（S1 未完成）——confidence 按 SCHEMA 标 low；检验结果回填本页。
- **口径**：每股经营现金流 TTM 公式已审计确认（docs/factor_docs/data_caliber_audit.md，2026-08-22）

## 相关页面
- [[roe-ttm]] — ROE 的现金流验证
- [[gpm-factor]] — 毛利能否转化为现金流
- [[factor-direction-map]] — 权重与方向一览

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化，权重0.05 | v2策略MImo审查后定稿 |
