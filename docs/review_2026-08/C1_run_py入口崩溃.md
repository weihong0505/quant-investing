# C1 — run.py 入口必然崩溃（三元解包二元组）

> 来源：项目复盘 2026-08-22 第 C1 项（Wiki 全文：G:\quant-investing\wiki\comparisons\project-review-2026-08.md）
> ✅ 已验收 2026-08-22 AI批处理：run.py二元解包修复，banner叙事更新，import与解包验证通过
> ✅ 实跑验收 2026-08-22（AI 验收子任务）：run.py 实跑 18s 完成、无 ValueError；静态检查解包一致；import 回归通过 — **通过**。注：实跑暴露 C10 链路下游新问题（新浪代码前缀导致因子 merge 全 NaN → pick 表 30 行全 bj + SCORE 全 NaN），与 C1 解包无关，已记入 C10 页
> 严重度：🔴 阻断　|　任务性质：代码修复　|　涉及文件：code/run.py（必要时 code/multi_factor_value.py）
> 依赖：无　|　建议优先级：第一批（最高优先）

## 1. 问题现状

用户双击 run.bat → 执行 run.py → 在整条数据管线跑完之后必然抛出 `ValueError`。入口脚本是坏的，系统对用户而言不可用。

## 2. 证据

- `code/multi_factor_value.py` L404：`return scored, selected` —— 返回**二元组**
- `code/run.py` L19：`all_data, selected, backtest = run_full_pipeline(top_n=30, backtest_days=60)` —— 按**三元组**解包
- Python 对二元组做三元解包必然抛 `ValueError: not enough values to unpack (expected 3, got 2)`
- 且崩溃发生在 run_full_pipeline 全部执行完之后——先白跑一次完整网络拉取，再炸

## 3. 为什么是错

1. 入口即入口：入口坏了 = 用户视角的"系统坏了"，其他模块再对也白搭
2. 附带浪费：崩溃前已完成 spot+yjbb×8+zcfz×4 的全部网络请求（东财限流环境下代价高昂）
3. 该 bug 的存在同时说明 run.py 从未被实际执行过一次（任何一次运行都会立刻暴露）——与"主流程从未在 G 盘运行"（S2 证据）互相印证

## 4. 修改要求

1. run.py L19 改为两元解包：
   ```python
   scored, selected = run_full_pipeline(top_n=30, backtest_days=60)
   ```
2. 若需要"回测"结果变量：按 C2 的修改要求，simple_backtest 将被删除、run_full_pipeline 的 with_backtest 参数同步移除——**不要**为保留第三个变量而改 run_full_pipeline 返回三元组（那会维持一个未来函数回测的接口）
3. 顺带：run.py 头部 banner（"启动多因子价值选股系统..."）与 multi_factor_value.py L386-387 的 banner 需按 M1 统一改叙事口径（"设计已审、有效性未验"）
4. run.py 内 `sys.path.insert` 保留；输出保存路径保持 `output/` 目录规范

## 5. 验收标准

- [ ] `D:/pyh/python.exe -E run.py` 不再抛 ValueError（因 C10 数据断供导致的网络异常属另一任务，不属于本项失败）
- [ ] 静态检查：`grep -n 'run_full_pipeline' code/run.py` 处解包变量数与 `multi_factor_value.py` 中 return 语句一致
- [ ] 回归：multi_factor_value.py 其余模块不受影响（run.py 改动不涉及因子逻辑）

## 6. 修改后需同步的文档

- 无（本项是纯 bug 修复）；但如按第 3 点改了 banner，同步 wiki/entities/system/multi-factor-v2.md 与 M1 任务清单
