---


title: SOP 操作规范（当前 v1.4）


created: 2026-08-21


updated: 2026-08-25


type: entity


tags: [system, tool]


sources: [G:/股市探究/quant-investing/docs/SOP.md]


confidence: 85


---





# SOP 操作规范 — 量化投资标准操作流程





## 概述


`G:/股市探究/quant-investing/docs\SOP.md`（当前 **v1.4**），量化研究工作的唯一事实源。


每踩一个坑、每验证一个结论，立即回写。**SOP 优先于执行**。





## 版本演进


| 版本 | 日期 | 里程碑 |


|------|------|--------|


| v1.0 | 2026-08-20 | 初版：环境、工作流、协作规范 |


| v1.1 | 2026-08-20 | 终端执行规范(-E/编码)、数据源实测表、网络诊断判断树 |


| v1.2 | 2026-08-20 | +§7 附录A 回测成本模型细则 |


| v1.3 | 2026-08-21 | 因子检验方法论定稿引用、registry 机制 |


| v1.4 | 2026-08-21 | 回测工程规范定稿引用、基准改 ETF hfq |





## 核心规范





### 1. 环境


- Python: `D:\pyh\python.exe` (3.14.6)，**必须 `-E` 运行**（PYTHONPATH 被 Hermes venv 污染）


- 终端: git-bash（POSIX 语法）；长任务 `background=true` + `notify_on_complete=true`





### 2. 网络（最高频故障区）


- 代理三件套必须在 `import requests` 之前


- ProxyError → 代理问题；RemoteDisconnected → 东财限流（冷却10+分钟，≠代理）


- 先跑 `_netdiag.py`（DNS+直连探测）隔离问题





### 3. 数据源实测状态


- ✅ 稳定：`stock_yjbb_em`（5898家）、`stock_zcfz_em`（5230家）


- ⚠️ 易限流：`stock_zh_a_spot_em`（70页分页，跨两轮审查实测被封 ≥24h）


- ✅ 兜底：新浪 `stock_zh_a_daily`（无 PE/PB、无退市股）


- ❌ 弃用：百度估值（失效）、腾讯源（复权数据污染 corr 0.046）





### 4. 因子


- **新因子必经**：registry 前置登记（预期符号锁定）→ v3 全流程检验 → MImo 审批


- 防改口三件套；防陷阱清单（TTM 累计值、逐股 PIT、负利润符号保护、金融股中性化）





### 5. 回测


- 成本模型（§7 附录A）：佣金万2.5双边+印花税万5卖出(时变)+过户万0.1+滑点四档


- 基准：**510300/510500 ETF hfq 主基准**（价格指数不含分红会虚增超额 2%/年）


- T+1 成交、涨停不买跌停不卖、成本敏感性三档 0.5x/1x/2x


- 引擎与数据细则执行 [[backtest-engineering-spec]]





## 与 Wiki 的关系


- SOP 是**操作规范**（怎么做）；Wiki 是**知识积累**（知道什么）





## 相关页面


- [[multi-factor-v2]] — SOP 服务的主系统


- [[backtest-engine]] — §3.3 的执行引擎实现


- [[factor-testing-methodology]] — §3.2 的检验方法论


- [[mimo-review]] — 因子审批流程


- [[akshare]] — 数据源规范





## 变更历史


| 日期 | 变更 | 原因 |


|------|------|------|


| 2026-08-21 | v1.4 同步入 Wiki | 回测工程规范定稿、基准修正 |


