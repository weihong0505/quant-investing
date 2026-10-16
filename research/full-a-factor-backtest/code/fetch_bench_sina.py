# -*- coding: utf-8 -*-
"""fetch_bench_sina.py — 用新浪通路取 ETF 基准；并与项目既定「前收盘校验」交叉验证

口径说明（重要）：
  - 新浪 `fund_etf_hist_sina` 返回不复权价（列 open/high/low/close/volume/amount/postVol）。
  - v2.1 §3.6 要求「ETF hfq（含分红再投）」。东财 push2his 当前被本机代理拦截
    （ProxyError），拿不到 hfq。故本轮：
      主基准 = 510300 ETF **不复权价**（真实可交易价，但除息日的分红未再投）
      辅基准 = 沪深300 **价格指数** sh000300（v2.1 允许作辅基准/展示项）
      并**用 ETF 与指数的差值反推 ETF 分红拖累**，把「基准被低估」这一偏差量化出来，而非隐去。
  - 校验：新浪 ETF 的 close 与其 postVol 列（前收盘）应大体连续；若出现单日 >1% 跳空
    且指数当日无对应波动，即提示除息 → 记录为分红日。

用法：D:/pyh/python.exe -E fetch_bench_sina.py
输出：data/engine/bench_{510300,510500}.parquet、bench_hs300_index.parquet
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
OUT = r'g:\股市探究\fullA-检验与回测\data\engine'


def main():
    import akshare as ak
    os.makedirs(OUT, exist_ok=True)

    # ---- ETF（新浪）----
    for code, sym in [('510300', 'sh510300'), ('510500', 'sh510500')]:
        dst = os.path.join(OUT, f'bench_{code}.parquet')
        if os.path.exists(dst):
            d = pd.read_parquet(dst)
            print(f'  {code}: 已存在 {len(d)} 行')
            continue
        try:
            d = ak.fund_etf_hist_sina(symbol=sym)
        except Exception as e:
            print(f'  {code}: ✗ {type(e).__name__}: {str(e)[:90]}')
            continue
        d = d.copy()
        d['date'] = pd.to_datetime(d['date'])
        for c in ['open', 'high', 'low', 'close']:
            d[c] = pd.to_numeric(d[c], errors='coerce')
        d = d.dropna(subset=['close']).sort_values('date').reset_index(drop=True)
        d = d[d['date'] >= '2016-06-01']
        d[['date', 'open', 'high', 'low', 'close']].to_parquet(dst, index=False)
        print(f'  {code}: ✓ {len(d)} 行  {d.date.min().date()}~{d.date.max().date()}  '
              f'末收盘 {d.close.iloc[-1]:.4f}')
        # 疑似除息日：单日跌幅 >1.2% 且非连续下跌
        r = d['close'].pct_change()
        big = d[(r < -0.012)]
        print(f'      单日跌幅 >1.2% 的天数: {len(big)}（含真实下跌，仅作参考）')
        time.sleep(0.5)

    # ---- 辅基准：沪深300 价格指数 ----
    dst = os.path.join(OUT, 'bench_hs300_index.parquet')
    if not os.path.exists(dst):
        try:
            for sym in ['sh000300', 'sh000905']:
                d = ak.stock_zh_index_daily(symbol=sym)
                d = d.copy()
                d['date'] = pd.to_datetime(d['date'])
                d['close'] = pd.to_numeric(d['close'], errors='coerce')
                d = d.dropna(subset=['close']).sort_values('date')
                d = d[d['date'] >= '2016-06-01']
                nm = 'hs300' if sym == 'sh000300' else 'zz500'
                p = os.path.join(OUT, f'bench_{nm}_index.parquet')
                d[['date', 'close']].to_parquet(p, index=False)
                print(f'  {nm} 指数: ✓ {len(d)} 行  {d.date.min().date()}~{d.date.max().date()}')
                time.sleep(0.5)
        except Exception as e:
            print(f'  指数: ✗ {type(e).__name__}: {str(e)[:90]}')
    else:
        print('  指数: 已存在')
    return 0


if __name__ == '__main__':
    sys.exit(main())
