# -*- coding: utf-8 -*-
"""回归：只有一只 ticker 的 pending 文件也必须能解出 OHLC。

生产事故（2026-10-22 → 10-24 连续 3 次 review 失败）：
  - us_stocks_pending_20261021.csv 只有 BX 一行
  - us_stocks_pending_20261022.csv 只有 DHR 一行
  - 日志：⚠️ 无法获取 BX OHLC → ✅ 成功获得 0 / 1 → [PENDING_INCOMPLETE_OHLC] exit 1

根因：review.extract_single_ticker_df 用 ticker_count == 1 判断"yf.download 返回扁平列"，
而 yfinance>=1.0 即使只请求一只 ticker 也返回 MultiIndex（('BX','Open')…）。
于是 "Open" not in sub.columns → 空 DataFrame → 该 pending 文件永远缺 Open/Close。

这些测试只抽取 review.py 里的纯函数（review.py 顶层有网络/落盘副作用，不能直接 import）。
"""

import ast
from pathlib import Path

import pandas as pd
import pytest

SOURCE = Path(__file__).resolve().parents[1] / "review.py"

TARGET_DATE = "2026-10-21"
FUNCS = (
    "extract_single_ticker_df",
    "download_ohlc_safe",
    "_normalize_market_dates",
    "get_exact_date_ohlc",
)


def _load():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name in FUNCS]
    assert len(nodes) == len(FUNCS), [n.name for n in nodes]
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {
        "pd": pd,
        "US_TZ": "America/New_York",
        "normalize_ticker_text": lambda v: str(v or "").strip().upper(),
        "safe_float": lambda v, default=None: (
            float(v) if v not in (None, "", "None") else default
        ),
    }
    exec(compile(module, "<review-ohlc>", "exec"), ns)
    return ns


def _multi_frame(tickers, dates, layout="ticker_first"):
    """构造 yf.download 的两种 MultiIndex 形态（ticker 在 level 0 / level 1）。"""
    fields = ["Open", "High", "Low", "Close"]
    index = pd.DatetimeIndex([pd.Timestamp(d) for d in dates],
                             name="Date", tz="America/New_York")
    parts = []
    for i, _ticker in enumerate(tickers):
        rows = [[100.0 + i + j, 101.0 + i + j, 99.0 + i + j, 100.5 + i + j]
                for j in range(len(index))]
        parts.append(pd.DataFrame(rows, index=index, columns=fields))
    frame = pd.concat(parts, axis=1, keys=list(tickers))
    if layout == "column_first":
        frame = frame.swaplevel(0, 1, axis=1).sort_index(axis=1)
    elif layout != "ticker_first":
        raise AssertionError(layout)
    return frame


class _FakeYF:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    def download(self, tickers, **kwargs):
        self.calls.append({"tickers": list(tickers), "kwargs": kwargs})
        return self.frame


@pytest.mark.parametrize("layout", ["ticker_first", "column_first"])
def test_single_ticker_multiindex_is_parsed(layout):
    """单只 ticker 的 MultiIndex 列必须解析出 Open/Close（旧实现返回空 → review 失败）。"""
    ns = _load()
    frame = _multi_frame(["BX"], [TARGET_DATE], layout=layout)
    ns["yf"] = _FakeYF(frame)

    hist, latest = ns["download_ohlc_safe"](["BX"], period="10d")

    assert latest["BX"]["open"] == pytest.approx(100.0)
    assert latest["BX"]["close"] == pytest.approx(100.5)

    exact = ns["get_exact_date_ohlc"](hist, "BX", TARGET_DATE)
    assert exact is not None
    assert exact["open"] == pytest.approx(100.0)
    assert exact["close"] == pytest.approx(100.5)


def test_single_ticker_flat_columns_still_supported():
    """兼容扁平列（旧版 yfinance / Ticker.history 形态）。"""
    ns = _load()
    index = pd.DatetimeIndex([pd.Timestamp(TARGET_DATE)], name="Date")
    frame = pd.DataFrame(
        [[100.0, 101.0, 99.0, 100.5]],
        index=index,
        columns=["Open", "High", "Low", "Close"],
    )
    ns["yf"] = _FakeYF(frame)

    _hist, latest = ns["download_ohlc_safe"](["DHR"], period="10d")

    assert latest["DHR"]["open"] == pytest.approx(100.0)


def test_two_tickers_still_parsed():
    """批量请求（>1 只）不得回归。"""
    ns = _load()
    frame = _multi_frame(["BX", "DHR"], [TARGET_DATE])
    ns["yf"] = _FakeYF(frame)

    hist, latest = ns["download_ohlc_safe"](["BX", "DHR"], period="10d")

    assert set(latest) == {"BX", "DHR"}
    assert set(hist["Ticker"]) == {"BX", "DHR"}


def test_ticker_absent_from_frame_is_empty_not_crash():
    ns = _load()
    frame = _multi_frame(["DHR"], [TARGET_DATE])
    ns["yf"] = _FakeYF(frame)

    hist, latest = ns["download_ohlc_safe"](["BX"], period="10d")

    assert latest == {}
    assert ns["get_exact_date_ohlc"](hist, "BX", TARGET_DATE) is None
