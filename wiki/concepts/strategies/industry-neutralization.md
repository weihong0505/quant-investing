---
title: 行业中性化
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, decision]
sources: [multi_factor_value.py]
confidence: 80
---

# 行业中性化 (Industry Neutralization)

## 定义
将因子值在行业内部做 z-score 标准化，消除行业间的系统性差异。

## 为什么需要
- 不同行业的因子分布差异巨大
- 银行业 ROE 天然 10%+，科技业可能只有 3%
- 如果全市场统一标化，银行股在 ROE 上永远"占便宜"
- 中性化后，只比较"同行业内谁的 ROE 更高"

## 实现逻辑
```python
def industry_zscore(df, col, industry_col, min_group=5):
    market_z = winsorize_zscore(df[col])
    def _f(g):
        return winsorize_zscore(g) if len(g) >= min_group else market_z.reindex(g.index)
    ind_z = df.groupby(industry_col)[col].transform(_f)
    return ind_z.fillna(market_z)
```

## 关键参数
- **min_group=5**：行业样本数 < 5 时回退到全市场 z-score
- **金融股特殊处理**：银行/保险/证券/多元金融/信托 → 强制置 0

## 哪些因子做了行业中性化
| 因子 | 中性化 | 原因 |
|------|--------|------|
| ROE_TTM | ✅ | 不同行业ROE差异大 |
| GPM | ✅ | 不同行业毛利率差异大 |
| LEV | ✅ | 不同行业杠杆差异大（金融股天生高杠杆） |
| EP/BP/MOM/等 | ❌ | 全市场标化即可 |

## 相关页面
- [[roe-ttm]] — 中性化的主要应用对象
- [[gpm-factor]] — 中性化的主要应用对象
- [[lev-factor]] — 中性化的主要应用对象
- [[multi-factor-v2]] — 中性化的代码实现

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化 | 搭建Wiki知识库 |
