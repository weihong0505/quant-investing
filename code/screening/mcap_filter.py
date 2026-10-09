# -*- coding: utf-8 -*-
"""
screening/mcap_filter.py — 初筛管线: 市值过滤模块
================================================================
功能:
  fetch_mcap(codes, batch_size=60)      — 腾讯 qt.gtimg.cn 实时总市值批量拉取(亿元), 缓存优先
  filter_by_mcap(codes_df, min_mcap_yi=50) — 市值≥阈值过滤; 无市值个股保守剔除

数据源: 腾讯 qt.gtimg.cn 实时行情
  URL: https://qt.gtimg.cn/q=sh600000,sz000001,bj920000 (每批 batch_size 只)
  返回: v_sh600000="1~浦发银行~600000~9.05~...~[45]总市值(亿元)~..."
  字段45 = 总市值(亿元), 与 e2e_pipeline.fetch_qt_quotes 同源
缓存:  data_cache/mcap_{YYYYMMDD}.parquet (code, mcap_yi, ts), 当日有效

代码转换: 60xxxx→sh, 00/30→sz, 8/4/9→bj (北交所 43x/83x/87x/88x/92x)

口径与声明:
  - 总市值为腾讯实时口径(最新交易日), 单位亿元
  - 失败/停牌无行情/非法代码 → 无市值数据, 一律保守剔除, 不进入初筛后续环节
  - 本模块独立实现(不依赖 data_fetcher / akshare), 仅需 requests + pandas + pyarrow

运行自测: D:/pyh/python.exe -X utf8 -E screening/mcap_filter.py
"""
import os
import sys
import time
import glob
import datetime
import logging
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# 代理绕过三件套 (必须先于 requests 导入; 与 data_fetcher 同款, 幂等)
# ============================================================
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
for k in list(os.environ):
    if 'proxy' in k.lower():
        os.environ.pop(k, None)

import requests

_ORIG_SESSION_REQUEST = requests.Session.request


def _no_proxy_request(self, method, url, **kwargs):
    kwargs['proxies'] = {'http': None, 'https': None}
    kwargs.setdefault('timeout', 30)
    return _ORIG_SESSION_REQUEST(self, method, url, **kwargs)


requests.Session.request = _no_proxy_request

import pandas as pd

# ============================================================
# 路径 & 日志
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # G:/股市探究/quant-investing/code
CACHE_DIR = os.path.join(BASE_DIR, 'data_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

TODAY = datetime.date.today().strftime('%Y%m%d')

logger = logging.getLogger('mcap_filter')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _fmt = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s', datefmt='%H:%M:%S')
    _sh = logging.StreamHandler()
    try:
        _sh.setStream(__import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
    except Exception:
        pass
    _sh.setFormatter(_fmt)
    logger.addHandler(_sh)

_REQUEST_COUNT = 0   # 实际网络请求批次计数 (缓存生效验证用)
_last_request_ts = 0.0


def _throttle(min_gap=0.5):
    """请求间隔 ≥ min_gap 秒"""
    global _last_request_ts
    elapsed = time.time() - _last_request_ts
    if elapsed < min_gap:
        time.sleep(min_gap - elapsed)
    _last_request_ts = time.time()


# ============================================================
# 代码规范化 & 腾讯格式转换
# ============================================================
def _normalize_code(c):
    """6位纯数字代码 → str; 非法返回 None"""
    s = str(c).strip()
    return s if (s.isdigit() and len(s) == 6) else None


def _code_to_tencent(c):
    """6位代码 → 腾讯格式: 60xxxx→sh, 00/30→sz, 8/4/9→bj; 不支持返回 None"""
    if not c or not c.isdigit() or len(c) != 6:
        return None
    if c.startswith('6'):
        return 'sh' + c
    if c.startswith(('0', '3')):
        return 'sz' + c
    if c.startswith(('4', '8', '9')):
        return 'bj' + c
    return None


# ============================================================
# 缓存读写 (data_cache/mcap_{YYYYMMDD}.parquet)
# ============================================================
def _cache_path():
    return os.path.join(CACHE_DIR, f'mcap_{TODAY}.parquet')


def _load_cache():
    """读当日缓存 → {code: mcap_yi}; 无缓存/损坏返回 {}"""
    p = _cache_path()
    if not os.path.exists(p):
        return {}
    try:
        df = pd.read_parquet(p)
        out = {}
        for _, r in df.iterrows():
            c = _normalize_code(r['code'])
            if c:
                try:
                    v = float(r['mcap_yi'])
                    if v > 0:
                        out[c] = v
                except (TypeError, ValueError):
                    pass
        return out
    except Exception as e:
        logger.warning(f'[mcap] 缓存读取失败(忽略, 重新拉取): {type(e).__name__}: {str(e)[:80]}')
        return {}


def _save_cache(mcap_map):
    """写当日缓存 (当日已拉取的全量合并)"""
    df = pd.DataFrame([{'code': c, 'mcap_yi': v,
                        'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                       for c, v in sorted(mcap_map.items())])
    df.to_parquet(_cache_path(), index=False)


# ============================================================
# 1) fetch_mcap — 腾讯 qt 实时总市值批量拉取 (缓存优先)
# ============================================================
def fetch_mcap(codes, batch_size=60, retries=3):
    """
    腾讯 qt 实时总市值批量拉取 (缓存优先)。

    参数:
        codes: 6位纯数字代码列表 (非法/重复自动清洗)
        batch_size: 每批拉取数量 (默认60, 腾讯qt单批上限约60-100)
        retries: 每批失败重试次数
    返回:
        Dict[code, float] — 总市值(亿元); 失败个股跳过不抛错
    缓存:
        data_cache/mcap_{YYYYMMDD}.parquet (当日合并全量, 第二次调用全命中)
    """
    global _REQUEST_COUNT
    codes = [c for c in (_normalize_code(c) for c in codes) if c is not None]
    if not codes:
        return {}
    seen = set()
    codes = [c for c in codes if not (c in seen or seen.add(c))]  # 去重保序

    cache = _load_cache()
    out = {}
    missing = []
    for c in codes:
        if c in cache:
            out[c] = cache[c]
        else:
            missing.append(c)

    if missing:
        logger.info(f'[mcap] 缓存命中 {len(out)}/{len(codes)} 只, 需拉取 {len(missing)} 只')
        for i in range(0, len(missing), batch_size):
            chunk = missing[i:i + batch_size]
            syms = ','.join(s for s in (_code_to_tencent(c) for c in chunk) if s)
            if not syms:
                continue
            for attempt in range(retries):
                try:
                    _throttle(0.5)
                    _REQUEST_COUNT += 1
                    r = requests.get(f'https://qt.gtimg.cn/q={syms}')
                    r.raise_for_status()
                    txt = r.content.decode('gbk', errors='replace')
                    for seg in txt.split(';'):
                        seg = seg.strip()
                        if '="' not in seg:
                            continue
                        body = seg.split('="', 1)[1].rstrip('"')
                        f = body.split('~')
                        if len(f) < 46:      # 缺字段45(总市值)则跳过
                            continue
                        code = f[2].strip()
                        try:
                            mcap_yi = float(f[45])
                        except ValueError:
                            continue
                        if code and mcap_yi > 0:
                            out[code] = mcap_yi
                    break
                except Exception as e:
                    if attempt == retries - 1:
                        logger.warning(f'[mcap] 批次 {i // batch_size} 失败: {type(e).__name__}: {str(e)[:80]}')
                    else:
                        time.sleep(2.0 * (attempt + 1))
        # 合并回当日缓存 (旧缓存 ∪ 新拉取)
        merged = dict(cache)
        merged.update(out)
        try:
            _save_cache(merged)
        except Exception as e:
            logger.warning(f'[mcap] 缓存写入失败: {type(e).__name__}: {str(e)[:80]}')
    else:
        logger.info(f'[mcap] 全缓存命中: {len(out)} 只 (无网络请求)')

    return {c: out[c] for c in codes if c in out}


# ============================================================
# 2) filter_by_mcap — 市值过滤
# ============================================================
def filter_by_mcap(codes_df, min_mcap_yi=50, mcap_map=None):
    """
    市值过滤: 保留总市值 ≥ min_mcap_yi(亿元) 的个股。

    参数:
        codes_df: DataFrame, 必须含 'code' 列 (6位数字代码)
        min_mcap_yi: 最低总市值阈值, 亿元 (默认50亿, 避开微盘)
        mcap_map: 可选, 预拉取的 {code: 市值(亿)}; 缺省时内部调用 fetch_mcap
    返回:
        过滤后 DataFrame (新增 mcap_yi 列, 单位亿元)
    剔除规则:
        - 市值不可得 (拉取失败/停牌无行情/非法代码): 保守剔除, 打印数量并声明
        - 市值 < min_mcap_yi: 剔除 (微盘)
    """
    df = codes_df.copy()
    if 'code' not in df.columns:
        raise ValueError("codes_df 必须含 'code' 列")
    df['code'] = df['code'].astype(str).str.strip()
    valid = df['code'].str.fullmatch(r'\d{6}')
    n_bad = int((~valid).sum())
    if n_bad:
        logger.warning(f'[mcap] {n_bad} 个非法代码(非6位数字), 视为市值不可得, 剔除')

    codes = df.loc[valid, 'code'].tolist()
    if mcap_map is None:
        mcap_map = fetch_mcap(codes)

    df['mcap_yi'] = df['code'].map(mcap_map)
    n_missing = int(df['mcap_yi'].isna().sum())
    if n_missing:
        miss_codes = df.loc[df['mcap_yi'].isna(), 'code'].tolist()
        print(f'[mcap] 市值不可得: {n_missing} 只 (保守剔除, 不进入初筛) '
              f'例: {miss_codes[:10]}{"..." if n_missing > 10 else ""}')
        logger.info(f'[mcap] 市值不可得 {n_missing} 只: {miss_codes[:20]}'
                    f'{"..." if n_missing > 20 else ""}')
    df = df.dropna(subset=['mcap_yi'])

    n_before = len(df)
    df = df[df['mcap_yi'] >= min_mcap_yi]
    n_after = len(df)
    print(f'[mcap] 过滤: 有市值 {n_before} 只 → ≥{min_mcap_yi}亿 {n_after} 只 '
          f'(剔除微盘 {n_before - n_after} 只)')
    return df.reset_index(drop=True)


# ============================================================
# 3) 模块自测
# ============================================================
def _selftest_coverage(limit=200):
    """
    读 spot 缓存等距抽样 limit 只 (覆盖沪深北全市场), 实测 qt 覆盖率。
    注: spot 文件按代码升序, 字面"前200只"= 920000-920199 全为北交所,
    样本单一; 故等距抽样覆盖 sh/sz/bj 三市场, 更符合接口实测意图。
    """
    spot_files = sorted(glob.glob(os.path.join(CACHE_DIR, 'spot_*.parquet')))
    if not spot_files:
        print('[selftest] 未找到 spot 缓存, 跳过覆盖率测试')
        return False, []
    spot_path = spot_files[-1]
    sp = pd.read_parquet(spot_path)
    all_codes = [str(c) for c in sp['代码'].tolist()]
    all_codes = [c for c in all_codes if c.isdigit() and len(c) == 6]
    stride = max(1, len(all_codes) // limit)
    sample = all_codes[::stride][:limit]

    from collections import Counter
    pref = Counter(c[:2] for c in sample)
    print(f'[selftest] spot源: {os.path.basename(spot_path)} ({len(all_codes)}只), '
          f'抽样 {len(sample)} 只, 前缀分布: {dict(sorted(pref.items()))}')

    global _REQUEST_COUNT
    _REQUEST_COUNT = 0
    t0 = time.time()
    mcap = fetch_mcap(sample)
    dt = time.time() - t0
    n_req = _REQUEST_COUNT
    cov = len(mcap) / len(sample)
    print(f'[selftest] 覆盖率: {len(mcap)}/{len(sample)} = {cov:.1%}  '
          f'耗时 {dt:.1f}s  请求批次 {n_req}')
    ok = cov >= 0.90
    print(f'[selftest] 拉取测试: {"PASS (覆盖率≥90%)" if ok else "FAIL (覆盖率<90%)"}')
    return ok, sample


def _selftest_cache(sample_codes):
    """缓存生效: 第二次调用不重复请求 (请求批次=0 且结果一致)"""
    global _REQUEST_COUNT
    _REQUEST_COUNT = 0
    t0 = time.time()
    m1 = fetch_mcap(sample_codes)
    dt1, n1 = time.time() - t0, _REQUEST_COUNT
    _REQUEST_COUNT = 0
    t0 = time.time()
    m2 = fetch_mcap(sample_codes)
    dt2, n2 = time.time() - t0, _REQUEST_COUNT
    print(f'[selftest] 缓存: 首次 {dt1:.2f}s/{n1}批请求 → 二次 {dt2:.2f}s/{n2}批请求; '
          f'二次返回 {len(m2)} 只')
    ok = (n2 == 0) and (m1 == m2)
    print(f'[selftest] 缓存测试: {"PASS (二次零网络请求, 结果一致)" if ok else "FAIL"}')
    return ok


def _selftest_filter():
    """合成 df: <50亿 / ≥50亿 / 无市值 / 非法代码 四类, 验证剔除逻辑"""
    synth = pd.DataFrame({
        'code': ['600000', '000001', '300001', '688001', '830001', '000002', '12345', 'abc'],
        'name': ['浦发银行', '平安银行', '特锐德', '某科创板', '某北交所', '万科A', '非法', '非法'],
    })
    # 注: 000002 故意不给市值 (模拟拉取失败); 12345/abc 非法代码
    fake_mcap = {'600000': 2500.0, '000001': 2100.0, '300001': 30.5,
                 '688001': 88.0, '830001': 12.0}
    out = filter_by_mcap(synth, min_mcap_yi=50, mcap_map=fake_mcap)
    got = set(out['code'])
    expect = {'600000', '000001', '688001'}
    ok = (got == expect) and ('mcap_yi' in out.columns) and \
         (out.loc[out['code'] == '600000', 'mcap_yi'].iloc[0] == 2500.0)
    print(f'[selftest] 过滤: 入 {len(synth)} 只 → 出 {len(out)} 只: {sorted(got)}')
    print(f'[selftest] 期望: {sorted(expect)} (剔除: 微盘300001/830001, 无市值000002, 非法12345/abc)')
    print(f'[selftest] 过滤测试: {"PASS" if ok else "FAIL"}')
    return ok


def main():
    print('=' * 66)
    print(f' mcap_filter 自测  {TODAY}   缓存: {_cache_path()}')
    print('=' * 66)
    ok1, sample = _selftest_coverage(200)
    ok2 = _selftest_cache(sample) if sample else False
    ok3 = _selftest_filter()
    all_ok = ok1 and ok2 and ok3
    print('-' * 66)
    print(f' 结果: 拉取测试 {"PASS" if ok1 else "FAIL"} | '
          f'缓存测试 {"PASS" if ok2 else "FAIL"} | '
          f'过滤测试 {"PASS" if ok3 else "FAIL"}')
    print(f' 总体: {"ALL PASS" if all_ok else "HAS FAILURE"}')
    return all_ok


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
