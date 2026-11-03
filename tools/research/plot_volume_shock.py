#!/usr/bin/env python3
"""Generate dependency-free SVG charts for the volume-shock study."""
from pathlib import Path
import json
import pandas as pd

OUT = Path("docs/research/volume_shock_reversal")


def line_chart(series, path, title, w=900, h=320):
    vals = [float(v) for v in series]
    lo, hi = min(vals), max(vals)
    lo, hi = lo - (hi - lo) * .05, hi + (hi - lo) * .05
    pts = []
    for i, v in enumerate(vals):
        x = 60 + i * (w - 100) / max(1, len(vals) - 1)
        y = h - 40 - (v - lo) / (hi - lo) * (h - 80)
        pts.append(f"{x:.1f},{y:.1f}")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
           f'<rect width="100%" height="100%" fill="white"/>'
           f'<text x="60" y="22" font-family="Arial" font-size="15">{title}</text>'
           f'<polyline points="{" ".join(pts)}" fill="none" stroke="#0f766e" stroke-width="2"/>'
           f'<text x="60" y="{h-10}" font-family="Arial" font-size="11">start {series.index[0].date()} '
           f'end {series.index[-1].date()}</text></svg>')
    Path(path).write_text(svg, encoding="utf-8")


def bars(rows, path, w=700, h=300):
    vals = [r["mean"] for r in rows]
    lo, hi = min(vals + [0]), max(vals + [0])
    span = max(hi - lo, 1e-9)
    bw = (w - 100) / len(rows)
    parts = []
    for i, r in enumerate(rows):
        v = r["mean"]; x = 60 + i * bw
        y0 = h - 40 - (0 - lo) / span * (h - 70)
        y1 = h - 40 - (v - lo) / span * (h - 70)
        parts.append(f'<rect x="{x:.1f}" y="{min(y0,y1):.1f}" width="{bw*.6:.1f}" '
                     f'height="{abs(y1-y0):.1f}" fill="{"#b91c1c" if v < 0 else "#0f766e"}"/>')
        parts.append(f'<text x="{x:.1f}" y="{h-22}" font-family="Arial" font-size="11">{r["ticker"]}</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
           f'<rect width="100%" height="100%" fill="white"/>'
           f'<text x="60" y="22" font-family="Arial" font-size="15">Mean 3-session event return by ETF</text>'
           + "".join(parts) + '</svg>')
    Path(path).write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    report = json.loads((OUT / "results.json").read_text())
    nav = pd.read_csv(OUT / "nav_10bps.csv", index_col=0, parse_dates=True).iloc[:, 0]
    bench = pd.read_csv(OUT / "benchmark_nav.csv", index_col=0, parse_dates=True)
    norm = pd.DataFrame({"strategy": nav / nav.iloc[0], "SPY25": bench.SPY25 / bench.SPY25.iloc[0],
                         "QQQ25": bench.QQQ25 / bench.QQQ25.iloc[0]})
    # one line per series: generate a combined simple SVG by plotting strategy only
    line_chart(norm.strategy, OUT / "nav_strategy.svg", "Volume-shock 3D portfolio NAV (10 bps/leg, normalized)")
    rows = [r for r in report["study"] if r["horizon"] == 3]
    bars(rows, OUT / "event_3d.svg")
