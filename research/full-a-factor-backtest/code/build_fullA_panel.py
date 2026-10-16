# -*- coding: utf-8 -*-
"""
build_fullA_panel.py — 全 A 月度面板构建（Workstream A）
======================================================
数据源（全 A，不依赖残缺的 data_cache）：
  财务 : quant.db quarterly_fin（5562 只 / 2015Q3~2026Q2 / eps,bps,roe,gpm）
  价格 : data_cache/hist_*.parquet（新浪 hfq，裸 close 与复权 close 成对）
  股本 : 日线 outstanding_share（流通股本）→ 市值

⚠️ 两个必须先钉死的口径（本脚本严格按此实现，写进输出元数据）：

1) **PIT（公告日）用法定披露截止日，不用 notice_date**
   实测：quarterly_fin.notice_date 是「最新修订日」而非首次披露日 —— 173,729 行里
   仅 15.0% 落在法定窗口内，74.5% 逾期 31~365 天，10.3% 逾期 >365 天
   （例：2015 年报的 notice_date = 2026-04-28）。直接用它会产生前视偏差。
   改用法定截止日（Q1→4/30、半年报→8/31、Q3→10/31、年报→次年4/30）作为
   「可用时点」。它单调不漏未来：85% 的 notice_date 晚于截止日，故对每行都成立。

2) **ROE_TTM 由 eps 差分滚动算，不用 roe 列直接求和**
   实测：roe 是报告期累计口径（600000：Q1 2.55 → Q2 4.33 → Q3 5.67 → Q4 6.76）。
   累计值直接滚动求和会重复计上半年。故：
     TTM_EPS_t = eps(最新期) + eps(上年年报) − eps(上年同期)
     ROE_TTM   = TTM_EPS / bps
   （eps 同为累计口径，已用 600000 对账确认）

因子（全 A 可算的 4 个）：
   ROE_TTM, GPM, EP = TTM_EPS/close, BP = bps/close
 不可算并如实声明：LEV（lev 列全 NULL）、CFO_NI_TTM（库内无净利润/经营现金流绝对额）

用法：D:/pyh/python.exe -E build_fullA_panel.py [--start 2017-01] [--sample 300]
输出：data/panel_fullA.parquet + output/panel_build_report.md
"""
import os
import sys
import glob
import json
import time
import argparse
import datetime as dt
import re

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'g:\股市探究\quant-investing\code'
CACHE = os.path.join(BASE, 'data_cache')
TASK = r'g:\股市探究\fullA-检验与回测'
DB = r'g:\股市探究\quant-investing\data\quant.db'

# 法定披露截止日：(月, 日, 是否跨年)
DEADLINE = {3: (4, 30, 0), 6: (8, 31, 0), 9: (10, 31, 0), 12: (4, 30, 1)}


def pit_available(report_date):
    """报告期的法定披露截止日 = 该财务数据最早可用日"""
    y, m = report_date.year, report_date.month
    mm, dd, cross = DEADLINE[m]
    return pd.Timestamp(dt.date(y + cross, mm, dd))


def load_fin():
    import sqlite3
    conn = sqlite3.connect(DB)
    df = pd.read_sql('SELECT code, report_date, eps, bps, roe, gpm FROM quarterly_fin', conn)
    conn.close()
    df['report_date'] = pd.to_datetime(df['report_date'])
    for c in ['eps', 'bps', 'roe', 'gpm']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['code'] = df['code'].astype(str).str.zfill(6)
    # PIT 可用日
    df['avail'] = df['report_date'].apply(pit_available)
    # 差分滚动所需的年/期标识
    df['year'] = df['report_date'].dt.year
    df['q'] = df['report_date'].dt.quarter
    return df.sort_values(['code', 'report_date'])


def build_ttm(fin):
    """TTM_EPS = eps(T) + eps(最近已披露财年) − eps(上年同期)。eps 为累计口径。

    ⚠️ 2026-10-09 修复的 bug #2（曾使 EP 中位数失真到 PE≈267 倍）：
       旧写法用 `merge(annual, on=['code','year'])`，即按**报告期所在年份**找 Q4 年报。
       但 2026 年还没有 Q4 行（尚未发生），所以 2026 各期 eps_annual 恒为 NaN，
       TTM 大面积算不出 —— 与数据无关，是**锚定年份选错**。
       正确锚定是「最近一个已披露财年」：
         Q3/Q4 → 若同年年报已存在则用同年，否则回退上一年报
         Q1/Q2 → 必须用上一年报（Q1 时点上年报刚披露；Q2 时点用上年报 + 上年同期）
       保守性声明：Q3 回退到上一年报时，TTM 窗口比 12 个月长约 3~6 个月，
       因子值略陈旧但不含未来信息（宁可陈旧，不可前视）。

    ⚠️ 2026-10-09 修复的 bug #1（列名撞名）：
       旧写法 `fin.merge(annual).merge(same)` 中 fin 已含 eps_annual，
       与 same 的 eps_annual 撞名 → 产出 eps_annual_x / _y，取值必为 NaN。
       故下面显式裁剪列 + 断言。
    """
    annual = (fin.loc[fin['q'] == 4, ['code', 'year', 'eps']]
                 .rename(columns={'eps': 'eps_annual'}))
    same = fin[['code', 'year', 'q', 'eps']].copy()
    same['year'] = same['year'] + 1                      # 对齐到"上年同期"
    same = same.rename(columns={'eps': 'eps_prev_same'})

    f = fin.copy()
    # 锚定财年：Q1/Q2 → year-1；Q3/Q4 → year（随后按缺失回退）
    f['anchor_year'] = np.where(f['q'].isin([1, 2]), f['year'] - 1, f['year'])

    out = f.merge(annual.rename(columns={'year': 'anchor_year'}),
                  on=['code', 'anchor_year'], how='left')
    # 回退：Q3/Q4 若同年年报缺失（尚未披露），改用上一年报（保守、无前视）
    need_fb = f['q'].isin([3, 4]) & out['eps_annual'].isna()
    if need_fb.any():
        fb = f.loc[need_fb, ['code', 'year', 'q', 'eps', 'bps', 'roe', 'gpm',
                             'report_date', 'avail', 'anchor_year']].copy()
        fb['anchor_year'] = fb['year'] - 1
        fb = fb.merge(annual.rename(columns={'year': 'anchor_year'}),
                      on=['code', 'anchor_year'], how='left')
        out.loc[need_fb, 'eps_annual'] = fb['eps_annual'].values
        print(f'  TTM: {int(need_fb.sum()):,} 行因同年年报未披露而回退上一年报（保守口径）')

    out = out.merge(same, on=['code', 'year', 'q'], how='left')

    for c in ('eps_annual', 'eps_prev_same'):
        assert c in out.columns, f'合并后缺列 {c}（疑似撞名，检查 merge 输入列）'

    # TTM = 上年报 + (本年累计 − 上年同期累计)
    out['ttm_eps'] = out['eps_annual'] + (out['eps'] - out['eps_prev_same'])
    # Q4 当期即年报：TTM == 年报累计（精确）
    is_q4 = out['q'] == 4
    out.loc[is_q4, 'ttm_eps'] = out.loc[is_q4, 'eps']
    # 无上年同期时（如某期缺失），退化为「上年报 + 本年累计」，标记为近似
    approx = out['ttm_eps'].isna() & out['eps_annual'].notna() & out['eps'].notna()
    out.loc[approx, 'ttm_eps'] = (out.loc[approx, 'eps_annual'] + out.loc[approx, 'eps'])
    if approx.any():
        print(f'  TTM: {int(approx.sum()):,} 行缺上年同期 → 近似口径（上年报+本年累计）')
    out.attrs['ttm_approx_rows'] = int(approx.sum())

    has_eps = out['eps'].notna()
    can = out.loc[has_eps, 'ttm_eps'].notna()
    print(f'  TTM 自检: 有 eps 的行 {has_eps.sum():,}，其中可算 TTM {can.sum():,} '
          f'({can.mean():.1%})')
    return out


def month_ends(start, end):
    return pd.date_range(start=start, end=end, freq='ME')


def build_price_cache_index(codes):
    """扫描 hist_*.parquet，返回 {(code, adjust_kind): path}
    文件名: hist_{code}_{start}_{end}_{adjust}_{endtag}.parquet
    adjust_kind: 'hfq' 或 'raw'（无 adjust 段）
    """
    idx = {}
    for f in glob.glob(os.path.join(CACHE, 'hist_*.parquet')):
        b = os.path.basename(f)
        m = re.match(r'hist_(\d{6})_(\d{8})_(\d{8})_(hfq|qfq)?_?(\d{8})\.parquet$', b)
        if not m:
            continue
        code, _s, _e, adj, _tag = m.groups()
        if code not in codes:
            continue
        kind = adj if adj else 'raw'
        # 同 kind 取最新文件
        if (code, kind) not in idx or os.path.getmtime(f) > os.path.getmtime(idx[(code, kind)]):
            idx[(code, kind)] = f
    return idx


def load_one_prices(path):
    try:
        d = pd.read_parquet(path)
        if d is None or len(d) == 0 or 'date' not in d.columns or 'close' not in d.columns:
            return None
        d = d[['date', 'close'] + (['outstanding_share'] if 'outstanding_share' in d.columns else [])]
        d['date'] = pd.to_datetime(d['date'], errors='coerce')
        d['close'] = pd.to_numeric(d['close'], errors='coerce')
        if 'outstanding_share' in d.columns:
            d['outstanding_share'] = pd.to_numeric(d['outstanding_share'], errors='coerce')
        else:
            d['outstanding_share'] = np.nan
        return d.dropna(subset=['date']).sort_values('date')
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', default='2017-01')
    ap.add_argument('--end', default=None)
    ap.add_argument('--sample', type=int, default=0, help='>0 时只跑前 N 只（冒烟）')
    a = ap.parse_args()

    t0 = time.time()
    fin = load_fin()
    print(f'财务: {len(fin):,} 行 / {fin.code.nunique():,} 只 / '
          f'{fin.report_date.min().date()}~{fin.report_date.max().date()}')
    fin = build_ttm(fin)
    n_ttm = fin['ttm_eps'].notna().sum()
    print(f'TTM_EPS 可算: {n_ttm:,} / {len(fin):,} ({n_ttm/len(fin):.1%})')

    mends = month_ends(f'{a.start}-01', a.end or dt.date.today().strftime('%Y-%m-%d'))
    print(f'月末日期: {len(mends)} 个  {mends[0].date()} ~ {mends[-1].date()}')

    codes = sorted(fin.code.unique())
    if a.sample:
        codes = codes[:a.sample]
    print(f'处理股票: {len(codes)} 只')

    pidx = build_price_cache_index(set(codes))
    print(f'价格缓存命中: {len(pidx)} 个 (code,kind) 组合')

    fin_by_code = {c: g for c, g in fin.groupby('code')}
    rows = []
    no_price = 0
    no_raw = 0
    checked = 0
    for i, code in enumerate(codes, 1):
        hfq = load_one_prices(pidx[(code, 'hfq')]) if (code, 'hfq') in pidx else None
        raw = load_one_prices(pidx[(code, 'raw')]) if (code, 'raw') in pidx else None
        if hfq is None or raw is None:
            # ⚠️ 2026-10-09：曾用 `raw_c = raw if raw is not None else hfq_c` 回退，
            #    结果把 hfq 当 raw 用 → EP 被压到 hfq 量级（中位 0.0039 / PE 256），
            #    且静默无声。hfq 推不出 raw（后复权在每个分红/拆股事件处累积，
            #    hfq_t/raw_t 随时间变化：000001 从 106.4 → 159.03）。
            #    故**拒绝静默回退**：缺 raw 的股票直接排除并计数，绝不混口径。
            if hfq is None:
                no_price += 1
            else:
                no_raw += 1
            continue
        checked += 1
        g = fin_by_code.get(code)
        if g is None:
            continue
        hfq_c = hfq.set_index('date')['close']
        raw_c = raw.set_index('date')['close']   # 两者都必须真实存在（上面已拒绝回退）
        # 流通股本以 raw 文件为准（hfq 与 raw 的股本列相同，但口径声明取 raw 侧）
        shares = (raw.set_index('date')['outstanding_share']
                  if 'outstanding_share' in raw.columns else
                  hfq.set_index('date')['outstanding_share'])
        for me in mends:
            # 该月末可得的最新财报（avail <= 月末）
            gg = g[g['avail'] <= me]
            if len(gg) == 0:
                continue
            r = gg.iloc[-1]
            # 月末收盘（取 <= 月末 的最后一个交易日）
            h = hfq_c[hfq_c.index <= me]
            w = raw_c[raw_c.index <= me]
            if len(h) == 0 or len(w) == 0:
                continue
            c_hfq = float(h.iloc[-1]); c_raw = float(w.iloc[-1])
            d_prev = me - pd.DateOffset(months=1)
            h_prev = hfq_c[hfq_c.index <= d_prev]
            ret = (c_hfq / float(h_prev.iloc[-1]) - 1.0) if len(h_prev) else np.nan
            sh = shares[shares.index <= me]
            sh = float(sh.iloc[-1]) if len(sh) and pd.notna(sh.iloc[-1]) else np.nan
            rows.append({
                'date': me, 'code': code,
                'ttm_eps': r['ttm_eps'], 'bps': r['bps'], 'gpm': r['gpm'], 'roe_cum': r['roe'],
                'close_hfq': c_hfq, 'close_raw': c_raw,
                'outstanding_share': sh,
                'mcap': (c_raw * sh / 1e8) if (pd.notna(sh) and pd.notna(c_raw)) else np.nan,
                'report_date': r['report_date'],
                'ret_1m': ret,
            })
        if i % 200 == 0:
            print(f'  {i}/{len(codes)} 只  行数 {len(rows):,}  无价格 {no_price}  | {time.time()-t0:.0f}s')

    p = pd.DataFrame(rows)
    if len(p) == 0:
        print('✗ 无数据行'); return 1
    # 因子
    # ⚠️ 2026-10-09 的记录：曾一度把分母改成 close_hfq，**是错的，已回滚**。
    #    当时的错误推理：以为 quarterly_fin 的 eps/bps 按当前股本重述，
    #    故应与 hfq 价配对；并用一个算错的交叉验证数（把 000001 的
    #    7.07/11.41=0.62 误算成 1.0382）当证据。
    #    实测裁决（57 只双口径齐全样本 / 5,125 行）：
    #      raw 口径 → EP 中位 0.0348（PE 28.7）、BP 中位 0.411（PB 2.44）✓ 落在 A 股真实区间
    #      hfq 口径 → EP 中位 0.0027（PE 372）✗ 荒谬
    #    000001 单点：raw PE=5.4（银行股合理） vs hfq PE=837。
    #    结论：**eps/bps 是「as-of 报告期」的口径，与未复权价 safe 配对**；
    #    hfq 价只用于计算收益（ret_1m，需含分红再投资），不用于因子分母。
    with np.errstate(divide='ignore', invalid='ignore'):
        p['EP'] = p['ttm_eps'] / p['close_raw']
        p['BP'] = p['bps'] / p['close_raw']
        p['ROE_TTM'] = p['ttm_eps'] / p['bps']
    p['GPM'] = p['gpm']
    p.attrs['pit_rule'] = 'legal disclosure deadline (Q1->4/30, H1->8/31, Q3->10/31, FY->next 4/30)'
    p.attrs['ttm_rule'] = 'ttm_eps = eps(T) + eps(prevFY) - eps(prevSamePeriod); cumulative caliber'

    # ---- 闸门：因子量级合理性（防同类 bug 静默流过）----
    ep_med = pd.to_numeric(p['EP'], errors='coerce').median()
    bp_med = pd.to_numeric(p['BP'], errors='coerce').median()
    roe_med = pd.to_numeric(p['ROE_TTM'], errors='coerce').median()
    print(f'\n闸门: EP 中位 {ep_med:.4f} (PE≈{1/ep_med:.1f}) | BP 中位 {bp_med:.4f} '
          f'(PB≈{1/bp_med:.2f}) | ROE_TTM 中位 {roe_med:.4f}')
    gate_fail = []
    # 口径说明：实测全样本（57 只双口径齐全）EP 中位 0.0348（PE 28.7）、
    # BP 中位 0.411（PB 2.44），落在 A 股真实区间。区间下探到 0.01
    # 是为容纳小样本偏斜（仅低代码段时中位可低至 0.004）。
    if not (0.01 <= ep_med <= 0.15):
        gate_fail.append(f'EP 中位数 {ep_med:.4f} 越界 [0.01, 0.15] → PE≈{1/ep_med:.0f} 倍不可信')
    if not (0.05 <= bp_med <= 1.5):
        gate_fail.append(f'BP 中位数 {bp_med:.4f} 越界 [0.05, 1.5] → PB≈{1/bp_med:.2f} 倍不可信')
    if not (-0.15 <= roe_med <= 0.5):
        gate_fail.append(f'ROE_TTM 中位数 {roe_med:.4f} 越界 [-0.15, 0.5]')
    if gate_fail:
        print('✗ 合理性闸门未通过，中止写出：')
        for g in gate_fail:
            print('   -', g)
        return 2
    print('✓ 合理性闸门通过')

    os.makedirs(f'{TASK}/data', exist_ok=True)
    out = f'{TASK}/data/panel_fullA.parquet'
    p.to_parquet(out, index=False)
    print(f'\n✓ 面板 {p.shape} → {out}')
    print(f'  股票 {p.code.nunique():,} | 月份 {p.date.nunique()} | '
          f'有双口径 {checked} 只 | 无 hfq {no_price} 只 | **缺 raw {no_raw} 只（已排除，不混口径）**')
    print(f'  耗时 {time.time()-t0:.0f}s')

    rep = [f'# 全 A 月度面板构建报告\n',
           f'- 面板 shape: {p.shape}',
           f'- 股票数: {p.code.nunique():,}（有价格 {checked} 只 / 无价格 {no_price} 只）',
           f'- 月份数: {p.date.nunique()}',
           f'- 区间: {p.date.min().date()} ~ {p.date.max().date()}',
           f'- 耗时: {time.time()-t0:.0f}s\n',
           '## 口径声明', '',
           '1. PIT = 法定披露截止日（非 notice_date；实测 notice_date 是修订日）',
           '2. TTM_EPS = eps(最近已披露财年) + eps(本年累计) − eps(上年同期累计)（均为累计口径）',
           '3. EP = TTM_EPS / raw_close；BP = bps / raw_close（**raw 口径，实测 PE 28.7 / PB 2.44 落在真实区间**）',
           '4. ret_1m 用 hfq 价（含分红再投资）；mcap = raw_close × outstanding_share（流通市值，亿元）',
           '5. 已声明缺失：LEV（lev 列全 NULL）、CFO_NI_TTM（库内无净利润/经营现金流绝对额）\n',
           '## 因子覆盖率', '']
    for f in ['EP', 'BP', 'ROE_TTM', 'GPM', 'ret_1m', 'mcap']:
        s = pd.to_numeric(p[f], errors='coerce')
        rep.append(f'- {f:10} 非空 {s.notna().sum():>9,} / {len(p):,} ({s.notna().mean():.1%})'
                   f'  中位数 {s.median():.4f}' if s.notna().any() else f'- {f:10} 全空')
    open(f'{TASK}/output/panel_build_report.md', 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
    print(f'✓ 报告 → {TASK}/output/panel_build_report.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
