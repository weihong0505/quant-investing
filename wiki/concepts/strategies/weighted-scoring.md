---
title: 加权评分策略
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, decision]
sources: [multi_factor_value.py]
confidence: 80
---

# 加权评分策略 (Weighted Scoring)

## 定义
将多个因子通过 z-score 标准化后，按预设权重加权求和，得到每只股票的综合评分（SCORE）。

## 处理流程
```
原始因子值
  ↓ winsorize ±3σ（截断极端值）
  ↓ z-score 标准化（均值0，标准差1）
  ↓ × direction（+1或-1，控制方向）
  ↓ × weight（权重）
  ↓ 求和 → SCORE
```

## 代码实现
```python
# score_factors() 函数核心逻辑
df['SCORE'] = 0.0
for f, w in WEIGHTS.items():
    df['SCORE'] += w * DIRECTION[f] * scores[f]
df = df.sort_values('SCORE', ascending=False)
```

## 为什么用 z-score 而不是原始值
- 不同因子量纲不同（PE 是倍数，ROE 是百分比，市值是亿元）
- z-score 统一到"偏离均值几个标准差"，可直接加权
- winsorize ±3σ 防止极端值（如 PE=1 的异常数据）主导评分

## 为什么需要 direction
- EP 越高越好（+1），但 LEV 越低越好（-1）
- direction 让所有因子"得分越高 = 越值得买"

## 当前局限
- 权重是静态的，不随市场状态调整
- 没有因子间相关性惩罚（共线性因子会被重复计算）
- 截断点（Top 30）是硬编码的

## 相关页面
- [[multi-factor-v2]] — 策略的代码实现
- [[factor-direction-map]] — 权重与方向配置
- [[industry-neutralization]] — 部分因子的前置处理
- [[factor-decay]] — 权重调整的触发条件

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化 | 搭建Wiki知识库 |
