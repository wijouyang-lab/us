"""P8.1 rolling walk-forward over the corrected PIT monthly returns."""
from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("data/research/p8")
TRAIN = 60; TEST = 12; PURGE = 1


def sharpe(x):
    x = np.asarray(x, float)
    return float(x.mean() / x.std(ddof=1) * math.sqrt(12)) if len(x) > 1 and x.std(ddof=1) > 0 else None


def hac(x, lags=6):
    x = np.asarray([v for v in x if np.isfinite(v)], float); n = len(x)
    if n < 20: return None, None
    mu = x.mean(); e = x - mu; var = float(e @ e / n)
    for lag in range(1, min(lags, n - 1) + 1):
        var += 2 * (1 - lag / (lags + 1)) * float(e[lag:] @ e[:-lag] / n)
    se = math.sqrt(max(var, 0) / n)
    if not se: return None, None
    t = mu / se
    from math import erf, sqrt
    return t, 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))


def main():
    df = pd.read_csv(OUT / "pit_monthly_corrected.csv", parse_dates=["formation"])
    pivot = df.pivot(index="formation", columns="strategy", values="net").sort_index()
    windows = []; selected = []; fixed = {k: [] for k in pivot.columns}
    for start in range(TRAIN + PURGE, len(pivot) - TEST + 1, TEST):
        train = pivot.iloc[start - TRAIN - PURGE:start - PURGE]
        test = pivot.iloc[start:start + TEST]
        if len(test) < TEST: continue
        sharpes = {c: sharpe(train[c].values) for c in pivot.columns}
        best = max((c for c in sharpes if sharpes[c] is not None), key=lambda c: sharpes[c])
        selected.extend(test[best].values.tolist())
        for c in pivot.columns: fixed[c].extend(test[c].values.tolist())
        windows.append({"test_start": str(test.index[0].date()), "test_end": str(test.index[-1].date()),
                        "train_start": str(train.index[0].date()), "train_end": str(train.index[-1].date()),
                        "train_n": len(train), "test_n": len(test), "selected": best,
                        "train_sharpes": {k: round(v, 4) if v is not None else None for k, v in sharpes.items()},
                        "test_return": float((np.prod(1 + test[best].values) - 1))})
    def stats(x):
        x = np.asarray(x, float); eq = np.cumprod(1 + x); years = len(x) / 12
        t, p = hac(x)
        return {"months": len(x), "cagr": float(eq[-1] ** (1 / years) - 1) if years else None,
                "sharpe": sharpe(x), "max_drawdown": float((eq / np.maximum.accumulate(eq) - 1).min()) if len(eq) else None,
                "hac_t_vs_zero": t, "p_value_vs_zero": p}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "method": "rolling 60m train, 1m purge, 12m test; strategy selected only on train Sharpe; fixed top20; net 10bps",
              "windows": windows, "selected_strategy": stats(selected),
              "fixed_strategy_test_results": {k: stats(v) for k, v in fixed.items()},
              "status": "WALK_FORWARD_COMPLETE", "note": "HAC is vs zero, not vs EW; no parameter grid."}
    (OUT / "walk_forward_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"windows": len(windows), "selected": report["selected_strategy"],
                      "fixed": {k: v["sharpe"] for k, v in report["fixed_strategy_test_results"].items()}}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
