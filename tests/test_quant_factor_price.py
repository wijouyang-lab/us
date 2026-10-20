# -*- coding: utf-8 -*-
"""Persistent Price History Layer 纯函数回归测试（不依赖真实 Yahoo 网络）。"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_factor_price import (
    PRICE_HISTORY_COLUMNS,
    filter_completed_daily_bars,
    get_snapshot_tickers,
    load_price_history,
    price_map_from_history,
    update_price_history,
    upsert_price_history,
)
from quant_factor_backtest import forward_return_nd



def check(name, cond, detail=""):
    """断言：FAIL 时抛出 AssertionError（pytest 可捕获），同时保留打印。"""
    if cond:
        print(f"  [PASS] {name}")
        return True
    print(f"  [FAIL] {name}  {detail}")
    raise AssertionError(f"{name}  {detail}".strip())


def make_snapshot():
    return pd.DataFrame({
        "Scan_Date": ["2026-02-01", "2026-02-01", "2026-02-02", "2026-02-02"],
        "Technical_Date": ["2026-01-30", "2026-01-30", "2026-02-02", "2026-02-02"],
        "Ticker": ["AAA", "BBB", "AAA", "CCC"],  # 历史 universe = A B C
        "Name": ["A", "B", "A", "C"],
        "Price": ["100", "100", "105", "50"],
    })


def make_history_df():
    return pd.DataFrame([
        {"Date": "2026-01-30", "Ticker": "AAA", "Close": "100.0"},
        {"Date": "2026-01-30", "Ticker": "BBB", "Close": "100.0"},
    ], columns=PRICE_HISTORY_COLUMNS)


# ---- 1-4. upsert 幂等 / 去重 / 追加 / 不覆盖 ----
def test_upsert():
    existing = make_history_df()
    new = pd.DataFrame([
        {"Date": "2026-01-30", "Ticker": "AAA", "Close": "999.0"},  # 已存在 → 不覆盖
        {"Date": "2026-01-30", "Ticker": "BBB", "Close": "999.0"},  # 已存在 → 不覆盖
        {"Date": "2026-02-02", "Ticker": "AAA", "Close": "105.0"},  # 新日期 → 追加
        {"Date": "2026-02-02", "Ticker": "CCC", "Close": "50.0"},   # 新 ticker → 追加
    ], columns=PRICE_HISTORY_COLUMNS)
    merged = upsert_price_history(existing, new)
    check("历史记录不被覆盖", len(merged) == 4, f"got {len(merged)}")
    aaa_130 = merged[(merged["Date"] == "2026-01-30") & (merged["Ticker"] == "AAA")]["Close"].iloc[0]
    check("AAA 01-30 保持原值 100.0", aaa_130 == "100.0", f"got {aaa_130}")
    check("新 ticker CCC 追加", ((merged["Ticker"] == "CCC")).sum() == 1)
    # 幂等：再次 upsert 相同内容不增长
    merged2 = upsert_price_history(merged, new)
    check("重复记录不产生重复", len(merged2) == 4, f"got {len(merged2)}")
    check("无 duplicate key", merged2.duplicated(subset=["Date", "Ticker"]).sum() == 0)


def test_upsert_empty_existing():
    empty = pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)
    new = make_history_df()
    merged = upsert_price_history(empty, new)
    check("空历史 → 直接返回新数据", len(merged) == 2, f"got {len(merged)}")


# ---- 5-10. Forward Return 用 price history ----
def test_forward_from_history():
    # 构造完整交易日序列（跳过周末）
    idx = pd.bdate_range("2026-01-28", periods=30)
    closes = pd.Series([100.0 + i for i in range(30)], index=idx)
    # T = 2026-01-30（idx 中的第 3 个交易日）
    t_date = pd.Timestamp("2026-01-30")
    close_t = float(closes.loc[t_date])  # = 100 + 2 = 102

    r5 = forward_return_nd(closes, t_date, close_t, 5)
    # T 之后第 5 个交易日 = idx 中 t_date 位置 +5
    pos = closes.index.get_loc(t_date)
    expected5 = closes.iloc[pos + 5] / close_t - 1
    check("T+5 正确", r5 is not None and abs(r5 - expected5) < 1e-6, f"got {r5} exp {expected5}")

    r10 = forward_return_nd(closes, t_date, close_t, 10)
    expected10 = closes.iloc[pos + 10] / close_t - 1
    check("T+10 正确", r10 is not None and abs(r10 - expected10) < 1e-6, f"got {r10}")

    r20 = forward_return_nd(closes, t_date, close_t, 20)
    expected20 = closes.iloc[pos + 20] / close_t - 1
    check("T+20 正确", r20 is not None and abs(r20 - expected20) < 1e-6, f"got {r20}")


def test_weekend_not_trading_day():
    # 周末日期不是交易日：price series 用 bdate_range，含周五/周一
    idx = pd.bdate_range("2026-01-30", periods=10)  # 01-30 是周五
    closes = pd.Series([100.0] * 10, index=idx)
    # T = 周五 01-30，T+5 应是 5 个工作日后的周五，而不是 5 个日历日
    r5 = forward_return_nd(closes, pd.Timestamp("2026-01-30"), 100.0, 5)
    check("周末不误算为交易日", r5 is not None, f"got {r5}")
    # 验证 T+5 对应的是 idx[5]（跳过 01-31/02-01 周末）
    expected_pos = idx.get_loc(pd.Timestamp("2026-01-30")) + 5
    check("T+5 位置跳过周末", abs(closes.iloc[expected_pos] / 100.0 - 1 - r5) < 1e-9)


def test_missing_future_none():
    idx = pd.bdate_range("2026-02-20", periods=3)  # 只有 3 个交易日
    closes = pd.Series([100.0, 101.0, 102.0], index=idx)
    r5 = forward_return_nd(closes, idx[0], 100.0, 5)
    check("缺失未来交易日 → None", r5 is None, f"got {r5}")


# ---- 11. 不使用未来因子 ----
def test_no_future_factor():
    # price history 只存 Date/Ticker/Close，不存任何因子/Review/Exit 字段
    df = make_history_df()
    check("无因子/Review/Exit 列", not any(c in df.columns for c in ["RSI", "Quant", "Exit", "PnL", "Review"]))


# ---- 12. 重复运行一致 ----
def test_deterministic():
    existing = make_history_df()
    new = pd.DataFrame([{"Date": "2026-02-02", "Ticker": "AAA", "Close": "105.0"}], columns=PRICE_HISTORY_COLUMNS)
    m1 = upsert_price_history(existing, new)
    m2 = upsert_price_history(existing, new)
    pd.testing.assert_frame_equal(m1, m2)
    check("重复运行结果一致", True)


# ---- 13. 空 Snapshot ----
def test_empty_snapshot():
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "snap.csv")
    ph_path = os.path.join(tmp, "price_history.csv")

    # 无 snapshot
    r = update_price_history(snapshot_path=snap_path, price_history_path=ph_path)
    check("无 snapshot → NO_SNAPSHOT", r["status"] == "NO_SNAPSHOT", f"got {r['status']}")

    # 空 snapshot
    pd.DataFrame(columns=["Ticker"]).to_csv(snap_path, index=False)
    r2 = update_price_history(snapshot_path=snap_path, price_history_path=ph_path)
    check("空 snapshot → EMPTY_SNAPSHOT", r2["status"] == "EMPTY_SNAPSHOT", f"got {r2['status']}")


# ---- 14. 全候选池覆盖 ----
def test_full_universe():
    snap = make_snapshot()
    tickers = get_snapshot_tickers(snap)
    check("历史 universe 覆盖 A/B/C", tickers == ["AAA", "BBB", "CCC"], f"got {tickers}")


# ---- update_price_history 注入 fetch 的完整链路 ----
def test_update_with_injected_fetch():
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "snap.csv")
    ph_path = os.path.join(tmp, "price_history.csv")
    make_snapshot().to_csv(snap_path, index=False)

    def fake_fetch(tickers, start, end):
        rows = []
        for t in tickers:
            for d in ["2026-01-30", "2026-02-02"]:
                rows.append({"Date": d, "Ticker": t, "Close": "100.0"})
        return pd.DataFrame(rows, columns=PRICE_HISTORY_COLUMNS)

    r = update_price_history(snapshot_path=snap_path, price_history_path=ph_path, fetch_func=fake_fetch)
    check("update 返回 OK", r["status"] == "OK", f"got {r['status']}")
    check("unique_tickers = 3", r["unique_tickers"] == 3, f"got {r['unique_tickers']}")
    check("total_rows = 6", r["total_rows"] == 6, f"got {r['total_rows']}")
    df = load_price_history(ph_path)
    check("price_history 已写盘", len(df) == 6, f"got {len(df)}")

    # 第二次运行：注入同样的 fetch，应无重复（幂等）
    r2 = update_price_history(snapshot_path=snap_path, price_history_path=ph_path, fetch_func=fake_fetch)
    check("二次运行无重复", r2["total_rows"] == 6 and r2["new_rows"] == 0,
          f"total={r2['total_rows']} new={r2['new_rows']}")


# ---- price_map_from_history ----
def test_price_map():
    df = make_history_df()
    pm = price_map_from_history(df)
    check("price_map 有 AAA/BBB", set(pm.keys()) == {"AAA", "BBB"}, f"got {set(pm.keys())}")
    check("AAA 01-30 close=100", abs(float(pm["AAA"].iloc[0]) - 100.0) < 1e-9)


# ---- filter_completed_daily_bars ----
def test_filter_bars():
    # 构造含"未来未完成"日期的 bar（tz-aware UTC，与 yfinance 返回口径一致）
    idx = pd.DatetimeIndex(
        ["2026-01-30 20:00:00", "2026-02-02 20:00:00", "2026-02-03 20:00:00"],
        tz="UTC",
    )
    df = pd.DataFrame({"Close": [100.0, 101.0, 102.0]}, index=idx)
    # cutoff = 2026-02-02（美东），应剔除 02-03（UTC 20:00 = 美东 15:00，日期仍为 02-03）
    filtered = filter_completed_daily_bars(df, "2026-02-02")
    check("未完成 bar 被剔除", len(filtered) == 2, f"got {len(filtered)}")


# ---- OHLCV 补采（STEP）：schema + 写入 + 向后兼容 ----
def test_schema_has_ohlcv():
    expected = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"]
    check("PRICE_HISTORY_COLUMNS 扩到 OHLCV", PRICE_HISTORY_COLUMNS == expected, f"got {PRICE_HISTORY_COLUMNS}")
    check("Close 列名保留（兼容 Phase 2）", "Close" in PRICE_HISTORY_COLUMNS)


def test_update_writes_ohlcv():
    """注入 mock fetch（不联网）验证 OHLCV 正确落盘，Close 不变。"""
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "snap.csv")
    ph_path = os.path.join(tmp, "price_history.csv")
    make_snapshot().to_csv(snap_path, index=False)

    def fake_fetch(tickers, start, end):
        rows = []
        for t in tickers:
            for d in ["2026-01-30", "2026-02-02"]:
                rows.append({
                    "Date": d, "Ticker": t,
                    "Open": 99.0, "High": 101.0, "Low": 98.0,
                    "Close": 100.0, "Volume": 123456,
                })
        return pd.DataFrame(rows, columns=PRICE_HISTORY_COLUMNS)

    r = update_price_history(snapshot_path=snap_path, price_history_path=ph_path, fetch_func=fake_fetch)
    check("update OK (OHLCV)", r["status"] == "OK", f"got {r['status']}")
    df = load_price_history(ph_path)
    for col in ["Open", "High", "Low", "Volume"]:
        check(f"列 {col} 存在并落盘", col in df.columns)
    sample = df[(df["Date"] == "2026-01-30") & (df["Ticker"] == "AAA")].iloc[0]
    check("Open 已写入", abs(float(sample["Open"]) - 99.0) < 1e-9, f"got {sample['Open']}")
    check("High 已写入", abs(float(sample["High"]) - 101.0) < 1e-9)
    check("Low 已写入", abs(float(sample["Low"]) - 98.0) < 1e-9)
    check("Volume 已写入(int)", int(float(sample["Volume"])) == 123456, f"got {sample['Volume']}")
    check("Close 列名未变", "Close" in df.columns)
    check("Close 值不变", abs(float(sample["Close"]) - 100.0) < 1e-9)


def test_load_backward_compat_old_csv():
    """旧 4 列 CSV（仅 Date/Ticker/Close/schema_version）读入后自动补空 OHLCV，Close 保留。"""
    tmp = tempfile.mkdtemp()
    ph_path = os.path.join(tmp, "old.csv")
    pd.DataFrame([
        {"Date": "2026-01-30", "Ticker": "AAA", "Close": "100.0", "schema_version": "phase2b.v1"},
    ]).to_csv(ph_path, index=False)
    df = load_price_history(ph_path)
    for col in ["Open", "High", "Low", "Volume"]:
        check(f"旧 CSV 自动补空列 {col}", col in df.columns and df.iloc[0][col] == "")
    check("旧 CSV Close 保留", df.iloc[0]["Close"] == "100.0")


def main():
    _tests = [
        test_upsert,
        test_upsert_empty_existing,
        test_forward_from_history,
        test_weekend_not_trading_day,
        test_missing_future_none,
        test_no_future_factor,
        test_deterministic,
        test_empty_snapshot,
        test_full_universe,
        test_update_with_injected_fetch,
        test_price_map,
        test_filter_bars,
        test_schema_has_ohlcv,
        test_update_writes_ohlcv,
        test_load_backward_compat_old_csv,
    ]
    _failed = 0
    for _t in _tests:
        try:
            _t()
        except Exception as _e:
            _failed += 1
            print(f"  [FAIL] {_t.__name__}: {_e}")
    print(f"\n结果：通过 {len(_tests) - _failed} / {len(_tests)}")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
