# -*- coding: utf-8 -*-
"""
fetch_all_daily.py — 全 A 日线抓取（Workstream B）
=================================================
目标：把 data_cache 的日线覆盖从 487 只补到全 A 5563 只（含退市股），
      供 factor_tests/build_panel.py 构建全 A 月度面板，打通 P4/P5。

复用 code/data_fetcher.get_history()（自带磁盘缓存 + 节流 + 退避 + 新浪兜底），
不重写抓取逻辑。

关键设计：
  - **可中断续跑**：每只完成即记 data/fetch_progress.jsonl；重跑自动跳过已有缓存
  - 并发由本脚本控制（N 线程），data_fetcher 内部节流仍生效
  - 退市股并入股票池（生存者偏差防线）
  - 只写缓存，不碰 quant.db（灌库另一步，保持职责分离）

用法：
  D:/pyh/python.exe -E fetch_all_daily.py --workers 8
  D:/pyh/python.exe -E fetch_all_daily.py --workers 8 --limit 50    # 冒烟测试
"""
import os
import sys
import json
import time
import argparse
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = r'g:\股市探究\quant-investing\code'
sys.path.insert(0, BASE)
sys.stdout.reconfigure(encoding='utf-8')

OUT_DIR = r'g:\股市探究\fullA-检验与回测\data'
PROGRESS = os.path.join(OUT_DIR, 'fetch_progress.jsonl')
CACHE = os.path.join(BASE, 'data_cache')

# 起点：60日动量 + 120日上市龄需要更早，面板本身从 2017-01 起
START = '20160601'
END = datetime.date.today().strftime('%Y%m%d')
ADJUST = 'hfq'   # 由 --adjust 覆盖；hfq→ret_1m，raw→EP/BP 分母

_lock = threading.Lock()
_stats = {'ok': 0, 'cached': 0, 'fail': 0}
_fails = []


def log(msg):
    with _lock:
        print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


def record(code, status, rows, err=''):
    with _lock:
        with open(PROGRESS, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'ts': datetime.datetime.now().isoformat(),
                'code': code, 'status': status, 'rows': rows, 'err': err[:200],
                'adjust': ADJUST,
            }, ensure_ascii=False) + '\n')


def build_universe():
    """全 A 股票池 = stock_master（当前上市）+ 退市股。退市股不可省，否则生存者偏差。

    排除非本项目口径的品种（实测这些段系统性失败且本就不属 A 股主板/创业板/科创板）：
      200xxx / 900xxx — B 股（外币计价）
      920xxx        — 北交所
    """
    import sqlite3
    db = r'g:\股市探究\quant-investing\data\quant.db'
    codes = set()
    if os.path.exists(db):
        c = sqlite3.connect(db)
        for (code,) in c.execute('SELECT code FROM stock_master'):
            s = str(code).zfill(6)
            if s[:3] in ('200', '900', '920'):
                continue
            codes.add(s)
        c.close()
    n_master = len(codes)

    try:
        from data_fetcher import get_delisted_stocks
        d = get_delisted_stocks()
        delisted = set()
        if d is not None and len(d):
            # 退市股表是沪/深 concat 的结果，两套代码列各占一半：
            #   沪市 → 公司代码 (600xxx 等) 非空 159 个；深市 → 证券代码 非空 208 个
            # 只取任一列都会漏掉另一半（实测 367 = 159 + 208），故两列都取。
            for col in ('证券代码', '公司代码'):
                if col in d.columns:
                    before = len(delisted)
                    delisted |= {str(x).zfill(6) for x in d[col].dropna()
                                 if str(x).strip() not in ('', 'nan', 'None')}
                    log(f'  退市股列 {col}: 新增 {len(delisted) - before} 只')
        log(f'退市股合计 {len(delisted)} 只')
        codes |= delisted
    except Exception as e:
        log(f'⚠ 退市股获取失败（{type(e).__name__}: {str(e)[:80]}）—— 将只有在市股票')

    log(f'股票池：stock_master {n_master} + 退市 → 合计 {len(codes)} 只')
    return sorted(codes)


def load_done():
    """已成功的代码（续跑用）。
    新版按 (code, adjust) 去重；旧记录无 adjust 字段一律视为 hfq（首次抓的就是 hfq）。"""
    done = set()
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding='utf-8') as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get('status') in ('ok', 'cached') and r.get('adjust', 'hfq') == ADJUST:
                        done.add(r['code'])
                except Exception:
                    pass
    return done


def fetch_one(code):
    from data_fetcher import get_history
    real_adj = '' if ADJUST == 'raw' else ADJUST   # raw 传空串（data_fetcher 约定）
    try:
        df = get_history(code, start=START, end=END, adjust=real_adj)
        n = 0 if df is None else len(df)
        if n == 0:
            record(code, 'fail', 0, 'empty')
            return code, 'fail', 0, 'empty'
        record(code, 'ok', n)
        return code, 'ok', n, ''
    except Exception as e:
        msg = f'{type(e).__name__}: {str(e)[:120]}'
        record(code, 'fail', 0, msg)
        return code, 'fail', 0, msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--adjust', default='hfq', choices=['hfq', 'qfq', 'raw'],
                    help='复权口径。hfq 用于 ret_1m；raw 用于 EP/BP 分母（eps/bps 是 as-of 报告期口径）')
    a = ap.parse_args()

    global ADJUST
    ADJUST = a.adjust
    os.makedirs(OUT_DIR, exist_ok=True)
    log(f'=== 全 A 日线抓取 | {START}~{END} | adjust={ADJUST} | workers={a.workers} ===')

    universe = build_universe()
    done = load_done()
    todo = [c for c in universe if c not in done]
    if a.limit:
        todo = todo[:a.limit]
    log(f'已成功 {len(done)} 只（跳过）| 本次待抓 {len(todo)} 只')
    if not todo:
        log('无待抓任务，退出')
        return 0

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(fetch_one, c): c for c in todo}
        for i, fu in enumerate(as_completed(futs), 1):
            code, st, rows, err = fu.result()
            with _lock:
                _stats[st] = _stats.get(st, 0) + 1
                if st == 'fail':
                    _fails.append((code, err))
            if i % 25 == 0 or i == len(todo):
                el = time.time() - t0
                rate = i / el if el else 0
                eta = (len(todo) - i) / rate / 60 if rate else 0
                log(f'  进度 {i}/{len(todo)}  ok={_stats["ok"]} fail={_stats["fail"]} '
                    f'| {rate:.1f} 只/秒 | 已用 {el/60:.1f} 分 | 剩余约 {eta:.1f} 分')

    el = time.time() - t0
    log(f'=== 完成 | ok={_stats["ok"]} fail={_stats["fail"]} | 耗时 {el/60:.1f} 分 ===')
    if _fails:
        fp = os.path.join(OUT_DIR, 'fetch_failed.json')
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(_fails, f, ensure_ascii=False, indent=1)
        log(f'失败清单（可重跑本脚本自动重试）: {fp}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
