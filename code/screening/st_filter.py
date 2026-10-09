# -*- coding: utf-8 -*-
"""
ST/退市过滤模块 —— 初筛管线第一步（剔除 ST / *ST / S*ST / 退市整理股）。

判定依据（A股规则）：
  1. ST 是交易所"特别处理"标记，按交易所命名规范，标记固定置于证券简称【最前】，
     如 'ST华微'、'*ST美盛'、'S*ST某某'（S=未股改）、'SST某某'。
     因此用【前缀匹配】即可 100% 覆盖，且天然避免误伤名称中段含 'ST' 的正常公司
     （如 'XXSTYY' 类，现实中 A 股简称全为中文，无此形态，但防御性写法更稳）。
  2. 退市整理期股票简称以 '退' 开头（'退市海医'、'退市XX'），同样前缀匹配。
  3. 明确【不使用】子串包含式匹配（'ST' in name）：本机缓存实测两个数据源
     spot(5548行)/yjbb(3876行) 中 "含ST但非前缀" 的样本均为 0，
     但包含式匹配在未来新增数据源（如英文简称/含字母代码）时存在误伤风险。

  说明：is_st(code, name) 的 code 参数仅用于接口完整性与审计日志，
  判定本身完全基于 name（A股 ST 状态以简称为准，代码无 ST 语义）。

使用：
    from screening.st_filter import is_st, filter_non_st
    df2 = filter_non_st(df)          # df 需含 code/name 列（列名自适应）
"""
import re

import pandas as pd

# ST 系前缀：'ST'、'*ST'、'SST'、'S*ST'（S=未股改标记，可位于 * 之前）
# 正则锚定开头，S 与 * 均可选，避免把 'SABCST' 之类误判
_ST_PREFIX_RE = re.compile(r"^(S?\*?ST)", re.IGNORECASE)
# 退市/退市整理：简称以 '退' 开头（'退市海医'、'退XX'）
_TUI_PREFIX_RE = re.compile(r"^退")

# filter_non_st 的列名自适应候选（按优先级）
_NAME_COL_CANDIDATES = ("名称", "股票简称", "证券简称")
_CODE_COL_CANDIDATES = ("代码", "股票代码", "证券代码")


def is_st(code=None, name=None) -> bool:
    """判断单个证券是否为 ST/退市类。

    规则（前缀匹配，见模块 docstring）：
      - 名称以 'ST' / '*ST' / 'S*ST' / 'SST' 开头  → True（大小写不敏感）
      - 名称以 '退' / '退市' 开头                  → True（退市整理期）
      - 其余（含 NaN/空）                          → False

    code 参数不参与判定，仅用于审计/接口兼容。
    """
    if name is None:
        return False
    s = str(name).strip()
    if not s:
        return False
    if _ST_PREFIX_RE.match(s):
        return True
    if _TUI_PREFIX_RE.match(s):
        return True
    return False


def filter_non_st(df: pd.DataFrame, code_col: str | None = None,
                  name_col: str | None = None) -> pd.DataFrame:
    """批量剔除 ST/退市股。

    参数：
      df      : 含 code/name 列的 DataFrame
      code_col: 代码列名；None 时按 ('代码','股票代码','证券代码') 自适应
      name_col: 名称列名；None 时按 ('名称','股票简称','证券简称') 自适应

    返回：
      剔除 ST/退市后的 DataFrame（保留原行序），并新增 'is_st' 列
      （该列在此为全 False，供审计确认"返回集确实无 ST"；剔除明细见打印输出）。

    副作用：打印剔除数量、剩余数量、前 10 个剔除示例（代码+名称）。
    """
    if name_col is None:
        for cand in _NAME_COL_CANDIDATES:
            if cand in df.columns:
                name_col = cand
                break
        else:
            raise ValueError(
                f"找不到名称列，候选 {_NAME_COL_CANDIDATES}，实际列 {list(df.columns)}")
    if code_col is None:
        for cand in _CODE_COL_CANDIDATES:
            if cand in df.columns:
                code_col = cand
                break
        # code 列找不到不报错（仅影响打印示例），名称判定不依赖 code

    out = df.copy()
    out["is_st"] = out[name_col].map(lambda n: is_st(None, n))

    removed = out[out["is_st"]]
    kept = out[~out["is_st"]]

    print(f"[filter_non_st] 输入 {len(out)} 行, 剔除 ST/退市 {len(removed)} 行, "
          f"剩余 {len(kept)} 行")
    if len(removed) > 0:
        show_cols = [c for c in (code_col, name_col) if c]
        print(f"[filter_non_st] 剔除示例(前10): "
              f"{removed[show_cols].head(10).values.tolist()}")
    return kept


def cross_check_sources(df_a: pd.DataFrame, name_col_a: str,
                        df_b: pd.DataFrame, name_col_b: str,
                        code_col_a: str = "代码", code_col_b: str = "股票代码",
                        label_a: str = "A", label_b: str = "B") -> pd.DataFrame:
    """交叉验证两个来源的 ST 判定一致性。

    同一代码在两个来源中的简称应给出相同 is_st 判定；
    返回不一致记录 DataFrame（空 = 完全一致），并打印汇总。
    """
    def _norm_code(v):
        s = str(v).strip()
        # 数字型代码补零到 6 位；带后缀(如 sh600000)取数字部分
        digits = re.sub(r"\D", "", s)
        if digits:
            return digits.zfill(6)
        return s

    a = df_a[[code_col_a, name_col_a]].copy()
    a.columns = ["code", "name"]
    a["code"] = a["code"].map(_norm_code)
    a["is_st"] = a["name"].map(lambda n: is_st(None, n))
    a = a.drop_duplicates("code")

    b = df_b[[code_col_b, name_col_b]].copy()
    b.columns = ["code", "name"]
    b["code"] = b["code"].map(_norm_code)
    b["is_st"] = b["name"].map(lambda n: is_st(None, n))
    b = b.drop_duplicates("code")

    merged = a.merge(b, on="code", suffixes=(f"_{label_a}", f"_{label_b}"),
                     how="inner")
    mism = merged[merged[f"is_st_{label_a}"] != merged[f"is_st_{label_b}"]]
    print(f"[cross_check] 两源共有代码 {len(merged)} 个, "
          f"判定不一致 {len(mism)} 个")
    if len(mism) > 0:
        print(f"[cross_check] 不一致明细(前20):\n{mism.head(20).to_string()}")
    return mism
