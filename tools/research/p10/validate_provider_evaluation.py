"""Validate P10 provider comparison and sample-validation data.

This is a scope/consistency check, not evidence that a vendor's claims are true.
A row can only be PASS when it carries a real evidence URL; actual downloads are
recorded separately by the research run.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data/research"
PROVIDERS = DATA / "p10_provider_comparison.csv"
SAMPLES = DATA / "p10_sample_validation.csv"
REQUIRED_PROVIDER = {
    "provider", "product", "category", "official_url", "pricing_url",
    "price_display", "price_monthly_usd", "price_as_of", "history_start",
    "exchanges", "delisted_support", "symbol_history",
    "historical_constituents_pit", "corporate_actions", "access_method",
    "trial", "license_research", "license_redistribution", "price_verified",
    "coverage_verified", "notes",
}
REQUIRED_SAMPLE = {
    "sample_id", "ticker", "company", "category", "event_period", "provider",
    "status", "evidence_url", "checks", "notes",
}
VALID_STATUS = {"PASS", "PARTIAL", "NOT_RUN", "NOT_VERIFIED"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def validate() -> list[str]:
    errors: list[str] = []
    prov = read_csv(PROVIDERS)
    samp = read_csv(SAMPLES)
    if not prov:
        return ["provider comparison is empty"]
    if not REQUIRED_PROVIDER.issubset(prov[0]):
        errors.append("provider comparison missing required columns")
    if len({r["provider"] for r in prov}) < 8:
        errors.append("need at least 8 distinct providers")
    if len({r["category"] for r in prov}) < 4:
        errors.append("need prices, fundamentals, macro and news categories")
    for r in prov:
        if r["price_verified"] == "YES" and not r["pricing_url"].startswith("https://"):
            errors.append(f"verified price without official URL: {r['provider']}")
        if r["price_verified"] not in {"YES", "NO"}:
            errors.append(f"invalid price_verified: {r['provider']}")
        if r["license_redistribution"] not in {"YES", "NO", "UNKNOWN"}:
            errors.append(f"invalid redistribution status: {r['provider']}")

    if not REQUIRED_SAMPLE.issubset(samp[0]) if samp else True:
        return errors + ["sample validation missing required columns"]
    tickers = {r["ticker"] for r in samp}
    if len(tickers) < 30:
        errors.append(f"need at least 30 distinct tickers, got {len(tickers)}")
    providers = {r["provider"] for r in samp}
    if providers != {"Sharadar", "Norgate", "EODHD"}:
        errors.append(f"unexpected sample providers: {sorted(providers)}")
    for p in providers:
        n = sum(1 for r in samp if r["provider"] == p)
        if n != len(tickers):
            errors.append(f"{p} sample coverage {n} != {len(tickers)}")
    for r in samp:
        if r["status"] not in VALID_STATUS:
            errors.append(f"invalid sample status: {r['sample_id']}")
        if r["status"] == "PASS" and not r["evidence_url"]:
            errors.append(f"PASS without evidence: {r['sample_id']}")
        if r["status"] == "PASS" and "UNKNOWN" in r["checks"]:
            errors.append(f"PASS with unknown checks: {r['sample_id']}")
    cats = {r["category"] for r in samp}
    for required in {"delisted", "rename_FB", "large_cap_split", "spinoff", "small_cap"}:
        if required not in cats:
            errors.append(f"missing sample category: {required}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("P10_VALIDATION=FAIL")
        for e in errors:
            print(f"- {e}")
        return 1
    print("P10_VALIDATION=PASS")
    print(f"providers={len(read_csv(PROVIDERS))}")
    print(f"samples={len(read_csv(SAMPLES))} tickers={len({r['ticker'] for r in read_csv(SAMPLES)})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
