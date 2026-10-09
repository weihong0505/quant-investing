# -*- coding: utf-8 -*-
"""
A股多因子价值选股系统 v2（对照基线, P2-B 冻结权重快照）
Value + Quality (MImo-reviewed-design, validity untested) + Liquidity + Size

状态标注（2026-08-25, 价值投资转型 P2-B 更新）:
  - MOM_60D 已淘汰出打分体系（权重归零）: 原方向(+)试点检验反向显著（signed NW-t=-3.63, registry #13）,
    FM 增量检验无贡献（#17）; 反转方向 #12 MOM_60D_R1 保持待检（P4 并入检验）——见
    value_investing_transition_v2.1.md §2.2。
  - 对照基线权重快照已冻结（P2-A）: 8 因子重归一化 EP 0.235/BP 0.235/ROE_TTM 0.141/GPM 0.071/
    CFO_NI_TTM 0.059/LEV 0.024/TURNOVER 0.176/LOG_MCAP 0.059（和=1.000）；动态共线性闸门保留
    相关矩阵报告但**不再砍权重**（消除对照基线权重漂移）。
  - 质量因子组已通过独立审查（factor_docs/quality_factors_v2.md）: ROE_TTM / GPM / CFO_NI_TTM / LEV
  - 本系统为对照基线保留；主策略迁移至 value_investing.py（价值投资决策系统 v1）
关键规则：
  - 逐股 PIT 最新报告期（最新公告日期 ≤ 今日，自动回退）
  - TTM = 去年年报 + 最新期累计 − 去年同期累计
  - 金融股全部质量因子中性化；非金融 GPM/ROE/LEV 行业内 z-score
  - 负利润符号保护（TTM每股收益 ≤ 0 → CFO_NI/ROE 最低分）
  - winsorize ±3σ → z-score → 方向加权合成
"""
import os
import sys
import time
import datetime
import warnings
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

from run_logger import get_run_logger, log_path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, 'data_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

FIN_KEYWORDS = ('银行', '保险', '证券', '多元金融', '信托')

# v2 权重（已按审查 Q4 调整；2026-08-25 P2-B: MOM_60D 归零后 8 因子重归一化, 和=1.000）
# VOL_RATIO 已弃用（东财 spot 盘中快照不可复现），权重并入 TURNOVER
# MOM_60D 淘汰原因: registry #13（试点反向显著, signed NW-t=-3.63）/ #17（FM 增量无贡献）,
#   反转方向 #12 MOM_60D_R1 保持待检 — value_investing_transition_v2.1.md §2.2
WEIGHTS = {
    'EP': 0.235,         # 价值（TTM 口径）
    'BP': 0.235,         # 价值
    'ROE_TTM': 0.141,    # 质量
    'GPM': 0.071,        # 质量
    'CFO_NI_TTM': 0.059, # 质量
    'LEV': 0.024,        # 质量
    'TURNOVER': 0.176,   # 流动性（低换手偏好）+ VOL_RATIO 0.05 并入
    'LOG_MCAP': 0.059,   # 规模（小市值偏好）
}
# 越高越好 → +1；越低越好 → -1
# 对照基线权重快照已冻结（P2-A）: 动态共线性闸门只报告不砍权，见 score_factors()
DIRECTION = {
    'EP': +1, 'BP': +1, 'ROE_TTM': +1, 'GPM': +1, 'CFO_NI_TTM': +1,
    'LEV': -1, 'TURNOVER': -1, 'LOG_MCAP': -1,
}


# ============================================================
# 通用工具
# ============================================================

def retry(fn, n=3, wait=2.0, name=''):
    for i in range(n):
        try:
            return fn()
        except Exception as e:
            print(f"  [retry {i+1}/{n}] {name} {type(e).__name__}: {str(e)[:80]}")
            time.sleep(wait * (i + 1))
    raise RuntimeError(f'{name} failed after {n} retries')


def last_quarter_ends(n=8, today=None):
    """最近 n 个季末日期（YYYYMMDD，≤ today）"""
    today = today or pd.Timestamp.now()
    cands = [pd.Timestamp(f'{yy}{md}')
             for yy in range(today.year - 2, today.year + 1)
             for md in ('0331', '0630', '0930', '1231')]
    cands = [c for c in cands if c <= today]
    cands.sort()
    return [c.strftime('%Y%m%d') for c in cands[-n:]]


def winsorize_zscore(s):
    """winsorize(±3σ) 后 z-score；常数/空列返回 0"""
    s = s.astype(float)
    if s.notna().sum() < 3:
        return s * 0
    m, sd = s.mean(), s.std()
    if pd.isna(sd) or sd == 0:
        return s * 0
    c = s.clip(m - 3 * sd, m + 3 * sd)
    return (c - c.mean()) / c.std()


def industry_zscore(df, col, industry_col, min_group=5):
    """行业内 winsorize+z-score；小行业回退全市场"""
    market_z = winsorize_zscore(df[col])
    def _f(g):
        return winsorize_zscore(g) if len(g) >= min_group else market_z.reindex(g.index)
    ind_z = df.groupby(industry_col)[col].transform(_f)
    return ind_z.fillna(market_z)


# ============================================================
# Part 1: 数据获取
# ============================================================

def get_spot():
    """全市场行情+估值（过滤 ST/北交所/负PE/PB）
    
    降级链: 东财 → 新浪(+本地财务合成PE/PB)
    数据源通过 data_fetcher.get_spot_data() 统一管理
    """
    from data_fetcher import get_spot_data
    print("[1/4] 获取行情与估值数据...")
    
    df = get_spot_data()
    
    # 声明数据源
    if '_source' in df.columns:
        src = df['_source'].iloc[0]
        print(f"  [数据源] {src}")
    if '_source' in df.columns and df['_source'].iloc[0] != 'eastmoney':
        n_mc = pd.to_numeric(df.get('总市值'), errors='coerce').notna().sum() if '总市值' in df.columns else 0
        if n_mc == 0:
            print('  [声明] 降级数据源无总市值列 → LOG_MCAP 因子中性 0 分（新浪降级限制）')
        n_pe = pd.to_numeric(df.get('市盈率-动态'), errors='coerce').notna().sum()
        print(f'  [声明] 降级数据源 PE 覆盖 {n_pe}/{len(df)}（财务缓存合成）')
    
    # 股票池口径统一（审查 P1-6）：剔 ST/退市/北交所(4/8开头)
    df = df[~df['名称'].str.contains('ST|退', na=False)]
    df = df[~df['代码'].str.startswith(('4', '8', '920'))]  # 北交所: 4/8 开头 + 920 新段
    for c in ('最新价', '市盈率-动态', '市净率'):
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['最新价', '市盈率-动态', '市净率'])
    df = df[(df['市盈率-动态'] > 0) & (df['市净率'] > 0)]
    print(f"  入池 {len(df)} 只（已剔 ST/北交所/负PE/负PB）")
    return df


def get_quality_data():
    """质量因子数据：yjbb 业绩报表(多期) + zcfz 资产负债表"""
    print("[2/4] 获取财务质量数据 (yjbb × 8期 + zcfz × 4期)...")

    yjbb = {}
    for p in last_quarter_ends(8):
        cache = os.path.join(CACHE_DIR, f'yjbb_{p}.parquet')
        if os.path.exists(cache):
            yjbb[p] = pd.read_parquet(cache)
        else:
            yjbb[p] = retry(lambda p=p: ak.stock_yjbb_em(date=p), name=f'yjbb_{p}')
            yjbb[p].to_parquet(cache)
            time.sleep(0.5)
        print(f"  yjbb {p}: {len(yjbb[p])} 家")

    zcfz = {}
    for p in last_quarter_ends(4):
        cache = os.path.join(CACHE_DIR, f'zcfz_{p}.parquet')
        if os.path.exists(cache):
            zcfz[p] = pd.read_parquet(cache)
        else:
            zcfz[p] = retry(lambda p=p: ak.stock_zcfz_em(date=p), name=f'zcfz_{p}')
            zcfz[p].to_parquet(cache)
            time.sleep(0.5)
        print(f"  zcfz {p}: {len(zcfz[p])} 家")
    return yjbb, zcfz


def build_quality_factors(yjbb, zcfz, today=None):
    """
    构建质量因子（审查 P0 规则全部落地）
    返回 DataFrame[代码, ROE_TTM, GPM, CFO_NI_TTM, LEV, 所处行业, 最新报告期, EPS_TTM]
    """
    today = today or pd.Timestamp.now()
    key_cols = ['股票代码', '股票简称', '每股收益', '每股净资产',
                '每股经营现金流量', '销售毛利率', '所处行业', '最新公告日期']

    # ---- 长表 + 逐股 PIT 最新报告期 ----
    frames = []
    for p, d in yjbb.items():
        dd = d[key_cols].copy()
        dd['报告期'] = p
        frames.append(dd)
    allf = pd.concat(frames, ignore_index=True)
    allf['公告日期'] = pd.to_datetime(allf['最新公告日期'], errors='coerce')
    valid = allf[allf['公告日期'] <= today].copy()
    valid = valid.sort_values(['股票代码', '报告期'], ascending=[True, False])
    latest = valid.groupby('股票代码', as_index=False).first()  # 最新报告期行

    # ---- 每期数值查找表 ----
    def period_map(col):
        m = {}
        for p, d in yjbb.items():
            s = pd.to_numeric(d.set_index('股票代码')[col], errors='coerce')
            m[p] = s
        return m

    eps_map = period_map('每股收益')
    cfps_map = period_map('每股经营现金流量')

    # ---- TTM 计算 ----
    def ttm_value(code, L, val_map):
        if L is None:
            return np.nan
        vL = val_map[L].get(code, np.nan)
        if L.endswith('1231'):
            return vL
        fy = f'{int(L[:4]) - 1}1231'
        sp = f'{int(L[:4]) - 1}{L[4:]}'
        vFY = val_map.get(fy, pd.Series(dtype=float)).get(code, np.nan)
        vSP = val_map.get(sp, pd.Series(dtype=float)).get(code, np.nan)
        if pd.isna(vL) or pd.isna(vFY):
            return np.nan
        if pd.isna(vSP):
            # 去年同期缺失（次新股）→ 年化近似
            f = {'0331': 4.0, '0630': 2.0, '0930': 4.0 / 3}.get(L[4:], np.nan)
            return vL * f if not pd.isna(f) else np.nan
        return vL + vFY - vSP

    rows = []
    for _, r in latest.iterrows():
        code = str(r['股票代码'])
        L = r['报告期']
        eps_ttm = ttm_value(code, L, eps_map)
        cfps_ttm = ttm_value(code, L, cfps_map)
        bps = pd.to_numeric(r['每股净资产'], errors='coerce')
        rows.append({
            '代码': code,
            '报告期': L,
            '所处行业': r['所处行业'],
            'EPS_TTM': eps_ttm,
            'ROE_TTM': (eps_ttm / bps) if (pd.notna(eps_ttm) and pd.notna(bps) and bps > 0) else np.nan,
            'GPM': pd.to_numeric(r['销售毛利率'], errors='coerce'),
            'CFO_NI_TTM': (cfps_ttm / eps_ttm) if (pd.notna(eps_ttm) and eps_ttm > 0 and pd.notna(cfps_ttm)) else np.nan,
        })
    qdf = pd.DataFrame(rows)

    # ---- LEV 资产负债率（zcfz 逐股 PIT）----
    zframes = []
    for p, d in zcfz.items():
        dd = d[['股票代码', '资产负债率', '公告日期']].copy()
        dd['报告期'] = p
        zframes.append(dd)
    zall = pd.concat(zframes, ignore_index=True)
    zall['公告日期'] = pd.to_datetime(zall['公告日期'], errors='coerce')
    zvalid = zall[zall['公告日期'] <= today].sort_values(['股票代码', '报告期'], ascending=[True, False])
    zlatest = zvalid.groupby('股票代码', as_index=False).first()
    zlatest['资产负债率'] = pd.to_numeric(zlatest['资产负债率'], errors='coerce')

    qdf = qdf.merge(zlatest[['股票代码', '资产负债率']].rename(
        columns={'股票代码': '代码', '资产负债率': 'LEV'}), on='代码', how='left')

    # ---- 覆盖率告警（审查 P0-2）----
    cov = len(qdf) / max(len(allf.dropna(subset=['公告日期'])['股票代码'].unique()), 1)
    print(f"  质量因子覆盖 {len(qdf)} 只 / 覆盖率告警阈值 90%（当前 {cov:.1%}）")
    return qdf


# ============================================================
# Part 2: 打分
# ============================================================

def score_factors(spot, qdf):
    """合并数据 → 因子清洗 → 中性化 → z-score 加权合成"""
    print("[3/4] 因子清洗、中性化与打分...")
    df = spot.merge(qdf, on='代码', how='left')

    # ---- 原始因子 ----
    # EP 改为 TTM 口径：EPS_TTM / 最新价（替代原动态 PE 倒数）
    df['EP_DYN'] = 1.0 / df['市盈率-动态']  # 参考列，不计入合成
    df['EP'] = df['EPS_TTM'] / df['最新价']
    df['BP'] = 1.0 / df['市净率']
    df['TURNOVER'] = pd.to_numeric(df.get('换手率'), errors='coerce')
    df['LOG_MCAP'] = np.log(pd.to_numeric(df.get('总市值'), errors='coerce'))

    fin_mask = df['所处行业'].astype(str).str.contains('|'.join(FIN_KEYWORDS), na=False)
    n_fin = fin_mask.sum()
    if n_fin:
        print(f"  金融股 {n_fin} 只 → 全部质量因子中性化")

    scores = {}
    # 全市场因子
    for f in ('EP', 'BP', 'TURNOVER', 'LOG_MCAP', 'CFO_NI_TTM'):
        scores[f] = winsorize_zscore(df[f])
    # 行业内中性化因子（非金融）
    for f in ('ROE_TTM', 'GPM', 'LEV'):
        z = industry_zscore(df, f, '所处行业')
        z.loc[fin_mask] = 0.0  # 金融股中性化
        scores[f] = z

    # ---- 负利润符号保护（P0-4）：EPS_TTM ≤ 0 → 质量盈利因子最低分 -3 ----
    eps_num = pd.to_numeric(df['EPS_TTM'], errors='coerce')
    neg = (eps_num <= -0.1) & (~fin_mask)        # 真实亏损（阈值 -0.1）
    missing = eps_num.isna() & (~fin_mask)        # 数据缺失
    for f in ('ROE_TTM', 'CFO_NI_TTM'):
        scores[f] = scores[f].where(~neg, -3.0)
        scores[f] = scores[f].where(~missing, 0.0)   # 缺失给中性分 0
    scores['GPM'] = scores['GPM'].where(~(eps_num <= -0.1), -3.0)
    scores['GPM'] = scores['GPM'].where(~missing, 0.0)

    # ---- 缺失 → 0（中性）----
    for f in scores:
        scores[f] = scores[f].fillna(0.0)

    # ---- 加权合成 ----
    df['SCORE'] = 0.0
    for f, w in WEIGHTS.items():
        df['SCORE'] += w * DIRECTION[f] * scores[f]
        df[f'{f}_Z'] = DIRECTION[f] * scores[f]

    df = df.sort_values('SCORE', ascending=False).reset_index(drop=True)

    # ---- 共线性闸门（P2-A: 对照基线权重快照已冻结, 只报告不砍权）----
    factor_cols = list(WEIGHTS.keys())
    z_cols = [f for f in factor_cols if f'{f}_Z' in df.columns]
    z_df = df[z_cols].rename(columns={f'{c}_Z': c for c in z_cols})
    corr = z_df.corr()
    print("\n  因子相关系数矩阵（winsorize后z值, 阈值 0.7）:")
    flagged = []
    for i, f1 in enumerate(z_cols):
        for f2 in z_cols[i + 1:]:
            v = corr.loc[f1, f2]
            if abs(v) > 0.7:
                flagged.append((f1, f2, round(v, 3)))
    if flagged:
        for f1, f2, v in flagged:
            print(f"    [!] {f1} x {f2} = {v:+.3f} - 触发闸门（仅报告）")
        print("    [P2-A] 对照基线权重已冻结: 不再砍权重/重归一化（消除权重漂移, "
              "对照口径固定为 8 因子快照 EP 0.235/BP 0.235/ROE_TTM 0.141/GPM 0.071/"
              "CFO_NI_TTM 0.059/LEV 0.024/TURNOVER 0.176/LOG_MCAP 0.059）")
    else:
        print("    [OK] 无高相关因子对")
    return df


# ============================================================
# Part 3: 输出与回测
# ============================================================

def select_top_stocks(df, n=30):
    print("\n[4/4] 选股输出...")
    result = df.head(n).copy()
    print("\n" + "=" * 78)
    print(f"  TOP {n} VALUE+QUALITY STOCKS  (Multi-Factor v2)")
    print("=" * 78)
    print(f"{'Rank':>4} {'Code':>8} {'Name':<9} {'Price':>8} {'PE':>8} {'PB':>6} "
          f"{'ROE':>7} {'GPM':>7} {'SCORE':>8}")
    print("-" * 78)
    for i, (_, row) in enumerate(result.iterrows(), 1):
        print(f"{i:>4} {row['代码']:>8} {str(row['名称'])[:8]:<9} "
              f"{row['最新价']:>8.2f} {row['市盈率-动态']:>8.1f} {row['市净率']:>6.2f} "
              f"{(row['ROE_TTM'] * 100 if pd.notna(row['ROE_TTM']) else float('nan')):>7.2f} "
              f"{row['GPM'] if pd.notna(row['GPM']) else 0:>7.2f} {row['SCORE']:>8.3f}")
    print("=" * 78)
    return result


# (simple_backtest removed: future-function bug — see S1 validation)
# ============================================================
# Main
# ============================================================

def run_full_pipeline(top_n=30):
    log = get_run_logger()
    _t0 = time.time()
    log.info("=" * 78)
    log.info(f"[启动] A股多因子价值+质量选股系统 v2  启动时间={datetime.datetime.now():%Y-%m-%d %H:%M:%S}  top_n={top_n}")
    log.info(f"[日志] 日志文件: {log_path()}")

    print("\n" + "=" * 78)
    print("  A股多因子价值+质量选股系统 v2")
    print("  因子设计: MImo 已审 (quality_factors_v2)；有效性: 未经 v3 统计检验（见 S1）")
    print("=" * 78)

    try:
        # 财务数据先于行情（东财被封时, 新浪兜底需要本地财务缓存合成PE/PB）
        _cached_yjbb = sum(os.path.exists(os.path.join(CACHE_DIR, f'yjbb_{p}.parquet'))
                           for p in last_quarter_ends(8))
        _cached_zcfz = sum(os.path.exists(os.path.join(CACHE_DIR, f'zcfz_{p}.parquet'))
                           for p in last_quarter_ends(4))
        log.info(f"[缓存] 财务数据缓存命中: yjbb {_cached_yjbb}/8 期, zcfz {_cached_zcfz}/4 期")
        yjbb, zcfz = get_quality_data()
        spot = get_spot()
        if '_source' in spot.columns:
            log.info(f"[数据源] 行情源命中: {spot['_source'].iloc[0]}")
        log.info(f"[入池] 入池股数: {len(spot)} 只（已剔 ST/北交所/负PE/负PB）")

        qdf = build_quality_factors(yjbb, zcfz)
        log.info(f"[覆盖] 质量因子覆盖: {len(qdf)} 只")
        scored = score_factors(spot, qdf)
        _cov = {f: round(float(scored[f].notna().mean()), 4) for f in WEIGHTS}
        log.info(f"[覆盖] 因子覆盖率(原始因子列非空占比): {_cov}")
        selected = select_top_stocks(scored, n=top_n)
        log.info(f"[选股] TOP {len(selected)} 只已选出")
    except Exception:
        log.exception("[异常] 主流程失败，异常堆栈如下（multi_factor_value.run_full_pipeline）")
        raise

    out = os.path.join(BASE_DIR, 'output')
    os.makedirs(out, exist_ok=True)
    today = datetime.date.today().strftime('%Y%m%d')
    pick_path = os.path.join(out, f'pick_{today}.csv')
    selected['代码'] = selected['代码'].astype(str).str.zfill(6)  # 前导零保护(Excel兼容)
    selected.to_csv(pick_path, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存: output/pick_{today}.csv")
    log.info(f"[输出] 选股表: {pick_path}")
    log.info(f"[完成] 总耗时 {time.time() - _t0:.1f}s")

    return scored, selected


if __name__ == '__main__':
    run_full_pipeline(top_n=30)
