---
title: 文件整理代理
created: 2026-08-22
updated: 2026-08-25
type: entity
tags: [system, tool]
sources: [file_organizer.py, file_organizer_watch.py, FILE-MANAGEMENT-STANDARD.md]
confidence: 80
---

# 文件整理代理

## 概述
依据 `FILE-MANAGEMENT-STANDARD.md` 规范自动归类文件的代理。融合**规则引擎 + 本地AI**双通道分类。

## 只处理两个来源
| 来源 | 目录 | 说明 |
|------|------|------|
| 用户文件 | `G:\股市探究\quant-investing\_inbox\` | 用户放入即自动整理 |
| Hermes 产出 | `G:\股市探究\quant-investing\_hermes_out\` | Hermes 生成的文件放此处 |

不做全库扫描，不擅动已归位文件。

## 分类流程
```
文件进入 _inbox/ 或 _hermes_out/
    ↓
规则引擎（扩展名+命名模式）→ 90%直接归位
    ↓ 无法判定
本地 AI (Qwen2.5-7B) 按规范决策树分类
    ↓ 仍无法判定
跳过，留给人工（不猜）
```

## 归位规则（映射自 FILE-MANAGEMENT-STANDARD.md §2.3）
| 文件类型 | 归宿 |
|----------|------|
| .py / .bat | code/ |
| .parquet | data/cache/ |
| pick_*.csv | output/picks/ |
| 其他 .csv / .html | output/ |
| factor_*_v*.md / spec / methodology | docs/factor_docs/ |
| 其他 .md | docs/research/ |
| .txt 文章 | wiki/raw/articles/ |
| .pdf | wiki/raw/papers/ |
| .png/.jpg | wiki/raw/assets/ |
| .gguf/.bin | ai/models/ |
| 0字节/临时 | 删除 |

## 自动机制
| 层 | 机制 | 间隔 |
|----|------|------|
| 实时 | `file_organizer_watch.py` 守护进程 | 5秒 |
| 兜底 | Hermes cron 任务 | 30分钟 |

## 日志
每次整理自动追加 `wiki/log.md`，操作者标识为 `AI (文件整理代理)`。

## 已知注意点
- 运行需 `PYTHONIOENCODING=utf-8`（Windows GBK 控制台）
- 守护进程输出被缓冲属正常（管道重定向时）
- Obsidian 离线时日志本地追加，恢复后 API 写入

## 相关页面
- [[sop-v1.1]] — SOP §9 文件整理代理
- [[local-ai]] — 本地 AI 分类引擎
- [[multi-factor-v2]] — 主策略（产出文件经 _hermes_out 整理）

## 变更历史
| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-08-22 | 初始化 | 依据 FILE-MANAGEMENT-STANDARD.md 搭建自动整理代理 |
