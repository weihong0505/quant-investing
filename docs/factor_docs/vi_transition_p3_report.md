# 价值投资转型 P3 阶段验收报告 — registry 登记 + 文档同步

> 日期：2026-08-25
> 执行：AI（P3 文档同步子代理）
> 上游定稿：`docs/factor_docs/value_investing_transition_v2.1.md`（2026-08-25 终审定稿）
> 范围：docs/ 与 wiki/，未动 code/

---

## 0. 结论

**✅ 验收通过**。五项验收标准全部满足；4 新因子已完成 registry ⓪ 步前置登记，SOP/Wiki 三轨同步一致，全部写入文件并经 python（utf-8-sig）读取验证（34/34 检查项通过）。

---

## 1. Task 1 — factor_registry.md 前置登记（⓪ 步，追加式）

| # | 因子 | 类型 | 状态 | 登记时间戳 | 预期符号 | 样本期 | MImo审批 | 备注（含 W-编号草案） |
|---|------|------|------|-----------|---------|--------|---------|----------------------|
| 18 | PE_PCTL | 价值 | ⏳ 待检验（设计已审） | 2026-08-25 | − | 2018-01+ | 已审(v2.1定稿) | 设计定稿v2.1，滚动窗口分位，数据源RPT_VALUEANALYSIS_DET；W-PE_PCTL-DESIGN-20260825-01 |
| 19 | PB_PCTL | 价值 | ⏳ 待检验（设计已审） | 2026-08-25 | − | 2018-01+ | 已审(v2.1定稿) | 设计定稿v2.1，滚动窗口分位，数据源RPT_VALUEANALYSIS_DET；W-PB_PCTL-DESIGN-20260825-01 |
| 20 | DY | 价值 | ⏳ 待检验（设计已审） | 2026-08-25 | + | 2018-01+ | 已审(v2.1定稿) | 股息率，fhps_detail_em，PIT除权除息日对齐；W-DY-DESIGN-20260825-01 |
| 21 | FCF_YIELD | 价值 | ⏳ 待检验（设计已审） | 2026-08-25 | + | 2018-01+ | 已审(v2.1定稿) | TTM FCF/市值，RPT_DMSK_FN_CASHFLOW，首次公告快照固化，金融股剔除；W-FCF_YIELD-DESIGN-20260825-01 |

- **N' 更新**：1 → **5**（MOM_60D_R1 反转重登记 + 4 新因子前置登记，2026Q3）；历史全量 17 → 21
- **审计日志**：追加 2026-08-25 条目（设计定稿 v2.1 → 登记 4 新因子 → W-编号草案挂起 → 待 P4 检验）
- **#13 备注同步**："v2.1定稿（2026-08-25）：原方向已淘汰出打分体系，反转#12保持待检"（追加式，原备注保留）
- **原行未改**：✅ 1-17 行内容保持原状。⚠️ 执行中 patch 工具的模糊匹配曾对 #17 行误插一个"—"单元格（26 格），已用 python 字节级恢复为原始 24 格形态并复核（append-only 纪律优先于表格规范；#17 原行为历史遗留的 24 格省略 内部基准 列，本次未"顺手修复"）

---

## 2. Task 2 — SOP.md §3.4 价值投资决策流程

- 版本 v1.5 → **v1.6**（2026-08-25）；§6 迭代记录追加 v1.6 行
- **§3.4 价值投资决策流程（v2.1 定稿）** 新增于 §3 标准工作流下，含：
  - 四层管线概要表（①可交易性过滤 ②质量门槛 ③估值打分 ④组合构建，参数默认值以 SOP 为准）
  - 安全边际分公式（0.30/0.30/0.15/0.15/0.05/0.05，主观先验、W-编号草案挂起）
  - 新增 4 因子表（预期符号 + registry #18-21 + 登记状态 ⏳ 待检验）
  - **生产开关条款（fail-closed）**：默认拒绝实验性权重；显式 `--experimental` 允许且强制标注；**禁止实盘信号输出**
  - **事件驱动卖出信号 = 完整持仓快照语义**（禁止只列卖出股，否则连带清仓）
  - 指向定稿文档 value_investing_transition_v2.1.md
- 原 §3.4 结果输出 SOP → **§3.5**；原 §3.5 Wiki 摄入 SOP → **§3.6**（历史文档/review 中"§3.4"旧引用保留为时间戳证据，未回改）
- **§2 结构树**：新增 `value_investing.py  # (计划) 价值投资主策略 v3（v2.1 设计定稿）` 行

---

## 3. Task 3 — Wiki 更新

1. **wiki/entities/system/multi-factor-v2.md**：更新为"价值投资决策系统 v3（设计定稿 2026-08-25）"——四层管线、安全边际分公式、集中持仓 12 只季度调仓、新增 4 因子（均标"待检验"）、MOM_60D 处置、实施阶段表（P0-P5）、旧系统 v2 保留对照（8 因子重归一化权重表）
2. **新建 4 概念页**（wiki/concepts/factors/）：pe-pctl.md / pb-pctl.md / dy-factor.md / fcf-yield.md——frontmatter 含 `contested: false` + `status: 待检验`，sources 指向 value_investing_transition_v2.1.md；每页含定义/数据源/预期符号（registry 锁定）/检验状态/风险
3. **momentum-60d.md**：状态改"**原方向已淘汰（#13，试点反向显著）；反转方向待检（#12）**"（frontmatter status + 正文状态节 + 变更历史 2026-08-25 行；代码现状 0.15 注明待 P2 归零）
4. **log.md**：追加 `[2026-08-25] update | 价值投资转型 v2.1 设计定稿：registry 登记 4 新因子 + SOP/Wiki 三轨文档同步（P3）`（含决策原因：设计已审 ≠ 统计检验、fail-closed、快照语义）
5. **index.md**（SOP §3.5 同步机制要求）：multi-factor-v2 条目改 v3 描述、momentum-60d 条目更新、+4 因子页、Total pages 49 → 53

---

## 4. Task 4 — 三轨一致性验证（python，utf-8-sig 读取）

- **registry**：4 新行全部字段（状态/时间戳/符号/样本期/MImo审批/结论/W-编号）逐项核对 ✅
- **SOP**：§3.4 存在、四层管线、公式、4 因子表、生产开关、快照语义、定稿文档引用、§2 树、v1.6 全部核对 ✅
- **wiki**：4 新页 frontmatter+正文结构、multi-factor-v2 v3 描述、momentum-60d 状态、log.md、index.md 全部核对 ✅
- **三轨一致性**：PE_PCTL(−)/PB_PCTL(−)/DY(+)/FCF_YIELD(+) 在 registry/SOP/wiki 三处均为"⏳ 待检验（设计已审）"表述 ✅
- **编码**：全部文件 UTF-8 无 BOM（registry/wiki 原为 LF，SOP 原为混合换行 748 CRLF+LF——写入后 CRLF 数 748 不变，字节级保留）

---

## 5. 遗留与注意事项

1. **data_caliber_audit.md**：设计 §6 列出的"6 字段口径行 + 行业映射表"未动——按设计属 **P1 阶段**（接口实测后登记），非 P3 范围；P1 完成接口实测后需补
2. **历史引用不回改**：docs/review_2026-08/ 与 wiki/log.md 旧条目中的"§3.4 结果输出"等引用保留原样（时间戳证据）；新读者以 SOP §3.5/§3.6 为准
3. **并发写入告警**：写入 multi-factor-v2.md 时系统提示该文件被同级子代理 sa-0-e5205b7a 并发修改过——本代理版本为按任务规格的完整 v3 描述（四层管线/公式/12 只季度调仓/4 因子待检验/旧系统对照），若父级需核对另一版本请比对
4. **#17 行格式**：registry 现存 #17 行为 24 格（历史遗留缺 内部基准 列，与 #1-11 同款旧格式），本次按 append-only 纪律未修复；如需规范化应另起追加行
5. **P4 出口**：4 新因子检验通过前，权重一律"实验性"，生产开关 fail-closed 拒绝实盘信号（SOP §3.4 已固化）

---

## 6. 修改文件清单

| 文件 | 操作 |
|------|------|
| docs/factor_docs/factor_registry.md | 追加 #18-21、N' 1→5、历史全量 21、审计日志 2026-08-25、#13 备注同步 |
| docs/SOP.md | v1.6；§3.4 新增；§3.5/§3.6 顺延；§2 树；§6 迭代记录 |
| wiki/entities/system/multi-factor-v2.md | 重写为 v3 描述 |
| wiki/concepts/factors/pe-pctl.md | 新建 |
| wiki/concepts/factors/pb-pctl.md | 新建 |
| wiki/concepts/factors/dy-factor.md | 新建 |
| wiki/concepts/factors/fcf-yield.md | 新建 |
| wiki/concepts/factors/momentum-60d.md | 状态更新 + 变更历史 |
| wiki/log.md | 追加 2026-08-25 条目 |
| wiki/index.md | 4 因子页 + 两条目更新 + Total pages 53 |
| docs/factor_docs/vi_transition_p3_report.md | 本报告 |
