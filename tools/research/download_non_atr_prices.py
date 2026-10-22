"""Download public adjusted daily prices for point-in-time research backtests.

Uses Yahoo Finance via yfinance; this is research data, not an execution feed.
Writes Date,Ticker,Adj Close rows and fails if the output is empty or unusable.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


def load_universe(data_dir: Path) -> list[str]:
    tickers: set[str] = set()
    sources = [
        (data_dir / "sp500_components_history.csv", ("symbol",)),
        (data_dir / "nasdaq100_membership_history.csv", ("symbol",)),
        (data_dir / "dow30_membership_history.csv", ("symbol",)),
        (data_dir / "sp500_ticker_aliases.csv", ("old_ticker", "canonical_ticker")),
    ]
    for path, fields in sources:
        if not path.is_file():
            raise FileNotFoundError(f"Required membership input is missing: {path}")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            available = {str(name or "").strip().lower() for name in (reader.fieldnames or [])}
            for field in fields:
                if field not in available:
                    raise ValueError(f"{path} must contain column {field!r}")
            for row in reader:
                for field in fields:
                    value = str(row.get(field) or "").strip().upper()
                    if value and value not in {"NAN", "NONE"}:
                        tickers.add(value)
    # Yahoo Finance uses dashes for several share-class symbols.
    normalized = {ticker.replace(".", "-") for ticker in tickers}
    normalized.discard("")
    return sorted(normalized)


def download_prices(tickers: list[str], start: str, end: str, chunk_size: int = 30) -> pd.DataFrame:
    chunks: list[pd.DataFrame] = []
    failures: list[str] = []
    for offset in range(0, len(tickers), chunk_size):
        batch = tickers[offset : offset + chunk_size]
        try:
            data = yf.download(
                tickers=batch,
                start=start,
                end=end,
                interval="1d",
                auto_adjust=False,
                actions=False,
                group_by="column",
                threads=False,
                progress=False,
                timeout=30,
            )
        except Exception as exc:
            failures.append(f"{','.join(batch[:3])}: {type(exc).__name__}: {exc}")
            continue
        if data is None or data.empty:
            failures.append(f"{','.join(batch[:3])}: no rows returned")
            continue
        adjusted = data.get("Adj Close")
        if adjusted is None:
            # Single-ticker responses may be a flat column index in some yfinance versions.
            if len(batch) == 1 and "Adj Close" in data.columns:
                adjusted = data["Adj Close"].to_frame(name=batch[0])
            else:
                failures.append(f"{','.join(batch[:3])}: missing Adj Close column")
                continue
        if isinstance(adjusted, pd.Series):
            adjusted = adjusted.to_frame(name=batch[0])
        elif isinstance(adjusted.columns, pd.MultiIndex):
            adjusted.columns = [str(col[-1] if isinstance(col, tuple) else col) for col in adjusted.columns]
        adjusted.index = pd.to_datetime(adjusted.index, errors="coerce")
        long = adjusted.rename_axis("Date").stack(future_stack=True).rename("Adj Close").reset_index()
        long.columns = ["Date", "Ticker", "Adj Close"]
        long["Ticker"] = long["Ticker"].astype(str).str.upper()
        long["Adj Close"] = pd.to_numeric(long["Adj Close"], errors="coerce")
        long = long.dropna(subset=["Date", "Adj Close"])
        long = long[long["Adj Close"] > 0]
        if not long.empty:
            chunks.append(long)
        print(f"Downloaded batch {offset // chunk_size + 1}: {len(long)} usable ticker-session rows")
    if not chunks:
        detail = "; ".join(failures[:8])
        raise RuntimeError(f"No adjusted-price rows downloaded. Sample errors: {detail}")
    result = pd.concat(chunks, ignore_index=True)
    result["Date"] = pd.to_datetime(result["Date"]).dt.tz_localize(None)
    result = result.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"], keep="last")
    if result.empty or result["Ticker"].nunique() < 2:
        raise RuntimeError(f"Downloaded data is insufficient: {len(result)} rows, {result['Ticker'].nunique()} tickers")
    if failures:
        print(f"WARNING: {len(failures)} ticker batches had no usable data; sample: {'; '.join(failures[:5])}")
    return result[["Date", "Ticker", "Adj Close"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="tools/research/data")
    parser.add_argument("--output", default="research_price_history_sp500_10y.csv")
    parser.add_argument("--years", type=int, default=10)
    args = parser.parse_args()
    if args.years < 3:
        parser.error("--years must be at least 3 for meaningful out-of-sample testing")
    end = date.today() + timedelta(days=1)
    start = date(end.year - args.years, end.month, min(end.day, 28))
    universe = load_universe(Path(args.data_dir))
    print(f"Downloading {len(universe)} unique historical index/member and alias tickers from {start} to {end}")
    frame = download_prices(universe, start.isoformat(), end.isoformat())
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, date_format="%Y-%m-%d")
    print(f"Wrote {len(frame)} rows for {frame['Ticker'].nunique()} tickers to {output}")
    if len(frame) < 1000:
        raise SystemExit("Downloaded price history is unexpectedly small; refusing to run backtest")


if __name__ == "__main__":
    main()
