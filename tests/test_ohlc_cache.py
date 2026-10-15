#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6mo OHLC 请求级缓存 _download_ohlc_6mo 的行为测试（mock yf，不联网）。"""
import ast
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_SRC = (REPO / "review.py").read_text(encoding="utf-8")


def _load(cache, yf_stub):
    """ast 抽取 _download_ohlc_6mo，注入受控的 _OHLC_6MO_CACHE 与 yf。"""
    for node in ast.parse(_SRC).body:
        if isinstance(node, ast.FunctionDef) and node.name == "_download_ohlc_6mo":
            ns = {"yf": yf_stub, "_OHLC_6MO_CACHE": cache}
            exec(ast.get_source_segment(_SRC, node), ns)
            return ns["_download_ohlc_6mo"]
    raise AssertionError("_download_ohlc_6mo not found in review.py")


def _df(vals):
    return pd.DataFrame({"Open": vals, "High": vals, "Low": vals, "Close": vals},
                        index=pd.date_range("2026-01-01", periods=len(vals)))


class _YF:
    def __init__(self, result):
        self.calls = []
        self._result = result

    def download(self, ticker, **kw):
        self.calls.append((ticker, kw))
        if callable(self._result):
            return self._result(ticker)
        return self._result


def test_second_call_uses_cache():
    yf = _YF(_df([1.0, 2.0]))
    cache = {}
    f = _load(cache, yf)
    a = f("ADSK")
    b = f("ADSK")
    assert len(yf.calls) == 1, "同 ticker 第二次仍触发下载"
    assert list(a["Close"]) == list(b["Close"])


def test_cached_frame_is_bitexact():
    yf = _YF(_df([3.0, 4.0, 5.0]))
    f = _load({}, yf)
    a = f("ADSK")
    b = f("ADSK")
    pd.testing.assert_frame_equal(a, b)


def test_empty_result_not_cached():
    yf = _YF(None)
    cache = {}
    f = _load(cache, yf)
    assert f("ADSK") is None
    assert f("ADSK") is None
    assert len(yf.calls) == 2, "空结果被缓存了（应每次重试）"
    assert cache == {}


def test_downstream_mutation_does_not_pollute_cache():
    yf = _YF(_df([1.0, 2.0]))
    cache = {}
    f = _load(cache, yf)
    a = f("ADSK")
    a.loc[a.index[0], "Close"] = 999.0
    b = f("ADSK")
    assert b.loc[b.index[0], "Close"] == 1.0, "下游 mutate 污染了缓存"
    assert len(yf.calls) == 1


def test_different_tickers_download_separately():
    yf = _YF(lambda tk: _df([1.0, 2.0]))
    cache = {}
    f = _load(cache, yf)
    f("ADSK")
    f("KR")
    f("ADSK")
    assert [c[0] for c in yf.calls] == ["ADSK", "KR"]
    assert set(cache) == {"ADSK", "KR"}


def test_download_params_unchanged():
    yf = _YF(_df([1.0]))
    f = _load({}, yf)
    f("ADSK")
    _, kw = yf.calls[0]
    assert kw.get("period") == "6mo"
    assert kw.get("auto_adjust") is True
    assert kw.get("threads") is False
