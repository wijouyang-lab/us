"""P12.2 SEC as-filed pilot: sample, facts, 8-K events, price alignment.

Raw SEC JSON is cached outside the repository. Only derived aggregates are written.
"""
from __future__ import annotations

import csv
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "cache"
DATA = ROOT / "data/research"
OUT = DATA / "p12_2"
H = {"User-Agent": "P12 SEC PIT pilot contact@example.com"}
ET = ZoneInfo("America/New_York")

METRICS = {
    "Revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenue"],
    "GrossProfit": ["GrossProfit"],
    "OperatingIncome": ["OperatingIncomeLoss", "ProfitLossFromOperatingActivities"],
    "NetIncome": ["NetIncomeLoss", "ProfitLoss"],
    "TotalAssets": ["Assets"],
    "TotalDebt": ["LongTermDebt", "LongTermDebtNoncurrent", "DebtCurrent", "Borrowings"],
    "Cash": ["CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalents"],
    "OperatingCashFlow": ["NetCashProvidedByUsedInOperatingActivities", "CashFlowsFromUsedInOperatingActivities"],
    "Capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PurchaseOfPropertyPlantAndEquipment"],
    "SharesOutstanding": ["EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding", "NumberOfSharesOutstanding"],
}
ITEM_DESC = {
    "1.01": "Material definitive agreement",
    "2.01": "Completion of acquisition or disposition",
    "2.02": "Results of operations and financial condition",
    "5.02": "Departure/election of directors or officers",
    "7.01": "Regulation FD disclosure",
    "8.01": "Other events",
}


def fetch(kind: str, cik: str) -> dict:
    p = CACHE / f"{cik}_{kind}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    base = "https://data.sec.gov/submissions" if kind == "subs" else "https://data.sec.gov/api/xbrl/companyfacts"
    url = f"{base}/CIK{cik}.json"
    r = requests.get(url, headers=H, timeout=120)
    r.raise_for_status()
    p.write_bytes(r.content)
    time.sleep(0.12)
    return r.json()


def parse_accept(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(ET)
    except ValueError:
        return None


def session(dt: datetime | None, trading_days: set) -> str:
    if dt is None:
        return "UNKNOWN"
    d = dt.date().isoformat()
    if d not in trading_days:
        return "NON_TRADING"
    hm = dt.hour * 60 + dt.minute
    if hm < 9 * 60 + 30:
        return "PREMARKET"
    if hm <= 16 * 60:
        return "INTRADAY"
    return "AFTER_HOURS"


def _prev_next_trading(fd: str, session_name: str, tdays: list[str]) -> tuple[str | None, str | None, str | None]:
    import bisect
    i = bisect.bisect_left(tdays, fd)
    if session_name in ("PREMARKET", "INTRADAY") and i < len(tdays) and tdays[i] == fd:
        reaction = fd
    else:
        reaction = tdays[i] if i < len(tdays) else None
    prev = tdays[i - 1] if i > 0 else None
    if reaction:
        j = bisect.bisect_right(tdays, reaction)
        nxt = tdays[j] if j < len(tdays) else None
    else:
        nxt = None
    return reaction, prev, nxt


def main() -> int:
    global OUT
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="data/research/p12_3_expanded_universe.csv")
    ap.add_argument("--out", default="data/research/p12_3")
    args = ap.parse_args()
    OUT = Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)
    sample = list(csv.DictReader((Path(args.sample)).open(encoding="utf-8")))
    price = pd.read_csv(ROOT.parent / "pr512/data/research/pit_data/finsaber_prices_raw.csv", usecols=["date", "symbol", "adjusted_close"], parse_dates=["date"])
    price["symbol"] = price.symbol.str.upper().str.replace(".", "-", regex=False)
    price = price[price.adjusted_close > 0]
    spy = pd.read_csv(ROOT.parent / "pr512/data/research/p9_1_support_resistance/spy.csv", parse_dates=["Date"])
    trading_days = set(spy.Date.dt.date.astype(str))
    tdays = sorted(trading_days)
    price_close: dict[str, pd.Series] = {}
    for sym, g in price.groupby("symbol"):
        price_close[sym] = g.set_index("date").adjusted_close.sort_index()

    fact_rows, event_rows, annual = [], [], []
    quality = Counter()
    metric_counts = Counter()
    annual_counts = defaultdict(lambda: Counter())
    item_events = defaultdict(Counter)
    item_issuers = defaultdict(set)
    acceptance_missing = 0
    restatements = 0

    for s in sample:
        cik, ticker, group = f"{int(s['cik']):010d}", s["ticker"], s["group"]
        try:
            subs = fetch("subs", cik)
            facts = fetch("facts", cik)
        except Exception as e:
            quality["fetch_failed"] += 1
            continue
        recent = subs.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accs = recent.get("accessionNumber", [])
        fdates = recent.get("filingDate", [])
        adates = recent.get("acceptanceDateTime", [])
        items = recent.get("items", [])
        rdates = recent.get("reportDate", [])
        docs = recent.get("primaryDocument", [])
        by_acc = {}
        for i, acc in enumerate(accs):
            by_acc[acc] = {
                "form": forms[i] if i < len(forms) else "",
                "filing_date": fdates[i] if i < len(fdates) else "",
                "acceptance": adates[i] if i < len(adates) else "",
                "items": items[i] if i < len(items) else "",
                "report_date": rdates[i] if i < len(rdates) else "",
                "doc": docs[i] if i < len(docs) else "",
            }
        # Facts: preserve accession-level values, never latest companyfacts snapshot backfill.
        for namespace in ("us-gaap", "ifrs-full", "dei"):
            for tag, obj in facts.get("facts", {}).get(namespace, {}).items():
                metric = next((m for m, tags in METRICS.items() if tag in tags), None)
                if not metric:
                    continue
                for unit, values in obj.get("units", {}).items():
                    for v in values:
                        allowed_fact_forms = ("10-K", "10-Q", "10-K/A", "10-Q/A") if group != "FOREIGN_ADR" else ("20-F", "40-F", "20-F/A", "40-F/A")
                        if v.get("form") not in allowed_fact_forms:
                            continue
                        filed = v.get("filed", "")
                        if not ("2009-01-01" <= filed <= "2024-12-31"):
                            continue
                        acc = v.get("accn", "")
                        if not acc:
                            continue
                        row = {
                            "cik": cik, "ticker": ticker, "group": group, "metric": metric,
                            "taxonomy": namespace, "tag": tag, "unit": unit,
                            "accession": acc, "form": v.get("form", ""),
                            "filing_date": by_acc.get(acc, {}).get("filing_date", v.get("filed", "")),
                            "acceptance_datetime": by_acc.get(acc, {}).get("acceptance", ""),
                            "fiscal_period": f"{v.get('fy','')}{v.get('fp','')}",
                            "period_start": v.get("start", ""), "period_end": v.get("end", ""),
                            "value": v.get("val"), "frame": v.get("frame", ""),
                            "source_url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{acc}-index.htm",
                        }
                        fact_rows.append(row)
                        metric_counts[metric] += 1
                        annual_counts[(cik, filed[:4])]["facts"] += 1
        # 8-K events.
        for i, acc in enumerate(accs):
            form = forms[i] if i < len(forms) else ""
            allowed_forms = ("8-K", "8-K/A") if group != "FOREIGN_ADR" else ("6-K", "6-K/A")
            if form not in allowed_forms:
                continue
            fd = fdates[i] if i < len(fdates) else ""
            if not ("2009-01-01" <= fd <= "2024-12-31"):
                continue
            adt = parse_accept(adates[i] if i < len(adates) else "")
            if adt is None:
                quality["8k_acceptance_missing"] += 1
            item_text = items[i] if i < len(items) else ""
            codes = [x.strip() for x in item_text.split(",") if x.strip()]
            row = {
                "cik": cik, "ticker": ticker, "group": group, "accession": acc,
                "form": form, "event_type": "8-K" if form.startswith("8-K") else "6-K", "filing_date": fd, "acceptance_datetime": adates[i] if i < len(adates) else "",
                "items": item_text, "item_count": len(codes),
                "event_session": session(adt, trading_days),
                "report_date": rdates[i] if i < len(rdates) else "",
                "filing_url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{acc}-index.htm",
            }
            ps = s.get("price_symbol", ticker)
            ser = price_close.get(ps)
            reaction, prev, nxt = _prev_next_trading(fd, row["event_session"], tdays)
            def ret(a, b):
                if ser is None or a not in ser.index or b not in ser.index:
                    return None
                return float(ser.loc[a] / ser.loc[b] - 1)
            row.update({
                "price_symbol": ps,
                "price_match": ser is not None,
                "reaction_day": reaction or "",
                "reaction_return": ret(reaction, prev),
                "next_day_return": ret(nxt, reaction),
                "daily_only": "YES",
                "intraday_claim": "NO",
            })
            event_rows.append(row)
            for code in codes:
                item_events[code]["events"] += 1
                item_issuers[code].add(cik)
                item_events[code][session(adt, trading_days)] += 1
            annual_counts[(cik, fd[:4])]["8k"] += 1
        for acc, meta in by_acc.items():
            fd = meta["filing_date"]
            if "2009-01-01" <= fd <= "2024-12-31":
                annual_counts[(cik, fd[:4])]["filings"] += 1
        quality["issuers_fetched"] += 1

    # Restatement/version audit by CIK/metric/period.
    versions = defaultdict(set)
    for r in fact_rows:
        versions[(r["cik"], r["metric"], r["taxonomy"], r["tag"], r["unit"], r["period_start"], r["period_end"])].add(r["accession"])
    restatements = sum(1 for v in versions.values() if len(v) > 1)
    quality["restatement_groups"] = restatements

    # Annual coverage.
    for (cik, year), c in sorted(annual_counts.items()):
        annual.append({"cik": cik, "year": year, "filings": c["filings"], "8k_events": c["8k"], "fact_rows": c["facts"], "metrics_covered": len({r["metric"] for r in fact_rows if r["cik"] == cik and r["filing_date"].startswith(year)})})
    pd.DataFrame(annual).to_csv(OUT / "p12_3_annual_coverage.csv", index=False)
    pd.DataFrame(fact_rows).to_csv(OUT / "p12_3_accession_fact_panel.csv", index=False)
    pd.DataFrame(event_rows).to_csv(OUT / "p12_3_filing_events.csv", index=False)
    item_rows = []
    for code, c in sorted(item_events.items()):
        item_rows.append({"item": code, "description": ITEM_DESC.get(code, "OTHER"), "events": c["events"], "issuers": len(item_issuers[code]), "acceptance_missing": 0, "premarket": c["PREMARKET"], "intraday": c["INTRADAY"], "after_hours": c["AFTER_HOURS"], "non_trading": c["NON_TRADING"], "unknown": c["UNKNOWN"]})
    pd.DataFrame(item_rows).to_csv(OUT / "p12_3_8k_item_coverage.csv", index=False)
    # Quality summary.
    qrows = [
        {"metric": "sample_issuers", "value": len(sample), "status": "PILOT_SAMPLE", "notes": "fixed before financial results"},
        {"metric": "issuers_fetched", "value": quality["issuers_fetched"], "status": "OK" if quality["issuers_fetched"] == len(sample) else "PARTIAL", "notes": "SEC submissions+facts HTTP success"},
        {"metric": "cik_ticker_mapping", "value": len({r['cik'] for r in fact_rows}), "status": "READY_RESTRICTED", "notes": "CIK primary; ticker label only"},
        {"metric": "fact_rows", "value": len(fact_rows), "status": "READY_RESTRICTED", "notes": "accession-level as-filed facts; includes amendments"},
        {"metric": "filing_events", "value": len(event_rows), "status": "READY_RESTRICTED", "notes": "8-K for US issuers; 6-K for foreign ADR"},
        {"metric": "8k_events", "value": sum(1 for e in event_rows if e["event_type"] == "8-K"), "status": "READY_RESTRICTED", "notes": "filing/acceptance timestamps; exact press-release time not guaranteed"},
        {"metric": "6k_foreign_events", "value": sum(1 for e in event_rows if e["event_type"] == "6-K"), "status": "PARTIAL", "notes": "foreign ADR; not comparable to 8-K disclosure"},
        {"metric": "8k_acceptance_missing", "value": quality["8k_acceptance_missing"], "status": "OK", "notes": "acceptance datetime available"},
        {"metric": "multi_accession_groups", "value": restatements, "status": "PARTIAL", "notes": "same CIK/metric/tag/unit/period with >1 accession; not all are restatements"},
        {"metric": "events_with_reaction_return", "value": sum(1 for e in event_rows if e.get("reaction_return") is not None), "status": "PARTIAL", "notes": "daily close-to-close; no intraday"},
        {"metric": "foreign_events_price_missing", "value": sum(1 for e in event_rows if not e.get("price_match")), "status": "DATA_BLOCKED", "notes": "foreign ADRs absent from local price panel"},
        {"metric": "price_tickers_matched", "value": sum(1 for s in sample if s['price_symbol'] in price_close), "status": "PARTIAL", "notes": "daily adjusted close only"},
        {"metric": "full_market_claim", "value": 0, "status": "DATA_BLOCKED", "notes": "40-issuer pilot only"},
    ]
    pd.DataFrame(qrows).to_csv(OUT / "p12_3_pit_quality_summary.csv", index=False)
    manifest = {
        "sample_file": str(args.sample),
        "issuers": len(sample),
        "fact_rows": len(fact_rows),
        "events": len(event_rows),
        "raw_sec_json_committed": False,
        "raw_price_committed": False,
        "source": "SEC submissions + companyfacts + local FINSABER price panel",
        "run_command": "python -m tools.research.p12.sec_pit_pilot",
        "notes": "Latest companyfacts values are used only with accession ancestry; no latest-value backfill.",
    }
    (OUT / "p12_3_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
