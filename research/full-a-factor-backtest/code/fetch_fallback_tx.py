# -*- coding: utf-8 -*-
"""
fetch_fallback_tx.py — 退市股日线兜底（腾讯源）
==============================================
背景：新浪 stock_zh_a_daily 不服务早期退市股。实测 fetch_all_daily 的失败项
      **100% 不在 stock_master 里**（即全是退市股），而退市股正是生存者偏差
      防线所必需的样本 —— 不能把失败当"脏数据"放过。

本脚本只处理 fetch_progress.jsonl 中 status=fail 的代码，走腾讯
`ak.stock_zh_a_hist_tx`（data_fetcher 已在其 e2e_pipeline 中用于退市股），
并把输出**归一化成与新浪缓存相同的列结构**，使 build_panel 无需分支：
    date, open, high, low, close, volume, amount, outstanding_share, turnover

列映射与不确定性（如实声明，不编造）：
  - 腾讯 tx 输出列名以实测为准（英文或中文），脚本内自动适配
  - `outstanding_share`：腾讯日线**不含**流通股本。退市股无法可靠取得，
    故填 NaN —— 下游不得用退市股的 outstanding_share 推算市值，
    改用 T 月末 close × 当日 amount/volume 口径不可行时，该样本市值标记为缺失。
  - `turnover`：由 volume 与 outstanding_share 推不出（同上），填 NaN。

用法：
  D:/pyh/python.exe -E fetch_fallback_tx.py --workers 6
"""
import os
import sys
import json
import time
import argparse
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np

BASE = r'g:\股市探究\quant-investing\code'
sys.path.insert(0, BASE)
sys.stdout.reconfigure(encoding='utf-8')

TASK = r'g:\股市探究\fullA-检验与回测\data'
PROGRESS = os.path.join(TASK, 'fetch_progress.jsonl')
CACHE = os.path.join(BASE, 'data_cache')
START = '20160601'
END = datetime.date.today().strftime('%Y%m%d')

_lock = threading.Lock()
_stats = {'ok': 0, 'fail': 0}
_fails = []

SINA_COLS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount',
             'outstanding_share', 'turnover']


def log(m):
    with _lock:
        print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}] {m}', flush=True)


def record(code, status, rows, err=''):
    with _lock:
        with open(PROGRESS, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'ts': datetime.datetime.now().isoformat(), 'code': code,
                                'status': status, 'rows': rows, 'err': err[:200],
                                'src': 'tx'}, ensure_ascii=False) + '\n')


def to_sina_schema(df):
    """把腾讯输出归一化成新浪列结构。列名中英自动适配。"""
    if df is None or len(df) == 0:
        return None
    ren = {}
    cn2en = {'日期': 'date', '开盘': 'open', '收盘': 'close', '最高': 'high',
             '最低': 'low', '成交量': 'volume', '成交额': 'amount'}
    for c in df.columns:
        lc = str(c).strip().lower()
        if lc in ('date', 'day', 'trade_date'):
            ren[c] = 'date'
        elif c in cn2en:
            ren[c] = cn2en[c]
        elif lc in ('open', 'high', 'low', 'close', 'volume', 'amount', 'turnover'):
            ren[c] = lc
    d = df.rename(columns=ren)
    need = ['date', 'open', 'high', 'low', 'close', 'volume']
    if not all(c in d.columns for c in need):
        return None
    if 'amount' not in d.columns:
        d['amount'] = np.nan
    d['date'] = pd.to_datetime(d['date'], errors='coerce')
    d = d.dropna(subset=['date']).sort_values('date')
    for c in ['open', 'high', 'low', 'close', 'volume', 'amount']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    # 腾讯不含流通股本 → 如实留空，不编造
    d['outstanding_share'] = np.nan
    d['turnover'] = np.nan
    return d[SINA_COLS].reset_index(drop=True)


def fetch_one(code):
    import akshare as ak
    from data_fetcher import _code_to_sina, _cache_path, _write_cache
    cache_path = _cache_path('hist', code, START, END, 'hfq', date_str=END)
    if os.path.exists(cache_path):
        try:
            old = pd.read_parquet(cache_path)
            if old is not None and len(old) > 0:
                record(code, 'cached', len(old))
                return code, 'cached', len(old), ''
        except Exception:
            pass
    try:
        sym = _code_to_sina(code)
        df = ak.stock_zh_a_hist_tx(symbol=sym, start_date=START, end_date=END, adjust='hfq')
        d = to_sina_schema(df)
        if d is None or len(d) == 0:
            record(code, 'fail', 0, 'tx empty/unmappable')
            return code, 'fail', 0, 'tx empty'
        _write_cache(d, cache_path)
        record(code, 'ok', len(d))
        return code, 'ok', len(d), ''
    except Exception as e:
        msg = f'{type(e).__name__}: {str(e)[:100]}'
        record(code, 'fail', 0, msg)
        return code, 'fail', 0, msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()

    fails = []
    if os.path.exists(PROGRESS):
        for line in open(PROGRESS, encoding='utf-8'):
            try:
                r = json.loads(line)
                if r.get('status') == 'fail' and r.get('src') != 'tx':
                    fails.append(r['code'])
            except Exception:
                pass
    fails = sorted(set(fails))
    log(f'=== 腾讯兜底 | 待处理失败代码 {len(fails)} 只 ===')
    if not fails:
        return 0

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(fetch_one, c): c for c in fails}
        for i, fu in enumerate(as_completed(futs), 1):
            code, st, rows, err = fu.result()
            with _lock:
                _stats[st] = _stats.get(st, 0) + 1
                if st == 'fail':
                    _fails.append((code, err))
            if i % 20 == 0 or i == len(fails):
                el = time.time() - t0
                log(f'  进度 {i}/{len(fails)} ok={_stats["ok"]} fail={_stats["fail"]} | {el:.0f}s')

    log(f'=== 完成 | ok={_stats["ok"]} fail={_stats["fail"]} ===')
    if _fails:
        fp = os.path.join(TASK, 'fetch_failed_tx.json')
        json.dump(_fails, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        log(f'仍失败清单 → {fp}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
