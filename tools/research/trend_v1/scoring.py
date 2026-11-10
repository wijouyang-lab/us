"""Transparent four-group trend score and cross-sectional ranking."""
from __future__ import annotations

import numpy as np
import pandas as pd

TREND = ["Mom20", "Mom60", "Mom120", "CloseToMA50", "MA50ToMA200"]
RS = ["Rel20", "Rel60", "Rel120"]
STABILITY = ["NegVol60", "DD60"]
EFFICIENCY = ["RiskEff20"]


def _pct(s: pd.Series) -> pd.Series:
    return s.rank(method="average", pct=True)


def score_snapshot(snap: pd.DataFrame) -> pd.DataFrame:
    d = snap.copy()
    d["CloseToMA50"] = d.Close / d.MA50 - 1
    d["MA50ToMA200"] = d.MA50 / d.MA200 - 1
    d["NegVol60"] = -d.Vol60
    # Every required component must be present; no neutral fill.
    required = TREND + RS + STABILITY + EFFICIENCY
    if d[required].isna().any(axis=1).any():
        d.loc[d[required].isna().any(axis=1), required] = np.nan
    for c in required:
        d[f"P_{c}"] = _pct(d[c])
    d["TrendScore"] = d[[f"P_{c}" for c in TREND]].mean(axis=1)
    d["RelStrengthScore"] = d[[f"P_{c}" for c in RS]].mean(axis=1)
    d["StabilityScore"] = d[[f"P_{c}" for c in STABILITY]].mean(axis=1)
    d["EfficiencyScore"] = d[[f"P_{c}" for c in EFFICIENCY]].mean(axis=1)
    d["Score"] = 0.25 * (d.TrendScore + d.RelStrengthScore + d.StabilityScore + d.EfficiencyScore)
    d.loc[d[required].isna().any(axis=1), "Score"] = np.nan
    d["rank"] = d.Score.rank(method="first", ascending=False)
    return d.sort_values(["rank", "Ticker"], na_position="last").reset_index(drop=True)
