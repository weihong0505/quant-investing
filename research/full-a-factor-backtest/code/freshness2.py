# -*- coding: utf-8 -*-
"""freshness2.py — 补：实时池 vs 库内池差集 + 是否已有 2026Q3 提前披露"""
import sys, sqlite3, warnings
import pandas as pd
warnings.filterwarnings('ignore')
sys.path.insert(0, r'g:\股市探究\quant-investing\code')
sys.stdout.reconfigure(encoding='utf-8')
import akshare as ak

c = sqlite3.connect(r'g:\股市探究\quant-investing\data\quant.db')
have = {str(r[0]).zfill(6) for r in c.execute('SELECT code FROM stock_master')}
print(f'  库内 stock_master: {len(have)} 只')

try:
    spot = ak.stock_zh_a_spot()          # 新浪实时全市场
    col = next((x for x in ('代码', 'code', 'symbol') if x in spot.columns), None)
    raw = spot[col].astype(str).tolist()
    now = {x[-6:] for x in raw if len(x) >= 6}
    print(f'  实时全市场(新浪): {len(now)} 只')
    new = sorted(now - have)
    gone = sorted(have - now)
    print(f'\n  **库内缺 {len(new)} 只**（09-17 后新上市/新纳入）:')
    print(f'    {new}')
    print(f'\n  库内多 {len(gone)} 只**（可能已退市/更名，或新浪口径差异）: {len(gone)}')
    if gone[:20]:
        print(f'    {gone[:20]}')
except Exception as e:
    print('  实时池失败:', type(e).__name__, str(e)[:120])

print('\n=== 是否已有 2026Q3 提前披露 ===')
try:
    q3 = ak.stock_yjbb_em(date='20260930')
    print(f'  yjbb 20260930 可得: {len(q3)} 行')
    if len(q3):
        nd = [x for x in q3.columns if '公告' in x or '日期' in x]
        for x in nd[:2]:
            s = pd.to_datetime(q3[x], errors='coerce').dropna()
            if len(s):
                print(f'    {x}: {s.min()} ~ {s.max()}')
except Exception as e:
    print(f'  yjbb 20260930 失败: {type(e).__name__}: {str(e)[:100]}')

print('\n=== 最近披露日分布（2026Q2 报告期的 notice_date 近年月）===')
try:
    d = pd.read_sql("SELECT notice_date, COUNT(*) n FROM quarterly_fin "
                    "WHERE report_date='2026-06-30' GROUP BY notice_date ORDER BY notice_date DESC LIMIT 8", c)
    print(d.to_string(index=False))
except Exception as e:
    print('  ', e)
c.close()
