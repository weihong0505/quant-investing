# -*- coding: utf-8 -*-
"""
S1/M5 试点检验 - 财务数据拉取 (东财 datacenter, 可用)
- yjbb 业绩报表: 2015Q3 ~ 2026Q2 (44 期)
- zcfz 资产负债表: 2016Q1 ~ 2026Q2 (42 期)
- fhps 分红送转: 20151231 ~ 20260630 (半年度, 22 期)
- 缓存 data_cache/{yjbb|zcfz|fhps}_{期}.parquet, 已存在跳过
- 用法: D:/pyh/python.exe -E fetch_financials_em.py
"""
import os, sys, time
sys.stdout.reconfigure(encoding='utf-8')
os.environ['NO_PROXY'] = '*'; os.environ['no_proxy'] = '*'
for k in list(os.environ):
    if 'proxy' in k.lower(): os.environ.pop(k, None)
import requests
_orig = requests.Session.request
def _no_proxy(self, method, url, **kwargs):
    kwargs['proxies'] = {'http': None, 'https': None}
    kwargs.setdefault('timeout', 60)
    return _orig(self, method, url, **kwargs)
requests.Session.request = _no_proxy

import pandas as pd
import akshare as ak

BASE = r'G:/股市探究/quant-investing/code'
CACHE = os.path.join(BASE, 'data_cache')

def quarter_ends(start, end):
    """start/end: 'YYYYMMDD' 之间的季末列表"""
    out = []
    y0, y1 = int(start[:4]), int(end[:4])
    for y in range(y0, y1 + 1):
        for md in ('0331', '0630', '0930', '1231'):
            q = f'{y}{md}'
            if start <= q <= end:
                out.append(q)
    return out

def fetch_with_retry(fn, name, retries=3):
    for i in range(retries):
        try:
            df = fn()
            if df is not None and len(df) > 0:
                return df
            print(f"[{name}] empty result, retry {i+1}", flush=True)
        except Exception as e:
            print(f"[{name}] {type(e).__name__}: {str(e)[:80]} retry {i+1}", flush=True)
        time.sleep(3 * (i + 1))
    return None

def main():
    # ---- yjbb ----
    yjbb_qs = quarter_ends('20150930', '20260630')
    print(f"[yjbb] {len(yjbb_qs)} quarters: {yjbb_qs[0]}..{yjbb_qs[-1]}", flush=True)
    for q in yjbb_qs:
        path = os.path.join(CACHE, f'yjbb_{q}.parquet')
        if os.path.exists(path) and os.path.getsize(path) > 50000:
            continue
        df = fetch_with_retry(lambda q=q: ak.stock_yjbb_em(date=q), f'yjbb_{q}')
        if df is not None:
            df.to_parquet(path, index=False)
            print(f"[yjbb {q}] OK {len(df)}", flush=True)
        else:
            print(f"[yjbb {q}] FAILED (skip)", flush=True)
        time.sleep(2.0)

    # ---- zcfz ----
    zcfz_qs = quarter_ends('20160331', '20260630')
    print(f"[zcfz] {len(zcfz_qs)} quarters", flush=True)
    for q in zcfz_qs:
        path = os.path.join(CACHE, f'zcfz_{q}.parquet')
        if os.path.exists(path) and os.path.getsize(path) > 50000:
            continue
        df = fetch_with_retry(lambda q=q: ak.stock_zcfz_em(date=q), f'zcfz_{q}')
        if df is not None:
            df.to_parquet(path, index=False)
            print(f"[zcfz {q}] OK {len(df)}", flush=True)
        else:
            print(f"[zcfz {q}] FAILED (skip)", flush=True)
        time.sleep(2.0)

    # ---- fhps 分红送转 ----
    fhps_dates = []
    for y in range(2015, 2027):
        for md in ('0630', '1231'):
            d = f'{y}{md}'
            if d <= '20260630':
                fhps_dates.append(d)
    print(f"[fhps] {len(fhps_dates)} dates", flush=True)
    for d in fhps_dates:
        path = os.path.join(CACHE, f'fhps_{d}.parquet')
        if os.path.exists(path) and os.path.getsize(path) > 50000:
            continue
        df = fetch_with_retry(lambda d=d: ak.stock_fhps_em(date=d), f'fhps_{d}')
        if df is not None:
            df.to_parquet(path, index=False)
            print(f"[fhps {d}] OK {len(df)}", flush=True)
        else:
            print(f"[fhps {d}] FAILED (skip)", flush=True)
        time.sleep(2.0)

    print("[ALL FINANCIALS DONE]", flush=True)

if __name__ == '__main__':
    main()
