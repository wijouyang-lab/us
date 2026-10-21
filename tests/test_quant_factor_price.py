# -*- coding: utf-8 -*-
"""Persistent Price History Layer 纯函数回归测试（不依赖真实 Yahoo 网络）。"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import quant_factor_price as price_mod
from quant_factor_price import (
    SCHEMA_VERSION,
    _normalize_us_date_index,
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
    requested_starts = []

    def fake_fetch(tickers, start, end):
        requested_starts.append(start)
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
    check("二次运行只刷新最新历史附近七天", requested_starts[1] == "2026-01-26",
          f"requested starts={requested_starts}")


# ---- empty price-fetch behavior: preserve history and keep Scan flowing ----
def test_empty_fetch_preserves_existing_file():
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "snap.csv")
    ph_path = os.path.join(tmp, "price_history.csv")
    make_snapshot().to_csv(snap_path, index=False)
    original = (
        "Date,Ticker,Open,High,Low,Close,Volume,schema_version\n"
        "2026-02-02,AAA,,,,100,,phase2b.v1\n"
    ).encode("utf-8")
    with open(ph_path, "wb") as fh:
        fh.write(original)

    def empty_fetch(tickers, start, end):
        return pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)

    result = update_price_history(
        snapshot_path=snap_path, price_history_path=ph_path, fetch_func=empty_fetch
    )
    with open(ph_path, "rb") as fh:
        after = fh.read()
    check("空 fetch 明确标为 FETCH_EMPTY", result["status"] == "FETCH_EMPTY",
          f"got {result['status']}")
    check("空 fetch 保留历史行数", result["total_rows"] == 1,
          f"got {result['total_rows']}")
    check("空 fetch 不改写已有文件字节", after == original)
    check("空 fetch 不留下临时文件", not os.path.exists(ph_path + ".tmp"))


def test_empty_fetch_does_not_create_header_only_csv():
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "snap.csv")
    ph_path = os.path.join(tmp, "price_history.csv")
    make_snapshot().to_csv(snap_path, index=False)

    def empty_fetch(tickers, start, end):
        return pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)

    result = update_price_history(
        snapshot_path=snap_path, price_history_path=ph_path, fetch_func=empty_fetch
    )
    check("首次空 fetch 返回 FETCH_EMPTY", result["status"] == "FETCH_EMPTY",
          f"got {result['status']}")
    check("首次空 fetch 不创建只有表头的历史文件", not os.path.exists(ph_path))
    check("首次空 fetch 不写临时文件", not os.path.exists(ph_path + ".tmp"))


def test_fetch_empty_does_not_fail_scan_step():
    original = price_mod.update_price_history
    try:
        price_mod.update_price_history = lambda rebuild=False: {
            "status": "FETCH_EMPTY",
            "reason": "test-only empty result",
        }
        check("FETCH_EMPTY 只产生 warning，不阻断 Scan", price_mod.main() == 0)
    finally:
        price_mod.update_price_history = original


def test_rebuild_preserves_historical_tickers():
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "snap.csv")
    ph_path = os.path.join(tmp, "price_history.csv")
    make_snapshot().to_csv(snap_path, index=False)
    old = pd.DataFrame([{
        "Date": "2024-01-02", "Ticker": "OLD", "Open": 9.0, "High": 11.0,
        "Low": 8.0, "Close": 10.0, "Volume": 1000, "schema_version": "phase2b.v1",
    }], columns=PRICE_HISTORY_COLUMNS)
    old.to_csv(ph_path, index=False)
    original_tickers = set()

    def fake_fetch(tickers, start, end):
        original_tickers.update(tickers)
        rows = []
        for ticker in tickers:
            rows.append({
                "Date": "2024-01-02", "Ticker": ticker, "Open": 9.5, "High": 10.5,
                "Low": 9.0, "Close": 10.0, "Volume": 1000, "schema_version": SCHEMA_VERSION,
            })
        return pd.DataFrame(rows, columns=PRICE_HISTORY_COLUMNS)

    result = update_price_history(
        snapshot_path=snap_path, price_history_path=ph_path, fetch_func=fake_fetch, rebuild=True
    )
    check("rebuild 成功保留旧 ticker", result["status"] == "OK", str(result))
    check("rebuild 下载集包含历史 ticker", "OLD" in original_tickers, str(original_tickers))
    rebuilt = load_price_history(ph_path)
    check("rebuild schema 全部更新", set(rebuilt["schema_version"]) == {SCHEMA_VERSION})
    check("rebuild 没静默丢旧 ticker", set(rebuilt["Ticker"]) == original_tickers)
    check("rebuild 生成旧文件备份", bool(result.get("backup_path")) and os.path.exists(result["backup_path"]))


def test_rebuild_missing_historical_ticker_preserves_original_file():
    tmp = tempfile.mkdtemp()
    snap_path = os.path.join(tmp, "snap.csv")
    ph_path = os.path.join(tmp, "price_history.csv")
    make_snapshot().to_csv(snap_path, index=False)
    old = pd.DataFrame([{
        "Date": "2024-01-02", "Ticker": "OLD", "Open": 9.0, "High": 11.0,
        "Low": 8.0, "Close": 10.0, "Volume": 1000, "schema_version": "phase2b.v1",
    }], columns=PRICE_HISTORY_COLUMNS)
    old.to_csv(ph_path, index=False)
    before = open(ph_path, "rb").read()

    def incomplete_fetch(tickers, start, end):
        # Deliberately omit OLD to verify that rebuild refuses a lossy replacement.
        return pd.DataFrame([{
            "Date": "2024-01-02", "Ticker": "AAA", "Open": 9.5, "High": 10.5,
            "Low": 9.0, "Close": 10.0, "Volume": 1000, "schema_version": SCHEMA_VERSION,
        }], columns=PRICE_HISTORY_COLUMNS)

    result = update_price_history(
        snapshot_path=snap_path, price_history_path=ph_path, fetch_func=incomplete_fetch, rebuild=True
    )
    check("缺少旧 ticker 时拒绝覆盖", result["status"] == "REBUILD_INCOMPLETE", str(result))
    check("拒绝覆盖后原 CSV 字节不变", open(ph_path, "rb").read() == before)

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


def test_naive_daily_session_date_preserved():
    """tz-naive yfinance daily indexes are session-date labels, not UTC instants."""
    idx = pd.DatetimeIndex(["2026-10-16", "2026-10-19", "2026-10-20"])
    df = pd.DataFrame({"Open": [1.0, 2.0, 3.0], "Close": [1.1, 2.1, 3.1]}, index=idx)
    normalized = _normalize_us_date_index(df)
    dates = [x.strftime("%Y-%m-%d") for x in normalized.index]
    check("tz-naive daily dates preserve session labels", dates == ["2026-10-16", "2026-10-19", "2026-10-20"], f"got {dates}")
    check("naive session labels are assigned US timezone", str(normalized.index.tz) == "America/New_York", f"got {normalized.index.tz}")


def test_aware_utc_daily_timestamp_converts_to_us_date():
    """tz-aware timestamps represent instants and should be converted, not relabeled."""
    idx = pd.DatetimeIndex(["2026-10-19 20:00:00"], tz="UTC")
    df = pd.DataFrame({"Close": [10.0]}, index=idx)
    normalized = _normalize_us_date_index(df)
    check("UTC bar converts to same ET calendar date", normalized.index[0].strftime("%Y-%m-%d") == "2026-10-19",
          f"got {normalized.index[0]}")

# ---- OHLCV 补采（STEP）：schema + 写入 + 向后兼容 ----
def test_schema_has_ohlcv():
    expected = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"]
    check("PRICE_HISTORY_COLUMNS 扩到 OHLCV", PRICE_HISTORY_COLUMNS == expected, f"got {PRICE_HISTORY_COLUMNS}")
    check("Close 列名保留（兼容 Phase 2）", "Close" in PRICE_HISTORY_COLUMNS)
    check("日期语义修复版本为 phase2b.v2", SCHEMA_VERSION == "phase2b.v2", f"got {SCHEMA_VERSION}")


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
        test_empty_fetch_preserves_existing_file,
        test_empty_fetch_does_not_create_header_only_csv,
        test_fetch_empty_does_not_fail_scan_step,
        test_price_map,
        test_filter_bars,
        test_schema_has_ohlcv,
        test_update_writes_ohlcv,
        test_load_backward_compat_old_csv,
        test_naive_daily_session_date_preserved,
        test_aware_utc_daily_timestamp_converts_to_us_date,
        test_rebuild_preserves_historical_tickers,
        test_rebuild_missing_historical_ticker_preserves_original_file,
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
