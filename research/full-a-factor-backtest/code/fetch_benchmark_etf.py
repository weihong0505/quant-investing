# -*- coding: utf-8 -*-
"""fetch_benchmark_etf.py — 取 510300/510500 ETF 的 **hfq** 总收益序列

⚠️ 为何不用项目自带的 data_fetcher.get_benchmark()：
   它用 `adjust='qfq'`（前复权）。v2.1 §3.6 明确「主基准 = 510300/510500 ETF **hfq**
   （含分红再投，真实可交易）」，并警告「价格指数为辅基准…防虚增超额 1.5~2.5%/年」。
   qfq 在除息日会向下调整、**不含分红再投**，直接拿它当基准会系统性低估基准、
   虚增超额。故本脚本独立取 hfq。

用法：D:/pyh/python.exe -E fetch_benchmark_etf.py
输出：data/engine/bench_{510300,510500}_hfq.parquet
"""
import os
import sys
import time

import pandas as pd

sys.path.insert(0, r'g:\股市探究\quant-investing\code')
sys.stdout.reconfigure(encoding='utf-8')
from data_fetcher import _throttle, _write_cache, _read_cache   # noqa: E402

OUT = r'g:\股市探究\fullA-检验与回测\data\engine'
START, END = '20160101', '20261009'


def main():
    import akshare as ak
    os.makedirs(OUT, exist_ok=True)
    for code in ['510300', '510500']:
        dst = os.path.join(OUT, f'bench_{code}_hfq.parquet')
        if os.path.exists(dst):
            d = pd.read_parquet(dst)
            print(f'  {code}: 已存在 {len(d)} 行 '
                  f'{str(d["date"].min())[:10]}~{str(d["date"].max())[:10]}')
            continue
        _throttle()
        try:
            d = ak.fund_etf_hist_em(symbol=code, period='daily',
                                    start_date=START, end_date=END, adjust='hfq')
        except Exception as e:
            print(f'  {code}: ✗ {type(e).__name__}: {str(e)[:100]}')
            continue
        if d is None or len(d) == 0:
            print(f'  {code}: ✗ 返回空')
            continue
        d = d.copy()
        d.columns = [str(c).strip() for c in d.columns]
        dc = next((c for c in d.columns if c in ('日期', 'date')), None)
        cc = next((c for c in d.columns if c in ('收盘', 'close')), None)
        if dc is None or cc is None:
            print(f'  {code}: ✗ 列名不含日期/收盘，实际列={list(d.columns)}')
            continue
        out = pd.DataFrame({'date': pd.to_datetime(d[dc]), 'close_hfq': pd.to_numeric(d[cc], errors='coerce')})
        out = out.dropna().sort_values('date').reset_index(drop=True)
        out.to_parquet(dst, index=False)
        print(f'  {code}: ✓ {len(out)} 行  {out.date.min().date()}~{out.date.max().date()}'
              f'  首 {out.close_hfq.iloc[0]:.4f} 末 {out.close_hfq.iloc[-1]:.4f}')
        time.sleep(0.6)
    return 0


if __name__ == '__main__':
    sys.exit(main())
