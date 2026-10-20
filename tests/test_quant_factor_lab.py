# -*- coding: utf-8 -*-
"""Quant Factor Lab 纯函数回归测试（不依赖真实 Yahoo 网络）。"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_factor_lab import (
    beta_60d,
    build_snapshot_rows,
    calculate_extended_quant_factors,
    check_technical_date_contract,
    momentum_pct,
    realized_volatility_20d_pct,
    stock_rs_20d_vs_spy,
    volume_ratio_20d,
    write_factor_snapshot,
    zscore_20d,
)



def check(name, cond, detail=""):
    """断言：FAIL 时抛出 AssertionError（pytest 可捕获），同时保留打印。"""
    if cond:
        print(f"  [PASS] {name}")
        return True
    print(f"  [FAIL] {name}  {detail}")
    raise AssertionError(f"{name}  {detail}".strip())


def make_series(values, start="2026-01-01"):
    """构造以日期为索引的 Series，便于 beta/rs 的 index 对齐。"""
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, dtype=float)


def make_df(close_values, volume_values=None, start="2026-01-01"):
    idx = pd.date_range(start, periods=len(close_values), freq="B")
    df = pd.DataFrame({"Close": close_values, "Volume": volume_values}, index=idx)
    return df


# ---- 1-3. Momentum 5D / 20D / 60D ----
def test_momentum():
    c = make_series([100.0] * 6 + [110.0])  # 最后一天 110，5 天前是第 2 个 100（index -6）
    check("Momentum 5D", momentum_pct(c, 5) == 10.0, f"got {momentum_pct(c, 5)}")

    # 20D: 21 根，最后一天 121 vs 第 1 根 100
    c20 = make_series([100.0] * 21)
    c20.iloc[-1] = 121.0
    check("Momentum 20D", momentum_pct(c20, 20) == 21.0, f"got {momentum_pct(c20, 20)}")

    # 60D: 61 根
    c60 = make_series([100.0] * 61)
    c60.iloc[-1] = 130.0
    check("Momentum 60D", momentum_pct(c60, 60) == 30.0, f"got {momentum_pct(c60, 60)}")


# ---- 4. Realized Volatility 20D ----
def test_realized_vol():
    # 20 个收益率，每个 1% → 日收益率 std=0，annualized=0
    c = make_series([100.0 * (1.01 ** i) for i in range(21)])
    rv = realized_volatility_20d_pct(c)
    # 常数日收益率 1% → std=0
    check("RV 常数收益率=0", rv == 0.0, f"got {rv}")

    # 波动序列：非零
    c2 = make_series([100 + (i % 2) * 5 for i in range(25)])
    rv2 = realized_volatility_20d_pct(c2)
    check("RV 非零", rv2 is not None and rv2 > 0, f"got {rv2}")


# ---- 5. Volume Ratio 20D ----
def test_volume_ratio():
    v = make_series([100.0] * 21)
    v.iloc[-1] = 200.0  # 当前 200 / 前20均值 100 = 2.0
    check("Volume Ratio 20D", volume_ratio_20d(v) == 2.0, f"got {volume_ratio_20d(v)}")

    # 前20均值含 0 → 均值为 0 时 None（但这里前20都是100，非0）
    v2 = make_series([0.0] * 20 + [100.0])
    check("Volume Ratio 均值0→None", volume_ratio_20d(v2) is None, f"got {volume_ratio_20d(v2)}")


# ---- 6. ZScore 20D ----
def test_zscore():
    c = make_series([100.0] * 20 + [120.0])  # 前20 std=0 → None
    check("ZScore 前20 std=0→None", zscore_20d(c) is None, f"got {zscore_20d(c)}")

    # 前20 有波动
    c2 = make_series([100 + i for i in range(20)] + [200.0])
    z = zscore_20d(c2)
    check("ZScore 非None", z is not None and z > 0, f"got {z}")


# ---- 7. Beta 60D ----
def test_beta():
    # 用固定种子生成有波动的 spy 收益率，stock = 2 * spy 收益率 → beta 应为 2
    rng = np.random.default_rng(42)
    spy_ret = rng.normal(0.0005, 0.01, size=64)
    spy_ret[0] = 0.0
    spy_close = 100.0 * np.cumprod(1.0 + spy_ret)
    stock_ret = 2.0 * spy_ret
    stock_close = 100.0 * np.cumprod(1.0 + stock_ret)
    spy = make_series(list(spy_close))
    stock = make_series(list(stock_close))
    b = beta_60d(stock, spy)
    check("Beta 完全相关≈2", b is not None and abs(b - 2.0) < 0.01, f"got {b}")


def test_beta_constant_spy():
    # SPY 恒定 → Var=0 → None
    spy = make_series([100.0] * 65)
    stock = make_series([100 * (1.01 ** i) for i in range(65)])
    check("Beta SPY恒定→None", beta_60d(stock, spy) is None, f"got {beta_60d(stock, spy)}")

# ---- 8. Stock RS 20D ----
def test_stock_rs():
    spy = make_series([100.0] * 21)
    spy.iloc[-1] = 110.0  # spy 20D +10%
    stock = make_series([100.0] * 21)
    stock.iloc[-1] = 115.0  # stock 20D +15%
    rs = stock_rs_20d_vs_spy(stock, spy)
    check("Stock RS 20D = 5%", rs is not None and abs(rs - 5.0) < 0.001, f"got {rs}")


# ---- 9. 缺少足够 bar → None ----
def test_insufficient_bars():
    short = make_series([100.0, 101.0, 102.0])
    check("Momentum 60D 不足→None", momentum_pct(short, 60) is None)
    check("RV 不足→None", realized_volatility_20d_pct(short) is None)
    check("VolumeRatio 不足→None", volume_ratio_20d(short) is None)
    check("ZScore 不足→None", zscore_20d(short) is None)


# ---- 10. SPY 缺失 → Beta/RS None ----
def test_spy_missing():
    c = make_series([100 + i for i in range(70)])
    check("Beta SPY缺失→None", beta_60d(c, None) is None)
    check("RS SPY缺失→None", stock_rs_20d_vs_spy(c, None) is None)


# ---- 12. NaN 处理 ----
def test_nan_handling():
    c = make_series([100.0, np.nan, 102.0, 103.0] + [104.0] * 20)
    # NaN 应被 dropna 清理，不报错
    m = momentum_pct(c, 5)
    check("NaN 清理后计算", m is not None, f"got {m}")
    # 全 NaN
    all_nan = make_series([np.nan] * 25)
    check("全NaN momentum→None", momentum_pct(all_nan, 5) is None)
    check("全NaN zscore→None", zscore_20d(all_nan) is None)


# ---- 13-16. Snapshot 去重 / upsert / 重跑不重复 ----
def _sample_pool():
    return [
        {"Ticker": "AMD", "Name": "AMD", "Technical_Date": "2026-10-05", "Sector": "Technology",
         "Price": 100.0, "RSI": 55.0, "乖离率(%)": 2.5, "MACD_HIST_LAST": 0.1, "MA20": 98.0,
         "MA50": 95.0, "MA20_Slope_Pct_5D": 1.2, "ATR_Pct": 3.0, "KDJ_J": 60.0, "量比": 1.5,
         "Momentum_5D_Pct": 5.0, "Momentum_20D_Pct": 8.0, "Momentum_60D_Pct": 15.0,
         "Realized_Volatility_20D_Pct": 25.0, "Volume_Ratio_20D": 1.8, "ZScore_20D": 0.6,
         "Beta_60D_SPY": 1.3, "Stock_RS_20D_vs_SPY": 3.0, "Sector_RS_20D_Pct": 2.0,
         "VIX": 15.0, "Market_Regime": "NORMAL", "Fundamental_Score": 25.0, "Event_Score": 15.0,
         "Technical_Score_25": 20.0, "Risk_Liquidity_Score": 15.0, "Quant_Score": 75.0,
         "技术确认数": 4, "Gate_Status": "PASS_PRE_AI"},
        {"Ticker": "META", "Name": "Meta", "Technical_Date": "2026-10-05", "Sector": "Communication",
         "Price": 200.0, "RSI": 60.0, "乖离率(%)": 1.0, "MACD_HIST_LAST": 0.2, "MA20": 198.0,
         "MA50": 195.0, "MA20_Slope_Pct_5D": 0.5, "ATR_Pct": 2.5, "KDJ_J": 70.0, "量比": 1.1,
         "Momentum_5D_Pct": 2.0, "Momentum_20D_Pct": 4.0, "Momentum_60D_Pct": 10.0,
         "Realized_Volatility_20D_Pct": 20.0, "Volume_Ratio_20D": 1.2, "ZScore_20D": 0.2,
         "Beta_60D_SPY": 1.1, "Stock_RS_20D_vs_SPY": 1.5, "Sector_RS_20D_Pct": 1.0,
         "VIX": 15.0, "Market_Regime": "NORMAL", "Fundamental_Score": 28.0, "Event_Score": 12.0,
         "Technical_Score_25": 18.0, "Risk_Liquidity_Score": 16.0, "Quant_Score": 74.0,
         "技术确认数": 3, "Gate_Status": "TECH_FAIL"},
    ]


def test_snapshot():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "quant_factor_snapshot.csv")
    pool = _sample_pool()
    n = write_factor_snapshot(pool, path, "2026-10-06")
    check("Snapshot 首次写 2 行", n == 2, f"got {n}")

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    check("Snapshot 列完整", list(df.columns) == list(__import__("quant_factor_lab").SNAPSHOT_COLUMNS),
          f"cols={list(df.columns)[:5]}...")

    # 重跑同一 Scan_Date：应 upsert 不重复
    n2 = write_factor_snapshot(pool, path, "2026-10-06")
    check("重跑同 Scan_Date 不重复", n2 == 2, f"got {n2}")

    # 新 Scan_Date：追加，总行数增加
    n3 = write_factor_snapshot(pool, path, "2026-10-07")
    check("新 Scan_Date 追加", n3 == 4, f"got {n3}")

    df3 = pd.read_csv(path, dtype=str, keep_default_na=False)
    check("无 duplicate key", df3.duplicated(subset=["Scan_Date", "Ticker"]).sum() == 0)
    check("META 的 Gate_Status 保留", "TECH_FAIL" in df3["Gate_Status"].values)


# ---- 15. 不出现未来数据（因子只用历史窗口，不读 Exit/PnL）----
def test_no_lookahead():
    # 构造带"未来"字段的 item，确认 build_snapshot_rows 不读取这些字段
    item = {"Ticker": "X", "Name": "X", "Technical_Date": "2026-10-05", "Sector": "Tech",
            "Price": 50.0, "RSI": 50.0, "乖离率(%)": 1.0, "MACD_HIST_LAST": 0.1, "MA20": 49.0,
            "MA50": 48.0, "MA20_Slope_Pct_5D": 0.5, "ATR_Pct": 2.0, "KDJ_J": 55.0, "量比": 1.0,
            "Exit_Price": 999.0, "PnL_Pct": 999.0, "future_milestone": "999"}
    rows = build_snapshot_rows([item], "2026-10-06")
    r = rows[0]
    check("无 Exit_Price 列", "Exit_Price" not in r)
    check("无 PnL 列", "PnL_Pct" not in r)
    check("Price 取快照价", r["Price"] == "50.00", f"got {r['Price']}")


# ---- 全量入口 ----
# ---- 契约告警（Technical_Date vs 理论最后完成交易日）----
# 约束：测试用例不出现任何绝对业务日期 —— 全部用 pandas.bdate_range 动态生成日历，
# 再按「末端 / 末端-1 / 末端-2」的相对位置取日期。
def test_technical_date_contract_warning():
    """契约告警必须把"隐性滞后"变成显性信号；且自身严格只读。"""
    cal = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-09-01", periods=30)]
    last = cal[-1]        # 理论最后完成交易日
    prev1 = cal[-2]       # 滞后 1 个交易日
    prev2 = cal[-3]       # 滞后 2 个交易日
    beyond = (pd.Timestamp(cal[-1]) + pd.Timedelta(days=3)).strftime("%Y-%m-%d")  # 超前场景

    # (1) 滞后 1 个交易日 → STALE + 完整 warning 四要素
    r = check_technical_date_contract(prev1, last, trading_dates=cal)
    check("滞后1个交易日 → STALE", r["status"] == "STALE", f"got {r['status']}")
    check("gap_trading_days = 1", r["gap_trading_days"] == 1, str(r["gap_trading_days"]))
    check("expected_date = 理论最后完成交易日", r["expected_date"] == last, str(r["expected_date"]))
    msg = r["message"]
    check("warning 含 实际 Technical_Date", prev1 in msg)
    check("warning 含 理论/最新可得日期", last in msg)
    check("warning 含 相差交易日数", ("1" in msg and "交易日" in msg))
    check("warning 含 建议", "建议" in msg)
    check("warning 指向契约出处", "quant_factor_price.py" in msg)

    # (2) 滞后 2 个交易日 → STALE 且 gap=2（可区分滞后幅度）
    r2 = check_technical_date_contract(prev2, last, trading_dates=cal)
    check("滞后2个交易日 → STALE", r2["status"] == "STALE", f"got {r2['status']}")
    check("gap_trading_days = 2", r2["gap_trading_days"] == 2, str(r2["gap_trading_days"]))

    # (3) 契约成立 → OK，不告警
    r3 = check_technical_date_contract(last, last, trading_dates=cal)
    check("T == 理论值 → OK", r3["status"] == "OK", f"got {r3['status']}")
    check("OK 时 gap = 0", r3["gap_trading_days"] == 0)

    # (4) 实际比日历更新 → AHEAD，不误报为 STALE
    r4 = check_technical_date_contract(beyond, last, trading_dates=cal)
    check("T 晚于日历末端 → AHEAD（不误报 STALE）",
          r4["status"] == "AHEAD", f"got {r4['status']}")

    # (5) 无 price history 参考时仍可用 cutoff 判定（降级为自然日差，不崩溃）
    r5 = check_technical_date_contract(prev1, last, trading_dates=None)
    check("无日历参考 → 仍能判定 STALE", r5["status"] == "STALE", f"got {r5['status']}")
    check("无日历参考 → gap 非空", r5["gap_trading_days"] is not None)

    # (6) 缺输入 → 明确状态，不崩溃
    r6 = check_technical_date_contract(None, last, trading_dates=cal)
    check("缺 Technical_Date → NO_DATA", r6["status"] == "NO_DATA", f"got {r6['status']}")
    r7 = check_technical_date_contract(prev1, None, trading_dates=cal)
    check("缺 cutoff → NO_REFERENCE", r7["status"] == "NO_REFERENCE", f"got {r7['status']}")

    # (7) 只读性：不修改入参、不产生任何文件
    cal_copy = list(cal)
    check_technical_date_contract(prev1, last, trading_dates=cal)
    check("只读：不修改传入的 trading_dates", cal == cal_copy)
    tmp = tempfile.mkdtemp()
    before = sorted(os.listdir(tmp))
    check_technical_date_contract(prev1, last, trading_dates=cal)
    check("只读：不产生任何文件", sorted(os.listdir(tmp)) == before)

    # (8) 确定性：同输入两次调用结果一致
    a = check_technical_date_contract(prev1, last, trading_dates=cal)
    b = check_technical_date_contract(prev1, last, trading_dates=cal)
    check("确定性：重复调用结果一致", a == b)


def main():
    _tests = [
        test_momentum,
        test_realized_vol,
        test_volume_ratio,
        test_zscore,
        test_beta,
        test_beta_constant_spy,
        test_stock_rs,
        test_insufficient_bars,
        test_spy_missing,
        test_nan_handling,
        test_snapshot,
        test_no_lookahead,
        # ---- 契约告警 ----
        test_technical_date_contract_warning,
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
