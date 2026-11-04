"""P4.1 recomputation with strict periods and split-basis gate."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from tools.investment_research.metrics import Snapshot
from tools.investment_research.sec.normalize import extract
from tools.investment_research.dividend.dividend_quality import dividend_metrics
from tools.investment_research.dividend.split_audit import split_status


def main():
    snap = json.loads(Path("docs/research/sec_fundamentals_snapshot.json").read_text())
    old = json.loads(Path("data/research/dividend_quality_p4.json").read_text()).get("tickers", {})
    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "source": "SEC CompanyFacts", "score_version": "dividend-score-2.0", "tickers": {}}
    for ticker, a in snap.items():
        cik = a.get("cik"); p = Path(f"data/sec/cache/companyfacts_{cik}.json")
        if not p.exists():
            out["tickers"][ticker] = {"classification": "DATA_MISSING"}; continue
        facts = extract(json.loads(p.read_text()), cik=cik, fetched_at="cached")
        sector = (a.get("industry") or {}).get("normalized_industry")
        m = dividend_metrics(Snapshot(ticker, cik, facts), sector=sector, split_basis_verified=False)
        rec = {"cik": cik, "sector": sector,
               "classification": m["classification"].get("value") or
                   ("NON_DIVIDEND_PAYER" if m["classification"].get("status") == "NON_DIVIDEND_PAYER" else "DIVIDEND_DATA_BLOCKED"),
               "score": m.get("dividend_quality_score"), "score_status": m.get("score_status"),
               "score_version": m.get("score_version"), "score_components": m.get("score_components"),
               "score_weights": m.get("score_weights"), "score_denominator": m.get("score_denominator"),
               "comparison_group": m.get("comparison_group"),
               "metrics": {k: m.get(k) for k in
                   ("net_income_payout","fcf_payout","fcf_dividend_coverage","consecutive_growth_years",
                    "total_positive_growth_years","dividend_cuts","dps_history_years","continuity_status",
                    "continuity_window","fcf_coverage_stability","dividend_continuity","capital_allocation")},
               "dps_split_basis": m.get("dps_split_basis"),
               "split_audit": split_status(ticker, []),
               "old_score": old.get(ticker, {}).get("score"),
               "old_score_status": old.get(ticker, {}).get("score_status"),
               "dps_concept": m.get("dps_concept"), "cash_dividend_concept": m.get("cash_dividend_concept"),
               "dps_series": m.get("dps_series")}
        out["tickers"][ticker] = rec
    Path("data/research/dividend_quality_p41.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("wrote", len(out["tickers"]))


if __name__ == "__main__":
    main()
