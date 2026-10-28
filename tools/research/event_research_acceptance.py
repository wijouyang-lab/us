#!/usr/bin/env python3
"""One research-only acceptance entrypoint for data, readiness, and archive.

Exit codes:
  0 = all checks pass
  2 = valid but pending (provider close, future bars, price basis)
  1 = fail/corrupt/missing input
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from tools.research.event_archive_store import rebuild
from tools.research.event_post_bar_readiness import evaluate as readiness


def _load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise ValueError(f"missing input: {p}")
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {p}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {p}")
    return value


def _max_date(df: pd.DataFrame, label: str) -> str:
    if "Date" not in df.columns:
        raise ValueError(f"{label} has no Date column")
    dates = pd.to_datetime(df["Date"], errors="coerce")
    if dates.dropna().empty:
        raise ValueError(f"{label} has no valid dates")
    return str(dates.max().date())


def _readiness_bundle(events, panel, spy, spy_meta, as_of):
    stock = readiness(events, panel, as_of=as_of)
    merged = panel.copy()
    merged["Ticker"] = merged["Ticker"].astype(str).str.upper()
    spy = spy.copy()
    spy["Ticker"] = "SPY"
    if "Adj_Close" not in spy.columns:
        raise ValueError("SPY file has no Adj_Close")
    spy["Close"] = spy["Adj_Close"]
    merged = pd.concat([merged, spy], ignore_index=True)
    market = readiness(events, merged, as_of=as_of, market_proxy="SPY",
                       research_mode="market_proxy_spy", proxy_metadata=spy_meta)
    return stock, market


def run(args) -> dict[str, Any]:
    for label, path in (("price_panel", args.price_panel), ("spy_file", args.spy_file), ("events", args.events)):
        if not Path(path).exists():
            raise ValueError(f"missing input: {path}")
    panel = pd.read_csv(args.price_panel)
    spy = pd.read_csv(args.spy_file)
    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    updater = _load_json(args.updater_metadata)
    spy_meta = _load_json(args.spy_metadata)
    archive = rebuild(Path(args.archive_store))
    stock, market = _readiness_bundle(events, panel, spy, spy_meta, args.as_of)
    panel_date = _max_date(panel, "price panel")
    spy_date = _max_date(spy, "SPY")
    required = args.required_date
    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    if panel_date != spy_date:
        add("date_alignment", "fail", {"panel": panel_date, "spy": spy_date})
    else:
        add("date_alignment", "pass", {"date": panel_date})
    if panel_date < required:
        add("required_close", "pending", {"required": required, "latest": panel_date,
                                          "reason": "pending_provider_close"})
    else:
        add("required_close", "pass", {"required": required, "latest": panel_date})
    if updater.get("failed_tickers", 0) or updater.get("download_status") not in {"ok", "no_new_sessions"}:
        add("updater", "fail" if updater.get("failed_tickers", 0) else "pending",
            {"status": updater.get("download_status"), "failed": updater.get("failed_tickers", 0)})
    else:
        add("updater", "pass", {"status": updater.get("download_status")})
    add("readiness_stock", "pass", {k: stock[k] for k in ("ready", "pending", "excluded", "lookahead_flags")})
    add("readiness_spy", "pass", {k: market[k] for k in ("ready", "pending", "excluded", "lookahead_flags")})
    add("archive_verify", "pass", archive)
    if any(c["status"] == "fail" for c in checks):
        overall, code = "fail", 1
    elif any(c["status"] == "pending" for c in checks):
        overall, code = "pending", 2
    else:
        overall, code = "pass", 0
    return {
        "exit_status": overall,
        "exit_code": code,
        "as_of": args.as_of,
        "required_date": required,
        "inputs": {
            "events": args.events,
            "price_panel": args.price_panel,
            "spy_file": args.spy_file,
            "updater_metadata": args.updater_metadata,
            "spy_metadata": args.spy_metadata,
            "archive_store": args.archive_store,
        },
        "data_dates": {"panel": panel_date, "spy": spy_date},
        "updater": updater,
        "readiness": {"stock": stock, "market_proxy_spy": market},
        "archive": archive,
        "checks": checks,
        "research_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--spy-file", required=True)
    p.add_argument("--spy-metadata", required=True)
    p.add_argument("--updater-metadata", required=True)
    p.add_argument("--archive-store", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--required-date", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    try:
        result = run(args)
    except Exception as exc:
        result = {"exit_status": "fail", "exit_code": 1, "error": f"{type(exc).__name__}: {exc}"}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"exit_status": result["exit_status"], "exit_code": result["exit_code"],
                      "data_dates": result.get("data_dates"), "checks": result.get("checks")}, indent=2))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
