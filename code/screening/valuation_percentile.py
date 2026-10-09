# -*- coding: utf-8 -*-
"""
估值分位模块 - screening/valuation_percentile.py
初筛管线: PE_PCTL / PB_PCTL 实际历史滚动窗口分位 (设计定稿 v2.1 §2.3)

规则 (v2.1 §2.3):
  - 窗口 = 实际历史滚动窗口: 数据源(东财 RPT_VALUEANALYSIS_DET) 2018-01-02 起
    全部累积, 截至 asof (默认最新交易日); 窗口随日历从 1 年累积至 ≈8.6 年
  - 最短窗口 ≥250 交易日才产出; 更短 → NaN + missing 原因 (缺失标记)
  - 有效观测 n_obs ≥ 250 才产出 (历史亏损期 PE<0 剔除出分位序列后仍须达标)
  - PE<0 / PB<0 (及 0/NaN) 从分位序列剔除; 当前值无效(<=0/NaN) → 该分位缺失
  - 分位口径: 当前值在历史序列中的百分位 0-100 = 严格小于占比的 ECDF 下侧
    (100 * mean(hist < cur); 参考序列含当日观测, 最小值→0, 最大值→<100)
  - 幸存者偏差: 退市股在估值历史接口完全缺失 (实测 300104/600401 均空),
    由调用方在报告中声明; 本模块对无数据个股返回缺失标记

使用:
  from screening.valuation_percentile import (
      calc_percentile, percentile_for_candidates, filter_by_percentile)
  vh = get_valuation_history('600595')
  r  = calc_percentile(vh)                      # -> dict
  df = percentile_for_candidates(['600595','002611'])   # -> DataFrame
  ok = filter_by_percentile(df, max_pctl=50)    # -> 过滤后 DataFrame
"""

import io
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

# 确保 code/ 在 sys.path (本模块位于 code/screening/ 下)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

# 引入 data_fetcher 即完成: 代理绕过三件套 (NO_PROXY + 清代理环境变量 +
# requests.Session.request 强制 proxies=None) + parquet 缓存 + 0.5s 全局节流
from data_fetcher import get_valuation_history

logger = logging.getLogger('valuation_percentile')
if not logger.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter('[valpctl] %(message)s'))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# 数据源起点 (东财 RPT_VALUEANALYSIS_DET 实测 2018-01-02 起)
DATA_START = pd.Timestamp('2018-01-02')
MIN_OBS = 250  # 最短窗口 ≥250 交易日才产出 (v2.1 §2.3)


def _clean_series(s):
    """估值序列清洗: 数值化 → 剔除 NaN/0/负值 (历史亏损期 PE<0 剔除出分位序列)."""
    s = pd.to_numeric(s, errors='coerce').dropna()
    return s[s > 0]


def _empty_result(reason, n_trading=0, window_days=0, asof=None):
    return {
        'pe_pctl': np.nan, 'pb_pctl': np.nan,
        'n_obs': 0, 'n_obs_pb': 0, 'n_trading': n_trading,
        'window_days': window_days,
        'asof': asof, 'missing': reason,
    }


def calc_percentile(vh_df, asof=None):
    """
    单股估值分位计算 (设计 v2.1 §2.3).

    参数
      vh_df: get_valuation_history 返回的 DataFrame (date/pe_ttm/pb_mrq 等列;
             列名大小写容错)
      asof:  截止日 (YYYY-MM-DD / Timestamp; 默认 = 数据最新交易日).
             超出数据范围时自动收敛到数据末端.

    返回 dict
      pe_pctl   当前 PE(TTM) 在窗口内历史序列的百分位 0-100 (严格小于占比 ECDF)
      pb_pctl   当前 PB(MRQ) 同上
      n_obs     窗口内有效 PE 观测数 (剔除 <0/0/NaN 后)
      n_obs_pb  窗口内有效 PB 观测数
      n_trading 窗口内交易日数 (原始行数, 2018-01-02 起累积)
      window_days 窗口日历天数 (首个交易日 → asof)
      asof      实际截止日 (Timestamp)
      missing   缺失原因 ('' = 正常产出; 非空 = 分位缺失标记, 供人工复核)
    """
    if vh_df is None or len(vh_df) == 0:
        return _empty_result('无估值历史数据')

    df = vh_df.copy()
    # 列名容错 (小写/大写)
    colmap = {}
    for c in df.columns:
        cl = str(c).strip().lower()
        if cl in ('date', 'pe_ttm', 'pb_mrq') and cl not in colmap:
            colmap[cl] = c
    if 'date' not in colmap:
        return _empty_result('缺 date 列')
    df = df.rename(columns={v: k for k, v in colmap.items()})
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    if len(df) == 0:
        return _empty_result('无有效日期')

    if asof is None:
        asof_dt = df['date'].max()
    else:
        asof_dt = pd.to_datetime(asof)
    # 窗口 = 实际历史滚动窗口: 2018-01-02 起累积, 截至 asof
    df = df[(df['date'] >= DATA_START) & (df['date'] <= asof_dt)]
    if len(df) == 0:
        return _empty_result('窗口为空 (数据早于2018-01-02或晚于asof)')

    asof_dt = df['date'].max()          # 收敛到数据末端
    first_dt = df['date'].min()
    n_trading = len(df)
    window_days = (asof_dt - first_dt).days
    if n_trading < MIN_OBS:             # 规则: 最短窗口 ≥250 交易日才产出
        return _empty_result(
            f'窗口不足: 仅{n_trading}个交易日 (<{MIN_OBS})',
            n_trading=n_trading, window_days=window_days, asof=asof_dt)

    cur_pe = pd.to_numeric(df['pe_ttm'], errors='coerce').iloc[-1] if 'pe_ttm' in df.columns else np.nan
    cur_pb = pd.to_numeric(df['pb_mrq'], errors='coerce').iloc[-1] if 'pb_mrq' in df.columns else np.nan
    s_pe = _clean_series(df['pe_ttm']) if 'pe_ttm' in df.columns else pd.Series(dtype=float)
    s_pb = _clean_series(df['pb_mrq']) if 'pb_mrq' in df.columns else pd.Series(dtype=float)
    n_obs, n_obs_pb = len(s_pe), len(s_pb)

    out = {'pe_pctl': np.nan, 'pb_pctl': np.nan,
           'n_obs': n_obs, 'n_obs_pb': n_obs_pb, 'n_trading': n_trading,
           'window_days': window_days, 'asof': asof_dt, 'missing': ''}

    # PE 分位 (当前值无效 或 有效观测不足 → 缺失标记)
    if not (np.isfinite(cur_pe) and cur_pe > 0):
        out['missing'] = '当前PE无效 (<=0或NaN)'
    elif n_obs < MIN_OBS:
        out['missing'] = f'有效PE观测不足 ({n_obs}<{MIN_OBS})'
    else:
        out['pe_pctl'] = round(100.0 * float((s_pe < cur_pe).mean()), 4)
    # PB 分位
    if not (np.isfinite(cur_pb) and cur_pb > 0):
        out['missing'] = (out['missing'] + '; ' if out['missing'] else '') + '当前PB无效 (<=0或NaN)'
    elif n_obs_pb < MIN_OBS:
        out['missing'] = (out['missing'] + '; ' if out['missing'] else '') + \
            f'有效PB观测不足 ({n_obs_pb}<{MIN_OBS})'
    else:
        out['pb_pctl'] = round(100.0 * float((s_pb < cur_pb).mean()), 4)
    return out


def _fetch_one(code, asof):
    """单股: 拉取估值历史 (有缓存秒回) → 算分位. 失败/无数据返回缺失标记行."""
    code = str(code).strip().zfill(6)
    try:
        vh = get_valuation_history(code)
        if vh is None or len(vh) == 0:
            return code, {'pe_pctl': np.nan, 'pb_pctl': np.nan, 'n_obs': 0,
                          'window_days': 0, 'missing': '无估值历史数据 (退市/未上市/接口无数据)'}
        r = calc_percentile(vh, asof=asof)
        return code, r
    except Exception as e:
        return code, {'pe_pctl': np.nan, 'pb_pctl': np.nan, 'n_obs': 0,
                      'window_days': 0,
                      'missing': f'拉取/计算异常: {type(e).__name__}: {str(e)[:120]}'}
    finally:
        time.sleep(0.2)  # 小 sleep 防限流 (data_fetcher 内部另有 0.5s 全局节流)


def percentile_for_candidates(codes, asof=None, max_workers=3):
    """
    候选池批量分位 (10-50 只规模, 逐股 get_valuation_history + calc_percentile).
    限制并发 max_workers=3 (requests 安全); 每请求后小 sleep 防限流.

    参数
      codes: 候选代码列表 (str/int 均可, 自动 zfill(6))
      asof:  截止日 (默认最新)
      max_workers: 并发数 (默认 3)

    返回 DataFrame[code, pe_pctl, pb_pctl, n_obs, window_days,
                   n_obs_pb, n_trading, asof, missing]
      失败/无数据个股: 行保留但分位=NaN, missing 注明原因, 不静默丢弃.
    """
    codes = [str(c).strip().zfill(6) for c in codes]
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_one, c, asof): c for c in codes}
        for f in as_completed(futs):
            code, r = f.result()
            results[code] = r

    rows = []
    for c in codes:
        r = results[c]
        rows.append({
            'code': c,
            'pe_pctl': r['pe_pctl'], 'pb_pctl': r['pb_pctl'],
            'n_obs': r['n_obs'], 'window_days': r['window_days'],
            'n_obs_pb': r.get('n_obs_pb', np.nan),
            'n_trading': r.get('n_trading', np.nan),
            'asof': r.get('asof'), 'missing': r.get('missing', ''),
        })
    out = pd.DataFrame(rows)
    for c in ('pe_pctl', 'pb_pctl'):
        out[c] = pd.to_numeric(out[c], errors='coerce')
    # 打印缺失/失败原因
    miss = out[out['missing'].astype(str) != '']
    if len(miss):
        for _, row in miss.iterrows():
            logger.warning(f"{row['code']}: {row['missing']}")
    else:
        logger.info(f"全部 {len(out)} 只候选分位正常产出")
    return out


def filter_by_percentile(df, max_pctl=50):
    """
    分位过滤: 保留 PE_PCTL < max_pctl **且** PB_PCTL < max_pctl.

    取舍说明: 用"两者都<50"更严格 — 任一指标处于自身历史上半区(>=50%)即视为
    不够便宜。宽松版"任一<50"会放过"PE便宜但PB贵"的个股(如周期股盈利高点
    呈现低PE+高PB), 安全边际打折, 故采用严格 AND 版。

    分位 NaN 的个股 (窗口不足的新股/数据缺失): **保留但标注** pctl_status=
    'missing', 不静默剔除 — 留给人工复核阶段处理。

    参数
      df: percentile_for_candidates 的输出 (含 code/pe_pctl/pb_pctl 列)
      max_pctl: 分位阈值 (默认 50)

    返回
      过滤后 DataFrame (通过 + 缺失保留), 新增列:
        pctl_status  'pass' 两者都<阈值 | 'missing' 分位缺失待人工复核
        pctl_note    缺失原因说明
    """
    if df is None or len(df) == 0:
        return df.copy() if df is not None else pd.DataFrame()

    out = df.copy()
    colmap = {str(c).strip().lower(): c for c in out.columns}
    pe_col, pb_col = colmap.get('pe_pctl'), colmap.get('pb_pctl')
    if pe_col is None or pb_col is None:
        raise ValueError('缺少 pe_pctl/pb_pctl 列: 请先运行 percentile_for_candidates')

    pe = pd.to_numeric(out[pe_col], errors='coerce')
    pb = pd.to_numeric(out[pb_col], errors='coerce')
    both_ok = (pe < max_pctl) & (pb < max_pctl)
    missing_mask = pe.isna() | pb.isna()

    status = np.where(both_ok, 'pass', np.where(missing_mask, 'missing', 'fail'))
    out['pctl_status'] = status
    note_col = colmap.get('missing')
    out['pctl_note'] = out[note_col].fillna('') if note_col is not None else ''
    out.loc[missing_mask & (out['pctl_note'] == ''), 'pctl_note'] = \
        '分位缺失 (窗口不足/数据缺失), 待人工复核'

    keep = out[(status == 'pass') | (status == 'missing')].copy()
    keep = keep.sort_values('pctl_status').reset_index(drop=True)  # pass 在前
    logger.info(
        f"分位过滤 (max_pctl={max_pctl}, 两者都<{max_pctl}才通过): "
        f"总{len(out)} | 通过{int((status == 'pass').sum())} | "
        f"缺失保留{int(missing_mask.sum())} | 剔除{int((status == 'fail').sum())}")
    return keep
