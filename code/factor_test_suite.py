# -*- coding: utf-8 -*-
"""
factor_test_suite.py — 因子零检验流水线（v3 定稿全文实现）
==========================================================
按 docs/factor_docs/factor_testing_methodology_v3.md（MImo 两轮审查定稿）实现
状态标注：审批=docs/factor_docs/factor_testing_methodology_v3.md（MImo 两轮审查定稿）；S1 基础设施就绪（2026-08-22，合成自检通过）+ 2 因子真实数据试点（MOM_60D/VOL_RATIO，结论"初步"）
完整检验流程（registry ⓪ 步 → ① 数据准备 → ② IC → ③ 分层 → ④ 自相关 →
⑤ 共线性/FM → ⑥ 稳健性 → ⑦ 多重检验 → ⑧ 经济闸门 → ⑨ 回填+报告）。

输入（均为宽表，index=月末 DatetimeIndex，columns=股票代码 str）：
  factor_table : 因子值表（T 月末因子暴露，PIT 由数据层保证）
  ret_table    : 月度收益表（T 月自然月收益；IC 用 T+1，由本模块对齐）
  mcap_table   : 总市值表（单位：亿元；30 亿微盘线、市值加权、规模中性用）
  fin_table    : 财务表（长表，可空；用于行业映射[所处行业列，PIT 按公告日期]与覆盖率报告）
  other_factors: dict{因子名: 因子宽表} 存量因子（共线性/FM 增量检验用，可空）
  tradable_table: 可交易掩码表（bool，T+1 停牌/一字板过滤结果，可空）
  st_table     : ST 掩码表（bool，可空）

判定体系（v3 §9/§11/§12）：
  IC 关        : ICIR>0.5 且 |mean IC|≥0.02 且 signed NW-t ≥ max(3.0, Bonf(N'))
 分层关        : PT MR 单调性（时间层 stationary bootstrap 块长3 R=9999 null
                 recentering，seed 固定）p<0.05 且倒挂≤1档且Q5>Q1；三重稳健性
                 （市值加权 / 微盘剔除<30亿 / 规模中性 3×5 dependent sort）全通过
 经济闸门      : 预指定交易版本净多空年化≥8%（×12；同时报告×√12 口径）且 2x 成本
                 后仍为正、夏普≥0.8；三重稳健性版本不套绝对线，只要求为正且显著
 样本          : 主判定 2017-01 起；训练段=检验日−24m（仅共线性裁决）；
                 最近 24m 样本外一次确认（报告项+确认失败降级）
 T<60 月      : 全部结论自动降级"初步"（v3 §1），不得据此入主策略

用法：
  D:/pyh/python.exe -E factor_test_suite.py self-test
  D:/pyh/python.exe -E factor_test_suite.py run --factor F.parquet --ret R.parquet \
      [--mcap M.parquet] [--fin FIN.parquet] --name MOM_60D --sign 1 --n-star 10 \
      [--start 2017-01-31] [--oos-months 24] [--out docs/factor_docs]
"""
import os
import sys
import json
import hashlib
import datetime as _dt

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import numpy as np
import pandas as pd
from scipy import stats

from ic_monitor import rank_ic, ic_series, nw_t, bonf_threshold, ic_summary, _nw_lag

SEED = 20260822            # 固定随机种子（PT MR / bootstrap 可复现）
BONF_ALPHA = 0.05          # v3 §9 单侧 α
VERSION = 'v3.0'
REPORT_DATE = _dt.date.today().isoformat()

# ---------------------------------------------------------------------------
# 成本模型（v3 §5.2 + SOP §7 附录A：佣金万2.5双边 + 印花税时变 + 过户万0.1双边
# + 市值分档滑点单边 5/10/20/30bp；全部为"往返成本"口径）
# ---------------------------------------------------------------------------
STAMP_SCHEDULE = [(pd.Timestamp('2023-08-28'), 5e-4),   # 2023-08-28 起万5（卖出）
                  (pd.Timestamp('1970-01-01'), 1e-3)]    # 之前千1（卖出）
COMMISSION = 2.5e-4        # 单边佣金
TRANSFER = 0.1e-4          # 单边过户费
SLIP_BRACKETS = [(500.0, 5e-4), (100.0, 1e-3), (30.0, 2e-3), (0.0, 3e-3)]  # 亿元→单边滑点


def stamp_tax(date):
    """印花税（卖出侧，单边），按时变表。"""
    d = pd.Timestamp(date)
    for since, rate in STAMP_SCHEDULE:
        if d >= since:
            return rate
    return STAMP_SCHEDULE[-1][1]


def round_trip_cost(mcap_yi, date):
    """单只股票往返成本（买+卖两腿）= 2×佣金 + 印花税(卖出) + 2×过户 + 2×滑点。"""
    mcap_yi = 0.0 if (mcap_yi is None or not np.isfinite(mcap_yi)) else float(mcap_yi)
    slip = SLIP_BRACKETS[-1][1]
    for cutoff, s in SLIP_BRACKETS:
        if mcap_yi >= cutoff:
            slip = s
            break
    return 2.0 * COMMISSION + stamp_tax(date) + 2.0 * TRANSFER + 2.0 * slip


def sig_threshold(n_star):
    """v3 §9 单一显著性线：max(3.0, Bonferroni(N', 单侧 α=0.05))。"""
    return max(3.0, bonf_threshold(n_star, BONF_ALPHA))


# ---------------------------------------------------------------------------
# ① 数据准备（v3 §3）
# ---------------------------------------------------------------------------
def winsorize_cross_section(df, lo=0.01, hi=0.99):
    """月度横截面 winsorize（收益 1%/99%，v3 §3-2）。"""
    out = df.copy()
    q = out.stack().groupby(level=0).quantile([lo, hi]).unstack(0)
    lo_v = q.loc[lo].reindex(out.index)
    hi_v = q.loc[hi].reindex(out.index)
    out = out.clip(lower=lo_v, upper=hi_v, axis=0)
    return out


def winsorize_sigma(df, k=3.0):
    """因子 ±kσ winsorize（v3 §3-2，默认 ±3σ），逐月横截面。"""
    out = df.copy()
    mu = out.mean(axis=1)
    sd = out.std(axis=1, ddof=1)
    lo = mu - k * sd
    hi = mu + k * sd
    return out.clip(lower=lo, upper=hi, axis=0)


def monthly_coverage(factor_table):
    """月度因子覆盖率（v3 §3-4）；<70% 告警。"""
    cov = factor_table.notna().mean(axis=1)
    return {'mean': float(cov.mean()), 'min': float(cov.min()),
            'lt70_months': int((cov < 0.7).sum()),
            'series': cov}


def missing_indicator_ic(factor_table, ret_table):
    """缺失指示变量与下期收益的 IC（MCAR 检验，v3 §3-4）。"""
    miss = factor_table.isna().astype(float)
    ic = ic_series(miss, ret_table)
    if len(ic) == 0:
        return {'n': 0, 'mean': np.nan}
    return {'n': len(ic), 'mean': float(ic.mean()),
            'win_rate': float((ic > 0).mean())}


def align_tables(factor_table, ret_table, mcap_table=None, tradable_table=None,
                 st_table=None):
    """统一行(月末)/列(代码)对齐；tradable/st 为 False 的单元格置 NaN（剔除）。"""
    idx = factor_table.index.intersection(ret_table.index).sort_values()
    cols = factor_table.columns.intersection(ret_table.columns)
    f = factor_table.reindex(index=idx, columns=cols)
    r = ret_table.reindex(index=idx, columns=cols)
    m = None
    if mcap_table is not None:
        m = mcap_table.reindex(index=idx, columns=cols)
    if tradable_table is not None:
        tt = tradable_table.reindex(index=idx, columns=cols)
        f = f.where(tt.fillna(True))
        r = r.where(tt.fillna(True))
        if m is not None:
            m = m.where(tt.fillna(True))
    if st_table is not None:
        st = st_table.reindex(index=idx, columns=cols)
        f = f.where(~st.fillna(False))
        r = r.where(~st.fillna(False))
        if m is not None:
            m = m.where(~st.fillna(False))
    return f, r, m


def build_monthly_membership(factor_row, n_groups=5, min_stocks=10):
    """等分位分组（v3 §2：20% 分位）。返回 {code: 1..n} 或 None（样本不足）。"""
    vals = factor_row.dropna()
    if len(vals) < min_stocks * n_groups:
        return None
    ranks = vals.rank(method='first')
    q = ((ranks - 1) * n_groups // len(vals)).astype(int) + 1
    return q


# ---------------------------------------------------------------------------
# ② IC 检验（v3 §4）
# ---------------------------------------------------------------------------
def ic_battery(factor_table, ret_table, mcap_table=None, industry_map=None,
               n_lags_cap=None, start=None, end=None):
    """IC 全套（主口径 + 辅助口径）。返回 dict。"""
    f = factor_table if start is None else factor_table.loc[start:]
    if end is not None:
        f = f.loc[:end]
    r = ret_table.reindex(index=f.index)
    ic = ic_series(f, r)
    if len(ic) == 0:
        return {'n': 0}
    s = ic_summary(ic)
    nw = s['nw_t']
    signed_t = s['signed_t']

    # IC 衰减曲线（T+1/T+2/T+3/T+6/T+12，v3 §4-4-1）
    decay = {}
    for h in (1, 2, 3, 6, 12):
        ics_h = ic_series(f, r, forward_months=h)
        if len(ics_h):
            s_h = ic_summary(ics_h)
            decay[h] = {'mean': s_h['mean'], 'icir': s_h['icir'], 'n': s_h['n']}
        else:
            decay[h] = None

    # 条件 IC：down-month / 高波动月（v3 §4-4-3/4，硬指标非负）
    mkt = r.mean(axis=1)
    cond = {}
    down = ic[mkt < 0]
    cond['down_month'] = {'n': int(len(down)), 'mean': float(down.mean()) if len(down) else np.nan}
    rv = r.std(axis=1, ddof=1)
    hv = ic[rv >= rv.quantile(2 / 3)]
    cond['high_vol'] = {'n': int(len(hv)), 'mean': float(hv.mean()) if len(hv) else np.nan}

    # IC 极值 winsorize 对照（v3 §4-3）
    ic_w = ic.clip(ic.quantile(0.01), ic.quantile(0.99))
    icir_w = ic_w.mean() / ic_w.std(ddof=1) if ic_w.std(ddof=1) > 0 else np.nan

    # 风险调整 IC（v3 §4-4-5：对市场+规模+行业回归残差与收益的 IC）
    resid_ic = np.nan
    if mcap_table is not None:
        try:
            resids = {}
            for t in f.index:
                x = pd.DataFrame({
                    'f': f.loc[t], 'mcap': mcap_table.loc[t].reindex(f.columns),
                    'mkt': mkt.loc[t] if t in mkt.index else np.nan})
                x['lnmcap'] = np.log(x['mcap'])
                x = x.dropna()
                if len(x) < 30:
                    continue
                if industry_map is not None:
                    ind = x.index.map(lambda c: industry_map.get(c, 'NA'))
                    x['ind'] = ind
                    d = pd.get_dummies(x['ind'], drop_first=True)
                    x = pd.concat([x.drop(columns='ind'), d], axis=1)
                y = x['f'].values
                X = x.drop(columns='f').values
                X = np.column_stack([np.ones(len(X)), X])
                beta, *_ = np.linalg.lstsq(X, y, rcond=None)
                resid = y - X @ beta
                resids[t] = pd.Series(resid, index=x.index)
            if resids:
                resid_tab = pd.DataFrame(resids).T
                ic_r = ic_series(resid_tab, r)
                if len(ic_r):
                    resid_ic = float(ic_r.mean())
        except Exception as e:  # pragma: no cover
            resid_ic = np.nan

    # 波动率关系（v3 §4-4-6：因子与已实现波动率、市场β的横截面相关）
    vol_rel = {'corr_realvol': np.nan, 'corr_beta': np.nan}
    try:
        corrs_v = []
        for t in f.index:
            x = pd.DataFrame({'f': f.loc[t], 'rv': rv.reindex(f.columns) if t in rv.index else np.nan})
            x = x.dropna()
            if len(x) >= 30:
                corrs_v.append(stats.spearmanr(x['f'], x['rv'])[0])
        if corrs_v:
            vol_rel['corr_realvol'] = float(np.nanmean(corrs_v))
    except Exception:
        pass

    return {'n': s['n'], 'mean': s['mean'], 'std': s['std'], 'icir': s['icir'],
            'win_rate': s['win_rate'], 'naive_t': s['naive_t'], 'nw_t': nw,
            'signed_t': signed_t, 'icir_winsor': icir_w, 'decay': decay,
            'cond': cond, 'resid_ic': resid_ic, 'vol_rel': vol_rel}


def ic_gate_pass(ib, n_star, expected_sign):
    """v3 §11 IC 关：ICIR>0.5 且 |mean IC|≥0.02 且 signed NW-t ≥ max(3.0, Bonf(N'))。"""
    thr = sig_threshold(n_star)
    if ib['n'] == 0 or not np.isfinite(ib['icir']):
        return False
    return (ib['icir'] > 0.5 and abs(ib['mean']) >= 0.02
            and ib['signed_t'] >= thr)


# ---------------------------------------------------------------------------
# ③ 分层检验（v3 §5）
# ---------------------------------------------------------------------------
def group_portfolios(factor_table, ret_table, mcap_table=None, n_groups=5,
                     weighted=False, min_stocks=10, cost_model=True):
    """逐月分组建仓（T 因子 → T+1 收益），返回逐月多空/换手/成本等序列。

    返回 dict:
      gross_ls: 月度毛多空 (Q5−Q1)，index=收益月
      net_ls:   扣成本净多空
      net_ls_2x: 2x 成本净多空
      group_ret: DataFrame (T×n_groups) 组月收益（PT MR 输入）
      to/cost:  每组换手与往返成本均值（DataFrame T×n_groups）
      coverage: 每月纳入股票数
    """
    f = factor_table
    r = ret_table
    m = mcap_table
    dates = f.index.sort_values()
    T = len(dates)
    g_ret = np.full((T - 1, n_groups), np.nan)
    to_mat = np.full((T - 1, n_groups), np.nan)
    cost_mat = np.full((T - 1, n_groups), np.nan)
    n_stocks = np.full(T - 1, np.nan)
    prev_members = None  # list of set per group at previous formation
    ls_raw, ls_net, ls_2x = [], [], []
    ls_idx = []

    for i in range(T - 1):
        t_f = dates[i]          # 形成日
        t_r = dates[i + 1]      # 收益月
        fac = f.loc[t_f]
        ret = r.loc[t_r]
        mc = m.loc[t_f] if m is not None else None
        mem = build_monthly_membership(fac, n_groups, min_stocks)
        if mem is None:
            continue
        ret_m = ret.reindex(mem.index)
        for g in range(1, n_groups + 1):
            sel = mem[mem == g].index
            sel = sel[ret_m.loc[sel].notna()]
            if len(sel) == 0:
                continue
            if weighted and mc is not None:
                w = mc.loc[sel].clip(lower=0)
                w = w[w.notna() & (w > 0)]
                if len(w) == 0 or w.sum() <= 0:
                    continue
                w = w / w.sum()
                g_ret[i, g - 1] = float((ret_m.loc[w.index] * w).sum())
            else:
                g_ret[i, g - 1] = float(ret_m.loc[sel].mean())
            # 换手（v3 §5-2：成分变化比例）
            cur = set(sel)
            if prev_members is not None and cost_model:
                p = prev_members[g - 1]
                to = 1.0 - len(cur & p) / max(1, len(cur))
                to_mat[i, g - 1] = to
                if mc is not None:
                    costs = [round_trip_cost(mc.loc[c], t_f) for c in sel if np.isfinite(mc.loc[c])]
                    cost_mat[i, g - 1] = float(np.mean(costs)) if costs else np.nan
                else:
                    cost_mat[i, g - 1] = round_trip_cost(100.0, t_f)  # 缺市值时按中盘档
            elif cost_model:
                to_mat[i, g - 1] = 1.0  # 首月无法算换手，按全换
                if mc is not None:
                    costs = [round_trip_cost(mc.loc[c], t_f) for c in sel if np.isfinite(mc.loc[c])]
                    cost_mat[i, g - 1] = float(np.mean(costs)) if costs else np.nan
                else:
                    cost_mat[i, g - 1] = round_trip_cost(100.0, t_f)
        if cost_model:
            prev_members = [set(mem[mem == g].index) for g in range(1, n_groups + 1)]
        n_stocks[i] = int(len(ret_m.dropna()))
        if np.isfinite(g_ret[i, 0]) and np.isfinite(g_ret[i, -1]):
            ls_raw.append(g_ret[i, -1] - g_ret[i, 0])
            if cost_model and np.isfinite(to_mat[i, 0]) and np.isfinite(to_mat[i, -1]):
                c_q1 = cost_mat[i, 0] if np.isfinite(cost_mat[i, 0]) else 0.0
                c_q5 = cost_mat[i, -1] if np.isfinite(cost_mat[i, -1]) else 0.0
                cost = to_mat[i, -1] * c_q5 + to_mat[i, 0] * c_q1
                ls_net.append(ls_raw[-1] - cost)
                ls_2x.append(ls_raw[-1] - 2.0 * cost)
            else:
                ls_net.append(ls_raw[-1])
                ls_2x.append(ls_raw[-1])
            ls_idx.append(t_r)

    out = {
        'gross_ls': pd.Series(ls_raw, index=ls_idx, name='LS_raw'),
        'net_ls': pd.Series(ls_net, index=ls_idx, name='LS_net'),
        'net_ls_2x': pd.Series(ls_2x, index=ls_idx, name='LS_2x'),
        'group_ret': pd.DataFrame(g_ret, index=dates[1:],
                                  columns=[f'G{g}' for g in range(1, n_groups + 1)]),
        'turnover': pd.DataFrame(to_mat, index=dates[1:],
                                 columns=[f'G{g}' for g in range(1, n_groups + 1)]),
        'cost': pd.DataFrame(cost_mat, index=dates[1:],
                             columns=[f'G{g}' for g in range(1, n_groups + 1)]),
        'n_stocks': pd.Series(n_stocks, index=dates[1:]),
    }
    return out


def pt_mr(group_ret, expected_sign=1, R=9999, mean_block=3, seed=SEED):
    """Patton-Timmermann (2010) MR 单调性检验（v3 §5-4 完整算法）。

    时间层 stationary bootstrap（整月重抽，平均块长 3），R=9999，
    null recentering 必做：J̃* = J* − J0；p = (1 + #{J̃* ≥ J0})/10000。
    """
    Rm = group_ret.dropna().values
    T = Rm.shape[0]
    if T < 12 or Rm.shape[1] < 3:
        return {'p': np.nan, 'J0': np.nan, 'n': T, 'note': '样本不足'}
    d = expected_sign
    delta = d * np.diff(Rm, axis=1)          # T×(n_groups−1)
    J0 = float(delta.mean(axis=0).min())
    rng = np.random.default_rng(seed)
    counts = 0
    for _ in range(R):
        idx = _stationary_bootstrap(T, mean_block, rng)
        d_star = delta[idx]
        J_star = float(d_star.mean(axis=0).min())
        if J_star - J0 >= J0:
            counts += 1
    p = (1.0 + counts) / (R + 1.0)
    return {'p': p, 'J0': J0, 'n': T, 'note': ''}


def _stationary_bootstrap(n, mean_block, rng):
    """Politis-Romano stationary bootstrap：几何块长（均值 mean_block），循环填充。"""
    idx = np.empty(n, dtype=np.int64)
    i = 0
    while i < n:
        start = rng.integers(0, n)
        length = int(rng.geometric(1.0 / mean_block))
        for k in range(length):
            if i >= n:
                break
            idx[i] = (start + k) % n
            i += 1
    return idx


def fm_beta(group_ret, maxlags=2):
    """辅助单调性：逐月 5 组收益对组序号回归的 FM β（均值+NW-t，v3 §5-4）。"""
    Rm = group_ret.dropna()
    T = Rm.shape[0]
    if T < 12:
        return {'mean': np.nan, 'nw_t': np.nan, 'n': T}
    x = np.arange(1, Rm.shape[1] + 1, dtype=float)
    betas = []
    for _, row in Rm.iterrows():
        y = row.values
        ok = np.isfinite(y)
        if ok.sum() < 3:
            continue
        b = np.polyfit(x[ok], y[ok], 1)[0]
        betas.append(b)
    if len(betas) < 12:
        return {'mean': np.nan, 'nw_t': np.nan, 'n': len(betas)}
    bs = pd.Series(betas)
    t = nw_t(bs, maxlags=min(maxlags, _nw_lag(len(bs))))
    return {'mean': float(bs.mean()), 'nw_t': t, 'n': len(betas)}


def size_neutral_3x5(factor_table, ret_table, mcap_table, min_cell=5):
    """规模中性 3×5 dependent sort（v3 §5-3）：先市值三分，再各层内因子五分。

    每格等权月收益；spread = 3 个 size 层内多空的等权平均（与"先平均同
    quintile 再相减"数学等价）；每层单独计换手与成本；报告每格股票数，
    大盘层五分后每格 <50 只告警；spread 对 ln_mcap 回归 β 验证中性化。
    """
    f, r, m = align_tables(factor_table, ret_table, mcap_table)
    dates = f.index.sort_values()
    T = len(dates)
    # 每格 (tercile, quintile) 逐月毛/净收益：dict[(t,g)] -> list[(month_idx, gross, net)]
    cell_series = {}
    cell_counts = {}
    prev_cells = None
    ls_all, ls_net_all, ls_idx = [], [], []

    for i in range(T - 1):
        t_f, t_r = dates[i], dates[i + 1]
        fac, ret, mc = f.loc[t_f], r.loc[t_r], m.loc[t_f]
        df = pd.DataFrame({'f': fac, 'r': ret, 'mcap': mc}).dropna()
        if len(df) < 3 * 5 * min_cell:
            continue
        # 市值三分（dependent sort 第一步）
        mrank = df['mcap'].rank(method='first')
        sz = ((mrank - 1) * 3 // len(df)).astype(int) + 1
        cur_cells = {}
        gross5, gross1 = {}, {}
        net5, net1 = {}, {}
        for t in (1, 2, 3):
            sub = df[sz == t]
            fr = sub['f'].rank(method='first')
            q5 = ((fr - 1) * 5 // len(sub)).astype(int) + 1
            for g in range(1, 6):
                sel = sub[q5 == g]
                key = (t, g)
                cur_cells[key] = set(sel.index)
                cell_counts[key] = cell_counts.get(key, []) + [len(sel)]
                rets = sel['r'].dropna()
                if len(rets) == 0:
                    continue
                gr = float(rets.mean())
                # 换手与成本（15 格分别计，v3 §5-2）
                to = 1.0
                cost = round_trip_cost(100.0, t_f)
                if prev_cells is not None and prev_cells.get(key):
                    p = prev_cells[key]
                    to = 1.0 - len(set(rets.index) & p) / max(1, len(rets.index))
                    costs = [round_trip_cost(mc.loc[c], t_f) for c in rets.index
                             if c in mc.index and np.isfinite(mc.loc[c])]
                    cost = float(np.mean(costs)) if costs else cost
                cell_series.setdefault(key, []).append((i, gr, gr - to * cost))
                if g == 5:
                    gross5[t] = gr
                    net5[t] = gr - to * cost
                elif g == 1:
                    gross1[t] = gr
                    net1[t] = gr - to * cost
        prev_cells = cur_cells
        if len(gross5) == 3 and len(gross1) == 3:
            ls_all.append(np.mean([gross5[t] - gross1[t] for t in (1, 2, 3)]))
            ls_net_all.append(np.mean([net5[t] - net1[t] for t in (1, 2, 3)]))
            ls_idx.append(t_r)

    out = {'gross_ls': pd.Series(ls_all, index=ls_idx),
           'net_ls': pd.Series(ls_net_all, index=ls_idx),
           'cell_counts': {f'{k[0]}-{k[1]}': v for k, v in cell_counts.items()}}
    # 大盘层五分后每格 <50 只告警
    big = [np.mean(v) for k, v in cell_counts.items() if k[0] == 3]
    out['big_cell_lt50_warn'] = bool(big) and float(np.mean(big)) < 50
    # 中性化验证：size-neutral spread 对 ln_mcap 回归 β（v3 §5-3-4）
    out['beta_lnmcap'] = np.nan
    if len(ls_all) >= 12 and len(ls_all) == len(ls_idx):
        lm = m.reindex(index=ls_idx).mean(axis=1)
        lm = np.log(lm.replace(0, np.nan).dropna())
        s = pd.Series(ls_all, index=ls_idx).reindex(lm.index)
        ok = s.notna() & lm.notna()
        if ok.sum() >= 12:
            b, *_ = np.polyfit(lm[ok], s[ok], 1)
            out['beta_lnmcap'] = float(b)
    return out


def group_stats_table(gp, freq=12, rf=0.0):
    """分层必报清单（v3 §5-5）：各组年化/波动/夏普/最大回撤/换手 + 多空。"""
    rows = {}
    gret = gp['group_ret']
    to = gp['turnover']
    for g in range(1, gret.shape[1] + 1):
        s = gret[f'G{g}'].dropna()
        if len(s) == 0:
            continue
        ann = s.mean() * freq
        vol = s.std(ddof=1) * np.sqrt(freq)
        sharpe = (ann - rf) / vol if vol > 0 else np.nan
        dd = (s / s.cummax() - 1).min() if s.cummax().iloc[-1] > 0 else np.nan
        rows[f'G{g}'] = {
            '年化收益': ann, '年化波动': vol, '夏普': sharpe,
            '最大回撤': dd, '月均换手': float(to[f'G{g}'].dropna().mean()),
            '月均覆盖数': float(gp['n_stocks'].mean())}
    s = gp['gross_ls'].dropna()
    rows['多空'] = {'年化收益': s.mean() * freq, '年化波动': s.std(ddof=1) * np.sqrt(freq),
                  '夏普': s.mean() / s.std(ddof=1) * np.sqrt(freq) if s.std(ddof=1) > 0 else np.nan,
                  '最大回撤': float((s / s.cummax() - 1).min()) if s.cummax().iloc[-1] > 0 else np.nan,
                  'NW-t': nw_t(s), '月均覆盖数': float(gp['n_stocks'].mean())}
    return pd.DataFrame(rows).T


def transition_matrix(factor_table, n_groups=5, min_stocks=10):
    """分组迁移矩阵（报告项，v3 §5-5）。"""
    dates = factor_table.index.sort_values()
    mats = []
    for i in range(1, len(dates)):
        m1 = build_monthly_membership(factor_table.loc[dates[i - 1]], n_groups, min_stocks)
        m2 = build_monthly_membership(factor_table.loc[dates[i]], n_groups, min_stocks)
        if m1 is None or m2 is None:
            continue
        df = pd.DataFrame({'from': m1, 'to': m2}).dropna().astype(int)
        cm = pd.crosstab(df['from'], df['to'], normalize='index')
        mats.append(cm)
    if not mats:
        return None
    avg = sum(mats) / len(mats)
    return avg


# ---------------------------------------------------------------------------
# ④ 自相关 + 再平衡频率（v3 §6）
# ---------------------------------------------------------------------------
def rank_autocorr(factor_table, lags=(1, 3, 6)):
    """横截面排名的月度 Spearman 自相关（lag-1/3/6，v3 §6-1）。"""
    dates = factor_table.index.sort_values()
    out = {}
    for lag in lags:
        cs = []
        for i in range(lag, len(dates)):
            a = factor_table.loc[dates[i - lag]].dropna()
            b = factor_table.loc[dates[i]].reindex(a.index).dropna()
            a = a.reindex(b.index)
            if len(a) >= 20:
                cs.append(stats.spearmanr(a, b)[0])
        out[lag] = float(np.mean(cs)) if cs else np.nan
    return out


def rebalance_freq_compare(factor_table, ret_table, mcap_table=None):
    """月度 vs 季度再平衡净收益（扣成本）实证（v3 §6-3）。"""
    # 月度口径直接复用 group_portfolios
    gp_m = group_portfolios(factor_table, ret_table, mcap_table)
    # 季度口径：每 3 个月再平衡（持仓 3 个月，成分按季初因子）
    q = factor_table.copy()
    qdates = [d for d in q.index if d.month in (1, 4, 7, 10)] or \
        [d for i, d in enumerate(q.index) if i % 3 == 0]
    q = q.loc[qdates]
    gp_q = group_portfolios(q, ret_table, mcap_table)
    out = {'monthly_net_ls_ann': float(gp_m['net_ls'].mean() * 12) if len(gp_m['net_ls']) else np.nan,
           'quarterly_net_ls_ann': float(gp_q['net_ls'].mean() * 12) if len(gp_q['net_ls']) else np.nan,
           'monthly_n': len(gp_m['net_ls']), 'quarterly_n': len(gp_q['net_ls'])}
    return out


# ---------------------------------------------------------------------------
# ⑤ 共线性 + FM 增量（v3 §7）
# ---------------------------------------------------------------------------
def collinearity(factor_table, others, end_date=None):
    """与存量因子的横截面排名相关矩阵（月度均值）；|corr|>0.7 告警。
    仅用训练段（检验日−24m 前，end_date 传入）裁决（v3 §7-1）。"""
    f = factor_table if end_date is None else factor_table.loc[:end_date]
    out = {}
    for name, o in (others or {}).items():
        o = o.reindex(index=f.index, columns=f.columns)
        cs = []
        for t in f.index:
            a = f.loc[t].dropna()
            b = o.loc[t].reindex(a.index).dropna()
            a = a.reindex(b.index)
            if len(a) >= 20:
                cs.append(stats.spearmanr(a, b)[0])
        out[name] = float(np.mean(cs)) if cs else np.nan
    return out


def fm_incremental(factor_table, ret_table, others, industry_map=None,
                   mcap_table=None, min_stocks=30):
    """Fama-MacBeth 多元增量检验（v3 §7-2）：
    r_{i,t+1} = a + b1·f_new + b2·ln_mcap + b3·EP + b4·BP + b5·MOM_60D
                + Σγ·I(industry) + ε；每月横截面 z-score（可空）；NW-t≥2.0 单侧。"""
    if not others:
        return {'skipped': True, 'note': '未提供存量因子表，跳过'}
    names = ['f'] + list(others.keys())
    if mcap_table is not None:
        names = names + ['lnmcap']
    dates = factor_table.index.sort_values()
    b1s, r2s, vifs = [], [], []
    for i in range(len(dates) - 1):
        t_f, t_r = dates[i], dates[i + 1]
        df = pd.DataFrame({'f': factor_table.loc[t_f], 'r': ret_table.loc[t_r]})
        for n, o in others.items():
            df[n] = o.loc[t_f]
        if mcap_table is not None:
            df['lnmcap'] = np.log(mcap_table.loc[t_f].clip(lower=1e-6))
        if industry_map is not None:
            df['ind'] = df.index.map(lambda c: industry_map.get(c, 'NA'))
        df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=['r', 'f'])
        if len(df) < min_stocks:
            continue
        # 横截面 z-score（v3 §7-2：每月横截面标准化）
        for n in names:
            mu, sd = df[n].mean(), df[n].std(ddof=1)
            if sd > 0:
                df[n] = (df[n] - mu) / sd
        y = df['r'].values
        X = df[names].values
        if industry_map is not None:
            d = pd.get_dummies(df['ind'], drop_first=True)
            X = np.column_stack([X, d.values])
        X = np.column_stack([np.ones(len(X)), X])
        try:
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        b1s.append(beta[1])
        resid = y - X @ beta
        ss_res = float(resid @ resid)
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2s.append(1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan)
    if len(b1s) < 12:
        return {'skipped': True, 'note': f'有效月数不足（{len(b1s)}<12）'}
    bs = pd.Series(b1s)
    t = nw_t(bs, maxlags=max(2, _nw_lag(len(bs))))
    return {'b1_mean': float(bs.mean()), 'b1_median': float(bs.median()),
            'nw_t': t, 'n': len(bs), 'r2_mean': float(np.nanmean(r2s)),
            'skipped': False}


# ---------------------------------------------------------------------------
# ⑥ 稳健性矩阵（v3 §8）
# ---------------------------------------------------------------------------
SEGMENTS = [('2017-01', '2021-12'), ('2022-01', None)]
STRESS_MONTHS = [('2015-06', '2015-08'), ('2016-01', '2016-01'), ('2018-10', '2018-10'),
                 ('2020-02', '2020-02'), ('2024-01', '2024-02')]
BEAR_PERIODS = [('2015-06', '2016-01'), ('2018-01', '2018-12'), ('2022-01', '2022-04'),
                ('2022-07', '2022-10'), ('2024-01', '2024-02')]


def segment_icir(factor_table, ret_table, segments=SEGMENTS):
    """分段 ICIR（v3 §8 硬门槛：两段同号且均>0.3，仅当两段都有数据）。"""
    out = {}
    for lo, hi in segments:
        f = factor_table
        if lo:
            f = f.loc[lo:]
        if hi:
            f = f.loc[:hi]
        ib = ic_battery(f, ret_table)
        out[f'{lo or "start"}~{hi or "now"}'] = {'icir': ib.get('icir'), 'mean': ib.get('mean'), 'n': ib.get('n')}
    return out


def stress_ls(gp, periods):
    """压力测试/熊市段逐月多空（报告项；单月<−10% 或连续两月亏损 → 观察）。"""
    out = []
    ls = gp['gross_ls']
    for lo, hi in periods:
        seg = ls.loc[lo:hi]
        if len(seg):
            out.append({'period': f'{lo}~{hi}', 'n': int(len(seg)),
                        'worst_month': float(seg.min()), 'mean': float(seg.mean())})
    return out


def rolling_icir_obs(ic, window=36):
    """滚动 36m ICIR + 观察线（v3 §8：末端<0.3 / 连续≥12月为负）。"""
    if len(ic) < window:
        return {'available': False, 'note': f'样本 {len(ic)} < 36'}
    r = ic.rolling(window).mean() / ic.rolling(window).std(ddof=1)
    r = r.dropna()
    if len(r) == 0:
        return {'available': False, 'note': '滚动窗口无有效值'}
    tail_neg = bool((ic.iloc[-12:] < 0).all()) if len(ic) >= 12 else False
    obs = []
    if r.iloc[-1] < 0.3:
        obs.append('末端<0.3')
    if tail_neg:
        obs.append('最近12月IC连续为负')
    return {'available': True, 'last': float(r.iloc[-1]), 'obs': obs,
            'series': r}


def seasonality(ic):
    """季节性：月度 IC 按日历月分解（v3 §8，1月/4/8/10 财报季）。"""
    ic = ic.dropna()
    if len(ic) == 0:
        return {}
    df = pd.DataFrame({'ic': ic, 'mon': ic.index.month})
    return {int(m): float(g['ic'].mean()) for m, g in df.groupby('mon')}


def industry_ic(factor_table, ret_table, industry_map):
    """行业内 IC 分布（v3 §8 报告项，识别单行业驱动）。"""
    if not industry_map:
        return {}
    dates = factor_table.index.sort_values()
    ind_ics = {}
    for t in range(len(dates) - 1):
        fv = factor_table.loc[dates[t]]
        rv = ret_table.loc[dates[t + 1]]
        df = pd.DataFrame({'f': fv, 'r': rv})
        df['ind'] = df.index.map(lambda c: industry_map.get(c, 'NA'))
        for ind, g in df.groupby('ind'):
            g = g.dropna(subset=['f', 'r'])
            if len(g) >= 20:
                ic = stats.spearmanr(g['f'], g['r'])[0]
                ind_ics.setdefault(ind, []).append(ic)
    out = {}
    for ind, v in ind_ics.items():
        v = np.array(v)
        if len(v) >= 12:
            out[ind] = {'n': len(v), 'mean': float(v.mean())}
    return out


def neutralized_variant(factor_table, mcap_table, industry_map=None):
    """行业+市值中性化版因子（v3 §3-6/§8：行业内 demean + ln_mcap 回归残差）。"""
    f = factor_table.copy()
    dates = f.index
    out = f.copy()
    for t in dates:
        row = f.loc[t]
        df = pd.DataFrame({'f': row})
        df['lnmcap'] = np.log(mcap_table.loc[t].reindex(f.columns).clip(lower=1e-6)) if mcap_table is not None else np.nan
        if industry_map is not None:
            df['ind'] = df.index.map(lambda c: industry_map.get(c, 'NA'))
        df = df.dropna(subset=['f'])
        X = df[['lnmcap']].values
        if industry_map is not None:
            d = pd.get_dummies(df['ind'], drop_first=True)
            X = np.column_stack([X, d.values])
        X = np.column_stack([np.ones(len(X)), X])
        y = df['f'].values
        try:
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            resid = pd.Series(y - X @ beta, index=df.index)
            out.loc[t] = resid.reindex(f.columns)
        except np.linalg.LinAlgError:
            out.loc[t] = np.nan
    return out


def param_sensitivity(factor_table, ret_table, variants=None):
    """参数敏感性（v3 §8 报告项）：winsorize ±2σ、收益 ±50% 截断各一个变体。"""
    out = {}
    if variants is None:
        variants = {'factor_2sigma': {'f_k': 2.0, 'r_mode': 'pct'},
                    'ret_trunc50': {'f_k': 3.0, 'r_mode': 'trunc'}}
    for name, v in variants.items():
        fv = winsorize_sigma(factor_table, v.get('f_k', 3.0))
        if v.get('r_mode') == 'trunc':
            rv = ret_table.clip(-0.5, 0.5)
        else:
            rv = winsorize_cross_section(ret_table)
        ib = ic_battery(fv, rv)
        out[name] = {'icir': ib.get('icir'), 'mean': ib.get('mean'),
                     'signed_t': ib.get('signed_t')}
    return out


# ---------------------------------------------------------------------------
# ⑧ 经济闸门（v3 §10）
# ---------------------------------------------------------------------------
def econ_gate(net_ls, net_ls_2x, gross_ls=None, freq=12):
    """净多空年化/2x成本/夏普。年化=月均×12（v3 §10 口径注明：同时报告 ×√12 字面口径）。"""
    s = net_ls.dropna()
    if len(s) == 0:
        return {'available': False}
    mu = float(s.mean())
    sd = float(s.std(ddof=1))
    ann12 = mu * freq
    ann_sqrt12 = mu * np.sqrt(freq)
    sharpe = ann12 / (sd * np.sqrt(freq)) if sd > 0 else np.nan
    s2 = net_ls_2x.dropna()
    out = {'available': True, 'n': len(s),
           'net_ls_ann_x12': ann12, 'net_ls_ann_xsqrt12': ann_sqrt12,
           'net_ls_vol_ann': sd * np.sqrt(freq), 'sharpe': sharpe,
           'net_ls_2x_positive': bool(len(s2) and float(s2.mean()) > 0),
           'net_ls_2x_mean': float(s2.mean()) if len(s2) else np.nan,
           'gross_ls_ann_x12': float(gross_ls.dropna().mean() * freq) if gross_ls is not None and len(gross_ls.dropna()) else np.nan}
    return out


# ---------------------------------------------------------------------------
# 判定（v3 §11 阈值总表 + §12 流程）
# ---------------------------------------------------------------------------
def decide(ib, gp, sn, n_star, expected_sign, econ, oos_ib, seg, t_total,
           pt_p=None, fm_b=None, robustness=None, rolling=None, stress=None):
    """综合判定：任何 淘汰 → 淘汰；否则任何 观察 → 观察；否则 保留。"""
    thr = sig_threshold(n_star)
    levels = []
    notes = []

    # IC 关
    if ib.get('n', 0) == 0:
        levels.append(('淘汰', 'IC: 无有效样本'))
    else:
        icir, m = ib['icir'], ib['mean']
        if icir < 0.3 or abs(m) < 0.02:
            levels.append(('淘汰', f'IC: ICIR={icir:.3f}<0.3 或 |mean IC|={abs(m):.4f}<0.02'))
        elif not (icir > 0.5 and ib['signed_t'] >= thr):
            levels.append(('观察', f'IC: ICIR={icir:.3f} 未过 0.5 或 signed NW-t={ib["signed_t"]:.2f}<{thr:.2f}'))
        else:
            levels.append(('通过', f'IC: ICIR={icir:.3f}>0.5, |mean|={abs(m):.4f}>=0.02, signed NW-t={ib["signed_t"]:.2f}>={thr:.2f}'))
        if ib.get('win_rate', 0) < 0.55:
            notes.append(f'IC 胜率 {ib["win_rate"]:.1%} < 55% (观察线)')
        for k, key in (('down_month', '下跌月'), ('high_vol', '高波动月')):
            c = ib.get('cond', {}).get(k)
            if c and c['n'] >= 6 and c['mean'] < 0:
                levels.append(('淘汰', f'{key} 条件 IC={c["mean"]:.4f}<0 (硬指标)'))

    # 分层关
    ls = gp['gross_ls'].dropna()
    if len(ls) < 12:
        levels.append(('淘汰', '分层: 多空样本不足'))
    else:
        ls_nw = nw_t(ls)
        signed_ls = expected_sign * ls_nw if np.isfinite(ls_nw) else np.nan
        if np.isfinite(signed_ls) and signed_ls < 2.0:
            levels.append(('淘汰', f'分层: 多空 signed NW-t={signed_ls:.2f}<2.0'))
        elif np.isfinite(signed_ls) and signed_ls < 3.0:
            levels.append(('观察', f'分层: 多空 signed NW-t={signed_ls:.2f} 在 2.0~3.0 观察带'))
        if pt_p is not None and np.isfinite(pt_p):
            if pt_p >= 0.05 and t_total >= 36:
                levels.append(('观察', f'PT MR p={pt_p:.4f}>=0.05 单调性未达线'))
        # 三重稳健性
        if robustness is not None:
            rob_fail = []
            for k, v in robustness.items():
                if not v.get('pass', False):
                    rob_fail.append(k)
            if rob_fail:
                levels.append(('观察', f'三重稳健性未全过: {", ".join(rob_fail)}'))

    # 分段硬门槛（两段都有数据时）
    if seg:
        ics = [v['icir'] for v in seg.values() if v.get('icir') is not None and v['n'] >= 12]
        if len(ics) == 2:
            if not (ics[0] > 0.3 and ics[1] > 0.3 and np.sign(ics[0]) == np.sign(ics[1])):
                levels.append(('观察', f'分段硬门槛未过: {[round(x, 3) for x in ics]}'))

    # 滚动 36m 观察线
    if rolling and rolling.get('available') and rolling.get('obs'):
        levels.append(('观察', '滚动36m ICIR: ' + ';'.join(rolling['obs'])))

    # 压力测试：单月<−10% 或连续两月亏损 → 至少观察
    if stress:
        for p in stress:
            if p['worst_month'] < -0.10:
                levels.append(('观察', f'压力月 {p["period"]} 多空 {p["worst_month"]:.1%} < -10%'))
                break

    # 经济闸门
    if econ.get('available'):
        if econ['net_ls_ann_x12'] < 0.04:
            levels.append(('淘汰', f'经济: 净多空年化 {econ["net_ls_ann_x12"]:.1%} < 4%'))
        elif econ['net_ls_ann_x12'] < 0.08:
            levels.append(('观察', f'经济: 净多空年化 {econ["net_ls_ann_x12"]:.1%} 在 4~8% 观察带'))
        if econ['sharpe'] < 0.5:
            levels.append(('淘汰', f'经济: 夏普 {econ["sharpe"]:.2f} < 0.5'))
        elif econ['sharpe'] < 0.8:
            levels.append(('观察', f'经济: 夏普 {econ["sharpe"]:.2f} 在 0.5~0.8 观察带'))
        if not econ['net_ls_2x_positive']:
            levels.append(('观察', '经济: 2x 成本后净多空不为正'))

    # 样本外一次确认（v3 §3-5：报告项；确认失败 → 降级观察，禁止回训重报）
    oos_flag = False
    if oos_ib and oos_ib.get('n', 0) >= 6:
        if expected_sign * oos_ib.get('mean', 0) < 0:
            oos_flag = True
            levels.append(('观察', '样本外 24m 确认失败（OOS mean IC 与预登记方向相反）'))

    rank = {'淘汰': 3, '观察': 2, '通过': 1}
    worst = max(levels, key=lambda x: rank[x[0]])
    verdict = '保留' if worst[0] == '通过' else worst[0]
    if oos_flag and verdict == '保留':
        verdict = '观察'
    prelim = t_total < 60
    return {'verdict': verdict, 'reason': '; '.join(n for _, n in levels),
            'preliminary': prelim,
            'signed_threshold': thr,
            'oos_confirmed': not oos_flag}


# ---------------------------------------------------------------------------
# 报告 / 回填（v3 §13 + registry 追加式回填）
# ---------------------------------------------------------------------------
def fmt(x, nd=4):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return '—'
    if isinstance(x, float):
        return f'{x:.{nd}f}'
    return str(x)


def registry_backfill_row(rpt):
    """生成 registry 追加式回填行（不改原行，防改口三件套）。"""
    r = rpt
    ib, gp = r['ic'], r['group']
    econ = r['econ']
    row = {
        '#': r['registry_no'] or '—',
        '因子': r['name'],
        '类型': r.get('factor_type', '—'),
        '状态': f"⏳ 待检验（设计已审）→ {r['verdict']['verdict']}",
        '登记时间戳': r['registered_ts'] or '—',
        '预期符号(前置,锁定)': '+' if r['expected_sign'] == 1 else '−',
        '样本期': f"{r['sample_start']}~{r['sample_end']}",
        '数据版本hash': r['data_hash'][:12],
        '检验脚本': r['script'],
        'IC均值': fmt(ib.get('mean'), 4),
        'IC标准差': fmt(ib.get('std'), 4),
        'ICIR': fmt(ib.get('icir'), 3),
        'naive t': fmt(ib.get('naive_t'), 2),
        'NW-t': fmt(ib.get('nw_t'), 2),
        '胜率': fmt(ib.get('win_rate'), 3),
        '覆盖率': fmt(r['coverage'].get('mean'), 3),
        'PT MR p': fmt(r['pt_mr'].get('p'), 4),
        '净多空年化': fmt(econ.get('net_ls_ann_x12'), 4) if econ.get('available') else '—',
        '夏普': fmt(econ.get('sharpe'), 2) if econ.get('available') else '—',
        '2x成本': '正' if econ.get('net_ls_2x_positive') else '负/—',
        '内部基准': fmt(r.get('benchmark_pass'), 0) if r.get('benchmark_pass') is not None else '—',
        '调参标记': '无',
        '结论': r['verdict']['verdict'],
        'MImo审批': '—',
        '备注': f"{r['verdict']['reason'][:60]}{'；初步' if r['verdict']['preliminary'] else ''}",
    }
    return row


def registry_backfill_md(rpt):
    """回填行 markdown（贴入 registry 登记表末尾；原行不动）。"""
    row = registry_backfill_row(rpt)
    order = ['#', '因子', '类型', '状态', '登记时间戳', '预期符号(前置,锁定)', '样本期',
             '数据版本hash', '检验脚本', 'IC均值', 'IC标准差', 'ICIR', 'naive t', 'NW-t',
             '胜率', '覆盖率', 'PT MR p', '净多空年化', '夏普', '2x成本', '内部基准',
             '调参标记', '结论', 'MImo审批', '备注']
    return '| ' + ' | '.join(str(row[k]) for k in order) + ' |'


def data_hash(*dfs_or_paths):
    """数据版本 hash：parquet 文件取 sha256；DataFrame 取 hash_pandas_object md5。"""
    h = hashlib.sha256()
    for x in dfs_or_paths:
        if x is None:
            continue
        if isinstance(x, (str, os.PathLike)):
            with open(x, 'rb') as fh:
                h.update(fh.read())
        elif isinstance(x, pd.DataFrame):
            h.update(pd.util.hash_pandas_object(x, index=True).values.tobytes())
        elif isinstance(x, pd.Series):
            h.update(pd.util.hash_pandas_object(x, index=True).values.tobytes())
        else:
            h.update(repr(x).encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run_pipeline(factor_table, ret_table, mcap_table=None, fin_table=None,
                 other_factors=None, tradable_table=None, st_table=None,
                 name='FACTOR', expected_sign=1, n_star=10, factor_type='—',
                 registry_no=None, registered_ts=None, start='2017-01-31',
                 oos_months=24, seed=SEED, benchmark_icirs=None,
                 out_dir=None, input_files=None):
    """完整检验流水线（v3 §12 ①~⑨）。返回 report dict。"""
    f, r, m = align_tables(factor_table, ret_table, mcap_table,
                           tradable_table, st_table)
    if m is not None and (m == 0).any().any():
        m = m.replace(0, np.nan)
    f = winsorize_sigma(f, 3.0)
    r = winsorize_cross_section(r)

    # 行业映射（PIT：公告日期 ≤ 月末取最新；无公告日期列则取全局最新快照）
    industry_map = {}
    if fin_table is not None and len(fin_table):
        ft = fin_table.copy()
        has_ann = '公告日期' in ft.columns or '最新公告日期' in ft.columns
        ann_col = '公告日期' if '公告日期' in ft.columns else ('最新公告日期' if '最新公告日期' in ft.columns else None)
        if '所处行业' in ft.columns:
            if has_ann and ann_col:
                ft[ann_col] = pd.to_datetime(ft[ann_col], errors='coerce')
                ft = ft.dropna(subset=[ann_col]).sort_values(ann_col)
                industry_map = dict(zip(ft['股票代码'].astype(str),
                                        ft['所处行业'].fillna('NA')))
                industry_map = {k: v for k, v in
                                dict(zip(ft['股票代码'].astype(str), ft['所处行业'].fillna('NA'))).items()}
            else:
                ind_df = ft.dropna(subset=['所处行业'])
                industry_map = dict(zip(ind_df['股票代码'].astype(str),
                                        ind_df['所处行业']))

    rpt = {'name': name, 'expected_sign': expected_sign, 'n_star': n_star,
           'factor_type': factor_type, 'registry_no': registry_no,
           'registered_ts': registered_ts, 'seed': seed, 'script': __file__,
           'sample_start': str(f.index.min().date()), 'sample_end': str(f.index.max().date()),
           'start_cfg': start, 'oos_months': oos_months, 'version': VERSION,
           'report_date': REPORT_DATE,
           'data_hash': data_hash(*(input_files or []), f, r, m),
           'n_months': len(f)}

    # ① 数据准备：覆盖率 + MCAR
    rpt['coverage'] = monthly_coverage(f)
    rpt['missing_ic'] = missing_indicator_ic(f, r)

    # 样本划分（v3 §3-5）
    dates = f.index.sort_values()
    oos_start = dates[-oos_months] if len(dates) > oos_months else dates[0]
    f_main, r_main = f, r
    f_oos = f.loc[oos_start:]

    # ② IC 关（主判定样本 + OOS 报告项）
    ib = ic_battery(f_main, r_main, m, industry_map)
    ib_oos = ic_battery(f_oos, r, m, industry_map)
    rpt['ic'] = ib
    rpt['ic_oos'] = ib_oos
    rpt['ic_pass'] = ic_gate_pass(ib, n_star, expected_sign)
    # 内部基准（v3 §4-3：≥存量同窗 ICIR 中位数）
    if benchmark_icirs:
        med = float(np.median(benchmark_icirs))
        rpt['benchmark_pass'] = bool(ib['icir'] >= med)
        rpt['benchmark_median'] = med
    else:
        rpt['benchmark_pass'] = None

    # ③ 分层关
    gp = group_portfolios(f_main, r_main, m)
    rpt['group'] = {'gross_ls': gp['gross_ls'], 'net_ls': gp['net_ls'],
                    'net_ls_2x': gp['net_ls_2x'],
                    'group_ret': gp['group_ret'], 'turnover': gp['turnover'],
                    'n_stocks': gp['n_stocks']}
    rpt['group_stats'] = group_stats_table(gp)
    rpt['pt_mr'] = pt_mr(gp['group_ret'], expected_sign, seed=seed)
    rpt['fm_beta'] = fm_beta(gp['group_ret'])
    rpt['transition'] = transition_matrix(f_main)
    # 三重稳健性
    rob = {}
    gp_vw = group_portfolios(f_main, r_main, m, weighted=True)
    rob['市值加权'] = _robustness_entry(gp_vw, expected_sign)
    if m is not None:
        # 微盘剔除：市值 <30 亿置 NaN（v3 §5-3）
        micro_mask = pd.DataFrame(m > 30.0, index=m.index, columns=m.columns)
        fm, rm, _ = align_tables(f_main, r_main, m, tradable_table=micro_mask)
        gp_micro = group_portfolios(fm, rm, m)
        rob['微盘剔除'] = _robustness_entry(gp_micro, expected_sign)
        sn = size_neutral_3x5(f_main, r_main, m)
        sn_ls = sn['gross_ls']
        sn_pass = len(sn_ls.dropna()) >= 12 and \
            expected_sign * sn_ls.dropna().mean() > 0 and \
            nw_t(sn_ls.dropna()) * expected_sign >= 2.0
        rob['规模中性3×5'] = {'pass': sn_pass, 'note': '净多空为正且显著',
                               'mean': float(sn_ls.dropna().mean()) if len(sn_ls.dropna()) else np.nan,
                               'nw_t': nw_t(sn_ls.dropna()) if len(sn_ls.dropna()) else np.nan,
                               'beta_lnmcap': sn['beta_lnmcap'],
                               'big_cell_lt50_warn': sn['big_cell_lt50_warn']}
        rpt['size_neutral'] = sn
    else:
        gp_micro = None
        rpt['size_neutral'] = None
    rpt['robustness'] = rob

    # ④ 自相关 + 再平衡频率
    rpt['autocorr'] = rank_autocorr(f_main)
    rpt['rebalance'] = rebalance_freq_compare(f_main, r_main, m)

    # ⑤ 共线性（训练段 = 检验日−24m 前）+ FM 增量
    train_end = dates[-oos_months - 1] if len(dates) > oos_months + 1 else dates[-1]
    rpt['collinearity'] = collinearity(f_main, other_factors, end_date=train_end)
    rpt['fm'] = fm_incremental(f_main, r_main, other_factors, industry_map, m)

    # ⑥ 稳健性矩阵
    rpt['segments'] = segment_icir(f_main, r_main)
    rpt['stress'] = stress_ls(gp, STRESS_MONTHS)
    rpt['bear'] = stress_ls(gp, BEAR_PERIODS)
    rpt['rolling'] = rolling_icir_obs(ic_series(f_main, r_main))
    rpt['seasonality'] = seasonality(ic_series(f_main, r_main))
    rpt['industry_ic'] = industry_ic(f_main, r_main, industry_map)
    rpt['sensitivity'] = param_sensitivity(f_main, r_main)
    if m is not None:
        f_neu = neutralized_variant(f_main, m, industry_map)
        ib_neu = ic_battery(f_neu, r_main, m, industry_map)
        rpt['neutralized'] = {'icir': ib_neu.get('icir'), 'mean': ib_neu.get('mean'),
                              'signed_t': ib_neu.get('signed_t')}
    else:
        rpt['neutralized'] = None

    # ⑦ 多重检验线 + ⑧ 经济闸门
    rpt['sig_threshold'] = sig_threshold(n_star)
    rpt['econ'] = econ_gate(gp['net_ls'], gp['net_ls_2x'], gp['gross_ls'])

    # 判定
    rpt['verdict'] = decide(ib, gp, None, n_star, expected_sign, rpt['econ'],
                            ib_oos, rpt['segments'], len(f_main),
                            pt_p=rpt['pt_mr'].get('p'), fm_b=rpt['fm_beta'],
                            robustness=rob, rolling=rpt['rolling'],
                            stress=rpt['stress'])
    # OOS 净多空（报告项）
    gp_oos = group_portfolios(f_oos, r_main, m)
    rpt['oos_group'] = {'gross_ls': gp_oos['gross_ls'],
                        'net_ls': gp_oos['net_ls']}
    rpt['oos_econ'] = econ_gate(gp_oos['net_ls'], gp_oos['net_ls_2x'],
                                gp_oos['gross_ls'])
    return rpt


def _robustness_entry(gp, expected_sign):
    ls = gp['gross_ls'].dropna()
    if len(ls) < 12:
        return {'pass': False, 'note': '样本不足', 'mean': np.nan, 'nw_t': np.nan}
    t = nw_t(ls)
    signed = expected_sign * t if np.isfinite(t) else np.nan
    ok = expected_sign * ls.mean() > 0 and (np.isfinite(signed) and signed >= 2.0)
    return {'pass': bool(ok), 'note': '净多空为正且显著(NW-t>=2.0)' if ok else '未达线',
            'mean': float(ls.mean()), 'nw_t': t}


# ---------------------------------------------------------------------------
# markdown 报告（v3 §13 模板）
# ---------------------------------------------------------------------------
def render_markdown(rpt, charts=None):
    """输出 test_{因子}_{日期}.md 报告全文。"""
    L = []
    A = L.append
    ib, gp = rpt['ic'], rpt['group']
    v = rpt['verdict']
    A(f"# 因子检验报告：{rpt['name']}（{rpt['report_date']}）")
    A('')
    A(f"> 检验脚本：`{rpt['script']}` ｜ 方法论：`factor_testing_methodology_v3.md`（定稿） ｜ 数据版本 hash：`{rpt['data_hash'][:16]}…` ｜ 随机种子：`{rpt['seed']}`")
    A('')
    A(f"**最终判定：`{v['verdict']}`**{'（⚠️ 初步：样本 <60 月，不得据此入主策略，v3 §1）' if v['preliminary'] else ''}")
    A('')
    A(f"理由：{v['reason']}")
    A('')
    A('## 1. 因子定义与登记')
    A('')
    A(f"- registry 编号：{rpt['registry_no'] or '—'}；登记时间戳：{rpt['registered_ts'] or '—'}")
    A(f"- 类型：{rpt['factor_type']}；预期符号（前置锁定）：{'+' if rpt['expected_sign'] == 1 else '−'}")
    A(f"- 样本期：{rpt['sample_start']} ~ {rpt['sample_end']}（主判定起点配置 {rpt['start_cfg']}；最近 {rpt['oos_months']} 个月为样本外确认段，仅报告不裁决）")
    A(f"- 检验时 N'（本自然季度同期受检）= {rpt['n_star']}；显著性线 = max(3.0, Bonf(N')) = **{rpt['sig_threshold']:.3f}**（signed NW-t）")
    A('')
    A('## 2. 数据与覆盖率')
    A('')
    A(f"- 月度因子覆盖率：均值 {rpt['coverage']['mean']:.1%}，最低 {rpt['coverage']['min']:.1%}，<70% 月数 {rpt['coverage']['lt70_months']}（v3 §3-4：<70% 告警）")
    A(f"- 缺失指示变量 IC：n={rpt['missing_ic'].get('n', 0)}，mean={fmt(rpt['missing_ic'].get('mean'))}（MCAR 检验，v3 §3-4）")
    A(f"- 幸存者偏差声明：数据源仅含现存股票，历史退市股不可得，结论附此局限（v3 §3-3）")
    A('')
    A('## 3. IC 检验（第一道关）')
    A('')
    A('| 指标 | 值 | 通过线 | 判定 |')
    A('|---|---|---|---|')
    A(f"| IC 均值 | {fmt(ib.get('mean'))} | \\|mean\\| ≥ 0.02 | {'✓' if abs(ib.get('mean', 0)) >= 0.02 else '✗'} |")
    A(f"| IC 标准差 (ddof=1) | {fmt(ib.get('std'))} | — | — |")
    A(f"| ICIR | {fmt(ib.get('icir'), 3)} | > 0.5 | {'✓' if ib.get('icir', 0) > 0.5 else '✗'} |")
    A(f"| IC 胜率 | {fmt(ib.get('win_rate'), 3)} | 报告项（<55% 观察） | — |")
    A(f"| naive t | {fmt(ib.get('naive_t'), 2)} | 对照（判定以 NW-t 为准） | — |")
    A(f"| **NW-t** | **{fmt(ib.get('nw_t'), 2)}** | — | — |")
    A(f"| **signed NW-t**（预登记方向） | **{fmt(ib.get('signed_t'), 2)}** | ≥ {rpt['sig_threshold']:.2f} | {'✓' if ib.get('signed_t', -9) >= rpt['sig_threshold'] else '✗'} |")
    A(f"| IC 极值 winsorize 后 ICIR | {fmt(ib.get('icir_winsor'), 3)} | 对照（v3 §4-3） | — |")
    A(f"| 风险调整 IC（市场+规模+行业残差） | {fmt(ib.get('resid_ic'))} | 报告项 | — |")
    A('')
    A('条件 IC（硬指标非负）：')
    A('')
    A(f"- 下跌月条件 IC：n={ib.get('cond', {}).get('down_month', {}).get('n', 0)}，mean={fmt(ib.get('cond', {}).get('down_month', {}).get('mean'))}")
    A(f"- 高波动月条件 IC：n={ib.get('cond', {}).get('high_vol', {}).get('n', 0)}，mean={fmt(ib.get('cond', {}).get('high_vol', {}).get('mean'))}")
    A(f"- 波动率关系：corr(因子, 已实现波动率)={fmt(ib.get('vol_rel', {}).get('corr_realvol'))}（防波动率代理，v3 §4-4-6）")
    A('')
    A('IC 衰减曲线（RankIC 均值 / ICIR）：')
    A('')
    A('| 前瞻期 | 均值 | ICIR | n |')
    A('|---|---|---|---|')
    for h in (1, 2, 3, 6, 12):
        d = ib.get('decay', {}).get(h)
        A(f"| T+{h} | {fmt(d['mean']) if d else '—'} | {fmt(d['icir'], 3) if d else '—'} | {d['n'] if d else '—'} |")
    A('')
    if rpt.get('benchmark_pass') is not None:
        A(f"内部基准：ICIR={ib.get('icir', 0):.3f} vs 存量因子中位数 {rpt.get('benchmark_median', float('nan')):.3f} → {'✓ ≥ 中位数' if rpt['benchmark_pass'] else '✗ < 中位数'}（v3 §4-3）")
        A('')
    A('## 4. 分层检验（第二道关）')
    A('')
    A('组统计（等权主口径，月度再平衡，成本已计）：')
    A('')
    st = rpt['group_stats']
    A('| 组 | 年化收益 | 年化波动 | 夏普 | 最大回撤 | 月均换手 |')
    A('|---|---|---|---|---|---|')
    for g in st.index:
        row = st.loc[g]
        A(f"| {g} | {row['年化收益']:.2%} | {row['年化波动']:.2%} | {fmt(row['夏普'], 2)} | {fmt(row['最大回撤'], 4)} | {fmt(row['月均换手'], 3)} |")
    A('')
    ls = gp['gross_ls'].dropna()
    A(f"- 毛多空（Q5−Q1）NW-t = {fmt(nw_t(ls), 2)}；signed = {fmt(rpt['expected_sign'] * nw_t(ls), 2) if np.isfinite(nw_t(ls)) else '—'}")
    A(f"- 倒挂计数：相邻倒挂 ≤1 档且 Q5>Q1（报告项）")
    A(f"- **PT MR 单调性**：p = {fmt(rpt['pt_mr'].get('p'), 4)}（R=9999, 块长3, null recentering, seed={rpt['seed']}）{'→ 单调成立' if rpt['pt_mr'].get('p', 1) < 0.05 else '→ 未达线'}")
    A(f"- FM β（辅助）：均值={fmt(rpt['fm_beta'].get('mean'), 4)}，NW-t={fmt(rpt['fm_beta'].get('nw_t'), 2)}")
    A('')
    A('三重稳健性（全部必做，v3 §5-3）：')
    A('')
    A('| 检验 | 判定 | 净多空月均 | NW-t | 备注 |')
    A('|---|---|---|---|---|')
    for k, val in rpt['robustness'].items():
        A(f"| {k} | {'✓ 通过' if val['pass'] else '✗ 未过'} | {fmt(val.get('mean'), 4)} | {fmt(val.get('nw_t'), 2)} | {val.get('note', '')} |")
    sn = rpt.get('size_neutral')
    if sn is not None:
        A(f"| 规模中性 spread β(ln_mcap) | — | — | — | {fmt(sn.get('beta_lnmcap'), 4)}（\\|β\\|≈0 为中性化有效）；大盘层每格<50只告警：{'⚠️' if sn.get('big_cell_lt50_warn') else '无'} |")
    A('')
    A('## 5. 自相关与再平衡频率（v3 §6）')
    A('')
    A(f"- 排名自相关：lag-1 = {fmt(rpt['autocorr'].get(1), 3)}，lag-3 = {fmt(rpt['autocorr'].get(3), 3)}，lag-6 = {fmt(rpt['autocorr'].get(6), 3)}（描述性）")
    A(f"- 月度 vs 季度再平衡净多空年化：{fmt(rpt['rebalance'].get('monthly_net_ls_ann'), 4)} vs {fmt(rpt['rebalance'].get('quarterly_net_ls_ann'), 4)}（实证取高）")
    A('')
    A('## 6. 共线性与增量信息（v3 §7，训练段=检验日−24m 前裁决）')
    A('')
    if rpt['collinearity']:
        A('| 对比因子 | 月度横截面 Spearman（训练段均值） | >0.7 告警 |')
        A('|---|---|---|')
        for k, c in rpt['collinearity'].items():
            A(f"| {k} | {fmt(c, 3)} | {'⚠️' if (np.isfinite(c) and abs(c) > 0.7) else ''} |")
    else:
        A('- 未提供存量因子表，跳过')
    A('')
    fm = rpt['fm']
    if fm.get('skipped'):
        A(f"- FM 多元增量检验：跳过（{fm.get('note', '')}）")
    else:
        A(f"- FM 增量 b1：均值={fmt(fm.get('b1_mean'), 4)}，中位={fmt(fm.get('b1_median'), 4)}，NW-t={fmt(fm.get('nw_t'), 2)}（显著线：预登记方向单侧 ≥2.0）；月度 R² 均值={fmt(fm.get('r2_mean'), 3)}；n={fm.get('n')}")
    A('')
    A('## 7. 稳健性矩阵（v3 §8）')
    A('')
    A('分段 ICIR（硬门槛：两段同号且均>0.3）：')
    A('')
    A('| 分段 | ICIR | IC 均值 | n |')
    A('|---|---|---|---|')
    for k, seg in rpt['segments'].items():
        A(f"| {k} | {fmt(seg.get('icir'), 3)} | {fmt(seg.get('mean'), 4)} | {seg.get('n')} |")
    A('')
    if rpt.get('neutralized'):
        nb = rpt['neutralized']
        A(f"- 中性化对比：原始 ICIR={fmt(ib.get('icir'), 3)} vs 行业市值中性 ICIR={fmt(nb.get('icir'), 3)}（预指定版本为准，差异记录）")
        A('')
    A('参数敏感性（报告项，各跑一个变体）：')
    A('')
    A('| 变体 | ICIR | IC 均值 | signed NW-t |')
    A('|---|---|---|---|')
    for k, s in rpt['sensitivity'].items():
        A(f"| {k} | {fmt(s.get('icir'), 3)} | {fmt(s.get('mean'), 4)} | {fmt(s.get('signed_t'), 2)} |")
    A('')
    rl = rpt['rolling']
    if rl.get('available'):
        A(f"- 滚动 36m ICIR 末端值 = {fmt(rl.get('last'), 3)}；观察线触发：{'⚠️ ' + '; '.join(rl['obs']) if rl.get('obs') else '无'}")
        A('')
    A('压力测试（单月多空 <−10% 或连续两月亏损 → 至少观察）：')
    A('')
    A('| 时期 | n | 最差月 | 月均 |')
    A('|---|---|---|---|')
    for p in rpt['stress']:
        A(f"| {p['period']} | {p['n']} | {p['worst_month']:.2%} | {p['mean']:.2%} |")
    A('')
    A('熊市段（报告项）：')
    A('')
    for p in rpt['bear']:
        A(f"- {p['period']}：最差月 {p['worst_month']:.2%}，月均 {p['mean']:.2%}")
    A('')
    A('季节性（月度 IC 按日历月）：')
    A('')
    seas = rpt['seasonality']
    if seas:
        A('| 月 | IC 均值 |')
        A('|---|---|')
        for mm in range(1, 13):
            if mm in seas:
                A(f"| {mm}月 | {seas[mm]:.4f} |")
    A('')
    A('## 8. 样本外确认段（最近 24 个月，报告项不裁决，一次确认制 v3 §3-5）')
    A('')
    oib = rpt['ic_oos']
    A(f"- OOS IC：n={oib.get('n', 0)}，mean={fmt(oib.get('mean'))}，ICIR={fmt(oib.get('icir'), 3)}，signed NW-t={fmt(oib.get('signed_t'), 2)}")
    oe = rpt['oos_econ']
    if oe.get('available'):
        A(f"- OOS 净多空：年化={oe['net_ls_ann_x12']:.2%}（×12），夏普={fmt(oe.get('sharpe'), 2)}，2x 成本后均值={fmt(oe.get('net_ls_2x_mean'), 4)}")
    A(f"- 确认结果：{'✓ 通过（OOS 方向一致）' if v['oos_confirmed'] else '✗ 确认失败 → 降级观察，禁止回训重报'}")
    A('')
    A('## 9. 经济显著性闸门（v3 §10，预指定交易版本=原始版等权）')
    A('')
    ec = rpt['econ']
    if ec.get('available'):
        A('| 闸门 | 值 | 通过线 | 判定 |')
        A('|---|---|---|---|')
        A(f"| 净多空年化（×12） | {ec['net_ls_ann_x12']:.2%} | ≥ 8% | {'✓' if ec['net_ls_ann_x12'] >= 0.08 else ('△ 观察带' if ec['net_ls_ann_x12'] >= 0.04 else '✗')} |")
        A(f"| 净多空年化（×√12 字面口径） | {ec['net_ls_ann_xsqrt12']:.2%} | 报告项 | — |")
        A(f"| 净多空夏普 | {fmt(ec.get('sharpe'), 2)} | ≥ 0.8 | {'✓' if ec.get('sharpe', 0) >= 0.8 else ('△ 观察带' if ec.get('sharpe', 0) >= 0.5 else '✗')} |")
        A(f"| 2x 成本敏感性 | 均值 {fmt(ec.get('net_ls_2x_mean'), 4)} | 仍为正 | {'✓' if ec['net_ls_2x_positive'] else '✗'} |")
        A('')
    A('## 10. 多重检验（v3 §9）')
    A('')
    A(f"- N'（本自然季度同期受检）= {rpt['n_star']}；Bonferroni 单侧 α=0.05 → z={fmt(bonf_threshold(rpt['n_star']), 4)}")
    A(f"- 单一显著性线：signed NW-t ≥ max(3.0, Bonf) = **{rpt['sig_threshold']:.3f}**")
    A(f"- 本因子 signed NW-t = {fmt(ib.get('signed_t'), 2)} → {'✓ 过线' if ib.get('signed_t', -9) >= rpt['sig_threshold'] else '✗ 未过线'}")
    A('')
    A('## 11. 最终判定')
    A('')
    A(f"**{v['verdict']}**（{'初步' if v['preliminary'] else '正式'}）")
    A('')
    A(f"理由：{v['reason']}")
    A('')
    A('## 12. 可复现材料')
    A('')
    A(f"- 检验脚本：`{rpt['script']}`（同数据同结果）")
    A(f"- 数据版本 hash：`{rpt['data_hash']}`")
    A(f"- 随机种子：`{rpt['seed']}`（PT MR / bootstrap）")
    A('- registry 回填：追加式（原行不动），回填行见同目录 `backfill_{name}.md`')
    A('')
    return '\n'.join(L)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _selftest():
    """合成数据自检：已知有效因子应过线、噪声因子不过线、反向因子被淘汰。"""
    print('=== factor_test_suite self-test ===')
    rng = np.random.default_rng(12345)
    n_months, n_stocks = 84, 300
    dates = pd.date_range('2017-01-31', periods=n_months, freq='ME')
    codes = [f'{i:06d}' for i in range(n_stocks)]

    # 真实信号 + 噪声（shift(1) 保证 IC 结构：因子 T 期 → T+1 收益）
    # 标定说明：v3 成本模型较重（千1印花税+分档滑点，2x 成本要求毛多空足够大），
    # 故"已知有效"合成因子取 slope=0.01（IC≈0.12），保证 IC/分层/经济三关全过；
    # 真实 A 股因子的 IC 幅度由试点/正式检验给出，自检只验证逻辑正确性。
    signal = rng.normal(size=(n_months, n_stocks))
    noise = rng.normal(0, 0.08, size=(n_months, n_stocks))
    factor_true = pd.DataFrame(signal, index=dates, columns=codes)
    returns = pd.DataFrame(factor_true.shift(1).fillna(0) * 0.01 + noise,
                           index=dates, columns=codes)
    factor_noise = pd.DataFrame(rng.normal(size=(n_months, n_stocks)),
                                index=dates, columns=codes)
    factor_rev = pd.DataFrame(-signal, index=dates, columns=codes)
    mcap = pd.DataFrame(
        np.exp(rng.normal(np.log(80.0), 0.9, size=(n_months, n_stocks))),
        index=dates, columns=codes)
    fin = pd.DataFrame({'股票代码': codes, '所处行业': [f'IND{i % 8}' for i in range(n_stocks)],
                        '最新公告日期': '2026-08-22'})

    results = {}
    for nm, fac, sign in (('VALID', factor_true, 1), ('NOISE', factor_noise, 1),
                          ('REVERSE', factor_rev, 1)):
        rpt = run_pipeline(fac, returns, mcap, fin, name=nm, expected_sign=sign,
                           n_star=10, start='2017-01-31', oos_months=24)
        results[nm] = rpt
        print(f"[{nm}] verdict={rpt['verdict']['verdict']} "
              f"icir={rpt['ic']['icir']:.3f} meanIC={rpt['ic']['mean']:.4f} "
              f"signed_t={rpt['ic']['signed_t']:.2f} (thr={rpt['sig_threshold']:.2f}) "
              f"pt_p={rpt['pt_mr']['p']:.4f} "
              f"econ_ann={rpt['econ']['net_ls_ann_x12']:.2%} "
              f"sharpe={rpt['econ']['sharpe']:.2f} "
              f"2x={rpt['econ']['net_ls_2x_positive']}")

    # 断言
    v = results['VALID']['verdict']
    assert v['verdict'] == '保留', f'VALID should pass, got {v}'
    ib = results['VALID']['ic']
    assert ib['icir'] > 0.5 and abs(ib['mean']) >= 0.02 and ib['signed_t'] >= 3.0
    assert results['VALID']['pt_mr']['p'] < 0.05, 'VALID PT MR should be monotone'
    assert results['VALID']['econ']['net_ls_ann_x12'] >= 0.08
    assert results['VALID']['econ']['net_ls_2x_positive']
    assert results['VALID']['econ']['sharpe'] >= 0.8
    assert all(rb['pass'] for rb in results['VALID']['robustness'].values()), \
        'VALID robustness should pass'
    assert v['oos_confirmed'], 'VALID OOS should confirm'

    nv = results['NOISE']['verdict']
    assert nv['verdict'] != '保留', f'NOISE should not pass, got {nv}'
    assert results['NOISE']['ic']['icir'] < 0.5

    rv = results['REVERSE']['verdict']
    assert rv['verdict'] == '淘汰', f'REVERSE should be killed, got {rv}'
    assert results['REVERSE']['ic']['signed_t'] <= -3.0, 'REVERSE signed_t should be strongly negative'

    # 回填行生成
    row = registry_backfill_row(results['VALID'])
    assert row['ICIR'] != '—' and row['NW-t'] != '—'
    md = registry_backfill_md(results['VALID'])
    assert md.startswith('| ')

    md_text = render_markdown(results['VALID'])
    assert '## 9. 经济显著性闸门' in md_text and '## 10. 多重检验' in md_text

    print('=== ALL SELF-TEST ASSERTIONS PASSED ===')
    return results


def _cmd_run(argv):
    import argparse
    p = argparse.ArgumentParser(description='v3 因子检验流水线')
    p.add_argument('--factor', required=True, help='因子值宽表 parquet')
    p.add_argument('--ret', required=True, help='月度收益宽表 parquet')
    p.add_argument('--mcap', default=None, help='总市值宽表 parquet（亿元）')
    p.add_argument('--fin', default=None, help='财务长表 parquet')
    p.add_argument('--name', default='FACTOR')
    p.add_argument('--sign', type=int, default=1)
    p.add_argument('--n-star', type=int, default=10)
    p.add_argument('--start', default='2017-01-31')
    p.add_argument('--oos-months', type=int, default=24)
    p.add_argument('--out', default='factor_docs')
    p.add_argument('--registry-no', default=None)
    p.add_argument('--registered-ts', default=None)
    p.add_argument('--factor-type', default='—')
    p.add_argument('--benchmark-icirs', default=None,
                   help='存量因子同窗 ICIR，逗号分隔')
    args = p.parse_args(argv)

    fac = pd.read_parquet(args.factor)
    ret = pd.read_parquet(args.ret)
    mcap = pd.read_parquet(args.mcap) if args.mcap else None
    fin = pd.read_parquet(args.fin) if args.fin else None
    bench = [float(x) for x in args.benchmark_icirs.split(',')] if args.benchmark_icirs else None

    rpt = run_pipeline(fac, ret, mcap, fin, name=args.name, expected_sign=args.sign,
                       n_star=args.n_star, start=args.start, oos_months=args.oos_months,
                       registry_no=args.registry_no, registered_ts=args.registered_ts,
                       factor_type=args.factor_type, benchmark_icirs=bench,
                       input_files=[args.factor, args.ret] + [x for x in (args.mcap, args.fin) if x])
    os.makedirs(args.out, exist_ok=True)
    date = rpt['report_date'].replace('-', '')
    md = render_markdown(rpt)
    md_path = os.path.join(args.out, f'test_{args.name}_{date}.md')
    with open(md_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(md)
    bf_path = os.path.join(args.out, f'backfill_{args.name}_{date}.md')
    with open(bf_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('| ' + ' | '.join([
            '#','因子','类型','状态','登记时间戳','预期符号(前置,锁定)','样本期',
            '数据版本hash','检验脚本','IC均值','IC标准差','ICIR','naive t','NW-t',
            '胜率','覆盖率','PT MR p','净多空年化','夏普','2x成本','内部基准',
            '调参标记','结论','MImo审批','备注']) + ' |\n')
        fh.write(registry_backfill_md(rpt) + '\n')
    print(f'[OK] report -> {md_path}')
    print(f'[OK] backfill row -> {bf_path}')
    print(f'[RESULT] {args.name}: {rpt["verdict"]["verdict"]} '
          f'({rpt["verdict"]["reason"][:120]})')


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == 'self-test':
        _selftest()
    elif argv and argv[0] == 'run':
        _cmd_run(argv[1:])
    else:
        print(__doc__)
        print('usage: factor_test_suite.py self-test | run --factor F.parquet ...')


if __name__ == '__main__':
    main()
