"""Read-only AkShare US 28-company coverage and input audit (P5.2).

No production writes. Fetches spot + daily qfq/raw history, then checks basic
integrity and cross-checks current market cap against SEC shares (when supplied).
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
COL_CODE = "\u4ee3\u7801"
COL_NAME = "\u540d\u79f0"
COL_PRICE = "\u6700\u65b0\u4ef7"
COL_MARKET_CAP = "\u603b\u5e02\u503c"
COL_PE = "\u5e02\u76c8\u7387"
COL_DATE = "\u65e5\u671f"
COL_OPEN = "\u5f00\u76d8"
COL_CLOSE = "\u6536\u76d8"
COL_HIGH = "\u6700\u9ad8"
COL_LOW = "\u6700\u4f4e"
COL_VOLUME = "\u6210\u4ea4\u91cf"
HISTORY_FIELDS = (COL_DATE, COL_OPEN, COL_CLOSE, COL_HIGH, COL_LOW, COL_VOLUME)


def normalize_ticker(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def build_spot_index(spot: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    required = (COL_CODE, COL_PRICE, COL_MARKET_CAP, COL_PE)
    missing = [name for name in required if name not in spot.columns]
    if missing:
        raise ValueError(f"AkShare spot response missing columns: {missing}")
    index: dict[str, list[dict[str, Any]]] = {}
    for row in spot.to_dict(orient="records"):
        vendor_code = str(row.get(COL_CODE, "")).strip()
        if not vendor_code:
            continue
        suffix = vendor_code.split(".", 1)[1] if "." in vendor_code else vendor_code
        key = normalize_ticker(suffix)
        if not key:
            continue
        index.setdefault(key, []).append({
            "vendor_symbol": vendor_code,
            "quote_price": _number(row.get(COL_PRICE)),
            "quote_market_cap_raw": _number(row.get(COL_MARKET_CAP)),
            "quote_pe_raw": _number(row.get(COL_PE)),
            "display_name": str(row.get(COL_NAME, "")),
        })
    return index


def assess_history(frame: pd.DataFrame | None) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {"rows": 0, "date_min": None, "date_max": None, "missing_close": 0,
                "missing_ohlc": 0, "duplicates": 0, "zero_volume": 0,
                "invalid_ohlc": 0, "nonpositive_ohlc": 0, "quality_pass": False,
                "quality_status": "NO_HISTORY"}
    missing_fields = [name for name in HISTORY_FIELDS if name not in frame.columns]
    if missing_fields:
        return {"rows": int(len(frame)), "missing_fields": missing_fields,
                "quality_pass": False, "quality_status": "SCHEMA_MISMATCH"}
    dates = pd.to_datetime(frame[COL_DATE], errors="coerce")
    duplicate_dates = int(dates.duplicated(keep=False).sum())
    valid_dates = dates.dropna()
    numeric = frame.loc[:, [COL_OPEN, COL_CLOSE, COL_HIGH, COL_LOW, COL_VOLUME]].apply(
        pd.to_numeric, errors="coerce")
    missing_close = int(numeric[COL_CLOSE].isna().sum())
    missing_ohlc = int(numeric[[COL_OPEN, COL_CLOSE, COL_HIGH, COL_LOW]].isna().any(axis=1).sum())
    nonpositive_ohlc = int((numeric[[COL_OPEN, COL_CLOSE, COL_HIGH, COL_LOW]] <= 0).any(axis=1).sum())
    bad = ((numeric[COL_HIGH] < numeric[COL_LOW])
           | (numeric[COL_OPEN] < numeric[COL_LOW] - 1e-8)
           | (numeric[COL_OPEN] > numeric[COL_HIGH] + 1e-8)
           | (numeric[COL_CLOSE] < numeric[COL_LOW] - 1e-8)
           | (numeric[COL_CLOSE] > numeric[COL_HIGH] + 1e-8))
    invalid_ohlc = int(bad.fillna(False).sum())
    zero_volume = int((numeric[COL_VOLUME].fillna(0) == 0).sum())
    quality_pass = (len(valid_dates) == len(frame) and duplicate_dates == 0
                    and missing_close == 0 and missing_ohlc == 0
                    and nonpositive_ohlc == 0 and invalid_ohlc == 0)
    return {"rows": int(len(frame)),
            "date_min": valid_dates.min().date().isoformat() if not valid_dates.empty else None,
            "date_max": valid_dates.max().date().isoformat() if not valid_dates.empty else None,
            "missing_close": missing_close, "missing_ohlc": missing_ohlc,
            "invalid_dates": int(dates.isna().sum()), "duplicates": duplicate_dates,
            "zero_volume": zero_volume, "invalid_ohlc": invalid_ohlc,
            "nonpositive_ohlc": nonpositive_ohlc, "quality_pass": bool(quality_pass),
            "quality_status": "DATA_QUALITY_PASS" if quality_pass else "DATA_QUALITY_FAIL"}


def _compare_quote_to_close(quote: float | None, frame: pd.DataFrame | None):
    if quote is None or quote <= 0 or frame is None or frame.empty or COL_CLOSE not in frame.columns:
        return None
    closes = pd.to_numeric(frame[COL_CLOSE], errors="coerce").dropna()
    close = _number(closes.iloc[-1]) if not closes.empty else None
    if close is None or close <= 0: return None
    return round((quote / close - 1.0) * 100.0, 4)


def _shares_check(quote_price: float | None, raw_cap: float | None, shares_doc: dict | None) -> dict:
    if not shares_doc or shares_doc.get("status") != "AVAILABLE":
        return {"value_input_ready": False, "status": "SHARES_DISCLOSURE_MISSING"}
    shares = _number(shares_doc.get("shares"))
    period = shares_doc.get("period_end")
    if quote_price is None or quote_price <= 0 or shares is None or shares <= 0:
        return {"value_input_ready": False, "status": "PRICE_OR_SHARES_INVALID"}
    age_days = None
    if period:
        try: age_days = (date.today() - date.fromisoformat(period)).days
        except ValueError: age_days = None
    estimated_cap = quote_price * shares
    unit_factor = None; ratio = None
    for factor in (1, 1e3, 1e6, 1e9):
        candidate = raw_cap / (estimated_cap * factor) if raw_cap and estimated_cap else None
        if candidate is not None and abs(candidate - 1.0) <= 0.10:
            unit_factor, ratio = factor, candidate
            break
    base = {"estimated_market_cap": estimated_cap, "akshare_market_cap_raw": raw_cap,
            "shares": shares, "shares_period_end": period, "shares_age_days": age_days}
    if ratio is None:
        return {"value_input_ready": False, "status": "MARKET_CAP_UNIT_OR_VALUE_MISMATCH", **base}
    if age_days is not None and age_days > 183:
        return {"value_input_ready": False, "status": "SHARES_NOT_CURRENT",
                "market_cap_unit_factor": unit_factor, "market_cap_ratio": ratio, **base}
    return {"value_input_ready": True, "status": "VALUE_INPUT_READY",
            "market_cap_unit_factor": unit_factor, "market_cap_ratio": ratio,
            "currency": "USD", "currency_status": "US_BOARD_CONVENTION",
            "shares_accession": shares_doc.get("accession"), "shares_form": shares_doc.get("form"), **base}


def run_audit(output_path: Path, start_date: str = "20160101", end_date: str | None = None,
              adjust: str = "qfq", sleep_seconds: float = 0.8,
              shares_path: Path | None = Path("data/research/sec_shares_outstanding_28.json"),
              raw_limit: int = 0) -> dict:
    import akshare as ak
    end_date = end_date or date.today().strftime("%Y%m%d")
    shares_doc = {}
    if shares_path and Path(shares_path).exists():
        shares_doc = json.loads(Path(shares_path).read_text(encoding="utf-8")).get("companies", {})
    try: version = importlib.metadata.version("akshare")
    except importlib.metadata.PackageNotFoundError: version = str(getattr(ak, "__version__", "unknown"))
    report = {"metadata": {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "akshare_version": version, "source": "AkShare stock_us_spot_em + stock_us_hist",
                "sample_scope": "P5.1_FIXED_28_COMPANIES", "tickers": list(SAMPLE_TICKERS),
                "start_date": start_date, "end_date": end_date, "history_adjust": adjust,
                "spot_delay_minutes": 15, "shares_source": str(shares_path) if shares_path else None,
                "notes": ["Read-only research diagnostic; no orders or production data writes.",
                          "Spot is 15-minute delayed per AkShare source.",
                          "Market-cap unit is inferred only when it matches SEC shares within 10%.",
                          "Historical qfq is not accepted as PIT/corporate-action proof.",
                          "Forward EPS is not inferred from price data."]},
              "summary": {}, "companies": {}}
    try:
        spot = ak.stock_us_spot_em(); spot_index = build_spot_index(spot)
    except Exception as exc:
        report["metadata"]["spot_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        for t in SAMPLE_TICKERS:
            report["companies"][t] = {"ticker": t, "spot_status": "SPOT_FETCH_FAILED",
                                      "history_status": "NOT_ATTEMPTED"}
        report["summary"] = {"sample_count": 28, "spot_matched": 0, "quote_price_ready": 0,
                             "history_nonempty": 0, "history_quality_pass": 0,
                             "value_input_ready": 0, "trend_quality_ready": 0,
                             "garp_forward_eps_ready": 0, "score_ready": 0, "backtest_ready": 0}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    matched = quote_ready = hist_nonempty = hist_quality = value_ready = trend_ready = 0
    raw_attempted = raw_quality = 0
    for ticker_index, ticker in enumerate(SAMPLE_TICKERS):
        candidates = spot_index.get(normalize_ticker(ticker), [])
        row = {"ticker": ticker, "spot_match_count": len(candidates), "data_available": False,
               "data_quality_pass": False, "input_ready": False, "score_ready": False,
               "backtest_ready": False}
        if len(candidates) == 0:
            row.update({"spot_status": "NOT_FOUND_IN_SPOT_UNIVERSE",
                        "history_status": "NOT_ATTEMPTED_NO_VENDOR_SYMBOL"})
            report["companies"][ticker] = row; continue
        if len(candidates) > 1:
            row.update({"spot_status": "AMBIGUOUS_SPOT_MATCH",
                        "candidate_symbols": [x["vendor_symbol"] for x in candidates],
                        "history_status": "NOT_ATTEMPTED_AMBIGUOUS_SYMBOL"})
            report["companies"][ticker] = row; continue
        quote = candidates[0]; matched += 1; row.update(quote)
        row["spot_status"] = ("QUOTE_PRICE_OK" if quote["quote_price"] and quote["quote_price"] > 0
                              else "QUOTE_PRICE_MISSING_OR_INVALID")
        row["data_available"] = row["spot_status"] == "QUOTE_PRICE_OK"
        if row["data_available"]: quote_ready += 1
        qfq = None
        try:
            qfq = ak.stock_us_hist(symbol=quote["vendor_symbol"], period="daily",
                                   start_date=start_date, end_date=end_date, adjust=adjust)
            row["history_qfq"] = assess_history(qfq)
            row["history_qfq"]["requested_adjust"] = adjust
            if row["history_qfq"].get("rows", 0) > 0: hist_nonempty += 1
            if row["history_qfq"].get("quality_pass"): hist_quality += 1
            row["quote_vs_latest_history_close_pct"] = _compare_quote_to_close(quote["quote_price"], qfq)
        except Exception as exc:
            row["history_qfq"] = {"quality_status": "HISTORY_FETCH_FAILED",
                                  "error": f"{type(exc).__name__}: {str(exc)[:400]}"}
        if raw_limit and ticker_index < raw_limit:
            raw_attempted += 1
            try:
                raw = ak.stock_us_hist(symbol=quote["vendor_symbol"], period="daily",
                                       start_date=start_date, end_date=end_date, adjust="")
                row["history_raw"] = assess_history(raw)
                row["history_raw"]["requested_adjust"] = "unadjusted"
                row["raw_vs_qfq_status"] = ("BOTH_HISTORY_AVAILABLE" if qfq is not None and raw is not None
                                            else "PARTIAL_HISTORY")
                if row["history_raw"].get("quality_pass"): raw_quality += 1
            except Exception as exc:
                row["history_raw"] = {"quality_status": "HISTORY_FETCH_FAILED",
                                      "error": f"{type(exc).__name__}: {str(exc)[:400]}"}
        else:
            row["history_raw"] = {"quality_status": "RAW_COMPARISON_NOT_ATTEMPTED",
                                  "reason": "rate-limit-protection; qfq is primary; raw optional sample"}
            row["raw_vs_qfq_status"] = "RAW_NOT_ATTEMPTED"
        qok = bool(row.get("history_qfq", {}).get("quality_pass"))
        rok = bool(row.get("history_raw", {}).get("quality_pass"))
        row["data_quality_pass"] = bool(row["data_available"] and qok)
        row["raw_quality_pass"] = rok
        trend_ready += 1 if row["data_quality_pass"] else 0
        row["trend"] = {"status": "DATA_QUALITY_PASS_NOT_PIT" if row["data_quality_pass"]
                        else "DATA_QUALITY_FAIL",
                        "backtest_ready": False,
                        "blocker": "PIT membership coverage gate remains 95%/98%"}
        val = _shares_check(quote["quote_price"], quote["quote_market_cap_raw"], shares_doc.get(ticker))
        row["valuation"] = val
        row["input_ready"] = bool(val.get("value_input_ready"))
        row["value_input_ready"] = row["input_ready"]
        if row["input_ready"]: value_ready += 1
        row["garp"] = {"forward_eps_status": "DATA_BLOCKED", "peg_status": "DATA_BLOCKED",
                       "input_ready": False, "reason": "forward EPS estimates not available from free source"}
        row["score_ready"] = False
        row["backtest_ready"] = False
        row["history_status"] = row.get("history_qfq", {}).get("quality_status", "NO_HISTORY")
        report["companies"][ticker] = row
        if sleep_seconds > 0: time.sleep(sleep_seconds)

    report["summary"] = {"sample_count": len(SAMPLE_TICKERS), "spot_matched": matched,
        "quote_price_ready": quote_ready, "history_nonempty": hist_nonempty,
        "history_quality_pass": hist_quality, "history_raw_attempted": raw_attempted,
        "history_raw_quality_pass": raw_quality, "value_input_ready": value_ready,
        "trend_quality_ready": trend_ready, "garp_forward_eps_ready": 0,
        "score_ready": 0, "backtest_ready": 0}
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
    parser.add_argument("--shares", type=Path, default=Path("data/research/sec_shares_outstanding_28.json"))
    parser.add_argument("--raw-limit", type=int, default=0)
    args = parser.parse_args()
    if args.sleep_seconds < 0: parser.error("--sleep-seconds must be >= 0")
    try:
        report = run_audit(args.output, args.start_date, args.end_date, args.adjust,
                           args.sleep_seconds, args.shares, max(0, args.raw_limit))
    except ImportError as exc:
        print(f"AkShare dependency unavailable: {exc}"); return 2
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    print(f"report={args.output}"); return 0


if __name__ == "__main__":
    raise SystemExit(main())
