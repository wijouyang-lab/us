"""P6.17 yfinance OHLCV quality audit.

Run manually (workflow_dispatch); regular CI uses the fixed snapshot. The current
snapshot is requested only for the 144 research Top50 tickers.
"""
from __future__ import annotations
import argparse, csv, json, math, tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path("data/universe/selection")
OUT = Path("data/universe/selection_inputs/liquidity_ohlcv_p616.csv")
SESSIONS = Path("data/universe/selection_inputs/liquidity_sessions_p617.csv")
QUALITY = Path("data/universe/selection/liquidity_quality_audit_p617.csv")
SUMMARY = Path("data/universe/selection_inputs/liquidity_fetch_summary_p616.json")
AS_OF = date(2026, 11, 5)
STALE_DAYS = 5


def tickers():
    out = set()
    for name in ("value_top50.csv", "quality_top50.csv", "garp_top50.csv"):
        with (ROOT / name).open(encoding="utf-8", newline="") as f:
            out |= {r["ticker"] for r in csv.DictReader(f)}
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="6mo")
    a = ap.parse_args()
    ts = tickers()
    yf.set_tz_cache_location(tempfile.mkdtemp(prefix="yf-liq-"))
    data = yf.download(ts, period=a.period, interval="1d", auto_adjust=False,
                       actions=False, threads=False, progress=False, group_by="ticker")
    today = date.today()
    agg = []; sessions = []; quality = []
    for t in ts:
        try:
            frame = data[t] if isinstance(data.columns, pd.MultiIndex) else data
            frame = frame.dropna(subset=["Close", "Volume"]).copy()
            frame.index = pd.to_datetime(frame.index).date
            frame = frame[[d < today for d in frame.index]]
            frame = frame.sort_index()
            dates = list(frame.index)
            close = frame["Close"].astype(float); vol = frame["Volume"].astype(float)
            dv = close * vol
            last20 = dv.tail(20); last60 = dv.tail(60)
            adv20 = float(last20.mean()) if len(last20) >= 20 else None
            adv60 = float(last60.mean()) if len(last60) >= 60 else None
            last_date = dates[-1].isoformat() if dates else ""
            last_close = float(close.iloc[-1]) if len(close) else None
            last_volume = float(vol.iloc[-1]) if len(vol) else None
            duplicate = len(dates) != len(set(dates))
            finite = all(math.isfinite(float(x)) for x in list(close) + list(vol))
            positive = all(float(x) > 0 for x in close) and all(float(x) >= 0 for x in vol)
            stale = (AS_OF - datetime.strptime(last_date, "%Y-%m-%d").date()).days > STALE_DAYS if last_date else True
            rets = close.pct_change().dropna()
            anomaly = bool(len(rets) and (rets.abs().max() > 0.50))
            reasons = []
            if duplicate: reasons.append("DUPLICATE_SESSION_DATE")
            if not finite: reasons.append("NONFINITE_OHLCV")
            if not positive: reasons.append("NONPOSITIVE_CLOSE_OR_NEGATIVE_VOLUME")
            if len(last20) < 20: reasons.append("LESS_THAN_20_VALID_SESSIONS")
            if stale: reasons.append("LAST_SESSION_TOO_OLD")
            if anomaly: reasons.append("EXTREME_PRICE_MOVE_REVIEW")
            if not last_date or adv20 is None or adv60 is None:
                qstatus = "LIQUIDITY_DATA_BLOCKED"
            elif any(x in reasons for x in ("DUPLICATE_SESSION_DATE", "NONFINITE_OHLCV", "NONPOSITIVE_CLOSE_OR_NEGATIVE_VOLUME", "LESS_THAN_20_VALID_SESSIONS")):
                qstatus = "LIQUIDITY_INVALID_SESSIONS"
            elif stale:
                qstatus = "LIQUIDITY_STALE"
            elif anomaly:
                qstatus = "LIQUIDITY_CORPORATE_ACTION_REVIEW"
            else:
                qstatus = "LIQUIDITY_VALID"
            agg.append({"ticker": t, "last_completed_session": last_date, "close": last_close, "volume": last_volume,
                        "adv20_usd": adv20, "adv60_usd": adv60, "valid_sessions_20": len(last20),
                        "valid_sessions_60": len(last60), "volume_source": "yfinance",
                        "retrieved_at": datetime.now(timezone.utc).isoformat(), "price_asof": last_date,
                        "currency": "USD", "adjustment": "UNADJUSTED_CLOSE_RAW_VOLUME",
                        "liquidity_status": qstatus, "liquidity_data_quality": "OK" if qstatus == "LIQUIDITY_VALID" else "FLAGGED",
                        "quality_reason": "|".join(reasons)})
            quality.append({"ticker": t, "sessions": len(dates), "unique_sessions": len(set(dates)),
                            "duplicate_dates": duplicate, "finite_values": finite, "positive_close_volume": positive,
                            "valid_sessions_20": len(last20), "valid_sessions_60": len(last60),
                            "last_session": last_date, "last_session_age_days": (AS_OF - datetime.strptime(last_date, "%Y-%m-%d").date()).days if last_date else None,
                            "max_abs_daily_return": float(rets.abs().max()) if len(rets) else None,
                            "adv20_finite": adv20 is not None and math.isfinite(adv20),
                            "adv60_finite": adv60 is not None and math.isfinite(adv60),
                            "quality_status": qstatus, "quality_reason": "|".join(reasons)})
            for d in dates:
                sessions.append({"ticker": t, "date": d.isoformat(), "close": float(close.loc[d]),
                                 "volume": float(vol.loc[d]), "provider": "yfinance",
                                 "adjustment": "UNADJUSTED_CLOSE_RAW_VOLUME"})
        except Exception as exc:
            agg.append({"ticker": t, "last_completed_session": "", "close": None, "volume": None,
                        "adv20_usd": None, "adv60_usd": None, "valid_sessions_20": 0, "valid_sessions_60": 0,
                        "volume_source": "yfinance", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "price_asof": "", "currency": "USD", "adjustment": "UNADJUSTED_CLOSE_RAW_VOLUME",
                        "liquidity_status": "LIQUIDITY_DATA_BLOCKED", "liquidity_data_quality": "ERROR",
                        "quality_reason": f"{type(exc).__name__}:{str(exc)[:80]}"})
            quality.append({"ticker": t, "sessions": 0, "unique_sessions": 0, "duplicate_dates": False,
                            "finite_values": False, "positive_close_volume": False, "valid_sessions_20": 0,
                            "valid_sessions_60": 0, "last_session": "", "last_session_age_days": None,
                            "max_abs_daily_return": None, "adv20_finite": False, "adv60_finite": False,
                            "quality_status": "LIQUIDITY_DATA_BLOCKED", "quality_reason": f"{type(exc).__name__}:{str(exc)[:80]}"})
    for path, rows in ((OUT, agg), (SESSIONS, sessions), (QUALITY, quality)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    s = {"requested": len(ts), "ok": sum(1 for r in agg if r["liquidity_status"] == "LIQUIDITY_VALID"),
         "stale": sum(1 for r in agg if r["liquidity_status"] == "LIQUIDITY_STALE"),
         "corporate_action_review": sum(1 for r in agg if r["liquidity_status"] == "LIQUIDITY_CORPORATE_ACTION_REVIEW"),
         "invalid_sessions": sum(1 for r in agg if r["liquidity_status"] == "LIQUIDITY_INVALID_SESSIONS"),
         "blocked": sum(1 for r in agg if r["liquidity_status"] == "LIQUIDITY_DATA_BLOCKED"),
         "retrieved_at": datetime.now(timezone.utc).isoformat(), "source": "yfinance",
         "as_of": AS_OF.isoformat(), "adjustment": "UNADJUSTED_CLOSE_RAW_VOLUME",
         "session_rows": len(sessions), "quality_rows": len(quality),
         "note": "Manual/dispatch snapshot; regular CI uses fixed files."}
    SUMMARY.write_text(json.dumps(s, indent=2), encoding="utf-8")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
