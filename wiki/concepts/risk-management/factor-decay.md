---
title: 因子衰减
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, decay]
sources: []
confidence: 60
---

# 因子衰减 (Factor Decay)

## 定义
因子的历史预测能力（IC/ICIR）随时间推移逐渐下降的现象。是量化策略亏损的第一大原因。

## 为什么会衰减
1. **套利消除**：因子被广泛使用后，超额收益被竞争摊薄
2. **市场结构变化**：注册制、量化普及、散户减少改变了市场微观结构
3. **Regime 切换**：牛市/熊市/震荡市下因子有效性不同
4. **因子拥挤**：太多人用同一因子，导致反转

## 检测方法
1. **滚动 IC**：每月计算因子值与下月收益的 Spearman 相关系数
2. **IC 均值趋势**：近6个月 IC 均值 vs 历史均值
3. **分组多空收益**：Top组 - Bottom组的收益是否缩小
4. **ICIR 衰减**：IC 的信息比率是否下降

## 当前系统中的风险

| 因子 | 衰减风险 | 原因 |
|------|----------|------|
| EP | ⚠️ 中 | 2024年后创业板失效迹象（待验证） |
| BP | ⚠️ 中 | 轻资产公司区分度低 |
| ROE_TTM | ✅ 低 | 学术支持强，长期稳定 |
| MOM_60D | 🔴 高 | regime依赖性强，急转时回撤大 |
| TURNOVER | ⚠️ 中 | A股散户比例变化影响 |
| VOL_RATIO | 🔴 高 | 日频噪音大，信号不稳定 |
| LOG_MCAP | ⚠️ 中 | 2017年后小盘溢价减弱 |

## Wiki 如何追踪衰减
1. 每月更新各因子页面的 `confidence` 字段
2. 当 `confidence` 从 high 降到 low 时，标记 `contested: true`
3. Lint 检查时自动提醒低 confidence 因子
4. 在 `factor-direction-map` 的调整记录中记录权重变化

## 相关页面
- [[ep-factor]] — 可能存在衰减
- [[momentum-60d]] — 高regime依赖
- [[vol-ratio]] — 信号最弱的因子
- [[factor-direction-map]] — 权重调整触发条件
- [[weighted-scoring]] — 权重调整影响合成逻辑

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化 | 搭建Wiki知识库 |
