# -*- coding: utf-8 -*-
"""trade_history.csv 数据质量纯函数层：确定性去重 + 价格精度。

与 review.py 严格共享同一套规则，供 review.py 与测试共同 import，
避免"同名函数不同公式"造成口径漂移。

Review Event Key = Ticker|Date|Tag（大写 Ticker、日期归一到 YYYY-MM-DD）。
"""
import re

import pandas as pd

# 与 review.py 的 INVALID_STRINGS 语义一致：这些值视为"无信息"。
_INVALID_FIELD_VALUES = {"", "N/A", "NA", "NAN", "NONE", "NULL", "观望", "-", "--"}


def field_is_informative(value):
    """字段是否携带真实信息（非空、非 N/A、非观望、非 nan）。"""
    v = str(value).strip()
    return v.upper() not in {x.upper() for x in _INVALID_FIELD_VALUES} and v.lower() != "nan"


def review_event_key(df):
    """构造 Review Event Key = Ticker|Date|Tag（幂等键）。"""
    date_str = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return (df["Ticker"].astype(str).str.upper().str.strip()
            + "|" + date_str.fillna("")
            + "|" + df["Tag"].astype(str).str.strip())


def deduplicate_trade_history(df):
    """按 Review Event Key (Ticker|Date|Tag) 确定性去重。

    Canonical Record 规则（勿随意更改，测试覆盖）：
      - 同一个 Event Key 的多行中，优先保留信息更完整的一行 —— 即
        Hold_Period / Stop_Loss 越"非空/非 N/A/非观望"优先级越高；
      - 关键业务字段（Price / Exit_Date / Exit_Price / Status / PnL）在 duplicate 间
        实测完全一致，因此该规则不会丢失任何交易状态或退出信息；
      - 完整性相同则稳定保留最先出现的行（stable sort + keep='first'）。
    """
    if df is None or df.empty or "Ticker" not in df.columns or "Date" not in df.columns:
        return df
    dd = df.copy()
    dd["_key"] = review_event_key(dd)
    hp = (dd["Hold_Period"].apply(lambda s: 1 if field_is_informative(s) else 0)
          if "Hold_Period" in dd.columns else 0)
    sl = (dd["Stop_Loss"].apply(lambda s: 1 if field_is_informative(s) else 0)
          if "Stop_Loss" in dd.columns else 0)
    dd["_score"] = hp + sl
    dd = dd.sort_values("_score", ascending=False, kind="stable")
    dd = dd.drop_duplicates(subset=["_key"], keep="first")
    return dd.drop(columns=["_key", "_score"])


def fmt_price(value):
    """价格持久化格式：float -> 两位小数字符串；None/NaN/无效 -> 空字符串。

    只改显示精度，绝不改变数值语义或价格来源。
    """
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    s = str(value).strip().replace(",", "").replace("$", "")
    if s.upper() in {x.upper() for x in _INVALID_FIELD_VALUES}:
        return ""
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return s
    try:
        return f"{float(m.group(0)):.2f}"
    except Exception:
        return s
