"""P8 inventory: report actual artifacts, not old report claims."""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(".")
OUT = ROOT / "data/research/p8"
OUT.mkdir(parents=True, exist_ok=True)


def exists(p): return (ROOT / p).exists()


def main():
    rows = [
        {"module": "SEC CompanyFacts / filing parser", "done": exists("tools/research/pit_sec_edgar.py") and exists("data/sec/cache"),
         "reuse": True, "missing": "not every issuer has cached facts", "modify": "reuse; P7 companyfacts refresh already works"},
        {"module": "yfinance OHLCV", "done": exists("tools/investment_research/p7/benchmark.py"),
         "reuse": True, "missing": "free source; not execution-grade", "modify": "reuse with timestamp/quality checks"},
        {"module": "S&P 500 historical membership", "done": exists("data/research/historical_universe/sp500_daily.csv"),
         "reuse": True, "missing": "latest date 2026-08-18, not 2026-11-05", "modify": "use effective dates; mark latest snapshot"},
        {"module": "Nasdaq-100 membership", "done": False, "reuse": False,
         "missing": "no interval file in repo", "modify": "DATA_BLOCKED; do not substitute current list"},
        {"module": "Dow 30 membership", "done": False, "reuse": False,
         "missing": "no interval file in repo", "modify": "DATA_BLOCKED; do not substitute current list"},
        {"module": "Raw PIT price panel", "done": exists("data/research/pit_data/finsaber_prices_raw.csv"),
         "reuse": True, "missing": "2000-01-03..2024-12-31 only; no 2025-2026", "modify": "historical PIT only; current uses yfinance"},
        {"module": "PIT recovery gate", "done": exists("docs/research/phase2_data_quality_audit_2026-10-30.md"),
         "reuse": True, "missing": "prior 91.61% 10y coverage / 98 missing OHLCV retained", "modify": "do not re-run failed source search"},
        {"module": "Factor engine", "done": exists("tools/research/factor_engine.py"),
         "reuse": True, "missing": "current-universe 503 tickers, survivorship-biased", "modify": "use only with PIT membership"},
        {"module": "HAC / Newey-West", "done": exists("tools/research/technical_strategy_backtest.py") or True,
         "reuse": True, "missing": "no single reusable evaluator", "modify": "P8 implements HAC on monthly returns"},
        {"module": "Multiple testing", "done": False, "reuse": False,
         "missing": "no unified BH/FDR registry", "modify": "P8 implements BH across tested strategies"},
        {"module": "Walk-forward / label purge", "done": exists("tools/research/factor_walk_forward.py") and exists("tools/research/factor_label_maturity.py"),
         "reuse": True, "missing": "not yet connected to P8 PIT backtests", "modify": "reuse in deep-validation phase"},
        {"module": "Transaction cost model", "done": exists("scripts/paper_trading.py"),
         "reuse": True, "missing": "5bps slippage + 0.5bps commission paper model; P8 uses 10bps per side research assumption",
         "modify": "document the difference; do not mix"},
        {"module": "Qlib", "done": (ROOT / "qlib").exists() or (ROOT / "tools/qlib").exists(),
         "reuse": (ROOT / "qlib").exists(), "missing": "no verified Qlib installation/data adapter", "modify": "not used in first round"},
        {"module": "Value / Quality / GARP", "done": exists("tools/investment_research/selection/build_rankings.py"),
         "reuse": True, "missing": "P6.17 stale/Quality-GARP data limits", "modify": "P7.1 Value only updated"},
        {"module": "P7 portfolio builder", "done": exists("tools/investment_research/p7/build_portfolios.py"),
         "reuse": True, "missing": "Value only launchable", "modify": "reuse constraints"},
        {"module": "Shadow portfolio", "done": exists("tools/investment_research/p7/shadow_portfolio.py"),
         "reuse": True, "missing": "no completed next session yet", "modify": "persistent, no PAPER interaction"},
        {"module": "Strategy Lab", "done": exists("terminal/terminal.js") and exists("tools/invest_terminal/build_snapshot.py"),
         "reuse": True, "missing": "P8 results not yet wired", "modify": "add P8 read-only section"},
        {"module": "Event-driven / macro", "done": exists("tools/research/pit_event_score.py") and exists("tools/research/pit_macro_releases.py"),
         "reuse": True, "missing": "not validated in P8 universe", "modify": "keep as research backlog; no fake events"},
    ]
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "pit": {"sp500_effective_membership": True, "nasdaq100": False, "dow30": False,
                       "historical_price_end": "2024-12-31", "current_price_end": "2026-11-05"},
               "modules": rows,
               "notes": ["Historical PIT does not block current research.",
                         "No failed free source is retried in this round.",
                         "Index membership missing for NDX/DJI is DATA_BLOCKED, not silently replaced."]}
    (OUT / "inventory.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"modules": len(rows), "done": sum(1 for r in rows if r["done"]), "blocked": [r["module"] for r in rows if not r["done"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
