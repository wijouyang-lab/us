"""Build a current US-listed common-equity/ADR universe registry (P6.1).

Sources:
- Nasdaq Trader nasdaqlisted.txt + otherlisted.txt
- SEC company_tickers_exchange.json (cross mapping only)

Current listing status only. This is not a historical point-in-time universe.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SAMPLE = ["AAPL", "MSFT", "GOOGL", "NVDA", "CRM", "ADBE", "AMZN", "HD", "MCD", "NKE",
          "CAT", "HON", "UNP", "XOM", "CVX", "NEE", "DUK", "JNJ", "PFE", "UNH",
          "MRNA", "JPM", "BAC", "BRK.B", "MET", "PLD", "O", "RIVN"]
OUT_DIR = Path("data/universe")
SOURCE_DIR = OUT_DIR / "source"

EXCHANGE = {"N": "NYSE", "A": "NYSE American", "P": "NYSE Arca", "Z": "Cboe BZX",
            "V": "IEX", "Q": "NASDAQ", "G": "NASDAQ", "S": "NASDAQ"}
SEC_EXCHANGE = {"Nasdaq": "NASDAQ", "NYSE": "NYSE", "NYSE American": "NYSE American",
                "NYSE Arca": "NYSE Arca", "Cboe BZX": "Cboe BZX", "IEX": "IEX"}


def norm_ticker(v: str) -> str:
    return str(v or "").strip().upper().replace("-", ".")


def decode_timestamp(raw: str) -> dict:
    m = re.search(r"(\d{2})(\d{2})(\d{4})(\d{2}):(\d{2})", raw or "")
    if not m: return {"raw": raw, "parsed": None, "timezone": "unknown"}
    mm, dd, yyyy, hh, mi = m.groups()
    return {"raw": raw, "parsed": f"{yyyy}-{mm}-{dd}T{hh}:{mi}", "timezone": "unknown (vendor footer)"}


def source_timestamp(path: Path) -> dict:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("File Creation Time:"):
                return decode_timestamp(line.strip())
    return {"raw": None, "parsed": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            "timezone": "UTC file mtime"}


def classify(name: str, etf: str, test: str, nextshares: str = "") -> tuple[str, str | None]:
    low = re.sub(r"\s+", " ", (name or "").lower())
    if str(test).strip().upper() == "Y": return "EXCLUDED", "TEST_ISSUE"
    if str(etf).strip().upper() == "Y" or str(nextshares).strip().upper() == "Y":
        return "EXCLUDED", "ETF_OR_NEXTSHARES"
    excluded = (
        ("warrant", "WARRANT"), (" right", "RIGHT"), ("rights", "RIGHT"),
        (" unit", "UNIT"), ("units", "UNIT"), ("preferred", "PREFERRED"),
        ("preference shares", "PREFERRED"),
        ("note", "NOTE"), ("bond", "BOND"), ("debenture", "DEBENTURE"),
        ("fund", "FUND"), ("etn", "ETN"), ("exchange traded", "ETF"),
        ("subscription", "SUBSCRIPTION"), ("test issue", "TEST_ISSUE"),
    )
    for token, reason in excluded:
        if token in low: return "EXCLUDED", reason
    if "depositary shares" in low and "american depositary" not in low:
        return "EXCLUDED", "DEPOSITARY_SHARES"
    if (any(x in low for x in ("american depositary", "american depository", "new york registry",
                               "new york shares"))
            or re.search(r"\bads\b|\badss\b", low)):
        return "ADR", None
    if any(x in low for x in ("common stock", "common share", "ordinary share", "ordinary shares",
                              "subordinate voting", "common subordinate", "class a", "class b",
                              "class c", "capital stock", "shares of beneficial interest",
                              "beneficial interest", "ord shares", "registered shares")):
        return "COMMON", None
    return "UNCLASSIFIED", None


def read_pipe(path: Path, source: str) -> tuple[list[dict], int, dict]:
    ts = source_timestamp(path)
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n\r")
            if not line or line.startswith("File Creation Time:"): continue
            parts = line.split("|")
            if source == "nasdaqlisted":
                if parts[0] == "Symbol": continue
                if len(parts) < 8: continue
                ticker, name, category, test, status, lot, etf, nexts = parts[:8]
                exchange = EXCHANGE.get(category.strip().upper(), f"NASDAQ:{category}")
            else:
                if parts[0] == "ACT Symbol": continue
                if len(parts) < 8: continue
                ticker, name, ex, cqs, etf, lot, test, nsym = parts[:8]
                exchange = EXCHANGE.get(ex.strip().upper(), f"OTHER:{ex}")
                nexts = ""
            if not ticker.strip(): continue
            rows.append({"ticker": ticker.strip(), "security_name": name.strip(), "exchange": exchange,
                         "etf": etf, "test": test, "nextshares": nexts,
                         "source": source, "source_timestamp": ts})
    return rows, len(rows), ts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    ap.add_argument("--sec", type=Path, default=SOURCE_DIR / "company_tickers_exchange.json")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    nas = args.source_dir / "nasdaqlisted.txt"; oth = args.source_dir / "otherlisted.txt"
    if not nas.exists() or not oth.exists() or not args.sec.exists():
        print("missing source files; expected nasdaqlisted.txt, otherlisted.txt, company_tickers_exchange.json")
        return 2
    nrows, nraw, nts = read_pipe(nas, "nasdaqlisted")
    orows, oraw, ots = read_pipe(oth, "otherlisted")
    raw = nrows + orows
    sec = json.loads(args.sec.read_text(encoding="utf-8"))
    by_ticker: dict[str, list[dict]] = {}
    for cik, name, ticker, exchange in sec["data"]:
        by_ticker.setdefault(norm_ticker(ticker), []).append(
            {"cik": str(cik).zfill(10), "name": name, "exchange": exchange})

    current: list[dict] = []; excluded: list[dict] = []
    seen = set(); duplicates = 0
    for r in raw:
        key = (r["ticker"].upper(), r["exchange"], r["security_name"])
        if key in seen:
            duplicates += 1; continue
        seen.add(key)
        sec_rows = by_ticker.get(norm_ticker(r["ticker"]), [])
        ciks = {x["cik"] for x in sec_rows}
        if len(ciks) == 1:
            match = "MATCHED"; srow = sec_rows[0]
        elif len(ciks) > 1:
            match = "AMBIGUOUS"; srow = sec_rows[0]
        else:
            match = "UNMATCHED"; srow = None
        sec_ex = SEC_EXCHANGE.get(srow["exchange"], srow["exchange"]) if srow else None
        typ, reason = classify(r["security_name"], r["etf"], r["test"], r["nextshares"])
        note = "WHEN_ISSUED" if "when-issued" in r["security_name"].lower() else ""
        base = {"ticker": r["ticker"], "security_name": r["security_name"], "exchange": r["exchange"],
                "security_type": typ, "CIK": srow["cik"] if srow else "",
                "SEC_name": srow["name"] if srow else "", "listing_status": "CURRENT",
                "source": r["source"], "source_timestamp": json.dumps(r["source_timestamp"], ensure_ascii=False),
                "match_status": match, "sec_exchange": sec_ex or "",
                "exchange_match": bool(sec_ex and sec_ex == r["exchange"]), "listing_note": note,
                "universe_status": "INCLUDED" if typ in ("COMMON", "ADR", "UNCLASSIFIED") else "EXCLUDED"}
        if typ == "EXCLUDED":
            base["exclusion_reason"] = reason or "UNKNOWN"
            excluded.append(base)
        else:
            current.append(base)

    # Audit duplicate ticker groups without merging them.
    tickers = {}
    for r in current + excluded:
        tickers.setdefault(norm_ticker(r["ticker"]), []).append(r)
    duplicate_tickers = {k: len(v) for k, v in tickers.items() if len(v) > 1}
    multi_name = {k: len({x["security_name"] for x in v}) for k, v in tickers.items()
                  if len({x["security_name"] for x in v}) > 1}
    sp = []
    sp_path = Path("sp500_constituents.csv")
    if sp_path.exists():
        with sp_path.open(encoding="utf-8") as f:
            sp = [r["Ticker"].strip() for r in csv.DictReader(f) if r.get("Ticker")]
    sp_set = {norm_ticker(x) for x in sp}
    current_set = {norm_ticker(x["ticker"]) for x in current}
    sample_missing = [t for t in SAMPLE if norm_ticker(t) not in current_set]
    sp_missing = sorted(x for x in sp_set if x not in current_set)

    counts = {
        "raw_records": len(raw), "raw_nasdaqlisted": nraw, "raw_otherlisted": oraw,
        "deduplicated_records": len(current) + len(excluded), "duplicate_exact_records": duplicates,
        "current_records": len(current), "common": sum(1 for x in current if x["security_type"] == "COMMON"),
        "adr": sum(1 for x in current if x["security_type"] == "ADR"),
        "unclassified": sum(1 for x in current if x["security_type"] == "UNCLASSIFIED"),
        "excluded": len(excluded),
        "sec_matched": sum(1 for x in current + excluded if x["match_status"] == "MATCHED"),
        "sec_unmatched": sum(1 for x in current + excluded if x["match_status"] == "UNMATCHED"),
        "sec_ambiguous": sum(1 for x in current + excluded if x["match_status"] == "AMBIGUOUS"),
        "sec_matched_current": sum(1 for x in current if x["match_status"] == "MATCHED"),
        "sec_unmatched_current": sum(1 for x in current if x["match_status"] == "UNMATCHED"),
        "sec_ambiguous_current": sum(1 for x in current if x["match_status"] == "AMBIGUOUS"),
        "duplicate_ticker_groups": len(duplicate_tickers),
        "same_ticker_distinct_names": len(multi_name),
        "when_issued_included": sum(1 for x in current if x.get("listing_note") == "WHEN_ISSUED"),
        "multi_class_named_records": sum(1 for x in current if re.search(r"class\s+[abc]\b", x["security_name"], re.I)),
        "sp500_total": len(sp_set), "sp500_matched": len(sp_set & current_set),
        "sp500_missing": len(sp_missing), "sample_28_total": len(SAMPLE),
        "sample_28_missing": len(sample_missing),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    fields = ["ticker", "security_name", "exchange", "security_type", "CIK", "SEC_name",
              "listing_status", "source", "source_timestamp", "match_status",
              "sec_exchange", "exchange_match", "universe_status", "listing_note"]
    with (args.out_dir / "us_equities_current.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(current)
    xfields = fields + ["exclusion_reason"]
    with (args.out_dir / "us_equities_excluded.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=xfields); w.writeheader(); w.writerows(excluded)
    audit = {
        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
                     "scope": "CURRENT_LISTED_COMMON_EQUITY_AND_ADR",
                     "not_scope": "HISTORICAL_PIT_UNIVERSE; OTC/OTHER_UNVERIFIED_MARKETS",
                     "sources": {
                         "nasdaqlisted": {"url": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", "timestamp": nts},
                         "otherlisted": {"url": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", "timestamp": ots},
                         "sec": {"url": "https://www.sec.gov/files/company_tickers_exchange.json",
                                 "mtime_utc": datetime.fromtimestamp(args.sec.stat().st_mtime, timezone.utc).isoformat()}},
                     "exchange_scope": ["NASDAQ", "NYSE", "NYSE American", "NYSE Arca", "Cboe BZX", "IEX"]},
        "counts": counts,
        "coverage": {"sample_28_missing": sample_missing, "sp500_missing": sp_missing[:100],
                     "sp500_missing_count": len(sp_missing)},
        "duplicate_tickers": dict(sorted(duplicate_tickers.items(), key=lambda kv: (-kv[1], kv[0]))[:100]),
        "same_ticker_distinct_name_count": len(multi_name),
        "multi_class_examples": [
            [{"ticker": x["ticker"], "name": x["SEC_name"]} for x in current
             if re.search(r"class\s+[abc]\b", x["security_name"], re.I)
             and x["ticker"] in ("GOOG", "GOOGL", "FOX", "FOXA", "NWS", "NWSA", "BRK.A", "BRK.B")][:12]
        ],
        "unclassified_records": [{"ticker": x["ticker"], "security_name": x["security_name"],
                                  "exchange": x["exchange"]} for x in current if x["security_type"] == "UNCLASSIFIED"][:100],
        "exclusion_reasons": {k: sum(1 for x in excluded if x["exclusion_reason"] == k)
                              for k in sorted({x["exclusion_reason"] for x in excluded})},
    }
    (args.out_dir / "us_equities_universe_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(counts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
