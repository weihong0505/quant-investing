---
title: 防过拟合（Overfitting Prevention）
created: 2026-09-10
updated: 2026-09-11
type: concept
tags: [backtest, factor-test]
sources: [SOP §3.2/§3.3.5, factor-testing-methodology v3, backtest-engineering-spec v2.1, sharpe-ratio-efficient-frontier-2012, deflated-sharpe-ratio-2014]
confidence: 85
---

# 防过拟合（Overfitting Prevention）

## 概述

过拟合 = 模型在训练数据（样本内）表现极好，但学到的是数据中的噪声/偶然规律而非真实规律，一到新数据（样本外）就失效。**衡量标准只有一个：样本外表现。**

本页汇总防过拟合的完整工具箱：通用 ML 方法（数据切分/交叉验证/正则化/早停/集成）+ 量化专属方法（walk-forward/去偏夏普）。本项目已落地的量化部分见 [[walk-forward]]、[[factor-testing-methodology]]、[[backtest-engineering-spec]]。

> 来源：通用 ML/量化方法学（教科书标准方法）；PSR 见 Bailey & López de Prado (2012)、DSR 见 Bailey & López de Prado (2014)（原始论文已摄入 raw/，见 [[sharpe-ratio-efficient-frontier-2012]]、[[deflated-sharpe-ratio-2014]]）；项目落地条款见 SOP / 规范编号。

## 识别信号

| 信号 | 含义 |
|---|---|
| 训练误差低、验证/测试误差高，差距大 | 最直接的红旗 |
| 样本内表现 ≫ 样本外表现 | 学到的是噪声 |
| 学习曲线验证误差先降后升 | 拐点 = 过拟合开始 |
| 参数/特征数相对样本量过多 | 容量过大 |
| 对训练数据微小扰动/删一个点很敏感 | 记住了特异点 |

## 防范方法

### 1. 数据切分（地基）
测试集锁死、只用一次；调参选特征全在验证集上。时间序列**绝不随机 shuffle**——随机切会把未来信息漏进训练集。

```python
# 非时序：随机切
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
```

```python
# 时序（量化！）：按时间顺序切，未来永远在后面，X/y 必须同步切
split = int(len(X) * 0.8)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]
```

### 2. 交叉验证
时间序列用 `TimeSeriesSplit`（保持时间顺序）。调参 + 评估都用 CV 时，用**嵌套 CV**（外层公正评估、内层选参），否则「CV 选出的最优参数 + 同一 CV 报分」仍有偏。

```python
from sklearn.model_selection import cross_val_score, TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5)
scores = cross_val_score(model, X_train, y_train, cv=tscv, scoring='neg_mean_squared_error')
```

### 3. Walk-Forward 前进分析（量化核心）
滚动窗口模拟「过去训练、未来预测」：训练段 [t, t+T] → 预测 [t+T, t+T+M] → 窗口滚 M，拼接所有测试段为可信样本外成绩。本项目**真 walk-forward 尚未实现**（见 [[walk-forward]] 说明）。

```python
train_years, test_months = 3, 6   # 通用示例；本项目默认 36+12 月（见 rolling_stats.py）
i, results = 0, []
while (i + train_years*12 + test_months) <= len(data):
    train = data[i : i + train_years*12]
    test  = data[i + train_years*12 : i + train_years*12 + test_months]
    model = train_model(train)
    results.append(evaluate(model, test))
    i += test_months
```

### 4. 砍特征
- 相关性过高的特征/因子删一（本项目共线性闸门：|corr|>0.7 的因子对砍 IC 弱者或权重减半，SOP §3.2-5）
- 重要性排在尾部的删；LASSO 自动砍（L1 把不重要特征系数逼成 0）

```python
from sklearn.linear_model import LassoCV
# 时序数据应改用 TimeSeriesSplit 或提前切好的验证集；cv 默认 KFold 非时间感知
lasso = LassoCV(cv=5).fit(X_train, y_train)
kept = [c for c, coef in zip(X.columns, lasso.coef_) if abs(coef) > 1e-6]
```

### 5. 正则化（给复杂度上税）
L1/Lasso 逼稀疏（砍特征）、L2/Ridge 压缩权重、Elastic Net 混合。超参 `alpha` 在**验证集**上选，别在训练集上选。

### 6. 早停
验证误差开始回升就停。

```python
from sklearn.ensemble import GradientBoostingRegressor
gb = GradientBoostingRegressor(n_estimators=1000, validation_fraction=0.1,
                               n_iter_no_change=20)   # 经典版无 early_stopping 参数，靠 n_iter_no_change 触发早停
```

### 7. 集成
多个模型平均/投票，噪声互相抵消、信号被强化。树多但每棵别太深：`RandomForestRegressor(n_estimators=500, max_depth=5, min_samples_leaf=10)`。

### 8. 去偏夏普（多重检验修正）
试了 N 个策略，总有纯靠运气好看的。两个「修正后夏普」指标（Bailey & López de Prado）：

**PSR（Probabilistic Sharpe Ratio，2012）**——给定基准夏普 SR* 时，观测夏普 SR 有多可信：

```
PSR = Φ[ (SR − SR*) · √(n−1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²) ]
```

**DSR（Deflated Sharpe Ratio，2014）**——把 PSR 的固定基准换成「试 N 次后期望出现的最大夏普」SR₀，分母不变：

```
DSR = Φ[ (SR − SR₀) · √(n−1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²) ]
```

- SR = 策略夏普，n = 样本数，γ₃ = 偏度，γ₄ = **普通峰度**（正态=3；`scipy.stats.kurtosis(..., fisher=False)`，默认 fisher=True 返回的是超额峰度，需 +3）
- SR₀ = 「试 N 次后期望最大夏普」：由试验数 N 与受检 SR 的方差 σ² 共同决定（EVT 解析式 SR₀ ≈ σ·[(1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(N·e))]，γ≈0.5772；或蒙特卡洛模拟 N 次取 max 平均）；**不是**在分母额外加方差项
- Φ = 标准正态 CDF；结果 > 0.95 才可信
- 前提：收益近似 i.i.d.（或已处理自相关），基于夏普估计量的渐近正态

> 本项目对应实现：因子检验主判定线 signed NW-t ≥ max(3.0, Bonf(N'))（SOP §3.2、[[factor-testing-methodology]] v3），N' = **同期受检因子数**（非累计登记数）。

## 本项目已有落地

- 防过拟合红线：单次回测不作数，需样本外验证 + 一次确认制 + 功效声明（SOP §3.3.5；实测 90 月检出功效仅 20.3%）
- 滚动窗口描述统计：[[walk-forward]]（rolling_stats.py，非真 walk-forward）
- 因子统计检验：[[factor-testing-methodology]] v3（signed NW-t / Bonferroni）
- 回测工程规范：[[backtest-engineering-spec]] v2.1（策略判定标准 7 条，其中第 7 条要求入池因子过 v3 检验）

## 当前认知状态与未解决问题

- 通用 ML 方法（交叉验证/正则化/早停/集成）为标准方法论，认知稳定。
- 量化专属方法（walk-forward/去偏夏普）方法论成熟；但本项目**真 walk-forward 验证尚未实现**（rolling_stats.py 仅描述统计），防过拟合判定现由 signed NW-t 主判定线承担。
- 样本功效是硬约束：短样本上任何方向性结论都受限（20.3%），报告须声明。
- 遗留：已闭合——PSR/DSR 原始论文已摄入 wiki/raw/papers/（[[sharpe-ratio-efficient-frontier-2012]]、[[deflated-sharpe-ratio-2014]]），并据原文修正 DSR 公式（受检 SR 方差 σ² 在 SR₀ 内、非分母附加项）。

## 相关概念
- [[walk-forward]] — 滚动窗口统计 + 一次确认制
- [[factor-testing-methodology]] — 因子检验 v3 判定线
- [[backtest-engineering-spec]] — 回测工程规范
- [[factor-decay]] — 因子衰减（与过拟合相关的失效模式）
