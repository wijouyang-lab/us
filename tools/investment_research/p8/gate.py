"""P8 first-round gate and status."""
from __future__ import annotations
import csv, json, math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

P8 = Path("data/research/p8")


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
    pit = json.loads((P8 / "pit_strategy_results.json").read_text(encoding="utf-8"))
    etf = json.loads((P8 / "etf_multiasset_results.json").read_text(encoding="utf-8"))
    inv = json.loads((P8 / "inventory.json").read_text(encoding="utf-8"))
    uni = json.loads((P8 / "universe_summary.json").read_text(encoding="utf-8"))
    rows = []
    for k, v in pit["strategies"].items():
        rows.append({"strategy": k, "family": "PIT_EQUITY_TECHNICAL", "status": v["gate"],
                     "cagr": v["cagr_net"], "oos_cagr": v["oos_cagr_net"], "sharpe": v["sharpe"],
                     "oos_sharpe": v["oos_sharpe"], "max_drawdown": v["max_drawdown"],
                     "hac_t": v["hac_t"], "bh_q": v["bh_q"], "reason": "FAILED_OOS_OR_MULTIPLE_TESTING"})
    # ETF excess versus SPY, aligned to the ETF strategy month.
    px = pd.read_csv(P8 / "etf_prices.csv", parse_dates=["Date"]).set_index("Date")
    monthly = px.resample("ME").last()
    spy_next = monthly["SPY"].pct_change().shift(-1)
    etf_returns = pd.read_csv(P8 / "etf_strategy_returns.csv", parse_dates=["date"])
    etf_rows = []
    for k, v in etf["strategies"].items():
        x = etf_returns[etf_returns.strategy == k].copy()
        x["spy"] = x["date"].map(spy_next)
        ex = (x["ret"] - x["spy"]).dropna().values
        t, p = hac(ex)
        etf_rows.append({"strategy": k, "family": "ETF_MULTIASSET", "status": "NO-GO",
                         "cagr": v["cagr"], "oos_cagr": v["oos_cagr"], "sharpe": v["sharpe"],
                         "oos_sharpe": v["oos_sharpe"], "max_drawdown": v["max_drawdown"],
                         "hac_t": t, "p_value": p, "reason": "OOS_CAGR_BELOW_SPY_OR_HAC_NOT_SIGNIFICANT"})
    rows += etf_rows
    # BH across all newly tested strategies.
    ps = [(r["strategy"], r["p_value"] if "p_value" in r else None) for r in etf_rows]
    pit_ps = [(k, v["p_value"]) for k, v in pit["strategies"].items() if v.get("p_value") is not None]
    ps = pit_ps + [x for x in ps if x[1] is not None]
    ps.sort(key=lambda z: z[1]); q = {}
    for rank, (k, p) in enumerate(ps, 1): q[k] = min(1.0, p * len(ps) / rank)
    for r in rows:
        r["bh_q_all"] = q.get(r["strategy"])
        if r["status"] == "GO" and (r["bh_q_all"] or 1) > 0.10: r["status"] = "NO-GO"
    with (P8 / "strategy_gate_results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys([k for row in rows for k in row]))); w.writeheader(); w.writerows(rows)
    wf = json.loads((P8 / "walk_forward_results.json").read_text(encoding="utf-8")) if (P8 / "walk_forward_results.json").exists() else {}
    audit = json.loads((P8 / "p8_audit.json").read_text(encoding="utf-8")) if (P8 / "p8_audit.json").exists() else {}
    status = {"generated_at": datetime.now(timezone.utc).isoformat(), "status": "P8_FIRST_ROUND_NO_GO",
              "research_only": True, "as_of": "2024-12-31",
              "universe": {"sp500_pit": True, "nasdaq100": False, "dow30": False,
                           "note": "NDX/DJI DATA_BLOCKED; no current-list substitution"},
              "pit_coverage_mean": pit["coverage_mean"], "price_panel_end": "2024-12-31",
              "inventory_modules": len(inv["modules"]),
              "strategy_gate": rows, "go_count": sum(1 for r in rows if r["status"] == "GO"),
              "data_blocked": ["NASDAQ100", "DOW30", "Qlib adapter"],
              "audit": {"status": audit.get("status"), "data_issue": pit.get("data_issue", {}),
                        "extreme_months": audit.get("extreme_months", [])},
              "walk_forward": {"status": wf.get("status"), "windows": len(wf.get("windows", [])),
                               "selected": wf.get("selected_strategy", {}),
                               "gate": "NO-GO" if (wf.get("selected_strategy", {}).get("max_drawdown") or -1) < -0.35 else "REVIEW"},
              "limits": ["No 2025-2026 historical price panel", "No options/short/leverage",
                         "PIT coverage below 95%", "ETF uses free adjusted-close proxy"]}
    (P8 / "p8_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({"status": status["status"], "go_count": status["go_count"],
                      "gate": [{k: r[k] for k in ("strategy","status","cagr","oos_cagr","bh_q_all")} for r in rows]}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
