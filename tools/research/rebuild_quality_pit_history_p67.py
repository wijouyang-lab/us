"""P6.7 historical Quality V1 PIT feasibility gate and history rebuild."""
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
P66 = Path("data/universe/quality_v1_scores_p66.csv")
PANEL = Path("data/universe/sec_fundamentals_panel_p63.csv.gz")
PRICE = Path("research_price_history_sp500_10y.csv")
COMPONENTS = Path("tools/research/data/sp500_components_history.csv")
ALIASES = Path("tools/research/data/sp500_ticker_aliases.csv")
OUT_COVER = Path("data/research/quality_pit_coverage_p67.json")
OUT_SCORES = Path("data/research/quality_pit_scores_p67.csv.gz")
OUT_STAB = Path("data/research/quality_historical_stability_p67.json")
SPECIAL = {"BANKS","INSURANCE","REIT","BDC","OTHER_FINANCIALS","UTILITIES","ENERGY","UNCLASSIFIED"}
ANNUAL = "ANNUAL"
REBALANCE = [f"{y}-{m:02d}-{d:02d}" for y in range(2016, 2027) for m, d in ((3,31),(6,30),(9,30),(12,31))
             if (y, m, d) >= (2016, 3, 31) and (y, m, d) <= (2026, 9, 30)]


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None


def d(v):
    try: return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError): return None


def norm(v):
    import re
    x = re.sub(r"[^A-Z0-9]", ".", str(v or "").upper())
    return re.sub(r"\.+", ".", x).strip(".")


def build_pit_prices(price_path: Path):
    p = pd.read_csv(price_path, usecols=["Date", "Ticker", "Close"])
    p["Date"] = pd.to_datetime(p["Date"]).dt.date
    p["key"] = p["Ticker"].map(norm)
    p = p.sort_values(["key", "Date"]).drop_duplicates(["key", "Date"], keep="last")
    by = {k: g.reset_index(drop=True) for k, g in p.groupby("key")}
    return by


def membership_events(path: Path, aliases_path: Path):
    aliases = {}
    if aliases_path.exists():
        for r in csv.DictReader(aliases_path.open(encoding="utf-8")):
            aliases[norm(r["old_ticker"])] = norm(r["canonical_ticker"])
    rows = []
    for r in csv.DictReader(path.open(encoding="utf-8")):
        rows.append({"symbol": norm(r["symbol"]), "cik": str(r.get("cik") or "").zfill(10),
                     "added": d(r.get("date_added")), "removed": d(r.get("date_removed")),
                     "canonical": aliases.get(norm(r["symbol"]), norm(r["symbol"]))})
    return rows


def price_on_or_before(series, obs, max_days=7):
    if series is None or series.empty: return None
    x = series[series["Date"] <= obs]
    if x.empty: return None
    r = x.iloc[-1]
    if (obs - r["Date"]).days > max_days: return None
    return r


def load_panel_stats(panel: Path):
    annual = defaultdict(lambda: defaultdict(list))
    instant = defaultdict(lambda: defaultdict(list))
    with gzip.open(panel, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("unit") != "USD": continue
            pit = d(r.get("pit_available_date")); end = d(r.get("end")); m = r.get("metric")
            if not pit or not end or m not in ("NetIncome","TotalAssets","StockholdersEquity",
                                               "TotalLiabilities","OperatingCashFlow","Revenue","OperatingIncome"):
                continue
            rec = {"value": num(r.get("value")), "end": end, "filed": d(r.get("filed")),
                   "accn": r.get("accn") or "", "period_type": r.get("period_type") or "",
                   "taxonomy": r.get("taxonomy") or "", "tag": r.get("tag") or ""}
            if rec["value"] is None: continue
            if m in ("TotalAssets","StockholdersEquity","TotalLiabilities"):
                instant[(r["cik"].zfill(10))][m].append(rec)
            elif rec["period_type"] == "ANNUAL":
                annual[r["cik"].zfill(10)][m].append(rec)
    return annual, instant


def visible_latest(recs, obs, end=None):
    xs = [x for x in recs if x["end"] <= obs and (x["filed"] is None or x["filed"] <= obs)]
    if end is not None: xs = [x for x in xs if x["end"] == end]
    if not xs: return None
    xs.sort(key=lambda x: (x["end"], x["filed"] or date.min, x["accn"]))
    return xs[-1]


def financials_at(annual, instant, cik, obs):
    ni = visible_latest(annual.get(cik, {}).get("NetIncome", []), obs)
    if not ni: return None
    end = ni["end"]
    vals = {"NetIncome": ni["value"]}
    for m in ("OperatingCashFlow","Revenue","OperatingIncome"):
        x = visible_latest(annual.get(cik, {}).get(m, []), obs, end)
        if x: vals[m] = x["value"]
    for m in ("TotalAssets","StockholdersEquity","TotalLiabilities"):
        x = visible_latest(instant.get(cik, {}).get(m, []), obs, end)
        if x: vals[m] = x["value"]
    # prior year instant: closest visible period end 300-430 days earlier
    for m in ("TotalAssets","StockholdersEquity"):
        prior = None
        for x in instant.get(cik, {}).get(m, []):
            if x["end"] >= end or (x["filed"] is not None and x["filed"] > obs): continue
            delta = (end - x["end"]).days
            if 300 <= delta <= 430: prior = x
        if prior: vals[m + "_prior"] = prior["value"]
    return vals


def calc(vals):
    ni = vals.get("NetIncome"); assets = vals.get("TotalAssets"); eq = vals.get("StockholdersEquity")
    liab = vals.get("TotalLiabilities"); ocf = vals.get("OperatingCashFlow")
    avg_a = (assets + vals["TotalAssets_prior"]) / 2 if assets is not None and vals.get("TotalAssets_prior") is not None else None
    avg_e = (eq + vals["StockholdersEquity_prior"]) / 2 if eq is not None and vals.get("StockholdersEquity_prior") is not None else None
    roe = ni / avg_e if ni is not None and avg_e and avg_e > 0 else None
    roa = ni / avg_a if ni is not None and avg_a and avg_a > 0 else None
    cfo = ocf / avg_a if ocf is not None and avg_a and avg_a > 0 else None
    lev = liab / assets if liab is not None and assets and assets > 0 and liab >= 0 else None
    opm = vals.get("OperatingIncome") / vals["Revenue"] if vals.get("OperatingIncome") is not None and vals.get("Revenue") and vals["Revenue"] > 0 else None
    return {"roe": roe, "roa": roa, "cfo_to_avg_assets": cfo,
            "liabilities_to_assets": lev, "operating_margin": opm,
            "avg_assets": avg_a, "avg_equity": avg_e}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--price", type=Path, default=PRICE)
    ap.add_argument("--coverage", type=Path, default=OUT_COVER)
    ap.add_argument("--scores", type=Path, default=OUT_SCORES)
    ap.add_argument("--stability", type=Path, default=OUT_STAB)
    a = ap.parse_args()
    if not a.panel.exists(): print("P6.3 PANEL ARTIFACT MISSING"); return 2
    if not a.price.exists(): print("PRICE HISTORY MISSING"); return 2
    uni = list(csv.DictReader(CURRENT.open(encoding="utf-8")))
    ready = {r["ticker"]: r for r in csv.DictReader(READY.open(encoding="utf-8"))}
    sic = {r["ticker"]: r for r in csv.DictReader(SIC.open(encoding="utf-8"))}
    p66 = {r["ticker"]: r for r in csv.DictReader(P66.open(encoding="utf-8"))}
    prices = build_pit_prices(a.price)
    members = membership_events(COMPONENTS, ALIASES)
    total_obs = 0; price_obs = 0
    member_keys = set(); member_price_keys = set()
    for obs_s in REBALANCE:
        obs = d(obs_s)
        active = [m for m in members if m["added"] and m["added"] <= obs and (m["removed"] is None or obs < m["removed"])]
        for m in active:
            total_obs += 1; member_keys.add(m["canonical"])
            if price_on_or_before(prices.get(m["canonical"]), obs) is not None:
                price_obs += 1; member_price_keys.add(m["canonical"])
    member_session_cov = price_obs / total_obs if total_obs else 0
    ticker_cov = len(member_price_keys) / len(member_keys) if member_keys else 0
    # financial readiness and historical score rebuild
    annual, instant = load_panel_stats(a.panel)
    candidates = [r for r in uni if r["security_type"] in ("COMMON","ADR") and
                  ready.get(r["ticker"], {}).get("quality_standard_model_input_ready") == "True"]
    cand_ciks = {r["CIK"].zfill(10) for r in candidates if r.get("CIK")}
    fin_ready = 0; ni2 = 0; bal2 = 0; four_ready = 0; score_rows = []; quarter_counts = []
    for obs_s in REBALANCE:
        obs = d(obs_s)
        group = defaultdict(list)
        for cik in cand_ciks:
            q = next((r for r in candidates if r["CIK"].zfill(10) == cik), None)
            if not q: continue
            fam = sic.get(q["ticker"], {}).get("model_family", "UNCLASSIFIED")
            if fam in SPECIAL: continue
            vals = financials_at(annual, instant, cik, obs)
            if not vals: continue
            f = calc(vals)
            if all(f[k] is not None for k in ("roe","roa","cfo_to_avg_assets","liabilities_to_assets")):
                group[(fam, ready.get(q["ticker"], {}).get("accounting_standard","NONE"))].append((cik, f, vals))
        for key, items in group.items():
            if len(items) < 30: continue
            for metric in ("roe","roa","cfo_to_avg_assets","liabilities_to_assets"):
                s = pd.Series([x[1][metric] for x in items], dtype=float)
                lo, hi = np.percentile(s, [1,99]); s = s.clip(lo,hi)
                pct = s.rank(pct=True, method="average")*100
                if metric == "liabilities_to_assets": pct = 100-pct
                for i, (cik, f, vals) in enumerate(items):
                    f[metric + "_pct"] = pct.iloc[i]
            for cik, f, vals in items:
                score = 0.30*f["roe_pct"] + 0.25*f["roa_pct"] + 0.25*f["cfo_to_avg_assets_pct"] + 0.20*f["liabilities_to_assets_pct"]
                ticker = next(r["ticker"] for r in candidates if r["CIK"].zfill(10)==cik)
                score_rows.append({"observation_date": obs_s, "ticker": ticker, "cik": cik,
                    "model_family": key[0], "accounting_standard": key[1], "score": round(score,4),
                    "roe": f["roe"], "roa": f["roa"], "cfo_to_avg_assets": f["cfo_to_avg_assets"],
                    "liabilities_to_assets": f["liabilities_to_assets"], "financial_period": vals.get("end","")})
        quarter_counts.append({"observation_date": obs_s, "group_count": len(group),
                               "scored_issuers": sum(len(v) for k,v in group.items() if len(v)>=30)})
    # financial coverage counts from panel
    for cik in cand_ciks:
        ni = annual.get(cik, {}).get("NetIncome", [])
        ni_ends = {x["end"] for x in ni}
        a_ends = {x["end"] for x in instant.get(cik, {}).get("TotalAssets", [])}
        e_ends = {x["end"] for x in instant.get(cik, {}).get("StockholdersEquity", [])}
        if ni_ends: fin_ready += 1
        if len(ni_ends) >= 2: ni2 += 1
        if len(a_ends) >= 2 and len(e_ends) >= 2: bal2 += 1
        if ni_ends and a_ends and e_ends and any(True for _ in [0]): four_ready += 1
    a.scores.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(a.scores, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["observation_date","ticker","cik","model_family","accounting_standard",
                                          "score","roe","roa","cfo_to_avg_assets","liabilities_to_assets","financial_period"])
        w.writeheader(); w.writerows(score_rows)
    # stability: annual median and adjacent-year rank correlation
    df = pd.DataFrame(score_rows)
    stability = {"quarters": len(quarter_counts), "period_start": REBALANCE[0], "period_end": REBALANCE[-1],
                 "quarter_counts": quarter_counts,
                 "scored_issuer_observations": len(score_rows),
                 "scored_unique_issuers": int(df["cik"].nunique()) if not df.empty else 0}
    if not df.empty:
        df["year"] = df["observation_date"].str[:4]
        stability["annual"] = []
        for year, g in df.groupby("year"):
            stability["annual"].append({"year": year, "observations": len(g), "issuers": int(g["cik"].nunique()),
                "median_score": round(float(g["score"].median()),3), "q1": round(float(g["score"].quantile(.25)),3),
                "q3": round(float(g["score"].quantile(.75)),3)})
        # adjacent quarter rank persistence for issuers present both periods
        persist = []
        for q1, q2 in zip(REBALANCE, REBALANCE[1:]):
            x = df[df.observation_date==q1][["cik","score"]]
            y = df[df.observation_date==q2][["cik","score"]]
            z = x.merge(y, on="cik", suffixes=("_a","_b"))
            if len(z) >= 10:
                persist.append({"from":q1,"to":q2,"n":len(z),"spearman":round(float(z["score_a"].corr(z["score_b"],method="spearman")),4)})
        stability["adjacent_quarter_rank_persistence"] = persist
    a.stability.write_text(json.dumps(stability, indent=2, ensure_ascii=False), encoding="utf-8")
    # price readiness for 3/6/12 returns on current survivors (approximate)
    return_ready = {}
    for months in (3,6,12):
        n=0
        for r in candidates:
            key=norm(r["ticker"]); s=prices.get(key)
            if s is None: continue
            for obs_s in REBALANCE:
                obs=d(obs_s); end=date(obs.year + (obs.month+months-1)//12, (obs.month+months-1)%12+1, min(obs.day,28))
                if price_on_or_before(s,obs) is not None and price_on_or_before(s,end) is not None: n+=1; break
        return_ready[f"future_{months}m"] = n
    gate = member_session_cov >= .95 and ticker_cov >= .98
    coverage = {"metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
        "panel_artifact": "sec-fundamentals-p63 / 13402038887", "price_source": str(a.price),
        "price_file": "research_price_history_sp500_10y.csv", "scope": "S&P 500 historical members in price panel; current-survivor history is exploratory only",
        "current_sic_is_proxy": True, "pit_rule": "filed -> next weekday; holidays not adjusted"},
        "universe": {"current_target": len([r for r in uni if r["security_type"] in ("COMMON","ADR")]),
                     "current_candidates_p66": len(candidates), "candidate_unique_ciks": len(cand_ciks)},
        "membership": {"observations": len(REBALANCE), "member_sessions": total_obs,
                       "member_sessions_with_price": price_obs, "member_session_coverage": round(member_session_cov,6),
                       "unique_members": len(member_keys), "unique_members_with_price": len(member_price_keys),
                       "ticker_coverage": round(ticker_cov,6)},
        "financial": {"candidates_with_annual": fin_ready, "candidates_with_2_netincome": ni2,
                      "candidates_with_2_assets_equity": bal2,
                      "candidates_with_complete_four_metrics_any_quarter": int(df["cik"].nunique()) if not df.empty else 0,
                      "historical_quarters": len(REBALANCE)},
        "return_labels": return_ready,
        "gates": {"member_session_95": member_session_cov >= .95, "ticker_98": ticker_cov >= .98,
                  "backtest_ready": bool(gate), "validation_ready": bool(gate)},
        "status": "HISTORICAL_PIT_GATE_PASS" if gate else "HISTORICAL_PIT_GATE_FAIL",
        "notes": ["Current SIC is a non-PIT proxy.", "Price panel covers current S&P 500 survivors; delisted members are not fully present.",
                  "No forward-return test is claimed if the gate fails."]}
    a.coverage.write_text(json.dumps(coverage, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"membership": coverage["membership"], "financial": coverage["financial"],
                      "return_labels": return_ready, "gates": coverage["gates"], "stability": {"observations":len(score_rows)}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
