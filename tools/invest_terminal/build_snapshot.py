"""Build the read-only JSON contract for the integrated Invest Terminal page."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

from tools.invest_terminal.strategy_registry import STRATEGIES, BENCHMARKS
from tools.invest_terminal.risk import build_risk
from tools.invest_terminal.signals import evaluate
from tools.paper_trading.engine import PaperEngine

DEFAULT_DASHBOARD = Path("dashboard/data/dashboard_data.json")
DEFAULT_OUT = Path("dashboard/data/invest_terminal_data.json")


def load_paper(root: Path):
    engine = PaperEngine(root)
    account = engine.account()
    orders = list(engine.store.orders().values())
    history = engine.store.history()
    return engine, account, orders, history


def build(dashboard_path: Path = DEFAULT_DASHBOARD, paper_root: Path = Path("data/paper_trading"),
          out: Path = DEFAULT_OUT):
    d = json.loads(dashboard_path.read_text(encoding="utf-8"))
    engine, account, orders, history = load_paper(paper_root)
    prices = {}
    stocks = d.get("stocks") or []
    for s in stocks:
        s["signals"] = evaluate(s)
        px = s.get("current_price") or s.get("price")
        if px: prices[s["ticker"]] = float(px)
    risk = build_risk(account, prices, [])
    nav = risk["nav"]
    perf = {
        "status": "NO_HISTORY" if not history else "AVAILABLE",
        "nav": nav, "cash": account["cash"], "realized_pnl": account["realized_pnl"],
        "total_fees": account["total_fees"], "nav_series": [],
        "benchmarks": BENCHMARKS,
        "note": "No NAV history and no benchmark quotes are fabricated."
    }
    market_assets = [x for x in (d.get("market") or {}).get("assets", [])]
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "dashboard_generated_at": d.get("generated_at"),
            "dashboard_file": str(dashboard_path),
            "paper_db": str(Path(paper_root) / "paper.sqlite"),
            "account_id": account["account_id"],
            "real_trading": account["real_trading"],
        },
        "mode": "RESEARCH_AND_PAPER_ONLY",
        "account": {**account, "nav": nav, "orders": orders, "history": history,
                     "pending_order_count": sum(1 for o in orders if o.get("status") == "PENDING")},
        "portfolio": {"nav": nav, "cash": account["cash"], "positions": account["positions"],
                      "risk": risk, "performance": perf},
        "strategies": STRATEGIES,
        "benchmarks": BENCHMARKS,
        "scanner": {"count": len(stocks), "stocks": stocks,
                     "source": d.get("meta", {}).get("stocks_source"),
                     "universe_note": "Only dashboard active/observation stocks are exposed; no full-market fallback is implied."},
        "macro": {"regime": (d.get("market") or {}).get("regime"),
                  "assets": market_assets,
                  "macro": d.get("macro"), "indicators": d.get("macro_indicators"),
                  "forecast": d.get("macro_forecast"),
                  "updated_at": d.get("meta", {}).get("market_updated_at")},
        "news": {"items": d.get("news"), "review": d.get("review")},
        "risk": risk,
        "data_quality": {
            "status": "PARTIAL" if len(stocks) < 2 or not any(b["status"] == "AVAILABLE" for b in BENCHMARKS) else "OK",
            "warnings": risk.get("warnings", []) + ["BENCHMARK_QUOTES_UNAVAILABLE"],
            "strategy_blocked": sum(1 for s in STRATEGIES if s["status"] == "DATA_BLOCKED"),
            "strategy_pass": sum(1 for s in STRATEGIES if s["status"] == "PASS"),
            "trading": "PAPER_ONLY_MANUAL_CONFIRMATION",
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return snapshot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD)
    ap.add_argument("--paper-root", type=Path, default=Path("data/paper_trading"))
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    s = build(a.dashboard, a.paper_root, a.out)
    print(json.dumps({"out": str(a.out), "account": s["account"]["account_id"],
                      "nav": s["portfolio"]["nav"], "stocks": s["scanner"]["count"],
                      "strategies": [(x["id"], x["status"]) for x in s["strategies"]]}, indent=2))


if __name__ == "__main__":
    main()
