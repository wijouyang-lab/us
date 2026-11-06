"""P6.15 historical GARP inputs with strict fiscal-period matching.

No forward EPS, PEG or forecast. Annual facts only; each metric uses its own
latest fiscal period, and growth requires a matching prior period within an
explicit 52/53-week tolerance. Mismatched periods produce INSUFFICIENT_DATA.
"""
from __future__ import annotations
import argparse, csv, gzip, json, math, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

SNAPSHOT = date(2026, 11, 5)
DEFAULT_PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
DEFAULT_CURRENT = Path("data/universe/selection_inputs/us_equities_current.csv")
DEFAULT_CLASS = Path("data/universe/selection_inputs/issuer_classification_p615.csv")
DEFAULT_OUT = Path("data/universe/selection_inputs/garp_growth_metrics_p614.csv")
FLOWS = ("Revenue", "EPSBasic", "OperatingIncome", "OperatingCashFlow", "CapitalExpenditure")
TOL_1Y, TOL_3Y, TOL_5Y = 35, 45, 60


def read(path):
    b = path.read_bytes()[:2]
    with path.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def dt(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def latest_by_end(rows):
    best = {}
    for r in rows:
        e = (r.get("end") or "")[:10]
        if not e: continue
        key = (r.get("filed") or "", r.get("accn") or "")
        if e not in best or key > (best[e].get("filed") or "", best[e].get("accn") or ""):
            best[e] = r
    return [best[k] for k in sorted(best)]


def find_prior(rows, latest_end, target_days, tol):
    """Strict prior match near target days; never a several-hundred-day substitute."""
    if not latest_end: return None, None
    cand = []
    for r in rows:
        d = dt(r.get("end"))
        if not d or d >= latest_end: continue
        gap = (latest_end - d).days
        if abs(gap - target_days) <= tol:
            cand.append((abs(gap - target_days), gap, r))
    if not cand: return None, None
    cand.sort(key=lambda x: (x[0], x[1]))
    return cand[0][2], cand[0][1]


def same_end(rows, end):
    if not end: return None
    for r in rows:
        if (r.get("end") or "")[:10] == end[:10]:
            return r
    return None


def growth(latest, prior):
    if latest is None or prior is None or prior <= 0: return None
    return latest / prior - 1.0


def cagr(latest, prior, years):
    if latest is None or prior is None or latest <= 0 or prior <= 0 or years <= 0:
        return None
    return (latest / prior) ** (1.0 / years) - 1.0


def direction(latest, prior):
    if latest is None or prior is None: return "MISSING"
    if prior > 0 and latest > 0: return "POSITIVE_BASE"
    if prior > 0 and latest <= 0: return "TURNED_NEGATIVE"
    if prior <= 0 and latest > 0: return "TURNED_POSITIVE"
    return "BOTH_NONPOSITIVE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    ap.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    ap.add_argument("--classification", type=Path, default=DEFAULT_CLASS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    if not a.panel.exists(): print("PANEL_MISSING", a.panel); return 2
    facts = defaultdict(lambda: defaultdict(list))
    with gzip.open(a.panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("metric") not in FLOWS or r.get("period_type") != "ANNUAL": continue
            if r.get("unit") not in ("USD", "USD/shares"): continue
            fd = dt(r.get("filed")); pit = dt(r.get("pit_available_date"))
            if not fd or fd > SNAPSHOT or (pit and pit > SNAPSHOT): continue
            if num(r.get("value")) is None: continue
            cik = (r.get("cik") or "").zfill(10)
            facts[cik][r["metric"]].append(r)
    current = read(a.current)
    by_cik = defaultdict(list)
    for r in current:
        cik = (r.get("CIK") or "").zfill(10)
        if cik and r.get("security_type") in ("COMMON", "ADR"):
            by_cik[cik].append(r)
    cls = { (r.get("cik") or "").zfill(10): r for r in read(a.classification) } if a.classification.exists() else {}
    rows = []
    for cik, secs in sorted(by_cik.items()):
        secs.sort(key=lambda x: (x.get("security_type") != "COMMON", x.get("ticker", "")))
        sec = secs[0]
        series = {m: latest_by_end(facts.get(cik, {}).get(m, [])) for m in FLOWS}
        vals = {m: (num(series[m][-1].get("value")) if series[m] else None) for m in FLOWS}
        ends = {m: ((series[m][-1].get("end") or "")[:10] if series[m] else "") for m in FLOWS}
        filed = {m: ((series[m][-1].get("filed") or "") if series[m] else "") for m in FLOWS}
        accn = {m: ((series[m][-1].get("accn") or "") if series[m] else "") for m in FLOWS}
        # Each metric's own latest and prior
        prior_info = {}
        for m in ("Revenue", "EPSBasic"):
            end = dt(ends[m]); prior, gap = find_prior(series[m][:-1], end, 365, TOL_1Y)
            prior_info[m] = {"row": prior, "gap": gap}
        rev_end = dt(ends["Revenue"]); rev_prior = prior_info["Revenue"]["row"]
        eps_end = dt(ends["EPSBasic"]); eps_prior = prior_info["EPSBasic"]["row"]
        r_g = growth(vals["Revenue"], num(rev_prior.get("value")) if rev_prior else None)
        e_g = growth(vals["EPSBasic"], num(eps_prior.get("value")) if eps_prior else None)
        # FCF uses same-end CFO/capex
        cfo_end = ends["OperatingCashFlow"]; capex_same = same_end(series["CapitalExpenditure"], cfo_end)
        fcf_now = (vals["OperatingCashFlow"] - abs(num(capex_same.get("value")))
                   if vals["OperatingCashFlow"] is not None and capex_same else None)
        cfo_prior, cfo_gap = find_prior(series["OperatingCashFlow"][:-1], dt(cfo_end), 365, TOL_1Y) if cfo_end else (None, None)
        capex_prior = same_end(series["CapitalExpenditure"], (cfo_prior.get("end") or "")[:10]) if cfo_prior else None
        fcf_prior = (num(cfo_prior.get("value")) - abs(num(capex_prior.get("value")))
                     if cfo_prior and capex_prior else None)
        f_g = growth(fcf_now, fcf_prior)
        # 3Y/5Y revenue CAGR uses revenue's own latest end and strict anchor
        c3 = c5 = None; c3_gap = c5_gap = None; r3 = r5 = None
        if rev_end:
            r3, c3_gap = find_prior(series["Revenue"][:-1], rev_end, 1096, TOL_3Y)
            r5, c5_gap = find_prior(series["Revenue"][:-1], rev_end, 1826, TOL_5Y)
            if r3:
                c3 = cagr(vals["Revenue"], num(r3.get("value")), (rev_end - dt(r3.get("end"))).days / 365.25)
            if r5:
                c5 = cagr(vals["Revenue"], num(r5.get("value")), (rev_end - dt(r5.get("end"))).days / 365.25)
        # OI and margin must be same-period with revenue
        oi_now_row = same_end(series["OperatingIncome"], ends["Revenue"])
        oi_prior_row = same_end(series["OperatingIncome"], (rev_prior.get("end") or "")[:10]) if rev_prior else None
        oi_now = num(oi_now_row.get("value")) if oi_now_row else None
        oi_prior = num(oi_prior_row.get("value")) if oi_prior_row else None
        oi_g = growth(oi_now, oi_prior) if oi_now_row and oi_prior_row else None
        margin_now = oi_now / vals["Revenue"] if oi_now is not None and vals["Revenue"] not in (None, 0) else None
        margin_prior = oi_prior / num(rev_prior.get("value")) if oi_prior is not None and rev_prior and num(rev_prior.get("value")) not in (None, 0) else None
        margin_exp = margin_now - margin_prior if margin_now is not None and margin_prior is not None else None
        op_lev = (oi_g / r_g) if oi_g is not None and r_g not in (None, 0) else None
        op_spread = (oi_g - r_g) if oi_g is not None and r_g is not None else None
        eps_series = [num(x.get("value")) for x in series["EPSBasic"][-5:]]
        eps_series = [x for x in eps_series if x is not None]
        stability = None
        if len(eps_series) >= 3 and statistics.mean(eps_series) > 0:
            stability = 1.0 / (1.0 + statistics.pstdev(eps_series) / abs(statistics.mean(eps_series)))
        have = [x for x in (r_g, c3, c5, e_g, f_g, stability, margin_exp, op_lev) if x is not None]
        reasons = []
        if not rev_prior: reasons.append("REVENUE_PRIOR_NOT_MATCHED")
        if not eps_prior: reasons.append("EPS_PRIOR_NOT_MATCHED")
        if not cfo_prior or not capex_prior: reasons.append("FCF_PRIOR_NOT_MATCHED")
        if not r3: reasons.append("REVENUE_3Y_NOT_MATCHED")
        if not r5: reasons.append("REVENUE_5Y_NOT_MATCHED")
        if not oi_prior_row: reasons.append("OI_PRIOR_NOT_MATCHED")
        status = "GARP_HISTORY_AVAILABLE" if len(have) >= 2 else "GARP_DATA_BLOCKED"
        pd = {
            "Revenue": {"latest": ends["Revenue"], "prior": (rev_prior.get("end")[:10] if rev_prior else ""),
                        "latest_filed": filed["Revenue"], "prior_filed": (rev_prior.get("filed") if rev_prior else ""),
                        "days_apart": (rev_end - dt(rev_prior.get("end"))).days if rev_end and rev_prior else None},
            "EPS": {"latest": ends["EPSBasic"], "prior": (eps_prior.get("end")[:10] if eps_prior else ""),
                    "latest_filed": filed["EPSBasic"], "prior_filed": (eps_prior.get("filed") if eps_prior else ""),
                    "days_apart": (eps_end - dt(eps_prior.get("end"))).days if eps_end and eps_prior else None},
            "FCF": {"latest": cfo_end, "prior": (cfo_prior.get("end")[:10] if cfo_prior else ""),
                    "latest_filed": filed["OperatingCashFlow"], "prior_filed": (cfo_prior.get("filed") if cfo_prior else ""),
                    "days_apart": (dt(cfo_end) - dt(cfo_prior.get("end"))).days if cfo_end and cfo_prior else None},
            "Revenue3Y": {"prior": (r3.get("end")[:10] if r3 else ""), "days_apart": c3_gap},
            "Revenue5Y": {"prior": (r5.get("end")[:10] if r5 else ""), "days_apart": c5_gap},
        }
        rows.append({
            "ticker": sec.get("ticker", ""), "cik": cik, "company_name": sec.get("security_name", ""),
            "security_type": sec.get("security_type", ""),
            "model_family": (cls.get(cik) or {}).get("model_family") or "UNCLASSIFIED",
            "accounting_standard": (cls.get(cik) or {}).get("accounting_standard") or "NONE",
            "classification_status": (cls.get(cik) or {}).get("classification_status") or "UNCLASSIFIED",
            "latest_period": max((x for x in ends.values() if x), default=""),
            "filed": max((x for x in filed.values() if x), default=""),
            "accn": next((x for x in accn.values() if x), ""),
            "history_years": len({(x.get("end") or "")[:4] for x in series["Revenue"]}),
            "revenue": vals["Revenue"], "revenue_growth_1y": r_g,
            "revenue_cagr_3y": c3, "revenue_cagr_5y": c5,
            "eps_basic": vals["EPSBasic"], "eps_growth_1y": e_g,
            "eps_direction": direction(vals["EPSBasic"], num(eps_prior.get("value")) if eps_prior else None),
            "fcf": fcf_now, "fcf_growth_1y": f_g,
            "fcf_direction": direction(fcf_now, fcf_prior),
            "operating_income": oi_now,
            "operating_income_growth_1y": oi_g,
            "operating_margin": margin_now, "operating_margin_expansion": margin_exp,
            "operating_leverage_ratio": op_lev, "operating_growth_spread": op_spread,
            "earnings_stability": stability,
            "history_metric_count": len(have),
            "status": status, "reason_codes": "|".join(dict.fromkeys(reasons)),
            "period_detail_json": json.dumps(pd, ensure_ascii=False, separators=(",", ":")),
            "data_as_of": SNAPSHOT.isoformat(),
        })
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(json.dumps({"out": str(a.out), "rows": len(rows),
                      "available": sum(1 for r in rows if r["status"] == "GARP_HISTORY_AVAILABLE"),
                      "blocked": sum(1 for r in rows if r["status"] == "GARP_DATA_BLOCKED"),
                      "five_year": sum(1 for r in rows if r["revenue_cagr_5y"] not in ("", None))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
