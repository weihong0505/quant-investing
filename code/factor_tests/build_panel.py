# -*- coding: utf-8 -*-
"""
S1/M5 试点检验 - 月度面板构建
输入: data_cache/tx_raw_*.parquet (腾讯raw日线) + yjbb_*/zcfz_*/fhps_* (东财)
输出: data_cache/panel_monthly.parquet

面板列 (month-end T):
  date, code, ret_next (T+1月总收益, 红利再投资口径), 
  EP, BP, ROE_TTM, GPM, CFO_NI_TTM, LEV, MOM_60D, LOG_MCAP,
  industry, mcap_est (亿元, 用于成本分档), raw_close, shares_est,
  st_flag, age_days, susp_next, board_next, ret_t3 (T+1~T+3复合)
数据版本: 输入文件 sha256 manifest 写入 parquet 全局元数据
用法: D:/pyh/python.exe -E factor_tests/build_panel.py
"""
import os, sys, time, glob, hashlib, json
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
import numpy as np

BASE = r'G:/股市探究/quant-investing/code'
CACHE = os.path.join(BASE, 'data_cache')
PANEL_START = '2016-09-01'   # 价格起点(60日动量+120日上市龄需要更早)
PANEL_MONTHS_START = '2017-01'

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:16]

# ---------------- 1. 分红送转事件表 ----------------
def load_events():
    """返回 {code6: DataFrame(ex_date, cash_per_share, split_ratio)}"""
    ev = {}
    for f in sorted(glob.glob(os.path.join(CACHE, 'fhps_*.parquet'))):
        df = pd.read_parquet(f)
        df = df[df['方案进度'].astype(str).str.contains('实施', na=False)].copy()
        df['代码'] = df['代码'].astype(str).str.zfill(6)
        for _, r in df.iterrows():
            ex = str(r.get('除权除息日', ''))
            if not ex or ex == 'nan' or pd.isna(ex):
                continue
            code = r['代码']
            cash = pd.to_numeric(r.get('现金分红-现金分红比例', np.nan), errors='coerce')
            split = pd.to_numeric(r.get('送转股份-送转总比例', np.nan), errors='coerce')
            cash = cash / 10.0 if pd.notna(cash) else 0.0
            split = split / 10.0 if pd.notna(split) else 0.0
            if cash == 0 and split == 0:
                continue
            ev.setdefault(code, []).append((pd.Timestamp(ex), cash, split))
    out = {}
    for c, rows in ev.items():
        d = pd.DataFrame(rows, columns=['ex_date', 'cash', 'split']).sort_values('ex_date')
        d['cum_split'] = (1 + d['split']).cumprod()
        out[c] = d
    return out

# ---------------- 2. 财务 PIT 表 ----------------
def load_financials():
    """yjbb: {quarter: df}; zcfz: {quarter: df}"""
    yjbb, zcfz = {}, {}
    for f in sorted(glob.glob(os.path.join(CACHE, 'yjbb_*.parquet'))):
        q = os.path.basename(f)[5:13]
        yjbb[q] = pd.read_parquet(f)
    for f in sorted(glob.glob(os.path.join(CACHE, 'zcfz_*.parquet'))):
        q = os.path.basename(f)[5:13]
        zcfz[q] = pd.read_parquet(f)
    return yjbb, zcfz

def build_fin_panel(yjbb, zcfz, month_ends):
    """
    每股股票每月: 最新报告期(公告日<=T)的 EPS累计/净利润/BPS/OCFPS/毛利率/行业 + TTM EPS
    """
    # 长表 yjbb
    frames = []
    for q, d in yjbb.items():
        sub = d[['股票代码', '股票简称', '每股收益', '每股净资产', '每股经营现金流量',
                 '销售毛利率', '净利润-净利润', '所处行业', '最新公告日期']].copy()
        sub['报告期'] = q
        frames.append(sub)
    fin = pd.concat(frames, ignore_index=True)
    fin['股票代码'] = fin['股票代码'].astype(str).str.zfill(6)
    fin['公告日期'] = pd.to_datetime(fin['最新公告日期'], errors='coerce')
    for c in ('每股收益', '每股净资产', '每股经营现金流量', '销售毛利率', '净利润-净利润'):
        fin[c] = pd.to_numeric(fin[c], errors='coerce')
    fin = fin.dropna(subset=['公告日期'])

    # TTM 需要的同比期: 对每个报告期 q, 需要 q_prev_year (去年同期) 和 annual_prev (去年年报)
    eps_by_q = {q: fin[fin['报告期'] == q].set_index('股票代码')['每股收益'] for q in fin['报告期'].unique()}
    ocf_by_q = {q: fin[fin['报告期'] == q].set_index('股票代码')['每股经营现金流量'] for q in fin['报告期'].unique()}
    fin['EPS_TTM'] = np.nan
    fin['OCFPS_TTM'] = np.nan
    for q in fin['报告期'].unique():
        y, m = int(q[:4]), q[4:]
        q_prev = f'{y-1}{m}'
        annual_prev = f'{y-1}1231'
        eps_cur = eps_by_q.get(q); eps_qp = eps_by_q.get(q_prev); eps_ap = eps_by_q.get(annual_prev)
        ocf_cur = ocf_by_q.get(q); ocf_qp = ocf_by_q.get(q_prev); ocf_ap = ocf_by_q.get(annual_prev)
        idx = fin['报告期'] == q
        if m == '1231':
            fin.loc[idx, 'EPS_TTM'] = eps_cur.reindex(fin.loc[idx, '股票代码']).values
            fin.loc[idx, 'OCFPS_TTM'] = ocf_cur.reindex(fin.loc[idx, '股票代码']).values
        elif eps_qp is not None and eps_ap is not None:
            codes = fin.loc[idx, '股票代码']
            ttm = eps_cur.reindex(codes).values + eps_ap.reindex(codes).values - eps_qp.reindex(codes).values
            fin.loc[idx, 'EPS_TTM'] = ttm
            if ocf_cur is not None and ocf_qp is not None and ocf_ap is not None:
                fin.loc[idx, 'OCFPS_TTM'] = (ocf_cur.reindex(codes).values + ocf_ap.reindex(codes).values
                                             - ocf_qp.reindex(codes).values)

    # zcfz 长表 (LEV)
    zframes = []
    for q, d in zcfz.items():
        sub = d[['股票代码', '资产负债率', '公告日期']].copy()
        sub['报告期'] = q
        zframes.append(sub)
    zfin = pd.concat(zframes, ignore_index=True)
    zfin['股票代码'] = zfin['股票代码'].astype(str).str.zfill(6)
    zfin['资产负债率'] = pd.to_numeric(zfin['资产负债率'], errors='coerce')
    zfin['公告日期'] = pd.to_datetime(zfin['公告日期'], errors='coerce')
    zfin = zfin.dropna(subset=['公告日期'])

    # 逐月 PIT: 最近公告日 <= T 的行
    rows = []
    for T in month_ends:
        f = fin[fin['公告日期'] <= T].sort_values('公告日期')
        f = f.groupby('股票代码').last().reset_index()
        f['date'] = T
        z = zfin[zfin['公告日期'] <= T].sort_values('公告日期')
        z = z.groupby('股票代码').last().reset_index()[['股票代码', '资产负债率']]
        m = f.merge(z, on='股票代码', how='left')
        rows.append(m)
    return pd.concat(rows, ignore_index=True)

# ---------------- 3. 价格面板 ----------------
def build_price_panel(month_ends, events):
    """
    每股: 日线 raw -> 日总收益(事件调整) -> 月收益/MOM60/上市龄/停牌/一字板
    返回 {code: DataFrame(date, ret_next, mom60, raw_close, age_days, susp_next, board_next, ret_t3, ret_t6, ret_t12)}
    """
    cal = None
    files = sorted(glob.glob(os.path.join(CACHE, 'tx_raw_sh600000.parquet')))
    if files:
        cal_df = pd.read_parquet(files[0])
        cal = pd.to_datetime(cal_df['date']).dt.strftime('%Y-%m-%d').tolist()
    # 交易日历 = sh600000 的全部交易日
    if cal is None:
        raise RuntimeError('sh600000 价格缓存缺失, 无法建立日历')

    cal_set = set(cal)
    # 月度边界: 每月最后交易日
    month_end_dates = [pd.Timestamp(d) for d in cal if d[:7] in {t.strftime('%Y-%m') for t in month_ends}]
    me_by_month = {}
    for d in month_end_dates:
        me_by_month[d.strftime('%Y-%m')] = d
    month_ends = sorted(me_by_month.values())

    all_frames = []
    n_files = len(glob.glob(os.path.join(CACHE, 'tx_raw_*.parquet')))
    t0 = time.time()
    for i, f in enumerate(sorted(glob.glob(os.path.join(CACHE, 'tx_raw_*.parquet')))):
        code = os.path.basename(f)[7:13]
        df = pd.read_parquet(f)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        for c in ('open', 'close', 'high', 'low', 'volume'):
            df[c] = pd.to_numeric(df[c], errors='coerce')
        df = df.dropna(subset=['close'])
        if len(df) < 30:
            continue
        ev = events.get(code)
        # 日总收益
        close = df['close'].values.astype(float)
        r = np.zeros(len(df))
        r[1:] = close[1:] / close[:-1] - 1.0
        if ev is not None and len(ev) > 0:
            exmap = {pd.Timestamp(d): (cash, split) for d, cash, split in zip(ev['ex_date'], ev['cash'], ev['split'])}
            dates = df['date'].values
            for j in range(1, len(df)):
                key = pd.Timestamp(dates[j])
                if key in exmap:
                    cash, split = exmap[key]
                    # 除权日总收益 = (P_t*(1+split)+cash)/P_{t-1} - 1
                    r[j] = (close[j] * (1 + split) + cash) / close[j - 1] - 1.0
        df['ret_d'] = r
        # 复利指数
        idx = np.cumprod(1 + r)
        df['idx'] = idx
        dates_str = df['date'].dt.strftime('%Y-%m-%d').tolist()
        pos = {d: k for k, d in enumerate(dates_str)}
        # 月边界收益
        out = []
        for T in month_ends:
            ts = T.strftime('%Y-%m-%d')
            if ts not in pos:
                continue
            k = pos[ts]
            # ret_next: T 到下一月末
            nxt = None
            for T2 in month_ends:
                if T2 > T:
                    nxt = T2
                    break
            if nxt is None:
                continue
            nts = nxt.strftime('%Y-%m-%d')
            if nts not in pos:
                continue
            k2 = pos[nts]
            ret_next = idx[k2] / idx[k] - 1.0
            # MOM60: 60 交易日前
            k60 = max(0, k - 60)
            mom60 = idx[k] / idx[k60] - 1.0 if k60 < k else np.nan
            # age: 上市龄(交易日数)
            age = k + 1
            # susp_next: T+1 月缺失交易日数 (停牌)
            month1_days = [d for d in cal if T < pd.Timestamp(d) <= nxt]
            have = sum(1 for d in month1_days if d in pos)
            susp_next = len(month1_days) - have
            # board_next: 一字板天数 (open==high==low==close)
            board = 0
            for d in month1_days:
                if d in pos:
                    jj = pos[d]
                    if df['open'].iloc[jj] == df['high'].iloc[jj] == df['low'].iloc[jj] == df['close'].iloc[jj]:
                        board += 1
            # ret_t3 / t6 / t12 (复合)
            def fwd_ret(days):
                kk = pos.get(days)
                if kk is None:
                    return np.nan
                return idx[kk] / idx[k] - 1.0
            # T+3月: 跳过3个月末
            t3 = t6 = t12 = np.nan
            ends_after = [T2 for T2 in month_ends if T2 > T]
            if len(ends_after) >= 3:
                t3 = idx[pos[ends_after[2].strftime('%Y-%m-%d')]] / idx[k] - 1.0
            if len(ends_after) >= 6:
                t6 = idx[pos[ends_after[5].strftime('%Y-%m-%d')]] / idx[k] - 1.0
            if len(ends_after) >= 12:
                t12 = idx[pos[ends_after[11].strftime('%Y-%m-%d')]] / idx[k] - 1.0
            out.append((T, ret_next, mom60, close[k], age, susp_next, board, t3, t6, t12))
        if out:
            odf = pd.DataFrame(out, columns=['date', 'ret_next', 'mom60', 'raw_close', 'age_days',
                                             'susp_next', 'board_next', 'ret_t3', 'ret_t6', 'ret_t12'])
            odf['code'] = code
            all_frames.append(odf)
        if (i + 1) % 500 == 0:
            print(f"[prices] {i+1}/{n_files} {time.time()-t0:.0f}s", flush=True)
    return pd.concat(all_frames, ignore_index=True)

# ---------------- 4. 主流程 ----------------
def main():
    month_ends = pd.date_range('2017-01-31', '2026-07-31', freq='ME')
    events = load_events()
    print(f"[events] {len(events)} stocks with corp actions", flush=True)

    price_panel = build_price_panel(month_ends, events)
    print(f"[price panel] {price_panel.shape}", flush=True)
    price_panel.to_parquet(os.path.join(CACHE, 'panel_prices.parquet'), index=False)

    yjbb, zcfz = load_financials()
    print(f"[fin] yjbb {len(yjbb)} q, zcfz {len(zcfz)} q", flush=True)
    fin_panel = build_fin_panel(yjbb, zcfz, month_ends)
    print(f"[fin panel] {fin_panel.shape}", flush=True)

    # ---- 合并 ----
    p = price_panel.copy()
    p['date'] = pd.to_datetime(p['date'])
    f = fin_panel.copy()
    f['date'] = pd.to_datetime(f['date'])
    m = p.merge(f, on=['date', '股票代码' if '股票代码' in f.columns else 'code'], how='left')
    # 统一 code 列
    if '股票代码' in m.columns:
        m['code'] = m['股票代码']
        m = m.drop(columns=['股票代码'])
    m = m.rename(columns={'股票简称': 'name_fin'})

    # 送转累计因子: 每股因子归一 (EPS/BPS 以当前股本计)
    # cum_split at date d = Π_{exdate<=d}(1+split); EPS_T_units = EPS_rep * cum_T/cum_rep
    m['cum_split'] = 1.0
    m['cum_split_rep'] = 1.0
    ev_codes = set(events.keys())
    for code in ev_codes:
        ev = events[code]
        mask = m['code'] == code
        if not mask.any():
            continue
        dts = m.loc[mask, 'date'].values
        cs = np.ones(len(dts))
        for ex, sp in zip(ev['ex_date'], ev['split']):
            cs[dts >= np.datetime64(ex)] *= (1 + sp)
        m.loc[mask, 'cum_split'] = cs
    # 报告期的 cum_split: 用公告日期近似 (公告日当天股本已含此前事件)
    # 简化: 对每股因子, 直接用 (cum_split_T / cum_split_rep); cum_split_rep 用报告期最后一天近似
    # 这里更精确做法: EPS_units = EPS_rep * cum_T / cum_rep_q, cum_rep_q = Π_{exdate <= 报告期末}(1+split)
    # 报告期末 = 报告期 q 的季末日期
    rep_end = m['报告期'].astype(str).str[:4] + '-' + m['报告期'].astype(str).str[4:6] + '-' + {
        '0331': '31', '0630': '30', '0930': '30', '1231': '31'}.get('', '30')
    # 简化实现: 用字典查找
    qmap = {'0331': '-03-31', '0630': '-06-30', '0930': '-09-30', '1231': '-12-31'}
    rep_end = m['报告期'].astype(str).str[:4] + m['报告期'].astype(str).str[4:].map(qmap)
    rep_end = pd.to_datetime(rep_end, errors='coerce')
    m['cum_split_rep'] = 1.0
    for code in ev_codes:
        ev = events[code]
        mask = (m['code'] == code) & rep_end.notna()
        if not mask.any():
            continue
        dts = rep_end[mask].values
        cs = np.ones(len(dts))
        for ex, sp in zip(ev['ex_date'], ev['split']):
            cs[dts >= np.datetime64(ex)] *= (1 + sp)
        m.loc[mask, 'cum_split_rep'] = cs

    adj = m['cum_split'] / m['cum_split_rep'].replace(0, np.nan)
    m['EP'] = m['EPS_TTM'] * adj / m['raw_close']
    m['BP'] = m['每股净资产'] * adj / m['raw_close']
    m['ROE_TTM'] = m['EPS_TTM'] / m['每股净资产'].replace(0, np.nan)
    m['GPM'] = m['销售毛利率']
    m['CFO_NI_TTM'] = m['OCFPS_TTM'] / m['EPS_TTM'].replace(0, np.nan)
    m['LEV'] = m['资产负债率']
    m['MOM_60D'] = m['mom60'] * 100.0
    # LOG_MCAP: 股本估计 = 净利润/EPS (最新报告期, 当前股本) -> shares_T = shares_rep * cum_T/cum_rep
    shares_rep = m['净利润-净利润'] / m['每股收益'].replace(0, np.nan)
    m['shares_est'] = shares_rep * adj
    m['mcap_est'] = m['raw_close'] * m['shares_est'] / 1e8  # 亿元
    m['LOG_MCAP'] = np.log(np.maximum(m['mcap_est'], 1e-6))
    m['industry'] = m['所处行业'].fillna('未知')
    # ST 标记 (报告简称含ST)
    m['st_flag'] = m['name_fin'].astype(str).str.contains('ST', na=False)

    # 输出列
    cols = ['date', 'code', 'ret_next', 'ret_t3', 'ret_t6', 'ret_t12', 'EP', 'BP', 'ROE_TTM', 'GPM',
            'CFO_NI_TTM', 'LEV', 'MOM_60D', 'LOG_MCAP', 'industry', 'mcap_est', 'raw_close',
            'age_days', 'susp_next', 'board_next', 'st_flag', '报告期', 'name_fin']
    out = m[cols].copy()
    out['ret_next'] = pd.to_numeric(out['ret_next'], errors='coerce')
    out['ret_t3'] = pd.to_numeric(out['ret_t3'], errors='coerce')
    out['ret_t6'] = pd.to_numeric(out['ret_t6'], errors='coerce')
    out['ret_t12'] = pd.to_numeric(out['ret_t12'], errors='coerce')

    # 数据版本 manifest
    manifest = {}
    for pat in ('tx_raw_*.parquet', 'yjbb_*.parquet', 'zcfz_*.parquet', 'fhps_*.parquet', 'spot_*.parquet'):
        files = sorted(glob.glob(os.path.join(CACHE, pat)))
        for f in files[-3:]:
            manifest[os.path.basename(f)] = sha256_file(f)
    out.attrs['manifest'] = json.dumps(manifest)
    out.to_parquet(os.path.join(CACHE, 'panel_monthly.parquet'), index=False)
    print(f"[panel] saved {out.shape} rows", flush=True)
    print("[PANEL DONE]", flush=True)

if __name__ == '__main__':
    main()
