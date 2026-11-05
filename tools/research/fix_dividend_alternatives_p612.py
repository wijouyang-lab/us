"""P6.12 correction: verify Yahoo split adjustment and Nasdaq identity."""
import csv, json, tempfile
from datetime import date
from pathlib import Path
import yfinance as yf

OUT = Path("data/universe/dividend_alternative_source_results_p612.json")
COMP = Path("data/universe/dividend_source_comparison_p612.csv")
CURRENT = Path("data/universe/us_equities_current.csv")
SAMPLE = Path("data/universe/us_dividend_source_sample_p611.json")


def main():
    d = json.loads(OUT.read_text(encoding="utf-8"))
    cur = {r["ticker"]: r for r in csv.DictReader(CURRENT.open(encoding="utf-8"))}
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))["sample"]
    yf.set_tz_cache_location(tempfile.mkdtemp(prefix="yf-splits-"))
    split_info = {}
    for s in sample:
        t = s["ticker"]
        try:
            sp = yf.Ticker(t).splits
            rows = [{"date": str(i)[:10], "factor": float(v)} for i, v in sp.items()]
        except Exception as e:
            rows = []
        split_info[t] = rows
        yres = d["results"].setdefault(t, {}).setdefault("YAHOO_FINANCE", {})
        yres["splits"] = rows
        events = yres.get("events") or []
        status = "SPLIT_ADJUSTMENT_UNVERIFIED"
        details = []
        for sp in rows:
            sd = date.fromisoformat(sp["date"])
            before = [e for e in events if e.get("ex_dividend_date") and e["ex_dividend_date"] < sp["date"]]
            after = [e for e in events if e.get("ex_dividend_date") and e["ex_dividend_date"] > sp["date"]]
            if before and after:
                pre = float(before[-1]["dps"]); post = float(after[0]["dps"])
                if pre and post:
                    ratio = pre / post
                    # adjusted series should be near 1; unadjusted should be near split factor
                    ok = abs(ratio - 1) < abs(ratio - sp["factor"]) and abs(ratio - 1) < 0.40
                    details.append({"split_date": sp["date"], "factor": sp["factor"],
                                    "pre_dps": pre, "post_dps": post, "pre_post_ratio": ratio,
                                    "closer_to_adjusted": ok})
                    if ok: status = "SPLIT_ADJUSTMENT_OBSERVED_ADJUSTED"
        yres["split_adjustment_status"] = status
        yres["split_adjustment_details"] = details
        if not rows: yres["split_adjustment_status"] = "NO_SPLIT_IN_HISTORY"
    # Nasdaq identity: exact ticker/current security identity; no preferred mix
    comp = list(csv.DictReader(COMP.open(encoding="utf-8")))
    nas = [r for r in comp if r["source"] == "NASDAQ_DIVIDEND_HISTORY"]
    if not nas:
        for t, r in d["results"].items():
            n = r.get("NASDAQ_DIVIDEND_HISTORY")
            if not n: continue
            ev = n.get("events") or []
            nas.append({"ticker": t, "source": "NASDAQ_DIVIDEND_HISTORY", "http_status": n.get("status"),
                "success": bool(ev), "has_events": bool(ev), "event_count": len(ev),
                "dps_count": sum(1 for x in ev if x.get("dps") != ""),
                "ex_date_count": sum(1 for x in ev if x.get("ex_dividend_date")),
                "payment_date_count": sum(1 for x in ev if x.get("payment_date")),
                "declaration_date_count": sum(1 for x in ev if x.get("announcement_date")),
                "record_date_count": sum(1 for x in ev if x.get("record_date")),
                "currency_count": sum(1 for x in ev if x.get("currency")),
                "match_status": "UNVERIFIED", "source_url": n.get("url"), "as_of": n.get("as_of"),
                "raw_sha256": n.get("raw_sha256"), "error": n.get("error"), "sec_cash_paid": ""})
        comp.extend(nas)
    identity_counts = {"MATCHED": 0, "UNVERIFIED": 0}
    for r in nas:
        u = cur.get(r["ticker"])
        ok = bool(u and u.get("security_type") in ("COMMON", "ADR"))
        r["match_status"] = "MATCHED" if ok else "UNVERIFIED"
        r["identity_status"] = "MATCHED" if ok else "UNVERIFIED"
        r["security_type_verified"] = u.get("security_type", "") if u else ""
        r["issuer_cik"] = u.get("CIK", "") if u else ""
        identity_counts[r["identity_status"]] += 1
    fields = list(dict.fromkeys(list(comp[0].keys()) + ["identity_status", "security_type_verified", "issuer_cik"]))
    with COMP.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(comp)
    # Smarter current profile vs recent event
    sm = d["source_capability"]["SMARTERDIVIDENDS"]
    profiles = 0; recents = 0
    for t, r in d["results"].items():
        s = r.get("SMARTERDIVIDENDS", {})
        if s.get("profile", {}).get("annual_amount") is not None: profiles += 1
        if s.get("events"): recents += 1
    sm["current_profile_count"] = profiles
    sm["recent_event_count"] = recents
    d["corrections_p612"] = {
        "yahoo_split_validation": {"status_counts": {},
            "tickers_with_splits": sum(1 for v in split_info.values() if v),
            "method": "pre/post split DPS ratio compared with split factor; unadjusted if closer to factor"},
        "nasdaq_identity": {"attempted": len(nas), "counts": identity_counts},
        "smarter_current_profile_count": profiles, "smarter_recent_event_count": recents}
    from collections import Counter
    d["corrections_p612"]["yahoo_split_validation"]["status_counts"] = dict(Counter(
        r.get("YAHOO_FINANCE", {}).get("split_adjustment_status", "UNKNOWN") for r in d["results"].values()))
    OUT.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(d["corrections_p612"], indent=2))


if __name__ == "__main__":
    main()
