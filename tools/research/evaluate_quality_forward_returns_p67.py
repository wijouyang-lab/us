"""P6.7 forward-return gate and HAC/multiple-testing helpers.

The historical gate is evaluated by rebuild_quality_pit_history_p67.py. If the
strict PIT price coverage is below 95%/98%, this script records the block and
does not run a return test.
"""
from __future__ import annotations
import argparse, json, math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

COVERAGE = Path("data/research/quality_pit_coverage_p67.json")
OUT = Path("data/research/quality_forward_return_tests_p67.json")


def newey_west_tstat(values, lags: int | None = None):
    x = np.asarray([v for v in values if v is not None], dtype=float)
    n = len(x)
    if n < 3: return {"n": n, "mean": None, "tstat": None, "se": None, "lags": 0}
    if lags is None: lags = max(1, int(round(4 * (n / 100.0) ** (2 / 9))))
    mu = x.mean(); e = x - mu
    gamma0 = float((e * e).mean())
    var = gamma0
    for lag in range(1, min(lags, n - 1) + 1):
        gamma = float((e[lag:] * e[:-lag]).mean())
        var += 2 * (1 - lag / (lags + 1)) * gamma
    var = max(var, 0.0)
    se = math.sqrt(var / n) if n else None
    return {"n": n, "mean": float(mu), "se": se, "tstat": (mu / se if se else None), "lags": int(lags)}


def bh_qvalues(pvalues):
    p = np.asarray(pvalues, dtype=float); n = len(p)
    order = np.argsort(p); q = np.empty(n); prev = 1.0
    for rank in range(n, 0, -1):
        idx = order[rank - 1]
        val = min(prev, p[idx] * n / rank)
        q[idx] = val; prev = val
    return q.tolist()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coverage", type=Path, default=COVERAGE)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    cov = json.loads(a.coverage.read_text(encoding="utf-8"))
    gates = cov.get("gates", {})
    report = {"metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage_file": str(a.coverage), "method": "Newey-West HAC; BH multiple testing",
        "return_label": "3/6/12 month forward; overlapping labels, not independent"},
        "gate": gates,
        "status": "BLOCKED_BY_HISTORICAL_PIT_GATE" if not gates.get("backtest_ready") else "READY",
        "tests": [],
        "reason": None if gates.get("backtest_ready") else
                  "member-session coverage %.4f < 0.95 and/or ticker coverage %.4f < 0.98" % (
                      cov["membership"]["member_session_coverage"], cov["membership"]["ticker_coverage"]),
        "not_run": ["quintile returns", "Q5-Q1", "IC/RankIC", "HAC significance", "subgroup tests"],
        "notes": ["No full S&P 500 PIT backtest is claimed.",
                  "Current-survivor history is exploratory and survivorship-biased."]}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "reason": report["reason"], "gate": gates}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
