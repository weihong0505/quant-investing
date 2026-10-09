---
title: BP因子 — 账面价值比
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, value, bp]
sources: [multi_factor_value.py]
confidence: 60
contested: true
---

# BP因子 — 账面价值比 (Book-to-Price)

## 定义
BP = 1 / 市净率，即每块钱净资产对应的价格。BP 越高，股票越"便宜"。

## 计算公式
```python
BP = 1.0 / df['市净率']
```
- 数据来源：akshare `stock_zh_a_spot_em`
- 入池条件：PB > 0（剔除净资产为负的公司）

## 当前配置
| 项目 | 值 |
|------|-----|
| 权重 | 0.20 (20%) |
| 方向 | +1（越高越好） |
| 处理 | 全市场 winsorize ±3σ → z-score |
| 中性化 | 否（全市场统一标化） |

## 经济逻辑
- Fama-French 三因子模型中的核心价值因子
- 高 BP 意味着市场对该公司的资产给予较低估值
- 在 A 股，BP 对银行/地产等重资产行业区分度高

## 已知问题
- 轻资产公司（互联网/科技）PB 天然高，BP 信号弱
- 与 [[ep-factor]] 相关系数较高（约 0.5-0.7），存在共线性风险
- 商誉/无形资产会导致账面价值失真

## 待决事项（contested）

- "与 [[ep-factor]] 相关系数约 0.5-0.7"为**未实测的数值声明**（项目 10 因子零检验，复盘 S1），共线性风险的真实量级未验证。
- **✅ 2026-08-22 试点符号验证（初步）**：yjbb 快照试点（22 月，2024-10~2026-07）univariate signed IC 方向与登记 + 一致（NW-t=+2.51，ICIR=0.352，初步）；FM 增量（控制 ln_mcap+行业）t=+0.61 未达 2.0 线 → 维持 0.20 权重但标记**观察**，数据未就绪前不裁决（registry #16；报告 [[test_value_vs_momentum_20260822]]）。
- **指向任务**：复盘 S1（因子零检验：EP/BP 相关矩阵与共线性检验）→ M5（FM 增量检验裁决 EP/BP/MOM 三者的增量信息与去留）。全 A 2017+ 财务数据就绪后走 v3 全流程。
- 相关任务包：W2_Wiki错误声明.md 条目 4 巡检项。

## 相关页面
- [[ep-factor]] — 同属价值因子，共线性需关注
- [[weighted-scoring]] — BP 在加权评分中的角色
- [[factor-direction-map]] — 权重与方向一览
- [[multi-factor-v2]] — 当前策略版本

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化，权重0.20 | v2策略MImo审查后定稿 |
| 2026-08-22 | 试点符号验证回填：方向与登记 + 一致（NW-t=+2.51，初步）；FM 增量未达 2.0 → 观察 | 复盘 M5 执行（docs/factor_docs/test_value_vs_momentum_20260822.md） |
