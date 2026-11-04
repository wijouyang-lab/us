"""Dividend quality from SEC facts only. No price, no Yahoo/AKShare."""
from __future__ import annotations
from datetime import date
from statistics import pstdev
from tools.investment_research.metrics import (TAGS, Snapshot, _annual, _flow,
    _instant_at, _metric, _period_value, _unavailable, _fact_ref)

DPS_TAGS = ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"]
CASH_TAGS = ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"]
BUYBACK_TAGS = ["PaymentsForRepurchaseOfCommonStock"]
DEBT_REPAY_TAGS = ["RepaymentsOfLongTermDebt", "RepaymentsOfDebt"]


def _annual_concept(s: Snapshot, concepts, unit):
    by = {}
    for f in s.available():
        if f.concept in concepts and f.unit == unit and f.start and 330 <= (date.fromisoformat(f.end)-date.fromisoformat(f.start)).days <= 400:
            if f.end not in by or f.filed > by[f.end].filed: by[f.end] = f
    return [by[k] for k in sorted(by)]


def _best_series(s: Snapshot, concepts, unit):
    candidates = [_annual_concept(s, [c], unit) for c in concepts]
    candidates = [x for x in candidates if x]
    return max(candidates, key=lambda x: (x[-1].end, len(x))) if candidates else []


def _flow_concept(s: Snapshot, concepts, unit="USD"):
    # Cash dividend totals are annual here; never mix with quarterly DPS.
    a = _annual_concept(s, concepts, unit)
    if a:
        f = a[-1]
        return {"value": f.value, "period_type": "FY", "start": f.start, "end": f.end,
                "facts": [f], "fiscal_year": f.fy, "fiscal_period": f.fp or "FY"}
    return None


def _pct(name, num, den, ticker, formula, period, missing_na="denominator <= 0"):
    if not num or not den:
        return _unavailable(ticker, name, "ratio", missing="numerator or denominator unavailable", formula=formula)
    if den["value"] <= 0:
        return _unavailable(ticker, name, "ratio", "NOT_APPLICABLE", missing_na, formula)
    return _metric(ticker, name, num["value"] / den["value"], "ratio", period={
        "start": num.get("start"), "end": num.get("end"), "period_type": num.get("period_type"),
        "facts": num.get("facts", []) + den.get("facts", [])}, formula=formula)


def _growth(name, series, years):
    if len(series) < years + 1:
        return None
    a, b = series[-1-years], series[-1]
    if int(b.end[:4]) - int(a.end[:4]) != years or a.value <= 0:
        return None
    return (b.value / a.value) ** (1 / years) - 1


def dividend_metrics(s: Snapshot, *, sector: str | None = None) -> dict:
    out = {}
    dps = _best_series(s, DPS_TAGS, "USD/shares")
    cash = _flow_concept(s, CASH_TAGS)
    buyback = _flow_concept(s, BUYBACK_TAGS)
    debt_repay = _flow_concept(s, DEBT_REPAY_TAGS, "USD")
    cfo = _flow(s, "cfo"); capex = _flow(s, "capex")
    ni = _flow(s, "net_income")
    fcf = None
    if cfo and capex and cfo["start"] == capex["start"] and cfo["end"] == capex["end"]:
        fcf = {"value": cfo["value"] - abs(capex["value"]), "start": cfo["start"], "end": cfo["end"],
               "period_type": cfo["period_type"], "facts": cfo["facts"] + capex["facts"]}
    # classification
    if not dps and not cash:
        has_tag = any(f.concept in DPS_TAGS + CASH_TAGS for f in s.available())
        status = "DIVIDEND_DATA_BLOCKED" if has_tag else "NON_DIVIDEND_PAYER"
        out["classification"] = _unavailable(s.ticker, "dividend_classification", "text", status,
                                             "dividend tags exist but no usable annual series" if has_tag else "no SEC dividend tags")
        out["dividend_payer"] = False
    else:
        out["classification"] = _metric(s.ticker, "dividend_classification", "DIVIDEND_PAYER", "text",
            period={"start": dps[0].start if dps else cash["start"], "end": dps[-1].end if dps else cash["end"],
                    "period_type": "FY", "facts": ([dps[-1]] if dps else cash["facts"])}, formula="SEC dividend tag presence")
        out["dividend_payer"] = True
    out["net_income_payout"] = _pct("net_income_payout", cash, ni, s.ticker,
        "cash_dividends / net_income", cash)
    out["fcf_payout"] = _pct("fcf_payout", cash, fcf, s.ticker,
        "cash_dividends / free_cash_flow", fcf)
    if not fcf:
        out["fcf_dividend_coverage"] = _unavailable(s.ticker, "fcf_dividend_coverage", "ratio", "DATA_BLOCKED", "FCF unavailable or period mismatch")
    elif not cash:
        out["fcf_dividend_coverage"] = _unavailable(s.ticker, "fcf_dividend_coverage", "ratio", "NOT_APPLICABLE", "no cash dividend")
    elif cash["value"] <= 0:
        out["fcf_dividend_coverage"] = _unavailable(s.ticker, "fcf_dividend_coverage", "ratio", "NOT_APPLICABLE", "zero dividend")
    else:
        out["fcf_dividend_coverage"] = _metric(s.ticker, "fcf_dividend_coverage", fcf["value"]/cash["value"],
            "ratio", period={"start": fcf["start"], "end": fcf["end"], "period_type": fcf["period_type"],
                             "facts": fcf["facts"] + cash["facts"]}, formula="FCF / cash_dividends")
    # per-share growth; never use cash-total as DPS growth
    out["dps_series"] = [_fact_ref(f) for f in dps]
    out["dps_growth_1y"] = _growth("dps_growth_1y", dps, 1)
    out["dps_cagr_3y"] = _growth("dps_cagr_3y", dps, 3)
    out["dps_cagr_5y"] = _growth("dps_cagr_5y", dps, 5)
    growths = []
    cuts = 0; consecutive = 0
    for a, b in zip(dps, dps[1:]):
        g = (b.value - a.value) / a.value if a.value > 0 else None
        growths.append(g)
        if g is not None and g > 0: consecutive += 1
        if g is not None and g < -0.05: cuts += 1
    out["consecutive_growth_years"] = consecutive
    out["dividend_cuts"] = cuts
    out["dps_history_years"] = len(dps)
    out["dps_volatility"] = pstdev(growths) if len(growths) > 1 and all(g is not None for g in growths) else None
    # stability (FCF/earnings coverage over annual history)
    fcf_cover = []
    for c in _annual_concept(s, CASH_TAGS, "USD"):
        cf = _annual_concept(s, TAGS["cfo"], "USD"); cap = _annual_concept(s, TAGS["capex"], "USD")
        cf = next((x for x in cf if x.end == c.end), None); cap = next((x for x in cap if x.end == c.end), None)
        if cf and cap and c.value > 0: fcf_cover.append((cf.value-abs(cap.value))/c.value)
    out["fcf_coverage_stability"] = pstdev(fcf_cover) if len(fcf_cover) > 1 else None
    out["dividend_continuity"] = len(dps) >= 5 and all(x.value > 0 for x in dps[-5:])
    # capital allocation, all same annual cash-flow period where possible
    alloc = {}
    for name, d in (("dividends", cash), ("buybacks", buyback), ("debt_repayment", debt_repay),
                    ("cfo", cfo), ("fcf", fcf)):
        alloc[name] = d["value"] if d else None
    out["capital_allocation"] = alloc
    out["capital_allocation_inputs"] = [x for d in (cash, buyback, debt_repay, cfo, fcf) if d for x in d.get("facts", [])]
    # score: only available evidence; no missing-as-zero
    parts = {}
    if out["net_income_payout"]["status"] == "OK":
        p = out["net_income_payout"]["value"]; parts["payout"] = max(0.0, 1 - max(0.0, p-0.5)/0.5)
    if out["fcf_dividend_coverage"]["status"] == "OK":
        c = out["fcf_dividend_coverage"]["value"]; parts["coverage"] = min(1.0, c/2.0)
    if out["dps_cagr_5y"] is not None: parts["growth"] = min(1.0, max(0.0, out["dps_cagr_5y"]/0.08))
    if out["dividend_continuity"] is not None: parts["continuity"] = 1.0 if out["dividend_continuity"] else 0.0
    out["score_components"] = parts
    out["dividend_quality_score"] = round(100*sum(parts.values())/len(parts), 1) if len(parts) >= 3 else None
    out["score_status"] = "OK" if len(parts) >= 3 else "NOT_READY"
    return out
