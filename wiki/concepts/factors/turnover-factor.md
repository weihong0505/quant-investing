---
title: TURNOVER因子 — 换手率
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, liquidity, turnover]
sources: [multi_factor_value.py]
confidence: 35
contested: true
---

# TURNOVER因子 — 换手率

## 定义
TURNOVER = 当日成交量 / 流通股本，反映股票的交易活跃度。

## 计算公式
```python
TURNOVER = pd.to_numeric(df.get('换手率'), errors='coerce')
```
- 数据来源：akshare `stock_zh_a_spot_em`

## 当前配置
| 项目 | 值 |
|------|-----|
| 权重 | 0.15 (15%)（2026-08-22 吸收 VOL_RATIO 弃用权重 0.05） |
| 方向 | **-1**（换手率越低越好） |
| 处理 | 全市场 winsorize ±3σ → z-score |
| 中性化 | 否 |

## 经济逻辑
- 低换手 = 筹码稳定，机构持仓为主，不易被游资炒作
- 高换手 = 散户博弈，短期投机氛围浓
- 低换手率股票在熊市中更抗跌

## 已知问题
- 换手率是日频数据，受单日事件影响大（需要多日平均？）
- 新股/次新股换手率天然高，可能被误杀
- 与 [[vol-ratio]] 存在一定正相关

## 待决事项（contested）

- **先验待验**：仅通过设计审批，无 v3 统计检验证据（S1 未完成）——confidence 按 SCHEMA 标 low；检验结果回填本页。
- "换手率是否需要多日平均"为**未验证**的设计问题：单日换手的噪声/信号结构（及新股次新股误杀风险）从未在 A 股 2017+ 样本上检验（复盘 S1）。
- **口径**：换手率 = 当日成交量/流通股本（spot 当日口径），口径审计表记"待验证"（data_caliber_audit.md）；VOL_RATIO 弃用后权重并入（0.10→0.15，multi_factor_value.py WEIGHTS）。
- **指向任务**：复盘 S1（因子零检验：TURNOVER 补检 + 窗口敏感性）→ M5（符号本地验证：方向 −1 来自文献先验）。检验结果回填本页。

## 相关页面
- [[vol-ratio]] — 同属流动性/情绪类因子
- [[log-mcap]] — 小市值股票换手率通常更高
- [[factor-direction-map]] — 权重与方向一览

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化，权重0.10 | v2策略MImo审查后定稿 |
