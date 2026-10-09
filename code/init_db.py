# -*- coding: utf-8 -*-
"""
本地股票数据库 — 建库脚本 (init_db.py)
=========================================
SQLite 数据库: G:/股市探究/quant-investing/data/quant.db

表结构:
  stock_master      股票主表 (代码/名称/行业/上市日/是否退市)
  daily_bars        日线行情 (OHLCV, raw)
  quarterly_fin     季度财务 (yjbb+zcfz 合并, TTM 由调用方算)
  valuation_daily   估值历史日频 (PE_TTM/PB_MRQ/总市值/收盘)
  dividends         分红送转记录
  mcap_snapshot     市值快照 (腾讯qt, 每日)
  meta_updates      更新日志 (每次运行记录/行数/来源/状态)

用法: D:/pyh/python.exe -E init_db.py   (幂等, 可重复执行)
"""
import os
import sqlite3
import datetime

DB_PATH = r'G:/股市探究/quant-investing/data/quant.db'


SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_master (
    code        TEXT PRIMARY KEY,        -- 6位代码
    name        TEXT NOT NULL,           -- 最新简称
    industry    TEXT,                    -- 东财行业 (有则填)
    is_st       INTEGER DEFAULT 0,       -- 1=ST/退市
    delisted    INTEGER DEFAULT 0,       -- 1=已退市
    updated_at  TEXT                     -- 最近更新时间
);

CREATE TABLE IF NOT EXISTS daily_bars (
    code    TEXT NOT NULL,
    date    TEXT NOT NULL,               -- YYYY-MM-DD
    open    REAL, high REAL, low REAL, close REAL,
    volume  REAL,
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS quarterly_fin (
    code        TEXT NOT NULL,
    report_date TEXT NOT NULL,           -- 报告期 YYYY-MM-DD
    notice_date TEXT,                    -- 公告日期 (yjbb口径=首次披露日, 已验证)
    eps         REAL,                    -- 每股收益 (TTM 由调用方算)
    bps         REAL,                    -- 每股净资产
    roe         REAL,                    -- 净资产收益率(%)
    cfps        REAL,                    -- 每股经营现金流
    gpm         REAL,                    -- 销售毛利率(%)
    lev         REAL,                    -- 资产负债率(%)
    PRIMARY KEY (code, report_date)
);

CREATE TABLE IF NOT EXISTS valuation_daily (
    code       TEXT NOT NULL,
    date       TEXT NOT NULL,
    pe_ttm     REAL,                     -- PE(TTM)
    pe_lar     REAL,                     -- PE(静态)
    pb_mrq     REAL,                     -- PB(最新季度)
    total_mcap REAL,                     -- 总市值(元)
    close      REAL,
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS dividends (
    code        TEXT NOT NULL,
    report_date TEXT NOT NULL,           -- 分红所属报告期
    ex_date     TEXT,                    -- 除权除息日
    cash_per10  REAL,                    -- 每10股派现(含税,元)
    progress    TEXT,                    -- 方案进度 (已过滤"实施分配")
    PRIMARY KEY (code, report_date)
);

CREATE TABLE IF NOT EXISTS mcap_snapshot (
    code    TEXT NOT NULL,
    date    TEXT NOT NULL,
    mcap_yi REAL,                        -- 总市值(亿元)
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS meta_updates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name  TEXT NOT NULL,
    action      TEXT NOT NULL,           -- FULL/INCR/CHECK
    rows_before INTEGER,
    rows_after  INTEGER,
    source      TEXT,
    status      TEXT,                    -- OK/FAIL
    message     TEXT,
    ts          TEXT NOT NULL            -- 运行时间
);
"""


def init_db(verbose=True):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    if verbose:
        print(f'[init_db] 数据库就绪: {DB_PATH}')
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        for (t,) in cur.fetchall():
            n = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
            print(f'  - {t}: {n} 行')
    conn.close()
    return DB_PATH


if __name__ == '__main__':
    init_db()
