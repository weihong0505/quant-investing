# C7 — walk_forward.py 名不副实：死参数、非 WF 回测、判定线无功效依据

> ✅ 已验收 2026-08-22 操作者: AI-C7（方案 B：改名 rolling_stats.py + 去伪判定）

> 来源：项目复盘 2026-08-22 第 C7 项（Wiki 全文：G:\quant-investing\wiki\comparisons\project-review-2026-08.md）
> 严重度：🟠 重大　|　任务性质：代码修复或改名　|　涉及文件：code/walk_forward.py、wiki/entities/system/walk-forward.md
> 依赖：无　|　建议优先级：第五批

## 1. 问题现状

模块自称"Walk-Forward 滚动回测、防过拟合验证（SOP §3.3-5 + v3 §3-5 一次确认制）"，实际实现是：对一条**已经算好的**月收益序列做滑动窗口描述统计。没有训练段选参、没有测试段重跑策略——不是 walk-forward。

## 2. 证据

- `code/walk_forward.py` L19：参数 `strategy_fn: Callable[[pd.Series], pd.Series] = None`，docstring（L28）写"在训练段上运行的函数（如选最优参数），返回应用到测试段的转换"——**函数体从头到尾从未调用 strategy_fn**（死参数）
- `walk_forward()` 函数体只做 `returns.iloc[start:start+train]` 切片的 `mean/shape/std/prod` 统计
- `walk_forward_verdict()`：判定线 `oos_win >= 0.5 and oos_cum > 0` 即"通过"——任意设定，无任何功效论证
- 项目自研实测结论（backtest_engineering_spec 审查）：**90 月回测功效不足**（3% 超额 T=90@TE10% 检出功效仅 20.3%）——比 90 月更短的滑动窗口（36m 训练）上做"50% 胜率"判定线，与项目自己的功效结论直接冲突
- `train_test_consistency` 算了但没进判定

## 3. 为什么是错

1. 名不副实的工具比没有工具更危险：用户/Wiki 认为"做了 walk-forward 防过拟合验证"，实际只是窗口描述统计
2. 判定线（50% 胜率、cum>0）在功效不足的样本上会给随机策略 ~40%+ 的"通过"概率，产出虚假安全感
3. 死参数说明函数从未按设计使用过——又一个"文档与实现两张皮"实例

## 4. 修改要求（二选一，用户拍板）

**方案 A——实现真 walk-forward：**
- `walk_forward(returns_or_data, strategy_fn, ...)`：每个窗口在训练段上**调用 strategy_fn 选参/训练**，在测试段上**用该参数重跑**，返回每窗 OOS 收益
- 判定不做"50% 胜率"硬线；改为报告：各窗 OOS 均值/夏普分布、训练-测试符号一致性、总 OOS 拼接净收益（含成本口径声明）；结论措辞按项目功效实测改为"证据强度"分级（强/弱/无），附置信区间
- 与 v3"最近 24m 样本外一次确认制"衔接：最后一窗为一次确认窗，`one_time_confirmation` 保持不变

**方案 B——改名 + 去伪判定：**
- 模块改名 `rolling_stats.py`（或函数改名 `rolling_window_stats`），docstring 如实写"滚动窗口描述统计（非 walk-forward）"
- 删除 `strategy_fn` 死参数；`walk_forward_verdict` 删除"通过/观察"判定措辞，只输出统计量；删除或降级"verdict"字段
- Wiki walk-forward 页同步改标题与内容（"Walk-Forward 滚动回测"→"滚动窗口统计"）

## 5. 验收标准

- [x] 所选方案落地；`strategy_fn` 要么被真实调用（A）要么被删除（B）
- [x] 无"verdict=通过"式无依据判定残留（A 的"证据强度分级"需附置信区间计算）
- [x] 冒烟测试更新并通过（方案 A 需含选参函数在训练段只被调用一次/每窗的断言）
- [x] 模块名/docstring/Wiki 页三者一致

## 6. 修改后需同步的文档

- wiki/entities/system/walk-forward.md（按方案改写）
- docs/SOP.md §3.3-5（如引用 walk-forward 验证方式，措辞与最终实现对齐）
