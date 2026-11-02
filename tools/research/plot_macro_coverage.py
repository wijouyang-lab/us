#!/usr/bin/env python3
"""Coverage chart for macro event audit."""
import json
from pathlib import Path
import pandas as pd

OUT = Path("data/research/macro_event_response")
a = json.loads((OUT / "audit.json").read_text())
cov = a["audit"]["coverage_by_year"]
years = list(range(2007, 2027))
w, h = 1000, 360
bw = (w - 100) / len(years)
maxv = 12
parts = []
for i, y in enumerate(years):
    x = 60 + i * bw
    for j, fam in enumerate(("cpi", "empsit", "fomc")):
        v = cov[fam].get(str(y), 0)
        bh = v / maxv * (h - 90)
        color = {"cpi": "#0f766e", "empsit": "#b45309", "fomc": "#1d4ed8"}[fam]
        parts.append(f'<rect x="{x + j*8:.1f}" y="{h-45-bh:.1f}" width="6" height="{bh:.1f}" fill="{color}"/>')
    if y % 2 == 1:
        parts.append(f'<text x="{x:.1f}" y="{h-25}" font-family="Arial" font-size="9">{str(y)[2:]}</text>')
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
       f'<rect width="100%" height="100%" fill="white"/>'
       f'<text x="60" y="22" font-family="Arial" font-size="15">Official macro release coverage by year</text>'
       f'<text x="60" y="42" font-family="Arial" font-size="11">green CPI, orange Employment, blue FOMC; 12 max/year</text>'
       + "".join(parts) + '</svg>')
(OUT / "coverage.svg").write_text(svg, encoding="utf-8")
