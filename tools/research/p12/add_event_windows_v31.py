"""Recompute P12.3.1 event windows and assign one mutually exclusive status."""
from __future__ import annotations

import bisect
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/research/p12_3_1"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    e = pd.read_csv(ROOT / "data/research/p12_3/p12_3_filing_events.csv")
    px = pd.read_csv(ROOT.parent / "pr512/data/research/pit_data/finsaber_prices_raw.csv", usecols=["date", "symbol", "adjusted_close"], parse_dates=["date"])
    px["symbol"] = px.symbol.str.upper().str.replace(".", "-", regex=False)
    px = px[px.adjusted_close > 0]
    spy = pd.read_csv(ROOT.parent / "pr512/data/research/p9_1_support_resistance/spy.csv", parse_dates=["Date"])
    tdays = sorted(set(spy.Date.dt.date.astype(str)))
    close = {s: g.set_index("date").adjusted_close.sort_index() for s, g in px.groupby("symbol")}

    def prior(d):
        i = bisect.bisect_left(tdays, d)
        return tdays[i - 1] if i > 0 else None

    def after(d):
        i = bisect.bisect_right(tdays, d)
        return tdays[i] if i < len(tdays) else None

    def n_after(d, n):
        i = bisect.bisect_right(tdays, d)
        return tdays[i + n - 1] if i + n - 1 < len(tdays) else None

    for col in ("status", "status_reason", "reaction_date", "d0_base_date", "d1_base_date", "d5_base_date", "d0_return", "d1_return", "d5_return", "window_rule", "event_price_status"):
        e[col] = None
    for i, r in e.iterrows():
        fd, sess = str(r["filing_date"]), r["event_session"]
        if r["group"] == "FOREIGN_ADR":
            e.at[i, "status"] = "FOREIGN_PRICE_MISSING"
            e.at[i, "status_reason"] = "foreign ADR has no local daily price panel"
            continue
        ser = close.get(r["price_symbol"])
        if ser is None:
            e.at[i, "status"] = "US_SYMBOL_NOT_FOUND"
            e.at[i, "status_reason"] = "US symbol not present in local price panel"
            continue
        if sess in ("PREMARKET", "INTRADAY"):
            reaction = fd if fd in tdays else None
            prev = prior(fd)
            base = fd
            event_close_date = fd
            rule = f"{sess}_D0_EVENT_CLOSE_VS_PRIOR"
        elif sess == "AFTER_HOURS":
            reaction = after(fd)
            prev = fd
            base = reaction
            event_close_date = fd
            rule = "AFTER_HOURS_D0_NEXT_CLOSE_VS_EVENT_CLOSE"
        else:
            reaction = after(fd)
            prev = prior(fd)
            base = reaction
            event_close_date = reaction
            rule = "NON_TRADING_D0_NEXT_VS_PRIOR"
        e.at[i, "window_rule"] = rule
        e.at[i, "reaction_date"] = reaction or ""
        e.at[i, "d0_base_date"] = prev or ""
        e.at[i, "d1_base_date"] = reaction or ""
        e.at[i, "d5_base_date"] = reaction or ""
        if prev is None or prev not in ser.index:
            e.at[i, "status"] = "NON_TRADING_WINDOW_MISSING" if sess == "NON_TRADING" else "NO_PREVIOUS_CLOSE"
            e.at[i, "status_reason"] = "prior close unavailable"
            continue
        if reaction is None:
            e.at[i, "status"] = "NON_TRADING_WINDOW_MISSING" if sess == "NON_TRADING" else "NO_NEXT_SESSION_CLOSE"
            e.at[i, "status_reason"] = "next/event session unavailable"
            continue
        if base not in ser.index:
            e.at[i, "status"] = "NON_TRADING_WINDOW_MISSING" if sess == "NON_TRADING" else "NO_EVENT_CLOSE"
            e.at[i, "status_reason"] = "reaction/event close unavailable"
            continue
        if sess == "AFTER_HOURS":
            if event_close_date not in ser.index:
                e.at[i, "status"] = "NO_EVENT_CLOSE"
                e.at[i, "status_reason"] = "event-day close unavailable after hours"
                continue
            d0 = float(ser.loc[reaction] / ser.loc[event_close_date] - 1)
        else:
            d0 = float(ser.loc[reaction] / ser.loc[prev] - 1)
        nxt = n_after(reaction, 1)
        five = n_after(reaction, 5)
        d1 = float(ser.loc[nxt] / ser.loc[reaction] - 1) if nxt in ser.index else None
        d5 = float(ser.loc[five] / ser.loc[reaction] - 1) if five in ser.index else None
        e.at[i, "d0_return"] = d0
        e.at[i, "d1_return"] = d1
        e.at[i, "d5_return"] = d5
        e.at[i, "event_price_status"] = "OK"
        if d1 is None:
            e.at[i, "status"] = "D1_MISSING"
            e.at[i, "status_reason"] = "next-session close missing"
        elif d5 is None:
            e.at[i, "status"] = "D5_MISSING"
            e.at[i, "status_reason"] = "five-session close missing"
        elif sess == "NON_TRADING" and not all(pd.notna([d0, d1, d5])):
            e.at[i, "status"] = "NON_TRADING_WINDOW_MISSING"
            e.at[i, "status_reason"] = "non-trading window incomplete"
        else:
            e.at[i, "status"] = "OK_COMPLETE"
            e.at[i, "status_reason"] = "D0/D1/D5 available"
    e.to_csv(OUT / "p12_3_1_event_window_returns.csv", index=False)
    status = e.groupby(["group", "event_type", "event_session", "status"]).size().reset_index(name="events")
    status.to_csv(OUT / "p12_3_1_event_status_reconciliation.csv", index=False)
    cov = e.groupby(["group", "event_type", "event_session"]).agg(events=("accession", "size"), d0_ok=("d0_return", lambda x: x.notna().sum()), d1_ok=("d1_return", lambda x: x.notna().sum()), d5_ok=("d5_return", lambda x: x.notna().sum()), complete=("status", lambda x: (x == "OK_COMPLETE").sum())).reset_index()
    cov.to_csv(OUT / "p12_3_1_event_window_coverage.csv", index=False)
    print({"events": len(e), "status": e.status.value_counts().to_dict()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
