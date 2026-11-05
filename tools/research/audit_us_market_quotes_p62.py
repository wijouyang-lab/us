"""P6.2 one-batch AkShare quote coverage audit for the P6.1 universe.

Only current quotes. No historical downloads, fundamentals, or production writes.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

CURRENT = Path("data/universe/us_equities_current.csv")
AUDIT = Path("data/universe/us_equities_universe_audit.json")
OUT_JSON = Path("data/universe/us_market_quote_coverage_p62.json")
OUT_MAP = Path("data/universe/us_market_quote_mapping_p62.csv")
OUT_FAIL = Path("data/universe/us_market_quote_failures_p62.csv")
SAMPLE = ("AAPL", "MSFT", "GOOGL", "NVDA", "CRM", "ADBE", "AMZN", "HD", "MCD", "NKE",
          "CAT", "HON", "UNP", "XOM", "CVX", "NEE", "DUK", "JNJ", "PFE", "UNH",
          "MRNA", "JPM", "BAC", "BRK.B", "MET", "PLD", "O", "RIVN")
COL_CODE = "\u4ee3\u7801"
COL_NAME = "\u540d\u79f0"
COL_PRICE = "\u6700\u65b0\u4ef7"
COL_CAP = "\u603b\u5e02\u503c"
COL_PE = "\u5e02\u76c8\u7387"


def norm(v: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(v or "").upper())


def number(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def build_spot_index(spot: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    for c in (COL_CODE, COL_NAME, COL_PRICE, COL_CAP, COL_PE):
        if c not in spot.columns:
            raise ValueError(f"spot missing column {c!r}")
    out = {}
    for r in spot.to_dict(orient="records"):
        code = str(r.get(COL_CODE) or "").strip()
        if not code:
            continue
        suffix = code.split(".", 1)[1] if "." in code else code
        key = norm(suffix)
        if not key: continue
        out.setdefault(key, []).append({"vendor_symbol": code, "vendor_ticker": suffix,
            "quote_price": number(r.get(COL_PRICE)), "market_cap": number(r.get(COL_CAP)),
            "pe": number(r.get(COL_PE)), "display_name": str(r.get(COL_NAME) or "")})
    return out


def name_similarity(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9]+", str(a).lower()))
    tb = set(re.findall(r"[a-z0-9]+", str(b).lower()))
    if not ta or not tb: return 0.0
    overlap = len(ta & tb)
    return max(overlap / len(ta | tb), overlap / min(len(ta), len(tb)))


def match_one(ticker: str, name: str, exchange: str, index: dict[str, list[dict]]) -> tuple[str, dict | None, list[dict]]:
    candidates = index.get(norm(ticker), [])
    if not candidates: return "QUOTE_NOT_FOUND", None, []
    if len(candidates) == 1:
        c = candidates[0]
        if c["quote_price"] is None or c["quote_price"] <= 0: return "INVALID_QUOTE", c, candidates
        return "QUOTE_MATCHED", c, candidates
    scored = [(name_similarity(name, c["display_name"]), c) for c in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored[0][0] >= 0.80 and (len(scored) == 1 or scored[0][0] > scored[1][0] + 0.05):
        c = scored[0][1]
        return ("QUOTE_MATCHED" if c["quote_price"] and c["quote_price"] > 0 else "INVALID_QUOTE"), c, candidates
    return "AMBIGUOUS_MATCH", None, candidates


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def run(spot: pd.DataFrame | None = None, current_path: Path = CURRENT,
        audit_path: Path = AUDIT, out_json: Path = OUT_JSON,
        out_map: Path = OUT_MAP, out_fail: Path = OUT_FAIL,
        source_error: str | None = None) -> dict:
    with current_path.open(encoding="utf-8") as f:
        universe = list(csv.DictReader(f))
    target = [r for r in universe if r["security_type"] in ("COMMON", "ADR")]
    unclassified = [r for r in universe if r["security_type"] == "UNCLASSIFIED"]
    if spot is None:
        index = {}
    else:
        index = build_spot_index(spot)
    rows = []
    for r in target + unclassified:
        cohort = "TARGET" if r["security_type"] in ("COMMON", "ADR") else "UNCLASSIFIED"
        if source_error:
            status, chosen, cands = "SOURCE_ERROR", None, []
        else:
            status, chosen, cands = match_one(r["ticker"], r["security_name"], r["exchange"], index)
        row = {"ticker": r["ticker"], "security_name": r["security_name"], "exchange": r["exchange"],
               "security_type": r["security_type"], "cohort": cohort, "match_status": status,
               "vendor_symbol": chosen["vendor_symbol"] if chosen else "",
               "vendor_ticker": chosen["vendor_ticker"] if chosen else "",
               "quote_price": chosen["quote_price"] if chosen else "",
               "market_cap_raw": chosen["market_cap"] if chosen else "",
               "pe_raw": chosen["pe"] if chosen else "",
               "candidate_count": len(cands),
               "candidate_symbols": "|".join(c["vendor_symbol"] for c in cands),
               "source_error": source_error or ""}
        rows.append(row)
    trows = [x for x in rows if x["cohort"] == "TARGET"]
    urows = [x for x in rows if x["cohort"] == "UNCLASSIFIED"]
    def count(rs, status): return sum(1 for x in rs if x["match_status"] == status)
    matched = count(trows, "QUOTE_MATCHED")
    # coverage among all target rows
    total = len(trows)
    price_ok = sum(1 for x in trows if x["quote_price"] not in ("", None))
    cap_ok = sum(1 for x in trows if x["market_cap_raw"] not in ("", None))
    pe_ok = sum(1 for x in trows if x["pe_raw"] not in ("", None))
    by_type = {}
    for typ in ("COMMON", "ADR"):
        rs = [x for x in trows if x["security_type"] == typ]
        by_type[typ] = {"total": len(rs), "matched": count(rs, "QUOTE_MATCHED"),
                        "coverage": round(count(rs, "QUOTE_MATCHED") / len(rs), 6) if rs else None}
    by_exchange = {}
    for ex in sorted({x["exchange"] for x in trows}):
        rs = [x for x in trows if x["exchange"] == ex]
        by_exchange[ex] = {"total": len(rs), "matched": count(rs, "QUOTE_MATCHED"),
                           "coverage": round(count(rs, "QUOTE_MATCHED") / len(rs), 6)}
    sample = []
    for t in SAMPLE:
        x = next((r for r in rows if r["ticker"] == t), None)
        sample.append({"ticker": t, "status": x["match_status"] if x else "NOT_IN_CURRENT",
                       "quote_price": x["quote_price"] if x else None})
    u_matched = count(urows, "QUOTE_MATCHED")
    report = {"metadata": {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "AkShare stock_us_spot_em",
        "source_error": source_error,
        "spot_delay_minutes": 15,
        "scope": "CURRENT_LISTED_COMMON_AND_ADR",
        "target_denominator": total,
        "note": "15-minute delayed snapshot, not real-time; no per-symbol fallback attempted.",
        "akshare_version": __import__("importlib.metadata", fromlist=["version"]).version("akshare")
            if not source_error else None,
    }, "summary": {
        "raw_spot_records": len(spot) if spot is not None else 0,
        "target_total": total, "target_common": by_type["COMMON"]["total"],
        "target_adr": by_type["ADR"]["total"],
        "matched": matched, "not_found": count(trows, "QUOTE_NOT_FOUND"),
        "ambiguous": count(trows, "AMBIGUOUS_MATCH"),
        "invalid_quote": count(trows, "INVALID_QUOTE"),
        "source_error": count(trows, "SOURCE_ERROR"),
        "quote_coverage": round(matched / total, 6) if total else 0,
        "price_field_coverage": round(price_ok / total, 6) if total else 0,
        "market_cap_field_coverage": round(cap_ok / total, 6) if total else 0,
        "pe_field_coverage": round(pe_ok / total, 6) if total else 0,
        "unclassified_total": len(urows), "unclassified_matched": u_matched,
        "unclassified_not_found": count(urows, "QUOTE_NOT_FOUND"),
        "unclassified_ambiguous": count(urows, "AMBIGUOUS_MATCH"),
        "sample_28_matched": sum(1 for x in sample if x["status"] == "QUOTE_MATCHED"),
    }, "by_type": by_type, "by_exchange": by_exchange,
       "sample_28": sample,
       "unclassified": {"total": len(urows), "matched": u_matched,
                        "status_counts": dict(Counter(x["match_status"] for x in urows))},
       "mapping_note": "mapping CSV includes target and unclassified cohorts; denominator excludes UNCLASSIFIED"}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    fields = ["ticker", "security_name", "exchange", "security_type", "cohort", "match_status",
              "vendor_symbol", "vendor_ticker", "quote_price", "market_cap_raw", "pe_raw",
              "candidate_count", "candidate_symbols", "source_error"]
    write_csv(out_map, rows, fields)
    fail_fields = fields
    write_csv(out_fail, [x for x in rows if x["match_status"] != "QUOTE_MATCHED"], fail_fields)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-json", type=Path, default=OUT_JSON)
    ap.add_argument("--out-map", type=Path, default=OUT_MAP)
    ap.add_argument("--out-fail", type=Path, default=OUT_FAIL)
    args = ap.parse_args()
    import akshare as ak
    try:
        spot = ak.stock_us_spot_em()
    except Exception as exc:
        report = run(None, source_error=f"{type(exc).__name__}: {str(exc)[:500]}",
                     out_json=args.out_json, out_map=args.out_map, out_fail=args.out_fail)
        print(json.dumps(report["summary"], indent=2))
        return 1
    report = run(spot, out_json=args.out_json, out_map=args.out_map, out_fail=args.out_fail)
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
