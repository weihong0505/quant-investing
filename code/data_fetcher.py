# -*- coding: utf-8 -*-
"""
统一数据层 - data_fetcher.py
多源降级链 + parquet 缓存 + 指数退避重试 + 退市股纳入
状态标注：S2 交付 + C10 验收（2026-08-22，降级链/缓存/退市纳入）；字段口径见 docs/factor_docs/data_caliber_audit.md；数据层无因子逻辑，无需统计检验

降级策略:
  全市场行情: 东财 stock_zh_a_spot_em → 新浪 stock_zh_a_spot(+本地财务合成PE/PB)
  个股历史:   东财 stock_zh_a_hist → 新浪 stock_zh_a_daily
  基准ETF:    东财 fund_etf_hist_em → (无备选)
  财务数据:   东财 stock_yjbb_em / stock_zcfz_em → (无备选)

缓存: data_cache/{接口}_{参数}_{日期}.parquet
退市股: stock_info_sh_delist + stock_info_sz_delist
"""

import os
import sys
import time
import datetime
import warnings
import logging

warnings.filterwarnings('ignore')

# ============================================================
# Python 版本兼容: 确保 3.14 加载正确的 site-packages
# ============================================================
_site_pkgs = os.path.join(os.path.dirname(sys.executable), 'Lib', 'site-packages')
if os.path.isdir(_site_pkgs) and _site_pkgs not in sys.path:
    sys.path.insert(0, _site_pkgs)

# ============================================================
# 代理绕过（必须先于 requests import）
# ============================================================
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
for k in list(os.environ):
    if 'proxy' in k.lower():
        os.environ.pop(k, None)

import requests
_orig = requests.Session.request

def _no_proxy(self, method, url, **kwargs):
    kwargs['proxies'] = {'http': None, 'https': None}
    kwargs.setdefault('timeout', 60)
    return _orig(self, method, url, **kwargs)

requests.Session.request = _no_proxy

import pandas as pd
import numpy as np
import akshare as ak

# ============================================================
# 路径 & 日志
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, 'data_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

logger = logging.getLogger('data_fetcher')
if not logger.handlers:
    import io
    _h = logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
    _h.setFormatter(logging.Formatter('[data_fetcher] %(message)s'))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# ============================================================
# 通用工具
# ============================================================
_last_request_ts = 0.0

def _throttle(min_gap=0.5):
    """请求间隔 ≥ min_gap 秒"""
    global _last_request_ts
    elapsed = time.time() - _last_request_ts
    if elapsed < min_gap:
        time.sleep(min_gap - elapsed)
    _last_request_ts = time.time()


def retry_with_backoff(fn, n=3, base_wait=2.0, name=''):
    """指数退避重试: 2s, 4s, 6s"""
    for i in range(n):
        try:
            _throttle()
            return fn()
        except Exception as e:
            wait = base_wait * (i + 1)
            logger.warning(f"  [retry {i+1}/{n}] {name}: {type(e).__name__}: {str(e)[:100]}")
            if i < n - 1:
                time.sleep(wait)
    raise RuntimeError(f'{name} failed after {n} retries')


def _cache_path(prefix, *args, date_str=None):
    """生成缓存文件路径: data_cache/{prefix}_{args}_{date}.parquet"""
    if date_str is None:
        date_str = datetime.date.today().strftime('%Y%m%d')
    parts = '_'.join(str(a) for a in args if a)
    fname = f"{prefix}_{parts}_{date_str}.parquet" if parts else f"{prefix}_{date_str}.parquet"
    return os.path.join(CACHE_DIR, fname)


def _read_cache(path):
    """读取 parquet 缓存, 不存在返回 None"""
    if os.path.exists(path):
        try:
            return pd.read_parquet(path)
        except Exception:
            pass
    return None


def _write_cache(df, path, max_keep=None):
    """写入 parquet 缓存, max_keep=None 表示永久保留"""
    df.to_parquet(path, index=False)
    if max_keep is not None:
        _prune_cache(os.path.dirname(path), os.path.basename(path).rsplit('_', 2)[0], max_keep)


def _prune_cache(cache_dir, prefix, max_keep):
    """保留最近 max_keep 个同前缀缓存文件"""
    files = sorted(
        [f for f in os.listdir(cache_dir) if f.startswith(prefix) and f.endswith('.parquet')],
        reverse=True
    )
    for f in files[max_keep:]:
        try:
            os.remove(os.path.join(cache_dir, f))
        except OSError:
            pass


# ============================================================
# 全市场行情 (降级链: 东财 → 新浪)
# ============================================================

def _fetch_spot_em():
    """东财全市场行情"""
    return ak.stock_zh_a_spot_em()


def _fetch_spot_sina():
    """新浪全市场行情"""
    return ak.stock_zh_a_spot()


def _synthesize_pe_pb(sina_df, fin_cache_dir=None):
    """
    用新浪行情 + 本地财务缓存合成 PE/PB 列.
    
    需要:
      - yjbb_{最新期}.parquet 中的 每股收益、每股净资产
      - 新浪行情中的 最新价、代码
    """
    if fin_cache_dir is None:
        fin_cache_dir = CACHE_DIR

    today = datetime.date.today()
    # 尝试最近 4 个季末
    quarters = []
    for yy in range(today.year - 1, today.year + 1):
        for md in ('0331', '0630', '0930', '1231'):
            quarters.append(f'{yy}{md}')
    quarters = [q for q in quarters if q <= today.strftime('%Y%m%d')]
    quarters.sort(reverse=True)

    yjbb = None
    used_q = None
    for q in quarters:
        path = os.path.join(fin_cache_dir, f'yjbb_{q}.parquet')
        cached = _read_cache(path)
        if cached is not None and len(cached) > 0:
            yjbb = cached
            used_q = q
            break

    if yjbb is None:
        logger.warning("  [!] 无本地财务缓存, 无法合成 PE/PB")
        sina_df['市盈率-动态'] = np.nan
        sina_df['市净率'] = np.nan
        return sina_df

    logger.info(f"  [财务] 使用 yjbb_{used_q} 合成 PE/PB")
    
    # 提取每股收益和每股净资产
    eps = pd.to_numeric(yjbb.set_index('股票代码')['每股收益'], errors='coerce')
    bps = pd.to_numeric(yjbb.set_index('股票代码')['每股净资产'], errors='coerce')
    
    sina_df = sina_df.copy()
    # 新浪代码带交易所前缀 (sh600000/sz000001/bj920000)，财务缓存为纯数字代码 → 剥离前缀
    sina_df['_code_num'] = sina_df['代码'].astype(str).str.extract(r'(\d{6})$')[0]
    sina_df['_eps'] = sina_df['_code_num'].map(eps)
    sina_df['_bps'] = sina_df['_code_num'].map(bps)
    
    sina_df['市盈率-动态'] = np.where(
        (sina_df['_eps'].notna()) & (sina_df['_eps'] > 0),
        sina_df['最新价'] / sina_df['_eps'],
        np.nan
    )
    sina_df['市净率'] = np.where(
        (sina_df['_bps'].notna()) & (sina_df['_bps'] > 0),
        sina_df['最新价'] / sina_df['_bps'],
        np.nan
    )
    
    sina_df.drop(columns=['_eps', '_bps', '_code_num'], inplace=True)

    # 总市值合成: 腾讯 qt 快照缓存 (e2e_qt_{date}.parquet 含市值列)
    try:
        import glob as _glob
        qt_files = sorted(_glob.glob(os.path.join(fin_cache_dir, 'e2e_qt_*.parquet')))
        if qt_files:
            qt = pd.read_parquet(qt_files[-1])
            qcol = [c for c in qt.columns if '市值' in c]
            if qcol and '代码' in qt.columns:
                qt_map = pd.to_numeric(qt.set_index('代码')[qcol[0]], errors='coerce')
                qt_map = qt_map[~qt_map.index.duplicated()]
                n_mcap = int(sina_df['代码'].map(qt_map).notna().sum())
                sina_df['总市值'] = sina_df['代码'].map(qt_map)
                logger.info(f"  [市值] 腾讯快照合成总市值: {n_mcap}/{len(sina_df)} 只")
    except Exception as e:
        logger.warning(f"  [市值] 合成失败: {type(e).__name__}: {str(e)[:80]}")
    return sina_df


def _normalize_spot(df, source):
    """
    统一行情 DataFrame 列名和格式.
    返回: DataFrame[代码, 名称, 最新价, 市盈率-动态, 市净率, 换手率, 总市值, 60日涨跌幅, 量比, ...]
    """
    df = df.copy()
    
    # 确保代码为字符串, 统一去掉交易所前缀 (新浪/腾讯: sh600000/sz000001/bj920000)
    df['代码'] = df['代码'].astype(str).str.strip()
    df['代码'] = df['代码'].str.replace(r'^(sh|sz|bj)', '', regex=True)
    
    # 最新价必须有
    df['最新价'] = pd.to_numeric(df.get('最新价'), errors='coerce')
    
    # 为新浪缺失的列补充默认值
    for col in ('市盈率-动态', '市净率', '换手率', '总市值', '60日涨跌幅', '量比'):
        if col not in df.columns:
            df[col] = np.nan
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df['_source'] = source
    return df


def get_spot_data(force_refresh=False):
    """
    全市场行情 + 估值 (含降级链).
    
    降级策略:
      1. 东财 stock_zh_a_spot_em (3次重试)
      2. 新浪 stock_zh_a_spot + 本地财务合成 PE/PB
    
    返回: DataFrame[代码, 名称, 最新价, 市盈率-动态, 市净率, 换手率, 总市值, 60日涨跌幅, 量比, _source]
    """
    today = datetime.date.today().strftime('%Y%m%d')
    cache_path = _cache_path('spot', date_str=today)
    
    if not force_refresh:
        cached = _read_cache(cache_path)
        if cached is not None and len(cached) > 0:
            source = cached['_source'].iloc[0] if '_source' in cached.columns else 'cache'
            logger.info(f"[行情] 缓存命中 ({source}): {len(cached)} 只")
            return cached

    # ---- 降级链 ----
    
    # 1) 东财
    try:
        logger.info("[行情] 尝试东财 stock_zh_a_spot_em ...")
        df = retry_with_backoff(_fetch_spot_em, n=3, name='spot_em')
        df = _normalize_spot(df, 'eastmoney')
        _write_cache(df, cache_path, max_keep=3)
        logger.info(f"  [OK] 东财成功: {len(df)} 只")
        return df
    except Exception as e:
        logger.warning(f"  [FAIL] 东财失败: {e}")

    # 2) 新浪
    try:
        logger.info("[行情] 降级 → 新浪 stock_zh_a_spot ...")
        df = retry_with_backoff(_fetch_spot_sina, n=2, name='spot_sina')
        df = _normalize_spot(df, 'sina')
        
        # 合成 PE/PB
        if df['市盈率-动态'].isna().all():
            df = _synthesize_pe_pb(df)
        
        _write_cache(df, cache_path, max_keep=3)
        has_pe = df['市盈率-动态'].notna().sum()
        logger.info(f"  [OK] 新浪成功: {len(df)} 只, PE覆盖 {has_pe}")
        return df
    except Exception as e:
        logger.error(f"  [FAIL] 新浪也失败: {e}")
        raise RuntimeError(f"所有行情数据源均失败: {e}")


# ============================================================
# 个股历史行情 (东财 → 新浪)
# ============================================================

def _code_to_sina(code):
    """股票代码转新浪格式: 600000 → sh600000"""
    code = str(code).strip()
    if code.startswith(('6', '5')):
        return f'sh{code}'
    return f'sz{code}'


def get_history(code, start='20200101', end=None, adjust='hfq'):
    """
    个股历史行情 (含降级链).
    
    参数:
      code: 股票代码 (如 '600000')
      start: 起始日期 YYYYMMDD
      end: 结束日期 YYYYMMDD (默认今天)
      adjust: 复权方式 ('hfq','qfq','')
    
    返回: DataFrame[日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, ...]
    """
    if end is None:
        end = datetime.date.today().strftime('%Y%m%d')
    
    cache_path = _cache_path('hist', code, start, end, adjust, date_str=end)
    cached = _read_cache(cache_path)
    if cached is not None and len(cached) > 0:
        return cached

    # 1) 东财
    try:
        _throttle()
        df = ak.stock_zh_a_hist(symbol=code, period='daily',
                                start_date=start, end_date=end, adjust=adjust)
        if df is not None and len(df) > 0:
            _write_cache(df, cache_path)
            return df
    except Exception as e:
        logger.warning(f"  [hist] 东财 {code} 失败: {type(e).__name__}: {str(e)[:80]}")

    # 2) 新浪
    try:
        sina_code = _code_to_sina(code)
        _throttle()
        df = ak.stock_zh_a_daily(symbol=sina_code, start_date=start,
                                 end_date=end, adjust=adjust)
        if df is not None and len(df) > 0:
            _write_cache(df, cache_path)
            return df
    except Exception as e:
        logger.warning(f"  [hist] 新浪 {code} 失败: {type(e).__name__}: {str(e)[:80]}")

    logger.error(f"  [hist] {code} 所有数据源均失败")
    return pd.DataFrame()


# ============================================================
# 财务数据 (东财)
# ============================================================

def get_financials(quarters=8, report_type='yjbb'):
    """
    获取财务数据 (yjbb 业绩报表 或 zcfz 资产负债表).
    
    参数:
      quarters: 获取最近几期
      report_type: 'yjbb' 或 'zcfz'
    
    返回: dict[period_str → DataFrame]
    """
    periods = _last_quarter_ends(quarters)
    result = {}
    
    for p in periods:
        cache_path = _cache_path(report_type, p, date_str=p)
        cached = _read_cache(cache_path)
        if cached is not None and len(cached) > 0:
            result[p] = cached
            continue
        
        try:
            _throttle()
            if report_type == 'yjbb':
                df = ak.stock_yjbb_em(date=p)
            else:
                df = ak.stock_zcfz_em(date=p)
            
            if df is not None and len(df) > 0:
                # 财务数据永久保留
                _write_cache(df, cache_path)
                result[p] = df
                logger.info(f"  {report_type} {p}: {len(df)} 家")
        except Exception as e:
            logger.warning(f"  {report_type} {p} 失败: {type(e).__name__}: {str(e)[:80]}")
        
        time.sleep(0.5)
    
    return result


def _last_quarter_ends(n=8, today=None):
    """最近 n 个季末日期 (YYYYMMDD, ≤ today)"""
    today = today or pd.Timestamp.now()
    cands = [pd.Timestamp(f'{yy}{md}')
             for yy in range(today.year - 2, today.year + 1)
             for md in ('0331', '0630', '0930', '1231')]
    cands = [c for c in cands if c <= today]
    cands.sort()
    return [c.strftime('%Y%m%d') for c in cands[-n:]]


# ============================================================
# ETF 基准行情 (东财)
# ============================================================

def get_benchmark(code='510300', start='20200101', end=None):
    """
    ETF 基准行情.
    
    参数:
      code: ETF 代码 (默认 510300 沪深300ETF)
      start: 起始日期
      end: 结束日期
    
    返回: DataFrame[日期, 开盘, 收盘, 最高, 最低, 成交量, ...]
    """
    if end is None:
        end = datetime.date.today().strftime('%Y%m%d')
    
    cache_path = _cache_path('benchmark', code, start, end, date_str=end)
    cached = _read_cache(cache_path)
    if cached is not None and len(cached) > 0:
        return cached
    
    try:
        _throttle()
        df = ak.fund_etf_hist_em(symbol=code, period='daily',
                                  start_date=start, end_date=end,
                                  adjust='qfq')
        if df is not None and len(df) > 0:
            _write_cache(df, cache_path)
            return df
    except Exception as e:
        logger.error(f"  [benchmark] {code} 失败: {type(e).__name__}: {str(e)[:80]}")
    
    return pd.DataFrame()


# ============================================================
# 退市股
# ============================================================

def get_delisted_stocks():
    """
    获取退市股列表 (沪市 + 深市).
    
    返回: DataFrame[代码, 名称, ...]
    """
    today = datetime.date.today().strftime('%Y%m%d')
    cache_path = _cache_path('delisted', date_str=today)
    cached = _read_cache(cache_path)
    if cached is not None:
        return cached
    
    frames = []
    
    # 沪市退市
    try:
        _throttle()
        sh = ak.stock_info_sh_delist(symbol='全部')  # 新版签名: symbol (旧版 indicator= 已移除)
        if sh is not None and len(sh) > 0:
            frames.append(sh)
            logger.info(f"  沪市退市股: {len(sh)} 家")
    except Exception as e:
        logger.warning(f"  沪市退市股查询失败: {e}")
    
    # 深市退市
    try:
        _throttle()
        sz = ak.stock_info_sz_delist(symbol='终止上市公司')  # 新版签名: symbol (旧版 indicator= 已移除)
        if sz is not None and len(sz) > 0:
            frames.append(sz)
            logger.info(f"  深市退市股: {len(sz)} 家")
    except Exception as e:
        logger.warning(f"  深市退市股查询失败: {e}")
    
    if frames:
        df = pd.concat(frames, ignore_index=True)
        _write_cache(df, cache_path)
        return df
    
    return pd.DataFrame(columns=['代码', '名称'])


# ============================================================
# 辅助: 获取完整股票池 (含退市股历史)
# ============================================================

def get_full_stock_pool():
    """
    获取完整股票池: 当前在市 + 退市股.
    用于回测场景需要纳入退市股避免幸存者偏差.
    
    返回: DataFrame[代码, 名称, 是否退市]
    """
    today = datetime.date.today().strftime('%Y%m%d')
    cache_path = _cache_path('full_pool', date_str=today)
    cached = _read_cache(cache_path)
    if cached is not None:
        return cached
    
    frames = []
    
    # 当前在市
    try:
        spot = get_spot_data()
        current = spot[['代码', '名称']].copy()
        current['退市'] = False
        frames.append(current)
    except Exception:
        pass
    
    # 退市股
    try:
        delisted = get_delisted_stocks()
        if len(delisted) > 0:
            dl = delisted.copy()
            # ⚠️ 2026-10-09 修复：旧写法按「列名含『代码』」逐列改名，而退市股表是
            #   沪/深 concat 的结果，同时含 `公司代码`(沪 159 只) 与 `证券代码`(深 208 只)
            #   → 两列都被改成 `代码` → DataFrame 出现重复列名 →
            #   下一行 `dl[['代码','名称']]` 抛 InvalidIndexError（且被外层 except 静默吞掉，
            #   导致退市股整块丢失、生存者偏差防线失效）。
            #   修法：显式按优先级**只取一列**，缺失时回退到另一列，并合并两列。
            CODE_PREF = ['证券代码', '公司代码', '代码', '股票代码', 'SECURITY_CODE', 'code']
            NAME_PREF = ['证券简称', '名称', '简称', '公司简称', 'SECURITY_NAME_ABBR', 'name']
            code_col = next((c for c in CODE_PREF if c in dl.columns), None)
            name_col = next((c for c in NAME_PREF if c in dl.columns), None)
            if code_col is None:
                logger.warning('  [full_pool] 退市股表无可用代码列，已跳过: %s', list(dl.columns))
            else:
                # 沪市只在 `公司代码` 有值、深市只在 `证券代码` 有值 → 两列合并取值
                merged = None
                for c in [x for x in CODE_PREF if x in dl.columns]:
                    s = dl[c].astype(str).str.strip().replace({'nan': None, 'None': None, '': None})
                    merged = s if merged is None else merged.fillna(s)
                out = pd.DataFrame({'代码': merged})
                out['名称'] = dl[name_col].astype(str) if name_col else '退市'
                out = out[out['代码'].notna()]
                # 去重：同一代码在两列都出现时只留一条
                out = out.drop_duplicates(subset=['代码'], keep='first')
                out['退市'] = True
                if len(out):
                    frames.append(out)
                else:
                    logger.warning('  [full_pool] 退市股解析后为空（代码列=%s）', code_col)
    except Exception as e:
        # 不再静默吞异常：退市股缺失 = 生存者偏差防线失效，必须可见
        logger.error('  [full_pool] 退市股获取失败（生存者偏差防线受影响）: %s: %s',
                     type(e).__name__, str(e)[:150])
    
    if frames:
        df = pd.concat(frames, ignore_index=True)
        df = df.drop_duplicates(subset=['代码'], keep='first')
        _write_cache(df, cache_path)
        return df
    
    return pd.DataFrame(columns=['代码', '名称', '退市'])


# ============================================================
# 估值历史 / 现金流 / 分红 / 行业映射 (价值投资转型 P1 新增, 2026-08-25)
# 数据源: 东财 datacenter-web (push2 被封不影响) + akshare fhps
# ============================================================

_EM_DC_URL = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
_EM_HDRS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}

_VAL_COLS = ['date', 'pe_ttm', 'pe_lar', 'pb_mrq', 'total_mcap', 'close', 'total_shares']
_FCF_COLS = ['report_date', 'notice_date', 'netcash_operate', 'construct_long_asset', 'fcf']
_DIV_COLS = ['report_date', 'ex_date', 'cash_div_per10', 'progress']


def _em_datacenter_get(report_name, filt, page_size=500, page=1, sort_col='', sort_dir=''):
    """东财 datacenter-web 单页查询 (调用方负责重试/节流)"""
    params = {
        'reportName': report_name, 'columns': 'ALL', 'filter': filt,
        'pageSize': page_size, 'pageNumber': page,
    }
    if sort_col:
        params['sortColumns'] = sort_col
        params['sortTypes'] = sort_dir
    r = requests.get(_EM_DC_URL, params=params, headers=_EM_HDRS, timeout=60)
    return r.json()


def _em_paged(report_name, filt, sort_col, page_size=500, max_pages=30):
    """东财 datacenter 全量分页拉取 (升序), 返回原始行 list; 无数据抛 RuntimeError"""
    j = retry_with_backoff(
        lambda: _em_datacenter_get(report_name, filt, page_size, 1, sort_col, '1'),
        n=3, name=f'{report_name}')
    if not (j and j.get('success')):
        msg = (j or {}).get('message') if isinstance(j, dict) else str(j)
        raise RuntimeError(f'{report_name} 无数据: {msg}')
    res = j.get('result') or {}
    total = int(res.get('count') or 0)
    rows = list(res.get('data') or [])
    pages = min(max_pages, -(-total // page_size))
    for p in range(2, pages + 1):
        jp = retry_with_backoff(
            lambda p=p: _em_datacenter_get(report_name, filt, page_size, p, sort_col, '1'),
            n=3, name=f'{report_name}_p{p}')
        if jp and jp.get('success'):
            rows.extend((jp.get('result') or {}).get('data') or [])
    return rows


def get_valuation_history(code, start=None, end=None):
    """
    估值历史 (东财 RPT_VALUEANALYSIS_DET, 日频).
    返回 DataFrame[date, pe_ttm, pe_lar, pb_mrq, total_mcap, close, total_shares]
      date         交易日 (datetime64)
      pe_ttm       PE(TTM)          pe_lar     PE(静态/年报)
      pb_mrq       PB(最新报告期)    total_mcap 总市值 (元)
      close        收盘价 (不复权, 元)  total_shares 总股本 (股)
    参数 start/end: 日期过滤 (YYYY-MM-DD 或 YYYYMMDD, 含边界), 过滤在缓存之后.
    退市股/无数据 → 空 DataFrame 不抛错.
    缓存: data_cache/valhist_{code}.parquet (全量历史, 断点复用).
    """
    code = str(code).strip().zfill(6)
    cache_path = os.path.join(CACHE_DIR, f'valhist_{code}.parquet')
    df = _read_cache(cache_path)
    if df is None:
        try:
            rows = _em_paged('RPT_VALUEANALYSIS_DET', f'(SECURITY_CODE="{code}")', 'TRADE_DATE')
        except Exception as e:
            logger.warning(f"  [valhist] {code} 拉取失败: {type(e).__name__}: {str(e)[:120]}")
            return pd.DataFrame(columns=_VAL_COLS)
        if not rows:
            return pd.DataFrame(columns=_VAL_COLS)
        df = pd.DataFrame(rows)
        _write_cache(df, cache_path)
        logger.info(f"  [valhist] {code} 全量 {len(df)} 行 → 缓存 {os.path.basename(cache_path)}")

    df = df.rename(columns={
        'TRADE_DATE': 'date', 'PE_TTM': 'pe_ttm', 'PE_LAR': 'pe_lar', 'PB_MRQ': 'pb_mrq',
        'TOTAL_MARKET_CAP': 'total_mcap', 'CLOSE_PRICE': 'close', 'TOTAL_SHARES': 'total_shares'})
    out = pd.DataFrame()
    for c in _VAL_COLS:
        out[c] = df[c] if c in df.columns else np.nan
    out['date'] = pd.to_datetime(out['date'], errors='coerce')
    for c in ('pe_ttm', 'pe_lar', 'pb_mrq', 'total_mcap', 'close', 'total_shares'):
        out[c] = pd.to_numeric(out[c], errors='coerce')
    out = out.dropna(subset=['date']).sort_values('date').reset_index(drop=True)
    if start is not None:
        out = out[out['date'] >= pd.to_datetime(start)]
    if end is not None:
        out = out[out['date'] <= pd.to_datetime(end)]
    return out.reset_index(drop=True)


def get_fcf(code, quarters=None):
    """
    现金流量表 (东财 RPT_DMSK_FN_CASHFLOW, 季度).
    返回 DataFrame[report_date, notice_date, netcash_operate, construct_long_asset, fcf]
      report_date         报告期 (季度末)
      notice_date         最新公告日期 (东财口径=修订日, 非首告日)
      netcash_operate     经营活动现金流量净额 (元)
      construct_long_asset 购建固定资产、无形资产和其他长期资产支付的现金 (元)
      fcf                 = netcash_operate - construct_long_asset (元)
    按 report_date 升序; quarters=N 时只返回最近 N 个报告期.
    缓存: data_cache/fcf_{code}.parquet (全量).
    """
    code = str(code).strip().zfill(6)
    cache_path = os.path.join(CACHE_DIR, f'fcf_{code}.parquet')
    df = _read_cache(cache_path)
    if df is None:
        try:
            rows = _em_paged('RPT_DMSK_FN_CASHFLOW', f'(SECURITY_CODE="{code}")', 'REPORT_DATE')
        except Exception as e:
            logger.warning(f"  [fcf] {code} 拉取失败: {type(e).__name__}: {str(e)[:120]}")
            return pd.DataFrame(columns=_FCF_COLS)
        if not rows:
            return pd.DataFrame(columns=_FCF_COLS)
        df = pd.DataFrame(rows)
        _write_cache(df, cache_path)
        logger.info(f"  [fcf] {code} 全量 {len(df)} 行 → 缓存 {os.path.basename(cache_path)}")

    df = df.rename(columns={
        'REPORT_DATE': 'report_date', 'NOTICE_DATE': 'notice_date',
        'NETCASH_OPERATE': 'netcash_operate', 'CONSTRUCT_LONG_ASSET': 'construct_long_asset'})
    out = pd.DataFrame()
    for c in _FCF_COLS[:4]:
        out[c] = df[c] if c in df.columns else np.nan
    out['report_date'] = pd.to_datetime(out['report_date'], errors='coerce')
    for c in ('netcash_operate', 'construct_long_asset'):
        out[c] = pd.to_numeric(out[c], errors='coerce')
    out['fcf'] = out['netcash_operate'] - out['construct_long_asset']
    out = out.dropna(subset=['report_date']).sort_values('report_date').reset_index(drop=True)
    if quarters is not None and len(out) > int(quarters):
        out = out.tail(int(quarters)).reset_index(drop=True)
    return out


def get_dividends(code):
    """
    分红送转明细 (ak.stock_fhps_detail_em, 东财).
    返回 DataFrame[report_date, ex_date, cash_div_per10, progress]
      report_date    报告期
      ex_date        除权除息日
      cash_div_per10 每10股现金分红 (含税, 元)
      progress       方案进度 (已过滤, 仅保留 '实施分配')
    缓存: data_cache/div_{code}.parquet.
    """
    code = str(code).strip().zfill(6)
    cache_path = os.path.join(CACHE_DIR, f'div_{code}.parquet')
    df = _read_cache(cache_path)
    if df is None:
        try:
            df = retry_with_backoff(lambda: ak.stock_fhps_detail_em(symbol=code), n=3, name=f'div_{code}')
        except Exception as e:
            logger.warning(f"  [div] {code} 拉取失败: {type(e).__name__}: {str(e)[:120]}")
            return pd.DataFrame(columns=_DIV_COLS)
        if df is None or len(df) == 0:
            return pd.DataFrame(columns=_DIV_COLS)
        _write_cache(df, cache_path)
        logger.info(f"  [div] {code} 全量 {len(df)} 行 → 缓存 {os.path.basename(cache_path)}")

    df = df.rename(columns={
        '报告期': 'report_date', '除权除息日': 'ex_date',
        '现金分红-现金分红比例': 'cash_div_per10', '方案进度': 'progress'})
    out = pd.DataFrame()
    for c in _DIV_COLS:
        out[c] = df[c] if c in df.columns else np.nan
    out['report_date'] = pd.to_datetime(out['report_date'], errors='coerce')
    out['ex_date'] = pd.to_datetime(out['ex_date'], errors='coerce')
    out['cash_div_per10'] = pd.to_numeric(out['cash_div_per10'], errors='coerce')
    if 'progress' in out.columns:
        out = out[out['progress'] == '实施分配']
    return out.sort_values('report_date').reset_index(drop=True)


# 东财行业 → 申万一级 手工映射表 (2026-08-25 建; 覆盖东财行业分类全量)
_EM_TO_SW1 = {
    # 金融
    '银行': '银行', '保险': '非银金融', '证券': '非银金融', '多元金融': '非银金融',
    # 地产/建筑建材
    '房地产开发': '房地产', '房地产服务': '房地产',
    '工程建设': '建筑装饰', '装修装饰': '建筑装饰', '工程咨询服务': '建筑装饰',
    '装修建材': '建筑材料', '水泥建材': '建筑材料', '玻璃玻纤': '建筑材料',
    # 周期资源
    '钢铁行业': '钢铁', '煤炭行业': '煤炭', '石油行业': '石油石化', '燃气': '公用事业',
    '电力行业': '公用事业', '环保行业': '环保', '环境治理': '环保', '环保设备': '环保',
    '有色金属': '有色金属', '贵金属': '有色金属', '小金属': '有色金属', '工业金属': '有色金属',
    '能源金属': '有色金属', '金属新材料': '有色金属', '非金属材料': '基础化工',
    # 化工
    '化学制品': '基础化工', '化学原料': '基础化工', '化学纤维': '基础化工',
    '塑料制品': '基础化工', '橡胶制品': '基础化工', '化肥行业': '基础化工',
    '农药兽药': '基础化工', '化纤行业': '基础化工',
    # 电子/通信/计算机/传媒
    '半导体': '电子', '电子元件': '电子', '光学光电子': '电子', '消费电子': '电子',
    '电子化学品': '电子', '其他电子': '电子', '元件': '电子',
    '通信设备': '通信', '通信服务': '通信',
    '软件开发': '计算机', '计算机设备': '计算机', '互联网服务': '计算机',
    '游戏': '传媒', '文化传媒': '传媒', '数字媒体': '传媒', '广告营销': '传媒',
    '影视院线': '传媒', '出版': '传媒', '电视广播': '传媒',
    # 汽车/家电
    '汽车整车': '汽车', '汽车零部件': '汽车', '汽车服务': '汽车', '摩托车及其他': '汽车',
    '家电行业': '家用电器', '白色家电': '家用电器', '黑色家电': '家用电器', '厨卫电器': '家用电器',
    '小家电': '家用电器', '照明设备': '家用电器', '家电零部件': '家用电器',
    # 电力设备/军工
    '电池': '电力设备', '光伏设备': '电力设备', '风电设备': '电力设备', '电网设备': '电力设备',
    '电机': '电力设备', '其他电源设备': '电力设备', '电源设备': '电力设备',
    '船舶制造': '国防军工', '航天航空': '国防军工', '军工电子': '国防军工', '地面兵装': '国防军工',
    # 机械
    '工程机械': '机械设备', '专用设备': '机械设备', '通用设备': '机械设备',
    '自动化设备': '机械设备', '轨交设备': '机械设备', '仪器仪表': '机械设备',
    # 消费
    '食品饮料': '食品饮料', '酿酒行业': '食品饮料', '食品加工': '食品饮料',
    '饮料乳品': '食品饮料', '休闲食品': '食品饮料', '调味发酵品': '食品饮料',
    '纺织服装': '纺织服饰', '服装家纺': '纺织服饰', '饰品': '纺织服饰',
    '造纸印刷': '轻工制造', '包装印刷': '轻工制造', '家居用品': '轻工制造',
    '文娱用品': '轻工制造', '家用轻工': '轻工制造',
    '农牧饲渔': '农林牧渔', '养殖业': '农林牧渔', '种植业': '农林牧渔',
    '农产品加工': '农林牧渔', '饲料': '农林牧渔', '渔业': '农林牧渔', '林业': '农林牧渔',
    '动物保健': '农林牧渔',
    # 医药/美容
    '医疗器械': '医药生物', '医疗服务': '医药生物', '化学制药': '医药生物',
    '生物制品': '医药生物', '中药': '医药生物', '医药商业': '医药生物',
    '美容护理': '美容护理', '个护用品': '美容护理', '化妆品': '美容护理', '医疗美容': '美容护理',
    # 交运/商贸/社服
    '物流行业': '交通运输', '铁路公路': '交通运输', '航空机场': '交通运输', '航运港口': '交通运输',
    '商业百货': '商贸零售', '贸易行业': '商贸零售', '专业连锁': '商贸零售', '互联网电商': '商贸零售',
    '旅游酒店': '社会服务', '教育': '社会服务', '专业服务': '社会服务', '体育': '社会服务',
    '综合行业': '综合',
}

# 申万二级 → 申万一级 (yjbb 缓存 '所处行业' 为申万二级口径, 兜底源用; 2021版)
_SW2_TO_SW1 = {
    '种植业': '农林牧渔', '养殖业': '农林牧渔', '农产品加工': '农林牧渔', '饲料': '农林牧渔',
    '渔业': '农林牧渔', '林业Ⅱ': '农林牧渔', '农业综合Ⅱ': '农林牧渔', '动物保健Ⅱ': '农林牧渔',
    '农化制品': '基础化工', '化学原料': '基础化工', '化学制品': '基础化工', '化学纤维': '基础化工',
    '塑料': '基础化工', '橡胶': '基础化工', '非金属材料Ⅱ': '基础化工',
    '冶钢原料': '钢铁', '普钢': '钢铁', '特钢Ⅱ': '钢铁',
    '金属新材料': '有色金属', '小金属': '有色金属', '工业金属': '有色金属',
    '贵金属': '有色金属', '能源金属': '有色金属',
    '半导体': '电子', '光学光电子': '电子', '消费电子': '电子', '元件': '电子',
    '其他电子Ⅱ': '电子', '电子化学品Ⅱ': '电子',
    '乘用车': '汽车', '商用车': '汽车', '汽车零部件': '汽车', '摩托车及其他': '汽车', '汽车服务': '汽车',
    '白色家电': '家用电器', '黑色家电': '家用电器', '厨卫电器': '家用电器', '小家电': '家用电器',
    '照明设备Ⅱ': '家用电器', '其他家电Ⅱ': '家用电器', '家电零部件Ⅱ': '家用电器',
    '白酒Ⅱ': '食品饮料', '非白酒': '食品饮料', '饮料乳品': '食品饮料', '休闲食品': '食品饮料',
    '食品加工': '食品饮料', '调味发酵品': '食品饮料', '调味发酵品Ⅱ': '食品饮料',
    '服装家纺': '纺织服饰', '纺织制造': '纺织服饰', '饰品': '纺织服饰',
    '造纸': '轻工制造', '包装印刷': '轻工制造', '家居用品': '轻工制造', '文娱用品': '轻工制造',
    '中药Ⅱ': '医药生物', '化学制药': '医药生物', '生物制品': '医药生物', '医疗器械': '医药生物',
    '医疗服务': '医药生物', '医药商业': '医药生物',
    '医疗美容': '美容护理', '个护用品': '美容护理', '化妆品': '美容护理',
    '电力': '公用事业', '燃气Ⅱ': '公用事业',
    '物流': '交通运输', '铁路公路': '交通运输', '航空机场': '交通运输', '航运港口': '交通运输',
    '房地产开发': '房地产', '房地产服务': '房地产',
    '一般零售': '商贸零售', '互联网电商': '商贸零售', '贸易Ⅱ': '商贸零售', '专业连锁Ⅱ': '商贸零售',
    '旅游及景区': '社会服务', '酒店餐饮': '社会服务', '旅游零售Ⅱ': '社会服务',
    '教育': '社会服务', '专业服务': '社会服务', '体育Ⅱ': '社会服务',
    '综合Ⅱ': '综合',
    '水泥': '建筑材料', '玻璃玻纤': '建筑材料', '装修建材': '建筑材料',
    '基础建设': '建筑装饰', '房屋建设Ⅱ': '建筑装饰', '专业工程': '建筑装饰',
    '装修装饰Ⅱ': '建筑装饰', '工程咨询服务Ⅱ': '建筑装饰',
    '电机Ⅱ': '电力设备', '其他电源设备Ⅱ': '电力设备', '风电设备': '电力设备',
    '光伏设备': '电力设备', '电池': '电力设备', '电网设备': '电力设备',
    '航天装备Ⅱ': '国防军工', '航空装备Ⅱ': '国防军工', '航海装备Ⅱ': '国防军工',
    '地面兵装Ⅱ': '国防军工', '军工电子Ⅱ': '国防军工',
    '软件开发': '计算机', 'IT服务Ⅱ': '计算机', '计算机设备': '计算机',
    '游戏Ⅱ': '传媒', '数字媒体': '传媒', '广告营销': '传媒', '影视院线': '传媒',
    '出版': '传媒', '电视广播Ⅱ': '传媒',
    '通信设备': '通信', '通信服务': '通信',
    '银行Ⅱ': '银行', '证券Ⅱ': '非银金融', '保险Ⅱ': '非银金融', '多元金融': '非银金融',
    '煤炭开采': '煤炭', '焦炭Ⅱ': '煤炭',
    '油气开采Ⅱ': '石油石化', '油服工程': '石油石化', '炼化及贸易': '石油石化',
    '环境治理': '环保', '环保设备Ⅱ': '环保',
    '工程机械': '机械设备', '专用设备': '机械设备', '通用设备': '机械设备',
    '自动化设备': '机械设备', '轨交设备': '机械设备', '轨交设备Ⅱ': '机械设备',
}


def get_industry_map(source='eastmoney'):
    """
    东财行业 → 申万一级 映射.
    行业列表提取优先级:
      1) 本地 spot 缓存中含 '所处行业' 列的文件 (东财原始 spot 口径)
      2) 实时 ak.stock_zh_a_spot_em() (东财, 可能限流)
      3) yjbb 缓存 '所处行业' (申万二级口径, 兜底)
    返回 Dict[行业名, 申万一级名], 未映射行业值为 None; 打印覆盖率.
    """
    ind_series, src = None, None
    # 1) 本地 spot 缓存 (取最新文件)
    for f in sorted(os.listdir(CACHE_DIR), reverse=True):
        if f.startswith('spot_') and f.endswith('.parquet'):
            try:
                s = pd.read_parquet(os.path.join(CACHE_DIR, f))
                if '所处行业' in s.columns and s['所处行业'].notna().any():
                    ind_series, src = s['所处行业'], f'缓存 {f}'
                    break
            except Exception:
                continue
    # 2) 实时东财 spot
    if ind_series is None:
        try:
            s = retry_with_backoff(lambda: ak.stock_zh_a_spot_em(), n=2, name='spot_em(industry)')
            if s is not None and '所处行业' in s.columns and s['所处行业'].notna().any():
                ind_series, src = s['所处行业'], '实时东财 spot_em'
        except Exception as e:
            logger.warning(f"  [indmap] 实时 spot_em 不可用: {type(e).__name__}: {str(e)[:80]}")
    # 3) yjbb 缓存兜底 (取最新报告期)
    if ind_series is None:
        for f in sorted(os.listdir(CACHE_DIR), reverse=True):
            if f.startswith('yjbb_') and f.endswith('.parquet'):
                try:
                    s = pd.read_parquet(os.path.join(CACHE_DIR, f))
                    if '所处行业' in s.columns and s['所处行业'].notna().any():
                        ind_series, src = s['所处行业'], f'yjbb缓存 {f} (申万二级口径)'
                        break
                except Exception:
                    continue
    if ind_series is None:
        logger.warning("  [indmap] 无可用行业数据源")
        return {}

    industries = sorted(set(str(x) for x in ind_series.dropna().unique()))
    table = {**_EM_TO_SW1, **_SW2_TO_SW1}
    result = {ind: table.get(ind) for ind in industries}
    mapped = sum(1 for v in result.values() if v)
    unmapped = [k for k, v in result.items() if v is None]
    cov = mapped / len(result) if result else 0.0
    logger.info(f"  [indmap] 数据源: {src} | 行业数 {len(result)} | 映射 {mapped} | "
                f"覆盖率 {cov:.1%} | 未映射 {len(unmapped)}: {unmapped}")
    return result


# ============================================================
# 便捷入口
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("  data_fetcher.py 独立测试")
    print("=" * 60)
    
    df = get_spot_data()
    print(f"\n行情: {len(df)} 只")
    print(f"列: {list(df.columns)}")
    if '_source' in df.columns:
        print(f"数据源: {df['_source'].iloc[0]}")
    print(df.head(3).to_string())
