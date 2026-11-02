# -*- coding: utf-8 -*-
"""SPY trend benchmark must emit cash events on bearish weeks."""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "research"))
from trend_v1.backtest_run import _spy_trend_events  # noqa: E402


def test_bearish_week_emits_empty_target():
    dates = pd.bdate_range("2020-01-01", periods=300)
    close = np.r_[np.linspace(100, 200, 250), np.linspace(200, 80, 50)]
    spy = pd.DataFrame({"Date": dates, "Open": close, "Close": close,
                        "Ticker": "SPY", "asset_class": "ETF"})
    ev = _spy_trend_events(spy)
    assert ev
    assert any(len(v) == 0 for v in ev.values())
