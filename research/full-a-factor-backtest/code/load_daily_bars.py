# -*- coding: utf-8 -*-
"""
load_daily_bars.py — 把 data_cache 的日线灌入 quant.db 的 daily_bars
====================================================================
口径决策（有依据，非默认）：
  - daily_bars 只存 **raw（不复权）**：
      init_db.py 表注明「日线行情 (OHLCV, raw)」；
      backtest_engineering_spec_v2.1 §2.1「执行/估值/成本层用 raw」。
      hfq 由回测脚本直接从 data_cache 装宽表（避免库里存双份 2.34 GB）。
  - 实测规模：12.75M 行 / 91.9 B/行 → **1.17 GB**（含索引）。

可中断续跑：以 data/loader_ledger.jsonl 记录每只的完成状态；
重跑时跳过已入库的代码（按 daily_bars 内已有 code 判断，最可靠）。

用法：
  D:/pyh/python.exe -E load_daily_bars.py              # 全量
  D:/pyh/python.exe -E load_daily_bars.py --limit 50   # 冒烟
  D:/pyh/python.exe -E load_daily_bars.py --rebuild    # 先清空再灌
"""
import os
import re
import sys
import glob
import time
import sqlite3
import argparse
import datetime

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
CACHE = r'g:\股市探究\quant-investing\code\data_cache'
DB = r'g:\股市探究\quant-investing\data\quant.db'
LEDGER = r'g:\股市探究\fullA-检验与回测\data\loader_ledger.jsonl'
COLS = ['code', 'date', 'open', 'high', 'low', 'close', 'volume']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--rebuild', action='store_true')
    ap.add_argument('--batch', type=int, default=200, help='每多少只提交一次')
    a = ap.parse_args()

    # ⚠️ 2026-10-11 修正（独立审查 D1，数据完整性风险）：
    # 原实现是**黑名单**：`if '_hfq_' not in name` —— 只能挡 hfq，**挡不住 qfq**。
    # 实测 `hist_600000_20160601_20261009_qfq_20261009.parquet` 会通过旧筛选被灌进 daily_bars
    # （前复权价混入 raw 表，且表内**没有 provenance 列**，事后无法分辨）。
    # 现改为**白名单**（默认拒绝任何带调整标记或未来新增命名变体）：
    #   raw 命名 = hist_{6位代码}_{起始日}_{结束日}_{抓取日}.parquet（无 adjust 段）
    RAW_PAT = re.compile(r'^hist_\d{6}_20160601_\d{8}_\d{8}\.parquet$')
    _all = sorted(glob.glob(os.path.join(CACHE, 'hist_*_20160601_*_20261009.parquet')))
    files = [f for f in _all if RAW_PAT.match(os.path.basename(f))]
    _skipped = [os.path.basename(f) for f in _all if f not in files]
    print(f'  候选取 raw 缓存文件: {len(files)} 个（白名单）｜排除 {len(_skipped)} 个（复权/其它变体）')
    if _skipped:
        print(f'    排除样例: {_skipped[:3]}')
    _bad = [n for n in _skipped if '_hfq_' not in n and '_qfq_' not in n]
    if _bad:
        # 出现了"既不是 hfq 也不是 qfq"的命名变体 → 必须人工确认，不能静默忽略
        print(f'  ⚠️ 发现未经确认的命名变体 {len(_bad)} 个（已按白名单排除，请人工确认口径）: {_bad[:5]}')
    if not files:
        print('✗ 无输入'); return 1

    conn = sqlite3.connect(DB)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    if a.rebuild:
        print('  --rebuild: 清空 daily_bars')
        conn.execute('DELETE FROM daily_bars')
        conn.commit()
    done = {r[0] for r in conn.execute('SELECT DISTINCT code FROM daily_bars')}
    print(f'  库内已有 {len(done):,} 只')

    todo = []
    for f in files:
        code = os.path.basename(f).split('_')[1]
        if code not in done:
            todo.append((code, f))
    if a.limit:
        todo = todo[:a.limit]
    print(f'  本次待灌 {len(todo):,} 只')

    before = conn.execute('SELECT COUNT(*) FROM daily_bars').fetchone()[0]
    t0 = time.time()
    ins = ok = fail = 0
    buf = []
    log = open(LEDGER, 'a', encoding='utf-8')

    for i, (code, path) in enumerate(todo, 1):
        try:
            d = pd.read_parquet(path, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            if d is None or len(d) == 0:
                fail += 1
                log.write(f'{{"code":"{code}","status":"empty"}}\n')
                continue
            d = d.copy()
            d.insert(0, 'code', code)
            d['date'] = pd.to_datetime(d['date']).dt.strftime('%Y-%m-%d')
            buf.extend(d[COLS].itertuples(index=False, name=None))
            ok += 1
        except Exception as e:
            fail += 1
            log.write(f'{{"code":"{code}","status":"fail","err":"{type(e).__name__}:{str(e)[:80]}"}}\n')

        if len(buf) >= 200_000 or i == len(todo):
            conn.executemany(f'INSERT INTO daily_bars ({",".join(COLS)}) VALUES (?,?,?,?,?,?,?)', buf)
            conn.commit()
            ins += len(buf)
            buf = []
        if i % a.batch == 0 or i == len(todo):
            el = time.time() - t0
            rate = i / el if el else 0
            eta = (len(todo) - i) / rate / 60 if rate else 0
            print(f'    {i}/{len(todo)}  入库 {ins:,} 行  fail={fail}  '
                  f'| {rate:.1f} 只/秒 | 剩余约 {eta:.1f} 分')

    # 索引（首次建）
    have_idx = {r[1] for r in conn.execute('PRAGMA index_list(daily_bars)')}
    if not have_idx:
        print('  建索引 idx_bars(code,date) ...')
        conn.execute('CREATE INDEX idx_bars ON daily_bars(code, date)')
        conn.commit()
    after = conn.execute('SELECT COUNT(*) FROM daily_bars').fetchone()[0]
    ncode = conn.execute('SELECT COUNT(DISTINCT code) FROM daily_bars').fetchone()[0]
    dmin, dmax = conn.execute('SELECT MIN(date), MAX(date) FROM daily_bars').fetchone()
    conn.execute(
        'INSERT INTO meta_updates (table_name, action, rows_before, rows_after, source, status, message, ts) '
        'VALUES (?,?,?,?,?,?,?,?)',
        ('daily_bars', 'FULL', before, after, 'data_cache hist_* raw', 'OK',
         f'codes={ncode} range={dmin}~{dmax} fail={fail}', datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    log.close()

    print(f'\n=== 完成 ===')
    print(f'  行数 {before:,} → {after:,}（+{after-before:,}）')
    print(f'  股票 {ncode:,} 只 | 日期 {dmin} ~ {dmax}')
    print(f'  失败 {fail} 只 | 耗时 {(time.time()-t0)/60:.1f} 分')
    print(f'  库体积 {os.path.getsize(DB)/1e9:.2f} GB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
