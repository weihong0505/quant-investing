# Wiki Schema — A股量化价值投资知识库



## Domain

本 Wiki 覆盖 A 股量化价值投资的全部知识领域：因子研究、策略设计、回测验证、市场观察、系统工程。

服务于 `G:/股市探究/quant-investing/code\` 项目的长期演进。



## 三层架构



```

wiki/

├── SCHEMA.md              ← 你正在读的这个文件

├── index.md               ← 内容目录（按类型分组）

├── log.md                 ← 操作日志（追加写入，年度轮转）

├── raw/                   ← 第一层：不可修改的原始资料

│   ├── articles/          ← 网页文章、研报摘录

│   ├── papers/            ← 学术论文、量化白皮书

│   ├── transcripts/       ← 播客、访谈、会议记录

│   └── assets/            ← 图片、图表

├── entities/              ← 第二层：实体页

│   ├── stocks/            ← 个股分析

│   ├── sectors/           ← 行业板块

│   ├── market-events/     ← 市场事件

│   ├── system/            ← 系统组件（代码、数据源、工具）

│   │   └── ai-tools/      ← AI 协作工具链经验（DSH/Claude 协作、编码与工具坑）

├── concepts/              ← 第二层：概念页

│   ├── factors/           ← 因子定义与研究

│   ├── strategies/        ← 策略逻辑

│   ├── risk-management/   ← 风控概念

│   └── regime/            ← 市场状态

├── comparisons/           ← 第二层：对比分析

├── queries/               ← 第二层：归档的查询结果

└── _archive/              ← 归档（内容被替代时移入）

```



## 分工原则

- **人类**：策展资料来源、决策权重调整、最终投资判断

- **AI**：摄入编译、交叉引用、一致性维护、衰减检测



## Frontmatter 规范（每页必须）



```yaml

---

title: 页面标题

created: YYYY-MM-DD

updated: YYYY-MM-DD

type: entity | concept | comparison | query

tags: [来自下方标签体系]

sources: [raw/ 下的源文件路径]

confidence: 0-100                 # 当前认知可信度（0-100 整数，档位见下方）

contested: true                     # 有未解决的矛盾时设置

contradictions: [其他页面slug]       # 与本页矛盾的页面

---

```



### confidence 含义（0–100 整数，越高越可信）

| 分值 | 档位 | 含义 |
|---|---|---|
| 90–100 | 极高 very-high | 多个独立来源交叉验证 + 近期回测/实盘支撑 |
| 70–89 | 高 high | 多来源交叉验证，或近期回测支持 |
| 50–69 | 中 medium | 单来源，或历史验证近期未复验 |
| 30–49 | 低 low | 单来源、过时，或与更新数据矛盾 |
| 0–29 | 极低 very-low | 未经验证的猜测 / 初步假设 |



## raw/ 规范

原始资料**不可修改**。添加 frontmatter 记录来源：

```yaml

---

source_url: https://...

ingested: YYYY-MM-DD

sha256: <body内容的哈希>

---

```

Re-ingest 时比对 sha256，内容变化则标记 drift。



## 标签体系（Taxonomy）



### 因子类

- `factor` — 因子总标签

- `value` — 价值因子（EP, BP）

- `quality` — 质量因子（ROE, GPM, CFO, LEV）

- `momentum` — 动量因子

- `liquidity` — 流动性因子（换手率）

- `size` — 规模因子（市值）

- `sentiment` — 情绪因子（量比）



### 分析类

- `backtest` — 回测相关

- `factor-test` — 因子检验（IC/ICIR/分组）

- `regime` — 市场状态/牛熊判断

- `correlation` — 因子相关性/共线性

- `decay` — 因子衰减/失效



### 系统类

- `data-source` — 数据源（akshare/tushare/东财）

- `pipeline` — 数据管线

- `system` — 系统组件

- `tool` — 工具/库



### 操作类

- `decision` — 重要决策记录

- `weight-change` — 权重调整

- `factor-addition` — 新增因子

- `factor-removal` — 移除因子

- `incident` — 故障/异常记录



### 市场类

- `market-event` — 重大市场事件

- `policy` — 政策变化

- `sector-rotation` — 行业轮动

- `macro` — 宏观经济



## 页面创建阈值

- **创建新页**：实体/概念在 2+ 来源中出现，或在单来源中居核心地位

- **更新现有页**：新来源提到已有页面的主题

- **不创建**：一笔带过的提及、次要细节、超出领域范围

- **拆分页面**：超过 200 行时拆分为子主题

- **归档页面**：内容被完全替代时移入 `_archive/`



## 实体页规范

每个实体一页，包含：

- 概述 / 是什么

- 关键事实与日期

- 与其他实体的 [[wikilink]] 关系

- 来源引用



## 概念页规范

每个概念一页，包含：

- 定义 / 解释

- 当前认知状态

- 未解决问题或争议

- 相关概念 [[wikilink]]



## 对比页规范

并列分析，包含：

- 对比对象和原因

- 对比维度（表格格式优先）

- 结论或综合判断

- 来源



## 更新策略

新信息与现有内容冲突时：

1. 检查日期——更新的来源通常覆盖旧的

2. 确实矛盾时，同时标注两个观点（附日期和来源）

3. 在 frontmatter 中标记：`contradictions: [page-name]`

4. 在 lint 报告中标记待审

5. **事实冲突时以 SOP/定稿规范为准，Wiki 页标注来源版本号**（如"SOP v1.4 §7 A.5"、"spec v2.1 §3.2"）；Wiki 只引用条款编号，不复制参数值，确需复制时标注"同步自 X，更新于 Y"（复盘 W3，SOP §2.1）



## 操作日志规范

所有操作记录在 `log.md`，格式：

```

## [YYYY-MM-DD] action | subject

- 操作者: AI / 用户

- 原因: 为什么做这个操作

- 影响: 创建/更新了哪些文件

- 备注: 需要复盘时关注的点

```



**action 类型**：

- `create` — 创建新页面

- `update` — 更新现有页面

- `ingest` — 摄入原始资料

- `query` — 查询并归档结果

- `lint` — 健康检查

- `decision` — 记录重要决策

- `weight-change` — 权重调整

- `archive` — 归档

- `error` — 故障记录

**实际在用但补充登记的 action**（2026-09-18 补：这些类型自 2026-08 起已在 `log.md` 实际使用，此前未登记，属登记缺失而非误用）：

- `fix` — 代码/逻辑缺陷修复
- `build` — 新功能或新模块落地
- `verify` — 验证/验收动作（含交叉核对）
- `audit` — 独立审查（含跨 AI 对抗审查）
- `review` — 审查/评审结论记录
- `review-prep` — 送审材料准备（审批前置动作）
- `organize` — 文件整理代理的自动归位
- `delete` — 删除/清理记录（须附删除对象与依据）

