# -*- coding: utf-8 -*-
"""
build_engine_inputs.py — 为 backtest.BacktestEngine 构建输入宽表
===============================================================
引擎契约（读 backtest.py BacktestEngine.__init__ 确认）：
  calendar        : DatetimeIndex 交易日历
  prices_raw_open : DataFrame 行=交易日 列=code 值=不复权开盘价
  prices_raw_close: 同上，收盘价
  prices_hfq      : 同上，后复权收盘价（收益层）
  market_cap      : 总市值（滑点分档用；单位按引擎口径：亿元）
  tradable        : bool 停牌 False（涨跌停引擎自判）
  st_flags        : bool ST（5% 幅度）
  cash_div / share_ratio / list_dates / limit_free_dates : 可选

数据来源：
  raw OHLCV : quant.db daily_bars（本轮刚灌，5,219 只 / 10.26M 行）
  hfq close : data_cache hist_*_hfq_*.parquet
  股本       : 同缓存的 outstanding_share → mcap = raw_close × 流通股本 / 1e8（亿元）

⚠️ 本轮**明确跳过**并声明（避免静默缺失）：
  - st_flags   ：无历史 ST 生效日数据 → 全部 False（引擎会把涨跌幅按 10% 处理；
                 对含 ST 的样本会有偏差，报告须声明）
  - cash_div   ：分红已含在 hfq 收益层（引擎 §2.1 口径），raw 现金对账略过
  - share_ratio：送转已含在 hfq
  - list_dates ：不提供 → 引擎自动取首个有效收盘价为上市日（其 docstring 已说明）

用法：D:/pyh/python.exe -E build_engine_inputs.py
输出：data/engine/{raw_open,raw_close,hfq_close,mcap,tradable}.parquet
"""
import os
import sys
import glob
import time
import sqlite3

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
TASK = r'g:\股市探究\fullA-检验与回测'
OUT = os.path.join(TASK, 'data', 'engine')
CACHE = r'g:\股市探究\quant-investing\code\data_cache'
DB = r'g:\股市探究\quant-investing\data\quant.db'


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()

    # ---- 1) 从 daily_bars 读 raw（一次读全，10.26M 行）----
    print('  读 daily_bars ...')
    conn = sqlite3.connect(DB)
    df = pd.read_sql('SELECT code,date,open,close,volume FROM daily_bars', conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    print(f'    {len(df):,} 行 / {df.code.nunique():,} 只 / '
          f'{df.date.min().date()}~{df.date.max().date()}  ({time.time()-t0:.0f}s)')

    cal = pd.DatetimeIndex(sorted(df['date'].unique()))
    print(f'  交易日历 {len(cal)} 天')

    for nm, col in [('raw_open', 'open'), ('raw_close', 'close')]:
        w = df.pivot_table(index='date', columns='code', values=col, aggfunc='last')
        w = w.reindex(cal)
        p = os.path.join(OUT, f'{nm}.parquet')
        w.to_parquet(p)
        print(f'  {nm:11} {w.shape}  非空率 {w.notna().mean().mean():.1%}  '
              f'{os.path.getsize(p)/1e6:.0f} MB')

    # tradable：当日有成交且有收盘价
    df['ok'] = df['volume'].notna() & (df['volume'] > 0) & df['close'].notna() & (df['close'] > 0)
    tr = df.pivot_table(index='date', columns='code', values='ok', aggfunc='last')
    tr = tr.reindex(cal).fillna(False).astype(bool)
    p = os.path.join(OUT, 'tradable.parquet')
    tr.to_parquet(p)
    print(f'  tradable    {tr.shape}  可交易占比 {tr.values.mean():.1%}  '
          f'{os.path.getsize(p)/1e6:.0f} MB')

    # ---- 2) hfq close + 股本（从缓存）----
    print('  读 hfq/股本缓存 ...')
    files = [f for f in glob.glob(os.path.join(CACHE, 'hist_*_20160601_*_hfq_20261009.parquet'))]
    print(f'    {len(files)} 个 hfq 文件')
    recs, share = [], []
    for i, f in enumerate(files, 1):
        code = os.path.basename(f).split('_')[1]
        try:
            d = pd.read_parquet(f, columns=['date', 'close', 'outstanding_share'])
            if d is None or len(d) == 0:
                continue
            d = d.copy()
            d['code'] = code
            d['date'] = pd.to_datetime(d['date'])
            recs.append(d[['date', 'code', 'close']])
            share.append(d[['date', 'code', 'outstanding_share']])
        except Exception:
            continue
        if i % 1000 == 0:
            print(f'      {i}/{len(files)}  ({time.time()-t0:.0f}s)')
    h = pd.concat(recs, ignore_index=True)
    sh = pd.concat(share, ignore_index=True)
    print(f'    hfq {len(h):,} 行 | 股本 {len(sh):,} 行')

    wh = h.pivot_table(index='date', columns='code', values='close', aggfunc='last').reindex(cal)
    p = os.path.join(OUT, 'hfq_close.parquet')
    wh.to_parquet(p)
    print(f'  hfq_close   {wh.shape}  非空率 {wh.notna().mean().mean():.1%}  '
          f'{os.path.getsize(p)/1e6:.0f} MB')

    # ---- 3) 市值 = raw_close × 流通股本 / 1e8（亿元）----
    ws = sh.pivot_table(index='date', columns='code', values='outstanding_share', aggfunc='last')
    ws = ws.reindex(cal).ffill()
    rc = pd.read_parquet(os.path.join(OUT, 'raw_close.parquet'))
    mc = rc * ws.reindex_like(rc) / 1e8
    p = os.path.join(OUT, 'mcap.parquet')
    mc.to_parquet(p)
    print(f'  mcap        {mc.shape}  非空率 {mc.notna().mean().mean():.1%}  '
          f'中位 {np.nanmedian(mc.values):.1f} 亿  {os.path.getsize(p)/1e6:.0f} MB')

    print(f'\n✓ 引擎输入 → {OUT}  总耗时 {(time.time()-t0)/60:.1f} 分')
    print('  跳过项（须在报告声明）：st_flags(全 False，无历史 ST 生效日) / '
          'cash_div / share_ratio / list_dates')
    return 0


if __name__ == '__main__':
    sys.exit(main())
