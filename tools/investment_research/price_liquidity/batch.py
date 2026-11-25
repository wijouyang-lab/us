#!/usr/bin/env python3
"""FS-1.1 resumable batch downloader with ticker validation and per-batch isolation."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[3]
UNIV = ROOT / "data/universe/selection_inputs/us_equities_current.csv"


def normalize(raw):
    import re
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "", "MISSING_TICKER"
    if not isinstance(raw, str):
        return "", "INVALID_TICKER_TYPE"
    s = raw.strip().upper()
    if not s:
        return "", "MISSING_TICKER"
    if not re.match(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$", s):
        return s, "INVALID_SYMBOL_FORMAT"
    return s, "VALID"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch", type=int, default=150)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    bdir = a.out / "batches"; bdir.mkdir(exist_ok=True)
    d = pd.read_csv(UNIV, dtype=str)
    d["ticker_raw"] = d["ticker"]
    norm = [normalize(x) for x in d.ticker]
    d["ticker"] = [x[0] for x in norm]; d["ticker_status"] = [x[1] for x in norm]
    d = d.drop_duplicates(["ticker"]).copy()
    valid = d[(d.ticker_status == "VALID") & d.security_type.isin(["COMMON", "ADR"])].drop_duplicates("ticker")
    if a.limit: valid = valid.head(a.limit)
    valid.to_csv(a.out / "download_universe.csv", index=False)
    done = set()
    if (a.out / "download_status.csv").exists():
        old = pd.read_csv(a.out / "download_status.csv", dtype=str)
        done = set(old[old.status == "SUCCESS"].ticker)
    yf.set_tz_cache_location(r"C:\Users\ouyan\Documents\deepseek-harness\default-workspace\_yf_tmp")
    status = []
    tick = valid.ticker.tolist()
    for bi in range(0, len(tick), a.batch):
        batch = [t for t in tick[bi:bi + a.batch] if t not in done]
        if not batch: continue
        ok = None
        for attempt in range(2):
            try:
                ok = yf.download(batch, period="6mo", interval="1d", group_by="ticker",
                                 progress=False, threads=True, auto_adjust=False, actions=False)
                break
            except Exception as e:
                if attempt == 1:
                    status.extend({"ticker": t, "status": "REQUEST_FAILED", "reason": type(e).__name__, "retries": attempt + 1} for t in batch)
                    continue
                time.sleep(2)
        if ok is None: continue
        frames = []
        for t in batch:
            try:
                x = ok[t] if isinstance(ok.columns, pd.MultiIndex) and t in ok.columns.get_level_values(0) else ok
                x = x.reset_index()
                ren = {"Date": "date", "Open": "raw_open", "High": "raw_high", "Low": "raw_low",
                       "Close": "raw_close", "Adj Close": "adjusted_close", "Volume": "raw_volume"}
                x = x.rename(columns={k: v for k, v in ren.items() if k in x.columns})
                if "date" not in x or len(x) < 1: raise ValueError("NO_ROWS")
                x["ticker"] = t
                frames.append(x[["ticker", "date", "raw_open", "raw_high", "raw_low", "raw_close", "adjusted_close", "raw_volume"]])
                status.append({"ticker": t, "status": "SUCCESS", "rows": len(x), "reason": "", "retries": 0})
            except Exception as e:
                status.append({"ticker": t, "status": "NO_DATA", "rows": 0, "reason": type(e).__name__, "retries": 0})
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(bdir / f"batch_{bi:05d}.csv.gz", index=False, compression="gzip")
        pd.DataFrame(status).drop_duplicates("ticker", keep="last").to_csv(a.out / "download_status.csv", index=False)
        print(f"batch {bi} done={sum(1 for s in status if s['status']=='SUCCESS')}", flush=True)
    # combine
    frames = [pd.read_csv(p) for p in sorted(bdir.glob("batch_*.csv.gz"))]
    if frames:
        allp = pd.concat(frames, ignore_index=True)
        allp["date"] = pd.to_datetime(allp.date, errors="coerce")
        allp = allp.dropna(subset=["date", "ticker"]).drop_duplicates(["ticker", "date"])
        allp["source"] = "yfinance"; allp["fetched_at"] = pd.Timestamp.utcnow().isoformat()
        allp.to_csv(a.out / "price_cache_v1.csv.gz", index=False, compression="gzip")
    final = pd.DataFrame(status).drop_duplicates("ticker", keep="last")
    final.to_csv(a.out / "download_status.csv", index=False)
    print(final.status.value_counts().to_dict(), len(final))


if __name__ == "__main__":
    main()


