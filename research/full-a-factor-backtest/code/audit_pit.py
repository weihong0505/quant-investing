# -*- coding: utf-8 -*-
"""
audit_pit.py — quarterly_fin 的 PIT（公告日）质量审计
=====================================================
背景：quant.db 的 quarterly_fin 有 (report_date, notice_date) 两列，
      但抽样发现 2015-09-30 报告期出现 notice_date=2018-08-31 / 2017-10-21。
      yjbb 的「最新公告日期」在业绩报表语境下可能是**修订日**而非**首次披露日**。
      若把修订日当首次披露日，检验会在 T 时刻用上"未来才修正过的"财务数据，
      产生前视偏差（look-ahead bias）→ IC 虚高。这正是本库最忌讳的 M 类错误。

判定依据（可对账）：
  A股定期报告法定披露截止日：Q1 → 4/30；半年报 → 8/31；Q3 → 10/31；年报 → 次年 4/30。
  若 notice_date 落在法定窗口内，视为「像首次披露」；远超窗口 → 疑为修订日。

用法：D:/pyh/python.exe -E audit_pit.py
输出：output/pit_audit.md + output/pit_lag_dist.csv
"""
import os
import sys
import sqlite3
import datetime as dt

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
DB = r'g:\股市探究\quant-investing\data\quant.db'
OUT = r'g:\股市探究\fullA-检验与回测\output'
os.makedirs(OUT, exist_ok=True)

# 法定披露截止日（月, 日）相对于报告期的偏移
DEADLINE = {3: (4, 30), 6: (8, 31), 9: (10, 31), 12: (4, 30)}  # 12月=次年4/30


def deadline_of(report_date):
    y, m, d = report_date.year, report_date.month, report_date.day
    mm, dd = DEADLINE[m]
    yy = y + 1 if (m == 12 and mm == 4) else y
    return dt.date(yy, mm, dd)


def main():
    conn = sqlite3.connect(DB)
    df = pd.read_sql(
        'SELECT code, report_date, notice_date, eps, bps, roe, cfps, gpm, lev '
        'FROM quarterly_fin', conn)
    conn.close()
    print(f'总行数 {len(df):,} | 股票 {df.code.nunique():,}')

    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    df['notice_date'] = pd.to_datetime(df['notice_date'], errors='coerce')

    n = len(df)
    miss_rep = df['report_date'].isna().sum()
    miss_not = df['notice_date'].isna().sum()
    print(f'report_date 缺失 {miss_rep:,} | notice_date 缺失 {miss_not:,}({miss_not/n:.1%})')

    # 1) 结构合法性：notice 必须晚于 report
    bad_order = df[df['notice_date'] < df['report_date']]
    print(f'notice_date 早于 report_date（逻辑非法）: {len(bad_order):,}')

    # 2) 与实际法定截止日的偏离（负=提前，正=逾期）
    ok = df.dropna(subset=['report_date', 'notice_date']).copy()
    ok['deadline'] = ok['report_date'].apply(deadline_of)
    ok['lag_days'] = (ok['notice_date'] - ok['report_date']).dt.days
    ok['over_days'] = (ok['notice_date'] - pd.to_datetime(ok['deadline'])).dt.days

    print('\n--- report→notice 间隔（天）分位 ---')
    print(ok['lag_days'].describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).to_string())

    print('\n--- 超过法定截止日的天数（over_days）分位 ---')
    print(ok['over_days'].describe(percentiles=[.5, .75, .9, .95, .99]).to_string())

    # 3) 分类
    ontime = (ok['over_days'] <= 0).sum()
    late_30 = ((ok['over_days'] > 0) & (ok['over_days'] <= 30)).sum()
    late_1y = ((ok['over_days'] > 30) & (ok['over_days'] <= 365)).sum()
    late_1y_ = (ok['over_days'] > 365).sum()
    print(f'\n按时（≤截止日）      : {ontime:,} ({ontime/len(ok):.1%})')
    print(f'逾期 1~30 天          : {late_30:,} ({late_30/len(ok):.1%})')
    print(f'逾期 31~365 天        : {late_1y:,} ({late_1y/len(ok):.1%})')
    print(f'逾期 >365 天（可疑）  : {late_1y_:,} ({late_1y_/len(ok):.1%})')

    # 4) 致命检验：同一 (code, report_date) 是否有多条不同 notice_date
    dup = ok.groupby(['code', 'report_date'])['notice_date'].nunique()
    print(f'\n同一 (code, report_date) 出现多个不同 notice_date: {(dup > 1).sum():,} 组')

    # 5) 极端样本
    print('\n--- 逾期最久的 10 条 ---')
    worst = ok.nlargest(10, 'over_days')[['code', 'report_date', 'notice_date', 'lag_days', 'over_days']]
    print(worst.to_string(index=False))

    # 6) 关键结论：每个报告期的 notice_date 中位数（看是否稳定落在披露窗口）
    print('\n--- 各报告期 notice_date 相对截止日的逾期天数中位数 ---')
    by_rep = ok.groupby(ok['report_date'].dt.to_period('Q'))['over_days'].agg(['median', 'count'])
    print(by_rep.tail(12).to_string())

    # 落盘
    ok[['code', 'report_date', 'notice_date', 'lag_days', 'over_days']].to_csv(
        os.path.join(OUT, 'pit_lag_dist.csv'), index=False, encoding='utf-8-sig')

    verdict = []
    verdict.append(f'| 指标 | 值 |')
    verdict.append(f'|---|---|')
    verdict.append(f'| 总行数 | {n:,} |')
    verdict.append(f'| notice_date 缺失 | {miss_not:,} ({miss_not/n:.1%}) |')
    verdict.append(f'| notice 早于 report（非法） | {len(bad_order):,} |')
    verdict.append(f'| 按时披露（≤法定截止日） | {ontime:,} ({ontime/len(ok):.1%}) |')
    verdict.append(f'| 逾期 >365 天（疑为修订日） | {late_1y_:,} ({late_1y_/len(ok):.1%}) |')
    verdict.append(f'| 同 (code,report) 多 notice_date | {(dup>1).sum():,} 组 |')
    with open(os.path.join(OUT, 'pit_audit.md'), 'w', encoding='utf-8') as f:
        f.write('# quarterly_fin 的 PIT 质量审计\n\n')
        f.write('\n'.join(verdict) + '\n\n')
        f.write('## 逾期最久的 10 条\n\n```\n')
        f.write(worst.to_string(index=False))
        f.write('\n```\n\n## 各报告期逾期天数中位数（末 12 期）\n\n```\n')
        f.write(by_rep.tail(12).to_string())
        f.write('\n```\n')
    print(f'\n报告 → {os.path.join(OUT, "pit_audit.md")}')
    print(f'明细 → {os.path.join(OUT, "pit_lag_dist.csv")}')


if __name__ == '__main__':
    main()
