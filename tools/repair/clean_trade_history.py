# -*- coding: utf-8 -*-
"""trade_history.csv 历史数据清理：去重（canonical 规则）+ Price round(2)。
与 review.py 的 deduplicate_trade_history / f"{:.2f}" 规则严格一致。"""
import sys, shutil, re, datetime
import pandas as pd

PATH = "trade_history.csv"

def field_is_informative(s):
    v = str(s).strip()
    return v != "" and v.upper() != "N/A" and v != "观望" and v.lower() != "nan"

def review_event_key(d):
    ds = pd.to_datetime(d["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return (d["Ticker"].astype(str).str.upper().str.strip()
            + "|" + ds.fillna("")
            + "|" + d["Tag"].astype(str).str.strip())

def clean_price(v):
    if v is None or str(v).strip() == "":
        return ""
    s = str(v).strip().replace(",", "").replace("$", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return s  # 非数字原样保留
    try:
        return f"{float(m.group(0)):.2f}"
    except Exception:
        return s

def run(dry_run=True):
    raw = pd.read_csv(PATH, dtype=str, keep_default_na=False, on_bad_lines="skip")
    before_rows = len(raw)
    raw["_key"] = review_event_key(raw)
    before_unique = raw["_key"].nunique()
    before_dup = before_rows - before_unique

    # Price 浮点尾数统计
    price_col = raw["Price"] if "Price" in raw.columns else None
    if price_col is not None:
        noisy = price_col[price_col.astype(str).str.contains(r"\.\d{3,}")]
    else:
        noisy = pd.Series(dtype=str)

    # canonical 去重
    hp = raw["Hold_Period"].apply(lambda s: 1 if field_is_informative(s) else 0) if "Hold_Period" in raw.columns else 0
    sl = raw["Stop_Loss"].apply(lambda s: 1 if field_is_informative(s) else 0) if "Stop_Loss" in raw.columns else 0
    raw["_score"] = hp + sl
    raw = raw.sort_values("_score", ascending=False, kind="stable")
    raw = raw.drop_duplicates(subset=["_key"], keep="first")
    removed_dup = before_rows - len(raw)
    dedup_keys = None

    # Price round(2)
    if price_col is not None:
        raw["Price"] = raw["Price"].apply(clean_price)

    after_rows = len(raw)
    after_unique = raw["_key"].nunique()
    after_dup = after_rows - after_unique

    # 输出统计
    print("===== 清理统计 =====")
    print(f"  before rows        : {before_rows}")
    print(f"  before unique      : {before_unique}")
    print(f"  before duplicate   : {before_dup}")
    print(f"  Price 浮点尾数行数 : {len(noisy)}")
    print(f"  ---")
    print(f"  after rows         : {after_rows}")
    print(f"  after unique       : {after_unique}")
    print(f"  after duplicate    : {after_dup}")
    print(f"  移除 duplicate 行  : {removed_dup}")

    if not dry_run:
        raw = raw.drop(columns=["_key", "_score"])
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = f"/tmp/trade_history.backup_{ts}.csv"
        shutil.copy(PATH, bak)
        raw.to_csv(PATH, index=False, encoding="utf-8")
        print(f"  备份: {bak}")
        print(f"  已写入: {PATH}")
    else:
        print("  (dry-run，未写入)")

if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    run(dry_run=dry)
