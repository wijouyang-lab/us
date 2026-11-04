"""P4.2 recomputation with the official split evidence registry."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from tools.investment_research.metrics import Snapshot
from tools.investment_research.sec.normalize import extract
from tools.investment_research.dividend.dividend_quality import dividend_metrics


def main():
    snap = json.loads(Path("docs/research/sec_fundamentals_snapshot.json").read_text())
    splits = {x["ticker"]: x for x in json.loads(Path("data/research/split_evidence_p42.json").read_text())}
    old = json.loads(Path("data/research/dividend_quality_p41.json").read_text()).get("tickers", {})
    events = json.loads(Path("data/research/dividend_events_p42.json").read_text())
    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "score_version": "dividend-score-2.1", "tickers": {}}
    for t, a in snap.items():
        cik = a.get("cik"); p = Path(f"data/sec/cache/companyfacts_{cik}.json")
        if not p.exists(): continue
        facts = extract(json.loads(p.read_text()), cik=cik, fetched_at="cached")
        sector = (a.get("industry") or {}).get("normalized_industry")
        sp = splits.get(t, {"status": "SPLIT_HISTORY_INCOMPLETE", "events": [], "source_share_basis": "UNKNOWN"})
        m = dividend_metrics(Snapshot(t, cik, facts), sector=sector,
                             split_basis_verified=(sp.get("status") == "SPLIT_CONFIRMED"))
        out["tickers"][t] = {
            "cik": cik, "sector": sector,
            "classification": m["classification"].get("value") or
                ("NON_DIVIDEND_PAYER" if m["classification"].get("status") == "NON_DIVIDEND_PAYER" else "DIVIDEND_DATA_BLOCKED"),
            "split_status": sp.get("status"), "split_events": sp.get("events", []),
            "source_share_basis": sp.get("source_share_basis", "UNKNOWN"),
            "dps_split_basis": m.get("dps_split_basis"), "growth_status": m.get("growth_status"),
            "score": m.get("dividend_quality_score"), "score_status": m.get("score_status"),
            "score_components": m.get("score_components"), "score_version": "2.1",
            "comparison_group": m.get("comparison_group"),
            "metrics": {k: m.get(k) for k in
                ("net_income_payout","fcf_payout","fcf_dividend_coverage","consecutive_growth_years",
                 "total_positive_growth_years","dividend_cuts","dps_history_years","continuity_status",
                 "dividend_continuity","capital_allocation")},
            "old_score": old.get(t, {}).get("score"), "old_score_status": old.get(t, {}).get("score_status"),
            "official_events": [e for e in events if e.get("ticker") == t],
        }
    Path("data/research/dividend_quality_p42.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("wrote", len(out["tickers"]))


if __name__ == "__main__":
    main()
