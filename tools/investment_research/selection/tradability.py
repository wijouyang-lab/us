"""P6.15 tradability screen layered on top of fundamental rankings.

The screen never changes a fundamental score. ADV20/ADV60 are unavailable in
the verified P6.2 batch mapping, so liquidity remains DATA_BLOCKED; no candidate
is promoted to ELIGIBLE merely because price/market cap look acceptable.
"""
from __future__ import annotations
import argparse, csv, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("data/universe/selection")
INPUTS = Path("data/universe/selection_inputs")
QUOTES = INPUTS / "us_market_quote_mapping_p62.csv"
CURRENT = INPUTS / "us_equities_current.csv"
CLASS = INPUTS / "issuer_classification_p615.csv"
LIQUIDITY = INPUTS / "liquidity_ohlcv_p616.csv"
FRESHNESS = {k: ROOT / f"{k}_freshness_adjusted.csv" for k in ("value", "quality", "garp")}
VALUATION = ROOT / "valuation_integrity_audit.csv"
OUT = ROOT / "tradability"
PRICE_ASOF = "2026-11-05T08:16:00Z"
SCENARIOS = {
    "conservative": {"min_price": 5.0, "min_mcap": 2_000_000_000, "min_adv": 5_000_000},
    "balanced": {"min_price": 3.0, "min_mcap": 500_000_000, "min_adv": 2_000_000},
    "aggressive": {"min_price": 1.0, "min_mcap": 50_000_000, "min_adv": 500_000},
}


def read(path):
    b = path.read_bytes()[:2]
    with path.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        x = float(v)
        return x if x > 0 else None
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    quotes = {r["ticker"]: r for r in read(QUOTES)}
    current = {r["ticker"]: r for r in read(CURRENT)}
    cls = {r["ticker"]: r for r in read(CLASS)}
    liq = {r["ticker"]: r for r in read(LIQUIDITY)} if LIQUIDITY.exists() else {}
    fresh_maps = {k: {r["ticker"]: r for r in read(v)} for k, v in FRESHNESS.items() if v.exists()}
    valuation = {r["ticker"]: r for r in read(VALUATION)} if VALUATION.exists() else {}
    a.out.mkdir(parents=True, exist_ok=True)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "price_asof": PRICE_ASOF,
               "price_source": "P6_2_AKSHARE_BATCH_15MIN_DELAY",
               "liquidity_source": "YFINANCE_1D_UNADJUSTED_CLOSE_RAW_VOLUME",
               "scenarios": SCENARIOS, "research_only": True,
               "note": "ADV from yfinance current 20/60 completed sessions; ELIGIBLE is a research screen, not trading approval."}
    for kind, file, topfile in (("value", "value_rankings.csv", "value_top50.csv"),
                                ("quality", "quality_rankings.csv", "quality_top50.csv"),
                                ("garp", "garp_rankings.csv", "garp_top50.csv")):
        rows = read(ROOT / topfile)
        base = {r["ticker"] for r in rows}
        out_rows = []
        for r in rows:
            t = r["ticker"]; q = quotes.get(t, {}); c = current.get(t, {}); cl = cls.get(t, {})
            price = num(q.get("quote_price")); mcap = num(q.get("market_cap_raw")) or num(r.get("market_cap"))
            sec_type = r.get("security_type") or q.get("security_type") or c.get("security_type") or "UNKNOWN"
            active = (c.get("listing_status") == "CURRENT") if c else False
            special = cl.get("model_family") in ("BANKS", "INSURANCE", "REIT", "BDC", "OTHER_FINANCIALS", "UTILITIES", "ENERGY")
            reasons = []
            if sec_type not in ("COMMON", "ADR"): reasons.append("SECURITY_TYPE_NOT_COMMON_OR_ADR")
            if not active: reasons.append("NOT_ACTIVE_LISTING")
            if q.get("match_status") != "QUOTE_MATCHED": reasons.append("QUOTE_NOT_MATCHED")
            if price is None: reasons.append("PRICE_INVALID_OR_MISSING")
            if mcap is None: reasons.append("MARKET_CAP_MISSING")
            if special: reasons.append("SPECIAL_MODEL_REVIEW")
            lr = liq.get(t, {})
            adv20 = num(lr.get("adv20_usd")); adv60 = num(lr.get("adv60_usd"))
            if adv20 is None and adv60 is None: reasons.append("ADV20_60_UNAVAILABLE")
            statuses = {}
            for name, s in SCENARIOS.items():
                rs = list(reasons)
                if price is not None and price < s["min_price"]: rs.append("PRICE_BELOW_" + name.upper())
                if mcap is not None and mcap < s["min_mcap"]: rs.append("MCAP_BELOW_" + name.upper())
                if adv20 is None or adv60 is None:
                    rs.append("ADV20_60_UNAVAILABLE")
                else:
                    if adv20 < s["min_adv"]: rs.append("ADV20_BELOW_" + name.upper())
                    if adv60 < s["min_adv"]: rs.append("ADV60_BELOW_" + name.upper())
                hard_block = any(x.startswith(("SECURITY_TYPE_", "NOT_ACTIVE")) for x in rs)
                missing_data = any(x in ("QUOTE_NOT_MATCHED", "PRICE_INVALID_OR_MISSING", "MARKET_CAP_MISSING", "ADV20_60_UNAVAILABLE") for x in rs)
                below = any(x.startswith(("PRICE_BELOW", "MCAP_BELOW", "ADV20_BELOW", "ADV60_BELOW")) for x in rs)
                status = "DATA_BLOCKED" if missing_data else ("BLOCKED" if hard_block or below else ("WATCH" if rs else "ELIGIBLE"))
                statuses[name] = status
            fresh = fresh_maps.get(kind, {}).get(t, {})
            fstatus = fresh.get("freshness_status", "FUNDAMENTALS_DATA_BLOCKED")
            vstatus = valuation.get(t, {}).get("valuation_status", "VALUATION_NOT_APPLICABLE") if kind == "value" else "VALUATION_NOT_APPLICABLE"
            reason = "|".join(dict.fromkeys(reasons))
            if fstatus != "FUNDAMENTALS_FRESH": reason = "|".join([reason, "FRESHNESS_" + fstatus]).strip("|")
            if kind == "value" and vstatus != "VALUATION_VALID": reason = "|".join([reason, "VALUATION_" + vstatus]).strip("|")
            base_status = statuses["balanced"]
            final_status = ("ELIGIBLE" if base_status == "ELIGIBLE" and fstatus == "FUNDAMENTALS_FRESH"
                            and (kind != "value" or vstatus == "VALUATION_VALID") else
                            "DATA_BLOCKED" if fstatus in ("FUNDAMENTALS_DATA_BLOCKED", "FUNDAMENTALS_UPDATE_MISSING")
                            else "WATCH" if base_status in ("ELIGIBLE", "WATCH") else "BLOCKED")
            out_rows.append({**r, "tradability_status": final_status, "tradability_reason": reason,
                             "raw_tradability_status": base_status, "freshness_status": fstatus,
                             "valuation_status": vstatus,
                             "price_source": "P6_2_AKSHARE_BATCH_15MIN_DELAY", "price_asof": PRICE_ASOF,
                             "market_cap": mcap if mcap is not None else "",
                             "adv20_usd": adv20 if adv20 is not None else "",
                             "adv60_usd": adv60 if adv60 is not None else "",
                             "volume_source": lr.get("volume_source", ""),
                             "last_completed_session": lr.get("last_completed_session", ""),
                             "valid_sessions_20": lr.get("valid_sessions_20", 0),
                             "valid_sessions_60": lr.get("valid_sessions_60", 0),
                             "liquidity_status": lr.get("liquidity_status", "DATA_BLOCKED"),
                             "liquidity_data_quality": lr.get("liquidity_data_quality", "MISSING"),
                             "security_type": sec_type, "exchange": q.get("exchange") or c.get("exchange") or "",
                             "is_active": active, "liquidity_coverage": "OK" if adv20 is not None and adv60 is not None else "DATA_BLOCKED",
                             "special_model": special,
                             "tradability_conservative": statuses["conservative"],
                             "tradability_balanced": statuses["balanced"],
                             "tradability_aggressive": statuses["aggressive"]})
        # write all top50 with status; separate filtered WATCH/ELIGIBLE file
        fields = list(out_rows[0].keys()) if out_rows else []
        with (a.out / f"{kind}_tradable_candidates.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(out_rows)
        passing = [r for r in out_rows if r["tradability_status"] in ("ELIGIBLE", "WATCH")]
        with (a.out / f"{kind}_watchlist.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(passing)
        summary[kind] = {"base_top50": len(base), "tradable_rows": len(out_rows),
                         "raw_eligible": sum(1 for r in out_rows if r["raw_tradability_status"] == "ELIGIBLE"),
                         "eligible": sum(1 for r in out_rows if r["tradability_status"] == "ELIGIBLE"),
                         "watch": sum(1 for r in out_rows if r["tradability_status"] == "WATCH"),
                         "blocked": sum(1 for r in out_rows if r["tradability_status"] == "BLOCKED"),
                         "data_blocked": sum(1 for r in out_rows if r["tradability_status"] == "DATA_BLOCKED"),
                         "scenario_counts": {s: dict(Counter(r["tradability_" + s] for r in out_rows)) for s in SCENARIOS},
                         "final_scenario_counts": {s: dict(Counter(
                             ("ELIGIBLE" if r["tradability_" + s] == "ELIGIBLE" and r["freshness_status"] == "FUNDAMENTALS_FRESH"
                              and (kind != "value" or r["valuation_status"] == "VALUATION_VALID") else
                              "WATCH" if r["tradability_" + s] in ("ELIGIBLE", "WATCH") else "BLOCKED")
                             for r in out_rows)) for s in SCENARIOS},
                         "top50_overlap_with_eligible": sum(1 for r in out_rows if r["tradability_status"] == "ELIGIBLE"),
                         "liquidity_coverage": "OK" if all(r["adv20_usd"] != "" for r in out_rows) else "PARTIAL"}
    (a.out / "tradability_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
