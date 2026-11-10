"""P6.17 independent arithmetic recalculation of Value Top50 ratios.

Raw inputs come from P6.8/P6.9; the output is separate from the original ranking.
Formula:
  mcap = price * sec_shares
  P/B = mcap / equity; P/S = mcap / revenue
  EY = net_income / mcap; PE = mcap / net_income
  FCF = CFO - |CapEx|; FCF yield = FCF / mcap
"""
from __future__ import annotations
import csv, json, math
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path("data/universe/selection")
INPUTS = Path("data/universe/selection_inputs")
READY = INPUTS / "value_v1_readiness_p68.csv"
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


def diff(a, b):
    if a is None or b is None or b == 0: return None
    return abs(a - b) / abs(b)


def main():
    top = read(ROOT / "value_top50.csv")
    ready = {r["ticker"]: r for r in read(READY)}
    hist = {}
    hp = ROOT / "sec_filing_history_p617.csv"
    if hp.exists():
        for h in read(hp):
            hist[h["accessionNumber"]] = h
    rows = []
    for r in top:
        q = ready.get(r["ticker"], {})
        price = num(q.get("price")); shares = num(q.get("sec_shares"))
        mcap = num(q.get("market_cap_raw")); equity = num(q.get("stockholders_equity"))
        revenue = num(q.get("revenue")); ni = num(q.get("net_income"))
        cfo = num(q.get("operating_cash_flow")); capex = num(q.get("capital_expenditure"))
        pb0 = num(q.get("pb")); ps0 = num(q.get("ps")); ey0 = num(q.get("earnings_yield"))
        pe0 = num(q.get("pe_derived")); fcf0 = num(q.get("free_cash_flow"))
        missing = [k for k, v in (("price", price), ("sec_shares", shares), ("equity", equity),
                                  ("revenue", revenue), ("net_income", ni), ("cfo", cfo), ("capex", capex)) if v is None]
        mcap_calc = price * shares if price and shares else None
        pb_calc = mcap_calc / equity if mcap_calc and equity and equity > 0 else None
        ps_calc = mcap_calc / revenue if mcap_calc and revenue and revenue > 0 else None
        ey_calc = ni / mcap_calc if ni is not None and mcap_calc and mcap_calc > 0 else None
        pe_calc = mcap_calc / ni if ni is not None and ni != 0 and mcap_calc else None
        fcf_calc = cfo - abs(capex) if cfo is not None and capex is not None else None
        fcfy_calc = fcf_calc / mcap_calc if fcf_calc is not None and mcap_calc and mcap_calc > 0 else None
        reasons = []; extreme = []
        if missing:
            status = "VALUATION_DATA_BLOCKED"
        elif r.get("filed") and r["filed"] > AS_OF.isoformat():
            status = "VALUATION_PERIOD_MISMATCH"; reasons.append("FILED_AFTER_AS_OF")
        elif not q.get("market_cap_status") == "ISSUER_MARKET_CAP_VALIDATED":
            status = "VALUATION_SHARES_STALE_OR_UNVERIFIED"; reasons.append("MARKET_CAP_NOT_VALIDATED")
        else:
            diffs = {"pb": diff(pb_calc, pb0), "ps": diff(ps_calc, ps0), "ey": diff(ey_calc, ey0),
                     "pe": diff(pe_calc, pe0), "fcf": diff(fcf_calc, fcf0), "mcap": diff(mcap_calc, mcap)}
            reasons = [k + "_RECALC_DIFF" for k, v in diffs.items() if v is not None and v > 0.01]
            ratios = [num(q.get("shares_ratio"))]
            if any(x is not None and abs(x - 1) > 0.01 for x in ratios):
                reasons.append("SHARES_RATIO_OUTSIDE_1PCT")
            status = "VALUATION_RECALCULATION_MISMATCH" if reasons else "VALUATION_RECALCULATED_VALID"
            if ey_calc is not None and ey_calc > 2: extreme.append("EXTREME_EY_GT_200PCT")
            if pb_calc is not None and pb_calc < 0.05: extreme.append("EXTREME_PB_LT_0_05")
            if ps_calc is not None and ps_calc < 0.02: extreme.append("EXTREME_PS_LT_0_02")
            if mcap_calc is not None and mcap_calc < 50_000_000: extreme.append("MICROCAP_UNDER_50M")
        rows.append({"ticker": r["ticker"], "cik": r["cik"], "company_name": r.get("company_name", ""),
                     "price": price, "price_source": "P6_8_VALUE_READINESS", "price_asof": "UNKNOWN_QUOTE_TIMESTAMP",
                     "sec_shares": shares, "shares_ratio": q.get("shares_ratio"), "market_cap_reported": mcap,
                     "market_cap_calc": mcap_calc, "equity": equity, "revenue": revenue, "net_income": ni,
                     "cfo": cfo, "capex": capex, "fcf_recalc": fcf_calc,
                     "pb_calc": pb_calc, "pb_reported": pb0, "ps_calc": ps_calc, "ps_reported": ps0,
                     "ey_calc": ey_calc, "ey_reported": ey0, "pe_calc": pe_calc, "pe_reported": pe0,
                     "fcfy_calc": fcfy_calc, "fcfy_reported": (fcf0 / mcap if fcf0 and mcap else None),
                     "financial_period": r.get("financial_period", ""), "filed": r.get("filed", ""),
                     "accn": r.get("accn", ""), "form": hist.get(r.get("accn", ""), {}).get("form", "NOT_FOUND_IN_SUBMISSIONS"),
                     "unit": "USD", "currency": "USD",
                     "unit_currency_status": "ASSUMED_USD_FROM_P6_3", "taxonomy_tag": "NOT_IN_VALUE_READINESS_FILE",
                     "recalc_status": status, "recalc_reason": "|".join(reasons),
                     "extreme_flags": "|".join(extreme)})
    out = ROOT / "valuation_recalculation_audit_p617.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "data_as_of": AS_OF.isoformat(),
               "rows": len(rows), "status_counts": dict(Counter(r["recalc_status"] for r in rows)),
               "mismatch_tickers": [r["ticker"] for r in rows if r["recalc_status"] != "VALUATION_RECALCULATED_VALID"],
               "shares_stale_or_unverified_tickers": [r["ticker"] for r in rows if "SHARES_RATIO_OUTSIDE_1PCT" in r["recalc_reason"]],
               "extreme_tickers": [r["ticker"] for r in rows if r["extreme_flags"]],
               "formula_version": "P6.17_VALUE_RECALC_v1",
               "boundary": "Raw P6.8 values and P6.9 period/accession; XBRL tags not present in readiness file."}
    (ROOT / "valuation_recalculation_summary_p617.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(json.dumps([{k: r[k] for k in ("ticker","market_cap_calc","pb_calc","ps_calc","ey_calc","fcf_recalc","recalc_status","recalc_reason","extreme_flags")} for r in rows[:5]], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
