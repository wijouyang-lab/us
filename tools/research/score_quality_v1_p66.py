"""P6.6 Quality V1 research score from P6.3 annual panel.

Research only; no production score/backtest.
"""
from __future__ import annotations
import argparse, csv, gzip, json, math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

CURRENT = Path("data/universe/us_equities_current.csv")
READY = Path("data/universe/us_equity_quality_readiness_p65.csv")
SIC = Path("data/universe/us_equity_industry_sic_p65.csv")
QUOTES = Path("data/universe/us_market_quote_mapping_p62.csv")
PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
OUT_SCORES = Path("data/universe/quality_v1_scores_p66.csv")
OUT_METRICS = Path("data/universe/quality_v1_metric_coverage_p66.csv")
OUT_AUDIT = Path("data/universe/quality_v1_scoring_audit_p66.json")
SPEC = Path("data/universe/quality_v1_model_spec_p66.json")
SNAPSHOT = date(2026, 11, 5)
METRICS = ("NetIncome", "TotalAssets", "StockholdersEquity", "TotalLiabilities",
           "OperatingCashFlow", "Revenue", "OperatingIncome")
FAMILY_TO_GROUP = None


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _date(v):
    try: return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError): return None


def average_balance(current, prior):
    a, b = num(current), num(prior)
    if a is None or b is None: return None
    return (a + b) / 2.0


def ratio(numerator, denominator, allow_negative_num=True):
    n, d = num(numerator), num(denominator)
    if n is None or d is None or d <= 0: return None
    if not allow_negative_num and n < 0: return None
    return n / d


def calc_quality_metrics(current, prior):
    """current/prior each map annual-flow and instant values.

    Required keys:
      NetIncome, TotalAssets, StockholdersEquity, TotalLiabilities,
      OperatingCashFlow, Revenue, OperatingIncome.
    TotalAssets/StockholdersEquity are current-year instant values in current;
    prior contains prior-year instant values.
    """
    ni = num(current.get("NetIncome")); assets = num(current.get("TotalAssets"))
    equity = num(current.get("StockholdersEquity")); liabilities = num(current.get("TotalLiabilities"))
    ocf = num(current.get("OperatingCashFlow")); revenue = num(current.get("Revenue"))
    opinc = num(current.get("OperatingIncome"))
    avg_assets = average_balance(current.get("TotalAssets"), prior.get("TotalAssets"))
    avg_equity = average_balance(current.get("StockholdersEquity"), prior.get("StockholdersEquity"))
    roe = ratio(ni, avg_equity) if avg_equity is not None and avg_equity > 0 else None
    roa = ratio(ni, avg_assets) if avg_assets is not None and avg_assets > 0 else None
    cfo = ratio(ocf, avg_assets) if avg_assets is not None and avg_assets > 0 else None
    lev = ratio(liabilities, assets, allow_negative_num=False) if assets and assets > 0 and liabilities is not None and liabilities >= 0 else None
    opm = ratio(opinc, revenue, allow_negative_num=True) if revenue and revenue > 0 else None
    return {"roe": roe, "roa": roa, "cfo_to_avg_assets": cfo,
            "liabilities_to_assets": lev, "operating_margin": opm,
            "avg_assets": avg_assets, "avg_equity": avg_equity}


def winsorize(values, lower=0.01, upper=0.99):
    vals = [v for v in values if v is not None]
    if not vals: return {}
    lo, hi = np.percentile(vals, [lower * 100, upper * 100])
    return {i: min(max(v, lo), hi) for i, v in enumerate(values) if v is not None}, lo, hi


def percentile_map(pairs, higher_is_better=True):
    """pairs: [(key, value)] unique issuer keys -> 0..100 percentile."""
    if not pairs: return {}
    s = pd.Series({k: v for k, v in pairs}, dtype=float)
    s = s.rank(pct=True, method="average") * 100.0
    if not higher_is_better:
        s = 100.0 - s
    return s.to_dict()


def select_annual(panel: Path, cutoff: date = SNAPSHOT):
    """Read panel once and retain PIT-visible annual/instant facts."""
    annual = defaultdict(lambda: defaultdict(list))
    instant = defaultdict(lambda: defaultdict(list))
    restatements = Counter()
    with gzip.open(panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("unit") not in ("USD", "USD/shares"): continue
            pit = _date(r.get("pit_available_date"))
            filed = _date(r.get("filed"))
            if not pit or not filed or pit > cutoff: continue
            cik = (r.get("cik") or "").zfill(10)
            m = r.get("metric")
            if m not in METRICS: continue
            rec = {"value": num(r.get("value")), "filed": r.get("filed") or "",
                   "accn": r.get("accn") or "", "form": r.get("form") or "",
                   "end": r.get("end") or "", "start": r.get("start") or "",
                   "taxonomy": r.get("taxonomy") or "", "tag": r.get("tag") or "",
                   "period_type": r.get("period_type") or ""}
            if rec["value"] is None: continue
            key = (r.get("end") or "")[:10]
            if m in ("TotalAssets", "StockholdersEquity", "TotalLiabilities"):
                instant[cik][m].append(rec)
            elif r.get("period_type") == "ANNUAL":
                annual[cik][m].append(rec)
    for cik, d in annual.items():
        for m, vals in d.items():
            vals.sort(key=lambda x: (x["end"], x["filed"], x["accn"]))
            # latest filing per end (restatement); preserve latest, count older versions
            restatements[(cik, m)] += max(0, len(vals) - len({x["end"] for x in vals}))
            d[m] = vals
    for cik, d in instant.items():
        for m, vals in d.items():
            vals.sort(key=lambda x: (x["end"], x["filed"], x["accn"]))
            d[m] = vals
    return annual, instant, restatements


def latest_for_end(vals, end):
    same = [x for x in vals if x["end"][:10] == end[:10]]
    if not same: return None
    same.sort(key=lambda x: (x["filed"], x["accn"]))
    return same[-1]


def build_issuer_financials(annual, instant):
    out = {}
    for cik, flows in annual.items():
        ni_rows = flows.get("NetIncome", [])
        if not ni_rows: continue
        end = ni_rows[-1]["end"][:10]
        # latest annual NetIncome for the chosen period, latest filing
        ni = latest_for_end(flows.get("NetIncome", []), end)
        if not ni: continue
        cur = {"NetIncome": ni}
        for m in ("OperatingCashFlow", "Revenue", "OperatingIncome"):
            x = latest_for_end(flows.get(m, []), end)
            if x: cur[m] = x
        balances = {}
        for m in ("TotalAssets", "StockholdersEquity", "TotalLiabilities"):
            x = latest_for_end(instant.get(cik, {}).get(m, []), end)
            if x: balances[m] = x
        if not balances.get("TotalAssets") or not balances.get("StockholdersEquity"): continue
        # prior year: closest instant end 300-430 days earlier
        prior = {}
        for m in ("TotalAssets", "StockholdersEquity"):
            vals = instant.get(cik, {}).get(m, [])
            cand = []
            for x in vals:
                d = _date(x["end"]); e = _date(end)
                if d and e and 300 <= (e - d).days <= 430: cand.append(x)
            if cand:
                cand.sort(key=lambda x: (x["end"], x["filed"]))
                prior[m] = cand[-1]
        cur.update({"TotalAssets": balances["TotalAssets"], "StockholdersEquity": balances["StockholdersEquity"],
                    "TotalLiabilities": balances.get("TotalLiabilities")})
        # calc expects numeric current/prior; retain source separately
        nums = {k: num(v.get("value")) if isinstance(v, dict) else None for k, v in cur.items()}
        pnums = {m: num(prior[m].get("value")) if m in prior else None for m in ("TotalAssets","StockholdersEquity")}
        metrics = calc_quality_metrics(nums, pnums)
        out[cik] = {"metrics": metrics, "period": end, "filed": ni["filed"],
                    "accn": ni["accn"], "current": cur, "prior": prior,
                    "sources": {m: {"filed": v["filed"], "accn": v["accn"], "tag": v["tag"],
                                    "taxonomy": v["taxonomy"], "unit": "USD"}
                                for m, v in cur.items() if isinstance(v, dict)}}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--scores", type=Path, default=OUT_SCORES)
    ap.add_argument("--metrics-out", type=Path, default=OUT_METRICS)
    ap.add_argument("--audit", type=Path, default=OUT_AUDIT)
    ap.add_argument("--spec", type=Path, default=SPEC)
    a = ap.parse_args()
    if not a.panel.exists(): print("P6.3 PANEL ARTIFACT MISSING"); return 2
    with CURRENT.open(encoding="utf-8") as f: uni = list(csv.DictReader(f))
    with READY.open(encoding="utf-8") as f: ready = {r["ticker"]: r for r in csv.DictReader(f)}
    with SIC.open(encoding="utf-8") as f: sic = {r["ticker"]: r for r in csv.DictReader(f)}
    with QUOTES.open(encoding="utf-8") as f: quotes = {r["ticker"]: r for r in csv.DictReader(f)}
    annual, instant, restatements = select_annual(a.panel)
    fin = build_issuer_financials(annual, instant)
    candidates = [r for r in uni if r["security_type"] in ("COMMON","ADR") and
                  ready.get(r["ticker"], {}).get("quality_standard_model_input_ready") == "True"]
    cand_ciks = {r["CIK"].zfill(10) for r in candidates if r.get("CIK")}
    # compute issuer metrics and group membership
    groups = defaultdict(list)
    for cik in cand_ciks:
        q = ready.get(next((r["ticker"] for r in candidates if r["CIK"].zfill(10) == cik), ""), {})
        model = q.get("model_family") or "UNCLASSIFIED"
        acc = q.get("accounting_standard") or "NONE"
        f = fin.get(cik, {}).get("metrics")
        if not f: continue
        if all(f.get(k) is not None for k in ("roe","roa","cfo_to_avg_assets","liabilities_to_assets")):
            groups[(model, acc)].append((cik, f))
    # score each group; require >=30 unique issuers
    issuer_scores = {}
    group_meta = {}
    for key, items in groups.items():
        group_meta[key] = {"issuers": len(items), "scored": 0, "status": "INSUFFICIENT_PEER_GROUP"}
        if len(items) < 30:
            for cik, f in items: issuer_scores[cik] = {"metrics": f, "status": "INSUFFICIENT_PEER_GROUP", "group": key}
            continue
        cols = {}
        for metric in ("roe","roa","cfo_to_avg_assets","liabilities_to_assets"):
            vals = [f[metric] for _, f in items]
            lo, hi = np.percentile(vals, [1, 99])
            clipped = [min(max(v, lo), hi) for v in vals]
            # leverage inverse: higher is better
            s = pd.Series(clipped, dtype=float)
            pct = s.rank(pct=True, method="average") * 100.0
            if metric == "liabilities_to_assets": pct = 100.0 - pct
            cols[metric] = pct.tolist()
        scored = 0
        for i, (cik, f) in enumerate(items):
            score = 0.30*cols["roe"][i] + 0.25*cols["roa"][i] + 0.25*cols["cfo_to_avg_assets"][i] + 0.20*cols["liabilities_to_assets"][i]
            issuer_scores[cik] = {"metrics": f, "score": score,
                "pct": {m: cols[m][i] for m in cols}, "status": "QUALITY_V1_SCORED", "group": key}
            scored += 1
        group_meta[key]["scored"] = scored
        group_meta[key]["status"] = "SCORED"
    # assign ranks within each comparison group
    rank_meta = {}
    for key in group_meta:
        vals = [(cik, x["score"]) for cik, x in issuer_scores.items() if x.get("group") == key and x.get("score") is not None]
        vals.sort(key=lambda x: x[1], reverse=True)
        ranks = {cik: i+1 for i, (cik, _) in enumerate(vals)}
        rank_meta[key] = {"count": len(vals), "ranks": ranks}
    # security rows
    rows = []
    scored_securities = 0
    for u in uni:
        t = u["ticker"]; ci = (u.get("CIK") or "").strip().zfill(10) if (u.get("CIK") or "").strip() else ""
        rd = ready.get(t, {}); sd = sic.get(t, {}); q = quotes.get(t, {})
        candidate = t in {r["ticker"] for r in candidates}
        iss = issuer_scores.get(ci)
        status = "QUALITY_V1_BLOCKED"; blockers = []
        if u["security_type"] == "UNCLASSIFIED":
            status = "QUALITY_V1_BLOCKED"; blockers.append("UNCLASSIFIED_SECURITY")
        elif sd.get("model_family") in ("BANKS","INSURANCE","REIT","BDC","OTHER_FINANCIALS","UTILITIES","ENERGY"):
            status = "QUALITY_V1_SPECIAL_MODEL_REQUIRED"; blockers.append("P6_5_SPECIAL_MODEL")
        elif not candidate:
            status = "QUALITY_V1_BLOCKED"; blockers.append("NOT_P6_5_STANDARD_INPUT_READY")
        elif iss and iss.get("score") is not None:
            status = "QUALITY_V1_SCORED"; scored_securities += 1
        elif iss and iss.get("status") == "INSUFFICIENT_PEER_GROUP":
            status = "INSUFFICIENT_PEER_GROUP"; blockers.append("INSUFFICIENT_PEER_GROUP")
        else:
            status = "QUALITY_V1_BLOCKED"; blockers.append("FINANCIAL_METRICS_OR_PIT_INCOMPLETE")
        f = iss.get("metrics") if iss else {}
        rank = rank_meta.get(iss.get("group"), {}).get("ranks", {}).get(ci) if iss else None
        rows.append({"ticker": t, "cik": ci, "industry": sd.get("model_family") or "UNCLASSIFIED",
            "model_family": sd.get("model_family") or "UNCLASSIFIED",
            "security_type": u["security_type"],
            "cohort": "TARGET" if u["security_type"] in ("COMMON","ADR") else "UNCLASSIFIED",
            "accounting_standard": rd.get("accounting_standard") or "NONE",
            "candidate": candidate, "financial_period": fin.get(ci, {}).get("period", ""),
            "filed": fin.get(ci, {}).get("filed", ""), "accn": fin.get(ci, {}).get("accn", ""),
            "roe": f.get("roe", "") if f else "", "roa": f.get("roa", "") if f else "",
            "cfo_to_avg_assets": f.get("cfo_to_avg_assets", "") if f else "",
            "liabilities_to_assets": f.get("liabilities_to_assets", "") if f else "",
            "operating_margin": f.get("operating_margin", "") if f else "",
            "avg_assets": f.get("avg_assets", "") if f else "",
            "avg_equity": f.get("avg_equity", "") if f else "",
            "roe_percentile": iss.get("pct",{}).get("roe","") if iss else "",
            "roa_percentile": iss.get("pct",{}).get("roa","") if iss else "",
            "cfo_percentile": iss.get("pct",{}).get("cfo_to_avg_assets","") if iss else "",
            "leverage_percentile": iss.get("pct",{}).get("liabilities_to_assets","") if iss else "",
            "quality_v1_score": iss.get("score","") if iss else "",
            "quality_v1_rank": rank or "", "scoring_status": status,
            "blocker_codes": "|".join(dict.fromkeys(blockers)),
            "research_label": "RESEARCH_ONLY_NOT_PRODUCTION_APPROVED_NOT_BACKTEST_VALIDATED",
            "data_as_of": "2026-11-05"})
    a.scores.parent.mkdir(parents=True, exist_ok=True)
    with a.scores.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    # metric coverage on candidates
    coverage = []
    for m in ("roe","roa","cfo_to_avg_assets","liabilities_to_assets","operating_margin"):
        valid = sum(1 for cik in cand_ciks if fin.get(cik, {}).get("metrics", {}).get(m) is not None)
        coverage.append({"metric": m, "candidate_securities": len(candidates),
                         "candidate_issuers": len(cand_ciks),
                         "valid_issuers": valid, "missing_issuers": len(cand_ciks)-valid,
                         "valid_rate": round(valid/len(cand_ciks),6) if cand_ciks else 0})
    with a.metrics_out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(coverage[0].keys())); w.writeheader(); w.writerows(coverage)
    status_counts = Counter(r["scoring_status"] for r in rows if r["security_type"] in ("COMMON","ADR"))
    by_acc = {}
    for acc in ("US_GAAP","IFRS","MIXED","NONE"):
        rs = [r for r in rows if r["security_type"] in ("COMMON","ADR") and r["accounting_standard"] == acc]
        by_acc[acc] = {"records": len(rs), "scored": sum(1 for r in rs if r["scoring_status"]=="QUALITY_V1_SCORED")}
    by_family = {}
    for fam in sorted({r["model_family"] for r in rows if r["security_type"] in ("COMMON","ADR")}):
        rs = [r for r in rows if r["security_type"] in ("COMMON","ADR") and r["model_family"] == fam]
        by_family[fam] = {"records": len(rs), "scored": sum(1 for r in rs if r["scoring_status"]=="QUALITY_V1_SCORED")}
    top = {}
    for (model, acc), meta in group_meta.items():
        rs = sorted([(cik, issuer_scores[cik]["score"]) for cik, x in issuer_scores.items()
                     if x.get("group")==(model,acc) and x.get("score") is not None], key=lambda x: x[1], reverse=True)[:10]
        tops = []
        for cik, sc in rs:
            tick = next((r["ticker"] for r in candidates if r["CIK"].zfill(10)==cik), "")
            tops.append({"ticker": tick, "cik": cik, "score": round(sc,2)})
        top[f"{model}|{acc}"] = {"group": meta, "top10": tops}
    reason_counts = Counter()
    for r in rows:
        if r["security_type"] in ("COMMON","ADR") and r["scoring_status"] != "QUALITY_V1_SCORED":
            reason_counts[r["blocker_codes"]] += 1
    audit = {"metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_date": str(SNAPSHOT), "panel": str(a.panel),
        "research_label": "RESEARCH_ONLY_NOT_PRODUCTION_APPROVED_NOT_BACKTEST_VALIDATED",
        "pit_rule": "P6.3 filed -> next weekday; no holiday/acceptanceDateTime adjustment"},
        "candidate_securities": len(candidates), "candidate_unique_ciks": len(cand_ciks),
        "issuers_with_four_metrics": len(issuer_scores),
        "scored_securities": scored_securities,
        "scored_issuers": sum(1 for x in issuer_scores.values() if x.get("score") is not None),
        "status_counts": dict(status_counts), "by_accounting": by_acc, "by_family": by_family,
        "group_status": {f"{k[0]}|{k[1]}": v for k,v in group_meta.items()},
        "top10_by_group": top, "metric_coverage": coverage,
        "restatement_versions_observed": sum(restatements.values()),
        "blockers": reason_counts.most_common(20),
        "score_ready": False, "backtest_ready": False,
        "notes": ["V1 formula is a research hypothesis, not validated alpha.",
                  "Four primary metrics must all be present; no weight reallocation.",
                  "Peer groups are model_family x accounting_standard; <30 issuers gets no percentile."]}
    a.audit.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    spec = {"version":"P6.6-V1","status":"RESEARCH_ONLY","snapshot_date":"2026-11-05",
            "universe":"P6.5 quality_standard_model_input_ready",
            "weights":{"roe":0.30,"roa":0.25,"cfo_to_avg_assets":0.25,"inverse_liabilities_to_assets":0.20},
            "peer_key":["model_family","accounting_standard"],"min_peer_issuers":30,
            "winsorization":"1%/99% within peer group","operating_margin":"diagnostic only; weight 0",
            "period":"latest fully annual fiscal year, current and prior instant balances",
            "pit_rule":"P6.3 pit_available_date <= 2026-11-05; no holiday adjustment",
            "excluded_families":["BANKS","INSURANCE","REIT","BDC","OTHER_FINANCIALS","UTILITIES","ENERGY","UNCLASSIFIED"]}
    a.spec.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(json.dumps({"candidates":len(candidates),"unique_ciks":len(cand_ciks),"scored_securities":scored_securities,
                      "scored_issuers":audit["scored_issuers"],"status":dict(status_counts),
                      "groups":{f"{k[0]}|{k[1]}":v["status"] for k,v in group_meta.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
