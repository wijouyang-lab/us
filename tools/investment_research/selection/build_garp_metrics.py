"""P6.14 historical GARP growth inputs from the P6.3 SEC panel.

No forward EPS, PEG or forecast is produced. All figures are historical annual
facts visible by the snapshot date. The output is an experimental research input,
not a GARP strategy.
"""
from __future__ import annotations
import argparse, csv, gzip, json, math, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

SNAPSHOT = date(2026, 11, 5)
DEFAULT_PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
DEFAULT_CURRENT = Path("data/universe/selection_inputs/us_equities_current.csv")
DEFAULT_OUT = Path("data/universe/selection_inputs/garp_growth_metrics_p614.csv")
FLOW_METRICS = ("Revenue", "EPSBasic", "OperatingIncome", "OperatingCashFlow", "CapitalExpenditure")


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
        if not e:
            continue
        key = (r.get("filed") or "", r.get("accn") or "")
        if e not in best or key > (best[e].get("filed") or "", best[e].get("accn") or ""):
            best[e] = r
    return [best[k] for k in sorted(best)]


def growth(latest, prior):
    if latest is None or prior is None or prior <= 0:
        return None
    return latest / prior - 1.0


def cagr(latest, prior, years):
    if latest is None or prior is None or prior <= 0 or years <= 0:
        return None
    return (latest / prior) ** (1.0 / years) - 1.0


def find_near(rows, end, target_days, tol_days=250):
    best = None; best_delta = None
    for r in rows:
        d = dt(r.get("end"))
        if not d: continue
        delta = (end - d).days
        if abs(delta - target_days) <= tol_days and (best_delta is None or abs(delta-target_days) < best_delta):
            best = r; best_delta = abs(delta-target_days)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    ap.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    if not a.panel.exists(): print("PANEL_MISSING", a.panel); return 2
    facts = defaultdict(lambda: defaultdict(list))
    with gzip.open(a.panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("metric") not in FLOW_METRICS: continue
            if r.get("period_type") != "ANNUAL": continue
            if r.get("unit") not in ("USD", "USD/shares"): continue
            fd = dt(r.get("filed")); pit = dt(r.get("pit_available_date"))
            if not fd or fd > SNAPSHOT: continue
            if pit and pit > SNAPSHOT: continue
            val = num(r.get("value"))
            if val is None: continue
            cik = (r.get("cik") or "").zfill(10)
            facts[cik][r["metric"]].append(r)
    # one primary target security per CIK
    current = list(csv.DictReader(a.current.open(encoding="utf-8")))
    by_cik = defaultdict(list)
    for r in current:
        cik = (r.get("CIK") or "").zfill(10)
        if cik and r.get("security_type") in ("COMMON", "ADR"):
            by_cik[cik].append(r)
    rows = []
    for cik, secs in sorted(by_cik.items()):
        secs.sort(key=lambda x: (x.get("security_type") != "COMMON", x.get("ticker", "")))
        sec = secs[0]
        f = facts.get(cik, {})
        series = {m: latest_by_end(f.get(m, [])) for m in FLOW_METRICS}
        latest_end = max((dt(x[-1].get("end")) for x in series.values() if x), default=None)
        base = {m: (series[m][-1] if series[m] else None) for m in FLOW_METRICS}
        prior = {m: (find_near(series[m][:-1], latest_end, 365) if series[m] and latest_end else None) for m in FLOW_METRICS}
        rev_now = num(base["Revenue"].get("value")) if base["Revenue"] else None
        rev_prior = num(prior["Revenue"].get("value")) if prior["Revenue"] else None
        eps_now = num(base["EPSBasic"].get("value")) if base["EPSBasic"] else None
        eps_prior = num(prior["EPSBasic"].get("value")) if prior["EPSBasic"] else None
        oi_now = num(base["OperatingIncome"].get("value")) if base["OperatingIncome"] else None
        oi_prior = num(prior["OperatingIncome"].get("value")) if prior["OperatingIncome"] else None
        cfo_now = num(base["OperatingCashFlow"].get("value")) if base["OperatingCashFlow"] else None
        cfo_prior = num(prior["OperatingCashFlow"].get("value")) if prior["OperatingCashFlow"] else None
        capex_now = num(base["CapitalExpenditure"].get("value")) if base["CapitalExpenditure"] else None
        capex_prior = num(prior["CapitalExpenditure"].get("value")) if prior["CapitalExpenditure"] else None
        fcf_now = cfo_now - abs(capex_now) if cfo_now is not None and capex_now is not None else None
        fcf_prior = cfo_prior - abs(capex_prior) if cfo_prior is not None and capex_prior is not None else None
        rev_g = growth(rev_now, rev_prior)
        eps_g = growth(eps_now, eps_prior)
        fcf_g = growth(fcf_now, fcf_prior)
        # 3Y / 5Y CAGR using closest annual anchor
        c3 = None; c5 = None
        if latest_end and series["Revenue"]:
            if len(series["Revenue"]) >= 2:
                r3 = find_near(series["Revenue"][:-1], latest_end, 365 * 3)
                r5 = find_near(series["Revenue"][:-1], latest_end, 365 * 5)
                if r3:
                    c3 = cagr(rev_now, num(r3.get("value")), (latest_end - dt(r3.get("end"))).days / 365.25)
                if r5:
                    c5 = cagr(rev_now, num(r5.get("value")), (latest_end - dt(r5.get("end"))).days / 365.25)
        margin_now = oi_now / rev_now if oi_now is not None and rev_now not in (None, 0) else None
        margin_prior = oi_prior / rev_prior if oi_prior is not None and rev_prior not in (None, 0) else None
        margin_exp = margin_now - margin_prior if margin_now is not None and margin_prior is not None else None
        op_lev = ((oi_now / oi_prior - 1) - rev_g) if oi_now is not None and oi_prior not in (None, 0) and rev_g is not None else None
        eps_series = [num(x.get("value")) for x in series["EPSBasic"][-5:]]
        eps_series = [x for x in eps_series if x is not None]
        stability = None
        if len(eps_series) >= 3 and statistics.mean(eps_series) > 0:
            cv = statistics.pstdev(eps_series) / abs(statistics.mean(eps_series))
            stability = 1.0 / (1.0 + cv)
        have = [x for x in (rev_g, c3, eps_g, fcf_g, stability, margin_exp, op_lev) if x is not None]
        status = "GARP_HISTORY_AVAILABLE" if len(have) >= 2 else "GARP_DATA_BLOCKED"
        reasons = []
        if rev_now is None: reasons.append("REVENUE_MISSING")
        if len(eps_series) < 3: reasons.append("EPS_HISTORY_LT_3Y")
        if fcf_now is None: reasons.append("FCF_MISSING")
        if len(series["Revenue"]) < 2: reasons.append("REVENUE_HISTORY_LT_2Y")
        filed = max((x.get("filed") or "" for x in base.values() if x and x.get("filed")), default="")
        accn = next((x.get("accn") or "" for x in base.values() if x and x.get("accn")), "")
        rows.append({
            "ticker": sec.get("ticker", ""), "cik": cik,
            "company_name": sec.get("security_name", ""), "security_type": sec.get("security_type", ""),
            "model_family": sec.get("model_family", ""), "accounting_standard": "",
            "latest_period": latest_end.isoformat() if latest_end else "", "filed": filed,
            "accn": accn, "history_years": len({(x.get("end") or "")[:4] for x in series["Revenue"]}),
            "revenue": rev_now, "revenue_growth_1y": rev_g,
            "revenue_cagr_3y": c3, "revenue_cagr_5y": c5,
            "eps_basic": eps_now, "eps_growth_1y": eps_g,
            "fcf": fcf_now, "fcf_growth_1y": fcf_g,
            "operating_margin": margin_now, "operating_margin_expansion": margin_exp,
            "operating_leverage": op_lev, "earnings_stability": stability,
            "history_metric_count": len(have),
            "status": status, "reason_codes": "|".join(dict.fromkeys(reasons)),
            "data_as_of": SNAPSHOT.isoformat(),
        })
    fields = list(rows[0].keys()) if rows else []
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(json.dumps({"out": str(a.out), "rows": len(rows), "available": sum(1 for r in rows if r["status"]=="GARP_HISTORY_AVAILABLE"),
                      "blocked": sum(1 for r in rows if r["status"]=="GARP_DATA_BLOCKED")}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
