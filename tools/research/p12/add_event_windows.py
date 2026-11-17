"""Recompute P12.3 event windows with explicit session rules."""
from __future__ import annotations

import bisect
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/research/p12_3"


def main() -> int:
    e = pd.read_csv(OUT / "p12_3_filing_events.csv")
    px = pd.read_csv(ROOT.parent / "pr512/data/research/pit_data/finsaber_prices_raw.csv", usecols=["date", "symbol", "adjusted_close"], parse_dates=["date"])
    px["symbol"] = px.symbol.str.upper().str.replace(".", "-", regex=False)
    px = px[px.adjusted_close > 0]
    spy = pd.read_csv(ROOT.parent / "pr512/data/research/p9_1_support_resistance/spy.csv", parse_dates=["Date"])
    tdays = sorted(set(spy.Date.dt.date.astype(str)))
    close = {s: g.set_index("date").adjusted_close.sort_index() for s, g in px.groupby("symbol")}
    for col in ("d0_return", "d1_return", "d5_return", "window_rule", "event_price_status"):
        if col not in e:
            e[col] = None
    for i, r in e.iterrows():
        ser = close.get(r["price_symbol"])
        fd = str(r["filing_date"])
        sess = r["event_session"]
        if ser is None or fd not in tdays:
            e.at[i, "event_price_status"] = "PRICE_MISSING"
            e.at[i, "window_rule"] = "NO_PRICE_OR_TRADING_DAY"
            continue
        j = bisect.bisect_left(tdays, fd)
        if sess in ("PREMARKET", "INTRADAY"):
            reaction = tdays[j]
            prev = tdays[j - 1] if j > 0 else None
            rule = f"{sess}_D0_EVENT_CLOSE_VS_PRIOR"
        elif sess == "AFTER_HOURS":
            reaction = tdays[j + 1] if j + 1 < len(tdays) else None
            prev = tdays[j]
            rule = "AFTER_HOURS_D0_NEXT_CLOSE_VS_EVENT_CLOSE"
        else:
            reaction = tdays[j + 1] if j + 1 < len(tdays) else None
            prev = tdays[j - 1] if j > 0 else None
            rule = "NON_TRADING_D0_NEXT_VS_PRIOR"
        if reaction is None or prev is None or reaction not in ser.index or prev not in ser.index:
            e.at[i, "event_price_status"] = "PRICE_MISSING"
            e.at[i, "window_rule"] = rule
            continue
        e.at[i, "d0_return"] = float(ser.loc[reaction] / ser.loc[prev] - 1)
        k = tdays.index(reaction)
        nxt = tdays[k + 1] if k + 1 < len(tdays) else None
        five = tdays[k + 5] if k + 5 < len(tdays) else None
        e.at[i, "d1_return"] = float(ser.loc[nxt] / ser.loc[reaction] - 1) if nxt in ser.index else None
        e.at[i, "d5_return"] = float(ser.loc[five] / ser.loc[reaction] - 1) if five in ser.index else None
        e.at[i, "reaction_return"] = e.at[i, "d0_return"]
        e.at[i, "next_day_return"] = e.at[i, "d1_return"]
        e.at[i, "window_rule"] = rule
        e.at[i, "event_price_status"] = "OK" if pd.notna(e.at[i, "d0_return"]) else "PRICE_MISSING"
    e.to_csv(OUT / "p12_3_event_window_returns.csv", index=False)
    print({"rows": len(e), "ok": int((e.event_price_status == "OK").sum()), "missing": int((e.event_price_status == "PRICE_MISSING").sum())})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
