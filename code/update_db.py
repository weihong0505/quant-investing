# -*- coding: utf-8 -*-
"""
本地股票数据库 — 更新脚本 (update_db.py)
=========================================
从数据源/缓存拉取增量数据写入 SQLite.

调度: Windows 任务计划程序 (schtasks, 每日 18:30)
用法:
  D:/pyh/python.exe -E update_db.py                 # 全量更新所有表 (默认)
  D:/pyh/python.exe -E update_db.py --tables fin    # 只更新财务
  D:/pyh/python.exe -E update_db.py --tables spot,val,mcap,div,fin
  D:/pyh/python.exe -E update_db.py --no-network    # 只用本地缓存灌库, 不联网

表更新策略:
  stock_master    从 spot + full_pool 合并 (全量刷新)
  quarterly_fin   从 yjbb/zcfz 最新缓存灌入 (全量刷新, 缓存季度更新)
  valuation_daily 从 valhist 缓存 + 增量拉取 (候选池)
  dividends       从 div 缓存 (候选池)
  mcap_snapshot   从腾讯qt拉取 (当日, 全市场或候选池)
  daily_bars      从 get_history 拉取 (候选池, 增量; 东财受限时新浪兜底)
"""
import os
import sys
import glob
import re
import sqlite3
import argparse
import datetime

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, 'data_cache')
sys.path.insert(0, BASE)

from init_db import DB_PATH, init_db
from data_fetcher import get_spot_data, get_financials, get_valuation_history, \
    get_fcf, get_dividends, get_history, get_full_stock_pool
from screening.mcap_filter import fetch_mcap

TODAY = datetime.date.today().strftime('%Y-%m-%d')
TODAY_TAG = datetime.date.today().strftime('%Y%m%d')


def log_update(conn, table, action, rows_before, rows_after, source, status, message=''):
    conn.execute(
        'INSERT INTO meta_updates (table_name, action, rows_before, rows_after, source, status, message, ts) '
        'VALUES (?,?,?,?,?,?,?,?)',
        (table, action, rows_before, rows_after, source, status, message, datetime.datetime.now().isoformat()))
    conn.commit()  # 必须立即提交: 单表运行时若等下次 commit 会随 close 回滚丢失


def load_latest_cache(prefix):
    """取行数最多的缓存文件 (防残缺缓存: 抓取中断的文件行数必然更少)"""
    files = sorted(glob.glob(os.path.join(CACHE, f'{prefix}_2*.parquet')))
    if not files:
        return None
    import pyarrow.parquet as pq
    best, best_n = None, -1
    for f in files:
        try:
            n = pq.ParquetFile(f).metadata.num_rows
            if n > best_n:
                best, best_n = f, n
        except Exception:
            continue
    return pd.read_parquet(best) if best else None


def load_latest_cache_period(prefix):
    """取最新报告期的缓存文件, 返回 (df, 报告期) — 报告期从文件名解析 (yyyymmdd→yyyy-mm-dd)

    选择规则: 文件名中的报告期(第一个20xxxxxx)最大者; 同报告期取文件名排序最后
    (带 _date_str 后缀的是更新抓取版)。历史报告期文件(2015-2024)行数可能更多,
    故不能用行数最多策略。
    """
    files = sorted(glob.glob(os.path.join(CACHE, f'{prefix}_2*.parquet')))
    if not files:
        return None, None
    best, best_period = None, None
    for f in files:
        base = os.path.basename(f)[len(prefix) + 1:]
        m = re.findall(r'20\d{6}', base)
        if not m:
            continue
        if best_period is None or m[0] > best_period or (m[0] == best_period and f > best):
            best, best_period = f, m[0]
    if best is None:
        return None, None
    period = f'{best_period[:4]}-{best_period[4:6]}-{best_period[6:8]}'
    return pd.read_parquet(best), period


def update_stock_master(conn, verbose=True):
    """从 spot 缓存 + full_pool 合并主表"""
    before = conn.execute('SELECT COUNT(*) FROM stock_master').fetchone()[0]
    spot = load_latest_cache('spot')
    rows = []
    if spot is not None:
        codes = spot['代码'].astype(str).str.extract(r'(\d{6})$')[0]
        names = spot['名称'] if '名称' in spot.columns else spot.get('股票简称', '')
        for c, n in zip(codes, names):
            if pd.notna(c):
                rows.append((c, str(n), None, 1 if 'ST' in str(n) or '退' in str(n) else 0, 0, TODAY))
    # full_pool 退市标记
    try:
        fp = get_full_stock_pool()
        if fp is not None and len(fp) > 0:
            delist_codes = set(fp.loc[fp['退市'] == True, '代码'].astype(str).str.zfill(6))
            for c in delist_codes:
                rows.append((c, '', None, 0, 1, TODAY))
    except Exception as e:
        if verbose:
            print(f'  [warn] full_pool 不可用: {e}')
    if rows:
        conn.execute('DELETE FROM stock_master')
        conn.executemany(
            'INSERT OR REPLACE INTO stock_master (code, name, industry, is_st, delisted, updated_at) '
            'VALUES (?,?,?,?,?,?)', rows)
    conn.commit()
    after = conn.execute('SELECT COUNT(*) FROM stock_master').fetchone()[0]
    log_update(conn, 'stock_master', 'FULL', before, after, 'spot+full_pool', 'OK')
    if verbose:
        print(f'[stock_master] {before} → {after} 行')


def update_quarterly_fin(conn, verbose=True):
    """从 yjbb/zcfz 缓存灌入财务 (多报告期, 过滤到 stock_master 池)

    遍历 data_cache 下所有 yjbb_{报告期}*.parquet, 报告期从文件名解析;
    zcfz 同样遍历, lev 按 (code, report_date) 合并 (缺期则 NULL)。
    """
    before = conn.execute('SELECT COUNT(*) FROM quarterly_fin').fetchone()[0]
    # 只保留主表股票池 (东财接口含新三板, 必须过滤)
    pool = set(r[0] for r in conn.execute('SELECT code FROM stock_master'))

    def _period_of(f):
        base = os.path.basename(f)
        m = re.findall(r'20\d{6}', base)
        return f'{m[0][:4]}-{m[0][4:6]}-{m[0][6:8]}' if m else None

    frames = []
    for f in sorted(glob.glob(os.path.join(CACHE, 'yjbb_2*.parquet'))):
        period = _period_of(f)
        if not period:
            continue
        try:
            df = pd.read_parquet(f)
        except Exception:
            continue
        if len(df) == 0:
            continue
        df = df[df['股票代码'].astype(str).str.zfill(6).isin(pool)].copy()
        if len(df) == 0:
            continue
        fin = pd.DataFrame({
            'code': df['股票代码'].astype(str).str.zfill(6),
            'report_date': period,
            'notice_date': df.get('最新公告日期', None),
            'eps': pd.to_numeric(df['每股收益'], errors='coerce'),
            'bps': pd.to_numeric(df['每股净资产'], errors='coerce'),
            'roe': pd.to_numeric(df['净资产收益率'], errors='coerce'),
            'cfps': pd.to_numeric(df['每股经营现金流量'], errors='coerce'),
            'gpm': pd.to_numeric(df['销售毛利率'], errors='coerce'),
        })
        frames.append(fin)
    if not frames:
        if verbose:
            print('  [skip] 无 yjbb 缓存')
        return
    fin = pd.concat(frames, ignore_index=True)
    fin['lev'] = None
    # zcfz: 按 (code, report_date) 合并资产负债率
    for f in sorted(glob.glob(os.path.join(CACHE, 'zcfz_2*.parquet'))):
        period = _period_of(f)
        if not period:
            continue
        try:
            zc = pd.read_parquet(f)
        except Exception:
            continue
        if len(zc) == 0:
            continue
        zc = zc[zc['股票代码'].astype(str).str.zfill(6).isin(pool)].copy()
        if len(zc) == 0:
            continue
        lev = pd.DataFrame({
            'code': zc['股票代码'].astype(str).str.zfill(6),
            'report_date': period,
            'lev': pd.to_numeric(zc['资产负债率'], errors='coerce'),
        })
        fin = fin.merge(lev, on=['code', 'report_date'], how='left', suffixes=('', '_zc'))
        fin['lev'] = fin['lev'].fillna(fin.get('lev_zc'))
        fin = fin.drop(columns=['lev_zc'], errors='ignore')
    fin = fin.dropna(subset=['code'])
    conn.execute('DELETE FROM quarterly_fin')
    conn.executemany(
        'INSERT OR REPLACE INTO quarterly_fin (code, report_date, notice_date, eps, bps, roe, cfps, gpm, lev) '
        'VALUES (?,?,?,?,?,?,?,?,?)',
        fin[['code', 'report_date', 'notice_date', 'eps', 'bps', 'roe', 'cfps', 'gpm', 'lev']].itertuples(index=False))
    conn.commit()
    after = conn.execute('SELECT COUNT(*) FROM quarterly_fin').fetchone()[0]
    n_period = conn.execute('SELECT COUNT(DISTINCT report_date) FROM quarterly_fin').fetchone()[0]
    log_update(conn, 'quarterly_fin', 'FULL', before, after, 'yjbb+zcfz cache', 'OK')
    if verbose:
        print(f'[quarterly_fin] {before} → {after} 行 ({n_period} 个报告期)')


def update_valuation_daily(conn, codes=None, verbose=True):
    """估值历史: 有 valhist 缓存则灌入, 否则拉取"""
    before = conn.execute('SELECT COUNT(*) FROM valuation_daily').fetchone()[0]
    if codes is None:
        files = sorted(glob.glob(os.path.join(CACHE, 'valhist_*.parquet')))
        codes = [os.path.basename(f)[8:14] for f in files]
    added = 0
    for code in codes:
        try:
            vh = get_valuation_history(code)
            if vh is None or len(vh) == 0:
                continue
            vh = vh.rename(columns={'date': 'date'})
            vh['code'] = code
            vh['date'] = vh['date'].astype(str).str[:10]
            rows = vh[['code', 'date', 'pe_ttm', 'pe_lar', 'pb_mrq', 'total_mcap', 'close']] \
                .dropna(subset=['date']).itertuples(index=False)
            conn.execute('DELETE FROM valuation_daily WHERE code=?', (code,))
            conn.executemany(
                'INSERT OR REPLACE INTO valuation_daily (code, date, pe_ttm, pe_lar, pb_mrq, total_mcap, close) '
                'VALUES (?,?,?,?,?,?,?)', rows)
            conn.commit()
            added += len(vh)
        except Exception as e:
            if verbose:
                print(f'  [warn] {code} 估值历史失败: {type(e).__name__} {str(e)[:50]}')
    after = conn.execute('SELECT COUNT(*) FROM valuation_daily').fetchone()[0]
    log_update(conn, 'valuation_daily', 'FULL', before, after, 'RPT_VALUEANALYSIS_DET', 'OK' if added else 'FAIL')
    if verbose:
        print(f'[valuation_daily] {before} → {after} 行 (本次+{added})')


def update_dividends(conn, codes=None, verbose=True):
    """分红: 有 div 缓存则灌入"""
    before = conn.execute('SELECT COUNT(*) FROM dividends').fetchone()[0]
    files = sorted(glob.glob(os.path.join(CACHE, 'div_*.parquet')))
    if not files:
        if verbose:
            print('  [skip] 无 div 缓存')
        return
    added = 0
    for f in files:
        code = os.path.basename(f)[4:10]
        try:
            dv = pd.read_parquet(f)
            if dv is None or len(dv) == 0:
                continue
            # 缓存列名为中文(东财 fhps 口径), 映射到库表英文列
            if '现金分红-现金分红比例' in dv.columns:
                dv = dv.rename(columns={
                    '报告期': 'report_date',
                    '除权除息日': 'ex_date',
                    '现金分红-现金分红比例': 'cash_div_per10',
                    '方案进度': 'progress',
                })
            dv['code'] = code
            cols = [c for c in ['code', 'report_date', 'ex_date', 'cash_div_per10', 'progress'] if c in dv.columns]
            if not cols or 'report_date' not in cols:
                if verbose:
                    print(f'  [warn] {code} 分红缓存列不完整: {list(dv.columns)}')
                continue
            conn.execute('DELETE FROM dividends WHERE code=?', (code,))
            conn.executemany(
                'INSERT OR REPLACE INTO dividends (code, report_date, ex_date, cash_per10, progress) '
                'VALUES (?,?,?,?,?)',
                dv[cols].itertuples(index=False))
            conn.commit()
            added += len(dv)
        except Exception as e:
            if verbose:
                print(f'  [warn] {code} 分红失败: {e}')
    after = conn.execute('SELECT COUNT(*) FROM dividends').fetchone()[0]
    log_update(conn, 'dividends', 'FULL', before, after, 'fhps cache', 'OK')
    if verbose:
        print(f'[dividends] {before} → {after} 行 (本次+{added})')


def update_mcap(conn, codes=None, verbose=True):
    """市值快照: 腾讯qt拉取"""
    before = conn.execute('SELECT COUNT(*) FROM mcap_snapshot').fetchone()[0]
    if codes is None:
        spot = load_latest_cache('spot')
        if spot is None:
            if verbose:
                print('  [skip] 无 spot 缓存, 无法确定股票池')
            return
        codes = spot['代码'].astype(str).str.extract(r'(\d{6})$')[0].dropna().tolist()
    mcaps = fetch_mcap(codes)
    rows = [(c, TODAY, v) for c, v in mcaps.items()]
    conn.execute('DELETE FROM mcap_snapshot WHERE date=?', (TODAY,))
    conn.executemany('INSERT OR REPLACE INTO mcap_snapshot (code, date, mcap_yi) VALUES (?,?,?)', rows)
    conn.commit()
    after = conn.execute('SELECT COUNT(*) FROM mcap_snapshot').fetchone()[0]
    log_update(conn, 'mcap_snapshot', 'INCR', before, after, 'tencent qt', 'OK')
    if verbose:
        print(f'[mcap_snapshot] {before} → {after} 行 (今日+{len(rows)})')


def main():
    ap = argparse.ArgumentParser(description='本地股票数据库更新')
    ap.add_argument('--tables', default='all', help='all 或逗号分隔: spot,fin,val,mcap,div,bars')
    ap.add_argument('--codes', default='', help='限定代码(逗号分隔), 默认全市场/缓存池')
    ap.add_argument('--no-network', action='store_true', help='只用本地缓存, 不联网')
    args = ap.parse_args()

    print('=' * 60)
    print(f' 本地股票数据库更新  {TODAY}')
    print('=' * 60)
    init_db(verbose=False)
    conn = sqlite3.connect(DB_PATH)
    codes = args.codes.split(',') if args.codes else None

    tables = args.tables.split(',')
    if 'all' in tables or 'spot' in tables:
        update_stock_master(conn)
    if 'all' in tables or 'fin' in tables:
        update_quarterly_fin(conn)
    if 'all' in tables or 'val' in tables:
        update_valuation_daily(conn, codes=codes)
    if 'all' in tables or 'div' in tables:
        update_dividends(conn, codes=codes)
    if 'all' in tables or 'mcap' in tables:
        update_mcap(conn, codes=codes)
    conn.close()
    print('=' * 60)
    print(' 完成')


if __name__ == '__main__':
    main()
