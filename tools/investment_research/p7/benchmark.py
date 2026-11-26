"""P7.1 benchmark NAV aligned to the shadow's official dates."""
from __future__ import annotations
import csv, json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

P7 = Path("data/universe/p7")
AS_OF = date(2026, 11, 5)
INITIAL = 50000.0


def read(p):
    b = p.read_bytes()[:2]
    with p.open(encoding="utf-16" if b in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    snap = read(P7 / "benchmark_snapshot.csv")
    by = defaultdict(list)
    for r in snap:
        if r["ticker"] in ("SPY", "QQQ", "IWM") and r["close"]:
            by[r["ticker"]].append((r["date"], float(r["close"])))
    nav = read(P7 / "shadow_nav.csv") if (P7 / "shadow_nav.csv").exists() else []
    dates = [r["date"] for r in nav if r.get("date")] or [AS_OF.isoformat()]
    rows = []
    for t in ("SPY", "QQQ", "IWM"):
        xs = sorted(by[t])
        if not xs: continue
        base = xs[0][1]
        prev = None
        for d in dates:
            candidates = [x for x in xs if x[0] <= d]
            if not candidates: continue
            close = candidates[-1][1]
            ret = (close / prev - 1) if prev else 0.0
            rows.append({"date": d, "ticker": t, "close": close, "daily_return": round(ret, 10),
                         "nav_50000": round(INITIAL * close / base, 4),
                         "status": "ALIGNED_TO_SHADOW_DATE"})
            prev = close
    # Equal-weight target is a reference, not a historical return.
    for d in dates:
        rows.append({"date": d, "ticker": "EQUAL_WEIGHT", "close": "", "daily_return": "",
                     "nav_50000": "", "status": "PENDING_TARGET_REFERENCE"})
    with (P7 / "benchmark_nav.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "as_of": AS_OF.isoformat(),
               "dates": dates, "rows": len(rows), "status": "DATE_ALIGNED_SNAPSHOT",
               "note": "No missing date is filled as zero return; equal-weight remains pending."}
    (P7 / "benchmark_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
