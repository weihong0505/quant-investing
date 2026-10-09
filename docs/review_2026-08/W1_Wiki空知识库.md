# W1 — Wiki 是"代码的镜像"，不是知识库：零资料摄入

> 来源：项目复盘 2026-08-22 第 W1 项（Wiki 全文：G:\quant-investing\wiki\comparisons\project-review-2026-08.md）
> ✅ 已验收 2026-08-22 AI批处理：raw/papers×2 + raw/articles×1摄入，concepts/regime/建3页，index.md更新
> ✅ 已验收（第二批）2026-08-22 AI批处理：raw/papers ×2 + raw/articles ×2 摄入（累计 papers×4 / articles×3，均带 source_url/ingested/sha256 frontmatter）、concepts/regime/ 新增市场状态识别（累计 4 页，confidence low）、queries/ ×2 归档（S1 试点检验、金样本 103 PASS）、SOP §3.5 Wiki 摄入 SOP、index.md（34→41）/log.md 同步
> 严重度：🟡 中等　|　任务性质：Wiki 建设　|　涉及文件：wiki/raw/、wiki/concepts/、wiki/queries/、wiki/index.md
> 依赖：无　|　建议优先级：随时可做

## 1. 问题现状

建库初衷（LLM Wiki："资料进来时先整理"优于 RAG"问的时候再找"）完全没有实现。27 个页面全部是从代码/文档自动生成的描述页，**没有任何一份原始资料被摄入**。

## 2. 证据

- `wiki/raw/articles/`、`raw/papers/`、`raw/transcripts/`、`raw/assets/` **全部为空**
- `wiki/queries/` 空；`wiki/concepts/regime/` 空
- 全部页面 sources 字段指向的都是项目自己的代码文件（如 multi_factor_value.py），没有一篇外部资料
- SCHEMA.md 定义的三层知识工作流（raw 摄入 → 提炼 → concepts 落地）从未运转过一次

## 3. 为什么是错

Wiki 现在的更新逻辑是"代码变了就同步一页描述"——本质是 docs/ 的平行宇宙，没有知识增量。而项目真正的知识资产（两轮 MImo 审查报告、数据源实测结论、功效模拟结果、金样本方法论）散落在 factor_docs 里没有被结构化提炼。知识库空转。

## 4. 修改要求

1. **第一批摄入清单（现成素材，零外部依赖）**：
   - `raw/papers/`：两轮审查报告（`backtest_engineering_spec_v2_review_round2.md`、`review_factor_testing_methodology_v2_round2.md` 等 4 份）——按 SCHEMA raw 规范加 frontmatter（source_url/ingested/sha256）
   - `raw/articles/`：数据源实测验证脚本结论（东财限流模式、qfq 负价实弹、退市股三源对照）——从 factor_docs 的 `_*.py/_*.json` 验证产物提炼
   - `concepts/regime/`：市场状态相关概念（结构断点 2017/2021/2024 微盘危机）建页，sources 指向 raw
   - `queries/`：归档本次复盘的全部实测记录（金样本运行输出、_netdiag 输出、grep 证据）
2. **建立持续摄入机制**：每次 MImo 审查、每次数据验证、每次回测 → 先落 raw/（不可修改），再提炼可执行结论到 concepts/，SOP 加一节"Wiki 摄入 SOP"
3. **页面证据规范**：concepts 页面的"当前认知状态"必须挂证据（raw 文件路径或检验报告编号）；无证据的观点标 low
4. index.md 同步新增条目

## 5. 验收标准

- [ ] raw/ 至少含 6 份摄入资料（带规范 frontmatter）
- [ ] concepts/regime/ 至少 3 个页面（结构断点类）
- [ ] 每个新页面 sources 非空且指向 raw/ 或检验报告
- [ ] SOP 增加"Wiki 摄入 SOP"小节

## 6. 修改后需同步的文档

- docs/SOP.md（摄入 SOP）
- wiki/index.md、wiki/log.md
