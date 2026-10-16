# -*- coding: utf-8 -*-
"""measure_dailybars.py — 实测 daily_bars 的规模与体积（决定入库策略）"""
import os, sys, glob
import pandas as pd, numpy as np, sqlite3, tempfile, time

sys.stdout.reconfigure(encoding='utf-8')
C = r'g:\股市探究\quant-investing\code\data_cache'

raw = sorted(glob.glob(os.path.join(C, 'hist_*_20160601_*_20261009.parquet')))
raw = [f for f in raw if '_hfq_' not in f]
hfq = sorted(glob.glob(os.path.join(C, 'hist_*_20160601_*_hfq_20261009.parquet')))
print(f'  raw 文件 {len(raw)} | hfq 文件 {len(hfq)}')

SAMPLE = 100
frames, tot_rows = [], 0
t0 = time.time()
for f in raw[:SAMPLE]:
    d = pd.read_parquet(f, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    code = os.path.basename(f).split('_')[1]
    d.insert(0, 'code', code)
    tot_rows += len(d)
    frames.append(d)
df = pd.concat(frames, ignore_index=True)
avg = tot_rows / SAMPLE
print(f'  样本 {SAMPLE} 只 / {tot_rows:,} 行，平均 {avg:.0f} 交易日/只  ({time.time()-t0:.1f}s)')

proj_rows = int(avg * len(raw))
print(f'  全量投影 raw: {proj_rows:,} 行 ({proj_rows/1e6:.1f}M)')

# 实测 SQLite 占用（含索引）
db = os.path.join(tempfile.gettempdir(), '_size_probe.db')
if os.path.exists(db):
    os.remove(db)
conn = sqlite3.connect(db)
conn.execute('''CREATE TABLE daily_bars (
    code TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL)''')
d = df.copy()
d['date'] = d['date'].astype(str)
conn.executemany('INSERT INTO daily_bars VALUES (?,?,?,?,?,?,?)',
                 d[['code', 'date', 'open', 'high', 'low', 'close', 'volume']].values.tolist())
conn.execute('CREATE INDEX idx_bars ON daily_bars(code, date)')
conn.commit()
conn.close()
sz = os.path.getsize(db)
per_row = sz / len(d)
print(f'  实测 SQLite: {sz/1e6:.1f} MB / {len(d):,} 行 = {per_row:.1f} B/行（含索引）')
print(f'  → 全量 raw 投影: {proj_rows*per_row/1e9:.2f} GB')
print(f'  → raw + hfq 两份: {2*proj_rows*per_row/1e9:.2f} GB')
os.remove(db)

# 宽表 parquet 投影
w = df.pivot_table(index='date', columns='code', values='close')
print(f'  宽表 close {w.shape} 内存 {w.memory_usage(deep=True).sum()/1e6:.1f} MB')
tmp = os.path.join(tempfile.gettempdir(), '_w.parquet')
w.to_parquet(tmp)
print(f'  宽表 parquet（{SAMPLE} 列）{os.path.getsize(tmp)/1e6:.2f} MB'
      f' → 投影 {os.path.getsize(tmp)/1e6*len(raw)/SAMPLE:.0f} MB/张')
os.remove(tmp)
free = 11.58
print(f'\n  G: 可用 {free:.2f} GB')
print(f'  决策参考：若只存 raw → {proj_rows*per_row/1e9:.2f} GB；raw+hfq → {2*proj_rows*per_row/1e9:.2f} GB')
