# -*- coding: utf-8 -*-
"""
1万元价值投资初筛管线 (run_screen.py) — 固化版 v1.0
====================================================
纯缓存 + 腾讯qt + 东财估值历史 三源组装, 输出候选清单.

管线: 财务+价格合并 → ST剔除 → 主板/价格过滤 → 市值≥50亿 → 质量门槛 → 估值分位<50% → 输出

用途: 1万元实盘选股初筛 (演示级, 非投资建议; 结果须经人工复核5问)
频率: 每月一次 (spot 数据随交易日更新)

用法:
  D:/pyh/python.exe -X utf8 -E run_screen.py                  # 严格模式(PE/PB分位均<50%)
  D:/pyh/python.exe -X utf8 -E run_screen.py --top 5          # 只显示前5
  D:/pyh/python.exe -X utf8 -E run_screen.py --min-mcap 30    # 市值阈值30亿
  D:/pyh/python.exe -X utf8 -E run_screen.py --out custom.csv # 自定义输出路径

输出:
  output/screen_{YYYYMMDD}.csv    候选清单 (utf-8-sig, Excel友好)
  output/screen_{YYYYMMDD}.json   各阶段统计+运行信息

依赖模块 (screening/):
  st_filter.py  — ST/退市过滤 (前缀匹配, 两源一致性已验证)
  mcap_filter.py — 腾讯qt市值 (当日缓存, 覆盖率100%实测)
  valuation_percentile.py — PE/PB历史分位 (东财RPT_VALUEANALYSIS_DET, 手算对照0.0000pp)

数据源: yjbb(财务) + zcfz(负债率) + spot(价格/PE/PB) + qt.gtimg.cn(市值) + datacenter(估值历史)
"""
import os
import sys
import glob
import json
import argparse
import datetime

import pandas as pd
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, 'data_cache')
OUTPUT = os.path.join(BASE, 'output')
sys.path.insert(0, BASE)

from screening.st_filter import filter_non_st
from screening.mcap_filter import fetch_mcap, filter_by_mcap
from screening.valuation_percentile import percentile_for_candidates, filter_by_percentile

VERSION = '1.0.0'


def load_cache_latest(prefix):
    """取 data_cache/ 下最新一期缓存文件 (按文件名日期排序)"""
    files = sorted(glob.glob(os.path.join(CACHE, f'{prefix}_2*.parquet')))
    if not files:
        return None
    return pd.read_parquet(files[-1])


def spot_age_days():
    """spot 缓存距今多少天 (用于过期警告)"""
    files = sorted(glob.glob(os.path.join(CACHE, 'spot_2*.parquet')))
    if not files:
        return None
    name = os.path.basename(files[-1])  # spot_YYYYMMDD.parquet
    try:
        d = datetime.datetime.strptime(name.split('_')[1].split('.')[0], '%Y%m%d').date()
        return (datetime.date.today() - d).days
    except Exception:
        return None


def build_pool(min_mcap=50, verbose=True):
    """完整初筛管线 → (候选df, 各阶段统计)"""
    stats = {'version': VERSION, 'date': datetime.date.today().isoformat()}

    # ── 1. 数据加载 (最新缓存) ──
    spot = load_cache_latest('spot')
    yjbb = load_cache_latest('yjbb')
    zcfz = load_cache_latest('zcfz')
    if spot is None:
        raise RuntimeError('缺 spot 缓存 (data_cache/spot_*.parquet) — 先运行数据刷新')
    if yjbb is None or zcfz is None:
        raise RuntimeError('缺 yjbb/zcfz 缓存')

    # ── 2. 财务+价格合并 ──
    fin = pd.DataFrame({
        'code': yjbb['股票代码'].astype(str).str.zfill(6),
        '股票简称': yjbb['股票简称'],
        'eps': pd.to_numeric(yjbb['每股收益'], errors='coerce'),
        'bps': pd.to_numeric(yjbb['每股净资产'], errors='coerce'),
        'roe': pd.to_numeric(yjbb['净资产收益率'], errors='coerce'),
        'cfps': pd.to_numeric(yjbb['每股经营现金流量'], errors='coerce'),
        'gpm': pd.to_numeric(yjbb['销售毛利率'], errors='coerce'),
    })
    lev = pd.DataFrame({
        'code': zcfz['股票代码'].astype(str).str.zfill(6),
        'lev': pd.to_numeric(zcfz['资产负债率'], errors='coerce'),
    })
    fin = fin.merge(lev, on='code', how='left')

    sp = pd.DataFrame({
        'code': spot['代码'].astype(str).str.extract(r'(\d{6})$')[0],
        'name_s': spot['名称'],
        'price': pd.to_numeric(spot['最新价'], errors='coerce'),
        'pe': pd.to_numeric(spot['市盈率-动态'], errors='coerce'),
        'pb': pd.to_numeric(spot['市净率'], errors='coerce'),
    }).dropna(subset=['code'])

    df = fin.merge(sp, on='code', how='inner')
    # 名称列统一为 '股票简称' (st_filter 需要)
    if '股票简称' not in df.columns and 'name' in df.columns:
        df['股票简称'] = df['name']
    df = df.drop(columns=['name'], errors='ignore')
    stats['合并'] = len(df)
    if verbose:
        print(f'[1] 合并财务+行情: {len(df)} 只')

    # ── 3. ST剔除 ──
    df = filter_non_st(df)
    stats['ST剔除后'] = len(df)
    if verbose:
        print(f'[2] ST/退市剔除后: {len(df)} 只')

    # ── 4. 主板+价格+基本面基础过滤 ──
    m = (
        df['code'].str.match(r'^(60|00)') &          # 主板 (剔除688/30/8/4/9)
        df['price'].between(5, 30) &                  # 1万元买得起1-3手
        (df['eps'] > 0) &                             # 盈利
        (df['roe'] >= 8) &                            # 质量门槛
        (df['cfps'] > 0) &                            # 现金流为正
        (df['lev'] < 70) &                            # 负债安全
        (df['pe'] > 0) & (df['pe'] < 15) &            # 估值
        (df['pb'] > 0)
    )
    df = df[m].copy()
    stats['基础过滤后'] = len(df)
    if verbose:
        print(f'[3] 主板+价格+质量门槛: {len(df)} 只')

    # ── 5. 市值过滤 (腾讯qt, 当日缓存) ──
    if len(df) > 0:
        mcaps = fetch_mcap(df['code'].tolist())
        df['mcap_yi'] = df['code'].map(mcaps)
        df = filter_by_mcap(df, min_mcap_yi=min_mcap)
    stats['市值过滤后'] = len(df)
    if verbose:
        print(f'[4] 市值≥{min_mcap}亿: {len(df)} 只')

    # ── 6. 估值分位 (东财估值历史, 逐股缓存) ──
    if len(df) > 0:
        pctl = percentile_for_candidates(df['code'].tolist())
        df = df.merge(pctl, on='code', how='left')
        df = filter_by_percentile(df, max_pctl=50)
    stats['分位过滤后'] = len(df)
    if verbose:
        print(f'[5] PE/PB分位<50%: {len(df)} 只')

    return df, stats


def main():
    ap = argparse.ArgumentParser(description='1万元价值投资初筛 (固化版)')
    ap.add_argument('--top', type=int, default=0, help='只显示前N')
    ap.add_argument('--min-mcap', type=float, default=50, help='市值阈值(亿)')
    ap.add_argument('--out', default='', help='自定义输出CSV路径 (默认 output/screen_日期.csv)')
    ap.add_argument('--no-save', action='store_true', help='不落盘, 只打印')
    args = ap.parse_args()

    print('=' * 62)
    print(f' 1万元价值投资初筛管线 v{VERSION} (演示级, 非投资建议)')
    print(f' 日期: {datetime.date.today()}  市值阈值: {args.min_mcap}亿')
    print('=' * 62)

    # 过期警告
    age = spot_age_days()
    if age is not None and age > 7:
        print(f' ⚠️ 行情缓存已 {age} 天未更新 — 建议刷新 spot 数据后再运行 (结果仅供流程演示)')
        print()

    df, stats = build_pool(min_mcap=args.min_mcap)
    print()
    print('── 各阶段数量 ──')
    for k, v in stats.items():
        print(f'  {k}: {v}')

    # 落盘
    os.makedirs(OUTPUT, exist_ok=True)
    date_tag = datetime.date.today().strftime('%Y%m%d')
    if not args.no_save:
        if len(df) > 0:
            csv_path = args.out or os.path.join(OUTPUT, f'screen_{date_tag}.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f'\n[保存] 候选清单 → {csv_path}')
        json_path = os.path.join(OUTPUT, f'screen_{date_tag}.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f'[保存] 阶段统计 → {json_path}')

    if len(df) == 0:
        print('\n[结果] 无候选通过全部过滤 (空仓等待也是价值投资)')
        return 0

    cols = [c for c in ['code', '股票简称', 'price', 'pe', 'pb', 'roe', 'eps', 'cfps', 'lev',
                        'mcap_yi', 'pe_pctl', 'pb_pctl', 'n_obs'] if c in df.columns]
    show = df[cols].sort_values(['pe_pctl', 'pb_pctl'], na_position='last')
    if args.top > 0:
        show = show.head(args.top)
    print()
    print('── 候选清单 ──')
    print(show.to_string(index=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
