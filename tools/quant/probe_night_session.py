"""Yahoo night-session 覆盖实测（只读，不改任何数据）。"""
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yfinance as yf

ET = ZoneInfo("America/New_York")

SYM = "AAPL"


def to_et(ts):
    # yfinance 返回的 index 是 tz-aware（多数版本为 UTC）
    return ts.astimezone(ET)


def analyze(period, interval="1m", prepost=True):
    print("=" * 60)
    print(f"period={period!r} interval={interval!r} prepost={prepost}")
    df = yf.Ticker(SYM).history(period=period, interval=interval, prepost=prepost)
    if df is None or df.empty:
        print("  !! 返回空 DataFrame")
        return None
    idx = df.index
    tz = idx.tz
    first = to_et(idx[0])
    last = to_et(idx[-1])
    print(f"  tz={tz}")
    print(f"  行数={len(df)}")
    print(f"  首 [ET] = {first}   首 [UTC] = {idx[0]}")
    print(f"  末 [ET] = {last}   末 [UTC] = {idx[-1]}")

    # 逐小时统计 ET 覆盖（hour 0..23 各有多少 bar）
    hours = {h: 0 for h in range(24)}
    for t in idx:
        hours[to_et(t).hour] += 1
    print("  ET 每小时 bar 数:")
    for h in range(24):
        bar = "#" * min(hours[h], 40)
        print(f"    {h:02d}:00 ET  {hours[h]:5d} {bar}")

    # 夜盘定义：21:00–23:59 + 00:00–04:00 ET
    night_bars = sum(v for h, v in hours.items() if h >= 21 or h < 4)
    print(f"  夜盘(21:00-04:00 ET) bar 数 = {night_bars}")
    return {"rows": len(df), "first_et": first, "last_et": last,
            "hours": hours, "night_bars": night_bars}


if __name__ == "__main__":
    r5 = analyze("5d")
    print()
    r1 = analyze("1d")
    print()
    # 结论
    for name, r in (("5d", r5), ("1d", r1)):
        if r is None:
            print(f"[{name}] 无数据，无法判定")
            continue
        ok = r["night_bars"] > 0
        print(f"[{name}] 夜盘覆盖={'是' if ok else '否'} -> "
              f"{'夜盘可只读刷新' if ok else '夜盘完全静默'}")
