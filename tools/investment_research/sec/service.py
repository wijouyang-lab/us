"""SEC ingestion service for a small, demonstrable P2 universe."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

from tools.investment_research.sec.client import SECClient
from tools.investment_research.sec.normalize import extract
from tools.investment_research.sec.industry import industry_from_submissions
from tools.investment_research.metrics import analyze


def fetch_company(client: SECClient, ticker: str, *, as_of: str | None = None,
                  market_quote: dict | None = None, share_count: dict | None = None,
                  sector: str | None = None) -> dict:
    t = ticker.upper()
    mp = client.ticker_map()
    mapping = mp.get(t) or mp.get(t.replace(".", "-")) or mp.get(t.replace("-", "."))
    if not mapping:
        return {"ticker": t, "status": "IDENTITY_UNVERIFIED", "error": "ticker not in SEC map"}
    cik = mapping["cik"]
    sub = client.submissions(cik); facts_json = client.companyfacts(cik)
    accepted = {}
    for i, acc in enumerate(sub.get("filings", {}).get("recent", {}).get("accessionNumber", [])):
        dt = sub["filings"]["recent"].get("acceptanceDateTime", [None] * (i + 1))[i]
        if acc and dt: accepted[acc] = dt
    payload = json.dumps(facts_json, sort_keys=True).encode()
    fetched = datetime.now(timezone.utc).isoformat()
    facts = extract(facts_json, cik=cik, fetched_at=fetched,
                    sha256=hashlib.sha256(payload).hexdigest(), accepted=accepted)
    ind = industry_from_submissions(cik, sub, manual_sector=sector,
                                    manual_reason="caller sector override" if sector else None)
    ind["ticker"] = t
    analysis = analyze(t, cik, facts, as_of=as_of, market_quote=market_quote,
                       share_count=share_count, sector=ind["normalized_industry"])
    analysis["industry"] = ind
    analysis["company_name"] = mapping["company_name"]
    analysis["identity_source"] = "SEC company_tickers.json"
    analysis["companyfacts_sha256"] = hashlib.sha256(payload).hexdigest()
    analysis["facts_count"] = len(facts)
    return analysis


def get_fundamentals(ticker: str, *, as_of: str | None = None, cache_dir: str = "data/sec/cache",
                     market_quote: dict | None = None, share_count: dict | None = None,
                     sector: str | None = None) -> dict:
    """Fetch SEC facts and return Value/Quality/GARP metrics gated by as_of."""
    return fetch_company(SECClient(cache_dir), ticker, as_of=as_of, market_quote=market_quote,
                         share_count=share_count, sector=sector)
