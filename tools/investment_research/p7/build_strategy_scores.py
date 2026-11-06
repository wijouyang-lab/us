"""P7: assemble interpretable factor scores into four strategy definitions.

Missing factors are not treated as zero. A strategy is launchable only when at
least 10 names pass every data gate; no threshold is relaxed to reach that count.
"""
from __future__ import annotations
import csv, json, math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEL = Path("data/universe/selection")
OUT = Path("data/universe/p7")
OUT.mkdir(parents=True, exist_ok=True)
STRATEGIES = ("VALUE_V1", "QUALITY_V1", "GARP_V1", "BLENDED_V1")
MIN_LAUNCH = 10


def read(p):
    b = p.read_bytes()[:2]
    with p.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        x = float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def load_map(name):
    return {r["ticker"]: r for r in read(SEL / name)}


def main():
    value = load_map("value_top50.csv"); quality = load_map("quality_top50.csv"); garp = load_map("garp_top50.csv")
    fresh = {k: load_map(f"{k}_freshness_adjusted.csv") for k in ("value", "quality", "garp")}
    sec = {}
    for r in read(SEL / "filing_freshness_audit_p617.csv"):
        sec[(r["ranking"], r["ticker"])] = r["audit_status"]
    val = load_map("valuation_integrity_audit.csv")
    trade = {}
    for r in read(SEL / "tradability/value_tradable_candidates.csv"):
        trade["VALUE_V1", r["ticker"]] = r
    for r in read(SEL / "tradability/quality_tradable_candidates.csv"):
        trade["QUALITY_V1", r["ticker"]] = r
    for r in read(SEL / "tradability/garp_tradable_candidates.csv"):
        trade["GARP_V1", r["ticker"]] = r
    all_tickers = sorted(set(value) | set(quality) | set(garp))
    wide = []
    for t in all_tickers:
        v = value.get(t, {}); q = quality.get(t, {}); g = garp.get(t, {})
        def gate(kind, row, score_field, base_status):
            if not row: return "NO_FACTOR", "FACTOR_NOT_PRESENT"
            score = num(row.get(score_field))
            if score is None: return "NO_FACTOR", "SCORE_MISSING"
            if row.get("status_field", base_status) not in (base_status,):
                pass
            fr = fresh[{"VALUE_V1": "value", "QUALITY_V1": "quality", "GARP_V1": "garp"}[kind]].get(t, {})
            fstatus = fr.get("freshness_status", "FUNDAMENTALS_DATA_BLOCKED")
            sstatus = sec.get(({"VALUE_V1": "value", "QUALITY_V1": "quality", "GARP_V1": "garp"}[kind], t), "FILING_DATA_BLOCKED")
            tr = trade.get((kind, t), {})
            raw_status = tr.get("raw_tradability_status", "")
            final_status = tr.get("tradability_status", "DATA_BLOCKED")
            if kind == "VALUE_V1" and val.get(t, {}).get("valuation_status") != "VALUATION_VALID":
                return "BLOCKED", "VALUATION_" + val.get(t, {}).get("valuation_status", "UNKNOWN")
            if fstatus != "FUNDAMENTALS_FRESH": return "BLOCKED", "FRESHNESS_" + fstatus
            if sstatus != "FILING_HISTORY_CONFIRMED": return "BLOCKED", "SEC_" + sstatus
            if final_status == "ELIGIBLE": return "ELIGIBLE", ""
            if final_status == "WATCH": return "WATCH", tr.get("tradability_reason", "")
            if final_status == "DATA_BLOCKED": return "DATA_BLOCKED", tr.get("tradability_reason", "")
            return "BLOCKED", tr.get("tradability_reason", "LIQUIDITY_OR_MARKET_GATE")
        vscore = num(v.get("value_composite_experimental")); qscore = num(q.get("quality_score_recomputed")); gscore = num(g.get("garp_score"))
        v_status, v_reason = gate("VALUE_V1", v, "value_composite_experimental", "VALUE_EXPERIMENTAL_ALL_FOUR")
        q_status, q_reason = gate("QUALITY_V1", q, "quality_score_recomputed", "QUALITY_V1_SCORED")
        g_status, g_reason = gate("GARP_V1", g, "garp_score", "GARP_EXPERIMENTAL_HISTORICAL_GROWTH")
        factors = [x for x in (vscore, qscore, gscore) if x is not None]
        fcount = len(factors)
        bscore = round(sum(factors) / len(factors), 4) if factors else None
        # BLENDED needs at least two independently present factors; no zero fill.
        b_status = "NO_FACTOR" if fcount < 2 else "BLOCKED"
        b_reason = "FACTOR_COUNT_LT_2" if fcount < 2 else ""
        if fcount >= 2:
            b_status = "ELIGIBLE" if all(x == "ELIGIBLE" for x in (v_status, q_status, g_status) if x in ("ELIGIBLE", "WATCH", "BLOCKED")) and any(x == "ELIGIBLE" for x in (v_status, q_status, g_status)) else "WATCH"
            # A blended name must have its available factors serviceable; missing factors are allowed but not zeroed.
            if any(x in ("BLOCKED", "DATA_BLOCKED") for x in (v_status, q_status, g_status) if x not in ("NO_FACTOR",)):
                b_status = "BLOCKED"; b_reason = "AVAILABLE_FACTOR_BLOCKED"
            elif b_status == "ELIGIBLE": b_reason = ""
        wide.append({"ticker": t, "cik": v.get("cik") or q.get("cik") or g.get("cik"),
                     "company_name": v.get("company_name") or q.get("company_name") or g.get("company_name"),
                     "model_family": v.get("model_family") or q.get("model_family") or g.get("model_family"),
                     "value_score": vscore, "quality_score": qscore, "garp_score": gscore,
                     "blended_score": bscore, "factor_count": fcount,
                     "factors_present": "|".join([n for n, x in (("VALUE", vscore), ("QUALITY", qscore), ("GARP", gscore)) if x is not None]),
                     "value_status": v_status, "value_reason": v_reason,
                     "quality_status": q_status, "quality_reason": q_reason,
                     "garp_status": g_status, "garp_reason": g_reason,
                     "blended_status": b_status, "blended_reason": b_reason,
                     "tradability_value": trade.get(("VALUE_V1", t), {}).get("tradability_status", ""),
                     "tradability_quality": trade.get(("QUALITY_V1", t), {}).get("tradability_status", ""),
                     "tradability_garp": trade.get(("GARP_V1", t), {}).get("tradability_status", "")})
    fields = list(wide[0].keys())
    with (OUT / "strategy_scores.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(wide)
    long = []
    for r in wide:
        for sid, sf, st, reason in (("VALUE_V1", "value_score", "value_status", "value_reason"),
                                    ("QUALITY_V1", "quality_score", "quality_status", "quality_reason"),
                                    ("GARP_V1", "garp_score", "garp_status", "garp_reason"),
                                    ("BLENDED_V1", "blended_score", "blended_status", "blended_reason")):
            if r[sf] is None: continue
            if sid == "BLENDED_V1" and r["factor_count"] < 2: continue
            long.append({"strategy": sid, "ticker": r["ticker"], "company_name": r["company_name"],
                         "model_family": r["model_family"], "score": r[sf],
                         "factor_count": r["factor_count"], "factors_present": r["factors_present"],
                         "candidate_status": r[st], "reason": r[reason]})
    long.sort(key=lambda x: (x["strategy"], 0 if x["candidate_status"] == "ELIGIBLE" else 1, -float(x["score"] or 0)))
    with (OUT / "strategy_candidates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(long[0].keys())); w.writeheader(); w.writerows(long)
    counts = {s: dict(Counter(r["candidate_status"] for r in long if r["strategy"] == s)) for s in STRATEGIES}
    status = {"generated_at": datetime.now(timezone.utc).isoformat(), "as_of": "2026-11-05",
              "status": "P7_STRATEGY_RESEARCH", "research_only": True,
              "min_launch_candidates": MIN_LAUNCH,
              "strategy_counts": counts,
              "launchable": {s: counts.get(s, {}).get("ELIGIBLE", 0) >= MIN_LAUNCH for s in STRATEGIES},
              "note": "Missing factors are not zero-filled; BLENDED uses only available factor scores."}
    (OUT / "p7_strategy_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
