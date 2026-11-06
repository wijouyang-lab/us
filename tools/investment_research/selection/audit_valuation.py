"""P6.16 Value Top50 valuation integrity audit.

Checks internal consistency of P6.8/P6.9 inputs; it does not invent external
prices or remove extreme stocks. Suspect stocks remain in the original ranking.
"""
from __future__ import annotations
import argparse, csv, json, math
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path("data/universe/selection")
INPUTS = Path("data/universe/selection_inputs")
READY = INPUTS / "value_v1_readiness_p68.csv"
QUOTES = INPUTS / "us_market_quote_mapping_p62.csv"
LIQUIDITY = INPUTS / "liquidity_ohlcv_p616.csv"
AS_OF = date(2026, 11, 5)


def read(p):
    b = p.read_bytes()[:2]
    with p.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "valuation_integrity_audit.csv")
    ap.add_argument("--summary", type=Path, default=ROOT / "valuation_integrity_summary.json")
    a = ap.parse_args()
    top = read(ROOT / "value_top50.csv")
    ready = {r["ticker"]: r for r in read(READY)}
    quotes = {r["ticker"]: r for r in read(QUOTES)}
    liq = {r["ticker"]: r for r in read(LIQUIDITY)} if LIQUIDITY.exists() else {}
    rows = []
    for r in top:
        t = r["ticker"]; rd = ready.get(t, {}); q = quotes.get(t, {})
        price = num(rd.get("price")); sec_shares = num(rd.get("sec_shares"))
        mcap = num(rd.get("market_cap_raw")); quote_price = num(q.get("quote_price"))
        mcap_calc = price * sec_shares if price and sec_shares else None
        cfo = num(rd.get("operating_cash_flow")); capex = num(rd.get("capital_expenditure"))
        fcf_calc = cfo - abs(capex) if cfo is not None and capex is not None else None
        fcf_reported = num(rd.get("free_cash_flow"))
        pe = num(rd.get("pe_derived")); ey = num(rd.get("earnings_yield"))
        ext = liq.get(t, {}); ext_close = num(ext.get("close")); ext_session = ext.get("last_completed_session", "")
        ext_diff = ((ext_close - price) / price * 100) if ext_close and price else None
        reasons = []
        status = "VALUATION_VALID"
        if not all(x is not None for x in (price, sec_shares, mcap, quote_price, cfo, capex, fcf_reported, pe, ey)):
            status = "VALUATION_DATA_BLOCKED"; reasons.append("REQUIRED_RAW_INPUT_MISSING")
        elif rd.get("market_cap_status") != "ISSUER_MARKET_CAP_VALIDATED":
            status = "VALUATION_DATA_BLOCKED"; reasons.append("MARKET_CAP_NOT_VALIDATED")
        if status != "VALUATION_DATA_BLOCKED":
            if mcap_calc is None or abs(mcap_calc - mcap) / mcap > 0.01:
                status = "VALUATION_INPUT_SUSPECT"; reasons.append("MARKET_CAP_PRICE_SHARES_MISMATCH")
            if abs(price - quote_price) / quote_price > 0.01 if quote_price else True:
                status = "VALUATION_INPUT_SUSPECT"; reasons.append("P68_PRICE_VS_P62_QUOTE_MISMATCH")
            if fcf_calc is None or abs(fcf_calc - fcf_reported) / abs(fcf_reported) > 0.01 if fcf_reported else True:
                status = "VALUATION_INPUT_SUSPECT"; reasons.append("FCF_RECONCILIATION_MISMATCH")
            if abs(ey * pe - 1) > 1e-4:
                status = "VALUATION_INPUT_SUSPECT"; reasons.append("EARNINGS_YIELD_PE_RECIPROCAL_MISMATCH")
            if ey > 2 or abs(fcf_reported / mcap) > 2 if mcap else False:
                status = "VALUATION_INPUT_SUSPECT"; reasons.append("EXTREME_EARNINGS_OR_FCF_YIELD")
            if (num(rd.get("pb")) or 0) < 0.05 or (num(rd.get("ps")) or 0) < 0.02:
                status = "VALUATION_INPUT_SUSPECT"; reasons.append("EXTREME_PB_OR_PS")
            if mcap < 50_000_000:
                reasons.append("MICROCAP_UNDER_50M")
            if ext_diff is not None and abs(ext_diff) > 10:
                status = "VALUATION_INPUT_SUSPECT"; reasons.append("EXTERNAL_PRICE_DIFF_GT_10PCT")
            pm = num(rd.get("pe_mismatch"))
            if pm is not None and pm > 0.20:
                reasons.append("PROVIDER_PE_MISMATCH_GT_20PCT")
            if r.get("filed") and r.get("filed") > AS_OF.isoformat():
                status = "VALUATION_PERIOD_MISMATCH"; reasons.append("FILED_AFTER_AS_OF")
        rows.append({"ticker": t, "cik": r["cik"], "company_name": r.get("company_name", ""),
                     "price": price, "quote_price": quote_price, "price_source": "P6_2_AKSHARE_BATCH_15MIN_DELAY",
                     "price_asof": "2026-11-05T08:16:00Z", "sec_shares": sec_shares, "market_cap_reported": mcap,
                     "market_cap_calc": mcap_calc, "market_cap_diff_pct": ((mcap_calc-mcap)/mcap*100 if mcap and mcap_calc else None),
                     "pb": rd.get("pb"), "ps": rd.get("ps"), "earnings_yield": ey, "pe_derived": pe,
                     "net_income": rd.get("net_income"), "equity": rd.get("stockholders_equity"),
                     "revenue": rd.get("revenue"), "cfo": cfo, "capex": capex, "fcf_reported": fcf_reported,
                     "fcf_calc": fcf_calc, "external_close": ext_close,
                     "external_session": ext_session, "external_price_diff_pct": ext_diff,
                     "financial_period": r.get("financial_period", ""),
                     "filed": r.get("filed", ""), "valuation_status": status,
                     "valuation_reason": "|".join(dict.fromkeys(reasons))})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "data_as_of": AS_OF.isoformat(),
               "top50": len(rows), "status_counts": dict(Counter(r["valuation_status"] for r in rows)),
               "suspect_tickers": [r["ticker"] for r in rows if r["valuation_status"] != "VALUATION_VALID"],
               "extreme_tickers": [r["ticker"] for r in rows if "EXTREME" in r["valuation_reason"]],
               "validation_checks": ["market_cap = price * sec_shares (1%)", "P6.8 price vs P6.2 quote (1%)",
                                     "FCF = CFO - |capex| (1%)", "EY * derived PE ~= 1", "filed <= as_of"],
               "note": "Suspect status does not delete the original ranking; composite permissions remain separate."}
    a.summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(json.dumps([{k: r[k] for k in ("ticker","market_cap_calc","pb","ps","earnings_yield","fcf_reported","valuation_status","valuation_reason")} for r in rows[:10]], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
