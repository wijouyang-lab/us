"""P2.1 Value / Quality / GARP metrics with strict period and PIT rules.

Every OK metric carries complete input facts, a formula version and an explicit
period. FY values are never labelled TTM. Missing values are never zero-filled.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from tools.investment_research.sec.normalize import Fact, duration_days

TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "pretax_income": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItems",
                       "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "tax_expense": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "eps_basic": ["EarningsPerShareBasic"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "equity": ["StockholdersEquity"],
    "assets": ["Assets"], "current_assets": ["AssetsCurrent"], "current_liabilities": ["LiabilitiesCurrent"],
    "long_term_debt": ["LongTermDebtNoncurrent"],
    "total_long_term_debt": ["LongTermDebt"],
    "current_ltd": ["LongTermDebtCurrent"],
    "short_term_debt": ["ShortTermBorrowings", "DebtCurrent"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "shares_outstanding": ["CommonStockSharesOutstanding"],
    "dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "depreciation": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet"],
    "interest_expense": ["InterestExpense", "InterestExpenseDebt", "InterestAndDebtExpense", "InterestExpenseNonoperating"],
}

SPECIAL_SECTORS = {"financials", "banks", "insurance", "bank", "reit", "real estate"}


def _parse_as_of(as_of: str | None) -> tuple[datetime | None, bool]:
    if not as_of: return None, False
    if "T" not in as_of:
        return datetime.fromisoformat(as_of).replace(tzinfo=timezone.utc), True
    dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    if dt.tzinfo is None: raise ValueError("as_of timestamp must include timezone")
    return dt.astimezone(timezone.utc), False


@dataclass
class Snapshot:
    ticker: str; cik: str; facts: list[Fact]; as_of: str | None = None
    def available(self) -> list[Fact]:
        ts, date_only = _parse_as_of(self.as_of)
        if ts is None: return list(self.facts)
        out = []
        for f in self.facts:
            if date_only:
                # Conservative date rule: a filing is usable only after its filed date.
                if f.filed and date.fromisoformat(f.filed) < ts.date(): out.append(f)
            elif f.availability_quality == "OBSERVED_FIRST_SEEN" and f.first_seen_at:
                if datetime.fromisoformat(f.first_seen_at.replace("Z", "+00:00")) <= ts: out.append(f)
            elif f.availability_quality == "ACCEPTANCE_ESTIMATE" and f.accepted_at:
                if datetime.fromisoformat(f.accepted_at.replace("Z", "+00:00")) <= ts: out.append(f)
            elif f.availability_quality == "FILED_DATE_ONLY" and f.filed:
                # No exact time exists; same-day intraday is conservatively excluded.
                if date.fromisoformat(f.filed) < ts.date(): out.append(f)
        return out


def _fact_ref(f: Fact) -> dict:
    return {"concept": f.concept, "value": f.value, "unit": f.unit, "start": f.start,
            "end": f.end, "filed": f.filed, "accepted_at": f.accepted_at,
            "first_seen_at": f.first_seen_at, "availability_quality": f.availability_quality,
            "accession": f.accession, "form": f.form, "taxonomy": f.taxonomy}


def _latest_filed(facts: Iterable[Fact]) -> Fact | None:
    x = list(facts)
    return sorted(x, key=lambda f: (f.end, f.filed, f.accession))[-1] if x else None


def _instant_at(s: Snapshot, concepts: list[str], target_end: str, unit="USD") -> Fact | None:
    cand = [f for f in s.available() if f.concept in concepts and f.unit == unit
            and not f.start and f.end <= target_end]
    return _latest_filed(cand)


def _annual(s: Snapshot, key: str, unit="USD") -> list[Fact]:
    best = {}
    for f in s.available():
        if f.concept in TAGS[key] and f.unit == unit and f.start and 330 <= duration_days(f.start, f.end) <= 400:
            if f.end not in best or f.filed > best[f.end].filed: best[f.end] = f
    return [best[k] for k in sorted(best)]


def _quarters(s: Snapshot, key: str, unit="USD") -> list[Fact]:
    """Build singleton quarters, allowing validated YTD differences by fiscal year."""
    facts = [f for f in s.available() if f.concept in TAGS[key] and f.unit == unit and f.start]
    by_fy: dict[str, list[Fact]] = {}
    for f in facts:
        fy = str(f.fy or f.end[:4]); by_fy.setdefault(fy, []).append(f)
    out: dict[str, Fact] = {}
    def pick(cands):
        return _latest_filed([f for f in cands if f in facts])
    for fy, group in by_fy.items():
        direct = [f for f in group if 70 <= duration_days(f.start, f.end) <= 100]
        for f in direct:
            if f.end not in out or f.filed > out[f.end].filed: out[f.end] = f
        q1 = pick([f for f in group if 70 <= duration_days(f.start, f.end) <= 100 and f.fp == "Q1"])
        h1 = pick([f for f in group if 160 <= duration_days(f.start, f.end) <= 200])
        q9 = pick([f for f in group if 250 <= duration_days(f.start, f.end) <= 290])
        fyf = pick([f for f in group if 330 <= duration_days(f.start, f.end) <= 400])
        def add(start, end, value, src):
            if not start or not end or end in out: return
            out[end] = Fact(src.cik, src.taxonomy, src.concept, src.unit, value, start, end,
                            src.filed, src.form, src.accession, src.fy, src.fp, src.frame,
                            src.accepted_at, src.first_seen_at, src.source, src.fetched_at,
                            src.sha256, src.availability_quality)
        if q1 and h1 and h1.start == q1.start and h1.value != q1.value:
            add(q1.end, h1.end, h1.value - q1.value, h1)
        if h1 and q9 and q9.start == h1.start:
            add(h1.end, q9.end, q9.value - h1.value, q9)
        if q9 and fyf and fyf.start == q9.start:
            add(q9.end, fyf.end, fyf.value - q9.value, fyf)
    return [out[k] for k in sorted(out)]


def _ttm_quarter_chain(s: Snapshot, key: str, unit="USD") -> list[Fact] | None:
    qs = _quarters(s, key, unit)
    if len(qs) < 4: return None
    last = qs[-4:]
    for a, b in zip(last, last[1:]):
        gap = (date.fromisoformat(b.start) - date.fromisoformat(a.end)).days
        if gap < 0 or gap > 3: return None
    total = (date.fromisoformat(last[-1].end) - date.fromisoformat(last[0].start)).days
    if not (350 <= total <= 380): return None
    return last


def _period_value(s: Snapshot, key: str, unit="USD") -> dict | None:
    qs = _ttm_quarter_chain(s, key, unit)
    if qs:
        return {"value": sum(f.value for f in qs), "period_type": "TTM", "start": qs[0].start,
                "end": qs[-1].end, "facts": qs, "fiscal_year": qs[-1].fy,
                "fiscal_period": "TTM"}
    annual = _annual(s, key, unit)
    if annual:
        f = annual[-1]
        return {"value": f.value, "period_type": "FY", "start": f.start, "end": f.end,
                "facts": [f], "fiscal_year": f.fy, "fiscal_period": f.fp or "FY"}
    return None


def _metric(ticker, name, value, unit, status="OK", formula="1.0", period=None,
            inputs=None, missing=None, extra=None):
    p = period or {}
    d = {"ticker": ticker, "metric": name, "value": value, "unit": unit, "status": status,
         "formula_version": formula, "period_start": p.get("start"), "period_end": p.get("end"),
         "period_type": p.get("period_type"), "fiscal_year": p.get("fiscal_year"),
         "fiscal_period": p.get("fiscal_period"),
         "observation_date": p.get("end"),
         "available_at": max((f.accepted_at or f.filed for f in p.get("facts", []) if (f.accepted_at or f.filed)), default=None),
         "availability_quality": ("OBSERVED_FIRST_SEEN" if p.get("facts") and all(f.availability_quality == "OBSERVED_FIRST_SEEN" for f in p.get("facts", [])) else
                                  "ACCEPTANCE_ESTIMATE" if p.get("facts") and all(f.availability_quality in ("OBSERVED_FIRST_SEEN", "ACCEPTANCE_ESTIMATE") for f in p.get("facts", [])) else
                                  "FILED_DATE_ONLY" if p.get("facts") else "UNKNOWN"),
         "source": "SEC CompanyFacts", "accession": (p.get("facts") or [None])[-1].accession if p.get("facts") else None,
         "form": (p.get("facts") or [None])[-1].form if p.get("facts") else None,
         "input_facts": [_fact_ref(f) for f in p.get("facts", [])], "missing_reason": missing}
    if extra: d.update(extra)
    return d


def _unavailable(ticker, name, unit="USD", status="INSUFFICIENT_DATA", missing="required source fact unavailable", formula="1.0"):
    return _metric(ticker, name, None, unit, status, formula, missing=missing)


def _flow(s: Snapshot, key, unit="USD"):
    d = _period_value(s, key, unit); return d


def value_metrics(s: Snapshot, *, market_quote: dict | None = None, share_count: dict | None = None) -> dict:
    out = {}
    rev, op, ni = _flow(s, "revenue"), _flow(s, "operating_income"), _flow(s, "net_income")
    cfo, cap = _flow(s, "cfo"), _flow(s, "capex")
    for name, d, unit in [("revenue", rev, "USD"), ("operating_income", op, "USD"),
                          ("net_income", ni, "USD"), ("cash_from_operations", cfo, "USD"),
                          ("capital_expenditure", cap, "USD")]:
        out[name] = _metric(s.ticker, name, d["value"], unit, period=d) if d else _unavailable(s.ticker, name, unit)
    # FCF must use identical start/end; otherwise it is not a valid FCF.
    fcf = None
    if cfo and cap and cfo["start"] == cap["start"] and cfo["end"] == cap["end"]:
        fcf = cfo["value"] - abs(cap["value"])
        p = {"start": cfo["start"], "end": cfo["end"], "period_type": cfo["period_type"],
             "fiscal_year": cfo["fiscal_year"], "fiscal_period": cfo["fiscal_period"],
             "facts": cfo["facts"] + cap["facts"]}
        out["free_cash_flow"] = _metric(s.ticker, "free_cash_flow", fcf, "USD", period=p,
                                         formula="CFO - abs(CapEx)", extra={"formula_version": "2.0"})
        out["owner_earnings_proxy"] = _metric(s.ticker, "owner_earnings_proxy", fcf, "USD", period=p,
                                               formula="FCF proxy = CFO - CapEx", extra={"proxy_note": "maintenance capex unavailable"})
    else:
        out["free_cash_flow"] = _unavailable(s.ticker, "free_cash_flow", missing="CFO and CapEx periods do not match or are missing")
        out["owner_earnings_proxy"] = _unavailable(s.ticker, "owner_earnings_proxy", missing="FCF unavailable")
    eq = _instant_at(s, TAGS["equity"], (ni or rev or {"end": "0000"}).get("end", "0000"))
    cash = _instant_at(s, TAGS["cash"], (ni or rev or {"end": "0000"}).get("end", "0000"))
    debt = _total_debt(s, (ni or rev or {"end": "0000"}).get("end", "0000"))
    out["stockholders_equity"] = _metric(s.ticker, "stockholders_equity", eq.value, "USD",
        period={"start": None, "end": eq.end, "period_type": "INSTANT", "facts": [eq]}) if eq else _unavailable(s.ticker, "stockholders_equity")
    out["cash_and_equivalents"] = _metric(s.ticker, "cash_and_equivalents", cash.value, "USD",
        period={"start": None, "end": cash.end, "period_type": "INSTANT", "facts": [cash]}) if cash else _unavailable(s.ticker, "cash_and_equivalents")
    out["total_debt"] = debt
    if debt["status"] == "OK" and cash:
        p = {"start": None, "end": cash.end, "period_type": "INSTANT",
             "facts": debt["input_facts"] and []}
        out["net_debt"] = _metric(s.ticker, "net_debt", debt["value"] - cash.value, "USD",
            period={"start": None, "end": cash.end, "period_type": "INSTANT", "facts": [cash]},
            formula="total_debt - cash", extra={"debt_rule": debt.get("debt_rule")})
    else:
        out["net_debt"] = _unavailable(s.ticker, "net_debt", missing="debt or cash missing")
    # Price inputs are gated by an explicit quote/share provenance contract.
    if not _valid_quote(market_quote) or not _valid_shares(share_count):
        for name in ("pe_ttm", "pb", "ev_ebit", "ev_ebitda", "earnings_yield", "fcf_yield",
                     "market_cap", "enterprise_value", "margin_of_safety"):
            out[name] = _unavailable(s.ticker, name, "ratio" if name not in ("market_cap", "enterprise_value") else "USD",
                                     "DATA_BLOCKED", "authorized market quote/current shares not supplied")
        return out
    mcap = market_quote["price"] * share_count["shares"]
    out["market_cap"] = _metric(s.ticker, "market_cap", mcap, "USD", formula="price * current shares")
    if ni and ni["value"] > 0:
        out["pe_ttm"] = _metric(s.ticker, "pe_ttm", mcap / ni["value"], "ratio", period=ni, formula="market_cap / net_income")
        out["earnings_yield"] = _metric(s.ticker, "earnings_yield", ni["value"] / mcap, "ratio", period=ni, formula="net_income / market_cap")
    if eq and eq.value > 0:
        out["pb"] = _metric(s.ticker, "pb", mcap / eq.value, "ratio", formula="market_cap / equity")
    if fcf is not None:
        out["fcf_yield"] = _metric(s.ticker, "fcf_yield", fcf / mcap, "ratio", formula="fcf / market_cap")
    if debt["status"] == "OK" and cash:
        out["enterprise_value"] = _metric(s.ticker, "enterprise_value", mcap + debt["value"] - cash.value,
                                          "USD", formula="market_cap + total_debt - cash",
                                          extra={"debt_rule": debt.get("debt_rule")})
        if op and op["value"] > 0:
            out["ev_ebit"] = _metric(s.ticker, "ev_ebit", (mcap + debt["value"] - cash.value) / op["value"], "ratio", period=op, formula="EV / EBIT")
        dep = _flow(s, "depreciation")
        if op and dep and op["start"] == dep["start"] and op["end"] == dep["end"]:
            ebitda = op["value"] + dep["value"]
            if ebitda > 0:
                out["ev_ebitda"] = _metric(s.ticker, "ev_ebitda", (mcap + debt["value"] - cash.value) / ebitda,
                                           "ratio", period=op, formula="EV / (EBIT + D&A)",
                                           extra={"ebitda": ebitda})
            else:
                out["ev_ebitda"] = _unavailable(s.ticker, "ev_ebitda", "ratio", "NOT_APPLICABLE", "EBITDA <= 0")
    else:
        out["enterprise_value"] = _unavailable(s.ticker, "enterprise_value", "USD", missing="debt or cash missing; EV not zero-filled")
    return out


def _total_debt(s: Snapshot, end: str) -> dict:
    """Avoid double counting LongTermDebt (total) plus its current portion."""
    total = _instant_at(s, TAGS["total_long_term_debt"], end)
    noncurrent = _instant_at(s, TAGS["long_term_debt"], end)
    current = _instant_at(s, TAGS["current_ltd"], end)
    stb = _instant_at(s, TAGS["short_term_debt"], end)
    if total:
        parts = [total] + ([stb] if stb and stb.concept == "ShortTermBorrowings" else [])
        rule = "LongTermDebt total + ShortTermBorrowings only; LongTermDebtCurrent not added"
    elif noncurrent and current:
        parts = [noncurrent, current] + ([stb] if stb and stb.concept == "ShortTermBorrowings" else [])
        rule = "LongTermDebtNoncurrent + LongTermDebtCurrent + ShortTermBorrowings"
    elif noncurrent:
        parts = [noncurrent] + ([stb] if stb else [])
        rule = "LongTermDebtNoncurrent + short-term borrowings"
    elif stb:
        parts = [stb]; rule = "short-term borrowings only"
    else:
        return _unavailable(s.ticker, "total_debt", missing="interest-bearing debt tags missing")
    p = {"start": None, "end": max(f.end for f in parts), "period_type": "INSTANT", "facts": parts}
    m = _metric(s.ticker, "total_debt", sum(f.value for f in parts), "USD", period=p,
                formula="rule=" + rule, extra={"debt_rule": rule}); m["_parts"] = parts
    return m


def _valid_quote(q: dict | None) -> bool:
    return bool(q and q.get("price", 0) > 0 and q.get("source") and q.get("license_status") == "AUTHORIZED"
                and q.get("timestamp") and q.get("price_type") and q.get("currency"))


def _valid_shares(s: dict | None) -> bool:
    return bool(s and s.get("shares", 0) > 0 and s.get("observation_date") and s.get("available_at") and s.get("source"))


def _ratio(s, name, num: dict | None, den: dict | None, formula, *, percent=False):
    if den and den.get("value") == 0:
        return _unavailable(s.ticker, name, "ratio", "NOT_APPLICABLE", "zero denominator", formula)
    if not num or not den:
        return _unavailable(s.ticker, name, "ratio", missing="numerator or denominator unavailable", formula=formula)
    p = {"start": num.get("start"), "end": num.get("end"), "period_type": num.get("period_type"),
         "fiscal_year": num.get("fiscal_year"), "fiscal_period": num.get("fiscal_period"),
         "facts": num.get("facts", []) + den.get("facts", [])}
    return _metric(s.ticker, name, num["value"] / den["value"], "ratio", period=p, formula=formula)


def _avg_equity(s, start: str, end: str):
    begin = _instant_at(s, TAGS["equity"], start)
    finish = _instant_at(s, TAGS["equity"], end)
    if not begin or not finish: return None, None, None
    if begin.end == finish.end: return None, begin, finish
    return (begin.value + finish.value) / 2, begin, finish


def quality_metrics(s: Snapshot, *, sector: str | None = None) -> dict:
    out = {}; rev = _flow(s, "revenue"); gp = _flow(s, "gross_profit")
    op = _flow(s, "operating_income"); ni = _flow(s, "net_income")
    cfo, cap = _flow(s, "cfo"), _flow(s, "capex")
    dep = _flow(s, "depreciation"); tax = _flow(s, "tax_expense"); pretax = _flow(s, "pretax_income")
    end = (ni or rev or op or {"end": "0000"})["end"]
    eq = _instant_at(s, TAGS["equity"], end); cash = _instant_at(s, TAGS["cash"], end)
    debt = _total_debt(s, end)
    out["gross_margin"] = _ratio(s, "gross_margin", gp, rev, "gross_profit / revenue")
    out["operating_margin"] = _ratio(s, "operating_margin", op, rev, "operating_income / revenue")
    out["net_margin"] = _ratio(s, "net_margin", ni, rev, "net_income / revenue")
    # Average equity, matched to TTM/FY income period.
    if ni:
        avg, begin, finish = _avg_equity(s, ni["start"], ni["end"])
    else: avg = begin = finish = None
    if not avg or not ni:
        out["roe"] = _unavailable(s.ticker, "roe", "ratio", missing="beginning/ending equity or TTM income missing")
    elif avg <= 0:
        out["roe"] = _unavailable(s.ticker, "roe", "ratio", "NOT_APPLICABLE", "average equity <= 0")
    else:
        p = {"start": ni["start"], "end": ni["end"], "period_type": ni["period_type"], "facts": ni["facts"] + [begin, finish]}
        out["roe"] = _metric(s.ticker, "roe", ni["value"] / avg, "ratio", period=p,
                             formula="net_income / average_equity")
    fcf = cfo["value"] - abs(cap["value"]) if cfo and cap and cfo["start"] == cap["start"] and cfo["end"] == cap["end"] else None
    out["fcf_conversion"] = _ratio(s, "fcf_conversion",
        {"value": fcf, "start": cfo["start"], "end": cfo["end"], "period_type": cfo["period_type"], "facts": cfo["facts"] + cap["facts"]} if fcf is not None else None,
        ni, "free_cash_flow / net_income")
    if debt["status"] != "OK":
        out["debt_to_equity"] = _unavailable(s.ticker, "debt_to_equity", "ratio", missing="interest-bearing debt missing")
    elif not eq or eq.value <= 0:
        out["debt_to_equity"] = _unavailable(s.ticker, "debt_to_equity", "ratio", "NOT_APPLICABLE", "equity <= 0")
    else:
        out["debt_to_equity"] = _metric(s.ticker, "debt_to_equity", debt["value"] / eq.value, "ratio",
            formula="total_debt / equity", period={"start": None, "end": eq.end, "period_type": "INSTANT",
            "facts": debt.get("_parts", []) + [eq]}, extra={"debt_rule": debt.get("debt_rule")})
    if debt["status"] == "OK" and cash and op and dep and op["start"] == dep["start"] and op["end"] == dep["end"]:
        ebitda = op["value"] + dep["value"]
        out["net_debt_to_ebitda"] = _metric(s.ticker, "net_debt_to_ebitda", (debt["value"] - cash.value) / ebitda, "ratio",
            period={"start": op["start"], "end": op["end"], "period_type": op["period_type"], "facts": op["facts"] + dep["facts"]},
            formula="(total_debt - cash) / (operating_income + depreciation)") if ebitda > 0 else _unavailable(s.ticker, "net_debt_to_ebitda", "ratio", "NOT_APPLICABLE", "EBITDA <= 0")
    else:
        out["net_debt_to_ebitda"] = _unavailable(s.ticker, "net_debt_to_ebitda", "ratio", missing="EBITDA/debt/cash inputs incomplete")
    out["roic"] = _roic(s, op, tax, pretax, eq, cash, debt, end, sector)
    out["interest_coverage"] = _interest_coverage(s, op, end, sector)
    stability = _stability(s)
    out.update(stability)
    if sector and sector.lower() in SPECIAL_SECTORS:
        for name in ("net_debt_to_ebitda", "roic", "interest_coverage"):
            out[name] = _unavailable(s.ticker, name, "ratio", "NOT_APPLICABLE", f"not meaningful for {sector}")
    return out


def _roic(s, op, tax, pretax, eq, cash, debt, end, sector):
    if sector and sector.lower() in ("financials", "banks", "insurance", "bank"):
        return _unavailable(s.ticker, "roic", "ratio", "NOT_APPLICABLE", f"industrial ROIC not applicable to {sector}")
    if not op or not tax or not pretax or not eq or not cash or debt["status"] != "OK":
        return _unavailable(s.ticker, "roic", "ratio", missing="EBIT, tax, pretax, debt, equity, or cash missing")
    if pretax["value"] <= 0: return _unavailable(s.ticker, "roic", "ratio", "NOT_APPLICABLE", "pretax income <= 0")
    rate = tax["value"] / pretax["value"]
    if rate < 0 or rate > 1: return _unavailable(s.ticker, "roic", "ratio", "NOT_APPLICABLE", "effective tax rate outside 0..1")
    begin_eq = _instant_at(s, TAGS["equity"], op["start"])
    begin_cash = _instant_at(s, TAGS["cash"], op["start"])
    begin_debt = _total_debt(s, op["start"])
    if not begin_eq or not begin_cash or begin_debt["status"] != "OK":
        return _unavailable(s.ticker, "roic", "ratio", missing="beginning invested-capital inputs missing")
    end_ic = debt["value"] + eq.value - cash.value
    begin_ic = begin_debt["value"] + begin_eq.value - begin_cash.value
    avg = (begin_ic + end_ic) / 2
    if avg <= 0: return _unavailable(s.ticker, "roic", "ratio", "NOT_APPLICABLE", "average invested capital <= 0")
    nopat = op["value"] * (1 - rate)
    p = {"start": op["start"], "end": op["end"], "period_type": op["period_type"], "facts": op["facts"] + tax["facts"] + pretax["facts"] + [begin_eq, begin_cash, eq, cash]}
    return _metric(s.ticker, "roic", nopat / avg, "ratio", period=p,
                   formula="EBIT*(1-tax_rate) / average(debt+equity-cash)",
                   extra={"nopat": nopat, "effective_tax_rate": rate, "average_invested_capital": avg})


def _interest_coverage(s, op, end, sector):
    if sector and sector.lower() in ("financials", "banks", "insurance", "bank"):
        return _unavailable(s.ticker, "interest_coverage", "ratio", "NOT_APPLICABLE", f"not meaningful for {sector}")
    interest = _flow(s, "interest_expense")
    if not op or not interest:
        return _unavailable(s.ticker, "interest_coverage", "ratio", missing="EBIT or interest expense missing")
    if op["start"] != interest["start"] or op["end"] != interest["end"]:
        return _unavailable(s.ticker, "interest_coverage", "ratio", missing="EBIT and interest expense periods differ")
    if interest["value"] <= 0:
        return _unavailable(s.ticker, "interest_coverage", "ratio", "NOT_APPLICABLE", "interest expense <= 0; ratio undefined")
    p = {"start": op["start"], "end": op["end"], "period_type": op["period_type"], "facts": op["facts"] + interest["facts"]}
    return _metric(s.ticker, "interest_coverage", op["value"] / interest["value"], "ratio", period=p,
                   formula="EBIT / interest_expense")


def _stability(s):
    out = {}
    for key, name, positive_label in (("revenue", "revenue_stability", "positive_growth_years"),
                                      ("operating_income", "earnings_stability", "positive_earnings_years")):
        series = _annual(s, key)[-5:]
        if len(series) < 5:
            out[name] = _unavailable(s.ticker, name, "ratio", missing="fewer than 5 annual periods")
            continue
        values = [f.value for f in series]
        growth = []
        for a, b in zip(series, series[1:]):
            growth.append(None if a.value <= 0 else (b.value - a.value) / abs(a.value))
        out[name] = _metric(s.ticker, name, {
            "years": [f.end for f in series], "values": values, "growth": growth,
            positive_label: sum(1 for x in growth if x is not None and x > 0),
            "negative_years": sum(1 for x in values if x < 0),
            "cagr": None if values[0] <= 0 else (values[-1] / values[0]) ** (1 / 4) - 1,
            "volatility": None if len([x for x in growth if x is not None]) < 2 else __import__("statistics").pstdev([x for x in growth if x is not None]),
        }, "ratio", period={"start": series[0].start, "end": series[-1].end, "period_type": "FY",
                            "facts": series}, formula="5y annual dispersion")
    return out


def garp_metrics(s: Snapshot) -> dict:
    out = {}; rev = _annual(s, "revenue"); gp = _annual(s, "gross_profit")
    op = _annual(s, "operating_income"); eps = _annual(s, "eps_diluted", "USD/shares")
    cfo, cap = _annual(s, "cfo"), _annual(s, "capex")
    def growth(name, series):
        if len(series) < 2:
            out[name] = _unavailable(s.ticker, name, "ratio", missing="two annual periods required")
            return
        a, b = series[-2], series[-1]
        if a.value <= 0:
            out[name] = _unavailable(s.ticker, name, "ratio", "NOT_APPLICABLE", "non-positive base")
            return
        p = {"start": a.start, "end": b.end, "period_type": "FY", "facts": [a, b]}
        out[name] = _metric(s.ticker, name, (b.value - a.value) / abs(a.value), "ratio", period=p,
                            formula="(latest - prior) / abs(prior)")
    growth("revenue_growth", rev); growth("gross_profit_growth", gp)
    growth("operating_income_growth", op); growth("eps_growth", eps)
    fcf = []
    cfo_by_end = {f.end: f for f in cfo}
    for c in cap:
        if c.end in cfo_by_end:
            fcf.append(Fact(c.cik, "x", "fcf", "USD", cfo_by_end[c.end].value - abs(c.value),
                            c.start, c.end, c.filed, c.form, c.accession, c.fy, c.fp, c.frame,
                            c.accepted_at, c.first_seen_at, c.source, c.fetched_at, c.sha256, c.availability_quality))
    growth("fcf_growth", fcf)
    for name, n in (("revenue_cagr_3y", 3), ("revenue_cagr_5y", 5)):
        if len(rev) < n + 1:
            out[name] = _unavailable(s.ticker, name, "ratio", missing=f"{n+1} annual periods required")
        else:
            a, b = rev[-(n+1)], rev[-1]
            out[name] = (_unavailable(s.ticker, name, "ratio", "NOT_APPLICABLE", "non-positive base")
                         if a.value <= 0 else _metric(s.ticker, name, (b.value/a.value)**(1/n)-1, "ratio",
                         period={"start": a.start, "end": b.end, "period_type": "FY", "facts": [a, b]},
                         formula=f"{n}y CAGR"))
    # Require both annual series to end on the same fiscal period.
    if len(rev) >= 2 and len(op) >= 2 and rev[-1].end == op[-1].end and rev[-2].end == op[-2].end:
        rg = None if rev[-2].value <= 0 else (rev[-1].value-rev[-2].value)/abs(rev[-2].value)
        og = None if op[-2].value <= 0 else (op[-1].value-op[-2].value)/abs(op[-2].value)
        p = {"start": rev[-2].start, "end": rev[-1].end, "period_type": "FY", "facts": rev[-2:] + op[-2:]}
        if rg and og:
            out["operating_leverage_ratio"] = _metric(s.ticker, "operating_leverage_ratio", og/rg, "ratio",
                period=p, formula="operating_income_growth / revenue_growth")
            out["operating_margin_expansion"] = _metric(s.ticker, "operating_margin_expansion", og-rg, "ratio",
                period=p, formula="operating_income_growth - revenue_growth")
        else:
            for name in ("operating_leverage_ratio", "operating_margin_expansion"):
                out[name] = _unavailable(s.ticker, name, "ratio", "NOT_APPLICABLE", "zero/non-positive base")
    else:
        for name in ("operating_leverage_ratio", "operating_margin_expansion"):
            out[name] = _unavailable(s.ticker, name, "ratio", missing="revenue/operating income periods do not match")
    out["operating_leverage"] = out["operating_margin_expansion"]
    out["peg"] = _unavailable(s.ticker, "peg", "ratio", "DATA_BLOCKED", "forward EPS estimates not licensed")
    return out


def analyze(ticker: str, cik: str, facts: list[Fact], *, as_of: str | None = None,
            market_quote: dict | None = None, share_count: dict | None = None,
            sector: str | None = None) -> dict:
    s = Snapshot(ticker, cik, facts, as_of)
    return {"ticker": ticker, "cik": cik, "as_of": as_of, "sector": sector,
            "value": value_metrics(s, market_quote=market_quote, share_count=share_count),
            "quality": quality_metrics(s, sector=sector), "garp": garp_metrics(s)}
