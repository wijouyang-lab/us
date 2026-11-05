"""P6.7 stability checks over the reconstructed historical Quality V1 panel."""
from __future__ import annotations
import argparse, csv, gzip, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

SCORES = Path("data/research/quality_pit_scores_p67.csv.gz")
COVERAGE = Path("data/research/quality_pit_coverage_p67.json")
OUT = Path("data/research/quality_historical_stability_p67.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", type=Path, default=SCORES)
    ap.add_argument("--coverage", type=Path, default=COVERAGE)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    df = pd.read_csv(a.scores, compression="gzip")
    cov = json.loads(a.coverage.read_text(encoding="utf-8"))
    df["year"] = df["observation_date"].str[:4]
    annual = []
    for y, g in df.groupby("year"):
        annual.append({"year": y, "observations": len(g), "issuers": int(g["cik"].nunique()),
                       "median_score": round(float(g["score"].median()),3),
                       "q1": round(float(g["score"].quantile(.25)),3),
                       "q3": round(float(g["score"].quantile(.75)),3)})
    persist = []
    dates = sorted(df["observation_date"].unique())
    for q1, q2 in zip(dates, dates[1:]):
        x = df[df.observation_date==q1][["cik","score"]]
        y = df[df.observation_date==q2][["cik","score"]]
        z = x.merge(y, on="cik", suffixes=("_a","_b"))
        if len(z) >= 10:
            persist.append({"from":q1,"to":q2,"n":len(z),
                            "spearman":round(float(z["score_a"].corr(z["score_b"],method="spearman")),4)})
    # rank persistence between first and last year for common issuers
    first = df[df.year == df.year.min()][["cik","score"]]
    last = df[df.year == df.year.max()][["cik","score"]]
    z = first.merge(last, on="cik", suffixes=("_a","_b"))
    long_persist = round(float(z["score_a"].corr(z["score_b"], method="spearman")),4) if len(z) >= 10 else None
    report = {"metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
                           "scores_file": str(a.scores), "coverage": str(a.coverage)},
              "period": {"start": dates[0], "end": dates[-1], "configured_quarters": int(cov.get("financial", {}).get("historical_quarters", 43)),
                         "scored_quarters": len(dates), "observations": len(df),
                         "unique_issuers": int(df.cik.nunique())},
              "annual": annual, "adjacent_quarter_rank_persistence": persist,
              "long_horizon_first_last_year_spearman": long_persist,
              "gate": cov.get("gates"),
              "note": "Historical panel is current-survivor based; current SIC is a non-PIT proxy. Not BACKTEST_READY."}
    a.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"quarters": len(dates), "observations": len(df), "issuers": int(df.cik.nunique()),
                      "long_spearman": long_persist, "gate": cov.get("gates")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
