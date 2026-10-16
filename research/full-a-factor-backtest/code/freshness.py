# -*- coding: utf-8 -*-
"""freshness.py — 数据新鲜度体检：逐源回答「够不够新」

用法：D:/pyh/python.exe -E freshness.py
"""
import os
import sys
import sqlite3
import datetime as dt

sys.path.insert(0, r'g:\股市探究\quant-investing\code')
sys.stdout.reconfigure(encoding='utf-8')
DB = r'g:\股市探究\quant-investing\data\quant.db'
CACHE = r'g:\股市探究\quant-investing\code\data_cache'
TODAY = dt.date.today()


def main():
    print(f'体检时点: {TODAY} {dt.datetime.now().strftime("%H:%M")}（今日尚未开盘，最近收盘=10-08）\n')
    c = sqlite3.connect(DB)

    print('=== 库内各源最新数据点 ===')
    q = [
        ('quarterly_fin.report_date', 'SELECT MAX(report_date) FROM quarterly_fin',
         '定期报告；2026Q3 法定截止 10-31，尚未到'),
        ('quarterly_fin.notice_date', 'SELECT MAX(notice_date) FROM quarterly_fin',
         '注意：此列是"最新修订日"非首次披露日'),
        ('stock_master.updated_at', 'SELECT MAX(updated_at) FROM stock_master', '可交易池刷新时点'),
        ('mcap_snapshot.date', 'SELECT MAX(date) FROM mcap_snapshot', '市值快照'),
        ('valuation_daily.date', 'SELECT MAX(date) FROM valuation_daily', 'PE/PB 历史'),
        ('dividends.ex_date', 'SELECT MAX(ex_date) FROM dividends', '分红'),
    ]
    for name, sql, note in q:
        try:
            v = c.execute(sql).fetchone()[0]
            print(f'  {name:28} {str(v):12}  {note}')
        except Exception as e:
            print(f'  {name:28} ERR {str(e)[:50]}')

    print('\n=== 日线缓存最新交易日 ===')
    import glob
    import pandas as pd
    fs = glob.glob(os.path.join(CACHE, 'hist_*_20260601_*_hfq_*.parquet'))
    latest = {}
    for f in fs[:400]:
        try:
            d = pd.read_parquet(f, columns=['date'])
            mx = str(d['date'].max())[:10]
            latest[mx] = latest.get(mx, 0) + 1
        except Exception:
            pass
    for k in sorted(latest, reverse=True)[:4]:
        print(f'  末交易日 {k}: {latest[k]} 只（抽样 {min(400,len(fs))} 只）')

    print('\n=== 隐患①：可交易池是否漏了新上市 ===')
    have = {str(r[0]).zfill(6) for r in c.execute('SELECT code FROM stock_master')}
    print(f'  stock_master {len(have)} 只，更新于 {c.execute("SELECT MAX(updated_at) FROM stock_master").fetchone()[0]}')
    try:
        from data_fetcher import get_full_stock_pool
        pool = get_full_stock_pool()
        col = next((x for x in ('code', '代码', '股票代码', '证券代码') if x in pool.columns), None)
        if col:
            now = {str(x).zfill(6) for x in pool[col].dropna()}
            new = sorted(now - have)
            gone = sorted(have - now)
            print(f'  实时全池 {len(now)} 只')
            print(f'  **库内缺失（应新上市/新纳入）: {len(new)} 只**')
            if new:
                print(f'    {new[:25]}')
            print(f'  库内多出（应已退市/剔除）: {len(gone)} 只')
            if gone:
                print(f'    {gone[:25]}')
    except Exception as e:
        print(f'  实时池获取失败: {type(e).__name__}: {str(e)[:90]}')

    print('\n=== 隐患②：valuation_daily 覆盖 ===')
    r = c.execute('SELECT MIN(date), MAX(date), COUNT(*), COUNT(DISTINCT code) FROM valuation_daily').fetchone()
    print(f'  {r[0]} ~ {r[1]}  {r[2]:,} 行 / **仅 {r[3]} 只股票**')
    print(f'  → PE_PCTL / PB_PCTL 需要全 A 估值历史，此表**撑不起**（缺 {5563-r[3]} 只）')

    print('\n=== 隐患③：dividends 覆盖 ===')
    r = c.execute('SELECT COUNT(*), COUNT(DISTINCT code), MAX(ex_date) FROM dividends').fetchone()
    print(f'  {r[0]} 行 / 仅 {r[1]} 只 / 最新除权除息日 {r[2]}')
    print(f'  → DY 股息率因子**撑不起**')

    print('\n=== 隐患④：daily_bars ===')
    print(f'  {c.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0]} 行（空表）')
    print('  → 真实回测/P5 需要它；本轮抓的日线在 data_cache，尚未灌库')
    c.close()


if __name__ == '__main__':
    main()
