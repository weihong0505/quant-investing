# -*- coding: utf-8 -*-
"""
价值投资主策略 value_investing.py v1
====================================
定稿设计: docs/factor_docs/value_investing_transition_v2.1.md (§3 决策框架 / §5 代码改造)
状态标注: 四层管线实现（P2 交付）；4 个新估值因子权重 = 主观先验（W-编号草案），
          未经 v3 统计检验 → 实验性；生产开关 fail-closed（P2.5）：experimental=False 拒绝运行。

四层管线:
  ① filter_universe        可交易性过滤: 市值≥30亿 / 换手0.1%~20% / 非ST / 上市≥5年 / 非北交所
  ② quality_gate           质量门槛一票否决: ROE(含周期8行业豁免) / GPM>0 / CFO_NI_TTM>0 / LEV<70% / EPS_TTM>0
  ③ build_valuation_factors + safety_margin_score
                            估值打分: PE_PCTL/PB_PCTL(实际历史滚动窗口分位, 月末快照) + EP_z/BP_z(申万一级行业内)
                            + DY + FCF_YIELD(金融股剔除); 安全边际分 = 0.30/0.30/0.15/0.15/0.05/0.05
  ④ build_portfolio + generate_signals
                            组合构建: top12 等权, 行业上限30%, 个股上限10%; 信号=完整目标组合语义
                            (事件驱动卖出行=完整持仓快照, 未动持仓保留原权重 — backtest.py 未列出即清仓)

对照基线: multi_factor_value.py（MOM_60D 已归零重归一化, 权重快照冻结, P2-B）
数据层: data_fetcher.py（P1 交付 4 新接口, 实测验证通过）
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

import numpy as np
import pandas as pd

from data_fetcher import (get_spot_data, get_history, get_valuation_history,
                          get_fcf, get_dividends, get_industry_map)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, 'data_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# ============================================================
# 常量与规则表（v2.1 §3.1）
# ============================================================

FIN_KEYWORDS = ('银行', '保险', '证券', '多元金融', '信托')
SW1_FIN = {'银行', '非银金融'}

# 周期 8 行业（申万一级, P1-A 固定清单）
CYCLICAL_SW1 = {'煤炭', '钢铁', '有色金属', '基础化工', '石油石化',
                '农林牧渔', '交通运输', '建筑材料'}

MIN_MCAP = 3e9          # 市值 ≥ 30 亿（raw 元）
TURNOVER_MIN = 0.1      # 日换手率下限 %（流动性过滤, 原 TURNOVER 因子降级为约束）
TURNOVER_MAX = 20.0     # 日换手率上限 %
MIN_LIST_YEARS = 5      # 上市 ≥ 5 年
VAL_MIN_WINDOW = 250    # 估值分位最短窗口（交易日, P0-A）
MIN_ROE = 0.08          # 非金融 ROE 门槛（TTM 或 5年中位数）
MIN_ROE_CYC = 0.04      # 周期行业 5年中位数门槛
MAX_LEV = 0.70          # 资产负债率上限
ROE_5Y_MIN_YEARS = 3    # 5年中位数至少覆盖的年数
DY_WINDOW_DAYS = 365    # 最近 12 个月股息窗口

# 安全边际分权重（主观先验, W-编号草案 W-PE_PCTL-DESIGN-20260825-01 等;
# 未经 v3 检验前一律"实验性", 生产开关 fail-closed）
DEFAULT_WEIGHTS = {'PE_PCTL': 0.30, 'PB_PCTL': 0.30, 'EP': 0.15,
                   'BP': 0.15, 'DY': 0.05, 'FCF_YIELD': 0.05}

EXPERIMENTAL_WARNING = ('⚠️ 实验性权重，未经统计检验，禁止实盘 ⚠️\n'
                        '    PE_PCTL/PB_PCTL/DY/FCF_YIELD 为主观先验权重（W-编号草案），\n'
                        '    须经 v3 统计检验（registry 前置登记 + 组合层检验）通过后方可转正式。')

_FAIL_CLOSED_MSG = (
    '[FAIL-CLOSED] 价值投资管线拒绝运行：4 个新估值因子权重（PE_PCTL/PB_PCTL/DY/FCF_YIELD）'
    '未经 v3 统计检验（P2.5 生产开关）。\n'
    '  如需实验性运行（仅供研究/检验，禁止实盘），请显式传入 experimental=True（run.py 加 --experimental）。')


# ============================================================
# 通用工具
# ============================================================

def _fmt_code(code):
    return str(code).strip().zfill(6)


def winsorize_zscore(s):
    """winsorize(±3σ) 后 z-score；常数/空列返回 0"""
    s = pd.to_numeric(s, errors='coerce').astype(float)
    if s.notna().sum() < 3:
        return s * 0.0
    m, sd = s.mean(), s.std()
    if pd.isna(sd) or sd == 0:
        return s * 0.0
    c = s.clip(m - 3 * sd, m + 3 * sd)
    return (c - c.mean()) / c.std()


def industry_zscore(df, col, industry_col, min_group=5):
    """行业内 winsorize+z-score（v2.1 P1-C: 申万一级）；小行业回退全市场"""
    market_z = winsorize_zscore(df[col])
    if industry_col not in df.columns or df[industry_col].notna().sum() == 0:
        return market_z
    def _f(g):
        return winsorize_zscore(g) if len(g) >= min_group else market_z.reindex(g.index)
    ind_z = df.groupby(industry_col)[col].transform(_f)
    return ind_z.fillna(market_z)


def last_quarter_ends(n=8, today=None):
    """最近 n 个季末日期（YYYYMMDD, ≤ today）"""
    today = today or pd.Timestamp.now()
    cands = [pd.Timestamp(f'{yy}{md}')
             for yy in range(today.year - 2, today.year + 1)
             for md in ('0331', '0630', '0930', '1231')]
    cands = [c for c in cands if c <= today]
    cands.sort()
    return [c.strftime('%Y%m%d') for c in cands[-n:]]


def _is_financial(sw1, raw_industry):
    """金融判定: 申万一级 ∈ {银行,非银金融}，兜底关键词匹配"""
    if isinstance(sw1, str) and sw1 in SW1_FIN:
        return True
    if isinstance(raw_industry, str):
        return any(k in raw_industry for k in FIN_KEYWORDS)
    return False


# ============================================================
# ① 可交易性过滤
# ============================================================

# 上市年限快速判定（Tier B）: 首次出现在此报告期或更早的 yjbb → 上市≥5年
# 理由: yjbb 报告期 20210331 的公告日 ≤ 2021-08, 距今 ≥5 年（保守口径, 无需逐股网络调用）
_LIST_AGE_CUTOFF = '20210331'


def _first_yjbb_period_map():
    """代码 → 首次出现报告期（本地 yjbb 缓存扫描, 无网络）"""
    import glob
    m = {}
    for f in sorted(glob.glob(os.path.join(CACHE_DIR, 'yjbb_*.parquet'))):
        base = os.path.basename(f).replace('yjbb_', '').replace('.parquet', '')
        p = base[:8]
        if len(p) != 8 or not p.isdigit():
            continue
        try:
            d = pd.read_parquet(f, columns=['股票代码'])
        except Exception:
            continue
        for c in d['股票代码'].astype(str).str.zfill(6):
            if c not in m:
                m[c] = p
    return m


def filter_universe(spot_df):
    """① 可交易性过滤（约束层, v2.1 §3.1 层①）

    规则: 市值≥30亿 / 换手率 0.1%~20% / 非ST·退 / 上市≥5年 / 非北交所(4/8/920)
    上市日推断三级链（避免全市场逐股网络调用）:
      Tier A: spot 自带'上市日期'列
      Tier B: yjbb 缓存首次出现报告期 ≤ 20210331（本地快速, 覆盖绝大多数存量股）
      Tier C: get_history 首个非NaN交易日（仅新上市/数据缺口股, 结果入 listing_dates.parquet 缓存）

    返回 DataFrame[代码,名称,...,通过(bool),原因(str)]；通过者 原因='OK'。
    """
    df = spot_df.copy()
    df['代码'] = df['代码'].map(_fmt_code)
    reasons = []
    first_map = _first_yjbb_period_map()

    # 数据源声明: 降级源(sina)无总市值/换手率 → 过滤无法执行
    mc = pd.to_numeric(df.get('总市值'), errors='coerce')
    to = pd.to_numeric(df.get('换手率'), errors='coerce')
    if mc.notna().sum() == 0:
        print('  [声明] 总市值全缺失（数据源降级无市值列）→ 市值≥30亿 无法验证，全部剔除')
    if to.notna().sum() == 0:
        print('  [声明] 换手率全缺失（数据源降级无换手列）→ 换手率过滤无法执行，全部剔除')

    for i, r in df.iterrows():
        code, name = r['代码'], str(r.get('名称', ''))
        fails = []
        # 停牌/退市/ST
        if pd.isna(r.get('最新价')):
            fails.append('停牌/无行情')
        if 'ST' in name or '退' in name:
            fails.append('ST/退市')
        if code.startswith(('4', '8', '920')):
            fails.append('北交所')
        # 市值
        mcv = mc.loc[i] if mc is not None and i in mc.index else np.nan
        if pd.isna(mcv):
            fails.append('总市值缺失')
        elif mcv < MIN_MCAP:
            fails.append('市值<30亿')
        # 换手率
        tov = to.loc[i] if to is not None and i in to.index else np.nan
        if pd.isna(tov):
            fails.append('换手率缺失')
        elif not (TURNOVER_MIN <= tov <= TURNOVER_MAX):
            fails.append(f'换手率{TURNOVER_MIN}%~{TURNOVER_MAX}%外')
        # 上市 ≥ 5 年（Tier A/B/C）
        ld = None
        if '上市日期' in df.columns and pd.notna(r.get('上市日期')):
            ld = pd.Timestamp(r['上市日期'])
        if ld is None:
            fp = first_map.get(code)
            if fp is not None and fp <= _LIST_AGE_CUTOFF:
                ld = pd.Timestamp(f'{fp[:4]}-{fp[4:6]}-{fp[6:]}')  # 报告期日=上市日上限, 保守
            else:
                ld = _listing_date(code, r)
        if ld is None:
            fails.append('上市日无法确认')
        else:
            age_y = (pd.Timestamp.now() - ld).days / 365.25
            if age_y < MIN_LIST_YEARS:
                fails.append(f'上市不足{MIN_LIST_YEARS}年')
        reasons.append('OK' if not fails else '|'.join(fails))

    df['通过'] = [x == 'OK' for x in reasons]
    df['原因'] = reasons
    n_ok = df['通过'].sum()
    print(f'  [过滤] 入池 {len(df)} → 通过 {n_ok}（剔除 {len(df) - n_ok}）')
    return df


# ---------- 上市日推断 ----------

def _listing_date(code, spot_row=None):
    """上市日推断三级链: spot'上市日期'列 → listing_dates.parquet 缓存 → get_history 首个非NaN交易日"""
    if spot_row is not None and '上市日期' in spot_row.index:
        ld = spot_row['上市日期']
        if pd.notna(ld):
            return pd.Timestamp(ld)
    cache_path = os.path.join(CACHE_DIR, 'listing_dates.parquet')
    if os.path.exists(cache_path):
        try:
            ld_map = pd.read_parquet(cache_path)
            if code in ld_map.index:
                return pd.Timestamp(ld_map.loc[code, '上市日期'])
        except Exception:
            pass
    try:
        h = get_history(code, start='19900101', end=None, adjust='')
        if h is not None and len(h) > 0:
            date_col = '日期' if '日期' in h.columns else h.columns[0]
            ld = pd.to_datetime(pd.to_numeric(pd.Series(h[date_col]), errors='coerce'),
                                format='%Y%m%d', errors='coerce').dropna()
            if len(ld) == 0:
                ld = pd.to_datetime(h[date_col], errors='coerce').dropna()
            if len(ld) > 0:
                ld = ld.min()
                # 持久化缓存
                try:
                    if os.path.exists(cache_path):
                        m = pd.read_parquet(cache_path)
                    else:
                        m = pd.DataFrame(columns=['代码', '上市日期']).set_index('代码')
                    m.loc[code, '上市日期'] = ld
                    m.to_parquet(cache_path)
                except Exception:
                    pass
                return ld
    except Exception as e:
        print(f'  [上市日] {code} 推断失败: {type(e).__name__}: {str(e)[:60]}')
    return None


# ============================================================
# 财务数据（含 5 年历史, 周期豁免用）
# ============================================================

def build_financials(today=None):
    """从 yjbb/zcfz 缓存构建财务表（PIT 最新期 TTM + 近5年 ROE/EPS 年度中位数）

    返回 DataFrame[代码, 名称, 所处行业, 行业SW1, 报告期, ROE_TTM, GPM, CFO_NI_TTM,
                   LEV, EPS_TTM, ROE_5Y_MED, EPS_5Y_MED]
    """
    today = today or pd.Timestamp.now()
    key_cols = ['股票代码', '股票简称', '每股收益', '每股净资产',
                '每股经营现金流量', '销售毛利率', '所处行业', '最新公告日期']

    # ---- 加载全部 yjbb 缓存（2015-09 起, 覆盖 5 年历史）----
    yjbb = {}
    import glob
    for f in sorted(glob.glob(os.path.join(CACHE_DIR, 'yjbb_*.parquet'))):
        base = os.path.basename(f)
        m = base.replace('yjbb_', '').replace('.parquet', '')
        p = m[:8]  # YYYYMMDD 段
        if len(p) == 8 and p.isdigit():
            yjbb[p] = pd.read_parquet(f)
    if not yjbb:
        from data_fetcher import get_financials
        for p in last_quarter_ends(8):
            d = get_financials(1, 'yjbb')
            if d is not None and len(d):
                yjbb[p] = d

    frames = []
    for p, d in yjbb.items():
        cols = [c for c in key_cols if c in d.columns]
        dd = d[cols].copy()
        dd['报告期'] = p
        frames.append(dd)
    allf = pd.concat(frames, ignore_index=True)
    allf['公告日期'] = pd.to_datetime(allf['最新公告日期'], errors='coerce')
    valid = allf[allf['公告日期'] <= today].copy()

    # ---- 逐股 PIT 最新报告期（TTM 口径, 与 multi_factor_value 同款）----
    def period_map(col):
        m = {}
        for p, d in yjbb.items():
            if col in d.columns:
                m[p] = pd.to_numeric(d.set_index('股票代码')[col], errors='coerce')
        return m

    eps_map = period_map('每股收益')
    cfps_map = period_map('每股经营现金流量')
    bps_map = period_map('每股净资产')

    def ttm_value(code, L, val_map):
        if L is None or L not in val_map:
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
            f = {'0331': 4.0, '0630': 2.0, '0930': 4.0 / 3}.get(L[4:], np.nan)
            return vL * f if not pd.isna(f) else np.nan
        return vL + vFY - vSP

    latest = (valid.sort_values(['股票代码', '报告期'], ascending=[True, False])
              .groupby('股票代码', as_index=False).first())

    # ---- 近 5 个完整年度中位数（周期豁免口径, P1-A）----
    # 年度 ROE/EPS 序列预计算一次（避免逐行 O(n×p×s) 嵌套）
    complete_years = sorted({int(y) for y in yjbb if y.endswith('1231')})
    cyears = [y for y in complete_years if y < today.year][-5:]
    roe_annual = {}  # p -> Series(股票代码 -> 年度 ROE=EPS/BPS)
    eps_annual = {}
    for y in cyears:
        p = f'{y}1231'
        if p in eps_map and p in bps_map:
            ep, bp = eps_map[p], bps_map[p]
            roe = (ep / bp).replace([np.inf, -np.inf], np.nan)
            roe_annual[p] = roe  # 保留负值行（中位数口径不剔负）
            eps_annual[p] = ep

    def _annual_median(code, col_map):
        vals = []
        for y in cyears:
            p = f'{y}1231'
            if p in col_map:
                v = col_map[p].get(code, np.nan)
                if pd.notna(v):
                    vals.append(v)
        if len(vals) < ROE_5Y_MIN_YEARS:
            return np.nan
        return float(np.median(vals))

    rows = []
    for _, r in latest.iterrows():
        code = str(r['股票代码'])
        L = r['报告期']
        eps_ttm = ttm_value(code, L, eps_map)
        cfps_ttm = ttm_value(code, L, cfps_map)
        bps = pd.to_numeric(r['每股净资产'], errors='coerce')
        roe_ttm = (eps_ttm / bps) if (pd.notna(eps_ttm) and pd.notna(bps) and bps > 0) else np.nan
        rows.append({
            '代码': code,
            '名称': r['股票简称'],
            '报告期': L,
            '所处行业': r['所处行业'],
            'EPS_TTM': eps_ttm,
            'ROE_TTM': roe_ttm,
            'GPM': pd.to_numeric(r['销售毛利率'], errors='coerce'),
            'CFO_NI_TTM': (cfps_ttm / eps_ttm) if (pd.notna(eps_ttm) and eps_ttm > 0 and pd.notna(cfps_ttm)) else np.nan,
            'ROE_5Y_MED': _annual_median(code, roe_annual),
            'EPS_5Y_MED': _annual_median(code, eps_annual),
        })
    qdf = pd.DataFrame(rows)

    # ---- LEV（zcfz 逐股 PIT）----
    import glob as _glob
    zframes = []
    for f in sorted(_glob.glob(os.path.join(CACHE_DIR, 'zcfz_*.parquet'))):
        try:
            d = pd.read_parquet(f)
            if '股票代码' not in d.columns or '资产负债率' not in d.columns:
                continue
            base = os.path.basename(f).replace('zcfz_', '').replace('.parquet', '')
            p = base[:8]
            dd = d[['股票代码', '资产负债率', '公告日期']].copy()
            dd['报告期'] = p
            zframes.append(dd)
        except Exception:
            continue
    if zframes:
        zall = pd.concat(zframes, ignore_index=True)
        zall['公告日期'] = pd.to_datetime(zall['公告日期'], errors='coerce')
        zvalid = zall[zall['公告日期'] <= today].sort_values(['股票代码', '报告期'], ascending=[True, False])
        zlatest = zvalid.groupby('股票代码', as_index=False).first()
        zlatest['资产负债率'] = pd.to_numeric(zlatest['资产负债率'], errors='coerce')
        qdf = qdf.merge(zlatest[['股票代码', '资产负债率']].rename(
            columns={'股票代码': '代码', '资产负债率': 'LEV'}), on='代码', how='left')

    # ---- 行业映射（东财/申万二级 → 申万一级）----
    try:
        ind_map = get_industry_map()
        qdf['行业SW1'] = qdf['所处行业'].map(lambda x: ind_map.get(str(x)) if pd.notna(x) else None)
        n_mapped = qdf['行业SW1'].notna().sum()
        print(f'  [行业] 申万一级映射 {n_mapped}/{len(qdf)}（覆盖率 {n_mapped / max(len(qdf), 1):.1%}）')
    except Exception as e:
        print(f'  [行业] 映射失败 {type(e).__name__}: {str(e)[:60]} → 行业SW1 缺失（周期豁免/行业内z 降级）')
        qdf['行业SW1'] = None

    print(f'  [财务] {len(qdf)} 只 | 近5年完整年度 {cyears} | LEV 覆盖 {qdf.get("LEV", pd.Series(dtype=float)).notna().sum()}')
    return qdf


# ============================================================
# ② 质量门槛（一票否决）
# ============================================================

def quality_gate(spot_df, financials_df):
    """② 质量门槛（排除层, v2.1 §3.1 层②, 一票否决）

    规则:
      - 非金融: ROE_TTM≥8% 或 近5年ROE中位数≥8%
      - 周期 8 行业豁免: 近5年ROE中位数≥4% 且 同源5年EPS中位数>0
      - 非金融: GPM>0 / CFO_NI_TTM>0 / LEV<70%（金融豁免）
      - EPS_TTM>0（含金融, P2-I: 亏损券商同样排除）

    financials_df 需含: 代码, ROE_TTM, ROE_5Y_MED, EPS_TTM, EPS_5Y_MED,
                        GPM, CFO_NI_TTM, LEV, 行业SW1(可空), 所处行业(可空)
    返回 DataFrame[代码, 名称, 行业SW1, 通过(bool), 原因(str), 各指标列]
    """
    fin = financials_df.copy()
    fin['代码'] = fin['代码'].map(_fmt_code)
    spot_codes = set(spot_df['代码'].map(_fmt_code))
    fin = fin[fin['代码'].isin(spot_codes)].copy()

    if '行业SW1' not in fin.columns:
        fin['行业SW1'] = None
    if '所处行业' not in fin.columns:
        fin['所处行业'] = None

    fin['_FIN'] = [_is_financial(a, b) for a, b in zip(fin['行业SW1'], fin['所处行业'])]
    fin['_CYC'] = fin['行业SW1'].isin(CYCLICAL_SW1)

    reasons = []
    for _, r in fin.iterrows():
        fails = []
        eps_ttm = r['EPS_TTM']
        if pd.isna(eps_ttm):
            fails.append('EPS_TTM缺失')
        elif eps_ttm <= 0:
            fails.append('EPS_TTM<=0')

        if r['_CYC']:
            # 周期豁免: 5年中位数≥4% 且 EPS>0
            if pd.isna(r['ROE_5Y_MED']):
                fails.append('ROE_5Y缺失')
            elif r['ROE_5Y_MED'] < MIN_ROE_CYC:
                fails.append(f'ROE_5Y<{MIN_ROE_CYC:.0%}')
            if pd.isna(r['EPS_5Y_MED']) or r['EPS_5Y_MED'] <= 0:
                fails.append('EPS_5Y<=0')
        else:
            roe_ok = (pd.notna(r['ROE_TTM']) and r['ROE_TTM'] >= MIN_ROE) or \
                     (pd.notna(r['ROE_5Y_MED']) and r['ROE_5Y_MED'] >= MIN_ROE)
            if pd.isna(r['ROE_TTM']) and pd.isna(r['ROE_5Y_MED']):
                fails.append('ROE缺失')
            elif not roe_ok:
                fails.append(f'ROE<{MIN_ROE:.0%}')

        if not r['_FIN']:
            if pd.isna(r['GPM']):
                fails.append('GPM缺失')
            elif r['GPM'] <= 0:
                fails.append('GPM<=0')
            if pd.isna(r['CFO_NI_TTM']):
                fails.append('CFO_NI缺失')
            elif r['CFO_NI_TTM'] <= 0:
                fails.append('CFO_NI<=0')
            if pd.isna(r['LEV']):
                fails.append('LEV缺失')
            elif r['LEV'] >= MAX_LEV:
                fails.append(f'LEV>={MAX_LEV:.0%}')
        reasons.append('OK' if not fails else '|'.join(fails))

    fin['通过'] = [x == 'OK' for x in reasons]
    fin['原因'] = reasons
    n_ok = fin['通过'].sum()
    print(f'  [门槛] 评估 {len(fin)} → 通过 {n_ok}（剔除 {len(fin) - n_ok}）')
    return fin


# ============================================================
# ③ 估值因子
# ============================================================

def _rolling_pctl(series, min_window=VAL_MIN_WINDOW):
    """实际历史滚动窗口分位（P0-A 主口径）: 每个交易日 = 截至当日全部历史的分位
    最短窗口 < min_window 交易日 → NaN；负值已由调用方剔除"""
    s = pd.to_numeric(series, errors='coerce').dropna().sort_index()
    if len(s) == 0:
        return s
    pct = s.expanding(min_periods=min_window).apply(
        lambda a: float((a <= a[-1]).mean()), raw=True)
    return pct


def _month_end_series(s):
    """月末最后交易日快照序列（index=月末交易日）"""
    s = pd.to_numeric(s, errors='coerce').dropna().sort_index()
    if len(s) == 0:
        return pd.Series(dtype=float)
    grp = s.groupby([s.index.year, s.index.month])
    ends = grp.apply(lambda g: g.index[-1])
    ends.index = range(len(ends))
    out = s.loc[ends.values]
    out.index = pd.DatetimeIndex(ends.values)
    return out


def _fcf_ttm(fcf_df, today=None):
    """TTM FCF = 最新期 + 去年年报 − 去年同期（累计口径）"""
    if fcf_df is None or len(fcf_df) == 0:
        return np.nan
    d = fcf_df.copy()
    d['report_date'] = pd.to_datetime(d['report_date'], errors='coerce')
    d = d.dropna(subset=['report_date', 'fcf']).sort_values('report_date')
    if len(d) == 0:
        return np.nan
    if today is not None:
        d = d[d['report_date'] <= pd.Timestamp(today)]
        if len(d) == 0:
            return np.nan
    latest = d.iloc[-1]
    L = latest['report_date']
    if L.strftime('%m%d') == '1231':
        return float(latest['fcf'])
    fy = pd.Timestamp(f'{L.year - 1}-12-31')
    sp = pd.Timestamp(f'{L.year - 1}-{L.month:02d}-{L.day:02d}')
    vFY = d.loc[d['report_date'] == fy, 'fcf']
    vSP = d.loc[d['report_date'] == sp, 'fcf']
    vFY = float(vFY.iloc[0]) if len(vFY) else np.nan
    vSP = float(vSP.iloc[0]) if len(vSP) else np.nan
    if pd.isna(vFY):
        return np.nan
    if pd.isna(vSP):
        f = {3: 4.0, 6: 2.0, 9: 4.0 / 3}.get(L.month, np.nan)
        return float(latest['fcf']) * f if not pd.isna(f) else np.nan
    return float(latest['fcf']) + vFY - vSP


def build_valuation_factors(codes, spot_df, financials_df, industry_map):
    """③ 估值因子（v2.1 §2.3 / §3.1 层③）

    返回 DataFrame(index=代码) 列:
      PE_PCTL/PB_PCTL  实际历史滚动窗口分位（最短≥250交易日, 更短缺失）月末快照
      EP_z/BP_z        申万一级行业内 z-score（EP=EPS_TTM/最新价, BP=1/市净率）
      DY               最近12个月每股股息(实施分配)/raw 最新价
      FCF_YIELD        TTM FCF/raw 总市值（金融股剔除出打分 → IS_FIN 标记, 打分时中性化→0）
      IS_FIN           金融股标记
      PE_PCTL_N/PB_PCTL_N  分位计算可用交易日数（窗口不足声明用）
    """
    codes = [_fmt_code(c) for c in codes]
    spot = spot_df.copy()
    spot['代码'] = spot['代码'].map(_fmt_code)
    spot = spot[spot['代码'].isin(codes)].set_index('代码')
    fin = financials_df.copy()
    fin['代码'] = fin['代码'].map(_fmt_code)
    fin = fin.set_index('代码')

    rows = []
    for code in codes:
        if code not in spot.index:
            continue
        sr = spot.loc[code]
        fr = fin.loc[code] if code in fin.index else None
        rows.append((code, sr, fr))
    print(f'  [因子] 估值因子计算 {len(rows)} 只（每只拉取估值历史/现金流/分红, 有缓存则秒回）')

    recs = []
    n_pe, n_pb, n_dy, n_fcf = 0, 0, 0, 0
    for code, sr, fr in rows:
        rec = {'代码': code, 'PE_PCTL': np.nan, 'PB_PCTL': np.nan,
               'EP_z': np.nan, 'BP_z': np.nan, 'DY': np.nan, 'FCF_YIELD': np.nan,
               'IS_FIN': 0, 'PE_PCTL_N': 0, 'PB_PCTL_N': 0}
        # 金融判定
        sw1 = fr['行业SW1'] if (fr is not None and pd.notna(fr.get('行业SW1'))) else None
        raw_ind = fr['所处行业'] if (fr is not None and pd.notna(fr.get('所处行业'))) else None
        if _is_financial(sw1, raw_ind):
            rec['IS_FIN'] = 1

        # ---- PE_PCTL / PB_PCTL: 滚动分位月末快照 ----
        try:
            vh = get_valuation_history(code)
            if vh is not None and len(vh):
                vh['date'] = pd.to_datetime(vh['date'], errors='coerce')
                vh = vh.dropna(subset=['date']).sort_values('date')
                pe = vh.loc[vh['pe_ttm'] > 0, ['date', 'pe_ttm']].set_index('date')['pe_ttm']
                if len(pe):
                    pe_pct = _month_end_series(_rolling_pctl(pe))
                    if len(pe_pct):
                        rec['PE_PCTL'] = float(pe_pct.iloc[-1])
                        rec['PE_PCTL_N'] = int(len(pe))
                        if len(pe) >= VAL_MIN_WINDOW:
                            n_pe += 1
                pb = vh.loc[vh['pb_mrq'] > 0, ['date', 'pb_mrq']].set_index('date')['pb_mrq']
                if len(pb):
                    pb_pct = _month_end_series(_rolling_pctl(pb))
                    if len(pb_pct):
                        rec['PB_PCTL'] = float(pb_pct.iloc[-1])
                        rec['PB_PCTL_N'] = int(len(pb))
                        if len(pb) >= VAL_MIN_WINDOW:
                            n_pb += 1
        except Exception as e:
            print(f'  [估值历史] {code} 失败: {type(e).__name__}: {str(e)[:60]}')

        # ---- DY: 最近12个月每股股息 / raw 最新价 ----
        try:
            price = pd.to_numeric(sr.get('最新价'), errors='coerce')
            divs = get_dividends(code)
            if divs is not None and len(divs) and pd.notna(price) and price > 0:
                divs['ex_date'] = pd.to_datetime(divs['ex_date'], errors='coerce')
                today = pd.Timestamp.now()
                win = divs[(divs['ex_date'] >= today - pd.Timedelta(days=DY_WINDOW_DAYS)) &
                           (divs['ex_date'] <= today)]
                if len(win):
                    per_share = pd.to_numeric(win['cash_div_per10'], errors='coerce').sum() / 10.0
                    rec['DY'] = float(per_share) / float(price)
                    n_dy += 1
                else:
                    rec['DY'] = 0.0
            else:
                rec['DY'] = 0.0
        except Exception as e:
            print(f'  [分红] {code} 失败: {type(e).__name__}: {str(e)[:60]}')

        # ---- FCF_YIELD: TTM FCF / raw 总市值 ----
        try:
            mcap = pd.to_numeric(sr.get('总市值'), errors='coerce')
            fcf_df = get_fcf(code)
            ttm = _fcf_ttm(fcf_df)
            if pd.notna(ttm) and pd.notna(mcap) and mcap > 0:
                rec['FCF_YIELD'] = float(ttm) / float(mcap)
                n_fcf += 1
        except Exception as e:
            print(f'  [现金流] {code} 失败: {type(e).__name__}: {str(e)[:60]}')

        recs.append(rec)

    fdf = pd.DataFrame(recs).set_index('代码')
    print(f'  [覆盖] PE_PCTL(≥250日) {n_pe}/{len(rows)} | PB_PCTL {n_pb} | DY {n_dy} | FCF_YIELD {n_fcf}')

    # ---- EP_z / BP_z: 申万一级行业内 z-score ----
    merged = fdf.reset_index().copy()
    merged['最新价'] = [spot.loc[c, '最新价'] if c in spot.index else np.nan for c in merged['代码']]
    merged['市净率'] = [spot.loc[c, '市净率'] if c in spot.index else np.nan for c in merged['代码']]
    merged['EPS_TTM'] = [fin.loc[c, 'EPS_TTM'] if c in fin.index else np.nan for c in merged['代码']]
    merged['行业SW1'] = [fin.loc[c, '行业SW1'] if c in fin.index and pd.notna(fin.loc[c].get('行业SW1')) else None
                         for c in merged['代码']]
    merged['所处行业'] = [fin.loc[c, '所处行业'] if c in fin.index and pd.notna(fin.loc[c].get('所处行业')) else None
                          for c in merged['代码']]
    px = pd.to_numeric(merged['最新价'], errors='coerce')
    eps = pd.to_numeric(merged['EPS_TTM'], errors='coerce')
    merged['EP_raw'] = eps / px
    merged['BP_raw'] = 1.0 / pd.to_numeric(merged['市净率'], errors='coerce')
    # 行业内 z; 行业SW1 缺失时回退原始行业, 再回退全市场
    ind_col = '行业SW1' if merged['行业SW1'].notna().sum() >= 5 else \
              ('所处行业' if merged['所处行业'].notna().sum() >= 5 else None)
    if ind_col is None:
        merged['EP_z'] = winsorize_zscore(merged['EP_raw'])
        merged['BP_z'] = winsorize_zscore(merged['BP_raw'])
        print('  [声明] 无行业映射 → EP_z/BP_z 回退全市场 z-score')
    else:
        merged['EP_z'] = industry_zscore(merged, 'EP_raw', ind_col)
        merged['BP_z'] = industry_zscore(merged, 'BP_raw', ind_col)

    fdf['EP_z'] = merged.set_index('代码')['EP_z']
    fdf['BP_z'] = merged.set_index('代码')['BP_z']
    fdf.index.name = '代码'
    return fdf


# ============================================================
# 安全边际分
# ============================================================

def safety_margin_score(factor_df, weights=None):
    """安全边际分（v2.1 §3.1 层③ 权重公式, 主观先验）

    默认权重: 0.30×PE_PCTL + 0.30×PB_PCTL + 0.15×EP_z + 0.15×BP_z + 0.05×DY_z + 0.05×FCF_YIELD_z
      - PE_PCTL/PB_PCTL 取负向（分位越低安全边际越大）
      - 全部因子 winsorize 后 z-score（EP_z/BP_z 已是行业内 z, 直接使用）
      - 金融股 FCF_YIELD 剔除出打分（中性化→0, P2-H）
      - 缺失 → 0（中性）

    返回 factor_df + 列[PE_PCTL_z, PB_PCTL_z, EP_z, BP_z, DY_z, FCF_YIELD_z, SCORE]
    """
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    total = sum(w.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f'权重和必须=1.0, 当前 {total:.4f}: {w}')
    df = factor_df.copy()

    df['PE_PCTL_z'] = -winsorize_zscore(df['PE_PCTL'])
    df['PB_PCTL_z'] = -winsorize_zscore(df['PB_PCTL'])
    df['DY_z'] = winsorize_zscore(df['DY'])
    df['FCF_YIELD_z'] = winsorize_zscore(df['FCF_YIELD'])
    if 'IS_FIN' in df.columns:
        fin_mask = df['IS_FIN'].fillna(0).astype(int) == 1
        if fin_mask.any():
            df.loc[fin_mask, 'FCF_YIELD_z'] = 0.0
            print(f'  [打分] 金融股 {int(fin_mask.sum())} 只 FCF_YIELD 中性化→0')
    # EP_z/BP_z 已是行业内 winsorize+z, 缺失→0
    for c in ('EP_z', 'BP_z'):
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

    df['SCORE'] = (w['PE_PCTL'] * df['PE_PCTL_z'] + w['PB_PCTL'] * df['PB_PCTL_z'] +
                   w['EP'] * df['EP_z'] + w['BP'] * df['BP_z'] +
                   w['DY'] * df['DY_z'] + w['FCF_YIELD'] * df['FCF_YIELD_z'])
    df['SCORE'] = df['SCORE'].fillna(0.0)
    print(f'  [打分] 权重 { {k: round(v, 3) for k, v in w.items()} } | '
          f'SCORE 非零 {int((df["SCORE"] != 0).sum())}/{len(df)}')
    return df


# ============================================================
# ④ 组合构建
# ============================================================

def build_portfolio(scored_df, top_n=12, industry_cap=0.30, stock_cap=0.10, aum=None):
    """④ 组合构建（v2.1 §3.1 层④）

    scored_df 需含: 代码, SCORE（可含 名称/行业SW1）
    规则: 按 SCORE 取 top_n 等权; 行业上限 industry_cap（申万一级, 超标行业丢最低分股）;
          个股上限 stock_cap（等权下约束持仓数 ≥ ceil(1/stock_cap)）;
          容量检查（报告项）: 单股单日 ≤5% ADV（需 aum 参数, 默认跳过）

    返回 DataFrame[代码, 名称, 行业SW1, SCORE, 权重] 按 SCORE 降序
    """
    df = scored_df.copy()
    df['代码'] = df['代码'].map(_fmt_code)
    if '名称' not in df.columns:
        df['名称'] = ''
    if '行业SW1' not in df.columns:
        df['行业SW1'] = None
    df = df.sort_values('SCORE', ascending=False).reset_index(drop=True)

    cands = df.head(top_n).copy()
    if len(cands) == 0:
        raise ValueError('无候选股票进入组合构建（过滤/质量门槛/打分后为空）')
    min_k = int(np.ceil(1.0 / stock_cap)) if stock_cap and stock_cap > 0 else 1

    # 行业上限: 超标行业循环丢最低分股（不低于 min_k 只）
    if industry_cap and industry_cap > 0:
        guard = 0
        while guard < 50:
            guard += 1
            k = len(cands)
            if k <= min_k:
                break
            cnt = cands['行业SW1'].fillna('未知').value_counts()
            bad = cnt[cnt / k > industry_cap]
            if len(bad) == 0:
                break
            worst_ind = bad.index[0]
            drop_idx = cands[cands['行业SW1'].fillna('未知') == worst_ind]['SCORE'].idxmin()
            cands = cands.drop(index=drop_idx).reset_index(drop=True)

    k = len(cands)
    cands['权重'] = 1.0 / k
    print(f'  [组合] top{top_n} → 保留 {k} 只, 等权 {1.0 / k:.2%} | '
          f'行业分布: {dict(cands["行业SW1"].fillna("未知").value_counts())}')

    if stock_cap and 1.0 / k > stock_cap + 1e-9:
        print(f'  [声明] 持仓 {k} 只 → 个股权重 {1.0 / k:.2%} > 上限 {stock_cap:.0%}（universe 不足, 无法满足）')

    # 容量检查（报告项）: 单股单日 ≤ 5% ADV
    if aum is not None:
        for _, r in cands.iterrows():
            notional = r['权重'] * aum
            adv = None
            try:
                to = pd.to_numeric(scored_df.loc[scored_df['代码'] == r['代码'], '换手率'], errors='coerce')
                mc = pd.to_numeric(scored_df.loc[scored_df['代码'] == r['代码'], '总市值'], errors='coerce')
                if len(to) and len(mc) and pd.notna(to.iloc[0]) and pd.notna(mc.iloc[0]):
                    adv = mc.iloc[0] * to.iloc[0] / 100.0
            except Exception:
                pass
            if adv is not None and notional > 0.05 * adv:
                print(f'  [容量告警] {r["代码"]} 目标市值 {notional / 1e8:.0f}亿 > 5%ADV {0.05 * adv / 1e8:.0f}亿')
    else:
        print('  [容量] aum=None → 5%ADV 容量检查跳过（P5 敏感性项）')
    return cands[['代码', '名称', '行业SW1', 'SCORE', '权重']]


# ============================================================
# 信号生成（backtest.py 兼容语义）
# ============================================================

def generate_signals(portfolio, prev_positions=None, rebalance_date=None,
                     sell_codes=None, event_date=None):
    """信号生成（v2.1 §5 P1-B: signals 行 = 完整目标组合语义）

    backtest.py 约定: index=调仓日, columns=股票代码, values=目标权重;
    ⚠️ 未列出的持仓按权重 0 全部清仓 → 事件驱动卖出行必须是**完整持仓快照**。

    - 季度调仓行: 完整目标组合（等权, portfolio 全量）
    - 事件驱动卖出行: prev_positions 全量快照, 卖出股权重=0, 其余保留**原权重**
    - 卖出触发日恰为季度调仓日 → 合并为单行（调仓行优先）
    - sell_codes=None 时默认卖出 prev_positions 中不在 portfolio 的代码

    返回 DataFrame(index=DatetimeIndex 调仓日, columns=全部代码, values=目标权重, 未涉及=0.0)
    """
    def _norm(x, name):
        if x is None:
            return {}
        if isinstance(x, pd.DataFrame):
            col = '权重' if '权重' in x.columns else x.columns[-1]
            return {_fmt_code(c): float(w) for c, w in zip(x['代码'], x[col])}
        if isinstance(x, pd.Series):
            return {_fmt_code(c): float(w) for c, w in x.items()}
        if isinstance(x, dict):
            return {_fmt_code(c): float(w) for c, w in x.items()}
        raise TypeError(f'{name} 类型不支持: {type(x)}')

    portfolio_w = _norm(portfolio, 'portfolio')
    if not portfolio_w:
        raise ValueError('portfolio 为空, 无法生成信号')
    if rebalance_date is None:
        rebalance_date = pd.Timestamp.now().normalize()
    rebalance_date = pd.Timestamp(rebalance_date)
    event_date = pd.Timestamp(event_date) if event_date is not None else rebalance_date

    prev = _norm(prev_positions, 'prev_positions')

    rows = []  # (date, dict)
    if not prev:
        rows.append((rebalance_date, dict(portfolio_w)))
    else:
        sells = set(_fmt_code(c) for c in (sell_codes or []))
        if not sells:
            sells = set(prev.keys()) - set(portfolio_w.keys())
        # 事件驱动卖出行 = 完整持仓快照（未动持仓保留原权重, 禁止只列卖出股）
        snapshot = {c: (0.0 if c in sells else w) for c, w in prev.items()}
        rows.append((event_date, snapshot))
        # 季度调仓行 = 完整目标组合
        rows.append((rebalance_date, dict(portfolio_w)))

    # 同日合并（调仓行在后, 覆盖事件行 → 卖出触发日恰为调仓日时合并为单行）
    merged = {}
    for d, w in rows:
        merged[d] = w

    # 完整快照语义: 全部行的列 = 所有出现过的代码并集（含被合并行/卖出股 → 显式 0.0,
    # 杜绝"未列出即清仓"歧义）
    all_codes = sorted(set().union(*[set(w.keys()) for _, w in rows]))
    dates = sorted(merged.keys())
    out = pd.DataFrame(0.0, index=pd.DatetimeIndex(dates), columns=all_codes)
    for d, w in merged.items():
        for c in all_codes:
            out.loc[d, c] = w.get(c, 0.0)
    for d in dates:
        print(f'  [信号] {pd.Timestamp(d).date()} 行: {int((out.loc[d] > 0).sum())} 只有权, '
              f'列数 {len(all_codes)}（完整快照）')
    return out


# ---------- 卖出规则辅助（每日检查, T+1 执行; 供 P4/P5 回测信号循环使用） ----------

def percentile_sell_flag(month_end_pctl, threshold=0.80, confirm_months=2):
    """月末分位连续 confirm_months 个月 > threshold → (True, 详情)。
    month_end_pctl: 月末快照分位序列（index=月末交易日）。"""
    s = pd.to_numeric(month_end_pctl, errors='coerce').dropna().sort_index()
    if len(s) < confirm_months:
        return False, f'分位序列仅 {len(s)} 个月(<{confirm_months}), 无法确认'
    last = s.iloc[-confirm_months:]
    if bool((last > threshold).all()):
        return True, f'月末分位连续{confirm_months}个月>{threshold:.0%}: ' + \
                     ', '.join(f'{d.date()}:{v:.2f}' for d, v in last.items())
    return False, '未触发'


def check_sell_rules(code, month_end_pctl=None, quality_row=None, name='',
                     threshold=0.80, confirm_months=2):
    """卖出规则汇总: ①分位顶线(连续2月>80%) ②质量破门槛 ③ST/退市
    返回 (sell: bool, reason: str)。供每日监控/回测信号循环调用。"""
    reasons = []
    if month_end_pctl is not None and len(month_end_pctl):
        flag, detail = percentile_sell_flag(month_end_pctl, threshold, confirm_months)
        if flag:
            reasons.append(f'分位顶线:{detail}')
    if quality_row is not None:
        if quality_row.get('通过') is False:
            reasons.append(f'质量破门槛:{quality_row.get("原因", "")}')
    if 'ST' in str(name) or '退' in str(name):
        reasons.append('ST/退市')
    return (bool(reasons), '|'.join(reasons))


# ============================================================
# 主入口（生产开关 fail-closed, P2.5）
# ============================================================

def run_value_pipeline(top_n=12, experimental=False):
    """价值投资主管线（四层: 过滤→门槛→因子→打分→组合→信号）

    ⚠️ 生产开关（P2.5）: 4 个新估值因子权重未经 v3 统计检验,
       experimental=False 默认**拒绝运行**（fail-closed）;
       experimental=True 仅允许实验性运行, 输出强制标注禁止实盘。

    返回 (scored, selected) — 与 multi_factor_value.run_full_pipeline 兼容的二元组:
      scored   = 全量打分表（含 SCORE 与各因子分）
      selected = 组合构建结果 DataFrame[代码,名称,行业SW1,SCORE,权重]
    """
    if not experimental:
        print(_FAIL_CLOSED_MSG)
        raise RuntimeError(_FAIL_CLOSED_MSG)

    print('\n' + '=' * 78)
    print('  价值投资决策系统 v1（定稿 v2.1 管线）— 实验性运行')
    print(EXPERIMENTAL_WARNING)
    print('=' * 78)

    # 1) 财务数据先于行情（东财被封时, 新浪兜底需要本地财务缓存）
    t0 = time.time()
    financials = build_financials()
    spot = get_spot_data()
    print(f'  [数据] spot {len(spot)} 只 | 财务 {len(financials)} 只 | 耗时 {time.time() - t0:.1f}s')

    # 2) 过滤 + 门槛
    filtered = filter_universe(spot)
    passed_codes = filtered.loc[filtered['通过'], '代码'].tolist()
    spot_f = filtered[filtered['通过']].copy()
    gated = quality_gate(spot_f, financials)
    gate_pass = gated[gated['通过']].copy()
    print(f'  [管线] 过滤 {len(passed_codes)} → 质量门槛通过 {len(gate_pass)}')
    if len(gate_pass) == 0:
        raise RuntimeError('无股票通过 ①可交易性过滤 + ②质量门槛（检查数据源/阈值）')

    # 3) 估值因子 + 打分
    ind_map = {}
    try:
        ind_map = get_industry_map()
    except Exception as e:
        print(f'  [行业映射] 失败: {type(e).__name__}: {str(e)[:60]}')
    factor_df = build_valuation_factors(gate_pass['代码'].tolist(), spot_f, financials, ind_map)
    scored = safety_margin_score(factor_df)
    scored = scored.reset_index()
    scored['名称'] = scored['代码'].map(dict(zip(spot_f['代码'], spot_f['名称'])))
    scored['行业SW1'] = scored['代码'].map(
        dict(zip(gate_pass['代码'], gate_pass['行业SW1'].fillna(''))))
    scored['总市值'] = scored['代码'].map(dict(zip(spot_f['代码'], pd.to_numeric(spot_f['总市值'], errors='coerce'))))
    scored['换手率'] = scored['代码'].map(dict(zip(spot_f['代码'], pd.to_numeric(spot_f['换手率'], errors='coerce'))))

    # 4) 组合 + 信号
    selected = build_portfolio(scored, top_n=top_n)
    signals = generate_signals(selected)
    print(f'\n  [完成] 价值投资管线输出: 打分 {len(scored)} 只 | 组合 {len(selected)} 只 | '
          f'信号 {len(signals)} 行 | 耗时 {time.time() - t0:.1f}s')
    return scored, selected


if __name__ == '__main__':
    try:
        run_value_pipeline(top_n=12, experimental=False)
    except RuntimeError as e:
        sys.exit(1)
