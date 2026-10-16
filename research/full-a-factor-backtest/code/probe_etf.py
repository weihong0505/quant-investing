# -*- coding: utf-8 -*-
"""probe_etf.py — 探测 ETF 日线可取的通路（东财/腾讯/新浪）"""
import sys, warnings, traceback
warnings.filterwarnings('ignore')
import akshare as ak
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')

def t(label, fn):
    try:
        d = fn()
        if d is None:
            print(f'  ✗ {label}: 返回 None'); return None
        print(f'  ✓ {label}: {len(d)} 行  列={list(d.columns)[:8]}')
        return d
    except Exception as e:
        print(f'  ✗ {label}: {type(e).__name__}: {str(e)[:90]}')
        return None

print('akshare', ak.__version__)
print('\n--- 510300 沪深300ETF ---')
t('fund_etf_hist_em(hfq)', lambda: ak.fund_etf_hist_em(symbol='510300', period='daily',
    start_date='20240101', end_date='20261009', adjust='hfq'))
t('fund_etf_hist_sina', lambda: ak.fund_etf_hist_sina(symbol='sh510300'))
t('fund_etf_spot_em', lambda: ak.fund_etf_spot_em())
print('\n--- 指数（备选基准）---')
t('stock_zh_index_daily(sh000300)', lambda: ak.stock_zh_index_daily(symbol='sh000300'))
t('stock_zh_index_daily_em(000300)', lambda: ak.stock_zh_index_daily_em(symbol='sh000300'))
t('index_zh_a_hist(000300)', lambda: ak.index_zh_a_hist(symbol='000300', period='daily',
    start_date='20240101', end_date='20261009'))
