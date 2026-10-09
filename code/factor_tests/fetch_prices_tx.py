# -*- coding: utf-8 -*-
"""
S1/M5 试点检验 - 价格数据拉取 (腾讯 raw 日线, 全市场)
- 源: web.ifzq.gtimg.cn fqkline/get, fq='' (raw, 与新浪 raw 交叉验证一致)
- 4 页 × count=800, 覆盖 2015-09 ~ 2026-08
- 8 线程并发, 每股缓存 data_cache/tx_raw_{code}.parquet, 断点续传
- 用法: D:/pyh/python.exe -E fetch_prices_tx.py
"""
import os, sys, time, json, threading, glob
sys.stdout.reconfigure(encoding='utf-8')
os.environ['NO_PROXY'] = '*'; os.environ['no_proxy'] = '*'
for k in list(os.environ):
    if 'proxy' in k.lower(): os.environ.pop(k, None)
import requests
_orig = requests.Session.request
def _no_proxy(self, method, url, **kwargs):
    kwargs['proxies'] = {'http': None, 'https': None}
    kwargs.setdefault('timeout', 30)
    return _orig(self, method, url, **kwargs)
requests.Session.request = _no_proxy

import pandas as pd

BASE = r'G:/股市探究/quant-investing/code'
CACHE = os.path.join(BASE, 'data_cache')
PAGES = ('2018-06-01', '2021-03-01', '2023-11-01', '2026-08-22')
COUNT = 800
N_THREADS = 2
HDR = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def load_universe():
    spot = pd.read_parquet(os.path.join(CACHE, 'spot_20260822.parquet'))
    codes = []
    for c in spot['代码'].astype(str):
        c6 = c[-6:] if c.endswith(('6', '0', '3', '9', '2', '8', '4')) or len(c) > 6 else c
        c6 = ''.join(ch for ch in c if ch.isdigit())
        if len(c6) != 6:
            continue
        if c6.startswith(('6', '0', '3')):
            codes.append(('sh' + c6) if c6.startswith('6') else ('sz' + c6))
    return sorted(set(codes))

def fetch_one(sym):
    """拉取一股全部页并合并, 返回 DataFrame 或 None"""
    rows = []
    for end in PAGES:
        # 新浪日线接口 (JSONP, 返回 raw 日线; scale=240 日线, datalen 上限 800)
        # end 作为终点日期, 用 start_date 参数分页 (新浪接口无 start_date, 用 datalen=800 取终点前 800 条)
        url = (f'https://quotes.sina.cn/cn/api/jsonp_v2.php/var/'
               f'CN_MarketDataService.getKLineData?symbol={sym}&scale=240&ma=no&datalen=800')
        for attempt in range(6):
            try:
                r = requests.get(url, headers=HDR, timeout=30)
                txt = r.text
                # JSONP: /*...*/var([{...}]);  → 提取数组
                i1 = txt.find('(')
                i2 = txt.rfind(')')
                if i1 < 0 or i2 < 0 or i2 <= i1:
                    raise ValueError('bad jsonp wrapper')
                j = json.loads(txt[i1 + 1:i2])
                if not isinstance(j, list) or len(j) == 0:
                    break
                # 新浪字段: day, open, high, low, close, volume, amount(最后一条有)
                rows += [[x['day'], x['open'], x['close'], x['high'], x['low'], x.get('volume', 0)] for x in j]
                break
            except Exception:
                if attempt < 5:
                    time.sleep(3.0 * (attempt + 1))
                else:
                    raise
    if not rows:
        return None
    seen = set(); uniq = []
    for x in rows:
        if x[0] not in seen:
            seen.add(x[0]); uniq.append(x)
    uniq.sort(key=lambda x: x[0])
    df = pd.DataFrame(uniq, columns=['date', 'open', 'close', 'high', 'low', 'volume'])
    return df

lock = threading.Lock()
progress = {'done': 0, 'fail': 0, 'skip': 0}
t_start = time.time()

def worker(queue):
    while True:
        with lock:
            if not queue:
                return
            sym = queue.pop()
        out = os.path.join(CACHE, f'tx_raw_{sym}.parquet')
        if os.path.exists(out):
            with lock:
                progress['skip'] += 1
            continue
        try:
            df = fetch_one(sym)
            if df is not None and len(df) > 0:
                df.to_parquet(out, index=False)
                with lock:
                    progress['done'] += 1
            else:
                with lock:
                    progress['fail'] += 1
        except Exception as e:
            with lock:
                progress['fail'] += 1
                print(f"[FAIL] {sym}: {type(e).__name__} {str(e)[:60]}", flush=True)
        with lock:
            n = progress['done'] + progress['fail'] + progress['skip']
            if n % 200 == 0:
                el = time.time() - t_start
                rate = progress['done'] / el if el > 0 else 0
                print(f"[progress] done={progress['done']} fail={progress['fail']} skip={progress['skip']} "
                      f"rate={rate:.2f} req/s ETA={ (len(all_codes)-n)/max(rate,1e-9)/60:.0f}min", flush=True)

if __name__ == '__main__':
    all_codes = load_universe()
    print(f"[universe] {len(all_codes)} stocks", flush=True)
    queue = list(reversed(all_codes))
    threads = [threading.Thread(target=worker, args=(queue,)) for _ in range(N_THREADS)]
    for t in threads: t.start()
    for t in threads: t.join()
    el = time.time() - t_start
    print(f"[DONE] done={progress['done']} fail={progress['fail']} skip={progress['skip']} "
          f"total={len(all_codes)} {el/60:.1f}min", flush=True)
