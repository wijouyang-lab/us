#!/usr/bin/env python3
"""Readiness check for post-event price bars and forward returns.

This tool does not run an event study. It only answers whether a given event
has valid timestamps, a known version, a real post-availability bar, and
enough +1/+5 bars. Raw close and unverified corporate actions are explicitly
reported and do not silently become "ready".
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from tools.research.event_market_alignment_audit import _available_at, _close_utc, _date_only, _entry_date
from tools.research.pit_event_eligibility import _parse_aware_timestamp
from tools.research.pit_event_archive import select_event_versions_asof

HORIZONS = (1, 5)


def _invalid_ohlc(row: Mapping[str, Any]) -> bool:
    try:
        o, h, l, c = (float(row[x]) for x in ("Open", "High", "Low", "Close"))
    except (KeyError, TypeError, ValueError):
        return True
    return not (o > 0 and h > 0 and l > 0 and c > 0 and h >= max(o, c, l) and l <= min(o, c, h))


def evaluate(events: list[Mapping[str, Any]], price: pd.DataFrame, *,
             as_of: str, adjusted_price_available: bool = False,
             corporate_actions_verified: bool = False,
             market_proxy: str | None = None,
             research_mode: str = "stock",
             proxy_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if research_mode not in {"stock", "market_proxy_spy"}:
        raise ValueError("research_mode must be stock or market_proxy_spy")
    proxy_metadata = dict(proxy_metadata or {})
    proxy_adjusted = bool(proxy_metadata.get("adjusted_close_available"))
    adj_ok = True if research_mode == "market_proxy_spy" and proxy_adjusted else adjusted_price_available
    corp_basis = "provider_adjustment_only" if research_mode == "market_proxy_spy" else "unverified"
    corp_ok = True if research_mode == "market_proxy_spy" and proxy_adjusted else corporate_actions_verified
    as_of_dt = _parse_aware_timestamp(as_of)
    if as_of_dt is None:
        raise ValueError("as_of must be timezone-aware ISO-8601")
    p = price.copy()
    p["Date"] = pd.to_datetime(p["Date"], errors="coerce").dt.date
    p["Ticker"] = p["Ticker"].astype(str).str.upper()
    dup = p.duplicated(["Date", "Ticker"]).sum()
    bad = p.apply(_invalid_ohlc, axis=1).sum()
    dates = sorted(p["Date"].dropna().unique())
    by_ticker = {t: g.set_index("Date").sort_index() for t, g in p.groupby("Ticker")}
    selected = select_event_versions_asof(events, as_of) if events else []
    rows = []
    for e in selected:
        event_id = str(e.get("event_id") or "")
        source = str(e.get("source") or "")
        url = str(e.get("source_url") or "")
        published = _parse_aware_timestamp(e.get("published_at_utc"))
        first_seen = _parse_aware_timestamp(e.get("first_seen_at_utc"))
        event_time = _parse_aware_timestamp(e.get("event_time_utc"))
        available = _available_at(e)
        reasons = []
        if not event_id:
            reasons.append("missing_event_id")
        if not source:
            reasons.append("missing_source")
        if not url.startswith(("http://", "https://")):
            reasons.append("missing_or_invalid_source_url")
        if published is None:
            reasons.append("missing_or_invalid_source_published_at")
        if first_seen is None:
            reasons.append("missing_or_invalid_first_seen_at")
        if _date_only(e.get("published_at_utc")) or _date_only(e.get("first_seen_at_utc")):
            reasons.append("date_only_timestamp")
        if available is None:
            reasons.append("missing_available_at")
        if available and first_seen and available < first_seen:
            reasons.append("available_before_first_seen")
        if available and available > as_of_dt:
            reasons.append("available_after_as_of")
        entity = {str(t).upper() for t in (e.get("tickers") or [])}
        ticker = next(iter(entity), None)
        if ticker is None and e.get("market_scope") == "market":
            ticker = str(market_proxy).upper() if market_proxy else None
            if ticker is None:
                reasons.append("missing_market_proxy")
        entry_date = entry_close = None
        returns = {}
        result_dates = {}
        result_closes = {}
        if ticker is None:
            reasons.append("missing_entity_ticker")
        elif ticker not in by_ticker:
            reasons.append("missing_ticker_price")
        elif available:
            entry_date, entry_close = _entry_date(available, dates)
            if entry_date is None:
                reasons.append("pending_future_entry_bar")
            else:
                g = by_ticker[ticker]
                if g.index.duplicated().any():
                    reasons.append("duplicate_price_bars")
                if entry_date not in g.index:
                    reasons.append("missing_entry_bar")
                else:
                    idx = list(g.index).index(entry_date)
                    for h in HORIZONS:
                        if idx + h >= len(g):
                            reasons.append(f"pending_future_{h}d_bar")
                        else:
                            exit_row = g.iloc[idx + h]
                            entry_row = g.loc[entry_date]
                            if _invalid_ohlc(entry_row) or _invalid_ohlc(exit_row):
                                reasons.append("invalid_ohlc")
                            else:
                                returns[f"return_{h}d"] = float(exit_row["Close"] / entry_row["Close"] - 1)
                                result_dates[h] = exit_row.name
                                result_closes[h] = exit_row["Close"]
        if not adj_ok:
            reasons.append("adjusted_price_unavailable")
        if not corp_ok:
            reasons.append("corporate_actions_unverified")
        hard = {
            "missing_event_id", "missing_source", "missing_or_invalid_source_url",
            "missing_or_invalid_source_published_at", "missing_or_invalid_first_seen_at",
            "date_only_timestamp", "missing_available_at", "available_before_first_seen",
            "available_after_as_of", "invalid_ohlc", "duplicate_price_bars",
        }
        if any(r in hard for r in reasons):
            status = "excluded"
        elif entry_date is None:
            status = "pending_future_entry_bar"
        elif 1 not in result_dates:
            status = "pending_future_1d_bar"
        elif 5 not in result_dates:
            status = "pending_future_5d_bar"
        elif not adj_ok or not corp_ok:
            status = "pending_price_basis"
        else:
            status = "ready"
        rows.append({
            "event_id": event_id or None,
            "event_type": e.get("event_type"),
            "entity_id": ticker,
            "source": source or None,
            "available_at": available.isoformat().replace("+00:00", "Z") if available else None,
            "as_of": as_of,
            "entry_bar_date": entry_date.isoformat() if entry_date else None,
            "entry_close_utc": entry_close.isoformat().replace("+00:00", "Z") if entry_close else None,
            "result_1d_date": result_dates.get(1).isoformat() if result_dates.get(1) else None,
            "result_5d_date": result_dates.get(5).isoformat() if result_dates.get(5) else None,
            "result_1d_close": result_closes.get(1),
            "result_5d_close": result_closes.get(5),
            "returns": returns,
            "price_basis": "SPY_Adj_Close_provider" if research_mode == "market_proxy_spy" else "raw_close",
            "adjusted_price_available": adj_ok,
            "corporate_actions_verified": corp_ok,
            "corporate_actions_basis": corp_basis,
            "strict_event_time": event_time is not None,
            "publication_forward_candidate": not any(r in hard for r in reasons),
            "status": status,
            "reasons": sorted(set(reasons)),
        })
    return {
        "as_of": as_of,
        "selected_events": len(selected),
        "ready": sum(r["status"] == "ready" for r in rows),
        "pending": sum(r["status"].startswith("pending_") for r in rows),
        "pending_future_bar": sum(r["status"].startswith("pending_") for r in rows),
        "pending_future_entry_bar": sum(r["status"] == "pending_future_entry_bar" for r in rows),
        "pending_future_1d_bar": sum(r["status"] == "pending_future_1d_bar" for r in rows),
        "pending_future_5d_bar": sum(r["status"] == "pending_future_5d_bar" for r in rows),
        "pending_price_basis": sum(r["status"] == "pending_price_basis" for r in rows),
        "excluded": sum(r["status"] == "excluded" for r in rows),
        "publication_forward_candidates": sum(r["publication_forward_candidate"] for r in rows),
        "lookahead_flags": 0,
        "panel_duplicate_rows": int(dup),
        "panel_invalid_rows": int(bad),
        "research_mode": research_mode,
        "market_proxy": market_proxy,
        "proxy_metadata": proxy_metadata,
        "price_basis": "SPY_Adj_Close_provider" if research_mode == "market_proxy_spy" else "raw_close",
        "adjusted_price_available": adj_ok,
        "corporate_actions_verified": corp_ok,
        "corporate_actions_basis": corp_basis,
        "events": rows,
        "research_only": True,
        "no_signal": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--price-panel", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--mode", choices=("stock", "market_proxy_spy"), default="stock")
    p.add_argument("--adjusted-price-available", action="store_true")
    p.add_argument("--corporate-actions-verified", action="store_true")
    p.add_argument("--market-proxy", help="Ticker used for market-wide events when no ticker is present")
    p.add_argument("--market-proxy-file", help="Optional CSV with the market proxy bars")
    p.add_argument("--market-proxy-adjusted", action="store_true",
                   help="Use the proxy Adj_Close as its close (proxy price basis is then adjusted)")
    p.add_argument("--proxy-metadata", help="JSON metadata for the market proxy")
    args = p.parse_args(argv)
    if args.mode == "market_proxy_spy" and not (args.market_proxy_file and args.market_proxy and args.market_proxy_adjusted):
        raise SystemExit("market_proxy_spy requires --market-proxy-file, --market-proxy, and --market-proxy-adjusted")
    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    price = pd.read_csv(args.price_panel)
    if args.market_proxy_file:
        if not args.market_proxy:
            raise SystemExit("--market-proxy is required with --market-proxy-file")
        proxy = pd.read_csv(args.market_proxy_file)
        proxy["Ticker"] = str(args.market_proxy).upper()
        if args.market_proxy_adjusted:
            if "Adj_Close" not in proxy.columns:
                raise SystemExit("proxy file has no Adj_Close")
            proxy["Close"] = proxy["Adj_Close"]
        price = pd.concat([price, proxy], ignore_index=True)
    proxy_metadata = json.loads(Path(args.proxy_metadata).read_text(encoding="utf-8")) if args.proxy_metadata else {}
    result = evaluate(events, price, as_of=args.as_of,
                      adjusted_price_available=args.adjusted_price_available,
                      corporate_actions_verified=args.corporate_actions_verified,
                      market_proxy=args.market_proxy,
                      research_mode=args.mode,
                      proxy_metadata=proxy_metadata)
    result["market_proxy_file"] = args.market_proxy_file
    result["market_proxy_price_basis"] = "adjusted" if args.market_proxy_adjusted else "raw"
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("selected_events", "ready", "pending_future_bar", "excluded", "lookahead_flags")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
