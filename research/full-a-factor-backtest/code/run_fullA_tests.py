# -*- coding: utf-8 -*-
"""
run_fullA_tests.py — 全 A 因子检验执行器（Workstream A 收口）
============================================================
按 registry 已登记的口径执行，不在看到结果后调参。

冻结的检验配置（**执行前写死并落盘**，符合 factor_testing_methodology v3 §9 防改口）：
  样本池    : 全 A 5,179 只（含退市股 361 只）
  样本期    : 2017-01-31 ~ 2026-09-30（117 个月）
  n_star    : 4（本季度同期受检新因子数：ROE_TTM / GPM / EP / BP）
  OOS       : 最近 24 个月一次确认
  签名（registry 锁定值）:
    ROE_TTM + | GPM + | EP + | BP +
  数据版本  : quant.db quarterly_fin 212,053 行 / 44 期；
              data_cache hist_* raw+hfq 各 5,219 只（末交易日 2026-10-08）
  PIT 口径  : 法定披露截止日
  TTM 口径  : eps(最近已披露财年) + eps(本年累计) − eps(上年同期累计)

用法：D:/pyh/python.exe -E run_fullA_tests.py [--factors EP,BP,ROE_TTM,GPM]
"""
import os
import sys
import json
import argparse
import datetime
import subprocess

sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

TASK = r'g:\股市探究\fullA-检验与回测'
WIDE = os.path.join(TASK, 'data', 'wide')
CODE = r'g:\股市探究\quant-investing\code'
OUT = os.path.join(TASK, 'reports', 'tests')   # 交付物目录（纳入版本控制；output/ 仅放中间产物）

# registry 锁定符号（不可改）
SIGNS = {'ROE_TTM': 1, 'GPM': 1, 'EP': 1, 'BP': 1}
N_STAR = 4
START = '2017-01-31'
OOS = 24


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--factors', default='EP,BP,ROE_TTM,GPM')
    ap.add_argument('--wide-dir', default='wide',
                    help='宽表目录名（data/ 下）：wide=原始Z；wide_n=行业内中性化')
    ap.add_argument('--out-dir', default='tests', help='reports/ 下的输出子目录')
    ap.add_argument('--tag', default='', help='文件名标记，如 _neutral')
    ap.add_argument('--dummy', action='store_true')
    a = ap.parse_args()
    factors = [x.strip() for x in a.factors.split(',') if x.strip()]

    wide = os.path.join(TASK, 'data', a.wide_dir)
    OUT = os.path.join(TASK, 'reports', a.out_dir)
    os.makedirs(OUT, exist_ok=True)

    # ---- 冻结配置留档（执行前写，事后不可改）----
    cfg = {
        'frozen_at': datetime.datetime.now().isoformat(),
        'wide_dir': a.wide_dir,
        'neutralized': a.wide_dir == 'wide_n',
        'universe': '全 A（含退市股 361）；中性化样本 5,024 只（缺行业 155 只已排除）',
        'panel': 'data/panel_neutral.parquet' if a.wide_dir == 'wide_n' else 'data/panel_fullA.parquet',
        'sample': f'{START} ~ 2026-09-30',
        'n_star': N_STAR,
        'oos_months': OOS,
        'signs': SIGNS,
        'factors': factors,
        'pit_rule': 'legal disclosure deadline',
        'ttm_rule': 'eps(nearest disclosed FY) + eps(YTD) - eps(prev-year same period)',
        'neutral_rule': ('行业内 winsorize(±3σ)+z-score，行业=申万一级，min_group=5 小行业回退全市场；'
                         '金融股质量因子置 0（复用 multi_factor_value.winsorize_zscore/industry_zscore）'
                         if a.wide_dir == 'wide_n' else '无（全市场 z-score 口径）'),
        'note': '配置在任何因子出结果前写死；registry 锁定符号未作任何改动',
    }
    cfgp = os.path.join(OUT, f'frozen_config{("_" + a.tag) if a.tag else ""}.json')
    with open(cfgp, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print('冻结配置 →', cfgp)
    for k, v in cfg.items():
        print(f'  {k}: {v}')

    ret = os.path.join(wide, 'ret.parquet')
    mcap = os.path.join(wide, 'mcap.parquet')
    results = []
    for fac in factors:
        fp = os.path.join(wide, f'{fac}.parquet')
        if not os.path.exists(fp):
            print(f'\n✗ {fac} 宽表不存在（{wide}），跳过')
            results.append({'factor': fac, 'status': 'missing'})
            continue
        print(f'\n{"="*70}\n=== 检验 {fac}（{a.wide_dir}, sign={SIGNS.get(fac,1)}）\n{"="*70}')
        cmd = [r'D:\pyh\python.exe', '-E', os.path.join(CODE, 'factor_test_suite.py'), 'run',
               '--factor', fp, '--ret', ret, '--mcap', mcap,
               '--name', fac, '--sign', str(SIGNS.get(fac, 1)),
               '--n-star', str(N_STAR), '--start', START, '--oos-months', str(OOS),
               '--out', OUT]
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', env=env)
        tail = (r.stdout or '')[-3000:]
        print(tail)
        if r.returncode != 0:
            print('  stderr:', (r.stderr or '')[-1200:])
        results.append({'factor': fac, 'returncode': r.returncode,
                        'stdout_tail': tail[-1500:]})

    with open(os.path.join(OUT, f'run_summary{("_" + a.tag) if a.tag else ""}.json'),
              'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n汇总 → {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
