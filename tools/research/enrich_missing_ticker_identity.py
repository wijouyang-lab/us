#!/usr/bin/env python3
"""Enrich missing-ticker records with SEC identity and membership evidence.

Evidence is kept separate from price data.  A membership removal is NOT
interpreted as proof of delisting.  SEC submissions are cached locally; no
credentials are required or logged.

Research only.  No production imports.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import requests

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
USER_AGENT = "wijouyang-lab research audit contact@example.com"
FORM_PRIORITY = ("8-K", "10-K", "10-Q", "S-4", "DEF 14A")


def _clean(value) -> str:
    return str(value or "").replace("*", "").strip()


def load_membership(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df["symbol"] = df["symbol"].str.upper().str.strip()
    df["cik"] = df["cik"].str.replace(r"\D", "", regex=True).str.zfill(10)
    return df


def _one_membership_row(group: pd.DataFrame) -> pd.Series:
    # Prefer the row with a removal date, then the latest addition.
    removed = group[group["date_removed"].map(_clean) != ""]
    if not removed.empty:
        return removed.sort_values("date_removed").iloc[-1]
    return group.sort_values("date_added").iloc[-1]


def fetch_submissions(cik: str, cache_dir: Path, session: requests.Session, sleeper=time.sleep) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"CIK{cik}.json"
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    response = session.get(
        SUBMISSIONS_URL.format(cik=cik),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    target.write_text(json.dumps(payload), encoding="utf-8")
    sleeper(0.15)  # SEC fair-access pacing
    return payload


def latest_filing(payload: dict) -> dict:
    recent = (payload.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    docs = recent.get("primaryDocument") or []
    best = None
    for form, day, acc, doc in zip(forms, dates, accessions, docs):
        if form not in FORM_PRIORITY:
            continue
        rank = FORM_PRIORITY.index(form)
        if best is None or rank < best[0]:
            best = (rank, form, day, acc, doc)
    if best is None:
        return {}
    _, form, day, acc, doc = best
    accession = str(acc).replace("-", "")
    return {
        "form": form,
        "filing_date": day,
        "accession": acc,
        "url": f"https://www.sec.gov/Archives/edgar/data/{int(payload.get('cik', 0))}/{accession}/{doc}",
    }


def enrich(classification: pd.DataFrame, membership: pd.DataFrame, cache_dir: Path,
           session: requests.Session) -> pd.DataFrame:
    rows = []
    for rec in classification.to_dict("records"):
        ticker = str(rec["ticker"]).upper()
        group = membership[membership["symbol"] == ticker]
        if group.empty:
            rows.append({**rec, "identity_confidence": "unresolved", "identity_error": "no membership/CIK match"})
            continue
        member = _one_membership_row(group)
        cik = str(member["cik"]).zfill(10)
        try:
            payload = fetch_submissions(cik, cache_dir, session)
            error = ""
        except Exception as exc:
            payload = {}
            error = f"{type(exc).__name__}: {exc}"
        filing = latest_filing(payload) if payload else {}
        former = payload.get("formerNames") or []
        former_names = "; ".join(
            f"{x.get('name', '')} ({_clean(x.get('from', ''))}..{_clean(x.get('to', ''))})"
            for x in former
            if x.get("name")
        )
        removed = _clean(member.get("date_removed"))
        added = _clean(member.get("date_added"))
        if removed:
            event_type = "removed_from_sp500_not_necessarily_delisted"
        else:
            event_type = "historical_membership_no_recorded_removal"
        rows.append({
            **rec,
            "cik": cik,
            "company_name": payload.get("name", member.get("name", "")),
            "sec_tickers_current": ",".join(payload.get("tickers") or []),
            "membership_added": added,
            "membership_removed": removed,
            "former_names": former_names,
            "event_type": event_type,
            "event_effective_date": removed,
            "announcement_available_date": filing.get("filing_date", ""),
            "latest_relevant_filing": filing.get("form", ""),
            "filing_url": filing.get("url", ""),
            "identity_evidence_url": SUBMISSIONS_URL.format(cik=cik),
            "identity_confidence": "high" if payload and filing else ("medium" if payload else "unresolved"),
            "identity_error": error,
            "next_step": "review SEC filing for merger/name/ticker event; then find a verified OHLCV source",
        })
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classification", required=True)
    parser.add_argument("--membership", required=True)
    parser.add_argument("--cache-dir", default=".research_cache/sec_submissions")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    cache = Path(args.cache_dir)
    classification = pd.read_csv(args.classification, dtype=str, keep_default_na=False)
    membership = load_membership(Path(args.membership))
    session = requests.Session()
    out = enrich(classification, membership, cache, session)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8")
    print(out["identity_confidence"].value_counts().to_string())
    print(out["event_type"].value_counts().to_string())
    print(f"wrote {len(out)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
