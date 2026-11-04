"""Dividend quality from SEC facts only, with strict annual period matching."""
from __future__ import annotations
from datetime import date
from statistics import pstdev
from tools.investment_research.metrics import TAGS, Snapshot, _metric, _unavailable, _fact_ref

DPS_TAGS = ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"]
CASH_TAGS = ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"]
BUYBACK_TAGS = ["PaymentsForRepurchaseOfCommonStock"]
DEBT_REPAY_TAGS = ["RepaymentsOfLongTermDebt", "RepaymentsOfDebt"]
SCORE_VERSION = "dividend-score-2.0"
FIN_INDUSTRIES = {"banking","banks","insurance","reit","real estate","financials"}


def _annual_concept(s: Snapshot, concept, unit):
    by = {}
    for f in s.available():
        if f.concept == concept and f.unit == unit and f.start:
            days = (date.fromisoformat(f.end) - date.fromisoformat(f.start)).days
            if 330 <= days <= 400:
                if f.end not in by or f.filed > by[f.end].filed: by[f.end] = f
    return [by[k] for k in sorted(by)]


def _best_series(s: Snapshot, concepts, unit):
    choices = [(c, _annual_concept(s, c, unit)) for c in concepts]
    choices = [(c, x) for c, x in choices if x]
    if not choices: return [], None
    c, x = max(choices, key=lambda z: (len(z[1]), z[1][-1].end))
    return x, c


def _d(x, unit="USD"):
    if not x: return None
    f = x[-1]
    return {"value": f.value, "start": f.start, "end": f.end, "period_type": "FY",
            "fiscal_year": f.fy, "fiscal_period": f.fp, "facts": [f], "unit": f.unit,
            "concept": f.concept}


def _period(a, b):
    if not (a and b and a.get("start") == b.get("start") and a.get("end") == b.get("end")
            and a.get("period_type") == b.get("period_type") and a.get("unit") == b.get("unit")):
        return False
    # Missing fiscal metadata is allowed; conflicting metadata is not.
    for key in ("fiscal_year", "fiscal_period"):
        if a.get(key) is not None and b.get(key) is not None and a.get(key) != b.get(key):
            return False
    return True


def _align(*series):
    """Return the latest fiscal year present in every series."""
    if not series or any(not x for x in series): return [None] * len(series)
    maps = [{f.end: f for f in x} for x in series]
    common = set(maps[0])
    for m in maps[1:]: common &= set(m)
    if not common: return [None] * len(series)
    end = max(common)
    return [[m[end]] for m in maps]


def _pct(name, num, den, ticker, formula):
    if not num or not den:
        return _unavailable(ticker, name, "ratio", missing="numerator or denominator unavailable", formula=formula)
    if not _period(num, den):
        return _unavailable(ticker, name, "ratio", "PERIOD_MISMATCH", "period/unit/fiscal mismatch", formula)
    if den["value"] <= 0:
        return _unavailable(ticker, name, "ratio", "NOT_APPLICABLE", "denominator <= 0", formula)
    return _metric(ticker, name, num["value"] / den["value"], "ratio", period={
        "start": num["start"], "end": num["end"], "period_type": "FY",
        "facts": num.get("facts", []) + den.get("facts", [])}, formula=formula)


def _cagr(series, n):
    if len(series) < n + 1: return None
    a, b = series[-1-n], series[-1]
    if int(b.end[:4]) - int(a.end[:4]) != n or a.value <= 0: return None
    return (b.value / a.value) ** (1/n) - 1


def _consecutive_years(series):
    return all(int(b.end[:4]) - int(a.end[:4]) == 1 for a, b in zip(series, series[1:]))


def dividend_metrics(s: Snapshot, *, sector: str | None = None, split_basis_verified: bool = False) -> dict:
    out = {}
    dps, dps_concept = _best_series(s, DPS_TAGS, "USD/shares")
    cash_series, cash_concept = _best_series(s, CASH_TAGS, "USD")
    buy_series, buy_concept = _best_series(s, BUYBACK_TAGS, "USD")
    debt_series, debt_concept = _best_series(s, DEBT_REPAY_TAGS, "USD")
    ni_series, _ = _best_series(s, ["NetIncomeLoss"], "USD")
    cfo_series, _ = _best_series(s, TAGS["cfo"], "USD")
    cap_series, _ = _best_series(s, TAGS["capex"], "USD")
    cash = _d(cash_series); ni = _d(ni_series); buy = _d(buy_series); debt = _d(debt_series)
    # Align payout to the latest common fiscal year, not merely latest dates.
    c_pay, n_pay = _align(cash_series, ni_series)
    cash_pay = _d(c_pay); ni_pay = _d(n_pay)
    fcf = None
    c_fcf, cfo_f, cap_f = _align(cash_series, cfo_series, cap_series)
    if cfo_f and cap_f:
        cfo = cfo_f[0]; cap = cap_f[0]
        if cfo.end == cap.end:
            fcf = {"value": cfo.value - abs(cap.value), "start": cfo.start, "end": cfo.end,
                   "period_type": "FY", "fiscal_year": cfo.fy, "fiscal_period": cfo.fp,
                   "facts": [cfo, cap], "unit": "USD", "concept": "CFO-abs(CapEx)"}
    cash_fcf = _d(c_fcf)
    if not dps and not cash:
        has_tag = any(f.concept in DPS_TAGS + CASH_TAGS for f in s.available())
        out["classification"] = _unavailable(s.ticker, "dividend_classification", "text",
            "DIVIDEND_DATA_BLOCKED" if has_tag else "NON_DIVIDEND_PAYER",
            "tags exist but no usable annual series" if has_tag else "no SEC dividend tags")
        out["dividend_payer"] = False
    else:
        p = {"start": (dps[0].start if dps else cash["start"]), "end": (dps[-1].end if dps else cash["end"]),
             "period_type": "FY", "facts": ([dps[-1]] if dps else cash["facts"])}
        out["classification"] = _metric(s.ticker, "dividend_classification", "DIVIDEND_PAYER", "text",
            period=p, formula="SEC dividend tag presence")
        out["dividend_payer"] = True
    out["cash_dividend_concept"] = cash_concept
    out["dps_concept"] = dps_concept
    out["net_income_payout"] = _pct("net_income_payout", cash_pay, ni_pay, s.ticker, "cash_dividends / net_income")
    out["fcf_payout"] = _pct("fcf_payout", cash_fcf, fcf, s.ticker, "cash_dividends / free_cash_flow")
    if not fcf:
        out["fcf_dividend_coverage"] = _unavailable(s.ticker, "fcf_dividend_coverage", "ratio", "DATA_BLOCKED", "FCF unavailable or period mismatch")
    elif not cash_fcf:
        out["fcf_dividend_coverage"] = _unavailable(s.ticker, "fcf_dividend_coverage", "ratio", "PERIOD_MISMATCH", "no common dividend/FCF fiscal year")
    elif not _period(cash_fcf, fcf):
        out["fcf_dividend_coverage"] = _unavailable(s.ticker, "fcf_dividend_coverage", "ratio", "PERIOD_MISMATCH", "dividend/FCF periods differ")
    elif cash_fcf["value"] <= 0:
        out["fcf_dividend_coverage"] = _unavailable(s.ticker, "fcf_dividend_coverage", "ratio", "NOT_APPLICABLE", "zero dividend")
    else:
        out["fcf_dividend_coverage"] = _metric(s.ticker, "fcf_dividend_coverage", fcf["value"]/cash_fcf["value"],
            "ratio", period={"start": fcf["start"], "end": fcf["end"], "period_type": "FY",
                             "facts": fcf["facts"] + cash_fcf["facts"]}, formula="FCF / cash_dividends")
    out["dps_series"] = [_fact_ref(f) for f in dps]
    out["dps_history_years"] = len(dps)
    consecutive_history = len(dps) >= 5 and _consecutive_years(dps[-5:]) and all(f.value > 0 for f in dps[-5:])
    out["dividend_continuity"] = consecutive_history
    out["continuity_status"] = "OK" if consecutive_history else "INSUFFICIENT_HISTORY"
    out["continuity_window"] = [dps[-5].end, dps[-1].end] if consecutive_history else None
    out["dps_split_basis"] = "VERIFIED" if split_basis_verified else "DPS_SPLIT_BASIS_UNVERIFIED"
    if split_basis_verified:
        out["dps_growth_1y"] = _cagr(dps, 1)
        out["dps_cagr_3y"] = _cagr(dps, 3)
        out["dps_cagr_5y"] = _cagr(dps, 5)
    else:
        out["dps_growth_1y"] = out["dps_cagr_3y"] = out["dps_cagr_5y"] = None
    run = 0; window = None
    for i in range(len(dps)-1, 0, -1):
        a, b = dps[i-1], dps[i]
        if int(b.end[:4]) - int(a.end[:4]) != 1 or a.value <= 0 or b.value <= a.value: break
        run += 1; window = [a.end, b.end]
    raw_consecutive = run; raw_total = sum(1 for a,b in zip(dps,dps[1:])
        if int(b.end[:4])-int(a.end[:4]) == 1 and a.value > 0 and b.value > a.value)
    raw_cuts = sum(1 for a,b in zip(dps,dps[1:])
        if int(b.end[:4])-int(a.end[:4]) == 1 and a.value > 0 and (b.value-a.value)/a.value < -0.05)
    raw_vol = pstdev([(b.value-a.value)/a.value for a,b in zip(dps,dps[1:]) if a.value>0 and int(b.end[:4])-int(a.end[:4])==1]) if len(dps)>2 else None
    out["raw_consecutive_growth_years"] = raw_consecutive
    out["raw_total_positive_growth_years"] = raw_total
    out["raw_dividend_cuts"] = raw_cuts
    out["raw_dps_volatility"] = raw_vol
    out["growth_status"] = "OK" if split_basis_verified else "DPS_SPLIT_BASIS_UNVERIFIED"
    if split_basis_verified:
        out["consecutive_growth_years"] = raw_consecutive
        out["consecutive_growth_window"] = window
        out["total_positive_growth_years"] = raw_total
        out["dividend_cuts"] = raw_cuts
        out["dps_volatility"] = raw_vol
    else:
        out["consecutive_growth_years"] = None
        out["consecutive_growth_window"] = None
        out["total_positive_growth_years"] = None
        out["dividend_cuts"] = None
        out["dps_volatility"] = None
    alloc = {"dividends": cash["value"] if cash else None, "buybacks": buy["value"] if buy else None,
             "debt_repayment": debt["value"] if debt else None,
             "cfo": cfo_series[-1].value if cfo_series else None, "fcf": fcf["value"] if fcf else None}
    out["capital_allocation"] = alloc
    out["capital_allocation_concepts"] = {"dividends": cash_concept, "buybacks": buy_concept,
                                          "debt_repayment": debt_concept}
    comps = {}
    if out["net_income_payout"]["status"] == "OK":
        p = out["net_income_payout"]["value"]; comps["payout"] = max(0.0, 1 - max(0.0, p-0.5)/0.5)
    if out["fcf_dividend_coverage"]["status"] == "OK" and (sector or "").lower() not in FIN_INDUSTRIES:
        comps["fcf_coverage"] = min(1.0, out["fcf_dividend_coverage"]["value"]/2.0)
    if split_basis_verified and out["dps_cagr_5y"] is not None:
        comps["dps_growth"] = min(1.0, max(0.0, out["dps_cagr_5y"]/0.08))
    if consecutive_history:
        comps["continuity"] = 1.0
    industry_specific = (sector or "").lower() in FIN_INDUSTRIES
    out["score_version"] = SCORE_VERSION
    out["score_components"] = comps
    out["score_component_count"] = len(comps)
    out["score_weights"] = {k: 1/len(comps) for k in comps} if comps else {}
    out["score_denominator"] = len(comps)
    out["comparison_group"] = "INDUSTRY_SPECIFIC" if industry_specific else "NON_FINANCIAL"
    out["dividend_quality_score"] = round(100*sum(comps.values())/len(comps), 1) if len(comps) >= 3 else None
    if len(comps) < 3:
        out["score_status"] = "NOT_READY"
    elif industry_specific:
        out["score_status"] = "INDUSTRY_SPECIFIC_SCORE"
    else:
        out["score_status"] = "SCORE_READY"
    return out
