#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CPI / 核心CPI 显示缺陷的回归测试（P1）。

背景
----
`macro.economic` 里 CPI 一度显示为 ``334.98%``（用户看到「通胀率 300%+」）。
根因：上游备用链 FRED → BLS API 中，FRED 失败后 BLS API 返回的是 CPI **指数点位**
（CUUR0000SA0 ≈ 334.98），同比（yoy）只在 `_fetch_bls_yoy_from_web()` 成功时才有。
`_build_macro_payload` 原逻辑把「无 yoy」当成「利率/比率类」，于是把指数点位
格式化成百分数 ``334.98%``。

修复
----
1. BLS API 兜底路径（`get_us_economic_data`）：值超出通胀类合理区间 0–15 时
   打标记 `is_index_level = True`；
2. `_build_macro_payload`：识别指数点位（标记 **或** 区间形态），展示为
   「指数 334.98」，绝不加 ``%``。

覆盖
----
1. 无 yoy 的 CPI 指数点位 → 「指数 334.98」（不是「334.98%」）
2. 核心CPI 同上
3. 有 yoy 的 CPI → 仍是百分比（区间内）
4. 其它指标（失业率 / 国债 / 区间内的通胀类）不受影响
5. `is_index_level` 标记优先于 yoy 判断
6. 0–15 区间边界行为
7. `_looks_like_index_level` 助手函数本身（含非通胀类/None/非数字输入）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 复用 test_macro_panel.py 中已经验证过的 scan.py 中性化加载器：单一实现，
# 避免复制一份后两处漂移 —— 尤其是 update_version_marker 的写盘中性化，
# 复制出错会重写被跟踪文件 scan_version.txt。
from test_macro_panel import scan  # noqa: E402


def _economic_of(economic_structured):
    """跑一次构造器，按 indicator 名索引返回。"""
    economic, _speakers = scan._build_macro_payload(economic_structured, None)
    return {e["indicator"]: e for e in economic}


# ------------------------------------------------------- 1/2. 无 yoy → 展示为指数
def test_cpi_without_yoy_shows_index_label():
    """BLS 兜底：无 yoy、value 是指数点位 → 「指数 334.98」，绝不是「334.98%」。

    这条 item **不带** is_index_level 标记，走的是构造器的「区间形态」兜底分支。
    """
    got = _economic_of({"CPI指数": {"value": 334.98, "prev": 333.92,
                                    "date": "2026-08-01", "source": "BLS API"}})
    assert got["CPI"]["value"] == "指数 334.98"
    assert got["CPI"]["prev"] == "指数 333.92"
    assert "%" not in got["CPI"]["value"]
    assert got["CPI"]["source"] == "BLS API"


def test_core_cpi_without_yoy_shows_index_label():
    """核心CPI 同上（带源头标记）。"""
    got = _economic_of({"核心CPI指数": {"value": 337.76, "prev": 336.79,
                                       "date": "2026-08-01", "source": "BLS API",
                                       "is_index_level": True}})
    assert got["核心CPI"]["value"] == "指数 337.76"
    assert got["核心CPI"]["prev"] == "指数 336.79"
    assert "%" not in got["核心CPI"]["value"]


# ------------------------------------------------------------ 3. 有 yoy → 百分比
def test_cpi_with_yoy_shows_pct():
    """FRED（或 BLS+网页）拿到同比时，仍按百分比展示；prev 是上一期指数故置 None。"""
    got = _economic_of({"CPI指数": {"value": 334.98, "prev": 333.92, "yoy": 3.2,
                                    "date": "2026-08-01", "source": "FRED"}})
    assert got["CPI"]["value"] == "3.20%"
    assert got["CPI"]["prev"] is None


# ------------------------------------------------------- 4. 其它指标不受影响
def test_other_indicators_unaffected():
    """失业率 / 国债（非通胀类）与区间内的核心PCE 都保持原逻辑。"""
    got = _economic_of({
        "失业率": {"value": 4.2, "prev": 4.1, "date": "2026-09-01", "source": "BLS API"},
        "10Y国债": {"value": 5.24, "prev": 5.24, "date": "2026-10-12", "source": "Yahoo Finance"},
        "核心PCE指数": {"value": 3.0, "date": "August 2026",
                        "source": "BEA 官方网页", "yoy": 3.0},
    })
    assert got["失业率"]["value"] == "4.20%"
    assert got["失业率"]["prev"] == "4.10%"
    assert got["10Y国债"]["value"] == "5.24%"
    assert got["10Y国债"]["prev"] == "5.24%"
    assert got["核心PCE"]["value"] == "3.00%"


# ------------------------------------------------------- 5. 标记优先于 yoy 判断
def test_is_index_level_flag_respected():
    """is_index_level=True 时优先于 yoy 判断（标记来自源头，语义更强）。"""
    got = _economic_of({"CPI指数": {"value": 334.98, "prev": 333.92, "yoy": 3.2,
                                    "is_index_level": True, "source": "BLS API"}})
    assert got["CPI"]["value"] == "指数 334.98"
    assert got["CPI"]["prev"] == "指数 333.92"


def test_index_without_prev_is_none():
    """指数点位缺 prev 时写 None（前端按既有约定渲染为「—」），不写伪值。"""
    got = _economic_of({"CPI指数": {"value": 334.98, "source": "BLS API"}})
    assert got["CPI"]["value"] == "指数 334.98"
    assert got["CPI"]["prev"] is None


# ------------------------------------------------------------ 6. 区间边界行为
def test_index_range_boundary():
    """0–15 边界：区间内按百分比，越界按指数。"""
    assert _economic_of({"核心PCE指数": {"value": 15.0, "source": "BEA"}})["核心PCE"]["value"] == "15.00%"
    assert _economic_of({"核心PCE指数": {"value": 15.01, "source": "BEA"}})["核心PCE"]["value"] == "指数 15.01"
    assert _economic_of({"核心PCE指数": {"value": 0.0, "source": "BEA"}})["核心PCE"]["value"] == "0.00%"
    assert _economic_of({"核心PCE指数": {"value": -0.5, "source": "BEA"}})["核心PCE"]["value"] == "指数 -0.50"


# ------------------------------------------------------------ 7. 助手函数本身
def test_looks_like_index_level_helper():
    """区间判定助手：只对通胀类生效；None/非数字安全返回 False。"""
    assert scan._looks_like_index_level("CPI指数", 334.98) is True
    assert scan._looks_like_index_level("CPI指数", 3.2) is False
    assert scan._looks_like_index_level("核心CPI指数", 337.76) is True
    assert scan._looks_like_index_level("核心PCE指数", 3.0) is False
    # 非通胀类一律不判定 —— 失业率 4.2 落在通胀区间内也必须是 False
    assert scan._looks_like_index_level("失业率", 334.98) is False
    assert scan._looks_like_index_level("10Y国债", 5.24) is False
    # 脏输入不抛异常
    assert scan._looks_like_index_level("CPI指数", None) is False
    assert scan._looks_like_index_level("CPI指数", "") is False
    assert scan._looks_like_index_level("CPI指数", "abc") is False
