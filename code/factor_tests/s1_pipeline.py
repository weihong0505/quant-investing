# -*- coding: utf-8 -*-
"""
S1/M5 检验管线核心统计函数 (factor_testing_methodology_v3 落地)
- nw_t: Bartlett 核 Newey-West t (手写, 与 statsmodels HAC 对照)
- ic_series / ic_report: 月度 Rank IC 全套
- layered: 5分组多空 + 三重稳健性 + 成本 + PT MR + FM β 单调性
- pt_mr: Patton-Timmermann 单调性 bootstrap (R=9999, null recentering)
- fm_incremental: Fama-MacBeth 多元增量检验
"""
import numpy as np
import pandas as pd

RNG_SEED = 42

# ---------------- NW-t ----------------
def nw_lag(N):
    """NW 1994: floor(4*(N/100)^(2/9)); 至少 2 (FM), 重叠收益 max(3, ...)"""
    return max(2, int(np.floor(4 * (N / 100.0) ** (2 / 9.0))))

def nw_t(x, lag=None, min_lag=2):
    """
    Bartlett 核 NW-t for 序列均值 (常数项回归).
    实现: var(mean) = [S0 + 2*Σ_{j=1..L} w_j S_j] / N, w_j = 1 - j/(L+1),
          S_j = (1/N) Σ_t e_t e_{t-j}, e = x - mean; t = mean / sqrt(var)
    """
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    N = len(x)
    if N < 10:
        return np.nan
    if lag is None:
        lag = max(min_lag, nw_lag(N))
    lag = int(min(lag, N - 2))
    m = x.mean()
    e = x - m
    S0 = (e @ e) / N
    var = S0
    for j in range(1, lag + 1):
        Sj = (e[j:] @ e[:-j]) / N
        wj = 1.0 - j / (lag + 1.0)
        var += 2 * wj * Sj
    var = max(var, 1e-16)
    return m / np.sqrt(var / N)

def nw_t_overlap(x, lag=None):
    """重叠收益 (T+1~T+3) 用 lag = max(3, 公式值)"""
    return nw_t(x, lag=max(3, nw_lag(len(x))) if lag is None else lag)

# ---------------- IC ----------------
def monthly_ic(panel, factor, direction=1):
    """逐月 Spearman(factor_T, ret_next); 返回 Series(index=date)"""
    ics = {}
    for d, g in panel.groupby('date'):
        g = g.dropna(subset=[factor, 'ret_next'])
        if len(g) < 30:
            continue
        ics[d] = g[factor].corr(g['ret_next'], method='spearman')
    s = pd.Series(ics).sort_index()
    return s * direction if direction != 1 else s

def ic_stats(ic_series, factor_name=''):
    ic = ic_series.dropna()
    N = len(ic)
    if N < 12:
        return None
    mean_ic = ic.mean()
    sd_ic = ic.std(ddof=1)
    icir = mean_ic / sd_ic if sd_ic > 0 else np.nan
    naive_t = mean_ic / (sd_ic / np.sqrt(N)) if sd_ic > 0 else np.nan
    nwt = nw_t(ic.values)
    win = (ic > 0).mean()
    return {'factor': factor_name, 'N': N, 'mean_ic': mean_ic, 'sd_ic': sd_ic,
            'icir': icir, 'naive_t': naive_t, 'nw_t': nwt, 'win_rate': win}

def ic_report(panel, factor, direction=1, label=''):
    """
    完整 IC 报告: 主口径 + 衰减 + down-month/高波动月 + winsorize 对照 + 分段 + 训练/测试 + 滚动36m
    """
    ic = monthly_ic(panel, factor, direction)
    ic = ic.dropna()
    res = {'factor': label or factor, 'ic_series': ic}
    st = ic_stats(ic)
    res.update(st)

    # 市场收益 (等权代理) 与波动
    mkt = panel.groupby('date')['ret_next'].mean()
    mkt = mkt.reindex(ic.index)
    down = ic[mkt < 0]
    res['down_month_ic'] = down.mean() if len(down) else np.nan
    res['down_month_n'] = len(down)
    vol = mkt.rolling(6, min_periods=3).std()
    hi_vol = ic[vol >= vol.quantile(2 / 3)]
    res['hivol_month_ic'] = hi_vol.mean() if len(hi_vol) else np.nan
    res['hivol_month_n'] = len(hi_vol)

    # winsorize 1%/99% 对照
    icw = ic.clip(ic.quantile(0.01), ic.quantile(0.99))
    res['icir_winsor'] = icw.mean() / icw.std(ddof=1) if icw.std(ddof=1) > 0 else np.nan

    # 衰减: T+2, T+3(复合), T+6, T+12
    decay = {}
    for k, col in ((1, 'ret_next'), (3, 'ret_t3'), (6, 'ret_t6'), (12, 'ret_t12')):
        ics = {}
        for d, g in panel.groupby('date'):
            g = g.dropna(subset=[factor, col])
            if len(g) < 30:
                continue
            ics[d] = g[factor].corr(g[col], method='spearman')
        s = pd.Series(ics).sort_index().dropna()
        decay[f'h{k}'] = s.mean() if len(s) else np.nan
        decay[f'h{k}_icir'] = s.mean() / s.std(ddof=1) if len(s) > 3 and s.std(ddof=1) > 0 else np.nan
    res['decay'] = decay

    # 分段 (结构断点)
    seg = {}
    for name, lo, hi in (('2017-2021', '2017-01', '2021-12'), ('2022-2026', '2022-01', '2026-12')):
        s = ic[(ic.index >= lo) & (ic.index <= hi)]
        seg[name] = {'mean_ic': s.mean() if len(s) else np.nan, 'nw_t': nw_t(s.values) if len(s) > 5 else np.nan}
    res['segments'] = seg

    # 训练/测试 (2017-2023 vs 2024+)
    tr = ic[ic.index < '2024-01']
    te = ic[ic.index >= '2024-01']
    res['train'] = {'N': len(tr), 'mean_ic': tr.mean() if len(tr) else np.nan,
                    'icir': tr.mean() / tr.std(ddof=1) if len(tr) > 3 and tr.std(ddof=1) > 0 else np.nan,
                    'nw_t': nw_t(tr.values) if len(tr) > 5 else np.nan}
    res['test'] = {'N': len(te), 'mean_ic': te.mean() if len(te) else np.nan,
                   'icir': te.mean() / te.std(ddof=1) if len(te) > 3 and te.std(ddof=1) > 0 else np.nan,
                   'nw_t': nw_t(te.values) if len(te) > 5 else np.nan}

    # 滚动 36m ICIR
    roll = ic.rolling(36, min_periods=24).apply(lambda x: x.mean() / x.std(ddof=1) if x.std(ddof=1) > 0 else np.nan, raw=True)
    res['rolling_icir'] = roll.dropna()
    return res

# ---------------- 分层 ----------------
def cost_bps(mcap_yi):
    """市值分档滑点 (单边 bp) + 往返成本 bp (含佣金/印花税/过户费, 按日期变印花税在调用处处理)"""
    if mcap_yi >= 500:
        return 5
    if mcap_yi >= 100:
        return 10
    if mcap_yi >= 30:
        return 20
    return 30

def roundtrip_cost_bp(mcap_yi, date):
    """往返成本 bp: 佣金万2.5双边 + 印花税卖出(2023-08-28前千1后万5) + 过户费万0.1双边 + 滑点×2"""
    comm = 2.5 * 2          # 万2.5 双边 -> bp: 2.5bp*2
    stamp = 10.0 if date < pd.Timestamp('2023-08-28') else 5.0   # 千1=10bp / 万5=5bp
    transfer = 0.1 * 2
    slip = cost_bps(mcap_yi) * 2
    return comm + stamp + transfer + slip

def layering(panel, factor, direction=1, label='', min_stocks=30):
    """
    5 分组: 等权主口径 + 成本后净多空; 返回完整结果 dict
    """
    g5 = {}
    for d, g in panel.groupby('date'):
        g = g.dropna(subset=[factor, 'ret_next', 'mcap_est'])
        if len(g) < min_stocks:
            continue
        g = g.copy()
        g['q'] = pd.qcut(g[factor].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
        g5[d] = g
    dates = sorted(g5.keys())

    # 组月收益 (等权)
    rets = pd.DataFrame(index=dates, columns=[1, 2, 3, 4, 5], dtype=float)
    sizes = pd.DataFrame(index=dates, columns=[1, 2, 3, 4, 5], dtype=float)
    for d in dates:
        g = g5[d]
        for q in range(1, 6):
            sub = g[g['q'] == q]
            rets.loc[d, q] = sub['ret_next'].mean()
            sizes.loc[d, q] = len(sub)
    ls = rets[5] - rets[1]
    if direction == -1:
        ls = -ls

    # 换手与成本 (等权, 组内成分变化)
    to = {}
    cost = {}
    prev_members = {}
    for d in dates:
        g = g5[d]
        members = {q: set(g[g['q'] == q].index) for q in range(1, 6)}
        for q in (1, 5):
            if d in prev_members:
                old = prev_members[q]
                new = members[q]
                turn = 1.0 - len(old & new) / max(len(old), 1)
            else:
                turn = 1.0
            sub = g[g['q'] == q]
            avg_cost = sub.apply(lambda r: roundtrip_cost_bp(r['mcap_est'], pd.Timestamp(d)), axis=1).mean()
            to[(d, q)] = turn
            cost[(d, q)] = avg_cost
        prev_members = members
    net_ls = pd.Series({d: ls[d] * 100 - (to[(d, 5)] * cost[(d, 5)] + to[(d, 1)] * cost[(d, 1)]) / 100.0
                        for d in dates})  # bp->%: /100
    net_ls_2x = pd.Series({d: ls[d] * 100 - 2 * (to[(d, 5)] * cost[(d, 5)] + to[(d, 1)] * cost[(d, 1)]) / 100.0
                           for d in dates})

    # 三重稳健性
    # A) 市值加权
    vw = {}
    for d in dates:
        g = g5[d]
        r = {}
        for q in range(1, 6):
            sub = g[g['q'] == q]
            if len(sub) == 0 or sub['mcap_est'].sum() <= 0:
                r[q] = np.nan
            else:
                r[q] = (sub['ret_next'] * sub['mcap_est']).sum() / sub['mcap_est'].sum()
        vw[d] = r
    vwdf = pd.DataFrame(vw).T
    vw_ls = vwdf[5] - vwdf[1]
    if direction == -1:
        vw_ls = -vw_ls
    # B) 剔 <30亿
    exs = {}
    for d in dates:
        g = g5[d][g5[d]['mcap_est'] >= 30]
        if len(g) < min_stocks:
            continue
        r = {}
        for q in range(1, 6):
            sub = g[g['q'] == q]
            r[q] = sub['ret_next'].mean()
        exs[d] = r
    exdf = pd.DataFrame(exs).T
    ex_ls = exdf[5] - exdf[1]
    if direction == -1:
        ex_ls = -ex_ls
    # C) 规模中性 3×5 dependent sort
    sn = {}
    for d in dates:
        g = g5[d]
        if len(g) < 3 * min_stocks:
            continue
        g = g.copy()
        g['sz3'] = pd.qcut(g['mcap_est'].rank(method='first'), 3, labels=[1, 2, 3])
        spreads = []
        for s in (1, 2, 3):
            sub = g[g['sz3'] == s]
            if len(sub) < 10:
                continue
            sub = sub.copy()
            sub['q'] = pd.qcut(sub[factor].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
            r = {q: sub[sub['q'] == q]['ret_next'].mean() for q in range(1, 6)}
            spreads.append(r[5] - r[1])
        if spreads:
            sn[d] = np.mean(spreads)
    sndf = pd.Series(sn)
    if direction == -1:
        sndf = -sndf
    # 规模中性有效性: spread 对 ln_mcap 回归 β (逐月, 用组均值差 vs 规模组)
    size_beta = np.nan

    def annualize(x):
        x = x.dropna()
        if len(x) < 6:
            return np.nan, np.nan, np.nan
        mu = x.mean() * 12
        sd = x.std(ddof=1) * np.sqrt(12)
        return mu, sd, (mu / sd if sd > 0 else np.nan)

    res = {
        'label': label, 'dates': dates,
        'g_ret_ann': rets.mean() * 12, 'g_sharpe': rets.mean() / rets.std(ddof=1) * np.sqrt(12),
        'g_size': sizes.mean(),
        'ls': ls, 'ls_ann': ls.mean() * 12, 'ls_nw_t': nw_t(ls.values),
        'net_ls': net_ls, 'net_ls_ann': net_ls.mean() * 12,
        'net_ls_2x': net_ls_2x, 'net_ls_2x_ann': net_ls_2x.mean() * 12,
        'net_sharpe': net_ls.mean() / net_ls.std(ddof=1) * np.sqrt(12) if net_ls.std(ddof=1) > 0 else np.nan,
        'turnover_q5': np.mean([to[(d, 5)] for d in dates]), 'turnover_q1': np.mean([to[(d, 1)] for d in dates]),
        'cost_q5': np.mean([cost[(d, 5)] for d in dates]), 'cost_q1': np.mean([cost[(d, 1)] for d in dates]),
        'vw_ls_ann': vw_ls.mean() * 12, 'vw_ls_nw_t': nw_t(vw_ls.dropna().values),
        'ex_ls_ann': ex_ls.mean() * 12, 'ex_ls_nw_t': nw_t(ex_ls.dropna().values),
        'sn_ls_ann': sndf.mean() * 12, 'sn_ls_nw_t': nw_t(sndf.dropna().values),
        'sn_n': len(sndf.dropna()),
        'size_beta': size_beta,
    }
    # 压力测试月份
    stress = {'2018-10': None, '2020-02': None, '2024-01': None, '2024-02': None, '2024-09': None}
    for k in stress:
        hit = [d for d in dates if d.strftime('%Y-%m') == k]
        stress[k] = ls[hit].iloc[0] * 100 if hit else None
    res['stress'] = stress
    return res

def pt_mr(g_ret, direction=1, R=9999, seed=RNG_SEED):
    """
    Patton-Timmermann 单调性检验.
    g_ret: DataFrame(T×5) 组月收益; direction: +1 递增
    """
    g = g_ret.dropna()
    if len(g) < 36:
        return {'p': np.nan, 'J0': np.nan, 'note': 'T<36 功效不足'}
    T = len(g)
    d = direction
    D = d * (g.values[:, 1:] - g.values[:, :-1])  # T×4
    J0 = D.mean(axis=0).min()
    rng = np.random.default_rng(seed)
    # stationary bootstrap: 几何块长平均3
    p_block = 1 / 3.0
    Jstar = np.zeros(R)
    for b in range(R):
        # 生成块起点序列
        starts = []
        i = 0
        while i < T:
            L = min(T - i, int(rng.geometric(p_block)))
            starts.append(i)
            i += L
        idx = np.concatenate([np.arange(s, min(s + T, T)) for s in starts])[:T]
        if len(idx) < T:
            idx = np.concatenate([idx, rng.integers(0, T, T - len(idx))])
        Db = D[idx]
        Jstar[b] = Db.mean(axis=0).min()
    Jt = Jstar - J0  # null recentering
    p = (1 + np.sum(Jt >= J0)) / (R + 1)
    return {'p': p, 'J0': J0, 'R': R, 'note': ''}

def fm_beta_monotonicity(g_ret, direction=1):
    """逐月 5组收益对组序号回归 β 的 FM 均值 + NW-t (lag=1~2)"""
    betas = []
    for _, row in g_ret.dropna().iterrows():
        x = np.arange(1, 6)
        y = row.values.astype(float)
        if np.isnan(y).any():
            continue
        b = np.polyfit(x, y, 1)[0]
        betas.append(b)
    b = np.array(betas)
    return {'fm_beta': b.mean() * direction, 'nw_t': nw_t(b * direction, min_lag=1) if len(b) > 5 else np.nan, 'n': len(b)}

def autocorr_rank(panel, factor):
    """月度横截面排名 Spearman 自相关 lag1/3/6"""
    ranks = {}
    for d, g in panel.groupby('date'):
        g = g.dropna(subset=[factor])
        if len(g) < 30:
            continue
        ranks[d] = g[factor].rank()
    rdf = pd.DataFrame(ranks).sort_index(axis=1)
    out = {}
    for lag in (1, 3, 6):
        corrs = []
        for i in range(lag, len(rdf.columns)):
            a, b = rdf.iloc[:, i - lag], rdf.iloc[:, i]
            common = a.index.intersection(b.index)
            if len(common) > 30:
                corrs.append(a[common].corr(b[common], method='spearman'))
        out[f'lag{lag}'] = np.mean(corrs) if corrs else np.nan
    return out

# ---------------- FM 增量 ----------------
def fm_incremental(panel, factors=('EP', 'BP', 'MOM_60D'), include_size=True, min_stocks=100):
    """
    Fama-MacBeth: r_{t+1} ~ ln_mcap + EP + BP + MOM_60D + 行业哑变量
    连续变量月度 z-score (先 ±3σ winsorize); 收益 1%/99% winsorize
    返回各变量月度系数均值 + NW-t
    """
    import statsmodels.api as sm
    coefs = {f: [] for f in factors}
    coefs['ln_mcap'] = []
    r2s = []
    vifs = {f: [] for f in factors}
    vifs['ln_mcap'] = []
    n_obs = []
    for d, g in panel.groupby('date'):
        g = g.dropna(subset=['ret_next', 'ln_mcap' if False else 'LOG_MCAP'] + list(factors))
        if len(g) < min_stocks:
            continue
        g = g.copy()
        y = g['ret_next'].clip(g['ret_next'].quantile(0.01), g['ret_next'].quantile(0.99))
        X = pd.DataFrame(index=g.index)
        for f in factors + ('LOG_MCAP',):
            if include_size or f != 'LOG_MCAP':
                v = g[f]
                m, s = v.mean(), v.std(ddof=0)
                v = v.clip(m - 3 * s, m + 3 * s) if s > 0 else v
                X[f] = (v - v.mean()) / v.std(ddof=0) if v.std(ddof=0) > 0 else 0.0
        if include_size:
            X = X.rename(columns={'LOG_MCAP': 'ln_mcap'})
        # 行业哑变量
        ind = g['industry'].astype('category')
        Xd = pd.get_dummies(ind, prefix='ind', drop_first=False)
        Xf = pd.concat([X, Xd], axis=1)
        Xf = sm.add_constant(Xf)
        try:
            fit = sm.OLS(y, Xf).fit()
        except Exception:
            continue
        for f in factors:
            if f in fit.params:
                coefs[f].append(fit.params[f])
        if 'ln_mcap' in fit.params:
            coefs['ln_mcap'].append(fit.params['ln_mcap'])
        r2s.append(fit.rsquared)
        n_obs.append(len(g))
        # VIF
        Xc = Xf.drop(columns=['const'])
        if Xc.shape[1] > 1:
            corr = Xc.corr()
            try:
                inv = np.linalg.inv(corr.values)
                vif = pd.Series(np.diag(inv), index=corr.columns)
                for f in factors + (['ln_mcap'] if include_size else []):
                    if f in vif.index:
                        vifs[f].append(vif[f])
            except Exception:
                pass
    out = {}
    for f in list(coefs.keys()):
        c = np.array(coefs[f])
        if len(c) > 5:
            out[f] = {'mean': c.mean(), 'nw_t': nw_t(c, min_lag=2), 'n': len(c),
                      'q10': np.percentile(c, 10), 'q90': np.percentile(c, 90),
                      'vif_mean': np.mean(vifs[f]) if vifs[f] else np.nan}
        else:
            out[f] = {'mean': np.nan, 'nw_t': np.nan, 'n': len(c), 'q10': np.nan, 'q90': np.nan, 'vif_mean': np.nan}
    out['r2_mean'] = np.mean(r2s) if r2s else np.nan
    out['n_obs_mean'] = np.mean(n_obs) if n_obs else np.nan
    return out
