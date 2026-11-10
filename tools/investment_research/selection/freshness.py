"""P6.16 fundamentals freshness gate for all Value/Quality/GARP candidates.

The available ranking files carry period_end and filed dates but not a complete
subsequent 10-K/10-Q history. This gate is therefore limited to the stored SEC
period/filed metadata; that boundary is reported explicitly.
"""
from __future__ import annotations
import argparse, csv, json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path("data/universe/selection")
AS_OF = date(2026, 11, 5)
DOMESTIC_DAYS = 400
FPI_DAYS = 540


def read(p):
    b = p.read_bytes()[:2]
    with p.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def dt(v):
    try: return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError): return None


def age(period, filed):
    p, f = dt(period), dt(filed)
    if not p or not f or f > AS_OF: return None, None
    return (AS_OF - p).days, (AS_OF - f).days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT)
    a = ap.parse_args()
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "as_of": AS_OF.isoformat(),
               "thresholds_days": {"DOMESTIC_US_GAAP": DOMESTIC_DAYS, "FPI_IFRS": FPI_DAYS,
                                    "MIXED_NONE": "DATA_BLOCKED"},
               "boundary": "Stored period/filed metadata only; no full subsequent filing history.",
               "rankings": {}}
    specs = (("value", "value_rankings.csv", "value_composite_experimental", "value_rank"),
             ("quality", "quality_rankings.csv", "quality_score_recomputed", "quality_rank"),
             ("garp", "garp_rankings.csv", "garp_score", "garp_rank"))
    for kind, filename, score_field, rank_field in specs:
        rows = read(ROOT / filename)
        out = []
        for r in rows:
            period = r.get("financial_period") or r.get("latest_period") or ""
            filed = r.get("filed") or ""
            acc = r.get("accounting_standard") or "NONE"
            p_age, f_age = age(period, filed)
            reasons = []
            if not period: reasons.append("PERIOD_MISSING")
            if not filed: reasons.append("FILED_MISSING")
            if acc in ("MIXED", "NONE"): reasons.append("ACCOUNTING_STANDARD_UNSUPPORTED")
            if p_age is None or f_age is None: reasons.append("PERIOD_OR_FILED_INVALID_OR_FUTURE")
            limit = FPI_DAYS if acc == "IFRS" else DOMESTIC_DAYS
            if p_age is not None and p_age > limit: reasons.append("PERIOD_OLDER_THAN_" + str(limit) + "D")
            if f_age is not None and f_age > limit: reasons.append("FILED_OLDER_THAN_" + str(limit) + "D")
            if "PERIOD_MISSING" in reasons or "FILED_MISSING" in reasons:
                status = "FUNDAMENTALS_UPDATE_MISSING"
            elif "ACCOUNTING_STANDARD_UNSUPPORTED" in reasons or "PERIOD_OR_FILED_INVALID_OR_FUTURE" in reasons:
                status = "FUNDAMENTALS_DATA_BLOCKED"
            elif reasons:
                status = "FUNDAMENTALS_STALE"
            else:
                status = "FUNDAMENTALS_FRESH"
            sc = r.get(score_field)
            out.append({**r, "score_for_freshness": sc, "original_rank": r.get(rank_field, ""),
                        "period_age_days": p_age, "filed_age_days": f_age,
                        "freshness_status": status, "freshness_reason": "|".join(dict.fromkeys(reasons)),
                        "filing_regime": "FPI_IFRS" if acc == "IFRS" else ("DOMESTIC_US_GAAP" if acc == "US_GAAP" else acc)})
        fresh = [r for r in out if r["freshness_status"] == "FUNDAMENTALS_FRESH" and r.get(score_field) not in ("", None)]
        fresh.sort(key=lambda r: (-float(r[score_field]), r["ticker"], r["cik"]))
        for i, r in enumerate(fresh, 1):
            r["freshness_adjusted_rank"] = i
        for r in out:
            r.setdefault("freshness_adjusted_rank", "")
        fields = list(out[0].keys()) if out else []
        path = a.out / f"{kind}_freshness_adjusted.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(out)
        top_original = [r for r in out if str(r.get("original_rank", "")).isdigit() and int(r["original_rank"]) <= 50]
        top_fresh = fresh[:50]
        summary["rankings"][kind] = {
            "rows": len(out),
            "status_counts": dict(Counter(r["freshness_status"] for r in out)),
            "fresh_scored": len(fresh),
            "original_top50": len(top_original),
            "fresh_top50": len(top_fresh),
            "stale_excluded_from_fresh_top50": [{"ticker": r["ticker"], "period": r.get("financial_period") or r.get("latest_period"),
                                                 "filed": r.get("filed"), "status": r["freshness_status"],
                                                 "reason": r["freshness_reason"]} for r in out
                                                 if r.get("original_rank") and str(r["original_rank"]).isdigit()
                                                 and int(r["original_rank"]) <= 50 and r["freshness_status"] != "FUNDAMENTALS_FRESH"],
            "top20_original": [{"ticker": r["ticker"], "period": r.get("financial_period") or r.get("latest_period"),
                                "filed": r.get("filed"), "status": r["freshness_status"]}
                               for r in out if r.get("original_rank") and str(r["original_rank"]).isdigit()
                               and int(r["original_rank"]) <= 20],
            "top20_fresh": [{"ticker": r["ticker"], "period": r.get("financial_period") or r.get("latest_period"),
                             "filed": r.get("filed")} for r in top_fresh[:20]],
        }
    (a.out / "freshness_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: {"rows": v["rows"], "status": v["status_counts"], "fresh_scored": v["fresh_scored"]}
                      for k, v in summary["rankings"].items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
