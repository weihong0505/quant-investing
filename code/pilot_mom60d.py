# -*- coding: utf-8 -*-
"""
pilot_mom60d.py — S1 试点：价格类因子真实数据检验（MOM_60D / VOL_RATIO）
======================================================================
数据：新浪（akshare stock_zh_a_daily，hfq+raw）个股日线 + spot 快照选股 +
      yjbb 财务（行业映射）。样本 2023-02 ~ 2026-07（~42 月，<60 月 → 结论降级"初步"）。
状态标注：S1 试点脚本——未审批/未检验（实验），全部结论为"初步"（见 docs/factor_docs/test_MOM_60D_20260822.md / test_VOL_RATIO_20260822.md）

局限（如实记录于报告）：
  1. 仅现存股票（新浪源无退市股历史）→ 幸存者偏差无法消除（v3 §3-3 声明）
  2. 市值 = raw 收盘价 × 流通股本（volume/turnover 推算）→ 流通市值代理，非总市值
  3. ST 仅按当前名称剔除（历史 ST 状态不可得）
  4. 行业 = yjbb 最新一期快照（非逐期 PIT）
  5. 主判定样本起点应为 2017-01（v3 §3-5），本试点数据不足 → 全部结论为"初步"

用法：
  D:/pyh/python.exe -E pilot_mom60d.py [--max-stocks 120] [--start 2021-01-01]
      [--no-fetch]   # 复用 data_cache 已缓存日线
输出：
  code/data_cache/pilot_hist_{sym}_{hfq|raw}.parquet（日线缓存）
  code/data_cache/pilot_mom60d_{factor|ret|mcap|tradable|st|fin}_{date}.parquet
  docs/factor_docs/test_MOM_60D_{date}.md / test_VOL_RATIO_{date}.md
  docs/factor_docs/backfill_*_{date}.md（registry 追加式回填行）
"""
import os
import sys
import time
import warnings
import datetime as _dt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

# ---- 代理三件套（import requests 之前）----
os.environ['NO_PROXY'] = '*'; os.environ['no_proxy'] = '*'
for k in list(os.environ):
    if 'proxy' in k.lower():
        os.environ.pop(k, None)
import requests
_orig = requests.Session.request


def _no_proxy(self, method, url, **kwargs):
    kwargs['proxies'] = {'http': None, 'https': None}
    kwargs.setdefault('timeout', 30)
    return _orig(self, method, url, **kwargs)


requests.Session.request = _no_proxy
import akshare as ak

from factor_test_suite import run_pipeline, render_markdown, registry_backfill_md

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, 'data_cache')
REPORT_DIR = os.path.join(os.path.dirname(BASE), 'docs', 'factor_docs')
TODAY = _dt.date.today().strftime('%Y%m%d')
SAMPLE_START = '2023-02'       # 试点样本起点（主判定应为 2017-01，见文件头局限 5）
FETCH_START = '2021-01-01'     # 拉数起点（≥180 交易日窗口：MOM60 + 次新120）

BOARD_LIMIT = {'60': 0.095, '00': 0.095, '30': 0.195, '68': 0.195}


def _limit(code):
    for pfx, lim in BOARD_LIMIT.items():
        if code.startswith(pfx):
            return lim
    return 0.095


def select_universe(spot_path, n=120, seed=20260822):
    """从 spot 快照分层抽样（主板/创业板/科创板），剔 ST、北交所。"""
    spot = pd.read_parquet(spot_path)
    spot = spot[spot['代码'].str.startswith(('sh', 'sz'))].copy()
    spot['code6'] = spot['代码'].str[2:]
    spot = spot[~spot['名称'].str.contains('ST', na=False)]
    spot = spot[spot['code6'].str.match(r'^(60|00|30|68)\d{4}$')]
    rng = np.random.default_rng(seed)
    boards = {'60': n // 3, '00': n // 3, '30': n // 6, '68': n // 6}
    picks = []
    for pfx, k in boards.items():
        sub = spot[spot['code6'].str.startswith(pfx)]
        if len(sub) == 0:
            continue
        picks += list(rng.choice(sub['代码'].tolist(), size=min(k, len(sub)),
                                 replace=False))
    picks = sorted(set(picks))
    return picks, spot.set_index('代码')['名称'].to_dict()


def fetch_daily(sym, adjust, start_date, end_date, cache_dir, retry=3):
    """新浪日线（hfq/raw），parquet 缓存。"""
    cache_path = os.path.join(cache_dir, f'pilot_hist_{sym}_{adjust}.parquet')
    if os.path.exists(cache_path):
        df = pd.read_parquet(cache_path)
        if len(df) > 100:
            return df
    last_err = None
    for i in range(retry):
        try:
            df = ak.stock_zh_a_daily(symbol=sym, start_date=start_date,
                                     end_date=end_date, adjust=adjust)
            if df is None or len(df) == 0:
                raise RuntimeError('empty')
            df.to_parquet(cache_path)
            time.sleep(0.25)
            return df
        except Exception as e:
            last_err = e
            time.sleep(2 * (i + 1))
    print(f'[WARN] fetch fail {sym} {adjust}: {last_err}')
    return None


def build_monthly_tables(daily_hfq, daily_raw, start='2023-02'):
    """由日线构建月度宽表：因子/收益/市值/可交易掩码。"""
    codes = sorted(set(daily_hfq.keys()) & set(daily_raw.keys()))
    # 交易日历 = 全体日期的并集（对齐用）
    all_days = sorted(set().union(*[set(d['date']) for d in daily_hfq.values()]))
    cal = pd.DatetimeIndex(all_days)
    # 月末 = 当月最后一个交易日（end_time 是自然月末，可能非交易日）
    month_ends = cal.to_series().groupby(cal.to_period('M')).max()
    month_ends = pd.DatetimeIndex(month_ends.values)
    month_ends = pd.DatetimeIndex(sorted(set(month_ends)))
    month_ends = month_ends[month_ends >= pd.Timestamp(start)]

    close = pd.DataFrame(index=cal, columns=codes, dtype=float)
    vol = pd.DataFrame(index=cal, columns=codes, dtype=float)
    raw_close = pd.DataFrame(index=cal, columns=codes, dtype=float)
    shares = pd.DataFrame(index=cal, columns=codes, dtype=float)
    first_bar = {}
    for c in codes:
        dh = daily_hfq[c].set_index('date')
        dh.index = pd.DatetimeIndex(dh.index)
        dr = daily_raw[c].set_index('date')
        dr.index = pd.DatetimeIndex(dr.index)
        first_bar[c] = dh.index.min()
        close.loc[dh.index, c] = dh['close'].values
        vol.loc[dh.index, c] = dh['volume'].values
        raw_close.loc[dr.index, c] = dr['close'].values
        # 流通股本推算：volume/turnover（历史值），逐日
        to = dh['turnover']
        sh = dh['volume'] / to.replace(0, np.nan)
        shares.loc[sh.index, c] = sh.values
    close = close.ffill()
    raw_close = raw_close.ffill()
    shares = shares.ffill()

    # 月度因子（T 月末）
    mom, vratio, mc = {}, {}, {}
    ret = {}
    tradable = {}
    cal_set = set(cal)
    for i, t in enumerate(month_ends):
        # 60 交易日前的日期（前 60 个交易日，含 T）
        pos = cal.get_loc(t) if t in cal else None
        if pos is None or pos < 60:
            continue
        t60 = cal[pos - 60]
        prev_me = month_ends[i - 1] if i > 0 else None
        for c in codes:
            cc = close.loc[t, c]
            bar_at_t = np.isfinite(vol.loc[t, c]) and vol.loc[t, c] > 0  # T 月末有实际成交（非停牌）
            if not np.isfinite(cc):
                continue
            if not bar_at_t:
                # T 期停牌：剔除（v3 §3-3），无因子值无收益
                tradable.setdefault(c, {})[t] = False
                continue
            # MOM_60D（T 月末停牌 → 用最后成交价，但标记不可交易）
            c60 = close.loc[t60, c]
            if np.isfinite(c60) and c60 > 0:
                mom.setdefault(c, {})[t] = cc / c60 - 1.0
            # VOL_RATIO：T 日量 / 前 5 交易日均量
            v_t = vol.loc[t, c]
            if np.isfinite(v_t) and pos >= 5:
                v5 = vol.iloc[max(0, pos - 5):pos][c]
                v5 = v5[v5 > 0]
                if len(v5):
                    vratio.setdefault(c, {})[t] = v_t / v5.mean()
            # 收益（T→T+1）：月末 close 比值；T 月末停牌 → 该期收益剔除（v3 §3-3 T 期停牌）
            if prev_me is not None and bar_at_t:
                c0 = close.loc[prev_me, c]
                if np.isfinite(c0) and c0 > 0 and np.isfinite(cc):
                    ret.setdefault(c, {})[t] = cc / c0 - 1.0
            # 流通市值代理（亿元）
            rc = raw_close.loc[t, c]
            sh = shares.loc[t, c]
            if np.isfinite(rc) and np.isfinite(sh) and sh > 0:
                mc.setdefault(c, {})[t] = rc * sh / 1e8
            # T+1 可交易性：持有月内停牌≥5 日 或 一字板≥5 日 → 剔除
            if prev_me is not None:
                m_lo, m_hi = prev_me, t
                days = [d for d in cal_set if m_lo <= d <= m_hi]
                susp = sum(1 for d in days if not np.isfinite(vol.loc[d, c]) or vol.loc[d, c] == 0)
                lim = _limit(c)
                one_word = 0
                cl = close.loc[days, c].values
                vv = vol.loc[days, c].values
                hl = None
                dhc = daily_hfq[c].set_index('date')
                if 'high' in dhc.columns and 'low' in dhc.columns:
                    h_ = dhc['high'].reindex(days).values
                    l_ = dhc['low'].reindex(days).values
                    for k in range(1, len(cl)):
                        if np.isfinite(cl[k]) and np.isfinite(cl[k - 1]) and cl[k - 1] > 0:
                            r = cl[k] / cl[k - 1] - 1
                            if np.isfinite(h_[k]) and np.isfinite(l_[k]) and h_[k] == l_[k] and abs(r) >= lim:
                                one_word += 1
                if susp >= 5 or one_word >= 5:
                    tradable.setdefault(c, {})[t] = False
                else:
                    tradable.setdefault(c, {})[t] = True

    def _wide(d):
        # d = {code: {date: val}} → 直接 DataFrame：index=date(union), columns=code
        return pd.DataFrame(d).sort_index() if d else pd.DataFrame()

    f_mom = _wide(mom)
    f_vol = _wide(vratio)
    r = _wide(ret)
    m = _wide(mc)
    tr = _wide(tradable).astype(bool)
    # 列名统一为 6 位代码（与财务表对齐）
    for tbl in (f_mom, f_vol, r, m, tr):
        if len(tbl):
            tbl.columns = [c[2:] for c in tbl.columns]
    first_bar = {k[2:]: v for k, v in first_bar.items()}
    # 次新剔除：首 bar 距样本起点 <120 交易日
    start_ts = pd.Timestamp(start)
    new_ok = {c for c, fb in first_bar.items() if fb <= start_ts - pd.Timedelta(days=240)}
    for tbl in (f_mom, f_vol, r, m, tr):
        if len(tbl):
            tbl.drop(columns=[c for c in tbl.columns if c not in new_ok], inplace=True)
    return f_mom, f_vol, r, m, tr, first_bar


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--max-stocks', type=int, default=120)
    p.add_argument('--start', default='2021-01-01')
    p.add_argument('--sample-start', default=SAMPLE_START)
    p.add_argument('--no-fetch', action='store_true')
    p.add_argument('--skip-mom', action='store_true')
    p.add_argument('--skip-vol', action='store_true')
    args = p.parse_args()

    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)

    spot_path = os.path.join(CACHE, 'spot_20260822.parquet')
    picks, names = select_universe(spot_path, args.max_stocks)
    print(f'[universe] {len(picks)} stocks sampled')

    # ---- 拉数 ----
    daily_hfq, daily_raw = {}, {}
    for i, sym in enumerate(picks):
        if not args.no_fetch:
            dh = fetch_daily(sym, 'hfq', args.start, '20260822', CACHE)
            dr = fetch_daily(sym, '', args.start, '20260822', CACHE)
        else:
            dh = fetch_daily(sym, 'hfq', args.start, '20260822', CACHE)
            dr = fetch_daily(sym, '', args.start, '20260822', CACHE)
        if dh is not None and len(dh) > 100:
            daily_hfq[sym] = dh
        if dr is not None and len(dr) > 100:
            daily_raw[sym] = dr
        if (i + 1) % 20 == 0:
            print(f'[fetch] {i + 1}/{len(picks)}')
    print(f'[fetch] done: hfq={len(daily_hfq)} raw={len(daily_raw)}')

    # ---- 建月度表 ----
    f_mom, f_vol, r, m, tr, first_bar = build_monthly_tables(
        daily_hfq, daily_raw, args.sample_start)
    print(f'[tables] MOM {f_mom.shape} VOL {f_vol.shape} RET {r.shape} '
          f'MCAP {m.shape} TRADABLE {tr.shape}')
    if len(f_mom) < 24:
        print('[ERROR] too few months; abort')
        sys.exit(1)

    # ---- 财务表（行业映射，最新一期快照）----
    fin = pd.read_parquet(os.path.join(CACHE, 'yjbb_20260630.parquet'))
    fin['股票代码'] = fin['股票代码'].astype(str).str.zfill(6)
    fin['代码6'] = fin['股票代码']
    fin_use = fin[['代码6', '所处行业']].rename(columns={'代码6': '股票代码'})

    # ---- 保存宽表缓存 ----
    factor_key = {'MOM_60D': 'mom_60d', 'VOL_RATIO': 'vol_ratio'}
    for nm, tbl in (('factor_mom_60d', f_mom), ('factor_vol_ratio', f_vol),
                    ('ret', r), ('mcap', m), ('tradable', tr)):
        tbl.to_parquet(os.path.join(CACHE, f'pilot_mom60d_{nm}_{TODAY}.parquet'))
    fin_use.to_parquet(os.path.join(CACHE, f'pilot_mom60d_fin_{TODAY}.parquet'))

    # ---- 运行检验 ----
    results = []
    if not args.skip_mom:
        results.append(('MOM_60D', f_mom, 1))
    if not args.skip_vol and len(f_vol) >= 24:
        results.append(('VOL_RATIO', f_vol, 1))
    for nm, fac, sign in results:
        print(f'[run] {nm} sign={sign:+d} months={len(fac)} stocks={fac.shape[1]}')
        rpt = run_pipeline(fac, r, m, fin_use, name=nm, expected_sign=sign,
                           n_star=10, start=args.sample_start, oos_months=24,
                           registry_no=None, registered_ts=_dt.date.today().isoformat(),
                           factor_type={'MOM_60D': '动量', 'VOL_RATIO': '情绪'}[nm],
                           input_files=[spot_path,
                                        os.path.join(CACHE, f'pilot_mom60d_factor_{factor_key[nm]}_{TODAY}.parquet'),
                                        os.path.join(CACHE, f'pilot_mom60d_ret_{TODAY}.parquet'),
                                        os.path.join(CACHE, f'pilot_mom60d_mcap_{TODAY}.parquet')])
        md = render_markdown(rpt)
        out = os.path.join(REPORT_DIR, f'test_{nm}_{TODAY}.md')
        with open(out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(md)
        bf = os.path.join(REPORT_DIR, f'backfill_{nm}_{TODAY}.md')
        with open(bf, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('registry 追加式回填行（原行不动，防改口三件套）：\n\n')
            fh.write(registry_backfill_md(rpt) + '\n')
        print(f'[OK] {nm}: verdict={rpt["verdict"]["verdict"]} '
              f'icir={rpt["ic"]["icir"]:.3f} signed_t={rpt["ic"]["signed_t"]:.2f} '
              f'pt_p={rpt["pt_mr"]["p"]:.4f} econ_ann={rpt["econ"]["net_ls_ann_x12"]:.2%} '
              f'sharpe={rpt["econ"]["sharpe"]:.2f} 2x={rpt["econ"]["net_ls_2x_positive"]}')
        print(f'[OK] report -> {out}')


if __name__ == '__main__':
    main()
