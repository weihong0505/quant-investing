---

title: 因子检验方法论 v3（定稿）

created: 2026-08-21

updated: 2026-08-25

type: entity

tags: [system, factor-test, decision]

sources: [G:/股市探究/quant-investing/docs/factor_docs/factor_testing_methodology_v3.md]

confidence: 85

---



# 因子检验方法论 v3



## 概述

新因子"能不能进主策略"的统计判定标准，MImo 两轮审查定稿。

全文：`G:/股市探究/quant-investing/code\factor_docs\factor_testing_methodology_v3.md`



## 两轮审查抓出的硬伤（沉淀为定稿规则）

| 硬伤 | 定稿修正 |

|------|---------|

| ICIR>0.5 与 NW-t>2 数学冗余（T>16 前者蕴含后者） | 第二条件改为经济幅度 \|mean IC\|≥0.02 |

| "5组年化收益回归"n=5 无时间维度 | 改 Patton-Timmermann MR bootstrap |

| 多重检验三档非单调（BHY 比 HLZ 严）+ BH 单因子误用 | 单一规则：signed NW-t ≥ max(3.0, Bonf(N')) |

| \|t\|≥3.0 会放行反向强因子 | 必须 signed（预登记方向） |

| 胜率>55% 判别力弱（原假设通过率16~18%） | 降级报告项 |



## 关键判定线（速查）

```

⓪ registry 前置登记（预期符号锁定+防改口三件套）

① IC 关：ICIR>0.5 且 |mean IC|≥0.02 且 signed NW-t ≥ max(3.0, Bonf(N'))

② 分层关：PT MR 单调性 p<0.05 + 三重稳健性（市值加权/微盘剔除/规模中性）

③ 经济闸门：净多空年化≥8% 且 2x成本为正 且 夏普≥0.8

④ 样本：主判定2017+；训练段=检验日−24m；最近24m样本外一次确认制

```



## 关键实测数字

- PT MR：时间层 stationary bootstrap（块长3）、R=9999、**必须 null recentering**（不做则 p≈0.5）

- 90月回测功效：超额5%/年@TE10% 仅38.7% → 回测不设显著性硬线

- Bonf(N') 单侧 α=0.05 在 N'=37 处与 3.0 无缝衔接



## 相关页面

- [[mimo-review]] — 两轮审查的流程载体

- [[factor-decay]] — §8 滚动 36m ICIR 观察线的概念

- [[ic-monitor]] — 生产环境的持续监控实现

- [[sop-v1.1]] — §3.2 引用本方法论

