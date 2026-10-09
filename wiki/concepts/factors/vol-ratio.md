---
title: VOL_RATIO因子 — 量比
created: 2026-08-21
updated: 2026-08-25
type: concept
tags: [factor, sentiment, volume]
sources: [multi_factor_value.py]
confidence: 35
contested: true
---

# VOL_RATIO因子 — 量比 (Volume Ratio)

## 定义
VOL_RATIO = 当日成交量 / 过去5日平均成交量，反映短期交易情绪的变化。

## 计算公式
```python
VOL_RATIO = pd.to_numeric(df.get('量比'), errors='coerce')
```
- 数据来源：akshare `stock_zh_a_spot_em`
- 量比 > 1：今日成交放量；量比 < 1：今日成交缩量

## 当前配置
| 项目 | 值 |
|------|-----|
| 权重 | **已弃用**（2026-08-22，0.05 并入 TURNOVER，现 0.15） |
| 方向 | **已弃用**（原 +1，M5 试点符号不显著，registry #14 淘汰·初步） |
| 处理 | 全市场 winsorize ±3σ → z-score |
| 中性化 | 否 |

## 经济逻辑
- 放量上涨 = 资金入场，可能有持续性
- 但量比是**日频快变量**，噪音很大
- 作为情绪辅助因子，权重最低

## 已知问题
- **日频噪音极大**：单日量比受突发消息影响，信号不稳定
- 方向设定为 +1（放量偏好），但放量也可能是放量下跌——需配合价格方向
- 与 [[turnover-factor]] 正相关
- **已弃用（2026-08-22）**：东财 spot 盘中量比不可复现（data_caliber_audit.md）；主策略已移除（multi_factor_value.py L59），权重并入 [[turnover-factor]]（0.05→0.15）；registry #14 试点 signed \|t\|=0.99 不显著 → 淘汰（初步，样本 <60 月）

## 待决事项（contested）

- **方向未验证**：量比方向 +1（放量偏好）来自文献先验，放量上涨 vs 放量下跌的判别力从未在 A 股 2017+ 样本上检验（复盘 M5/S1）；"是否保留"的评估无检验证据支撑。——⚠️ 本句已过时：2026-08-22 已完成检验，结论见下条。
- **✅ 2026-08-22 检验回填（初步，样本 2023-03~2026-08，<60 月，报告 [[test_VOL_RATIO_20260822]]）**：v3 全流程判定**淘汰**——ICIR=-0.169<0.3；下跌月条件 IC=-0.0158<0（硬指标）；多空 signed NW-t=-1.28<2.0；PT MR 单调性未达线；样本外 24m 确认失败（OOS mean IC 与预登记方向相反）；净多空年化 -21.0%（<4%）。处置（权重归零/并入 TURNOVER）待用户拍板——代码已将 VOL_RATIO 弃用并入 TURNOVER（见 [[factor-direction-map]] 备注）。
- **指向任务**：复盘 S1（因子零检验：VOL_RATIO 补检，含方向判别力）→ M5（符号本地验证）。检验结果回填本页并决定去留。

## 相关页面
- [[turnover-factor]] — 同属流动性/情绪类
- [[momentum-60d]] — 量价配合分析
- [[factor-direction-map]] — 权重与方向一览

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-21 | 初始化，权重0.05 | v2策略MImo审查后定稿 |
| 2026-08-22 | 检验回填：v3 全流程判定淘汰（初步，<60月）；处置待拍板 | 复盘 S1 执行（docs/factor_docs/test_VOL_RATIO_20260822.md） |
