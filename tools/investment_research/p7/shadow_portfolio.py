"""P7 independent research shadow: no PAPER-50000 reads/writes, no orders."""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

P7 = Path("data/universe/p7")


def read(p):
    b = p.read_bytes()[:2]
    with p.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    weights = read(P7 / "portfolio_weights.csv")
    risk = json.loads((P7 / "portfolio_risk_summary.json").read_text(encoding="utf-8"))
    scores = read(P7 / "strategy_candidates.csv")
    chosen = next((s for s in ("VALUE_V1", "QUALITY_V1", "GARP_V1", "BLENDED_V1")
                   if risk["strategies"][s].get("launchable")), None)
    if not chosen:
        raise SystemExit("P7: no launchable strategy for shadow")
    target = [r for r in weights if r["strategy"] == chosen and r["variant"] == "risk_adjusted"]
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "shadow_id": "RESEARCH_SHADOW_P7", "status": "INITIALIZED_PENDING_NEXT_SESSION",
               "research_only": True, "paper_account_untouched": True,
               "paper_account_read": False, "paper_account_write": False,
               "initial_capital": 50000.0, "signal_date": "2026-11-05",
               "next_tradable_session": "2026-11-06",
               "strategy": chosen, "holdings": len(target),
               "cash_weight": 0.05, "execution_status": "PENDING_NEXT_SESSION",
               "note": "Signal is after the 2026-11-05 close. No fill or return is fabricated before the next completed session."}
    positions = []
    for r in target:
        positions.append({"shadow_id": "RESEARCH_SHADOW_P7", "signal_date": "2026-11-05",
                          "ticker": r["ticker"], "target_weight": r["weight"],
                          "target_notional_usd": r["target_notional_usd"],
                          "status": "PENDING_NEXT_SESSION", "execution_date": "",
                          "fill_price": "", "shares": "", "reason": "NEXT_TRADABLE_SESSION_PRICE_REQUIRED"})
    with (P7 / "shadow_positions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(positions[0].keys())); w.writeheader(); w.writerows(positions)
    nav = [{"date": "2026-11-05", "shadow_id": "RESEARCH_SHADOW_P7", "nav": 50000.0,
            "cash": 50000.0, "positions_value": 0.0, "fees": 0.0, "turnover": 0.0,
            "status": "PENDING_NEXT_SESSION", "spy_return": "", "qqq_return": "", "iwm_return": "",
            "note": "Initial funding only; no fill before next completed session."}]
    with (P7 / "shadow_nav.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(nav[0].keys())); w.writeheader(); w.writerows(nav)
    status = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "status": "P7_RESEARCH_READY", "research_only": True,
              "as_of": "2026-11-05", "shadow": summary,
              "strategies": {s: risk["strategies"][s] for s in ("VALUE_V1", "QUALITY_V1", "GARP_V1", "BLENDED_V1")},
              "strategy_candidates": scores,
              "portfolio_risk": risk,
              "target_weights": target,
              "shadow_nav": nav[-1],
              "benchmarks": json.loads((P7 / "benchmark_summary.json").read_text(encoding="utf-8")),
              "not_claimed": ["No Alpha", "No PIT backtest", "No PAPER-50000 interaction", "Not a BUY/SELL signal"]}
    (P7 / "p7_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({"strategy": chosen, "holdings": len(positions), "shadow": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
