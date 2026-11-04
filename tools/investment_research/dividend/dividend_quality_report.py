"""Generate the 28-company dividend-quality snapshot from cached SEC facts."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

from tools.investment_research.metrics import Snapshot
from tools.investment_research.sec.normalize import extract
from tools.investment_research.dividend.dividend_quality import dividend_metrics
from tools.investment_research.dividend.dividend_events import annual_change_flags


def main():
    base = Path("data/sec/cache")
    snap = json.loads(Path("docs/research/sec_fundamentals_snapshot.json").read_text())
    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "source": "SEC CompanyFacts", "tickers": {}}
    for ticker, a in snap.items():
        cik = a.get("cik")
        if not cik: continue
        p = base / f"companyfacts_{cik}.json"
        if not p.exists():
            out["tickers"][ticker] = {"status": "DATA_MISSING"}; continue
        facts = extract(json.loads(p.read_text()), cik=cik, fetched_at="cached")
        m = dividend_metrics(Snapshot(ticker, cik, facts))
        series = m.get("dps_series", [])
        out["tickers"][ticker] = {
            "cik": cik,
            "classification": m["classification"].get("value") or
                              ("NON_DIVIDEND_PAYER" if m["classification"].get("status") == "NON_DIVIDEND_PAYER"
                               else "DIVIDEND_DATA_BLOCKED"),
            "score": m.get("dividend_quality_score"),
            "score_status": m.get("score_status"),
            "metrics": {k: v for k, v in m.items() if k in
                        ("net_income_payout","fcf_payout","fcf_dividend_coverage",
                         "dps_growth_1y","dps_cagr_3y","dps_cagr_5y","consecutive_growth_years",
                         "dividend_cuts","dividend_continuity","dps_history_years",
                         "fcf_coverage_stability","capital_allocation")},
            "dps_series": series,
            "possible_annual_reductions": annual_change_flags(series),
            "source": "SEC CompanyFacts",
        }
    Path("data/research/dividend_quality_p4.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("wrote", len(out["tickers"]), "tickers")


if __name__ == "__main__":
    main()
