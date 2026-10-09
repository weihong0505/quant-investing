---
title: LOG_MCAP因子 — 对数市值
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, size, market-cap]
sources: [multi_factor_value.py]
confidence: 35
contested: true
---

# LOG_MCAP因子 — 对数市值 (Log Market Cap)

## 定义
LOG_MCAP = ln(总市值)，反映公司的规模大小。

## 计算公式
```python
LOG_MCAP = np.log(pd.to_numeric(df.get('总市值'), errors='coerce'))
```
- 数据来源：akshare `stock_zh_a_spot_em`
- 取对数是为了压缩极端值（万亿 vs 十亿的差距）

## 当前配置
| 项目 | 值 |
|------|-----|
| 权重 | 0.05 (5%) |
| 方向 | **-1**（市值越小越好） |
| 处理 | 全市场 winsorize ±3σ → z-score |
| 中性化 | 否 |

## 经济逻辑
- 小盘股溢价：A 股长期存在小市值公司跑赢大市值公司的现象
- 小公司成长空间更大，被研究覆盖少，定价效率低
- 但2017年后小盘股溢价有所减弱

## 已知问题
- 小市值因子在2017-2019年经历了大幅回撤
- 微盘股（<30亿）流动性差，实际交易困难
- 与 [[turnover-factor]] 正相关（小盘股换手率通常更高）
- 权重仅 0.05，作为辅助因子

## 待决事项（contested）

- **先验待验**：仅通过设计审批，无 v3 统计检验证据（S1 未完成）——confidence 按 SCHEMA 标 low；检验结果回填本页。
- **口径**：总市值为东财 spot 盘中快照（非收盘终值），口径审计表记"待验证"（data_caliber_audit.md）

## 相关页面
- [[turnover-factor]] — 小市值与高换手率的共线性
- [[factor-direction-map]] — 权重与方向一览

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化，权重0.05 | v2策略MImo审查后定稿 |
