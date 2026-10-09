# -*- coding: utf-8 -*-
"""验证所有量化工具是否安装成功"""

import sys
print(f"Python: {sys.version}")
print()

modules = [
    ("numpy",           "Core computation"),
    ("pandas",          "Data manipulation"),
    ("scipy",           "Scientific computing"),
    ("akshare",         "A-share data source"),
    ("tushare",         "A-share data source 2"),
    ("matplotlib",      "Visualization"),
    ("plotly",          "Interactive charts"),
    ("sklearn",         "Machine learning"),
    ("statsmodels",     "Statistical models"),
    ("backtrader",      "Backtesting framework"),
    ("pypfopt",         "Portfolio optimization"),
    ("pandas_ta",       "Technical indicators"),
    ("tqdm",            "Progress bars"),
    ("requests",        "HTTP client"),
    ("openpyxl",        "Excel read/write"),
]

ok = 0
fail = 0
for mod, desc in modules:
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "installed")
        print(f"  OK   {mod:<20s} {str(ver):<20s} {desc}")
        ok += 1
    except Exception as e:
        print(f"  FAIL {mod:<20s} {str(e):<40s} {desc}")
        fail += 1

print()
print(f"Result: {ok}/{ok+fail} success")

if fail > 0:
    print(f"\n{fail} module(s) failed. Run install script again.")
else:
    print("\nAll modules ready!")
