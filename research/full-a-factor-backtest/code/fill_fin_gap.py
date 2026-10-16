# -*- coding: utf-8 -*-
"""
fill_fin_gap.py — 补齐 quarterly_fin 的报告期缺口
=================================================
问题：quant.db 的 quarterly_fin 缺 2022Q4~2024Q2 共 7 个报告期
      （实测 report_date 在 2022-09-30 → 2024-09-30 间有 731 天跳空），
      导致 TTM（需上年年报 + 上年同期）在 2024~2026 各期大面积算不出，
      EP 中位数被压到 0.41%（PE≈245 倍）的失真水平。

成因：update_db.py 的 quarterly_fin 是「从 yjbb 缓存全量刷新」，
      而 yjbb 缓存本身只有 37 个报告期（缺这 7 期）→ 缓存缺 → 库里也缺。

本脚本：
  1) 用 data_fetcher.get_financials / 直接抓东财 yjbb 补齐 7 期 → 写入 data_cache
  2) 调 update_db 自己的 quarterly_fin 刷新逻辑入库（不重写它）
  3) 校验：报告期数、各期行数、TTM 可算率

用法：D:/pyh/python.exe -E fill_fin_gap.py
"""
import os
import sys
import time
import sqlite3
import datetime as dt

import pandas as pd

BASE = r'g:\股市探究\quant-investing\code'
sys.path.insert(0, BASE)
sys.stdout.reconfigure(encoding='utf-8')

CACHE = os.path.join(BASE, 'data_cache')
DB = r'g:\股市探究\quant-investing\data\quant.db'
MISSING = ['20221231', '20230331', '20230630', '20230930', '20231231', '20240331', '20240630']


def fetch_one_period(p):
    """抓单个报告期的业绩报表（yjbb），落 data_cache/yjbb_<p>.parquet"""
    import akshare as ak
    from data_fetcher import _write_cache, _cache_path, retry_with_backoff
    target = _cache_path('yjbb', p, date_str=p)
    if os.path.exists(target):
        try:
            old = pd.read_parquet(target)
            if old is not None and len(old) > 0:
                print(f'  {p}: 已存在 {len(old)} 行，跳过')
                return 'cached', len(old)
        except Exception:
            pass
    try:
        df = retry_with_backoff(
            lambda: ak.stock_yjbb_em(date=p), n=3, base_wait=3.0, name=f'yjbb{p}')
        if df is None or len(df) == 0:
            print(f'  {p}: ✗ 返回空')
            return 'empty', 0
        _write_cache(df, target)
        print(f'  {p}: ✓ {len(df)} 行 → {os.path.basename(target)}')
        return 'ok', len(df)
    except Exception as e:
        print(f'  {p}: ✗ {type(e).__name__}: {str(e)[:100]}')
        return 'fail', 0


def main():
    print('=== 1. 抓取缺失报告期 ===')
    t0 = time.time()
    res = {}
    for p in MISSING:
        res[p] = fetch_one_period(p)
        time.sleep(1.0)
    ok_n = sum(1 for v in res.values() if v[0] in ('ok', 'cached'))
    print(f'  完成 {ok_n}/{len(MISSING)} 期，耗时 {time.time()-t0:.0f}s')
    if ok_n == 0:
        print('✗ 无新数据，终止'); return 1

    print('\n=== 2. 用 update_db 的刷新逻辑入库 ===')
    import update_db
    conn = sqlite3.connect(DB)
    before = conn.execute('SELECT COUNT(*), COUNT(DISTINCT report_date) FROM quarterly_fin').fetchone()
    print(f'  入库前: {before[0]:,} 行 / {before[1]} 个报告期')
    try:
        fn = getattr(update_db, 'refresh_quarterly_fin', None) or \
             getattr(update_db, 'update_quarterly_fin', None)
        if fn is None:
            print('  ⚠ 未找到刷新函数，改用 --tables fin 子进程')
            conn.close()
            import subprocess
            r = subprocess.run([r'D:\pyh\python.exe', '-E',
                                os.path.join(BASE, 'update_db.py'), '--tables', 'fin'],
                               capture_output=True, text=True, encoding='utf-8', errors='ignore')
            print('  ', (r.stdout or '')[-1500:])
            if r.returncode != 0:
                print('  stderr:', (r.stderr or '')[-600:])
        else:
            fn(conn)
            conn.commit()
            conn.close()
    except Exception as e:
        print(f'  ✗ 入库异常: {type(e).__name__}: {e}')
        try: conn.close()
        except Exception: pass

    print('\n=== 3. 校验 ===')
    conn = sqlite3.connect(DB)
    after = conn.execute('SELECT COUNT(*), COUNT(DISTINCT report_date) FROM quarterly_fin').fetchone()
    print(f'  入库后: {after[0]:,} 行 / {after[1]} 个报告期  (前 {before[0]:,} / {before[1]})')
    d = pd.read_sql('SELECT report_date, COUNT(*) n FROM quarterly_fin GROUP BY report_date ORDER BY report_date', conn)
    d['rd'] = pd.to_datetime(d.report_date)
    gaps = d[d.rd.diff().dt.days > 100]
    if len(gaps):
        print('  ⚠ 仍有跳空:')
        print(gaps[['report_date', 'n']].to_string(index=False))
    else:
        print('  ✓ 报告期连续，无 >100 天跳空')
    print('\n  最近 10 期:')
    print(d.tail(10)[['report_date', 'n']].to_string(index=False))
    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
