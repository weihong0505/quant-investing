# 初筛管线使用说明 (1万元价值投资)

> 固化版 v1.0 | 2026-08-29 | 演示级工具，非投资建议

## 快速开始

**方式一：双击**（推荐）
```
code\run_screen.bat
```

**方式二：命令行**（可选参数）
```bash
cd G:\股市探究\quant-investing\code
D:\pyh\python.exe -X utf8 -E run_screen.py                # 严格模式
D:\pyh\python.exe -X utf8 -E run_screen.py --top 5        # 只看前5
D:\pyh\python.exe -X utf8 -E run_screen.py --min-mcap 30  # 市值阈值30亿
D:\pyh\python.exe -X utf8 -E run_screen.py --no-save      # 不落盘只打印
```

## 输出

| 文件 | 内容 |
|------|------|
| `output/screen_{日期}.csv` | 候选清单（utf-8-sig，Excel直接打开） |
| `output/screen_{日期}.json` | 各阶段过滤统计（合并/ST/基础/市值/分位） |

## 管线逻辑（5道过滤）

```
① 合并财务+行情   yjbb(最新期) + zcfz(负债率) + spot(价格/PE/PB)
② ST/退市剔除     前缀匹配 ST/*ST/S*ST/退 (两源一致性验证过)
③ 基础过滤        主板(60/00) + 股价5~30元 + EPS>0 + ROE≥8% + CFPS>0 + LEV<70% + PE<15
④ 市值≥50亿       腾讯qt实时市值 (当日缓存, 覆盖率100%实测)
⑤ 估值分位<50%    PE/PB在自身历史(2018起滚动窗口)的下半区
```

## 使用频率建议

- **每月1次**（或市场大跌后）：跑一次看是否有新候选
- 行情缓存（spot）超过7天会提示过期——结果仅供参考演示
- 财务数据（yjbb）季度更新一次即可（财报季4/8/10月后）

## 数据依赖

| 数据 | 来源 | 缓存 | 刷新频率 |
|------|------|------|---------|
| spot行情 | 新浪(缓存) | data_cache/spot_*.parquet | 每日 |
| 财务yjbb | 东财datacenter | data_cache/yjbb_*.parquet | 每季度 |
| 负债zcfz | 东财datacenter | data_cache/zcfz_*.parquet | 每季度 |
| 市值 | 腾讯qt | data_cache/mcap_*.parquet | 每日(自动) |
| 估值历史 | 东财RPT_VALUEANALYSIS_DET | data_cache/valhist_*.parquet | 首次后缓存 |

## 重要限制（诚实声明）

1. **因子未经统计检验**（P4待跑）：初筛结果只能当线索，必须人工复核5问（见 docs/trading/1万元价值投资执行手册.md）
2. **spot缓存可能是旧数据**：运行时的过期警告要认真对待
3. **退市股估值历史缺失**（幸存者偏差）：历史分位可能偏乐观
4. **严格模式下可能长期0候选**：这是正常的，空仓等待是价值投资纪律
5. **演示级工具**：任何输出都不构成投资建议，决策权在用户

## 模块结构

```
code/
├── run_screen.py            # 主入口 (固化版)
├── run_screen.bat           # 双击启动器
├── screening/
│   ├── st_filter.py         # ST/退市过滤
│   ├── mcap_filter.py       # 市值过滤 (腾讯qt)
│   └── valuation_percentile.py  # 估值分位
└── output/                  # 结果输出
```

## 验证记录

- ST过滤：spot剔206只/两源一致性0冲突/合成用例9-9
- 市值过滤：覆盖率100%（200/200）、缓存二次0.01s
- 估值分位：600595手算对照0.0000pp、负PE/短窗口规则验证
- 全链路：1587→1532(ST)→7(基础)→6(市值)→0(分位) 实测
