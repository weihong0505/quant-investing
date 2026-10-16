# quant-investing · A 股量化价值投资知识库

> 一个人从零搭 A 股多因子选股与回测体系的全过程留痕：
> 因子检验方法论、回测工程规范、防过拟合纪律，以及**每个结论对应的反面证据**。
>
> **这个库最值钱的不是策略，是「哪些看起来对的东西其实不对」的记录。**

---

## 先看结论（也是这个库最该被看到的部分）

| 结论 | 证据 |
|---|---|
| **动量和量比因子被淘汰** | MOM_60D 反向显著（signed NW-t = **−3.63**）；VOL_RATIO 不显著。两个都进过试点，两个都被自己的检验杀掉 |
| **四个核心因子在全 A 样本上全部淘汰** | 5,179 只 × 116 个月：EP / BP / ROE_TTM / GPM **全灭**（含 GPM「几乎完美的不显著」p=0.8291）。且 **EP 在全 A 上的 IC 是 101 只试点的 3.8 倍** → 试点结论不可外推 → [完整报告](research/full-a-factor-backtest/) |
| **一个致命 bug 曾让回测结论翻转** | `nav2.index = nav1.index[:len(nav2)]` 使 2x 成本序列整体早标一个月，丢掉 2019-02 的 +22.0%。**由独立对抗性审查抓出**；首版错误结论保留在报告里备审计 |
| **回测引擎算术正确，但策略未验证** | 金样本对账 **103 PASS / 0 FAIL** —— 但这用的是**合成数据**，只验证算术，不验证策略。真实数据回测**未执行**（复盘 S2） |
| **样本量常常不够判断任何事** | 某择时方案均线夏普 0.54，按 PSR 最小 track record 要求需 **2,328 个交易日（≈9.2 年）** 才能确认 —— 而可用的窗口只有几十天 |
| **胜率优势往往撑不过 bootstrap** | 策略层样本外检验：walk-forward 年化 +2.54%、夏普 0.22、去偏夏普 0.156、**bootstrap p = 0.867** |
| **"因子有金融逻辑"不等于因子有效** | 新因子上线强制过三关：金融逻辑 + 异构 AI 审批 + IC 检验 |

---

## 这个库在做什么

目标形态：**四层管线 + 安全边际分 + 集中持仓 12 只、季度调仓**的 A 股价值投资决策系统。

```
数据层 ──▶ 因子层 ──▶ 合成层 ──▶ 组合层 ──▶ 回测/执行层
akshare    17 个因子    z-score×方向×权重   行业中性化    真实成本+T+1+涨跌停+公司行为
quant.db   质量/价值/    加权评分            集中持仓      双口径复权 / 分层样本
1025万行    动量/流动性                    Regime 调权
```

---

## 目录导航

### 方法论（最核心）

| 页面 | 内容 |
|---|---|
| [factor-testing-methodology](wiki/entities/system/factor-testing-methodology.md) | 因子检验方法论 v3：IC / 分层 / 经济闸门判定线 |
| [backtest-engineering-spec](wiki/entities/system/backtest-engineering-spec.md) | 回测工程规范 v2.1：hfq 复权 / 双口径 / 样本分层 / 策略判定 7 条 |
| [overfitting-prevention](wiki/concepts/risk-management/overfitting-prevention.md) | 防过拟合总览：样本外纪律 / 交叉验证 / 正则化 / 早停 / 集成 / walk-forward / 去偏夏普 |
| [walk-forward](wiki/entities/system/walk-forward.md) | 滚动窗口（**明确不是 walk-forward**）+ 一次确认制 |
| [dual-caliber-adjustment](wiki/concepts/risk-management/dual-caliber-adjustment.md) | 复权双口径铁律：hfq 统一 + raw 空间执行 |
| [backtest-cost-model](wiki/concepts/risk-management/backtest-cost-model.md) | 成本模型：佣金 / 印花税时变 / 滑点四档 / 敏感性三档 |

**原始论文摄入**：[PSR (2012)](wiki/raw/papers/sharpe-ratio-efficient-frontier-2012.md) · [DSR (2014)](wiki/raw/papers/deflated-sharpe-ratio-2014.md) —— 非正态收益下的夏普阈值概率、多重检验选择偏差校正。

### 因子（17 个）

`ep-factor` `bp-factor` `roe-ttm` `gpm-factor` `cfo-ni-ttm` `lev-factor` `log-mcap` `turnover-factor` `momentum-60d` `vol-ratio` `pe-pctl` `pb-pctl` `dy-factor` `fcf-yield` …

其中 `momentum-60d` 与 `vol-ratio` 的页面上记录的是**被淘汰的过程**，不是用法。

### 超出教科书的部分（我认为这个库最独特的几页）

| 页面 | 为什么独特 |
|---|---|
| [futures-margin-and-liquidation](wiki/concepts/risk-management/futures-margin-and-liquidation.md) | 期货保证金与强平机制实证：**追保缓冲 ≠ 强平距离**（95.4% 占用时差 **22 倍**）/ 熔断规则须换算成标的波动自检 ——「单日回撤 8% 全平」在 9.36 倍杠杆下只需跌 **0.86%**，等于没有规则 |
| [small-account-minimum-commission](wiki/concepts/risk-management/small-account-minimum-commission.md) | 小额账户最低佣金支配效应：每笔不足 5 元按 5 元（ETF 同样适用）；**月频交易 = 每年白送 6.94% 本金** |
| [small-account-execution](wiki/entities/system/small-account-execution.md) | 小额账户执行框架：整手 / 佣金下限 / 板块权限三重硬约束 + 五条自我纠错 |
| *行情数据「取错标的」陷阱*（本地版） | 期货合约级实证：主力连续 ≠ 持仓合约（把 7,910 当 8,008，**浮亏方向读反**）/ 主力连续持仓变化被换月污染 / 夜盘 21:00 整体滚动一天 / 单个仓库 ≠ 合计（仓单低估 **6.2 倍**）。含 7 条可复用纪律 |
| *单向取材型材料的识别*（本地版） | 每个数字都真实，但只引支持结论的那一半。实测 **47 条断言仅 40% 可原样引用**。五种病灶（选择性引用 / 跨报告拼装 / 标签与数字脱锚 / 伪精确 / 强度高估）—— **先问「被删了什么」，再问「数字对不对」**，逐条事实核查永远抓不到这类材料 |
| *外部数据源补充层*（本地版） | 实测 10/10 PASS + 三条反常识（翻页是假的 / 空串 ≠ 缺失 / 参数名差一词返回空） |

> ⚠️ **本仓库是 2026-10-09 的快照，落后于本地知识库。**
> 上表标「本地版」的三页（含期货合约实证、对抗性核验实证、数据源实测）**尚未发布** ——
> 其中两页含**真实账户持仓与盈亏数字**，需先脱敏才能公开。这是已知缺口，不是遗漏。

### AI 协作工具链（6 篇）

这个库是「人 + 多路 AI agent」协作产出的，踩过的工程坑单独成页：
`ai-toolchain-notes`（pwsh 传参编码 / 行尾 / Ollama 丢 tools）·
`dsh-plugin-internals`（Host/Client 重载差异 / 会话日志多帧 zstd / 两个静默给错结果的坑）·
`agent-teams`（强制力四档 / 反向加压三处 / 机制不管的四件事）·
`qlora-local-finetuning-methodology`（8GB 显存 QLoRA / GPU 疑难七步排查）·
`doubao-image-generation` · `dsh-tool-presentation-modes`

### 复盘与查询留痕

- [project-review-2026-08](wiki/comparisons/project-review-2026-08.md) —— 错误清单 **S/C/W/M 四层 22 项** + 证据链 + 改正方向 10 条
- [queries/](wiki/queries/) —— 每次检验的原始输出归档（`s1-pilot-factor-tests` / `mom60d-v3-test` / `volratio-v3-test` / `golden-samples-103-pass` / `value-vs-momentum-fm`）

### 代码与规范

| 路径 | 内容 |
|---|---|
| [`code/`](code/) | `factor_test_suite.py`（70KB 检验套件）· `backtest.py`（自研回测引擎）· `data_fetcher.py` · `e2e_pipeline.py` · `test_golden_samples.py` |
| [`docs/SOP.md`](docs/SOP.md) | 量化工作标准操作流程 v1.6 —— **踩坑记录的唯一事实源**，每踩一个坑立即回写 |
| [`docs/factor_docs/`](docs/factor_docs/) | 因子设计方案 + **每一版都有独立的审查报告**（v1/v2/v3 逐版留痕） |
| [`FILE-MANAGEMENT-STANDARD.md`](FILE-MANAGEMENT-STANDARD.md) | 文件摆放规范 |
| [`wiki/SCHEMA.md`](wiki/SCHEMA.md) | 笔记写法规范（标题 / 标签 / 来源 / 更新时间 / wiki-link） |

---

### 研究专题（独立成篇）

| 专题 | 一句话 |
|---|---|
| [**全 A 因子检验与组合层回测**](research/full-a-factor-backtest/) | 5,179 只 A 股 × 116 个月，4 个核心因子**全部淘汰**照样逐个报告失手原因；组合层七条判定「条件通过（含保留）」；一个致命 bug 由独立审查抓出、结论翻转，**首版错误结论留档备审计** |

---

> 📎 这个库里踩过的**工具层与流程层**的坑，已提炼成独立文档库：
> [**ai-collaboration-notes**](https://github.com/weihong0505/ai-collaboration-notes)
> （含「AI 工具失败模式目录」与 16 个真实案例）

---

## 这个库的方法论只有三条

1. **SOP 优先于执行** —— 遇新问题先完善 SOP 再继续，SOP 是唯一事实源
2. **结论必须有反面证据** —— 每个因子上线前必须过 IC 检验；每个设计稿必须有独立审查报告；每次检验的原始输出归档
3. **不确定就写"未核实"** —— 宁可降低交付完整度，也不用一个看起来精确、实则口径错误的数字

---

## 这个库不适合谁

- ❌ 想找**能直接用的赚钱策略**的人 —— 这里没有。恰恰相反，它记录了大量"看起来能赚钱、验证后不行"的东西
- ❌ 想要**完整可运行系统**的人 —— 回测引擎算术已验证，但**真实数据回测未执行**，四层管线是设计定稿而非成品
- ❌ 想要**教程**的人 —— 这是工作留痕，不是教程。很多页假设你已经知道 IC、分层、夏普是什么

## 这个库适合谁

- ✅ 想看**一个人怎么在没有导师、没有数据终端、没有算力的条件下，把量化研究的纪律立起来**的人
- ✅ 关心**怎么防止自己被自己的回测骗到**的人
- ✅ 想看**对抗性审查在一个真实项目里到底抓出了什么**的人

---

## 状态

| 模块 | 状态 |
|---|---|
| 因子检验方法论 | ✅ v3 定稿，已用于 17 个因子 |
| 回测引擎 | 🟡 算术正确（103 金样本 PASS），**真实数据回测未执行** |
| 因子库 | 🟡 20 个因子，2 个已淘汰，4 个待检验 |
| 组合层 / Regime 调权 | 🟡 设计稿定稿，增量价值未实测 |
| **全 A 因子检验与组合层回测** | ✅ **已完成并出结论**（4 因子全淘汰；组合层「条件通过」）→ [research/full-a-factor-backtest](research/full-a-factor-backtest/) |
| 本地数据库 | 🟡 `daily_bars` 已灌 1025 万行，估值历史 / 分红 / FCF 三张表待补 |
| 小额实盘执行框架 | ✅ 已产出可执行方案（并过独立审查） |

> **仓库版本说明**：本仓库为 **2026-10-09 发布快照**（wiki 64 页），本地知识库已更新至 2026-10-11 之后（65+ 页）。
> 本地新增的方法论页面（含真实账户数据的页面）需脱敏后才会同步过来。

---

<sub>本库为个人研究工作留痕，**不构成任何投资建议**。所有历史检验结果不代表未来表现。</sub>
