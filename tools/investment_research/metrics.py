"""P2 Value / Quality / GARP metrics from normalized SEC facts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Iterable
from tools.investment_research.sec.normalize import Fact, duration_days

TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "eps_basic": ["EarningsPerShareBasic"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "equity": ["StockholdersEquity"],
    "assets": ["Assets"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "short_term_debt": ["ShortTermBorrowings", "LongTermDebtCurrent", "DebtCurrent"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "shares_outstanding": ["CommonStockSharesOutstanding"],
    "dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "depreciation": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet"],
}


@dataclass
class Snapshot:
    ticker: str; cik: str; facts: list[Fact]; as_of: str | None = None
    def available(self): return [f for f in self.facts if not self.as_of or f.filed <= self.as_of[:10]]


def _pick(facts, concepts, unit=None, instant=False, quarterly=False):
    cand = [f for f in facts if f.concept in concepts and (unit is None or f.unit == unit)]
    if instant: cand = [f for f in cand if not f.start]
    else:
        cand = [f for f in cand if f.start and duration_days(f.start, f.end) is not None]
        if quarterly: cand = [f for f in cand if 70 <= duration_days(f.start, f.end) <= 100]
    if not cand: return None
    # latest public filing, then latest period
    return sorted(cand, key=lambda f: (f.end, f.filed, f.accession))[-1]


def _ttm(facts, concepts, unit, as_of):
    q = [f for f in facts if f.concept in concepts and f.unit == unit and f.start
         and 70 <= duration_days(f.start, f.end) <= 100]
    latest = {}
    for f in sorted(q, key=lambda x: (x.end, x.filed)):
        latest[f.end] = f
    qs = sorted(latest.values(), key=lambda x: x.end)[-4:]
    if len(qs) == 4:
        return {"value": sum(f.value for f in qs), "period": "TTM",
                "start": qs[0].start, "end": qs[-1].end, "facts": qs}
    annual = [f for f in facts if f.concept in concepts and f.unit == unit and f.start
              and 330 <= duration_days(f.start, f.end) <= 400]
    if annual:
        f = sorted(annual, key=lambda x: (x.end, x.filed))[-1]
        return {"value": f.value, "period": "FY", "start": f.start, "end": f.end, "facts": [f]}
    return None


def metric(ticker, name, value, unit, status="OK", formula="1.0", obs=None, avail=None,
           quality="UNKNOWN", source="SEC CompanyFacts", accession=None, form=None,
           inputs=None, missing=None):
    return {"ticker": ticker, "metric": name, "value": value, "unit": unit,
            "status": status, "formula_version": formula, "observation_date": obs,
            "available_at": avail, "availability_quality": quality, "source": source,
            "accession": accession, "form": form,
            "input_facts": inputs or [], "missing_reason": missing}


def _fact_ref(f):
    return {"concept": f.concept, "value": f.value, "unit": f.unit, "start": f.start,
            "end": f.end, "filed": f.filed, "form": f.form, "accession": f.accession}


def _base(name, ticker, unit="USD"):
    return metric(ticker, name, None, unit, "INSUFFICIENT_DATA",
                  missing="required source fact unavailable")


def _duration(s: Snapshot, key, unit="USD", ttm=True):
    facts = s.available(); concepts = TAGS[key]
    if ttm:
        d = _ttm(facts, concepts, unit, s.as_of)
        if d: return d
    f = _pick(facts, concepts, unit, instant=False)
    if not f: return None
    return {"value": f.value, "period": "FY", "start": f.start, "end": f.end, "facts": [f]}


def _instant(s: Snapshot, key, unit="USD"):
    f = _pick(s.available(), TAGS[key], unit, instant=True)
    if not f: return None
    return {"value": f.value, "fact": f, "end": f.end, "filed": f.filed,
            "accession": f.accession, "form": f.form}


def _ok(s, name, d, unit="USD", formula="1.0"):
    f = d["facts"][-1] if d.get("facts") else d.get("fact")
    return metric(s.ticker, name, d["value"], unit, "OK", formula,
                  d.get("end"), (f.accepted_at or f.filed) if f else None,
                  f.availability_quality if f else "UNKNOWN", accession=f.accession if f else None,
                  form=f.form if f else None, inputs=[_fact_ref(f)] if f else [])


def value_metrics(s: Snapshot, *, market_price: float | None = None,
                  current_shares: float | None = None) -> dict:
    out = {}
    rev = _duration(s, "revenue"); op = _duration(s, "operating_income")
    ni = _duration(s, "net_income"); cfo = _duration(s, "cfo")
    cap = _duration(s, "capex"); eq = _instant(s, "equity")
    cash = _instant(s, "cash"); ltd = _instant(s, "long_term_debt")
    std = _instant(s, "short_term_debt"); sh = _instant(s, "shares_outstanding")
    for name, d in [("revenue", rev), ("operating_income", op), ("net_income", ni),
                    ("cash_from_operations", cfo), ("capital_expenditure", cap)]:
        out[name] = _ok(s, name, d) if d else _base(name, s.ticker)
    fcf = None
    if cfo and cap:
        fcf = cfo["value"] - abs(cap["value"])
        out["free_cash_flow"] = metric(s.ticker, "free_cash_flow", fcf, "USD", "OK",
            "CFO - abs(CapEx)", cfo["end"], cfo["facts"][-1].filed,
            cfo["facts"][-1].availability_quality, accession=cfo["facts"][-1].accession,
            form=cfo["facts"][-1].form, inputs=[_fact_ref(cfo["facts"][-1]), _fact_ref(cap["facts"][-1])])
    else:
        out["free_cash_flow"] = _base("free_cash_flow", s.ticker)
    for name, d in [("stockholders_equity", eq), ("cash_and_equivalents", cash),
                    ("long_term_debt", ltd), ("short_term_debt", std),
                    ("shares_outstanding", sh)]:
        out[name] = _ok(s, name, d, "shares" if name == "shares_outstanding" else "USD") if d else _base(name, s.ticker, "shares" if name == "shares_outstanding" else "USD")
    if ltd and std:
        debt = ltd["value"] + std["value"]
        out["total_debt"] = metric(s.ticker, "total_debt", debt, "USD", "OK", "LTD + STD",
            max(ltd["end"], std["end"]), max(ltd["filed"], std["filed"]),
            "FILED_DATE_ONLY", accession=ltd["accession"], form=ltd["form"],
            inputs=[_fact_ref(ltd["fact"]), _fact_ref(std["fact"])])
        if cash: out["net_debt"] = metric(s.ticker, "net_debt", debt - cash["value"], "USD", "OK",
            "total_debt - cash", cash["end"], cash["filed"], cash["fact"].availability_quality,
            accession=cash["accession"], form=cash["form"],
            inputs=[_fact_ref(ltd["fact"]), _fact_ref(std["fact"]), _fact_ref(cash["fact"])])
    else:
        out["total_debt"] = _base("total_debt", s.ticker); out["net_debt"] = _base("net_debt", s.ticker)
    if fcf is not None:
        out["owner_earnings_proxy"] = metric(s.ticker, "owner_earnings_proxy", fcf, "USD", "OK",
            "FCF proxy = CFO - CapEx; maintenance capex unavailable", cfo["end"],
            cfo["facts"][-1].filed, cfo["facts"][-1].availability_quality,
            inputs=[_fact_ref(cfo["facts"][-1]), _fact_ref(cap["facts"][-1])])
    else:
        out["owner_earnings_proxy"] = _base("owner_earnings_proxy", s.ticker)
    # Price-dependent metrics are blocked without an authorized price and current shares.
    for name in ("pe_ttm", "pb", "ev_ebit", "ev_ebitda", "earnings_yield", "fcf_yield",
                 "market_cap", "enterprise_value", "margin_of_safety"):
        out[name] = metric(s.ticker, name, None, "ratio", "DATA_BLOCKED", "1.0",
                           missing="authorized market price / current shares not supplied")
    if market_price and current_shares and ni and ni["value"] != 0:
        mcap = market_price * current_shares
        out["market_cap"] = metric(s.ticker, "market_cap", mcap, "USD", "OK", "price * current shares")
        out["pe_ttm"] = (metric(s.ticker, "pe_ttm", mcap / ni["value"], "ratio", "OK", "market_cap / net_income")
                         if ni["value"] > 0 else metric(s.ticker, "pe_ttm", None, "ratio", "NOT_APPLICABLE",
                         "market_cap / net_income", missing="negative or zero net income"))
        out["earnings_yield"] = metric(s.ticker, "earnings_yield", ni["value"] / mcap, "ratio", "OK", "net_income / market_cap")
        if eq and eq["value"] > 0:
            out["pb"] = metric(s.ticker, "pb", mcap / eq["value"], "ratio", "OK", "market_cap / equity")
        if fcf is not None:
            out["fcf_yield"] = metric(s.ticker, "fcf_yield", fcf / mcap, "ratio", "OK", "fcf / market_cap")
        ev = mcap + (out["total_debt"]["value"] if out["total_debt"]["status"] == "OK" else 0) - (cash["value"] if cash else 0)
        out["enterprise_value"] = metric(s.ticker, "enterprise_value", ev, "USD", "OK", "market_cap + debt - cash")
        if op and op["value"] > 0: out["ev_ebit"] = metric(s.ticker, "ev_ebit", ev / op["value"], "ratio", "OK", "EV / operating_income")
    if fcf is not None and fcf > 0 and current_shares and current_shares > 0:
        def dcf(g, disc=0.10, term=0.025, years=5):
            pv = sum(fcf * ((1 + g) ** i) / ((1 + disc) ** i) for i in range(1, years + 1))
            tv = fcf * ((1 + g) ** years) * (1 + term) / (disc - term)
            return (pv + tv / ((1 + disc) ** years)) / current_shares
        bear, base, bull = dcf(-0.02), dcf(0.03), dcf(0.08)
        out["intrinsic_value"] = metric(s.ticker, "intrinsic_value", {"bear": bear, "base": base, "bull": bull},
            "USD/share", "OK", "5y FCF DCF; discount=10%, terminal=2.5%",
            obs=cfo["end"], avail=cfo["facts"][-1].accepted_at or cfo["facts"][-1].filed, quality=cfo["facts"][-1].availability_quality,
            inputs=[_fact_ref(cfo["facts"][-1]), _fact_ref(cap["facts"][-1])])
        out["dcf_assumptions"] = {"base_fcf": fcf, "years": 5, "discount_rate": 0.10,
                                  "terminal_growth": 0.025, "growth": {"bear": -0.02, "base": 0.03, "bull": 0.08},
                                  "shares": current_shares, "note": "current shares must be explicitly supplied; historical share count is not current"}
        if market_price:
            out["margin_of_safety"] = metric(s.ticker, "margin_of_safety", (base - market_price) / base,
                "ratio", "OK", "(base intrinsic - price) / base intrinsic", inputs=[])
    return out


def _enhance(s, out, name, f):
    if f and name in out and out[name].get("status") == "OK":
        out[name].update({"observation_date": f.end, "available_at": f.accepted_at or f.filed,
                          "availability_quality": f.availability_quality,
                          "accession": f.accession, "form": f.form,
                          "input_facts": [_fact_ref(f)]})


def _annual_series(s: Snapshot, key, unit="USD"):
    concepts = TAGS[key]; best = {}
    for f in s.available():
        if f.concept in concepts and f.unit == unit and f.start and 330 <= duration_days(f.start, f.end) <= 400:
            if f.end not in best or f.filed > best[f.end].filed: best[f.end] = f
    return [best[k] for k in sorted(best)]


def quality_metrics(s: Snapshot, *, sector: str | None = None) -> dict:
    out = {}; rev = _duration(s, "revenue"); gp = _duration(s, "gross_profit")
    op = _duration(s, "operating_income"); ni = _duration(s, "net_income")
    cfo = _duration(s, "cfo"); cap = _duration(s, "capex"); eq = _instant(s, "equity")
    ltd = _instant(s, "long_term_debt"); std = _instant(s, "short_term_debt")
    cash = _instant(s, "cash"); dep = _duration(s, "depreciation")
    def ratio(name, num, den, formula):
        if num is None or den is None or den == 0:
            out[name] = metric(s.ticker, name, None, "ratio", "NOT_APPLICABLE" if den == 0 else "INSUFFICIENT_DATA",
                               formula, missing="zero or missing denominator")
        else:
            out[name] = metric(s.ticker, name, num / den, "ratio", "OK", formula)
    ratio("gross_margin", gp["value"] if gp else None, rev["value"] if rev else None, "gross_profit / revenue")
    ratio("operating_margin", op["value"] if op else None, rev["value"] if rev else None, "operating_income / revenue")
    ratio("net_margin", ni["value"] if ni else None, rev["value"] if rev else None, "net_income / revenue")
    if eq and eq["value"] > 0:
        ratio("roe", ni["value"] if ni else None, eq["value"], "net_income / equity")
    else:
        out["roe"] = metric(s.ticker, "roe", None, "ratio", "NOT_APPLICABLE",
                            "net_income / equity", missing="equity is zero or negative")
    fcf = (cfo["value"] - abs(cap["value"])) if cfo and cap else None
    ratio("fcf_conversion", fcf, ni["value"] if ni else None, "free_cash_flow / net_income")
    debt = (ltd["value"] + std["value"]) if ltd and std else None
    if eq and eq["value"] > 0:
        ratio("debt_to_equity", debt, eq["value"], "total_debt / equity")
    else:
        out["debt_to_equity"] = metric(s.ticker, "debt_to_equity", None, "ratio", "NOT_APPLICABLE",
                                       "total_debt / equity", missing="equity is zero or negative")
    if dep and op and debt is not None:
        ebitda = op["value"] + dep["value"]
        ratio("net_debt_to_ebitda", debt - (cash["value"] if cash else 0), ebitda, "net_debt / (operating_income + depreciation)")
    else:
        out["net_debt_to_ebitda"] = metric(s.ticker, "net_debt_to_ebitda", None, "ratio", "INSUFFICIENT_DATA",
                                           missing="EBITDA inputs unavailable")
    _enhance(s, out, "gross_margin", gp["facts"][-1] if gp else None)
    _enhance(s, out, "operating_margin", op["facts"][-1] if op else None)
    _enhance(s, out, "net_margin", ni["facts"][-1] if ni else None)
    _enhance(s, out, "roe", eq["fact"] if eq else None)
    _enhance(s, out, "fcf_conversion", cfo["facts"][-1] if cfo else None)
    _enhance(s, out, "debt_to_equity", eq["fact"] if eq else None)
    _enhance(s, out, "net_debt_to_ebitda", dep["facts"][-1] if dep else None)
    # ROIC needs tax and invested capital; return explicit blocked rather than using ROE.
    out["roic"] = metric(s.ticker, "roic", None, "ratio", "INSUFFICIENT_DATA",
                         "NOPAT / invested capital", missing="tax rate / invested capital inputs not implemented")
    for name in ("revenue_stability", "earnings_stability", "interest_coverage"):
        out[name] = metric(s.ticker, name, None, "ratio", "INSUFFICIENT_DATA",
                           missing="multi-period history / interest expense unavailable")
    if sector and sector.lower() in ("financials", "banks", "insurance", "real estate"):
        for name in ("net_debt_to_ebitda", "debt_to_equity"):
            if name in out: out[name] = metric(s.ticker, name, None, "ratio", "NOT_APPLICABLE",
                                               missing=f"not meaningful for {sector}")
    return out


def garp_metrics(s: Snapshot) -> dict:
    out = {}
    rev = _annual_series(s, "revenue"); gp = _annual_series(s, "gross_profit")
    op = _annual_series(s, "operating_income"); eps = _annual_series(s, "eps_diluted", "USD/shares")
    cfo = _annual_series(s, "cfo"); cap = _annual_series(s, "capex")
    def growth(name, series):
        if len(series) < 2:
            out[name] = metric(s.ticker, name, None, "ratio", "INSUFFICIENT_DATA", missing="two annual periods required")
            return
        a, b = series[-2], series[-1]
        if a.value <= 0:
            out[name] = metric(s.ticker, name, None, "ratio", "NOT_APPLICABLE",
                               missing="non-positive base; growth rate not meaningful")
            return
        v = (b.value - a.value) / abs(a.value)
        out[name] = metric(s.ticker, name, v, "ratio", "OK", "(latest - prior) / abs(prior)",
                           b.end, b.accepted_at or b.filed, b.availability_quality, accession=b.accession,
                           form=b.form, inputs=[_fact_ref(a), _fact_ref(b)])
    growth("revenue_growth", rev); growth("gross_profit_growth", gp)
    growth("operating_income_growth", op); growth("eps_growth", eps)
    fcf = []
    by_end = {f.end: f for f in cfo}
    for c in cap:
        if c.end in by_end: fcf.append(Fact(c.cik,"x","fcf",unit="USD",value=by_end[c.end].value-abs(c.value),start=c.start,end=c.end,filed=c.filed,form=c.form,accession=c.accession))
    growth("fcf_growth", fcf)
    for name, n in (("revenue_cagr_3y", 3), ("revenue_cagr_5y", 5)):
        if len(rev) < n + 1:
            out[name] = metric(s.ticker, name, None, "ratio", "INSUFFICIENT_DATA", missing=f"{n+1} annual periods required")
        else:
            a, b = rev[-(n+1)], rev[-1]
            if a.value <= 0: out[name] = metric(s.ticker, name, None, "ratio", "NOT_APPLICABLE", missing="non-positive base")
            else: out[name] = metric(s.ticker, name, (b.value/a.value)**(1/n)-1, "ratio", "OK", f"{n}y CAGR",
                                     b.end, b.accepted_at or b.filed, b.availability_quality, accession=b.accession, form=b.form,
                                     inputs=[_fact_ref(a), _fact_ref(b)])
    if len(rev) >= 2 and len(op) >= 2 and rev[-1].value != 0 and op[-1].value != 0:
        rg = (rev[-1].value-rev[-2].value)/abs(rev[-2].value)
        og = (op[-1].value-op[-2].value)/abs(op[-2].value)
        out["operating_leverage"] = metric(s.ticker, "operating_leverage", og-rg, "ratio", "OK",
                                           "operating_income_growth - revenue_growth", op[-1].end,
                                           op[-1].filed, op[-1].availability_quality, accession=op[-1].accession,
                                           form=op[-1].form, inputs=[_fact_ref(op[-2]), _fact_ref(op[-1])])
    else:
        out["operating_leverage"] = metric(s.ticker, "operating_leverage", None, "ratio", "INSUFFICIENT_DATA", missing="two annual periods required")
    out["peg"] = metric(s.ticker, "peg", None, "ratio", "DATA_BLOCKED",
                        missing="forward EPS estimates not licensed; historical EPS growth is not a substitute")
    return out


def analyze(ticker: str, cik: str, facts: list[Fact], *, as_of: str | None = None,
            market_price: float | None = None, current_shares: float | None = None,
            sector: str | None = None) -> dict:
    s = Snapshot(ticker, cik, facts, as_of)
    return {"ticker": ticker, "cik": cik, "as_of": as_of, "sector": sector,
            "value": value_metrics(s, market_price=market_price, current_shares=current_shares),
            "quality": quality_metrics(s, sector=sector), "garp": garp_metrics(s)}
