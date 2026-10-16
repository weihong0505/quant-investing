import json, os
T = r'g:\股市探究\fullA-检验与回测\reports\composite'
m = json.load(open(os.path.join(T, 'composite_metrics.json'), encoding='utf-8'))
print('  组合层指标（JSON 全量关键项）:')
for k in ['ic_mean','ic_sd','icir','naive_t','nw_t','winrate','benchmark_B',
          'interaction_loss','roll36_last','last12_all_negative',
          'ic_down_month','ic_high_vol','verdict','backtest_done']:
    print(f'    {k:22} {m.get(k)}')
print()
print('  leave_one_out ΔIC（正=该因子有贡献）:')
for k, v in m['leave_one_out'].items():
    print(f'    {k:9} 剩余IC {v["mean_ic"]:+.4f}   ΔIC {v["delta_ic"]:+.4f}')
print()
print('  分层 5 组年化:')
for k, v in m['quintile_annual'].items():
    print(f'    Q{k} {v:+.2%}')
print()
print('  long_short:')
for k, v in m['long_short'].items():
    print(f'    {k:22} {v}')
print()
print('  分年度合成 IC:')
for k, v in m['by_year'].items():
    print(f'    {k} {v:+.4f}')
print()
print('  分制度段:')
for k, v in m['by_segment'].items():
    print(f'    {k} {v:+.4f}')
print()
print('  IC 衰减:')
for k, v in m['decay'].items():
    print(f'    {k} {v:+.4f}')
print()
print('  hard_fail:', m.get('hard_fail'))
print('  watch    :', m.get('watch'))
print('  econ_fail:', m.get('econ_fail'))
