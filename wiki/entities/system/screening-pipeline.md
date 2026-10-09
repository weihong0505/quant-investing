---
title: 初筛管线（screening）
created: 2026-08-29
updated: 2026-09-13
type: entity
tags: [pipeline, system, value]
sources: [code/screening/README.md, code/run_screen.py, docs/factor_docs/screen_st_report.md, docs/factor_docs/screen_mcap_report.md, docs/factor_docs/screen_pctl_report.md]
confidence: 80
---

# 初筛管线（screening）

## 概述

面向「1 万元价值投资」的初筛工具链（固化版 v1.0，2026-08-29）。**演示级，非投资建议**；因子 P4 统计检验未跑，结果只能当线索。

入口：`code/run_screen.py` / `run_screen.bat`  
模块：`code/screening/{st_filter,mcap_filter,valuation_percentile}.py`  
输出：`output/screen_{YYYYMMDD}.csv` + `.json`（阶段统计）

## 五道过滤

| 步 | 规则 | 实测链路（2026-08-29 演示） |
|---|---|---|
| ① 合并 | yjbb + zcfz + spot | 1587 |
| ② ST/退市 | 前缀 ST/*ST/S*ST/退，两源一致性 0 冲突 | →1532 |
| ③ 基础 | 主板 60/00、价 5–30、EPS>0、ROE≥8%、CFPS>0、LEV<70%、PE<15 | →7 |
| ④ 市值 | ≥50 亿（腾讯 qt，覆盖率 100%） | →6 |
| ⑤ 估值分位 | PE_PCTL **且** PB_PCTL 均 <50（严格 AND） | →0 |

**0 候选是纪律结果**，不是故障：周期股常呈低 PE + 高 PB，严格 AND 会剔掉单边“假便宜”。

## 估值分位要点

- 窗口：2018-01-02 起累积滚动；交易日与有效观测均 ≥250 才出分位
- 负 PE/PB 剔除；当前值无效 → NaN + `missing` 标注（不静默丢弃）
- 口径：`100 * mean(hist < cur)`（ECDF 下侧）；手算对照 600595 差 0.0000 pp
- 严格 AND 的典型：600595 PE 分位 2.9（极便宜）但 PB 64.9（偏贵）→ 剔除

## 诚实限制

1. 因子未经统计检验（P4 待跑）
2. spot 缓存过期要认真对待
3. 退市股估值历史缺失 → 分位可能偏乐观（幸存者偏差）
4. 严格模式可长期 0 候选 → 空仓等待符合价值投资纪律
5. 输出不构成投资建议

## 验证记录

- ST：spot 剔 206；两源 0 冲突；合成 9/9
- 市值：覆盖率 100%（200/200）；缓存二次 0.01s
- 分位：手算 0.0000 pp；负 PE / 短窗口 / 严格 AND 合成规则 PASS
- 全链路：1587→1532→7→6→0 实测

## 相关页面

- [[quant-db]] — 本地库（管道在建，内容仍缺估值/分红/FCF 全市场）
- [[multi-factor-v2]] — 完整价值投资管线（非本初筛）
- [[pe-pctl]] / [[pb-pctl]] — 分位因子设计页
- `docs/factor_docs/value_investing_transition_v2.1.md` — 设计依据（非 Wiki 页，路径引用）
