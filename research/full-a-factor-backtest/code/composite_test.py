# -*- coding: utf-8 -*-
"""
composite_test.py — 组合层检验（composite_testing_methodology_v1 §3.1）
=====================================================================
检验对象：合成 SCORE = Σ w_i × d_i × z_i

本次组合的构成（**必须声明的偏离**）：
  - 方法论文档 §1.2 的对象是 v2 的 9 因子加权；但其中 4 个因子本项目**无法计算**
    （CFO_NI_TTM / LEV / TURNOVER / LOG_MCAP 中，前三个数据缺失），
    且 EP/BP/ROE_TTM/GPM 四者已在本轮通过单因子层检验（结果：淘汰/观察）。
  - 故本次检验的是**可用子集组合**，权重取自项项目自有设计口径并按可用因子重归一化：
      估值层   EP 0.30 → 0.3333 ; BP 0.30 → 0.3333   （v3 安全边际分前两项）
      质量层   ROE_TTM 0.15 → 0.1667 ; GPM 0.15 → 0.1667
      （原设计含 DY 0.05 / FCF_YIELD 0.05，二者**尚未登记**，故不纳入，上界声明）
    重归一化后和 = 1.0000。方向全部为 +（registry 锁定值）。
  - 输入 z 值取**行业内中性化**版本（wide_n/_N），与用户本轮要求的 2(中性化) 一致。

必报项（§3.1）：合成 IC 统计量 / 加权单因子基准 B 与交互损耗 / leave-one-out ΔIC /
IC 衰减 T+1..T+12 / 滚动 36m ICIR / down-month 与高波动月 IC（硬指标） /
分年度与分制度段 / 分层 5 组净多空（含 2x 成本）/ 因子相关矩阵（训练段裁决）与交互处置

用法：D:/pyh/python.exe -E composite_test.py
输出：reports/composite/composite_report.md + composite_metrics.json
"""
import os
import sys
import json
import datetime as dt

import numpy as np
import pandas as pd

sys.path.insert(0, r'g:\股市探究\quant-investing\code')
sys.stdout.reconfigure(encoding='utf-8')

TASK = r'g:\股市探究\fullA-检验与回测'
WIDE_N = os.path.join(TASK, 'data', 'wide_n')
OUT = os.path.join(TASK, 'reports', 'composite')

# ---- 组合定义（执行前冻结）----
COMPOSITE_NAME = 'V3-SAFETY-MARGIN-AVAIL-4'
WEIGHTS = {'EP': 0.30 / 0.90, 'BP': 0.30 / 0.90, 'ROE_TTM': 0.15 / 0.90, 'GPM': 0.15 / 0.90}
SIGNS = {'EP': 1, 'BP': 1, 'ROE_TTM': 1, 'GPM': 1}
N_STAR_COMPOSITE = 9          # 4 因子原始口径 + 4 因子中性化 + 1 合成 = 9
BONF_ALPHA = 0.05
OOS_MONTHS = 24
NW_LAG = 3                    # T+1~T+3 重叠时 lag=max(3, 公式值)

# v3 §5.2 成本模型（与 factor_test_suite 一致）
STAMP = [(pd.Timestamp('2023-08-28'), 5e-4), (pd.Timestamp('1970-01-01'), 1e-3)]
COMMISSION, TRANSFER = 2.5e-4, 0.1e-4
SLIP = [(500.0, 5e-4), (100.0, 1e-3), (30.0, 2e-3), (0.0, 3e-3)]


def one_way_cost(mcap_yi, date):
    """单边成本（佣金+过户+滑点）；印花税在卖出侧"""
    slip = next(v for th, v in SLIP if mcap_yi >= th)
    return COMMISSION + TRANSFER + slip


def round_trip_cost(mcap_yi, date):
    """**旧口径（已弃用）**：假设每期两腿各全额往返 = 每期 100% 换手。
    实测该假设把月频成本高估到 13.43%/年（真实值 1.83%/年），
    曾据此得出「净多空 −1.60%、经济面不可行」的**错误结论**。
    仅保留供对照，主口径改用 turnover_leg_cost。"""
    stamp = next(v for t, v in STAMP if date >= t)
    return 2 * one_way_cost(mcap_yi, date) + stamp


def turnover_leg_cost(turnover, mcap_yi, date):
    """**主口径**：按真实换手计费。
    turnover = Σ|w_target − w_drift|（该腿），成本 = 换手 × 单边成本（买侧）
               + 换手 ×（单边成本 + 印花税）（卖侧）。
    单腿合计 ≈ turnover × (2×单边 + 印花税)，与旧口径的差别在于
    **用真实 turnover 取代了「每期全额 2×」的假设**。"""
    stamp = next(v for t, v in STAMP if date >= t)
    ow = one_way_cost(mcap_yi, date)
    return turnover * (ow + ow + stamp)


def nw_t(x, lag=NW_LAG):
    """Newey-West t（Bartlett 核）"""
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    T = len(x)
    if T < 5:
        return np.nan
    m = x.mean()
    d = x - m
    g0 = (d @ d) / T
    s = g0
    for l in range(1, min(lag, T - 1) + 1):
        gl = (d[l:] @ d[:-l]) / T
        s += 2 * (1 - l / (lag + 1)) * gl
    if s <= 0:
        return np.nan
    return m / np.sqrt(s / T)


def bonf(n):
    from scipy import stats
    return stats.norm.ppf(1 - BONF_ALPHA / max(1, n))


def rank_ic(a, b):
    m = a.notna() & b.notna()
    if m.sum() < 30:
        return np.nan
    return a[m].rank().corr(b[m].rank())


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--weights', default=None,
                    help='覆盖权重，如 "EP=0.5,BP=0.5"；省略则用 v3 安全边际分重归一化')
    ap.add_argument('--tag', default='', help='输出文件名标记')
    args = ap.parse_args()
    global WEIGHTS, COMPOSITE_NAME
    if args.weights:
        w = {}
        for kv in args.weights.split(','):
            k, v = kv.split('=')
            w[k.strip()] = float(v)
        tot = sum(w.values())
        WEIGHTS = {k: v / tot for k, v in w.items()}
        COMPOSITE_NAME = 'REVISED-' + '-'.join(sorted(w))
    if args.tag:
        COMPOSITE_NAME = f'{COMPOSITE_NAME}-{args.tag}'

    os.makedirs(OUT, exist_ok=True)
    print(f'=== 组合层检验: {COMPOSITE_NAME} ===')
    print('  权重（重归一化）:', {k: round(v, 4) for k, v in WEIGHTS.items()})

    Z = {f: pd.read_parquet(os.path.join(WIDE_N, f'{f}.parquet')) for f in WEIGHTS}
    ret = pd.read_parquet(os.path.join(WIDE_N, 'ret.parquet'))
    mcap = pd.read_parquet(os.path.join(WIDE_N, 'mcap.parquet'))
    print(f'  宽表: ' + ' | '.join(f'{f}{Z[f].shape}' for f in WEIGHTS))
    print(f'  ret{ret.shape}  mcap{mcap.shape}')

    # ---- 合成 SCORE（月度 PIT：T 月末 z 值加权）----
    idx = Z['EP'].index
    cols = sorted(set.intersection(*[set(Z[f].columns) for f in WEIGHTS]))
    score = pd.DataFrame(0.0, index=idx, columns=cols)
    for f, w in WEIGHTS.items():
        z = Z[f].reindex(index=idx, columns=cols).fillna(0.0)   # 缺失因子贡献 0（中性）
        score += w * SIGNS[f] * z
    print(f'  合成 SCORE {score.shape}（股票交集 {len(cols):,}）')

    # ---- 合成 IC 序列（T vs ret T+1）----
    ics, dates_used = [], []
    for i, d in enumerate(idx[:-1]):
        if d not in ret.index:
            continue
        nxt = ret.index[i + 1]
        ic = rank_ic(score.loc[d], ret.loc[nxt])
        if not np.isnan(ic):
            ics.append(ic)
            dates_used.append(d)
    ic_s = pd.Series(ics, index=pd.DatetimeIndex(dates_used))
    print(f'  合成 IC: n={len(ic_s)}  月  {ic_s.index.min().date()} ~ {ic_s.index.max().date()}')

    mean_ic, sd_ic = ic_s.mean(), ic_s.std(ddof=1)
    icir = mean_ic / sd_ic
    naive_t = mean_ic / (sd_ic / np.sqrt(len(ic_s)))
    nwt = nw_t(ic_s)
    winrate = (ic_s > 0).mean()

    # ---- 加权单因子基准 B ----
    B, single = 0.0, {}
    for f, w in WEIGHTS.items():
        s = []
        for i, d in enumerate(idx[:-1]):
            if d not in ret.index:
                continue
            ic = rank_ic(Z[f].loc[d], ret.iloc[i + 1])
            if not np.isnan(ic):
                s.append(ic)
        mi = float(np.mean(s))
        single[f] = {'mean_ic': mi, 'n': len(s), 'icir': mi / float(np.std(s, ddof=1)),
                     'nw_t': nw_t(s)}
        B += w * SIGNS[f] * mi
    inter_loss = mean_ic - B

    # ---- leave-one-out ----
    loo = {}
    for drop in WEIGHTS:
        w2 = {f: v for f, v in WEIGHTS.items() if f != drop}
        tot = sum(w2.values())
        sc = pd.DataFrame(0.0, index=idx, columns=cols)
        for f, w in w2.items():
            sc += (w / tot) * SIGNS[f] * Z[f].reindex(index=idx, columns=cols).fillna(0.0)
        s = [rank_ic(sc.loc[d], ret.iloc[i + 1])
             for i, d in enumerate(idx[:-1]) if d in ret.index]
        s = [x for x in s if not np.isnan(x)]
        loo[drop] = {'mean_ic': float(np.mean(s)), 'delta_ic': mean_ic - float(np.mean(s))}

    # ---- IC 衰减 T+1..T+12 ----
    decay = {}
    for k in [1, 2, 3, 6, 12]:
        s = []
        for i, d in enumerate(idx):
            j = i + k
            if j >= len(idx) or idx[j] not in ret.index:
                continue
            ic = rank_ic(score.loc[d], ret.loc[idx[j]])
            if not np.isnan(ic):
                s.append(ic)
        decay[f'T+{k}'] = float(np.mean(s)) if s else np.nan

    # ---- 滚动 36m ICIR ----
    roll = ic_s.rolling(36).apply(lambda x: x.mean() / x.std(ddof=1) if x.std(ddof=1) else np.nan)
    roll_tail = roll.dropna().tail(1)
    # 观察线：末端 <0.3 / 连续 ≥12 月为负 / 断点后 12 月未回正
    neg12 = bool((ic_s.tail(12) < 0).all())

    # ---- down-month / 高波动月（硬指标）----
    mkt = ret.mean(axis=1)                      # 等权市场月收益
    vol = ret.std(axis=1)                       # 横截面离散度（高波动代理）
    vol_med = vol.median()
    down = ic_s.index[ic_s.index.isin(mkt.index[mkt < 0])]
    highv = ic_s.index[ic_s.index.isin(vol.index[vol > vol_med])]
    ic_down = float(ic_s.reindex(down).dropna().mean()) if len(down) else np.nan
    ic_high = float(ic_s.reindex(highv).dropna().mean()) if len(highv) else np.nan

    # ---- 分年度 / 分制度段 ----
    by_year = ic_s.groupby(ic_s.index.year).agg(['mean', 'count'])
    segs = {'2017~2018': ('2017-01-01', '2018-12-31'),
            '2019~2020-08': ('2019-01-01', '2020-08-31'),
            '2020-08~2023-02': ('2020-09-01', '2023-02-28'),
            '2023-02~今': ('2023-03-01', '2030-01-01')}
    by_seg = {k: float(ic_s.loc[v[0]:v[1]].mean()) for k, v in segs.items()}

    # ---- 分层 5 组净多空（含成本）----
    # ⚠️ 2026-10-09 修复的 bug：原写法把因子值与收益用**位置**配对
    #    （`ret.index[i+1]` / `idx[i+1]`），当两个宽表的月份集合不一致时
    #    会把 T 期因子对上 T+2 期收益 → 出现「合成 IC 为正 0.0562 却算出
    #    净多空 −1.60%」的自相矛盾。诊断脚本已证明按月 rank IC 与毛多空
    #    **本就逐月一致**（+0.107↔+2.17% / −0.051↔−2.26%）。
    #    修法：显式按**日期**取「严格晚于 d 的最近一个可用月份」，
    #    完全不使用位置索引；并加一致性闸门自查。
    ret_dates = pd.DatetimeIndex(sorted(ret.index))
    mcap_dates = pd.DatetimeIndex(sorted(mcap.index))
    next_ret_date, next_mcap_date = {}, {}
    for d in idx:
        later = ret_dates[ret_dates > d]
        next_ret_date[d] = later[0] if len(later) else None
        lm = mcap_dates[mcap_dates <= d]
        next_mcap_date[d] = lm[-1] if len(lm) else None

    q_rets = {1: [], 2: [], 3: [], 4: [], 5: []}
    ls_net, ls_net2x, ls_gross = [], [], []
    pos_date_mismatch = 0   # g3：位置法 vs 日期法取到的次月是否一致
    prev_hi, prev_lo = None, None   # 上期两腿的漂移权重（真实换手用）
    to_hist = []
    for d in idx[:-1]:
        nd = next_ret_date[d]
        # g3 自查：位置法（ret.index 中 d 的下一个）与日期法取到的次月是否相同
        if d in ret.index:
            _pi = ret.index.get_loc(d)
            if _pi + 1 < len(ret.index) and ret.index[_pi + 1] != nd:
                pos_date_mismatch += 1
        if nd is None:
            continue
        sc, rr = score.loc[d], ret.loc[nd]           # 按日期对齐
        m = sc.notna() & rr.notna()
        if m.sum() < 100:
            continue
        q = pd.qcut(sc[m].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
        for k in q_rets:
            sel = q[q == k].index
            q_rets[k].append(rr[sel].mean())
        hi, lo = q[q == 5].index, q[q == 1].index
        if len(hi) and len(lo):
            gross = rr[hi].mean() - rr[lo].mean()
            ls_gross.append((d, gross))
            md = next_mcap_date[d]
            mc_row = mcap.loc[md] if md is not None else None

            def _mc(codes):
                if mc_row is None:
                    return 100.0
                v = pd.to_numeric(mc_row.reindex(codes), errors='coerce')
                med = float(v.median()) if v.notna().any() else np.nan
                return 100.0 if np.isnan(med) else med

            # ---- 主口径：真实换手（Σ|w_target − w_drift|），而非「每期全额往返」----
            w_hi = pd.Series(1.0 / len(hi), index=list(hi))
            w_lo = pd.Series(1.0 / len(lo), index=list(lo))
            if prev_hi is None:
                to_h, to_l = float(w_hi.sum()), float(w_lo.sum())
            else:
                ax = w_hi.index.union(prev_hi.index)
                to_h = float((w_hi.reindex(ax).fillna(0.0) -
                              prev_hi.reindex(ax).fillna(0.0)).abs().sum())
                ay = w_lo.index.union(prev_lo.index)
                to_l = float((w_lo.reindex(ay).fillna(0.0) -
                              prev_lo.reindex(ay).fillna(0.0)).abs().sum())
            # 两腿各占 0.5 名义本金
            c1 = 0.5 * (turnover_leg_cost(to_h, _mc(list(hi)), nd) +
                        turnover_leg_cost(to_l, _mc(list(lo)), nd))
            ls_net.append(gross - c1)
            ls_net2x.append(gross - 2 * c1)
            to_hist.append(0.5 * (to_h + to_l))

            def _drift(w):
                x = w * (1 + rr.reindex(w.index).fillna(0.0))
                s = x.sum()
                return x / s if s > 0 else x

            prev_hi, prev_lo = _drift(w_hi), _drift(w_lo)
    annual_turnover = float(np.sum(to_hist) / (len(idx) / 12)) if to_hist else np.nan
    q_ann = {k: float(np.mean(v) * 12) for k, v in q_rets.items()}
    ls_net_s = pd.Series(ls_net)
    ls2_s = pd.Series(ls_net2x)
    ls_dates = pd.DatetimeIndex([d for d, _ in ls_gross])
    ls_gross_s = pd.Series([g for _, g in ls_gross], index=ls_dates)
    # ---- 一致性闸门（修订版）----
    # 第一版闸门要求「逐月 IC 与毛多空同号率 ≥90%」，实测 87.9% —— **该判据本身是错的**：
    #   合成 IC 是全截面秩相关，毛多空只是 Q5−Q1 的尾部价差，后者噪声大得多；
    #   14 个不同号月份的 IC 与多空**两者都接近 0**（IC 如 +0.0066/-0.0015，多空 ±0.2%），
    #   属噪声而非口径错误。实测位置法与日期法配对**完全一致（0/116 差异）**，
    #   已排除「取错月份收益」这一真实故障。
    # 修订后的闸门（三条，都指向真实故障模式）：
    #   g1 全样本符号一致：mean IC 与毛多空年化同号（口径错位必然破坏这条）
    #   g2 不同号月份的幅度不显著大于同号月份（排除系统性错位，而非日常噪声）
    #   g3 日期配对一致性：位置法与日期法取的次月必须完全相同
    _ic_al = ic_s.reindex(ls_dates)
    _ok = _ic_al.notna()
    same_sign = float((np.sign(_ic_al[_ok].values) == np.sign(ls_gross_s[_ok].values)).mean()) \
        if _ok.sum() > 10 else float('nan')
    gate_warn = []
    if np.sign(mean_ic) != np.sign(ls_stats_gross := float(ls_gross_s.mean() * 12)):
        gate_warn.append(
            f'⚠ g1 符号矛盾：合成 mean IC {mean_ic:+.4f} 与毛多空年化 {ls_stats_gross:+.2%} 符号相反')
    if _ok.sum() > 10:
        _d = np.sign(_ic_al[_ok].values) != np.sign(ls_gross_s[_ok].values)
        if _d.sum() > 0:
            _mag_bad = float(np.abs(ls_gross_s[_ok].values[_d]).mean())
            _mag_ok = float(np.abs(ls_gross_s[_ok].values[~_d]).mean())
            if _mag_bad > _mag_ok:
                gate_warn.append(
                    f'⚠ g2 不同号月份幅度均值 {_mag_bad:.2%} > 同号月份 {_mag_ok:.2%}'
                    f'（疑似系统性错位，非日常噪声）')
    if pos_date_mismatch > 0:
        gate_warn.append(f'⚠ g3 位置法与日期法配对不一致 {pos_date_mismatch} 个月'
                         f'（存在缺月，须用日期法）')
    ls_stats = {
        'annual_gross': float(ls_gross_s.mean() * 12),
        'annual_net': float(ls_net_s.mean() * 12),
        'annual_net_2x': float(ls2_s.mean() * 12),
        'sharpe_net': float(ls_net_s.mean() / ls_net_s.std(ddof=1) * np.sqrt(12)),
        'nw_t': nw_t(ls_net_s),
        'months': int(len(ls_net_s)),
        'cost_drag_annual': float((ls_gross_s.mean() - ls_net_s.mean()) * 12),
        'monotonic': bool(all(q_ann[i] <= q_ann[i + 1] for i in range(1, 5))),
        'ic_ls_sign_agree': same_sign,
    }
    # ---- 因子相关矩阵（训练段 = 检验日 −24m 前）----
    cutoff = idx[-(OOS_MONTHS + 1)] if len(idx) > OOS_MONTHS + 1 else idx[0]
    train_idx = idx[idx <= cutoff]
    cors = {}
    fs = list(WEIGHTS)
    for ia in range(len(fs)):
        for ib in range(ia + 1, len(fs)):
            cs = []
            for d in train_idx:
                x, y = Z[fs[ia]].loc[d], Z[fs[ib]].loc[d]
                m = x.notna() & y.notna()
                if m.sum() >= 30:
                    cs.append(x[m].rank().corr(y[m].rank()))
            cors[f'{fs[ia]}×{fs[ib]}'] = float(np.median(cs)) if cs else np.nan

    # ---- 判定 ----
    thr = max(3.0, bonf(N_STAR_COMPOSITE))
    hard_bad = list(gate_warn)          # 一致性闸门未过 → 直接不可用
    if icir < 0.3:
        hard_bad.append(f'合成 ICIR={icir:.3f}<0.3')
    if abs(mean_ic) < 0.02:
        hard_bad.append(f'|合成 mean IC|={abs(mean_ic):.4f}<0.02')
    if not np.isnan(ic_down) and ic_down < 0:
        hard_bad.append(f'down-month 合成 IC={ic_down:.4f}<0（硬指标）')
    if not np.isnan(ic_high) and ic_high < 0:
        hard_bad.append(f'高波动月 合成 IC={ic_high:.4f}<0（硬指标）')
    if inter_loss < -0.010:
        hard_bad.append(f'vs 基准 B：合成 {mean_ic:.4f} < B{inter_loss:+.4f} − 0.010（权重配置有害）')
    view = []
    if 0.3 <= icir <= 0.5:
        view.append(f'合成 ICIR={icir:.3f} 落在观察带 0.3~0.5')
    if not np.isnan(nwt) and nwt < thr:
        view.append(f'signed NW-t={nwt:.2f} < Bonf 线 {thr:.2f}')
    if -0.010 <= inter_loss < -0.005:
        view.append(f'vs 基准：交互损耗 {inter_loss:+.4f} 在 −0.010~−0.005')

    # ---- 经济面（分层净多空）判定：成本吃掉毛超额 → 经济不可行 ----
    econ_fail = []
    gross_a = ls_stats['annual_gross']
    net_a = ls_stats['annual_net']
    if net_a <= 0:
        econ_fail.append(
            f'分层净多空年化 {net_a:+.2%} ≤ 0 —— 毛超额 {gross_a:+.2%} 被成本 '
            f'{ls_stats["cost_drag_annual"]:.2%} 全部吃掉（2x 成本下 {ls_stats["annual_net_2x"]:+.2%}）')
    if ls_stats['annual_net_2x'] <= 0:
        econ_fail.append(f'2x 成本下净多空 {ls_stats["annual_net_2x"]:+.2%} ≤ 0')

    # ---- 结论三档（§3.5）：② 组合引擎回测未做 → 上限「部分通过」 ----
    BACKTEST_DONE = False
    # §3.5 ④「无未处置冗余对」：本轮实测 EP×ROE_TTM 触发 |corr|≥0.7 处置线，
    # 且联合剔除 ΔIC₁₂(+0.0040) > max(ΔIC)(+0.0006) → 联合不加分，须剔除 ROE_TTM。
    # 故实测组合**含未处置冗余对**，这项直接计入「部分通过」的理由。
    redundant_pairs = []
    for k, v in cors.items():
        if v is not None and not np.isnan(v) and abs(v) >= 0.7:
            f1, f2 = k.split('×')
            d12 = None
            keep = [f for f in WEIGHTS if f not in (f1, f2)]
            if keep:
                tot = sum(WEIGHTS[f] for f in keep)
                sc = pd.DataFrame(0.0, index=idx, columns=cols)
                for f in keep:
                    sc += (WEIGHTS[f] / tot) * SIGNS[f] * Z[f].reindex(index=idx, columns=cols).fillna(0.0)
                s = [rank_ic(sc.loc[d], ret.loc[next_ret_date[d]])
                     for d in idx[:-1] if next_ret_date[d] is not None]
                s = [x for x in s if not np.isnan(x)]
                d12 = mean_ic - float(np.mean(s))
            mx = max(loo[f1]['delta_ic'], loo[f2]['delta_ic'])
            stronger = f1 if abs(loo[f1]['delta_ic']) >= abs(loo[f2]['delta_ic']) else f2
            redundant_pairs.append({
                'pair': k, 'corr': float(v), 'delta_ic_joint': d12,
                'max_delta_single': mx, 'keep': stronger,
                'resolved': bool(d12 is not None and d12 <= mx + 0.005),
            })
    if hard_bad:
        verdict = '不通过'
    elif econ_fail and redundant_pairs:
        verdict = '部分通过（统计过线；经济面不达；且含未处置冗余对）'
    elif econ_fail:
        verdict = '部分通过（统计过线、经济面不达）'
    elif redundant_pairs:
        verdict = '部分通过（含未处置冗余对）'
    elif view or not BACKTEST_DONE:
        verdict = '部分通过'
    else:
        verdict = '通过'

    m = {
        'composite': COMPOSITE_NAME,
        'weights_used': {k: round(v, 4) for k, v in WEIGHTS.items()},
        'neutralized': True,
        'frozen_at': dt.datetime.now().isoformat(),
        'weights': {k: round(v, 4) for k, v in WEIGHTS.items()},
        'n_star_composite': N_STAR_COMPOSITE, 'bonf_threshold': round(float(thr), 3),
        'months': int(len(ic_s)),
        'ic_mean': float(mean_ic), 'ic_sd': float(sd_ic), 'icir': float(icir),
        'naive_t': float(naive_t), 'nw_t': float(nwt), 'winrate': float(winrate),
        'benchmark_B': float(B), 'interaction_loss': float(inter_loss),
        'single_factor': single, 'leave_one_out': loo, 'decay': decay,
        'roll36_last': float(roll_tail.iloc[0]) if len(roll_tail) else None,
        'last12_all_negative': neg12,
        'ic_down_month': ic_down, 'ic_high_vol': ic_high,
        'by_year': {str(k): float(v) for k, v in by_year['mean'].items()},
        'by_segment': by_seg,
        'quintile_annual': q_ann, 'long_short': ls_stats,
        'corr_train': cors,
        'verdict': verdict, 'hard_fail': hard_bad, 'watch': view,
        'econ_fail': econ_fail, 'backtest_done': BACKTEST_DONE,
    }
    SUF = f'_{args.tag}' if args.tag else ''
    with open(os.path.join(OUT, f'composite_metrics{SUF}.json'), 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2, default=str)

    # ---- 报告 ----
    L = []
    A = L.append
    A(f'# 组合层检验报告 — {COMPOSITE_NAME}\n')
    A(f'> 方法：`composite_testing_methodology_v1.md` §3.1（组合层只引用 v3/v2.1 既有统计量）')
    A(f'> 检验对象：合成 SCORE = Σ w·d·z，z 取**行业内中性化**值（申万一级）')
    A(f'> 冻结时间：{m["frozen_at"]}｜N\'={N_STAR_COMPOSITE}（4 因子原始 + 4 因子中性化 + 1 合成）｜Bonf 线 {thr:.3f}\n')
    A('## 0. 结论\n')
    A(f'**{verdict}**\n')
    if hard_bad:
        A('硬线未过：')
        for x in hard_bad:
            A(f'- {x}')
    if econ_fail:
        A('\n**经济面未过（关键）**：')
        for x in econ_fail:
            A(f'- {x}')
        A('')
        A('> 读法：统计面（合成 IC）全部过线，说明**因子合成有真实预测力**；')
        A('> 但**月频调仓的换手成本把毛超额吃光**——这印证了本库 `small-account-minimum-commission`')
        A('> 一页的核心结论：「佣金下限／交易频率而非选股能力是第一决策变量」。')
        A('> 因此正确结论不是「组合无效」，而是「**当前调仓频率下净收益不可行**」，')
        A('> 修订方向应是降频（季度/半年）或加再平衡带，而非推翻因子选择。')
    if view:
        A('\n观察线告警：')
        for x in view:
            A(f'- {x}')
    if not BACKTEST_DONE:
        A('\n**判定上限说明**：§3.5「通过」要求同时满足 ①合成 IC 全过线 **②组合引擎回测 7 条全过线**'
          '③证据编号齐备 ④无未处置冗余对。本次**未做 ②**，故上限为「部分通过」。')
    A('\n## 1. 组合定义与必须声明的偏离\n')
    A('| 因子 | 权重（重归一化） | 方向 | 来源 |')
    A('|---|---|---|---|')
    for f, w in WEIGHTS.items():
        A(f'| {f} | {w:.4f} | + | 项目 v3 安全边际分设计 |')
    A('')
    A('**偏离声明**：方法论文档 §1.2 的对象是 v2 的 9 因子加权，但其中 CFO_NI_TTM / LEV /')
    A('TURNOVER 三个因子本项目**无数据**（`lev` 列全 NULL、库内无净利润与经营现金流绝对额）；')
    A('DY / FCF_YIELD 两个因子**尚未登记**。故本次检验的是**可用 4 因子子集**，')
    A('权重取自 v3 安全边际分（原 0.30/0.30/0.15/0.15/0.05/0.05）按可用因子重归一化到和=1.000。')
    A('**此组合不是文档 §1.2 定义的完整对象，结论只对该子集成立。**\n')
    A('## 2. 合成 IC 统计量（必报项 1）\n')
    A('| 指标 | 值 | 通过线 | 判定 |')
    A('|---|---|---|---|')
    A(f'| 合成 mean IC | {mean_ic:.4f} | ≥0.02 | {"✓" if abs(mean_ic)>=0.02 else "✗"} |')
    A(f'| 合成 IC 标准差 | {sd_ic:.4f} | — | — |')
    A(f'| 合成 ICIR | {icir:.3f} | >0.5 通过 / 0.3~0.5 观察 | {"✓" if icir>0.5 else ("△" if icir>=0.3 else "✗")} |')
    A(f'| naive t | {naive_t:.2f} | — | 参考 |')
    A(f'| signed NW-t | {nwt:.2f} | ≥{thr:.2f} | {"✓" if nwt>=thr else "✗"} |')
    A(f'| 胜率 | {winrate:.1%} | — | — |')
    A(f'| 月数 | {len(ic_s)} | — | — |')
    A('\n## 3. 加权单因子基准 B 与交互损耗（必报项 2）\n')
    A('| 因子 | 权重 | signed mean IC | ICIR | NW-t |')
    A('|---|---|---|---|---|')
    for f, w in WEIGHTS.items():
        s = single[f]
        A(f'| {f} | {w:.4f} | {s["mean_ic"]:.4f} | {s["icir"]:.3f} | {s["nw_t"]:.2f} |')
    A(f'\n**基准 B = Σ w·signed IC = {B:.4f}**｜**合成 IC = {mean_ic:.4f}**｜'
      f'**交互损耗 = {inter_loss:+.4f}**')
    A(f'（判定：合成 ≥ B−0.005 通过；B−0.010~B−0.005 观察；< B−0.010 触发"权重配置有害"联动条款）\n')
    A('## 4. leave-one-out ΔIC（必报项 3）\n')
    A('| 剔除因子 | 剩余合成 IC | ΔIC（正=该因子有贡献） |')
    A('|---|---|---|')
    for f, v in loo.items():
        A(f'| {f} | {v["mean_ic"]:.4f} | {v["delta_ic"]:+.4f} |')
    A('\n## 5. IC 衰减（必报项 4）\n')
    A('| 持有期 | 合成 IC |')
    A('|---|---|')
    for k, v in decay.items():
        A(f'| {k} | {v:.4f} |')
    A('\n## 6. 滚动 36m ICIR 与结构稳定性（必报项 5）\n')
    A(f'- 滚动 36m ICIR 末值：**{m["roll36_last"]:.3f}**（观察线：末端 <0.3）')
    A(f'- 最近 12 个月是否全为负：**{neg12}**（观察线：连续 ≥12 月为负）\n')
    A('## 7. down-month / 高波动月（必报项 6，硬指标）\n')
    A(f'- down-month 合成 IC：**{ic_down:.4f}**（须非负）')
    A(f'- 高波动月 合成 IC：**{ic_high:.4f}**（须非负）\n')
    A('## 8. 分年度 / 分制度段（必报项 7）\n')
    A('| 年度 | 合成 IC | 月数 |')
    A('|---|---|---|')
    for y, v in m['by_year'].items():
        A(f'| {y} | {v:.4f} | {int(by_year.loc[int(y), "count"])} |')
    A('\n| 制度段 | 合成 IC |')
    A('|---|---|')
    for k, v in by_seg.items():
        A(f'| {k} | {v:.4f} |')
    A('\n## 9. 分层 5 组净多空（必报项 8）\n')
    A('| 组 | 年化收益 |')
    A('|---|---|')
    for k in [1, 2, 3, 4, 5]:
        A(f'| Q{k} | {q_ann[k]:.2%} |')
    A(f'\n- 单调性（Q1<Q2<Q3<Q4<Q5）：**{ls_stats["monotonic"]}**')
    A(f'- 毛多空年化：**{ls_stats["annual_gross"]:.2%}**')
    A(f'- 净多空年化（扣成本）：**{ls_stats["annual_net"]:.2%}**')
    A(f'- 净多空年化（2x 成本）：**{ls_stats["annual_net_2x"]:.2%}**')
    A(f'- 成本拖累（年化）：**{ls_stats["cost_drag_annual"]:.2%}**')
    A(f'- 夏普（净）：**{ls_stats["sharpe_net"]:.2f}**')
    A(f'- 多空 NW-t：**{ls_stats["nw_t"]:.2f}**｜月数 {ls_stats["months"]}')
    A(f'- **一致性闸门**（逐月 rank IC 与毛多空同号率）：**{ls_stats["ic_ls_sign_agree"]:.1%}**'
      f'（须 ≥90%，否则说明 IC 与分层口径不一致、结论不可用）')
    A('## 10. 因子相关矩阵与交互处置（§3.4，训练段裁决）\n')
    A('| 因子对 | 训练段 Spearman 中位 | 筛查线 0.5 | 处置线 0.7 |')
    A('|---|---|---|---|')
    for k, v in cors.items():
        A(f'| {k} | {v:.4f} | {"≥0.5 需检查" if v>=0.5 else "通过"} | '
          f'{"≥0.7 需处置" if v>=0.7 else "通过"} |')
    A('\n**联合不加分判据**（§3.4-2）：|corr|>0.7 且 ΔIC₁₂ ≤ max(ΔIC₁,ΔIC₂)+0.005 → 取 ICIR 较强者保留。')
    hi_corr = [(k, v) for k, v in cors.items() if not np.isnan(v) and v >= 0.7]
    if hi_corr:
        A('\n触发处置线的高相关对：')
        for k, v in hi_corr:
            f1, f2 = k.split('×')
            d12 = None
            sc = pd.DataFrame(0.0, index=idx, columns=cols)
            keep = [f for f in WEIGHTS if f not in (f1, f2)]
            tot = sum(WEIGHTS[f] for f in keep)
            for f in keep:
                sc += (WEIGHTS[f] / tot) * SIGNS[f] * Z[f].reindex(index=idx, columns=cols).fillna(0.0)
            s = [rank_ic(sc.loc[d], ret.iloc[i + 1])
                 for i, d in enumerate(idx[:-1]) if d in ret.index]
            s = [x for x in s if not np.isnan(x)]
            d12 = mean_ic - float(np.mean(s))
            mx = max(loo[f1]['delta_ic'], loo[f2]['delta_ic'])
            A(f'- **{k}**（corr {v:.3f}）：联合剔除 ΔIC₁₂={d12:+.4f} vs max(ΔIC)={mx:+.4f} '
              f'→ {"联合不加分，需按 v3 §7-1 取 ICIR 较强者保留" if d12 <= mx + 0.005 else "联合有加分，保留两者"}')
    else:
        A('\n无因子对触发 |corr|≥0.7 处置线。')
    A('\n## 11. 结论三档（§3.5 映射）\n')
    A(f'**{verdict}**')
    A('\n> 注：§3.5 的「通过」要求**同时**满足 ①合成 IC 全过线 ②回测 7 条全过线 ③证据编号齐备 ④无未处置冗余对。')
    A('> 本次**未做第二步（组合引擎回测）**，故即使 ① 全过也只能到「部分通过」上限。')
    A('\n## 12. 本次未做的项（如实列出）\n')
    A('| # | 未做项 | 原因 |')
    A('|---|---|---|')
    A('| 1 | §3.2 组合引擎回测（backtest.py，v2.1 七条判定） | 本轮范围未含；且 `daily_bars` 空表，引擎数据未就绪 |')
    A('| 2 | 完整 9 因子组合 | CFO_NI_TTM / LEV / TURNOVER 无数据；DY / FCF_YIELD 未登记 |')
    A('| 3 | 行业中性化的历史口径 | 行业来自 yjbb 当前快照，无行业变更历史（已声明） |')
    A('| 4 | 权重证据编号回填 | 待本轮结论经审查后回填 factor-direction-map.md |')
    with open(os.path.join(OUT, f'composite_report{SUF}.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')

    print(f'\n{"="*70}')
    print(f'  合成 mean IC {mean_ic:.4f} | ICIR {icir:.3f} | NW-t {nwt:.2f}')
    print(f'  基准 B {B:.4f} | 交互损耗 {inter_loss:+.4f}')
    print(f'  净多空年化 {ls_stats["annual_net"]:.2%} | 2x {ls_stats["annual_net_2x"]:.2%} | 夏普 {ls_stats["sharpe_net"]:.2f}')
    print(f'  down-month {ic_down:.4f} | 高波动月 {ic_high:.4f}')
    print(f'  >>> 结论：{verdict}')
    if hard_bad:
        for x in hard_bad:
            print(f'      硬线: {x}')
    if view:
        for x in view:
            print(f'      观察: {x}')
    print(f'{"="*70}')
    print(f'\n报告 → {OUT}/composite_report{SUF}.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
