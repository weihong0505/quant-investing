# C8 — regime_weights.py 半成品：核心函数无条件 NotImplementedError + 先写码后审批
> 审批材料已备（docs/factor_docs/regime_based_weights_review_request.md）；MImo 审批已完成（2026-08-22 **有条件通过**，研究验证用途，见 docs/factor_docs/regime_weights_review_20260822.md），代码已实现并通过 4/4 验证（AI-C8 并行完成）。验收状态以审批报告与验证输出为准。

> ✅ 已验收 2026-08-22 操作者: AI-C8（审批通过 → 实现路径；4/4 验证 + 导入验收全过）

> 来源：项目复盘 2026-08-22 第 C8 项（Wiki 全文：G:\quant-investing\wiki\comparisons\project-review-2026-08.md）
> 严重度：🟠 重大　|　任务性质：代码修复 + 审批补流程　|　涉及文件：code/regime_weights.py、docs/research/regime_based_weights.md
> 依赖：需先有历史因子 IC 数据（依赖 S2 数据层）　|　建议优先级：第五批

## 1. 问题现状

① `regime_weight_history()`（设计文档 §5 验证要求的核心函数）函数体**无条件 raise NotImplementedError**——历史 PIT 调权验证在代码层面被掐断，永远不可能执行；② 设计文档自己标注"状态：设计稿（P2），尚未实施。按 SOP §3.0，实施前须经 MImo 审批"——**审批未做，代码已写**，违反强制流程。

## 2. 证据

- `code/regime_weights.py` L98：`raise NotImplementedError('因子值表需按因子分组传入...')`，前面还有一段空转的死循环代码（`for f in base_weights: if f in f_window.columns or f in f_window.index: pass`）
- `docs/research/regime_based_weights.md` 头部："状态：设计稿（P2），尚未实施。按 SOP §3.0，实施前须经 MImo 审批"
- `docs/SOP.md` §3.0："未过审的因子不得进入主策略"；设计文档 §5 验证要求 1-4（walk-forward PIT 调权、对比固定权重、调权增益>换手成本增量、参数敏感性）全部依赖 `regime_weight_history` 式功能——当前无法执行

## 3. 为什么是错

1. 半成品代码入主线：验收时只能跑 `regime_weights()` 单点调权冒烟，核心验证路径被 NotImplementedError 封死，给人"模块完成"的假象（Wiki 已为它建实体页）
2. 流程颠倒：先写码后审批——SOP §3.0 的强制流程被反向执行
3. 设计自身有隐患（设计文档自认"ICIR 噪声大"）：36m 窗口 ICIR 估计误差极大（项目实测 90 月功效不足），季度用噪声调权 = 引入新的过拟合面；且 ICIR 调权无视因子相关性——两个高相关因子会被同步加成，集中度风险。这些隐患正是审批流程应该拦下的

## 4. 修改要求

1. **先补审批，再动代码**：将 `docs/research/regime_based_weights.md` 按 SOP §3.0 提交 MImo 审查（delegate_task），重点审查问题：① 36m ICIR 噪声下季度调权的增量价值 ② 相关因子同步加成的处理（是否加相关性惩罚）③ floor=0.1/±50%/36m 参数的敏感性 ④ 与"先检验后集成"纪律的关系。审批结论存档 factor_docs/
2. **审批通过后**二选一：
   - 实现 `regime_weight_history()`：输入改为明确的 `factors_ic: Dict[str, pd.Series]`（每因子一条全历史 IC 序列，由 ic_monitor.ic_series 产出），对每个季度调权日取该日之前 36m 窗口算 ICIR → 调权 → 输出权重历史 DataFrame；删除死代码段
   - 或明确"暂缓实施"：**删除** regime_weights.py（连同 Wiki 实体页），保留设计文档待审状态，避免半成品长期污染主线
3. 无论哪种：审批未通过前，Wiki regime-weights 页标注"设计稿待审，代码已冻结/已移除"
4. 注意 `regime_weights()` 单点函数中"约束+归一化交替迭代 50 次"逻辑本身已通过冒烟（保持不动）

## 5. 验收标准

- [x] MImo 审批报告存在于 factor_docs/（含审查意见与结论）
- [x] `grep NotImplementedError code/regime_weights.py` 无残留（实现方案）或模块已删除（暂缓方案）
- [x] 死代码段（空转 for 循环）已清除
- [x] 若实现：合成 IC 数据下权重历史与逐期手算一致（抽查 2 个调权日）；PIT 无未来函数（调权日只用到其之前的数据）
- [x] Wiki 页面状态与审批结论一致

## 6. 修改后需同步的文档

- wiki/entities/system/regime-weights.md
- wiki/log.md（decision 记录审批结论）
