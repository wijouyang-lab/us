"""Persistent RESEARCH_SHADOW_P7 tracker.

Default (CI) is offline and preserves the existing state. `--refresh` may fill
only after a complete next-session OHLCV bar exists; otherwise it stays PENDING.
This module never touches PAPER-50000.
"""
from __future__ import annotations
import argparse, csv, json, math, tempfile
from datetime import date, datetime, timezone
from pathlib import Path


P7 = Path("data/universe/p7")
STATE = P7 / "shadow_state.json"
POSITIONS = P7 / "shadow_positions.csv"
FILLS = P7 / "shadow_fills.csv"
NAV = P7 / "shadow_nav.csv"
AS_OF = date(2026, 11, 5)
INITIAL = 50000.0
SLIPPAGE_BPS = 5.0
COMMISSION_BPS = 0.5


def read(p):
    b = p.read_bytes()[:2]
    with p.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None


def write_csv(path, rows, fields=None):
    if not rows: return
    fields = fields or list(dict.fromkeys([k for r in rows for k in r]))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def load_state():
    if STATE.exists(): return json.loads(STATE.read_text(encoding="utf-8"))
    return {"shadow_id": "RESEARCH_SHADOW_P7", "status": "INITIALIZED_PENDING_NEXT_SESSION",
            "signal_date": AS_OF.isoformat(), "next_tradable_session": "2026-11-06",
            "paper_account_untouched": True, "paper_account_read": False, "paper_account_write": False,
            "initial_capital": INITIAL, "filled": False, "execution_status": "PENDING_NEXT_SESSION"}


def target_rows(strategy="VALUE_V1"):
    ws = read(P7 / "portfolio_weights.csv")
    rows = [r for r in ws if r["strategy"] == strategy and r["variant"] == "risk_adjusted"]
    return rows or [r for r in ws if r["strategy"] == strategy]


def pending(strategy, state, reason):
    target = target_rows(strategy)
    pos = [{"shadow_id": "RESEARCH_SHADOW_P7", "signal_date": state.get("signal_date", AS_OF.isoformat()),
            "ticker": r["ticker"], "target_weight": r["weight"], "target_notional_usd": r["target_notional_usd"],
            "status": "PENDING_NEXT_SESSION", "execution_date": "", "fill_price": "", "shares": "",
            "reason": reason} for r in target]
    nav = [{"date": state.get("signal_date", AS_OF.isoformat()), "shadow_id": "RESEARCH_SHADOW_P7",
            "nav": INITIAL, "cash": INITIAL, "positions_value": 0.0, "fees": 0.0, "turnover": 0.0,
            "status": "PENDING_NEXT_SESSION" if reason == "NEXT_TRADABLE_SESSION_PRICE_REQUIRED" else "PENDING_MISSING_PRICES",
            "spy_return": "", "qqq_return": "", "iwm_return": "",
            "note": "No fill is fabricated before a complete next session."}]
    write_csv(POSITIONS, pos)
    write_csv(NAV, nav)
    if not FILLS.exists():
        FILLS.write_text("shadow_id,session,ticker,side,shares,reference_open,execution_price,gross_notional,slippage_bps,commission,close,market_value,status\n", encoding="utf-8")
    state.update({"status": nav[0]["status"], "execution_status": nav[0]["status"], "reason": reason, "holdings": len(pos), "cash_weight": 0.05})
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def refresh(strategy="VALUE_V1"):
    state = load_state()
    if state.get("filled"):
        return state  # idempotent: never overwrite a completed fill
    target = target_rows(strategy)
    tickers = [r["ticker"] for r in target]
    session = state.get("next_tradable_session", "2026-11-06")
    try:
        import yfinance as yf
        yf.set_tz_cache_location(tempfile.mkdtemp(prefix="p7-shadow-"))
        data = yf.download(tickers, start=session, end="2026-11-07", interval="1d",
                           auto_adjust=False, actions=True, threads=False, progress=False, group_by="ticker")
    except Exception as exc:
        return pending(strategy, state, f"PROVIDER_ERROR:{type(exc).__name__}")
    if data is None or len(data) == 0:
        return pending(strategy, state, "NO_COMPLETED_NEXT_SESSION")
    fills = []; cash = INITIAL; fees_total = 0.0
    for r in target:
        t = r["ticker"]
        try:
            frame = data[t] if hasattr(data.columns, "levels") else data
            frame = frame.dropna(subset=["Open", "Close"])
            row = frame[frame.index.date == date.fromisoformat(session)]
        except Exception:
            return pending(strategy, state, f"MISSING_OR_INCOMPLETE:{t}")
        if len(row) != 1:
            return pending(strategy, state, f"MISSING_OR_INCOMPLETE:{t}")
        row = row.iloc[0]
        split = num(row.get("Stock Splits", 0)) if hasattr(row, "get") else 0
        if split not in (None, 0):
            return pending(strategy, state, f"CORPORATE_ACTION_UNHANDLED:{t}")
        ref_open = num(row.get("Open")); ref_close = num(row.get("Close"))
        if ref_open is None or ref_close is None or ref_open <= 0:
            return pending(strategy, state, f"INVALID_PRICE:{t}")
        exec_price = ref_open * (1 + SLIPPAGE_BPS / 10000)
        notional = float(r["target_notional_usd"])
        shares = math.floor(notional / exec_price)
        gross = shares * exec_price
        comm = gross * COMMISSION_BPS / 10000
        cash -= gross + comm; fees_total += comm
        fills.append({"shadow_id": "RESEARCH_SHADOW_P7", "session": session, "ticker": t,
                      "side": "BUY", "shares": shares, "reference_open": ref_open,
                      "execution_price": round(exec_price, 6), "gross_notional": round(gross, 6),
                      "slippage_bps": SLIPPAGE_BPS, "commission": round(comm, 6),
                      "close": ref_close, "market_value": round(shares * ref_close, 6),
                      "status": "FILLED_RESEARCH_ONLY"})
    if cash < 0:
        return pending(strategy, state, "INSUFFICIENT_CASH")
    positions_value = sum(x["market_value"] for x in fills)
    nav = cash + positions_value
    write_csv(FILLS, fills)
    pos = [{"shadow_id": "RESEARCH_SHADOW_P7", "signal_date": state.get("signal_date", AS_OF.isoformat()),
            "ticker": x["ticker"], "target_weight": next(r["weight"] for r in target if r["ticker"] == x["ticker"]),
            "target_notional_usd": next(r["target_notional_usd"] for r in target if r["ticker"] == x["ticker"]),
            "status": "FILLED_RESEARCH_ONLY", "execution_date": session,
            "fill_price": x["execution_price"], "shares": x["shares"], "reason": ""} for x in fills]
    write_csv(POSITIONS, pos)
    write_csv(NAV, [{"date": session, "shadow_id": "RESEARCH_SHADOW_P7", "nav": round(nav, 6),
                      "cash": round(cash, 6), "positions_value": round(positions_value, 6),
                      "fees": round(fees_total, 6), "turnover": round(sum(x["gross_notional"] for x in fills) / INITIAL, 8),
                      "status": "FILLED_RESEARCH_ONLY", "spy_return": "", "qqq_return": "", "iwm_return": "",
                      "note": "First complete-session open fill; close valuation."}])
    state.update({"status": "FILLED_RESEARCH_ONLY", "filled": True, "fill_date": session,
                  "holds": len(fills), "cash": round(cash, 6), "fees": round(fees_total, 6)})
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    strategy = "VALUE_V1"
    state = refresh(strategy) if a.refresh else load_state()
    if not a.refresh:
        # preserve any existing completed artifacts; initialize only when absent.
        if STATE.exists() and state.get("filled"):
            print(json.dumps({"status": state.get("status"), "filled": True, "idempotent": True}, indent=2)); return 0
        state = pending(strategy, state, "NEXT_TRADABLE_SESSION_PRICE_REQUIRED")
    status = {"generated_at": datetime.now(timezone.utc).isoformat(), "status": "P7_RESEARCH_READY",
              "research_only": True, "as_of": AS_OF.isoformat(), "shadow": state,
              "strategies": json.loads((P7 / "portfolio_risk_summary.json").read_text(encoding="utf-8"))["strategies"],
              "strategy_candidates": read(P7 / "strategy_candidates.csv"),
              "portfolio_risk": json.loads((P7 / "portfolio_risk_summary.json").read_text(encoding="utf-8")),
              "target_weights": target_rows(strategy),
              "shadow_nav": read(NAV)[-1] if NAV.exists() and read(NAV) else {},
              "benchmarks": json.loads((P7 / "benchmark_summary.json").read_text(encoding="utf-8")),
              "not_claimed": ["No Alpha", "No PIT backtest", "No PAPER-50000 interaction", "Not a BUY/SELL signal"]}
    (P7 / "p7_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({"status": state.get("status"), "filled": state.get("filled"), "date": state.get("fill_date", "")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
