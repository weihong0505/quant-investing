# -*- coding: utf-8 -*-
"""
回测引擎 backtest.py
====================
按《回测工程规范 v2.1》实现（MImo 两轮审查定稿）。
规范引用：本文件每个关键逻辑标注 [规范 §x.y] 出处。
状态标注：审批=docs/factor_docs/backtest_engineering_spec_v2.1.md（MImo 两轮审查定稿）；检验=金样本 test_golden_samples.py 实跑 103/103 PASS（2026-08-22，合成数据手算对账——仅验证算术正确性，非策略验证，见 M4）

核心设计（双口径铁律 [§2.1]）：
  - 信号/收益层：hfq（总收益口径，含分红再投）
  - 执行/估值/成本层：raw（成交价、股数、整手、现金、税费金额、涨跌停判定）

引擎是纯逻辑层，不直接调 akshare。数据由 data_fetcher.py 提供，
标准输入格式见各 run() 参数说明。

成本模型 [SOP §7 附录A]：
  - 佣金 万2.5 双边，最低 5 元/笔
  - 印花税 卖出，时变 [§A.4]：2023-08-28 前千1、之后万5
  - 过户费 万0.1 双边
  - 滑点 按市值四档 5/10/20/30bp 单边 [§A.2]

执行规则 [§3.3 / SOP §A.3]：
  - T 日收盘信号 → T+1 开盘价成交（raw）
  - 一字涨停不买、一字跌停不卖、停牌顺延 5 日；复牌首日跳空 >20% 直接放弃
  - 免检白名单 [§2.2 M2]：科创板/创业板新股上市前 5 个交易日（2019-07-22/2020-08-24 起）、
    主板 2023-02-17 后新股前 5 日、北交所新股首日、恢复上市首日、退市整理期首日 → 跳过涨跌停判定
  - 买入整手 100 股；卖出可零股一次性清仓
  - 单笔买入 <2 万元跳过（5 元最低佣金盈亏平衡点）
  - 首期净值从首次 T+1 开盘起算 [§3.2 M7]

绩效与换手 [§3.4 / §3.6 / §3.7]：
  - 年化收益按实际日期跨度（365.25/间隔天数），不假设严格月度等间隔
  - 可选基准对比（benchmark_nav）：超额年化、超额夏普、相对回撤、跟踪误差、信息比率
  - 换手双列：目标换手 Σ|Δw|（对照）+ 实际单边换手（月内实际成交金额/2 ÷ 月末净值）
  - 月末持仓快照 positions_history（code→股数），与 trades 对账一致
"""
import bisect
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ============================================================
# 常量与规则表 [§2.2]
# ============================================================

STAMP_DUTY_SWITCH = pd.Timestamp('2023-08-28')  # 印花税减半生效日 [§A.4]

# 涨跌停幅度矩阵 [§2.2]：(板块, 起止)
LIMIT_RULES = [
    ('main', 0.10, pd.Timestamp.min, pd.Timestamp.max),
    ('chinext', 0.10, pd.Timestamp.min, pd.Timestamp('2020-08-24')),
    ('chinext', 0.20, pd.Timestamp('2020-08-24'), pd.Timestamp.max),
    ('star', 0.20, pd.Timestamp('2019-07-22'), pd.Timestamp.max),
    ('bse', 0.30, pd.Timestamp('2021-11-15'), pd.Timestamp.max),
]

# 滑点分档（总市值，元）[§A.2]
SLIPPAGE_TIERS = [
    (500e8, 0.0005),   # ≥500亿: 5bp
    (100e8, 0.0010),   # 100~500亿: 10bp
    (30e8, 0.0020),    # 30~100亿: 20bp
    (0.0, 0.0030),     # <30亿: 30bp
]

COMMISSION_RATE = 0.00025      # 万2.5 双边
COMMISSION_MIN = 5.0           # 最低 5 元
TRANSFER_RATE = 0.00001        # 过户费 万0.1 双边
STAMP_BEFORE = 0.001           # 印花税 千1 (2023-08-28 前)
STAMP_AFTER = 0.0005           # 印花税 万5 (2023-08-28 后)
LOT_SIZE = 100                 # 一手 100 股
MIN_ORDER_VALUE = 20000.0      # 单笔买入下限（5元佣金盈亏平衡点）
SUSPEND_MAX_DAYS = 5           # 停牌顺延上限
GAP_ABANDON_THRESHOLD = 0.20   # 复牌首日跳空 >20% 放弃 [§3.3]

# 免检白名单 [§2.2 M2]：白名单内日期跳过一字板（涨跌停）判定
STAR_FREE_START = pd.Timestamp('2019-07-22')      # 科创板新股上市前 5 个交易日
CHINEXT_FREE_START = pd.Timestamp('2020-08-24')   # 创业板注册制后新股前 5 个交易日
MAIN_FREE_START = pd.Timestamp('2023-02-17')      # 主板全面注册制后新股前 5 个交易日
BSE_FREE_START = pd.Timestamp('2021-11-15')       # 北交所新股首日
NEW_LISTING_FREE_DAYS = 5
BSE_FREE_DAYS = 1


def board_of(code: str) -> str:
    """代码 → 板块 [§2.2]"""
    if code.startswith(('300', '301')):
        return 'chinext'
    if code.startswith(('688', '689')):
        return 'star'
    if code.startswith(('43', '83', '87', '88', '92')):
        return 'bse'
    return 'main'


def limit_pct(board: str, date: pd.Timestamp) -> float:
    """板块 × 时间 → 涨跌停幅度 [§2.2]"""
    for b, pct, start, end in LIMIT_RULES:
        if b == board and start <= date < end:
            return pct
    return 0.10


def round_price(p: float) -> float:
    """四舍五入到分 [§2.2]"""
    return round(p + 1e-9, 2)


def limit_prices(prev_close: float, board: str, date: pd.Timestamp,
                 is_st: bool = False) -> Tuple[float, float]:
    """返回 (涨停价, 跌停价) [§2.2]"""
    pct = 0.05 if is_st else limit_pct(board, date)
    return round_price(prev_close * (1 + pct)), round_price(prev_close * (1 - pct))


def slippage_bps(market_cap: float) -> float:
    """市值分档滑点（单边，小数）[§A.2]"""
    for cap, bps in SLIPPAGE_TIERS:
        if market_cap >= cap:
            return bps
    return 0.0030


def stamp_duty_rate(date: pd.Timestamp) -> float:
    """印花税率（时变）[§A.4]"""
    return STAMP_AFTER if date >= STAMP_DUTY_SWITCH else STAMP_BEFORE


# ============================================================
# 交易成本 [§3.4]
# ============================================================

def trade_cost(amount: float, side: str, date: pd.Timestamp,
               market_cap: float) -> float:
    """
    单笔交易成本（元）。side: 'buy' / 'sell'
    含佣金(最低5元)+印花税(仅卖出,时变)+过户费+滑点 [§A.1]
    amount: 成交金额（raw 口径）
    """
    commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
    transfer = amount * TRANSFER_RATE
    stamp = amount * stamp_duty_rate(date) if side == 'sell' else 0.0
    slippage = amount * slippage_bps(market_cap)
    return commission + transfer + stamp + slippage


# ============================================================
# 绩效指标 [§3.7]
# ============================================================

@dataclass
class Performance:
    nav: pd.Series
    monthly_returns: pd.Series
    benchmark_nav: Optional[pd.Series] = None   # 基准净值（与 nav 同频同日历）[§3.6]

    def annual_return(self) -> float:
        """几何年化收益，按实际日期跨度年化（不假设严格月度等间隔）[§3.2]"""
        if len(self.nav) < 2:
            return 0.0
        total = self.nav.iloc[-1] / self.nav.iloc[0]
        days = (self.nav.index[-1] - self.nav.index[0]).days
        if days <= 0:
            return 0.0
        return total ** (365.25 / days) - 1

    def annual_vol(self) -> float:
        return self.monthly_returns.std(ddof=1) * np.sqrt(12)

    def sharpe(self) -> float:
        vol = self.annual_vol()
        return self.annual_return() / vol if vol > 0 else 0.0

    def max_drawdown(self) -> float:
        peak = self.nav.cummax()
        return float((self.nav / peak - 1).min())

    def calmar(self) -> float:
        mdd = self.max_drawdown()
        return self.annual_return() / abs(mdd) if mdd < 0 else 0.0

    def win_rate(self) -> float:
        return float((self.monthly_returns > 0).mean())

    # ---------- 基准对比 [§3.6] ----------

    def _bench(self) -> Optional[pd.Series]:
        """基准净值对齐到本组合净值日历（同期间、同再平衡日历 [§3.6#4]）"""
        if self.benchmark_nav is None:
            return None
        b = self.benchmark_nav
        if not b.index.equals(self.nav.index):
            b = b.reindex(self.nav.index).ffill()
        return b

    @staticmethod
    def _annual_of(nav: pd.Series) -> float:
        """任意净值序列的几何年化（与 annual_return 同口径）"""
        if len(nav) < 2:
            return 0.0
        total = nav.iloc[-1] / nav.iloc[0]
        if total <= 0:
            return 0.0
        days = (nav.index[-1] - nav.index[0]).days
        return total ** (365.25 / days) - 1 if days > 0 else 0.0

    def benchmark_annual_return(self) -> float:
        """基准年化（与 annual_return 同口径，按基准自身日期跨度）"""
        if self.benchmark_nav is None:
            return 0.0
        return self._annual_of(self.benchmark_nav)

    def excess_annual_return(self) -> float:
        """超额年化 = 组合年化 − 基准年化 [§3.6#4]"""
        b = self._bench()
        return self.annual_return() - self._annual_of(b) if b is not None else 0.0

    def excess_sharpe(self) -> float:
        """超额夏普：月频超额收益 mean/std × √12（rf=0）[§3.7]"""
        b = self._bench()
        if b is None:
            return 0.0
        ex = (self.monthly_returns - b.pct_change().fillna(0.0)).dropna()
        if len(ex) < 2:
            return 0.0
        sd = ex.std(ddof=1)
        return float(ex.mean() / sd * np.sqrt(12)) if sd > 0 else 0.0

    def relative_drawdown(self) -> float:
        """相对回撤：nav/基准 相对净值的最大回撤 [§3.6]"""
        b = self._bench()
        if b is None:
            return 0.0
        rel = self.nav / b
        return float((rel / rel.cummax() - 1).min())

    def tracking_error(self) -> float:
        """跟踪误差：月频超额收益的年化波动 [§3.6#4]"""
        b = self._bench()
        if b is None:
            return 0.0
        ex = (self.monthly_returns - b.pct_change().fillna(0.0)).dropna()
        return float(ex.std(ddof=1) * np.sqrt(12)) if len(ex) >= 2 else 0.0

    def information_ratio(self) -> float:
        """信息比率 = 超额年化 / 跟踪误差 [§3.6#4]"""
        b = self._bench()
        if b is None:
            return 0.0
        te = self.tracking_error()
        return self.excess_annual_return() / te if te > 0 else 0.0

    def summary(self, name: str = 'strategy') -> pd.Series:
        out = {
            'annual_return': self.annual_return(),
            'annual_vol': self.annual_vol(),
            'sharpe': self.sharpe(),
            'max_drawdown': self.max_drawdown(),
            'calmar': self.calmar(),
            'win_rate': self.win_rate(),
        }
        if self.benchmark_nav is not None:
            out.update({
                'excess_annual_return': self.excess_annual_return(),
                'excess_sharpe': self.excess_sharpe(),
                'relative_drawdown': self.relative_drawdown(),
                'tracking_error': self.tracking_error(),
                'information_ratio': self.information_ratio(),
            })
        return pd.Series(out, name=name)


# ============================================================
# 回测引擎
# ============================================================

@dataclass
class Position:
    """持仓（raw 空间：真实股数与成本）[§3.3]"""
    shares: int = 0
    avg_cost: float = 0.0


@dataclass
class TradeRecord:
    date: pd.Timestamp
    code: str
    side: str
    shares: int
    price: float
    amount: float
    cost: float
    reason: str = ''


@dataclass
class BacktestResult:
    nav: pd.Series
    monthly_returns: pd.Series
    trades: List[TradeRecord]
    turnover: pd.Series
    perf: Performance
    positions_history: List[pd.Series]
    # 合成的 hfq 总收益净值曲线与日收益（绩效口径；raw 净值仅对账）
    nav_hfq: Optional[pd.Series] = None
    daily_returns: Optional[pd.Series] = None
    # 实际换手（单边，月频）：月内 trades 实际成交金额 ÷ 月末组合净值 [§3.4]
    actual_turnover: Optional[pd.Series] = None
    turnover_annualized: float = 0.0            # 年化实际换手 = 12 × 月均（C4 缺口7）
    benchmark_nav: Optional[pd.Series] = None   # 基准净值（C4 缺口3）


class BacktestEngine:
    """
    月度调仓、T+1 开盘执行的回测引擎。

    输入约定：
      - calendar: pd.DatetimeIndex 交易日历（升序）
      - signals: DataFrame，行=再平衡日（月末最后交易日），
                 列=股票代码，值=目标权重（未列出的股票权重 0）
      - prices_raw: DataFrame，行=交易日，列=代码，值=不复权开盘价/收盘价字典
                    （传两个：prices_raw_open, prices_raw_close）
      - prices_hfq: DataFrame，行=交易日，列=代码，值=后复权收盘价（算收益）
      - market_cap: DataFrame，行=交易日，列=代码，值=总市值（滑点分档）
      - tradable: DataFrame bool，行=交易日，列=代码，True=当日可交易
                  （停牌 False；涨跌停由引擎按开盘价判定）
      - st_flags: DataFrame bool，行=交易日，列=代码，True=ST（5% 幅度）
      - initial_cash: 初始资金
    """

    def __init__(self, calendar, prices_raw_open, prices_raw_close,
                 prices_hfq, market_cap, tradable, st_flags,
                 initial_cash=1_000_000.0,
                 cash_div: Optional[pd.DataFrame] = None,
                 share_ratio: Optional[pd.DataFrame] = None,
                 list_dates: Optional[pd.Series] = None,
                 limit_free_dates: Optional[Dict[str, List[pd.Timestamp]]] = None):
        """
        cash_div: DataFrame, index=交易日, columns=代码, values=每股现金分红(元)
                  （除息日现金入账 [§2.3]；不提供则分红缺失，报告声明）
        share_ratio: DataFrame, index=交易日, columns=代码,
                     values=送转股数倍率（10送10=2.0；不提供则送转缺失）
        list_dates: Series, index=代码, values=上市日。免检白名单 [§2.2 M2] 用；
                    不提供则取该股首个有效 raw 收盘价日作为上市日
        limit_free_dates: dict code→日期清单，显式免检白名单
                    （恢复上市首日、退市整理期首日等，由数据层提供）
        """
        self.calendar = pd.DatetimeIndex(calendar).sort_values()
        self.dates = self.calendar
        self.px_open = prices_raw_open
        self.px_close = prices_raw_close
        self.px_hfq = prices_hfq
        # 前向填充：停牌/缺失日沿用最近有效价（供收益合成；停牌日收益按 0 计）
        self.px_close_ff = prices_raw_close.ffill()
        self.px_hfq_ff = prices_hfq.ffill()
        self.mcap = market_cap
        self.tradable = tradable
        self.st_flags = st_flags
        self.cash_div = cash_div
        self.share_ratio = share_ratio
        self.list_dates = list_dates
        self.limit_free_dates = limit_free_dates or {}
        self._mcap_warned: set = set()
        self.verbose = False
        self.initial_cash = initial_cash
        self.codes = list(prices_raw_open.columns)
        # 上市日索引（免检白名单 [§2.2 M2] 用）：
        # 优先显式 list_dates，否则取首个有效 raw 收盘价日（= 上市日）
        self._listing_idx: Dict[str, Optional[int]] = {}
        for c in self.codes:
            ld = None
            if list_dates is not None and c in list_dates.index \
                    and pd.notna(list_dates[c]):
                ld = pd.Timestamp(list_dates[c])
            else:
                valid = self.px_close[c].dropna()
                if len(valid):
                    ld = valid.index[0]
            if ld is not None:
                pos = int(self.dates.searchsorted(ld))
                self._listing_idx[c] = min(pos, len(self.dates) - 1)
            else:
                self._listing_idx[c] = None
        self._validate()

    def _validate(self):
        for df in (self.px_open, self.px_close, self.px_hfq, self.mcap,
                   self.tradable, self.st_flags):
            missing = set(self.codes) - set(df.columns)
            if missing:
                raise ValueError(f'列缺失: {list(missing)[:5]}...')
        assert self.px_open.index.equals(self.px_close.index), 'open/close 索引不一致'
        assert self.calendar.is_monotonic_increasing, '日历必须升序'
        assert self.px_hfq.index.equals(self.px_close.index), 'hfq 与 close 索引不一致' 

    # ---------- 工具 ----------

    def _idx(self, date) -> int:
        """日期 → 日历位置"""
        return self.dates.get_loc(date)

    def _next_trading_day(self, date) -> Optional[pd.Timestamp]:
        i = self._idx(date)
        return self.dates[i + 1] if i + 1 < len(self.dates) else None

    def _open_price(self, date, code) -> Optional[float]:
        v = self.px_open.at[date, code]
        return float(v) if pd.notna(v) else None

    def _is_st(self, date, code) -> bool:
        return bool(self.st_flags.at[date, code])

    def _is_tradable(self, date, code) -> bool:
        return bool(self.tradable.at[date, code])

    def _mcap_of(self, date, code) -> float:
        """市值缺失按最保守档（30bp）计滑点，verbose 模式打印告警 [§A.2]"""
        v = self.mcap.at[date, code]
        if pd.notna(v):
            return float(v)
        if self.verbose and code not in self._mcap_warned:
            self._mcap_warned.add(code)
            print(f'[warn] market_cap missing {code} @ {date.date()} '
                  f'-> slippage 30bp (most conservative tier)')
        # 缺失市值按最保守档 30bp：-1.0 不满足任何滑点档位（>= 0.0），
        # slippage_bps 落到末档 0.0030。注意不能返回 0.0——0.0 >= 0.0 命中
        # (0.0, 0.0030) 档之前的 (30e8, 0.0020) 判断链，实际得到 20bp。
        return -1.0

    def is_limit_free(self, code: str, date: pd.Timestamp) -> bool:
        """免检白名单 [§2.2 M2]：白名单内日期跳过一字板（涨跌停）判定。

        - 显式白名单（limit_free_dates）：恢复上市首日、退市整理期首日等
        - 新股规则：科创板/创业板上市前 5 个交易日（2019-07-22/2020-08-24 起）、
          主板 2023-02-17 后新股前 5 日、北交所新股首日（2021-11-15 起）
        """
        if code in self.limit_free_dates and date in self.limit_free_dates[code]:
            return True
        i_list = self._listing_idx.get(code)
        if i_list is None:
            return False
        try:
            i = self._idx(date)
        except KeyError:
            return False
        days_on_board = i - i_list + 1
        if days_on_board < 1:
            return False
        board = board_of(code)
        if board == 'bse':
            return date >= BSE_FREE_START and days_on_board <= BSE_FREE_DAYS
        if board == 'star':
            return date >= STAR_FREE_START and days_on_board <= NEW_LISTING_FREE_DAYS
        if board == 'chinext':
            return date >= CHINEXT_FREE_START and days_on_board <= NEW_LISTING_FREE_DAYS
        if board == 'main':
            return date >= MAIN_FREE_START and days_on_board <= NEW_LISTING_FREE_DAYS
        return False

    # ---------- 主流程 ----------

    def run(self, signals: pd.DataFrame,
            verbose: bool = False,
            benchmark_nav: Optional[pd.Series] = None) -> BacktestResult:
        """
        回测主循环。

        signals: index=调仓日（T日，月末），columns=code，values=目标权重
        benchmark_nav: 可选基准净值（与月末净值同频同日历），用于超额指标 [§3.6]

        双口径铁律 [规范 2.1]：
          - 收益层 hfq（含分红再投）：组合日收益 = Σ 持仓权重 × hfq 日收益合成，
            持仓权重用 t-1 日 raw 收盘市值；现金按 0 收益计入（隐含于权重缺口）。
            执行日（T+1 开盘成交）按执行价 raw→hfq 换算：hfq_exec = 成交价 × 当日
            复权因子（hfq_close/raw_close），拆隔夜段（t-1 收盘→执行价，执行前持仓）
            与日内段（执行价→t 收盘，执行后持仓）；成交成本作为当日负向现金流计入，
            保证合成收益与 raw 净值对账一致。
            ⚠️ 严禁直接 Σ shares × hfq_price 合成净值（hfq 价格水平跨股不可比）。
          - 执行/估值/成本层 raw：成交价、股数、整手、税费、涨跌停判定均 raw 空间。
          - raw 净值（nav）仅作交易对账；绩效指标全部基于合成的 hfq 总收益序列。

        净值记录 [规范 3.2 M7]：
          - 首条净值在首次 T+1 开盘成交后按开盘价记录；
          - 此后每个自然月末按收盘价记录。
        """
        cash = self.initial_cash
        self.verbose = verbose
        positions: Dict[str, Position] = {}
        nav_records = {}          # raw 净值（仅交易对账用）
        turnover_records = {}
        trades: List[TradeRecord] = []
        daily_returns: Dict[pd.Timestamp, float] = {}
        positions_history: List[pd.Series] = []   # 月末持仓快照（code→股数）[§3.4]

        rebalance_dates = pd.DatetimeIndex(signals.index).sort_values()
        first_exec = self._next_trading_day(rebalance_dates[0])
        if first_exec is None:
            raise ValueError('无交易日可执行')

        # 自然月末列表（>= first_exec 的每月最后一个交易日）
        month_ends = self._month_ends_from(first_exec)
        month_end_set = set(month_ends)

        # 每个调仓日 T 对应 T+1 执行日
        pending: List[Tuple[pd.Timestamp, pd.Series]] = [
            (self._next_trading_day(t), signals.loc[t].dropna())
            for t in rebalance_dates
        ]
        pending = [(d, w) for d, w in pending if d is not None]
        prev_weights: pd.Series = pd.Series(dtype=float)
        first_done = False

        pending_iter = iter(pending)
        next_item = next(pending_iter, None)

        i0 = self._idx(first_exec)
        i1 = self._idx(month_ends[-1])
        for i in range(i0, i1 + 1):
            t = self.dates[i]
            # 执行前持仓快照（= t-1 日收盘持仓，raw 空间）
            pre_shares = {c: p.shares for c, p in positions.items() if p.shares > 0}
            cash_pre = cash
            traded_info: Dict[str, Tuple[float, pd.Timestamp]] = {}
            exec_cost = 0.0
            # 1) 执行当日到期的调仓（T+1 开盘，raw 空间）[规范 3.3]
            while next_item is not None and next_item[0] <= t:
                exec_date, target = next_item
                if verbose:
                    print(f'[rebalance] exec={exec_date.date()} '
                          f'targets={int((target > 0).sum())}')
                n0 = len(trades)
                cash, _ = self._apply_rebalance(
                    exec_date, target, positions, cash, trades, verbose)
                # 从本次追加的成交记录提取实际成交价/成交日（含顺延成交）
                for tr in trades[n0:]:
                    traded_info[tr.code] = (tr.price, tr.date)
                    exec_cost += tr.cost
                if not first_done:
                    # 首条净值在首次 T+1 开盘成交后 [规范 3.2 M7]
                    nav_records[t] = (
                        cash + self._positions_value_at_open(t, positions))
                    first_done = True
                # 换手 [规范 3.4]
                turnover_records[self._month_end_of(month_ends, t)] = \
                    self._turnover(prev_weights, target)
                prev_weights = target.copy()
                next_item = next(pending_iter, None)
            # 2) 当日公司行为（现金分红入现金 / 送转调股数，raw 空间）[规范 2.3]
            #    cash_div 只影响 raw 现金对账；hfq 收益层已含分红再投，不重复计收益
            cash = self._apply_corporate_actions(t, positions, cash)
            # 3) 收益层：持仓权重 × hfq 日收益合成（含分红再投）[规范 2.1]
            daily_returns[t] = self._compose_daily_return(
                i, pre_shares, positions, cash_pre, traded_info, exec_cost)
            # 4) 月末记录 raw 净值（对账用）+ 持仓快照 [§3.4]
            if t in month_end_set:
                nav_records[t] = cash + self._positions_value(t, positions)
                positions_history.append(pd.Series(
                    {c: p.shares for c, p in positions.items() if p.shares > 0},
                    name=t))

        nav = pd.Series(nav_records).sort_index()
        turnover = pd.Series(turnover_records).sort_index()

        # 合成 hfq 总收益序列：日收益按月复利 → 月收益 + hfq 净值曲线
        daily = pd.Series(daily_returns).sort_index()
        monthly_composed: Dict[pd.Timestamp, float] = {}
        nav_hfq_vals = {daily.index[0]: self.initial_cash}
        cum = self.initial_cash
        prev_cum = self.initial_cash
        for t, r in daily.items():
            cum *= (1.0 + r)
            if t in month_end_set:
                monthly_composed[t] = cum / prev_cum - 1.0
                prev_cum = cum
                nav_hfq_vals[t] = cum
        nav_hfq = pd.Series(nav_hfq_vals).sort_index()
        monthly = pd.Series(monthly_composed).sort_index()

        # 绩效全部基于合成的 hfq 总收益序列；raw 净值仅作交易对账
        perf = Performance(nav=nav_hfq, monthly_returns=monthly,
                           benchmark_nav=benchmark_nav)
        # 实际换手（单边，月频）[§3.4 / C4 缺口7]：月内 trades 实际成交金额 ÷ 月末净值
        actual_turnover = self._actual_turnover(month_ends, trades, nav_records)
        return BacktestResult(nav=nav, monthly_returns=monthly, trades=trades,
                              turnover=turnover, perf=perf,
                              positions_history=positions_history,
                              nav_hfq=nav_hfq, daily_returns=daily,
                              actual_turnover=actual_turnover,
                              turnover_annualized=12.0 * float(actual_turnover.mean()),
                              benchmark_nav=benchmark_nav)

    def _actual_turnover(self, month_ends, trades, nav_records) -> pd.Series:
        """实际单边换手（月频）：月内 trades 实际成交金额 ÷ 月末组合净值 [§3.4]。
        单边口径：每笔成交金额计一次（买/卖同计），与目标换手 Σ|Δw| 同量纲；
        一字板/停牌顺延放弃时实际成交 < 目标换手（C4 缺口7，修正旧实现把目标
        权重变化当实际换手、系统性高估的问题）。目标换手保留作对照列。"""
        out: Dict[pd.Timestamp, float] = {}
        for m_end in month_ends:
            if m_end not in nav_records:
                continue
            traded = sum(t.amount for t in trades
                         if self._month_end_of(month_ends, t.date) == m_end)
            nav_m = nav_records[m_end]
            out[m_end] = traded / nav_m if nav_m > 0 else 0.0
        return pd.Series(out).sort_index()
    def _apply_corporate_actions(self, date, positions: Dict[str, Position],
                                 cash: float) -> float:
        """除息日现金分红入账 + 送转股数调整 [§2.3]。返回新现金"""
        # 现金分红（每股，raw 口径）
        if self.cash_div is not None and date in self.cash_div.index:
            row = self.cash_div.loc[date]
            for code in list(positions.keys()):
                if code in row.index and pd.notna(row[code]) and row[code] > 0:
                    pos = positions[code]
                    if pos.shares > 0:
                        cash += pos.shares * float(row[code])
        # 送转股数调整
        if self.share_ratio is not None and date in self.share_ratio.index:
            row = self.share_ratio.loc[date]
            for code in list(positions.keys()):
                if code in row.index and pd.notna(row[code]) and row[code] > 1:
                    pos = positions[code]
                    if pos.shares > 0:
                        pos.shares = int(pos.shares * float(row[code]))
        return cash

    def _apply_rebalance(self, exec_date, target: pd.Series,
                         positions: Dict[str, Position], cash: float,
                         trades: List[TradeRecord], verbose=False):
        """执行单期调仓。返回 (cash, trade_count)"""
        n_trades = 0
        # ---- 卖出（先卖后买）----
        for code in list(positions.keys()):
            pos = positions[code]
            if pos.shares <= 0:
                del positions[code]
                continue
            w = target.get(code, 0.0)
            if w <= 0:
                r = self._sell_with_extension(exec_date, code, pos, cash,
                                              trades, sell_all=True, verbose=verbose)
                if r is not None:
                    cash, n_trades = r, n_trades + 1
                    del positions[code]
            else:
                # 部分减仓：目标金额 < 当前市值
                px = self._open_price(exec_date, code)
                if px is not None:
                    total_value = cash + self._positions_value(exec_date, positions)
                    target_amount = w * total_value
                    cur_amount = pos.shares * px
                    if target_amount < cur_amount - MIN_ORDER_VALUE:
                        sell_amount = cur_amount - target_amount
                        shares_to_sell = int(sell_amount / px // LOT_SIZE) * LOT_SIZE
                        if shares_to_sell > 0:
                            r = self._sell_shares(exec_date, code, pos,
                                                  shares_to_sell, cash, trades,
                                                  verbose=verbose)
                            if r is not None:
                                cash, n_trades = r, n_trades + 1

        # ---- 买入 ----
        total_value = cash + self._positions_value(exec_date, positions)
        for code, w in target.items():
            if w <= 0:
                continue
            # 执行日无开盘价（停牌/缺失）不跳过：交给 _buy_with_extension 顺延重判 [§3.3]
            target_amount = w * total_value
            pos = positions.get(code)
            cur_amount = pos.shares * self._open_price(exec_date, code) \
                if pos and self._open_price(exec_date, code) else 0.0
            buy_amount = target_amount - cur_amount
            if buy_amount < MIN_ORDER_VALUE:
                continue  # 小额跳过 [§3.3]
            r = self._buy_with_extension(exec_date, code, buy_amount, cash,
                                         trades, verbose=verbose)
            if r is not None:
                cash, bought = r
                # 持仓入账
                if code not in positions:
                    positions[code] = Position()
                positions[code].shares += bought
                n_trades += 1
        return cash, n_trades

    def _turnover(self, prev_w: pd.Series, target: pd.Series) -> float:
        """单边换手 Σ|Δw| [§3.4]"""
        codes = set(prev_w.index) | set(target.index)
        return float(sum(abs(prev_w.get(c, 0.0) - target.get(c, 0.0))
                         for c in codes))

    # ---------- 收益层：hfq 日收益合成 [规范 2.1] ----------

    def _compose_daily_return(self, i: int,
                              pre_shares: Dict[str, int],
                              positions: Dict[str, Position],
                              cash_pre: float,
                              traded_info: Dict[str, Tuple[float, pd.Timestamp]],
                              exec_cost: float) -> float:
        """收益层：组合日收益 = Σ 持仓权重 × hfq 日收益（含分红再投）[规范 2.1]

        - 权重 w 用 t-1 日 raw 收盘市值（现金按 0 收益计入，隐含于权重缺口）
        - 执行日按执行价 raw→hfq 换算：hfq_exec = 成交价 × 当日复权因子
          （hfq_close/raw_close，执行日口径），拆隔夜段（t-1 收盘→执行价，
          执行前持仓）+ 日内段（执行价→t 收盘，执行后持仓）
        - 成交成本作为当日负向现金流（-cost/NAV_pre），与 raw 净值对账一致
        - ⚠️ 严禁 Σ shares × hfq_price 合成净值：hfq 价格水平跨股不可比；
          权重一律用 raw 市值，收益一律用 hfq 相对变化
        - hfq 数据缺失的股票当日收益按 0 计
        """
        nav_pre = cash_pre
        for code, s_pre in pre_shares.items():
            c_prev = self._close_ff(code, i - 1)
            if s_pre > 0 and pd.notna(c_prev):
                nav_pre += s_pre * c_prev
        if nav_pre <= 0:
            return 0.0
        ret = 0.0
        for code in (set(pre_shares) | set(positions.keys())):
            s_pre = pre_shares.get(code, 0)
            pos = positions.get(code)
            s_post = pos.shares if pos is not None else 0
            if s_pre <= 0 and s_post <= 0:
                continue
            h_prev = self._hfq_ff(code, i - 1)
            h_now = self._hfq_ff(code, i)
            c_prev = self._close_ff(code, i - 1)
            if code in traded_info:
                # 执行日：按执行价 raw→hfq 换算后拆隔夜/日内两段
                exec_price, exec_date = traded_info[code]
                j = self._idx(exec_date)
                h_exec = self._hfq_ff(code, j)
                c_exec = self._close_ff(code, j)
                if pd.isna(h_exec) or pd.isna(c_exec) or c_exec <= 0:
                    continue  # hfq 缺失：该股当日收益按 0 计
                hfq_exec = exec_price * (h_exec / c_exec)
                # 隔夜段：t-1 收盘 → 执行价（执行前持仓）
                if s_pre > 0 and pd.notna(h_prev) and h_prev > 0 \
                        and pd.notna(c_prev) and c_prev > 0:
                    w1 = s_pre * c_prev / nav_pre
                    ret += w1 * (hfq_exec / h_prev - 1.0)
                # 日内段：执行价 → t 收盘（执行后持仓）
                if s_post > 0 and hfq_exec > 0 \
                        and pd.notna(h_now) and h_now > 0:
                    w2 = s_post * exec_price / nav_pre
                    ret += w2 * (h_now / hfq_exec - 1.0)
            else:
                # 非执行日：整日 hfq 收益（含分红再投），权重取 t-1 收盘市值
                if s_pre > 0 and pd.notna(h_prev) and h_prev > 0 \
                        and pd.notna(h_now) and h_now > 0 \
                        and pd.notna(c_prev) and c_prev > 0:
                    w = s_pre * c_prev / nav_pre
                    ret += w * (h_now / h_prev - 1.0)
        # 成本：当日负向现金流（raw 金额 / 前收净值）
        ret -= exec_cost / nav_pre
        return ret

    @staticmethod
    def _month_end_of(month_ends: List[pd.Timestamp], date) -> pd.Timestamp:
        """date 所在自然月的月末交易日（month_ends 需覆盖该月）"""
        k = bisect.bisect_left(month_ends, date)
        return month_ends[k]

    def _close_ff(self, code, i: int) -> float:
        """index i 处最近有效 raw 收盘价（前向填充；i<0 返回 NaN）"""
        if i < 0:
            return np.nan
        return float(self.px_close_ff.iloc[i][code])

    def _hfq_ff(self, code, i: int) -> float:
        """index i 处最近有效 hfq 收盘价（前向填充；i<0 返回 NaN）"""
        if i < 0:
            return np.nan
        return float(self.px_hfq_ff.iloc[i][code])

    # ---------- 执行函数（含顺延 [§3.3]）----------

    def _gap_too_large(self, date, code, k: int) -> bool:
        """顺延第 k 日（k>=1）成交前：当日开盘价 vs 停牌前最后收盘价，
        |跳空| >20% 则该次顺延放弃 [§3.3]。"""
        if k < 1:
            return False
        price = self._open_price(date, code)
        if price is None:
            return False
        last_close = self._last_close_before(date, code, exclusive=True)
        if last_close is None or last_close <= 0:
            return False
        return abs(price / last_close - 1.0) > GAP_ABANDON_THRESHOLD

    def _buy_with_extension(self, exec_date, code, amount, cash, trades,
                            verbose=False):
        """买入 + 停牌/涨停顺延 5 日。返回 (新现金, 成交股数) 或 None（放弃）"""
        d = exec_date
        for k in range(SUSPEND_MAX_DAYS + 1):
            # 复牌首日跳空 >20% 直接放弃 [§3.3]
            if self._gap_too_large(d, code, k):
                return None
            r = self._buy(d, code, amount, cash, trades, verbose)
            if r is not None:
                return r
            d = self._next_trading_day(d)
            if d is None:
                return None
        # 顺延失败：资金持有现金至下一调仓日，不重配 [§3.3]
        return None

    def _sell_with_extension(self, exec_date, code, pos, cash, trades,
                             sell_all=True, verbose=False) -> Optional[float]:
        """卖出 + 停牌/跌停顺延 5 日"""
        d = exec_date
        for k in range(SUSPEND_MAX_DAYS + 1):
            if pos.shares <= 0:
                return cash
            # 复牌首日跳空 >20% 直接放弃 [§3.3]
            if self._gap_too_large(d, code, k):
                return None
            r = self._sell(d, code, pos, cash, trades, sell_all=sell_all,
                           verbose=verbose)
            if r is not None:
                return r
            d = self._next_trading_day(d)
            if d is None:
                return None
        return None

    def _sell_shares(self, date, code, pos: Position, shares: int, cash,
                     trades, verbose=False) -> Optional[float]:
        """卖出指定股数（部分减仓）。返回新现金或 None"""
        price = self._open_price(date, code)
        if price is None or not self._is_tradable(date, code):
            return None
        # 一字跌停不卖 [§3.3]；免检白名单内跳过判定 [§2.2 M2]
        if not self.is_limit_free(code, date):
            prev_close = self._prev_close(date, code)
            if prev_close is not None:
                _, down = limit_prices(prev_close, board_of(code), date,
                                       self._is_st(date, code))
                if price <= down + 1e-9:
                    return None
        shares = min(shares, pos.shares)
        if shares <= 0:
            return None
        trade_amount = shares * price
        cost = trade_cost(trade_amount, 'sell', date, self._mcap_of(date, code))
        pos.shares -= shares
        trades.append(TradeRecord(date, code, 'sell', shares, price,
                                  trade_amount, cost, 'rebalance'))
        return cash + trade_amount - cost

    def _buy(self, date, code, amount, cash, trades,
             verbose=False):
        """买入（raw 空间）。返回 (新现金, 成交股数) 或 None（放弃）"""
        price = self._open_price(date, code)
        if price is None:
            return None  # 无开盘价（停牌/缺失）
        if not self._is_tradable(date, code):
            return None
        # 一字涨停不买 [§3.3]；免检白名单内跳过判定 [§2.2 M2]
        if not self.is_limit_free(code, date):
            prev_close = self._prev_close(date, code)
            if prev_close is not None:
                up, _ = limit_prices(prev_close, board_of(code), date,
                                     self._is_st(date, code))
                if price >= up - 1e-9:
                    return None
        shares = int(amount / price // LOT_SIZE) * LOT_SIZE  # 整手
        # 现金缓冲：交易额+成本不得超过现金，超了逐手递减 [§3.3]
        fitted = False
        for _ in range(10):
            if shares <= 0:
                return None
            trade_amount = shares * price
            cost = trade_cost(trade_amount, 'buy', date, self._mcap_of(date, code))
            if trade_amount + cost <= cash:
                fitted = True
                break
            shares -= LOT_SIZE
        if not fitted:
            return None
        trades.append(TradeRecord(date, code, 'buy', shares, price,
                                  trade_amount, cost, 'rebalance'))
        return cash - trade_amount - cost, shares

    def _sell(self, date, code, pos: Position, cash, trades,
              sell_all=True, verbose=False) -> Optional[float]:
        """卖出（raw 空间）。返回新现金或 None（未成交）"""
        price = self._open_price(date, code)
        if price is None:
            return None
        if not self._is_tradable(date, code):
            return None
        # 一字跌停不卖 [§3.3]；免检白名单内跳过判定 [§2.2 M2]
        if not self.is_limit_free(code, date):
            prev_close = self._prev_close(date, code)
            if prev_close is not None:
                _, down = limit_prices(prev_close, board_of(code), date,
                                       self._is_st(date, code))
                if price <= down + 1e-9:
                    return None
        shares = pos.shares
        trade_amount = shares * price
        cost = trade_cost(trade_amount, 'sell', date, self._mcap_of(date, code))
        pos.shares = 0
        trades.append(TradeRecord(date, code, 'sell', shares, price,
                                  trade_amount, cost, 'rebalance'))
        return cash + trade_amount - cost

    # ---------- 估值与辅助 ----------

    def _positions_value(self, date, positions: Dict[str, Position]) -> float:
        """持仓市值（raw 收盘价）[§3.3]"""
        total = 0.0
        for code, pos in positions.items():
            if pos.shares <= 0:
                continue
            px = self.px_close.at[date, code]
            if pd.notna(px):
                total += pos.shares * float(px)
            else:
                total += pos.shares * self._last_close_before(date, code)
        return total

    def _positions_value_at_open(self, date, positions: Dict[str, Position]) -> float:
        """持仓市值（raw 开盘价）[§3.2 M7 首期]"""
        total = 0.0
        for code, pos in positions.items():
            if pos.shares <= 0:
                continue
            px = self.px_open.at[date, code]
            if pd.notna(px):
                total += pos.shares * float(px)
            else:
                total += pos.shares * self._last_close_before(date, code)
        return total

    def _last_close_before(self, date, code, exclusive: bool = False) -> float:
        """date 前最近有效 raw 收盘价（exclusive=True 不含 date 当日，用于跳空判定）"""
        i = self._idx(date)
        if exclusive:
            i -= 1
        for j in range(i, -1, -1):
            v = self.px_close.iloc[j][code]
            if pd.notna(v):
                return float(v)
        return 0.0

    def _prev_close(self, date, code) -> Optional[float]:
        i = self._idx(date)
        if i == 0:
            return None
        v = self.px_close.iloc[i - 1][code]
        return float(v) if pd.notna(v) else None

    def _month_ends_from(self, start_date) -> List[pd.Timestamp]:
        """>= start_date 的每个自然月末交易日"""
        out = []
        for i, d in enumerate(self.dates):
            if d < start_date:
                continue
            if i == len(self.dates) - 1 or self.dates[i + 1].month != d.month:
                out.append(d)
        return out
