"""Build P5.3 Value market-cap reconciliation from existing quote report + SEC shares.

No network calls. The quote values come from the recorded P5.2 AkShare live run.
"""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path

QUOTES = Path("data/research/akshare_us_28_coverage_2026-11-04.json")
SHARES = Path("data/research/sec_shares_outstanding_28.json")
OUT = Path("data/research/value_share_class_reconciliation_2026-11-05.json")


def main():
    quotes = json.loads(QUOTES.read_text(encoding="utf-8"))
    shares = json.loads(SHARES.read_text(encoding="utf-8"))["companies"]
    companies = {}
    ready = 0
    for ticker, quote in quotes["companies"].items():
        s = shares.get(ticker, {})
        price = quote.get("quote_price")
        raw_cap = quote.get("quote_market_cap_raw")
        sh = s.get("shares")
        as_of = s.get("as_of") or s.get("period_end")
        age = None
        if as_of:
            try: age = (date.today() - date.fromisoformat(as_of)).days
            except ValueError: pass
        estimated = price * sh if price and sh else None
        ratio = raw_cap / estimated if raw_cap and estimated else None
        ok = bool(ratio is not None and abs(ratio - 1.0) <= 0.10
                  and age is not None and age <= 183)
        if ok: ready += 1
        companies[ticker] = {
            "ticker": ticker,
            "quote_price": price,
            "quote_market_cap_raw": raw_cap,
            "quote_pe_raw": quote.get("quote_pe_raw"),
            "sec_shares": sh,
            "shares_basis": s.get("shares_basis"),
            "shares_as_of": as_of,
            "shares_filed": s.get("filed"),
            "shares_accession": s.get("accession"),
            "shares_form": s.get("form"),
            "shares_source_url": s.get("source_url"),
            "shares_age_days": age,
            "estimated_market_cap": estimated,
            "market_cap_ratio": ratio,
            "value_market_cap_input_ready": ok,
            "score_ready": False,
            "backtest_ready": False,
            "status": "VALUE_MARKET_CAP_INPUT_READY" if ok else "VALUE_MARKET_CAP_INPUT_BLOCKED",
        }
    data = {
        "metadata": {
            "generated_at": "2026-11-05T00:00:00Z",
            "method": "AkShare quote price x SEC disclosed shares; compare with AkShare total market cap",
            "quote_source": str(QUOTES),
            "quote_run": quotes["metadata"].get("verification_run_url"),
            "shares_source": str(SHARES),
            "currency": "USD",
            "currency_status": "US_BOARD_CONVENTION",
            "note": "Market-cap input readiness is not a Value score or backtest readiness.",
        },
        "summary": {
            "companies": len(companies),
            "value_market_cap_input_ready": ready,
            "score_ready": 0,
            "backtest_ready": 0,
            "share_class_corrected": ["NKE", "BRK.B", "NEE", "DUK", "PLD"],
        },
        "companies": companies,
    }
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(data["summary"])
    for t in ("NKE", "BRK.B", "NEE", "DUK", "PLD"):
        print(t, companies[t]["market_cap_ratio"], companies[t]["shares_as_of"], companies[t]["shares_basis"])


if __name__ == "__main__":
    main()
