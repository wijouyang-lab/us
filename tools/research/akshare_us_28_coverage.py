"""Read-only AkShare availability/quality audit for the P5.1 28-company sample.

This is a research diagnostic, not a production market-data adapter. It records
coverage and raw source fields without persisting OHLCV rows or creating scores.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import importlib.metadata
import json
import math
from pathlib import Path
import re
import time
from typing import Any

import pandas as pd

SAMPLE_TICKERS = (
    "AAPL", "MSFT", "GOOGL", "NVDA", "CRM", "ADBE", "AMZN", "HD",
    "MCD", "NKE", "CAT", "HON", "UNP", "XOM", "CVX", "NEE", "DUK",
    "JNJ", "PFE", "UNH", "MRNA", "JPM", "BAC", "BRK.B", "MET", "PLD",
    "O", "RIVN",
)
QUOTE_FIELDS = ("代码", "最新价", "总市值", "市盈率")
HISTORY_FIELDS = ("日期", "开盘", "收盘", "最高", "最低", "成交量")


def normalize_ticker(value: Any) -> str:
    """Normalize vendor ticker suffixes, e.g. BRK.B and BRK-B -> BRKB."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def build_spot_index(spot: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Index Eastmoney quote rows by ticker suffix, preserving ambiguities."""
    missing = [name for name in QUOTE_FIELDS if name not in spot.columns]
    if missing:
        raise ValueError(f"AkShare spot response missing columns: {missing}")

    index: dict[str, list[dict[str, Any]]] = {}
    for row in spot.to_dict(orient="records"):
        vendor_code = str(row.get("代码", "")).strip()
        if not vendor_code:
            continue
        # Eastmoney code is exchange-prefix + ticker, e.g. 105.AAPL.
        suffix = vendor_code.split(".", 1)[1] if "." in vendor_code else vendor_code
        key = normalize_ticker(suffix)
        if not key:
            continue
        index.setdefault(key, []).append(
            {
                "vendor_symbol": vendor_code,
                "quote_price": _number(row.get("最新价")),
                "quote_market_cap_raw": _number(row.get("总市值")),
                "quote_pe_raw": _number(row.get("市盈率")),
                "display_name": str(row.get("名称", "")),
            }
        )
    return index


def assess_history(frame: pd.DataFrame | None) -> dict[str, Any]:
    """Calculate basic OHLCV integrity counters for one returned history frame."""
    if frame is None or frame.empty:
        return {
            "rows": 0,
            "date_min": None,
            "date_max": None,
            "missing_close": 0,
            "missing_ohlc": 0,
            "duplicates": 0,
            "zero_volume": 0,
            "invalid_ohlc": 0,
            "nonpositive_ohlc": 0,
            "quality_pass": False,
            "quality_status": "NO_HISTORY",
        }

    missing_fields = [name for name in HISTORY_FIELDS if name not in frame.columns]
    if missing_fields:
        return {
            "rows": int(len(frame)),
            "missing_fields": missing_fields,
            "quality_pass": False,
            "quality_status": "SCHEMA_MISMATCH",
        }

    dates = pd.to_datetime(frame["日期"], errors="coerce")
    duplicate_dates = int(dates.duplicated(keep=False).sum())
    valid_dates = dates.dropna()

    numeric = frame.loc[:, ["开盘", "收盘", "最高", "最低", "成交量"]].apply(
        pd.to_numeric, errors="coerce"
    )
    missing_close = int(numeric["收盘"].isna().sum())
    missing_ohlc = int(numeric[["开盘", "收盘", "最高", "最低"]].isna().any(axis=1).sum())
    nonpositive_ohlc = int(
        (numeric[["开盘", "收盘", "最高", "最低"]] <= 0).any(axis=1).sum()
    )

    open_ = numeric["开盘"]
    close = numeric["收盘"]
    high = numeric["最高"]
    low = numeric["最低"]
    bad = (
        (high < low)
        | (open_ < low - 1e-8)
        | (open_ > high + 1e-8)
        | (close < low - 1e-8)
        | (close > high + 1e-8)
    )
    invalid_ohlc = int(bad.fillna(False).sum())
    zero_volume = int((numeric["成交量"].fillna(0) == 0).sum())

    quality_pass = (
        len(frame) > 0
        and len(valid_dates) == len(frame)
        and duplicate_dates == 0
        and missing_close == 0
        and missing_ohlc == 0
        and nonpositive_ohlc == 0
        and invalid_ohlc == 0
    )
    return {
        "rows": int(len(frame)),
        "date_min": valid_dates.min().date().isoformat() if not valid_dates.empty else None,
        "date_max": valid_dates.max().date().isoformat() if not valid_dates.empty else None,
        "missing_close": missing_close,
        "missing_ohlc": missing_ohlc,
        "invalid_dates": int(dates.isna().sum()),
        "duplicates": duplicate_dates,
        "zero_volume": zero_volume,
        "invalid_ohlc": invalid_ohlc,
        "nonpositive_ohlc": nonpositive_ohlc,
        "quality_pass": bool(quality_pass),
        "quality_status": "DATA_OK_FOR_FURTHER_REVIEW" if quality_pass else "DATA_QUALITY_FAIL",
    }


def _compare_quote_to_last_close(quote: float | None, frame: pd.DataFrame | None) -> float | None:
    if quote is None or quote <= 0 or frame is None or frame.empty or "收盘" not in frame.columns:
        return None
    closes = pd.to_numeric(frame["收盘"], errors="coerce").dropna()
    close = _number(closes.iloc[-1]) if not closes.empty else None
    if close is None or close <= 0:
        return None
    return round((quote / close - 1.0) * 100.0, 4)


def run_audit(
    output_path: Path,
    start_date: str = "20160101",
    end_date: str | None = None,
    adjust: str = "qfq",
    sleep_seconds: float = 0.8,
) -> dict[str, Any]:
    """Fetch one spot universe and one daily history series per sample company."""
    import akshare as ak  # Import only for the live network audit.

    end_date = end_date or date.today().strftime("%Y%m%d")
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        version = importlib.metadata.version("akshare")
    except importlib.metadata.PackageNotFoundError:
        version = str(getattr(ak, "__version__", "unknown"))

    report: dict[str, Any] = {
        "metadata": {
            "generated_at_utc": generated_at,
            "akshare_version": version,
            "source": "AkShare stock_us_spot_em + stock_us_hist",
            "sample_scope": "P5.1_FIXED_28_COMPANIES",
            "tickers": list(SAMPLE_TICKERS),
            "start_date": start_date,
            "end_date": end_date,
            "history_period": "daily",
            "history_adjust": adjust,
            "spot_delay_minutes": 15,
            "notes": [
                "Read-only research diagnostic; no orders or production data writes.",
                "Spot quote is documented by AkShare source code as 15-minute delayed.",
                "Raw market-cap currency/unit is not assumed; validate before valuation use.",
                "Historical qfq output is not accepted as corporate-action/PIT proof by itself.",
                "No shares outstanding or forward EPS are inferred from price data.",
            ],
        },
        "summary": {},
        "companies": {},
    }

    try:
        spot = ak.stock_us_spot_em()
        spot_index = build_spot_index(spot)
    except Exception as exc:  # Preserve the failure as an artifact for diagnosis.
        report["metadata"]["spot_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        for ticker in SAMPLE_TICKERS:
            report["companies"][ticker] = {
                "ticker": ticker,
                "spot_status": "SPOT_FETCH_FAILED",
                "history_status": "NOT_ATTEMPTED",
            }
        report["summary"] = {
            "sample_count": len(SAMPLE_TICKERS),
            "spot_matched": 0,
            "quote_price_ready": 0,
            "history_nonempty": 0,
            "history_quality_pass": 0,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    matched = quote_ready = history_nonempty = history_quality_pass = 0
    for ticker in SAMPLE_TICKERS:
        candidates = spot_index.get(normalize_ticker(ticker), [])
        row: dict[str, Any] = {
            "ticker": ticker,
            "spot_match_count": len(candidates),
        }
        if len(candidates) == 0:
            row.update(
                {
                    "spot_status": "NOT_FOUND_IN_SPOT_UNIVERSE",
                    "history_status": "NOT_ATTEMPTED_NO_VENDOR_SYMBOL",
                }
            )
            report["companies"][ticker] = row
            continue
        if len(candidates) > 1:
            row.update(
                {
                    "spot_status": "AMBIGUOUS_SPOT_MATCH",
                    "candidate_symbols": [item["vendor_symbol"] for item in candidates],
                    "history_status": "NOT_ATTEMPTED_AMBIGUOUS_SYMBOL",
                }
            )
            report["companies"][ticker] = row
            continue

        quote = candidates[0]
        matched += 1
        row.update(quote)
        row["spot_status"] = (
            "QUOTE_PRICE_OK" if quote["quote_price"] is not None and quote["quote_price"] > 0
            else "QUOTE_PRICE_MISSING_OR_INVALID"
        )
        if row["spot_status"] == "QUOTE_PRICE_OK":
            quote_ready += 1

        try:
            history = ak.stock_us_hist(
                symbol=quote["vendor_symbol"],
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            quality = assess_history(history)
            row["history"] = quality
            row["history_status"] = quality["quality_status"]
            if quality.get("rows", 0) > 0:
                history_nonempty += 1
            if quality.get("quality_pass"):
                history_quality_pass += 1
            row["quote_vs_latest_history_close_pct"] = _compare_quote_to_last_close(
                quote["quote_price"], history
            )
        except Exception as exc:
            row["history_status"] = "HISTORY_FETCH_FAILED"
            row["history_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"

        report["companies"][ticker] = row
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    report["summary"] = {
        "sample_count": len(SAMPLE_TICKERS),
        "spot_matched": matched,
        "quote_price_ready": quote_ready,
        "history_nonempty": history_nonempty,
        "history_quality_pass": history_quality_pass,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/akshare-us-28-coverage.json"))
    parser.add_argument("--start-date", default="20160101")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--adjust", choices=("", "qfq", "hfq"), default="qfq")
    parser.add_argument("--sleep-seconds", type=float, default=0.8)
    args = parser.parse_args()
    if args.sleep_seconds < 0:
        parser.error("--sleep-seconds must be >= 0")
    try:
        report = run_audit(
            output_path=args.output,
            start_date=args.start_date,
            end_date=args.end_date,
            adjust=args.adjust,
            sleep_seconds=args.sleep_seconds,
        )
    except ImportError as exc:
        print(f"AkShare dependency unavailable: {exc}")
        return 2
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    print(f"report={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
