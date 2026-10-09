# -*- coding: utf-8 -*-
"""
e2e_pipeline.py — 端到端回测管线（S2 验收）
============================================
数据(data_fetcher) → 因子(价格类) → 信号(sell_signals) → 引擎(backtest) → 报告(HTML/MD) + 日志
状态标注：S2 部分验收（2026-08-22，CSI300 试点子集跑通；全量真实数据端到端策略验证未完成）；组件审批/检验依据见各模块头部

管线阶段:
  Stage 1 数据准备
    1a 股票池: CSI300 成分(新浪 index_stock_cons) 或 自定义列表; 退市股名单(沪深交易所终止上市) 纳入验证
    1b 个股历史行情: 东财 stock_zh_a_hist(断路器, 封禁后跳过) → 新浪 stock_zh_a_daily(raw+hfq)
        退市股: 腾讯 stock_zh_a_hist_tx(raw; hfq 缺失以 raw 代, 声明)
    1c 总市值: 腾讯 qt.gtimg.cn 实时行情(字段45=总市值亿元) → 历史市值 = 总股本 × raw收盘(估算, 声明)
    1d ETF 基准: 东财 fund_etf_hist_em(qfq, 封禁) → 新浪 fund_etf_hist_sina(raw, 声明) → 腾讯 hist_tx(raw)
    1e 财务数据: data_cache 缓存命中即用; 未命中尝试东财并声明
  Stage 2 因子与信号
    2a 因子(月度截面): MOM_60D = hfq收盘 t / hfq收盘 t-60交易日 - 1; TURNOVER_20D = 20日均换手率(成交量/流通股本)
    2b 得分 = 0.7×z(MOM) + 0.3×z(TURN) (winsorize ±3, 缺数据 NaN 不入选)
    2c 信号: sell_signals.generate_signals(等权 Top-N, 时间止盈6月/止损-15%/冷却3月, T+1开盘成交价口径)
  Stage 3 引擎回测
    BacktestEngine(calendar/raw开收/hfq/市值/tradable/ST) + 基准对比(超额年化/相对回撤/IR)
  Stage 4 报告与日志
    output/backtest_{策略名}_{YYYYMMDD}.html + output/pick_{YYYYMMDD}.csv + logs/run_{时间戳}.log

用法:
  D:/pyh/python.exe -E e2e_pipeline.py [--universe csi300|file] [--limit N] [--start 20190101]
      [--end 20260822] [--top-n 20] [--initial-cash 1000000] [--bench 510300,510500]
      [--delisted 600401,002450] [--skip-network] [--strategy mom_turn_csi300]

验收(S2): 独立运行有输出; 东财封禁下新浪/腾讯降级可用; 真实数据端到端跑通; 退市股纳入/剔除验证;
          SOP §2 结构树更新。
"""
import os
import sys
import time
import json
import logging
import datetime
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# 代理三件套（必须先于 requests 导入；data_fetcher 内部同样处理, 幂等）
# ============================================================
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
for k in list(os.environ):
    if 'proxy' in k.lower():
        os.environ.pop(k, None)

import numpy as np
import pandas as pd
import akshare as ak

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import data_fetcher as fetcher
from sell_signals import generate_signals, SellRules
from backtest import BacktestEngine

# ============================================================
# 日志
# ============================================================
LOG_DIR = os.path.join(BASE_DIR, 'logs')
OUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

RUN_TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
TODAY = datetime.date.today().strftime('%Y%m%d')

logger = logging.getLogger('e2e_pipeline')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _fmt = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s', datefmt='%H:%M:%S')
    _sh = logging.StreamHandler()
    try:
        _sh.setStream(__import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
    except Exception:
        pass
    _sh.setFormatter(_fmt)
    logger.addHandler(_sh)
    _fh = logging.FileHandler(os.path.join(LOG_DIR, f'run_{RUN_TS}.log'), encoding='utf-8')
    _fh.setFormatter(_fmt)
    logger.addHandler(_fh)

# ============================================================
# 东财断路器: 首次失败后全管线跳过东财（封禁期 0.2s 快速失败, 无重试浪费）
# ============================================================
EM_BROKEN = {'flag': False}
_orig_em_hist = ak.stock_zh_a_hist


def _em_hist_breaker(*a, **k):
    if EM_BROKEN['flag']:
        raise ConnectionError('EM breaker open (skip eastmoney)')
    try:
        return _orig_em_hist(*a, **k)
    except Exception as e:
        EM_BROKEN['flag'] = True
        logger.warning(f'[降级] 东财 stock_zh_a_hist 失败({type(e).__name__}), '
                       f'后续个股历史全部直连新浪: {str(e)[:80]}')
        raise


ak.stock_zh_a_hist = _em_hist_breaker

# ============================================================
# 历史行情标准化: 东财/新浪/腾讯 → 统一 date index + open/close/high/low/volume/turnover
# ============================================================


def norm_hist(df, source='sina'):
    """统一历史行情列名与类型。turnover 统一为小数(0.05=5%)。"""
    if df is None or len(df) == 0:
        return None
    d = df.copy()
    rename = {}
    for cn, en in [('日期', 'date'), ('开盘', 'open'), ('收盘', 'close'),
                   ('最高', 'high'), ('最低', 'low'), ('成交量', 'volume'),
                   ('成交额', 'amount'), ('换手率', 'turnover_pct')]:
        if cn in d.columns:
            rename[cn] = en
    d = d.rename(columns=rename)
    if 'date' not in d.columns:
        # 新浪/腾讯已是英文列
        pass
    d['date'] = pd.to_datetime(d['date'])
    d = d.set_index('date').sort_index()
    for c in ('open', 'close', 'high', 'low'):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors='coerce')
    # turnover: 东财为百分数 → 小数
    if 'turnover_pct' in d.columns:
        d['turnover'] = pd.to_numeric(d['turnover_pct'], errors='coerce') / 100.0
    elif 'turnover' in d.columns:
        d['turnover'] = pd.to_numeric(d['turnover'], errors='coerce')
    if 'outstanding_share' in d.columns:
        d['outstanding_share'] = pd.to_numeric(d['outstanding_share'], errors='coerce')
    cols = [c for c in ('open', 'close', 'high', 'low', 'volume', 'amount', 'turnover')
            if c in d.columns]
    return d[cols]


def fetch_stock_history(code, start, end, adjust, retries=3, source_hint=''):
    """个股历史(缓存优先): 东财(断路器) → 新浪。返回 (normalized_df, source) 或 (None, '')。"""
    used = ''
    for i in range(retries):
        try:
            raw = fetcher.get_history(code, start=start, end=end, adjust=adjust)
        except Exception as e:
            logger.warning(f'  [hist] {code} adjust={adjust} 第{i+1}次异常: {type(e).__name__}: {str(e)[:80]}')
            raw = None
        if raw is not None and len(raw) > 0:
            if '日期' in raw.columns:
                used = 'eastmoney'
            else:
                used = 'sina'
            return norm_hist(raw, used), used
        time.sleep(1.0 * (i + 1))
    return None, ''


def fetch_delisted_history(code, start, end, retries=3):
    """退市股历史(缓存优先): 腾讯 stock_zh_a_hist_tx。hfq 无源, 以 raw 代(声明)。"""
    cache_path = fetcher._cache_path('hist_tx', code, start, end, date_str=end)
    cached = fetcher._read_cache(cache_path)
    if cached is not None and len(cached) > 0:
        return norm_hist(cached, 'tencent')
    for i in range(retries):
        try:
            fetcher._throttle()
            raw = ak.stock_zh_a_hist_tx(symbol=fetcher._code_to_sina(code),
                                        start_date=start, end_date=end)
            if raw is not None and len(raw) > 0:
                fetcher._write_cache(raw, cache_path)
                return norm_hist(raw, 'tencent')
        except Exception as e:
            logger.warning(f'  [hist_tx] {code} 第{i+1}次失败: {type(e).__name__}: {str(e)[:80]}')
        time.sleep(1.0 * (i + 1))
    return None


# ============================================================
# 市场数据: 腾讯 qt 实时行情 → 总市值
# ============================================================


def fetch_qt_quotes(codes, batch=60, retries=3):
    """
    腾讯实时行情批量拉取: v_{sym}="1~名称~代码~最新价~...~[45]总市值(亿)~..."
    返回 dict: code → {'name': str, 'price': float, 'mcap_yi': float(亿元)}
    缓存 data_cache/e2e_qt_{date}.parquet。
    """
    cache_path = fetcher._cache_path('e2e_qt', date_str=TODAY)
    cached = fetcher._read_cache(cache_path)
    out = {}
    have_codes = set()
    if cached is not None and len(cached) > 0:
        for _, r in cached.iterrows():
            c6 = ''.join(ch for ch in str(r['code']) if ch.isdigit())[-6:]
            if len(c6) == 6:
                out[c6] = {'name': str(r['name']), 'price': float(r['price']),
                           'mcap_yi': float(r['mcap_yi'])}
                have_codes.add(c6)
    missing = [c for c in codes if c not in have_codes]
    if not missing:
        logger.info(f'[qt] 缓存命中: {len(out)} 只')
        return out
    logger.info(f'[qt] 缓存 {len(out)} 只, 需补拉 {len(missing)} 只')

    def _sym(c):
        c = str(c).strip()
        return ('sh' if c.startswith(('6', '5', '9')) else 'sz') + c

    fetch_codes = [str(c).strip() for c in missing]
    for i in range(0, len(fetch_codes), batch):
        chunk = fetch_codes[i:i + batch]
        syms = ','.join(_sym(c) for c in chunk)
        for attempt in range(retries):
            try:
                fetcher._throttle(0.5)
                txt = requests_get(f'https://qt.gtimg.cn/q={syms}')
                for seg in txt.split(';'):
                    seg = seg.strip()
                    if '="' not in seg:
                        continue
                    body = seg.split('="', 1)[1].rstrip('"')
                    f = body.split('~')
                    if len(f) < 46:
                        continue
                    code = f[2].strip()
                    try:
                        price = float(f[3])
                        mcap_yi = float(f[45])
                    except ValueError:
                        continue
                    if code:
                        out[code] = {'name': f[1], 'price': price, 'mcap_yi': mcap_yi}
                break
            except Exception as e:
                if attempt == retries - 1:
                    logger.warning(f'  [qt] 批次{i//batch} 失败: {type(e).__name__}: {str(e)[:80]}')
                else:
                    time.sleep(2.0 * (attempt + 1))
    if out:
        pd.DataFrame([{'code': k, 'name': v['name'], 'price': v['price'],
                       'mcap_yi': v['mcap_yi']} for k, v in out.items()]
                     ).to_parquet(cache_path, index=False)
    logger.info(f'[qt] 腾讯实时行情: {len(out)}/{len(codes)} 只有效')
    return out


def requests_get(url, timeout=20):
    import requests
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text


# ============================================================
# ETF 基准: 东财(qfq) → 新浪(raw) → 腾讯(raw)
# ============================================================


def fetch_etf_benchmark(code, start, end):
    """返回 (normalized_df, source, adjust_kind)"""
    # 1) 东财 qfq (data_fetcher 内置, 封禁期快速失败)
    try:
        raw = fetcher.get_benchmark(code, start=start, end=end)
        if raw is not None and len(raw) > 0:
            return norm_hist(raw, 'eastmoney'), 'eastmoney', 'qfq'
    except Exception as e:
        logger.warning(f'  [bench] 东财 {code} 失败: {type(e).__name__}: {str(e)[:80]}')
    # 2) 新浪 fund_etf_hist_sina (raw)
    cache_path = fetcher._cache_path('bench_sina', code, start, end, date_str=end)
    cached = fetcher._read_cache(cache_path)
    if cached is not None and len(cached) > 0:
        return norm_hist(cached, 'sina'), 'sina', 'raw'
    try:
        fetcher._throttle(0.5)
        sym = fetcher._code_to_sina(code)
        raw = ak.fund_etf_hist_sina(symbol=sym)
        if raw is not None and len(raw) > 0:
            fetcher._write_cache(raw, cache_path)
            return norm_hist(raw, 'sina'), 'sina', 'raw'
    except Exception as e:
        logger.warning(f'  [bench] 新浪 {code} 失败: {type(e).__name__}: {str(e)[:80]}')
    # 3) 腾讯 hist_tx (raw)
    cache_path = fetcher._cache_path('bench_tx', code, start, end, date_str=end)
    cached = fetcher._read_cache(cache_path)
    if cached is not None and len(cached) > 0:
        return norm_hist(cached, 'tencent'), 'tencent', 'raw'
    for attempt in range(3):
        try:
            fetcher._throttle(0.5)
            raw = ak.stock_zh_a_hist_tx(symbol=fetcher._code_to_sina(code),
                                        start_date=start, end_date=end)
            if raw is not None and len(raw) > 0:
                fetcher._write_cache(raw, cache_path)
                return norm_hist(raw, 'tencent'), 'tencent', 'raw'
        except Exception as e:
            logger.warning(f'  [bench] 腾讯 {code} 第{attempt+1}次失败: '
                           f'{type(e).__name__}: {str(e)[:80]}')
        time.sleep(2.0 * (attempt + 1))
    return None, '', ''


# ============================================================
# 退市股名单
# ============================================================


def get_delisted_with_dates():
    """
    沪深终止上市公司名单。返回 DataFrame[代码, 名称, 终止日期(可能NaN)]。
    sh 接口无终止日期列 → 终止日期由行情数据推导(NaN)。
    """
    frames = []
    try:
        fetcher._throttle(0.5)
        sh = ak.stock_info_sh_delist(symbol='全部')
        if sh is not None and len(sh) > 0:
            sh = sh.rename(columns={'公司代码': '代码', '公司简称': '名称'})
            if '终止上市日期' in sh.columns:
                sh = sh.rename(columns={'终止上市日期': '终止日期'})
            elif '暂停上市日期' in sh.columns:
                sh = sh.rename(columns={'暂停上市日期': '终止日期'})
            sh['代码'] = sh['代码'].astype(str).str.zfill(6)
            frames.append(sh[['代码', '名称', '终止日期']])
            logger.info(f'[退市] 沪市终止上市公司: {len(sh)} 家')
    except Exception as e:
        logger.warning(f'  [退市] 沪市名单失败: {type(e).__name__}: {str(e)[:80]}')
    try:
        fetcher._throttle(0.5)
        sz = ak.stock_info_sz_delist(symbol='终止上市公司')
        if sz is not None and len(sz) > 0:
            sz = sz.rename(columns={'证券代码': '代码', '证券简称': '名称',
                                    '终止上市日期': '终止日期'})
            sz['代码'] = sz['代码'].astype(str).str.zfill(6)
            frames.append(sz[['代码', '名称', '终止日期']])
            logger.info(f'[退市] 深市终止上市公司: {len(sz)} 家')
    except Exception as e:
        logger.warning(f'  [退市] 深市名单失败: {type(e).__name__}: {str(e)[:80]}')
    if frames:
        out = pd.concat(frames, ignore_index=True)
        out['终止日期'] = pd.to_datetime(out['终止日期'], errors='coerce')
        return out.drop_duplicates(subset=['代码'])
    return pd.DataFrame(columns=['代码', '名称', '终止日期'])


# ============================================================
# Stage 1: 数据准备
# ============================================================


def load_universe(spot, mode='csi300', limit=None):
    """
    试点股票池: csi300 成分(新浪 index_stock_cons, 重试3次+缓存) 或 指定文件(每行一代码)。
    返回 list[code]。
    """
    if mode == 'csi300':
        cache_path = fetcher._cache_path('e2e_universe', 'csi300', date_str=TODAY)
        cached = fetcher._read_cache(cache_path)
        if cached is not None and len(cached) > 0:
            codes = [str(c).zfill(6) for c in cached['代码'].astype(str)]
            logger.info(f'[池] CSI300 成分股(缓存): {len(codes)} 只')
            return codes[:limit] if limit else codes
        last_err = None
        for attempt in range(3):
            try:
                fetcher._throttle(0.5)
                cons = ak.index_stock_cons(symbol='000300')
                codes = [str(c).zfill(6) for c in cons['品种代码'].astype(str)]
                pd.DataFrame({'代码': codes}).to_parquet(cache_path, index=False)
                logger.info(f'[池] CSI300 成分股: {len(codes)} 只 (新浪 index_stock_cons)')
                return codes[:limit] if limit else codes
            except Exception as e:
                last_err = e
                logger.warning(f'  [池] index_stock_cons 第{attempt+1}次失败: '
                               f'{type(e).__name__}: {str(e)[:80]}')
                time.sleep(2.0 * (attempt + 1))
        logger.warning(f'  [池] index_stock_cons 3次失败({last_err}), 回退 spot 前300')
    # 回退: spot 市值未知, 按代码顺序取(封顶300, 防全A误拉)
    codes = []
    for c in spot['代码'].astype(str):
        c6 = ''.join(ch for ch in c if ch.isdigit())[-6:]
        if len(c6) == 6 and c6.startswith(('0', '3', '6')):
            codes.append(c6)
    codes = sorted(set(codes))
    n = min(len(codes), limit if limit else 300)
    logger.warning(f'[池] 回退方案: spot 顺序取前 {n} 只 (封顶300)')
    return codes[:n]


def build_engine_inputs(cfg, spot, codes, delisted_codes, hist_raw, hist_hfq,
                        qt_quotes, st_names, delist_term, calendar, bench_df):
    """
    构造 BacktestEngine 输入面板。
    tradable: 停牌日(行情缺失) = False; 退市终止日后 = False。
    market_cap: 总股本 × raw收盘(估算; qt 缺失 → NaN → 30bp 滑点档)。
    """
    # 试点池 + 退市验证股 全部入面板(退市股在终止日后 tradable=False)
    pool = list(codes) + [c for c in delisted_codes if c not in codes]
    have = [c for c in pool if c in hist_raw and c in hist_hfq
            and hist_raw[c] is not None and len(hist_raw[c]) > 0]
    miss = [c for c in pool if c not in have]
    if miss:
        logger.warning(f'[数据] {len(miss)} 只无行情被剔除: {miss[:10]}...')

    raw_open = pd.DataFrame({c: hist_raw[c]['open'] for c in have}).reindex(calendar)
    raw_close = pd.DataFrame({c: hist_raw[c]['close'] for c in have}).reindex(calendar)
    hfq_close = pd.DataFrame({c: hist_hfq[c]['close'] for c in have}).reindex(calendar)

    # 市值: 总股本 × raw 收盘
    mcap = pd.DataFrame(index=calendar, columns=have, dtype=float)
    n_mcap = 0
    for c in have:
        q = qt_quotes.get(c)
        if q and q['price'] and q['price'] > 0:
            shares = q['mcap_yi'] * 1e8 / q['price']
            mcap[c] = shares * raw_close[c]
            n_mcap += 1
        # else: NaN → 引擎按 30bp 最保守滑点档
    logger.info(f'[市值] 总股本×收盘估算: {n_mcap}/{len(have)} 只有市值基准')

    # tradable: 有收盘价且未退市(终止日后 False)
    tradable = raw_close.notna()
    for c in have:
        term = delist_term.get(c)
        if term is not None:
            tradable.loc[tradable.index >= term, c] = False
            logger.info(f'[退市] {c} {st_names.get(c,"")} 终止日期 {term.date()}, 其后不可交易')

    # ST 标记: 名称含 'ST' (当前名称口径, 历史ST状态不可得, 声明)
    st_flags = pd.DataFrame({c: ('ST' in str(st_names.get(c, ''))) for c in have},
                            index=calendar, dtype=bool)

    # 上市日: 首个有效收盘日
    list_dates = raw_close.apply(lambda s: s.first_valid_index()).dropna()

    return {
        'codes': have, 'raw_open': raw_open, 'raw_close': raw_close,
        'hfq_close': hfq_close, 'mcap': mcap, 'tradable': tradable,
        'st_flags': st_flags, 'list_dates': list_dates,
    }


# ============================================================
# Stage 2: 因子与信号
# ============================================================


def build_factors_and_signals(cfg, panel, calendar):
    """
    月度截面因子:
      MOM_60D    = hfq 收盘 t / t-60交易日 - 1
      TURNOVER_20D = 近20交易日日均换手(成交量/流通股本; sina 口径)
    得分 = 0.7×z(MOM) + 0.3×z(TURN), winsorize ±3。
    信号 = sell_signals.generate_signals(等权 Top-N, 时间止盈/止损/冷却, T+1开盘成交价口径)。
    """
    hfq = panel['hfq_close']
    raw_close = panel['raw_close']
    raw_open = panel['raw_open']
    codes = panel['codes']

    month_ends = calendar.to_series().groupby(calendar.to_period('M')).max()
    month_ends = pd.DatetimeIndex(sorted(set(month_ends)))
    month_ends = month_ends[month_ends >= pd.Timestamp(cfg.start)]

    mom = pd.DataFrame(index=month_ends, columns=codes, dtype=float)
    turn = pd.DataFrame(index=month_ends, columns=codes, dtype=float)
    for t in month_ends:
        pos = calendar.get_loc(t)
        # MOM_60D: 60 个交易日前
        if pos >= 60:
            mom.loc[t] = (hfq.iloc[pos] / hfq.iloc[pos - 60] - 1.0).where(
                hfq.iloc[pos - 60].notna())
        # TURNOVER_20D: 近20交易日日均换手
        if 'turnover_ts' in panel:
            tseg = panel['turnover_ts'].iloc[max(0, pos - 19):pos + 1]
            turn.loc[t] = tseg.mean()

    # 截面 z-score + winsorize
    def zscore(row):
        r = row.astype(float)
        v = r.dropna()
        if len(v) < 5:
            return pd.Series(np.nan, index=row.index)
        mu, sd = v.mean(), v.std(ddof=0)
        if sd <= 0:
            return pd.Series(np.nan, index=row.index)
        z = (r - mu) / sd
        return z.clip(-3, 3)

    zm = mom.apply(zscore, axis=1)
    zt = turn.apply(zscore, axis=1)
    if turn.notna().any().any():
        score = (0.7 * zm + 0.3 * zt).where(mom.notna() | turn.notna())
        factor_desc = 'MOM_60D(0.7) + TURNOVER_20D(0.3)'
    else:
        # 换手数据全缺 → 退化为纯动量
        score = zm.where(mom.notna())
        factor_desc = 'MOM_60D(1.0, 换手数据缺失退化)'
        logger.warning('[因子] 换手数据全缺, 得分退化为纯动量')

    # 因子覆盖率统计
    cov = pd.DataFrame({'MOM': mom.notna().sum(axis=1) / len(codes),
                        'TURN': turn.notna().sum(axis=1) / len(codes),
                        'SCORE': score.notna().sum(axis=1) / len(codes)})
    logger.info(f'[因子] 月度因子覆盖率: MOM {cov["MOM"].mean():.1%} / '
                f'TURN {cov["TURN"].mean():.1%} / SCORE {cov["SCORE"].mean():.1%} (均值)')

    # 信号: 等权 Top-N + 卖出规则(T+1 开盘成交价口径)
    exec_price = raw_open.shift(-1).reindex(month_ends)
    sell_log = []
    sig = generate_signals(score, raw_close, top_n=cfg.top_n,
                           rules=SellRules(hold_months=cfg.hold_months,
                                           stop_loss=cfg.stop_loss,
                                           max_rebuy_gap=cfg.max_rebuy_gap),
                           exec_price_table=exec_price, sell_log=sell_log)
    # 去掉前导全零行(因子未就绪期不空跑)
    active = (sig > 0).any(axis=1)
    if active.any():
        first = sig.index[active][0]
        sig = sig.loc[first:]
    nz = (sig > 0).sum(axis=1)
    logger.info(f'[信号] 调仓期数 {len(sig)}, 每期持仓数 {int(nz.median())}(中位), '
                f'卖出事件 {len(sell_log)}')
    return score, sig, sell_log, cov


# ============================================================
# Stage 4: 报告
# ============================================================


def nav_svg(nav, bench, w=900, h=360):
    """净值曲线 SVG(英文标注, 避免字体问题)。返回 svg 字符串。"""
    df = pd.DataFrame({'策略': nav, '基准': bench}).dropna()
    if len(df) < 2:
        return '<p>净值数据不足</p>'
    lo = min(df.min().min(), 0)
    hi = max(df.max().max(), 1)
    pad = (hi - lo) * 0.05 if hi > lo else 1
    lo, hi = lo - pad, hi + pad
    xs = np.linspace(30, w - 30, len(df))
    pts = {}
    for col in df.columns:
        ys = 30 + (hi - df[col].values) / (hi - lo) * (h - 60)
        pts[col] = ' '.join(f'{x:.1f},{y:.1f}' for x, y in zip(xs, ys))
    colors = {'策略': '#c0392b', '基准': '#2980b9'}
    legend = ''.join(
        f'<line x1="{w-240+i*110}" y1="18" x2="{w-210+i*110}" y2="18" stroke="{colors[c]}" stroke-width="2"/>'
        f'<text x="{w-205+i*110}" y="22" font-size="12" font-family="Arial">{c}</text>'
        for i, c in enumerate(df.columns))
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
            + ''.join(f'<polyline points="{pts[c]}" fill="none" stroke="{colors[c]}" '
                      f'stroke-width="2"/>' for c in df.columns)
            + legend + '</svg>')


def build_html(cfg, meta, perf, result, bench_meta, cov, sell_log,
               delist_report, report_path):
    """生成自包含 HTML 报告。"""
    nav = result.nav_hfq
    bench_nav = result.benchmark_nav
    monthly = result.monthly_returns
    trades = result.trades
    pos_h = result.positions_history

    def pct(x):
        return f'{x:.2%}' if pd.notna(x) else '-'

    perf_s = perf.summary(cfg.strategy)
    rows = ''
    labels = {'annual_return': '年化收益', 'annual_vol': '年化波动', 'sharpe': '夏普',
              'max_drawdown': '最大回撤', 'calmar': '卡玛', 'win_rate': '月度胜率',
              'excess_annual_return': '超额年化(相对基准)', 'excess_sharpe': '超额夏普',
              'relative_drawdown': '相对回撤', 'tracking_error': '跟踪误差',
              'information_ratio': '信息比率'}
    ratio_keys = {'sharpe', 'excess_sharpe', 'information_ratio', 'calmar'}
    for k, v in perf_s.items():
        if k not in labels:
            continue
        if k in ratio_keys:
            cell = f'{v:.3f}'
        else:
            cell = pct(v)
        rows += f'<tr><td>{labels[k]}</td><td class="num">{cell}</td></tr>'

    mrows = ''
    for t, r in monthly.items():
        mrows += f'<tr><td>{t.date()}</td><td class="num">{pct(r)}</td></tr>'
    mrows = mrows or '<tr><td colspan="2">-</td></tr>'

    trows = ''
    for tr in trades[-80:]:
        trows += (f'<tr><td>{tr.date.date()}</td><td>{tr.code}</td>'
                  f'<td>{tr.side}</td><td class="num">{tr.shares}</td>'
                  f'<td class="num">{tr.price:.2f}</td>'
                  f'<td class="num">{tr.amount:,.0f}</td>'
                  f'<td class="num">{tr.cost:.1f}</td><td>{tr.reason}</td></tr>')
    trows = trows or '<tr><td colspan="8">-</td></tr>'

    srows = ''
    for e in sell_log[-30:]:
        srows += (f'<tr><td>{e["date"].date()}</td><td>{e["code"]}</td>'
                  f'<td>{e["reason"]}</td><td class="num">{e["cooldown"]}</td></tr>')
    srows = srows or '<tr><td colspan="4">-</td></tr>'

    covrows = ''
    for t, r in cov.iterrows():
        covrows += (f'<tr><td>{t.date()}</td>'
                    f'<td class="num">{r["MOM"]:.1%}</td><td class="num">{r["TURN"]:.1%}</td>'
                    f'<td class="num">{r["SCORE"]:.1%}</td></tr>')

    drows = ''
    for d in delist_report:
        drows += (f'<tr><td>{d["code"]}</td><td>{d["name"]}</td>'
                  f'<td class="num">{d["rows"]}</td><td>{d["first"]}</td>'
                  f'<td>{d["last"]}</td><td>{d["term"]}</td><td>{d["flip"]}</td>'
                  f'<td>{d["in_panel"]}</td></tr>')

    bench_meta_s = ''.join(f'<p><b>{k}:</b> {v}</p>' for k, v in bench_meta.items())
    meta_s = ''.join(f'<p><b>{k}:</b> {v}</p>' for k, v in meta.items())

    holdrows = ''
    if len(pos_h):
        for s in pos_h[-24:]:
            holdrows += f'<tr><td>{s.name.date()}</td><td class="num">{int((s>0).sum())}</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>回测报告 {cfg.strategy} {TODAY}</title>
<style>
body{{font-family:'Microsoft YaHei',Arial,sans-serif;margin:24px;color:#222;background:#fafafa}}
h1{{font-size:20px}} h2{{font-size:16px;border-left:4px solid #c0392b;padding-left:8px;margin-top:28px}}
table{{border-collapse:collapse;background:#fff;margin:8px 0}}
th,td{{border:1px solid #ddd;padding:4px 10px;font-size:13px}}
th{{background:#f0f0f0}} .num{{text-align:right;font-variant-numeric:tabular-nums}}
.warn{{background:#fff8e1;border:1px solid #f0c36d;padding:8px 12px;border-radius:4px}}
.meta p{{margin:2px 0;font-size:13px}}
</style></head><body>
<h1>端到端回测报告 — {cfg.strategy}</h1>
<div class="meta">{meta_s}</div>
<h2>基准与数据源声明</h2><div class="meta">{bench_meta_s}</div>
<h2>绩效总览(基准对比)</h2>
<table><tr><th>指标</th><th>数值</th></tr>{rows}</table>
<p>期末策略净值 {nav.iloc[-1]:,.0f} (初始 {cfg.initial_cash:,.0f}); 基准期末 {bench_nav.iloc[-1]:,.0f}</p>
<h2>净值曲线(hfq 合成口径 vs 基准)</h2>
{nav_svg(nav, bench_nav)}
<h2>月度收益</h2>
<table><tr><th>月份</th><th>组合月收益</th></tr>{mrows}</table>
<h2>持仓数(月末快照, 近24期)</h2>
<table><tr><th>日期</th><th>持仓数</th></tr>{holdrows}</table>
<h2>卖出事件(近30条)</h2>
<table><tr><th>日期</th><th>代码</th><th>原因</th><th>冷却期</th></tr>{srows}</table>
<h2>成交记录(近80笔)</h2>
<table><tr><th>日期</th><th>代码</th><th>方向</th><th>股数</th><th>价格</th><th>金额</th><th>成本</th><th>说明</th></tr>{trows}</table>
<h2>因子覆盖率(月度)</h2>
<table><tr><th>月份</th><th>MOM_60D</th><th>TURNOVER_20D</th><th>SCORE</th></tr>{covrows}</table>
<h2>退市股处理验证</h2>
<table><tr><th>代码</th><th>名称</th><th>历史行数</th><th>首日</th><th>末日</th><th>终止日期</th><th>tradable 翻转</th><th>入面板</th></tr>{drows}</table>
<p class="warn">免责声明: 本报告为 S2 端到端管线验收产出, 因子为演示用价格类因子, 未经 S1 统计检验;
基准与市值口径见数据源声明; 退市股 hfq 以 raw 代替; 分红送转 cash_div/share_ratio 未提供。</p>
</body></html>"""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return report_path


# ============================================================
# 主流程
# ============================================================


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--universe', default='csi300')
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--start', default='20190101')
    ap.add_argument('--end', default=TODAY)
    ap.add_argument('--top-n', type=int, default=20)
    ap.add_argument('--initial-cash', type=float, default=1_000_000.0)
    ap.add_argument('--bench', default='510300,510500')
    ap.add_argument('--delisted', default='600401,002450')
    ap.add_argument('--strategy', default='mom_turn_csi300')
    ap.add_argument('--hold-months', type=int, default=6)
    ap.add_argument('--stop-loss', type=float, default=-0.15)
    ap.add_argument('--max-rebuy-gap', type=int, default=3)
    ap.add_argument('--skip-network', action='store_true',
                    help='仅用本地缓存(验证用)')
    ap.add_argument('--min-coverage', type=float, default=0.9,
                    help='历史行情覆盖率低于该值时仅拉数据后退出(便于分片续跑)')
    args = ap.parse_args()

    class Cfg:
        pass
    cfg = Cfg()
    for k, v in vars(args).items():
        setattr(cfg, k, v)

    logger.info('=' * 70)
    logger.info(f'端到端回测管线启动 strategy={cfg.strategy} universe={cfg.universe} '
                f'start={cfg.start} end={cfg.end} top_n={cfg.top_n}')
    logger.info(f'日志: logs/run_{RUN_TS}.log')
    t0 = time.time()

    # ---------- Stage 1a: 股票池 + 退市名单 ----------
    logger.info('--- Stage 1a: 股票池与退市名单 ---')
    spot = fetcher.get_spot_data(force_refresh=cfg.skip_network is False and False)
    # spot 缓存今日已有则直接用; 无缓存时网络拉取(东财封禁→新浪)
    name_map = {}
    for _, r in spot.iterrows():
        c6 = ''.join(ch for ch in str(r['代码']) if ch.isdigit())[-6:]
        if len(c6) == 6:
            name_map.setdefault(c6, str(r['名称']))

    codes = load_universe(spot, cfg.universe, cfg.limit)
    codes = [c for c in codes if c.startswith(('0', '3', '6'))]  # 剔除北交所(试点口径)

    delist_df = get_delisted_with_dates()
    delist_term = {}
    if len(delist_df):
        for _, r in delist_df.iterrows():
            if pd.notna(r['终止日期']):
                delist_term[str(r['代码'])] = pd.Timestamp(r['终止日期'])
    verifiers = [c.strip() for c in cfg.delisted.split(',') if c.strip()]
    for c in verifiers:
        if c not in name_map:
            row = delist_df[delist_df['代码'] == c]
            name_map[c] = str(row['名称'].iloc[0]) if len(row) else '退市股'

    logger.info(f'[池] 最终试点池 {len(codes)} 只 + 退市验证 {len(verifiers)} 只: {verifiers}')

    # ---------- Stage 1d: ETF 基准 ----------
    logger.info('--- Stage 1d: ETF 基准 ---')
    bench_meta = {}
    bench_data = {}
    for bc in cfg.bench.split(','):
        bdf, src, adj = fetch_etf_benchmark(bc.strip(), cfg.start, cfg.end)
        if bdf is not None:
            bench_data[bc] = bdf
            bench_meta[f'{bc}'] = (f'{src} {adj} 口径, {len(bdf)} 行 '
                                   f'({bdf.index[0].date()}~{bdf.index[-1].date()})')
            logger.info(f'[基准] {bc}: 源={src} 复权={adj} 行数={len(bdf)}')
        else:
            bench_meta[f'{bc}'] = '全部数据源失败'
            logger.error(f'[基准] {bc}: 全部数据源失败')
    if '510300' not in bench_data:
        logger.error('无 510300 基准, 终止')
        return 1
    calendar = pd.DatetimeIndex(sorted(bench_data['510300'].index))
    calendar = calendar[(calendar >= pd.Timestamp(cfg.start)) &
                        (calendar <= pd.Timestamp(cfg.end))]
    logger.info(f'[日历] 交易日历 {len(calendar)} 天 '
                f'({calendar[0].date()}~{calendar[-1].date()})')

    # ---------- Stage 1b: 个股历史行情 ----------
    logger.info('--- Stage 1b: 个股历史行情 (东财→新浪降级) ---')
    hist_raw, hist_hfq = {}, {}
    all_codes = codes + verifiers
    t1 = time.time()
    n_ok_raw = n_ok_hfq = 0
    for i, c in enumerate(all_codes):
        raw_df, src_r = fetch_stock_history(c, cfg.start, cfg.end, '')
        hfq_df, src_h = fetch_stock_history(c, cfg.start, cfg.end, 'hfq')
        if raw_df is not None and len(raw_df):
            hist_raw[c] = raw_df
            n_ok_raw += 1
        if hfq_df is not None and len(hfq_df):
            hist_hfq[c] = hfq_df
            n_ok_hfq += 1
        if (i + 1) % 25 == 0 or i == len(all_codes) - 1:
            el = time.time() - t1
            logger.info(f'[行情] {i+1}/{len(all_codes)} raw={n_ok_raw} hfq={n_ok_hfq} '
                        f'耗时 {el:.0f}s 均速 {el/(i+1):.2f}s/只')
    # 退市股: 腾讯源(raw; hfq 以 raw 代)
    for c in verifiers:
        if c in hist_raw:
            continue
        tx = fetch_delisted_history(c, cfg.start, cfg.end)
        if tx is not None and len(tx):
            hist_raw[c] = tx
            hist_hfq[c] = tx.copy()
            logger.info(f'[退市] {c} 腾讯源 {len(tx)} 行')
        else:
            logger.warning(f'[退市] {c} 腾讯源也失败, 不入面板')
    logger.info(f'[行情] 完成: raw {n_ok_raw}/{len(all_codes)}, hfq {n_ok_hfq}/{len(all_codes)}')
    logger.info(f'[降级] 东财断路器状态: {"打开(已跳过东财)" if EM_BROKEN["flag"] else "未触发"}')

    # 覆盖率门槛: 不足时仅拉数据(fetch-only), 供分片续跑
    coverage = n_ok_raw / len(all_codes) if all_codes else 0.0
    if coverage < cfg.min_coverage:
        logger.warning(f'[覆盖] 行情覆盖率 {coverage:.1%} < {cfg.min_coverage:.0%}, '
                       f'本轮仅拉数据(fetch-only), 下次运行继续')
        print('\n=== E2E SUMMARY JSON ===')
        print(json.dumps({'mode': 'fetch-only', 'coverage': round(coverage, 4),
                          'n_ok_raw': n_ok_raw, 'n_ok_hfq': n_ok_hfq,
                          'n_total': len(all_codes),
                          'log': os.path.join(LOG_DIR, f'run_{RUN_TS}.log')},
                         ensure_ascii=False, default=str))
        return 0

    # ---------- Stage 1c: 市值 ----------
    logger.info('--- Stage 1c: 总市值 (腾讯 qt) ---')
    qt_quotes = {}
    if not cfg.skip_network:
        qt_quotes = fetch_qt_quotes(codes)
    else:
        try:
            qt_quotes = fetch_qt_quotes(codes)  # 缓存命中即用
        except Exception as e:
            logger.warning(f'[市值] qt 失败: {e}')

    # ---------- Stage 1e: 财务数据(缓存优先) ----------
    logger.info('--- Stage 1e: 财务数据(缓存) ---')
    fin_status = '未使用(价格类因子不依赖财务)'
    try:
        fin = fetcher.get_financials(quarters=2, report_type='yjbb')
        if fin:
            fin_status = f'yjbb 缓存 {len(fin)} 期: ' + ', '.join(sorted(fin.keys()))
            logger.info(f'[财务] {fin_status}')
        else:
            fin_status = '无 yjbb 缓存, 东财拉取失败(封禁) → 本管线不使用财务数据'
            logger.warning(fin_status)
    except Exception as e:
        fin_status = f'财务获取异常: {str(e)[:80]}'
        logger.warning(f'[财务] {fin_status}')

    # ---------- 面板构建 ----------
    logger.info('--- 面板构建 ---')
    panel = build_engine_inputs(cfg, spot, codes, verifiers, hist_raw, hist_hfq,
                                qt_quotes, name_map, delist_term, calendar, bench_data)
    logger.info(f'[面板] {len(panel["codes"])} 只入面板, '
                f'交易日 {len(calendar)}, 市值基准 {int(panel["mcap"].notna().any(axis=1).sum())} 天')
    # 换手率时间序列(供 TURNOVER 因子): 用 volume/outstanding_share 或行情 turnover 列
    turn_ts = pd.DataFrame(index=calendar, columns=panel['codes'], dtype=float)
    for c in panel['codes']:
        h = hist_raw.get(c)
        if h is not None and 'turnover' in h.columns and h['turnover'].notna().any():
            turn_ts[c] = h['turnover']
        elif h is not None and 'volume' in h.columns and 'outstanding_share' in h.columns:
            turn_ts[c] = (h['volume'] / h['outstanding_share'])
        # 无换手源 → NaN → TURNOVER 因子 NaN
    panel['turnover_ts'] = turn_ts

    # ---------- Stage 2: 因子与信号 ----------
    logger.info('--- Stage 2: 因子与信号 ---')
    score, sig, sell_log, cov = build_factors_and_signals(cfg, panel, calendar)

    # ---------- Stage 3: 引擎回测 ----------
    logger.info('--- Stage 3: 引擎回测 ---')
    # 基准净值: 用日频序列(归一化), Performance._bench 内部 reindex+ffill 到
    # 引擎净值日历(含首次执行日, 非月末) → 头 NaN 问题消除
    bench_close = bench_data['510300']['close']
    bench_nav = bench_close / bench_close.iloc[0] * cfg.initial_cash

    engine = BacktestEngine(
        calendar=calendar,
        prices_raw_open=panel['raw_open'],
        prices_raw_close=panel['raw_close'],
        prices_hfq=panel['hfq_close'],
        market_cap=panel['mcap'],
        tradable=panel['tradable'],
        st_flags=panel['st_flags'],
        initial_cash=cfg.initial_cash,
        cash_div=None,          # 分红数据源缺失, 声明
        share_ratio=None,       # 送转数据源缺失, 声明
        list_dates=panel['list_dates'],
        limit_free_dates=None,
    )
    t2 = time.time()
    result = engine.run(sig, verbose=False, benchmark_nav=bench_nav)
    logger.info(f'[引擎] 回测完成 {time.time()-t2:.1f}s, '
                f'调仓 {len(sig)} 期, 成交 {len(result.trades)} 笔, '
                f'净值点数 {len(result.nav_hfq)}')

    perf = result.perf
    s = perf.summary(cfg.strategy)
    logger.info('[绩效] ' + '; '.join(f'{k}={v:.4f}' for k, v in s.items()))
    if result.benchmark_nav is not None:
        logger.info(f'[基准] {cfg.bench.split(",")[0]} 年化 {perf.benchmark_annual_return():.2%}, '
                    f'超额年化 {perf.excess_annual_return():.2%}, '
                    f'相对回撤 {perf.relative_drawdown():.2%}, IR {perf.information_ratio():.3f}')

    # ---------- 退市股验证 ----------
    logger.info('--- 退市股验证 ---')
    delist_report = []
    for c in verifiers:
        h = hist_raw.get(c)
        term = delist_term.get(c)
        if h is None or len(h) == 0:
            delist_report.append({'code': c, 'name': name_map.get(c, ''), 'rows': 0,
                                  'first': '-', 'last': '-', 'term': '-',
                                  'flip': '无数据', 'in_panel': '否'})
            logger.warning(f'[退市] {c} 无历史数据')
            continue
        last = h.index[-1]
        term_s = term.date().isoformat() if term is not None else '数据推导'
        if term is None:
            term = last + pd.Timedelta(days=1)  # 终止日 = 行情末日+1(数据推导)
        flip = panel['tradable'].loc[panel['tradable'].index >= term, c]
        flip_date = flip[~flip].index[0].date().isoformat() if (~flip).any() else '未翻转!'
        in_panel = '是' if c in panel['codes'] else '否'
        delist_report.append({'code': c, 'name': name_map.get(c, ''),
                              'rows': len(h), 'first': h.index[0].date().isoformat(),
                              'last': last.date().isoformat(), 'term': term_s,
                              'flip': flip_date, 'in_panel': in_panel})
        logger.info(f'[退市] {c} {name_map.get(c,"")}: 历史 {len(h)} 行 '
                    f'({h.index[0].date()}~{last.date()}), 终止 {term_s}, '
                    f'tradable 自 {flip_date} 起 False, 入面板={in_panel}')

    # ---------- Stage 4: 报告 ----------
    logger.info('--- Stage 4: 报告落盘 ---')
    report_path = os.path.join(OUT_DIR, f'backtest_{cfg.strategy}_{TODAY}.html')
    meta = {
        '策略名': cfg.strategy, '股票池': f'{cfg.universe} 试点({len(panel["codes"])}只)',
        '回测区间': f'{cfg.start} ~ {cfg.end}', '调仓频率': '月度(月末信号, T+1开盘执行)',
        'Top-N': cfg.top_n, '初始资金': f'{cfg.initial_cash:,.0f}',
        '卖出规则': f'时间止盈{cfg.hold_months}月/信号衰减/止损{cfg.stop_loss:.0%}/冷却{cfg.max_rebuy_gap}月',
        '因子': 'MOM_60D(0.7) + TURNOVER_20D(0.3), 月度截面 z-score',
        '财务数据': fin_status,
        '分红送转': '未提供(cash_div/share_ratio=None, hfq 收益层已含分红再投; raw 对账层缺分红, 已声明)',
        '运行时间': RUN_TS,
        '东财断路器': '打开(已降级新浪/腾讯)' if EM_BROKEN['flag'] else '未触发',
        '市值口径': '腾讯qt总市值→总股本×raw收盘 估算',
    }
    bench_meta_all = dict(bench_meta)
    bench_meta_all['基准口径说明'] = ('新浪 fund_etf_hist_sina 为不复权口径, 未含ETF分红, '
                                     '基准收益略有低估; 东财 qfq 不可用(封禁)')
    build_html(cfg, meta, perf, result, bench_meta_all, cov, sell_log,
               delist_report, report_path)

    # 选股表: 最新一期 Top-N
    pick_path = os.path.join(OUT_DIR, f'pick_{TODAY}.csv')
    try:
        last_t = sig.index[-1]
        row = score.loc[last_t].sort_values(ascending=False)
        top = row.head(cfg.top_n)
        pick = pd.DataFrame({'代码': top.index,
                             '名称': [name_map.get(c, '') for c in top.index],
                             '得分': top.values.round(4)})
        pick.to_csv(pick_path, index=False, encoding='utf-8-sig')
        logger.info(f'[选股] 最新一期({last_t.date()}) Top-{cfg.top_n} → {pick_path}')
    except Exception as e:
        logger.warning(f'[选股] pick csv 生成失败: {e}')

    # ---------- 汇总 ----------
    summary = {
        'strategy': cfg.strategy, 'run_ts': RUN_TS,
        'universe_size': len(codes), 'panel_size': len(panel['codes']),
        'benchmark': bench_meta,
        'em_breaker': EM_BROKEN['flag'],
        'n_raw_ok': n_ok_raw, 'n_hfq_ok': n_ok_hfq,
        'n_rebalances': len(sig), 'n_trades': len(result.trades),
        'perf': {k: round(float(v), 6) for k, v in s.items()},
        'delisted_verified': delist_report,
        'report': report_path, 'log': os.path.join(LOG_DIR, f'run_{RUN_TS}.log'),
        'pick': pick_path if os.path.exists(pick_path) else None,
        'total_seconds': round(time.time() - t0, 1),
    }
    logger.info('=' * 70)
    logger.info(f'端到端管线完成: 总耗时 {summary["total_seconds"]}s')
    logger.info(f'报告: {report_path}')
    logger.info(f'日志: logs/run_{RUN_TS}.log')
    print('\n=== E2E SUMMARY JSON ===')
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


def mom_val(code, score, t):
    try:
        return float(score.loc[t, code])
    except Exception:
        return float('nan')


if __name__ == '__main__':
    sys.exit(main())
