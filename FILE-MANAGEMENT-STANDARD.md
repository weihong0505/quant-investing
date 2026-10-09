---
title: 文件管理标准 / File Management Standard
created: 2026-08-22
updated: 2026-08-25
type: spec
version: v1.4
tags: [standard, file-management]
---

# 文件管理标准 / File Management Standard

> **定位**：本库（`G:\股市探究\quant-investing\`）文件组织方式的**唯一事实源**。
> **受众**：在本库工作的 AI 代理（agent）与维护者。
> **用途**：任何文件的新建、命名、移动、重命名、归档、删除操作，都必须先按本标准执行。

> **阅读优先级**：AI 进入本库后，先读本文件 → 再按需读 `docs/SOP.md`（量化流程）与 `wiki/SCHEMA.md`（知识库内容规范）。

---

## 1. 总纲与优先级 / Principles & Precedence

三条铁律（所有文件操作的判据）：

1. **可定位 Locatable** — 任意文件都有且仅有一个「规范归宿」；只看文件类型，任何人（或 AI）都能立刻判断它该在哪、该叫什么。
2. **可复现 Reproducible** — 所有产出物带时间戳与来源，可重新生成；缓存与临时文件可安全删除重建。
3. **可追溯 Traceable** — 每次文件变更留下记录；原始资料不可篡改，历史不可静默覆盖。

**优先级（规范冲突时的裁决）**：

| 问题类型 | 以哪份为准 | 说明 |
|---|---|---|
| 文件放哪、叫什么、何时归档/删除 | **本文件** | 文件机制（mechanics） |
| 知识库页面内容该有什么、标签怎么定 | `wiki/SCHEMA.md` | 内容语义（semantics） |
| 因子/回测/研究该怎么走流程 | `docs/SOP.md` | 工作流程（process） |

冲突时「最具体者优先」：文件摆放问题看本文件；内容问题看 SCHEMA.md；流程问题看 SOP.md。仍无法裁定 → 停下问人，并把裁决结果回写进本文件。

---

## 2. 目录结构 / Directory Structure

### 2.1 规范结构（canonical layout）

```
quant-investing/                    # 库根 —— 只放「总纲类」文件
├── FILE-MANAGEMENT-STANDARD.md    # 本文档
├── code/                          # 可执行代码（Python）
│   ├── *.py                       # 主模块（snake_case）
│   ├── _*.py                      # 临时/诊断脚本（用完删除）
│   ├── test_*.py                  # 测试脚本
│   ├── _draft/                    # 未审批代码（SOP §3.0.2），审批后移入主目录
│   ├── data_cache/                # ⚠️ 遗留缓存位置（待并入 data/cache/，见 §13）
│   ├── factor_tests/              # 因子检验脚本
│   ├── logs/                      # 运行日志（SOP §1.1；当前未建，见 §13）
│   └── __pycache__/               # 自动生成，勿手动管理
├── data/                          # 外部数据（与代码运行分离）
│   └── cache/                     # ✅ 数据缓存的唯一规范归宿
├── docs/                          # 规范与研究文档
│   ├── SOP.md                     # 量化工作 SOP（唯一事实源）
│   ├── factor_docs/               # 因子方案 + 审批/检验报告
│   ├── research/                  # 研究笔记、阅读清单
│   └── review_YYYY-MM/            # 按周期归档的项目复盘
├── output/                        # 结果输出（可再生）
│   └── picks/                     # 选股表
├── wiki/                          # 知识库（独立 Obsidian vault，结构见 SCHEMA.md）
│   ├── raw/                       # 原始资料（不可改）：articles/papers/transcripts/assets
│   ├── entities/                  # 实体页：stocks/sectors/market-events/system（system/ai-tools/ 放 AI 协作工具链经验）
│   ├── concepts/                  # 概念页：factors/strategies/risk-management/regime
│   ├── comparisons/               # 对比分析
│   ├── queries/                   # 归档的查询结果
│   ├── index.md / log.md / SCHEMA.md
│   └── _archive/                  # 归档（内容被替代时移入）
└── ai/                            # 本地模型与 AI 资产
    └── models/                    # Ollama 模型文件
```

### 2.2 各目录职责与禁区

| 目录 | 放什么 | 禁止放什么 |
|---|---|---|
| 库根 `/` | 仅总纲类（本文件；如需可加 README） | 任何数据、代码、临时文件、散落 .md |
| `code/` | 可执行脚本、测试、临时诊断脚本 | 研究笔记、规范文档、原始资料 |
| `data/cache/` | 外部拉取的原始/半成品数据缓存 | 手写分析、结果结论 |
| `docs/` | SOP、因子方案、研究、复盘 | 可执行代码、缓存、原始资料 |
| `output/` | 选股表、回测报告等**可再生结果** | 手写的不可再生笔记（那是 wiki/docs） |
| `wiki/` | 知识页 + 原始资料 + 索引/日志 | 可执行代码、缓存、模型文件 |
| `ai/models/` | 模型权重等大二进制 | 任何文本/代码/文档 |

### 2.3 新文件归属决策树 / Decision Tree

拿到一个新文件，依次问：

1. 是**可执行代码**？ → `code/`（主模块裸放；临时脚本 `_` 前缀）
2. 是**原始摄入资料**（文章/论文/转录）？ → `wiki/raw/{articles|papers|transcripts}/`
3. 是**知识页**（实体/概念/对比）？ → `wiki/{entities|concepts|comparisons}/` 对应子目录
4. 是**因子方案或审批/检验报告**？ → `docs/factor_docs/`
5. 是**研究笔记 / 阅读清单**？ → `docs/research/`
6. 是**项目复盘**？ → `docs/review_YYYY-MM/`
7. 是**可再生结果**（选股表/回测报告/图表）？ → `output/`
8. 是**缓存/下载数据**？ → `data/cache/`（规范归宿；`code/data_cache/` 为遗留位置，勿新增）
9. 是**规范 / 规则 / 流程文档**？ → `docs/`
10. 是**模型/权重**？ → `ai/models/`
11. 是**临时/草稿**？ → 对应目录内 `_` 前缀文件，用完删除；**未审批代码放 `code/_draft/`**

> 不在任何上述类别 → **停下，不要随手放根目录**，先问人归类。

---

## 3. 命名规范 / Naming Conventions

### 3.1 分类型命名表

| 类型 | 模式 | 示例 |
|---|---|---|
| Python 主模块 | `snake_case.py` | `multi_factor_value.py` |
| 临时/诊断脚本 | `_snake_case.py` | `_netdiag.py` |
| 测试脚本 | `test_*.py` | `test_golden_samples.py` |
| 启动脚本 | `*.bat` / `*.sh`（snake_case） | `run.bat`、`setup_obsidian.bat` |
| 因子设计文档 | `{factor}_v{n}.md` | `quality_factors_v2.md` |
| 审查报告 | `{被审文档}_review_round{n}.md` | `backtest_engineering_spec_v1_review_round1.md` |
| 审查验证脚本 | `_*_verify*.py`（作为证据归档，保留） | `_methodology_review_verify_v2.py` |
| 定稿规范 | `{topic}_spec_v{major}.{minor}.md` | `backtest_engineering_spec_v2.1.md` |
| 检验方法论 | `{topic}_methodology_v{n}.md` | `factor_testing_methodology_v3.md` |
| 复盘发现 | `{C\|M\|S\|W}{n}_{标题}.md` | `C1_run_py入口崩溃.md` |
| 验证输出 | `{id}_validation_output.txt` | `C5_validation_output.txt` |
| 数据缓存 | `{接口}_{YYYYMMDD}.parquet` | `stock_yjbb_em_20260820.parquet` |
| 选股表 | `pick_{YYYYMMDD}.csv` | `pick_20260820.csv` |
| 回测报告 | `backtest_{策略}_{YYYYMMDD}.html` | `backtest_multi_factor_20260820.html` |
| 运行日志 | `run_{YYYYMMDD_HHMMSS}.log` | `run_20260820_143000.log` |
| Wiki 页面 | `kebab-case.md`（slug） | `ep-factor.md`、`multi-factor-v2.md` |
| 研究笔记 | `{主题}.md`（英文下划线亦可） | `regime_based_weights.md` |

### 3.2 通用命名规则

- **能用 ASCII 就用 ASCII**；中文仅用于人类可读的文档标题，且同类文件保持一致。
- **文件名无空格**：用 `_`（代码/数据）或 `-`（wiki slug）。
- **禁用的字符**：`/ \ : * ? " < > |` 及首尾的空格、点号。
- **日期一律 `YYYYMMDD`**（可排序、无歧义）；时间戳 `YYYYMMDD_HHMMSS`。
- **版本后缀**：`_v{n}` 或 `_v{major}.{minor}`；**绝不静默覆盖旧版本**——要改就升版本号。
- **`_` 前缀 = 临时/草稿**，用完删除；`_archive/` = 归档目录。
- **大小写**：代码/脚本 `snake_case`，wiki slug `kebab-case`，避免 PascalCase。
- **编码 Encoding**：文本一律 UTF-8（无 BOM）；供 Excel 打开的 CSV 用 `utf-8-sig`；Python 头部注明 `# -*- coding: utf-8 -*-`（SOP §1.2）。

### 3.3 前缀速查 / Prefix Reference

| 前缀 | 含义 | 处置 |
|---|---|---|
| `_*.py` | 临时/诊断脚本 | 用完删除；`_*_verify*.py` 审批证据脚本除外（保留归档，见 SOP §3.0.5） |
| `test_*` | 测试脚本 | 保留 |
| `00_` | 目录 README/索引头 | 保留，置于目录最前 |
| `C/M/S/W{n}_` | 复盘发现分级（Code/Methodology/System/Wiki） | 保留，归档于 `review_YYYY-MM/` |
| `_archive/`、`_draft/` | 归档 / 草稿目录 | 见 §8 |

---

## 4. Frontmatter 规范 / Frontmatter

> 所有**手写 .md**都必须有 frontmatter，**除外**：`raw/` 内文件、自动生成文件、以及 `index.md`/`log.md` 等追加型操作文件。AI 不得删改已有 frontmatter；每次编辑必须更新 `updated`。

### 4.1 全局基准字段（所有 .md 至少含）

```yaml
---
title: 页面标题
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: <见下方各类型>
tags: [来自受控词表]
sources: [相对路径，指向 wiki/raw/ 或引用的源文件]   # 有引用源时必填；无来源的规范文档可省略
---
```

### 4.2 分类型必填字段

**Wiki 页**（完整规范见 `wiki/SCHEMA.md`）：

```yaml
---
title: 页面标题
created: 2026-08-22
updated: 2026-08-22
type: entity | concept | comparison | query
tags: [来自 SCHEMA.md 标签体系]
sources: [raw/ 下的源文件路径]
confidence: 0-100                 # 当前认知可信度（0-100 整数，档位见 SCHEMA.md）
contested: true                    # 有未解决矛盾时
contradictions: [其他页面 slug]
---
```

**docs/ 研究笔记**：`type: note | reading`，加 `status: draft | review | final`。规范文档（SOP、本标准）用 `type: spec`；复盘发现用 `type: review-finding`。

**docs/factor_docs/**：

```yaml
---
title: 质量因子设计
created: 2026-08-20
updated: 2026-08-20
type: factor-design | factor-review | spec | test-report
factor: quality
status: draft | review | final
version: v2
approver: MImo            # 审批类必填
approved_on: 2026-08-20   # 审批通过日期
tags: [quality, factor]
sources: []
---
```

**docs/review_YYYY-MM/**：

```yaml
---
title: run.py 入口崩溃
created: 2026-08-22
updated: 2026-08-22
type: review-finding
severity: C              # C=代码 M=方法论 S=系统 W=Wiki
evidence: [C1_validation_output.txt]
tags: [incident]
---
```

---

## 5. 标签体系 / Tag Taxonomy

- 使用**受控词表**，跨目录保持一致；Wiki 内容的标签体系以 `wiki/SCHEMA.md` 为准。
- **不得随手造新标签**。确需新标签时，先在 SCHEMA.md 的 taxonomy 登记，再使用。
- 标签一律**小写 kebab-case**、无空格。
- 区分「标签 = 分类维度」与「目录 = 结构维度」：**不要把目录信息重复塞进标签**（文件在 `concepts/factors/` 下，就不必再打 `factor` 目录标签——语义分类标签除外）。
- **docs/ 与库根文档**使用「1 大类 + ≤2 描述」标签原则：大类受控词 `standard | spec | review | research | note | factor`，可再附 ≤2 个描述性标签（如 `file-management`）；新增大类标签先登记再使用。

---

## 6. 链接规范 / Linking

- 内部引用一律 `[[wikilink]]`，目标用 **slug**（= 文件名去掉 `.md`）。
- Wiki 页之间按 SCHEMA.md 的实体/概念规则互相链接。
- 外部来源：URL 写进源文件 frontmatter（SCHEMA.md 的 `source_url`），**正文里不要散落裸 URL**。
- **断链与孤儿页**：链接到不存在的页面会在 lint 中标记；不计划立刻创建的链接不要写。
- **slug 一致**：`[[wikilink]]` 目标必须与目标文件名（去 `.md`）逐字一致。
- **index 同步**：每次新增/删除/重命名 Wiki 页，必须同步 `wiki/index.md` 对应分组的一行条目（`[[slug]] — 一句话摘要`）。

### 6.1 重命名 / 移动的强制回改

重命名或移动任何文件后，**必须**：

1. 全库搜索 `[[旧名]]`，逐一改回 `[[新名]]`；
2. 更新 `index.md`（若被索引）与 `log.md`；
3. 若文件带附件，附件一并迁移。

---

## 7. 附件与媒体 / Attachments & Media

- 摄入的图片/图表/PDF → `wiki/raw/assets/`（见 SCHEMA.md）。
- 回测/分析生成的图表 → 与所属报告同放 `output/`，或随研究笔记放 `docs/research/`。
- 命名：`{主题}_{YYYYMMDD}.png`（描述性 + 日期）。
- **大二进制**（>10MB：模型权重、大数据集）→ `ai/models/` 或 `data/`，**不入 wiki/、不进 git**。
- 引用用相对路径或 `[[wikilink]]`；**禁止在笔记里写死绝对 Windows 路径**（破坏可移植性）。

---

## 8. 文件生命周期 / File Lifecycle

状态：`draft → active → archive → delete`。

| 阶段 | 触发条件 | 动作 |
|---|---|---|
| **create** | 达创建阈值（Wiki 页见 SCHEMA.md「页面创建阈值」；因子见 SOP §3.0） | 走 §2 决策树 + §3 命名 + §4 frontmatter |
| **update** | 内容变更 | 更新 `updated` + 追加日志（§9） |
| **archive** | 内容被完全替代 / 过期 | 移入 `wiki/_archive/`（知识页）或 `docs/review_YYYY-MM/`（复盘）；**不删历史**（`factor_docs/` 的规范走「升版本保留」，不归档） |
| **delete** | 仅限临时/草稿与可再生缓存 | 删 `_*.py`、缓存；**删除源文件/历史必须先问人** |

**硬规则**：

- `wiki/raw/` **不可修改**：重摄入时比对 `sha256`，内容变化标 `drift`（SCHEMA.md）。
- 未审批代码放 `code/_draft/`（SOP §3.0.2），审批通过再进主目录。
- `__pycache__/`、缓存均为可再生，**不手动管理、不纳入规范**。
- 旧版本**永远保留**（升版本而非覆盖）。

---

## 9. 日志与审计 / Logging

- Wiki 操作写 `wiki/log.md`，格式按 SCHEMA.md：

```
## [YYYY-MM-DD] action | subject
- 操作者: AI / 用户
- 原因: ...
- 影响: 创建/更新了哪些文件
- 备注: ...
```

`action` 类型：`create / update / ingest / query / lint / decision / weight-change / archive / error`。

- **代码/文档操作**：任何「新建/移动/重命名/删除」必须可追溯——有 git 则写 commit message，无 git 则追加对应 `log.md` 条目。
- 违反「可追溯」的文件变更视为不规范，需补记。

---

## 10. AI 代理执行清单 / AI Agent Checklist

> 这是给「其他 AI」用的核心。任何文件操作，按三阶段逐项过一遍。
> **元规则**：任何一步拿不准（放哪 / 叫什么 / 该不该删），**停下问人**，不要猜、不要随手放根目录。

### 10.1 新建文件前（Before create）

- [ ] 判断文件类型 → 走 §2.3 决策树，锁定目录
- [ ] 按 §3 定名（含日期/版本/前缀）
- [ ] 全库搜索同主题，避免**重复文件**
- [ ] Wiki 页：核对 SCHEMA.md「页面创建阈值」（2+ 来源？核心地位？）
- [ ] 因子文档：核对 SOP §3.0 审批流程
- [ ] 备好 §4 对应类型的 frontmatter（必填字段齐全）

### 10.2 写作时（During write）

- [ ] frontmatter 字段填全、类型/值在允许范围内
- [ ] 标签只取自 §5 受控词表，不造新词
- [ ] `[[wikilink]]` 用正确 slug（§6）
- [ ] 引用源文件路径写进 `sources:`，正文不散落裸 URL

### 10.3 完成后（After）

- [ ] 更新 `updated` 字段
- [ ] 更新 `index.md`（Wiki 页必做）或相关索引
- [ ] 追加日志条目（§9）
- [ ] 自检：无断链、无孤儿页、无重复
- [ ] 临时脚本 `_*.py`：目的达成即删除

### 10.4 移动 / 重命名（Before move/rename）

- [ ] 全库搜索 `[[旧名]]` 反链，全部改回
- [ ] 更新 `index.md` / `log.md` 引用
- [ ] 附件一并迁移

### 10.5 删除（Before delete）

- [ ] 是可再生缓存/临时文件？→ 可直接删
- [ ] 是源文件/历史/知识页？→ **归档而非删除**（移 `_archive/`）
- [ ] 确需永久删除？→ **停下，问人确认**

---

## 11. 反模式清单 / Anti-patterns

以下为禁止项，附**本库当前实际存在的实例**（撰写时扫描所得，应清理）：

| # | 反模式 | 现状实例 | 处置 |
|---|---|---|---|
| 1 | 库根散落文件 | 根目录 `wikilink.md`（0 字节）、`0`（0 字节） | 删除或归位 |
| 2 | Obsidian 临时产物残留 | `wiki/未命名.base`、`wiki/未命名 1.base`、`wiki/untitled-session-20260822.json` | 删除 |
| 3 | 命名不规范散落输出 | `output/smoke_ic_monitor_c6.txt`（应遵循 §3.1，如 `{策略}_smoke_{YYYYMMDD}.txt` 或归档） | 重命名/归档 |
| 4 | 重复/孤儿文件 | 同内容多处存放 | 合并，保留规范版本 |
| 5 | 手写 .md 缺 frontmatter | — | 补齐 |
| 6 | 同类文件命名混用（空格/中文/大小写混） | — | 统一到 §3 |
| 7 | 笔记里写死绝对 Windows 路径 | — | 改相对路径/`[[wikilink]]` |
| 8 | 一次性标签泛滥 | — | 清理并回写 taxonomy |
| 9 | 修改 `raw/` 原始资料 | — | 禁止，重摄入标 drift |
| 10 | 静默覆盖旧版本 | — | 升版本号 |
| 11 | 把密钥写进笔记 | `wiki/.env`（含 OBSIDIAN_API_KEY 等） | 移出 vault，或加入 `.gitignore`（若有 git）；绝不入库/入索引 |

---

## 12. 与其他规范的关系 / Relationship to Other Standards

| 文档 | 管辖 | 冲突时优先级 |
|---|---|---|
| `FILE-MANAGEMENT-STANDARD.md`（本文档） | 文件放哪、叫什么、生命周期 | 文件机制最高 |
| `docs/SOP.md` | 量化研究/回测工作流程 | 流程问题最高 |
| `wiki/SCHEMA.md` | 知识库内容语义、标签体系、页面阈值 | 内容语义最高 |
| `wiki/index.md` | 内容目录（派生，须与页面同步） | 派生索引 |
| `docs/factor_docs/*` | 特定因子/规范细节 | 各自范围内最高 |

**裁决链**：文件摆放 → 本文件；内容写法 → SCHEMA.md；研究流程 → SOP.md。

---

## 13. 附录：已知漂移与待清理 / Known Drift & Cleanup

撰写本标准时（2026-08-22）扫描发现的、与规范不一致之处，供后续清理与对齐：

1. **根目录杂物**：`wikilink.md`、`0` 两个 0 字节散落文件 → 删除。
2. **wiki 临时产物**：`.base`、`untitled-session-*.json` → 删除。
3. **缓存位置不唯一**：`data/cache/` 与 `code/data_cache/` 并存。SOP §1.1 记载为 `code/data_cache/`，但根目录又出现 `data/`。**需二选一**（建议统一为 `data/cache/`，代码运行期缓存单独隔离），裁定后回写 §2 与 SOP。
4. **散落输出**：`output/smoke_ic_monitor_c6.txt` → 重命名或归档。
5. **logs/ 缺失**：SOP §1.1 记载 `code/logs/`，当前未建 → 补建目录并让脚本写入。
6. **审查报告命名漂移**：`factor_docs/` 内审查报告存在三种写法（`{doc}_review_round{n}.md`、`{factor}_v{n}_review.md`、`review_{doc}_v{n}_round{n}.md`）→ 统一为 §3.1 的 `{被审文档}_review_round{n}.md`。
7. **核心文档缺 frontmatter**：`SCHEMA.md`、`SOP.md` 当前无 frontmatter（`index.md`/`log.md` 按 §4.1 豁免）。建议后续为 SCHEMA/SOP 补齐。
8. **raw/ 文件带 confidence frontmatter**：`wiki/raw/papers/composite-testing-methodology-review.md` 含 `confidence: medium/high`（raw/ 按 SCHEMA 只应有 `source_url`/`ingested`/`sha256`，不该有 confidence）。→ 整文件重摄入或移出 raw/，勿直接改 raw/ 内容。

> 清理动作本身也要按 §9 记日志。

---

## 版本记录 / Changelog

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-08-22 | v1.0 | 初稿：总纲、目录、命名、frontmatter、标签、链接、附件、生命周期、日志、AI 清单、反模式、规范关系、已知漂移 |
| 2026-08-22 | v1.1 | 迭代1（补完整性）：补 `code/_draft/` 入规范树；定 `data/cache/` 为唯一缓存归宿、标记 `code/data_cache/` 遗留；新增 §3.3 前缀速查表；新增编码规范（UTF-8/utf-8-sig）；补 factor_docs 与 review 的完整 frontmatter 示例；新增 docs 级标签词表、slug 一致、index 同步、大二进制管理、AI 元规则 |
| 2026-08-22 | v1.2 | 迭代2（校对一致性）：审查报告命名模式改 `{被审文档}_review_round{n}.md` 并与示例对齐；`sources` 改为有源才填；统一 docs 各 `type` 枚举；docs 标签改「1 大类 + ≤2 描述」原则并收紧本文档自身 tags；补 `logs/` 入规范树；§13 新增 logs/ 缺失与审查命名漂移；§11 密钥项按实测改 `.env` 内容并注明 git 为条件 |
| 2026-08-22 | v1.3 | 迭代3（扫边界定稿）：§4.1 明确豁免 `raw/`、自动生成、`index.md`/`log.md` 等操作文件；§3.1 补启动脚本 `.bat`/`.sh` 命名；§13 新增 SCHEMA/SOP 缺 frontmatter 待补齐项 |
| 2026-08-25 | v1.4 | confidence 从 high/medium/low 三档改为 0-100 数字评分（全库统一，对齐 SCHEMA.md 5 档位表）；§13 登记 raw/ 带 confidence 的漂移项 |
