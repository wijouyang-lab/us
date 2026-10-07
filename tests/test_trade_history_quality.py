# -*- coding: utf-8 -*-
"""Trade History 数据质量修复回归测试。

覆盖：duplicate 检测、canonical 选择、Review 幂等、KPI 不重复计数、
Rec_Price 精度、价格来源不改变、退出信息不丢失、PnL/Stop Loss 不变。
"""
import sys

import pandas as pd

sys.path.insert(0, ".")
from trade_history_quality import (
    deduplicate_trade_history,
    field_is_informative,
    fmt_price,
    review_event_key,
)



def check(name, cond, detail=""):
    """断言：FAIL 时抛出 AssertionError（pytest 可捕获），同时保留打印。"""
    if cond:
        print(f"  [PASS] {name}")
        return True
    print(f"  [FAIL] {name}  {detail}")
    raise AssertionError(f"{name}  {detail}".strip())


def make_th(rows):
    cols = ["Date", "Ticker", "Name", "Tag", "Price", "Hold_Period", "Stop_Loss",
            "Exit_Date", "Exit_Price", "Status", "Close_Price"]
    df = pd.DataFrame(rows, columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df


# ---- 1. duplicate event detection ----
def test_detect_duplicate():
    df = make_th([
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "N/A", "Stop_Loss": "N/A", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "5-12天", "Stop_Loss": "-5%", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
        {"Date": "2026-06-02", "Ticker": "BBB", "Tag": "Observation", "Price": "50.00",
         "Hold_Period": "观望", "Stop_Loss": "N/A", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
    ])
    keys = review_event_key(df)
    check("1. duplicate event detection（识别 AAA 重复）", keys.duplicated().sum() == 1,
          f"dup={keys.duplicated().sum()}")


# ---- 2. deterministic canonical selection ----
def test_canonical_selection():
    df = make_th([
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "N/A", "Stop_Loss": "N/A", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "5-12天", "Stop_Loss": "-5%", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
    ])
    out = deduplicate_trade_history(df)
    check("2. canonical selection 去重后 1 行", len(out) == 1, f"got {len(out)}")
    check("2b. 保留信息最完整行（Hold_Period=5-12天）", out.iloc[0]["Hold_Period"] == "5-12天",
          out.iloc[0]["Hold_Period"])
    check("2c. 保留信息最完整行（Stop_Loss=-5%）", out.iloc[0]["Stop_Loss"] == "-5%",
          out.iloc[0]["Stop_Loss"])


# ---- 3. duplicate Review run does not add event ----
def test_dedup_idempotent():
    df = make_th([
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "5-12天", "Stop_Loss": "-5%", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
    ])
    once = deduplicate_trade_history(df)
    # 再次叠加同 key 行（模拟 Review 重跑重复入账），去重后仍只有 1 行
    df2 = pd.concat([df, make_th([
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "5-12天", "Stop_Loss": "-5%", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
    ])], ignore_index=True)
    out = deduplicate_trade_history(df2)
    check("3. duplicate Review run 不新增事件", len(out) == 1, f"got {len(out)}")


# ---- 4. KPI does not double count ----
def test_kpi_no_double_count():
    df = make_th([
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "N/A", "Stop_Loss": "N/A", "Exit_Date": "", "Exit_Price": "", "Status": "Stop_Loss_Hit"},
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "5-12天", "Stop_Loss": "-5%", "Exit_Date": "2026-06-10", "Exit_Price": "95.00", "Status": "Stop_Loss_Hit"},
    ])
    out = deduplicate_trade_history(df)
    check("4. KPI 不重复计数（Stop_Loss_Hit 只算 1 次）",
          (out["Status"] == "Stop_Loss_Hit").sum() == 1, f"got {(out['Status']=='Stop_Loss_Hit').sum()}")


# ---- 5. Rec_Price rounds to 2 decimals ----
def test_fmt_price_round():
    check("5. 浮点尾数 -> 两位小数", fmt_price(479.8800048828125) == "479.88", fmt_price(479.8800048828125))
    check("5b. 保留尾零（483.30）", fmt_price(483.2999877929688) == "483.30", fmt_price(483.2999877929688))
    check("5c. 整数 -> 两位小数", fmt_price(100.0) == "100.00", fmt_price(100.0))


# ---- 6. None remains None ----
def test_fmt_none():
    check("6. None -> 空字符串（不变成 0）", fmt_price(None) == "", repr(fmt_price(None)))


# ---- 7. NaN does not become valid price ----
def test_fmt_nan():
    check("7. NaN -> 空字符串（不变成 0.00）", fmt_price(float("nan")) == "", repr(fmt_price(float("nan"))))


# ---- 8. price source remains recommendation-date Open ----
def test_price_source_unchanged():
    # dedup 不改变 Price 字段本身（来源仍是推荐日 Open）
    df = make_th([
        {"Date": "2026-08-21", "Ticker": "MSFT", "Tag": "Core_Dragon", "Price": "479.88",
         "Hold_Period": "N/A", "Stop_Loss": "N/A", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
        {"Date": "2026-08-21", "Ticker": "MSFT", "Tag": "Core_Dragon", "Price": "479.88",
         "Hold_Period": "10-20天", "Stop_Loss": "-5%", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
    ])
    out = deduplicate_trade_history(df)
    check("8. Price 来源不变（仍是推荐日 Open 值）", out.iloc[0]["Price"] == "479.88", out.iloc[0]["Price"])


# ---- 9. Exit record is not lost ----
def test_exit_not_lost():
    df = make_th([
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "N/A", "Stop_Loss": "N/A", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "5-12天", "Stop_Loss": "-5%", "Exit_Date": "2026-06-10", "Exit_Price": "95.00", "Status": "Stop_Loss_Hit"},
    ])
    out = deduplicate_trade_history(df)
    check("9. Exit_Date/Exit_Price 不丢失", out.iloc[0]["Exit_Date"] == "2026-06-10" and out.iloc[0]["Exit_Price"] == "95.00",
          f"{out.iloc[0]['Exit_Date']}/{out.iloc[0]['Exit_Price']}")


# ---- 10. Status is not incorrectly downgraded ----
def test_status_not_downgraded():
    df = make_th([
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "N/A", "Stop_Loss": "N/A", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "5-12天", "Stop_Loss": "-5%", "Exit_Date": "2026-06-10", "Exit_Price": "95.00", "Status": "Stop_Loss_Hit"},
    ])
    out = deduplicate_trade_history(df)
    check("10. Status 不被降级（保留 Stop_Loss_Hit）", out.iloc[0]["Status"] == "Stop_Loss_Hit", out.iloc[0]["Status"])


# ---- 11. PnL unchanged ----
def test_pnl_unchanged():
    # dedup 不触碰任何 PnL 相关字段（Price/Exit_Price 一致，PnL 语义不变）
    df = make_th([
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "N/A", "Stop_Loss": "N/A", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "5-12天", "Stop_Loss": "-5%", "Exit_Date": "2026-06-10", "Exit_Price": "95.00", "Status": "Stop_Loss_Hit"},
    ])
    out = deduplicate_trade_history(df)
    check("11. PnL 语义不变（Price=100.00 / Exit=95.00 保持）",
          out.iloc[0]["Price"] == "100.00" and out.iloc[0]["Exit_Price"] == "95.00",
          f"{out.iloc[0]['Price']}/{out.iloc[0]['Exit_Price']}")


# ---- 12. Stop Loss unchanged ----
def test_stop_loss_unchanged():
    df = make_th([
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "N/A", "Stop_Loss": "-5%", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "5-12天", "Stop_Loss": "-5%", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
    ])
    out = deduplicate_trade_history(df)
    check("12. Stop_Loss 不变（保留 -5%）", out.iloc[0]["Stop_Loss"] == "-5%", out.iloc[0]["Stop_Loss"])


# ---- 13. repeated execution is idempotent ----
def test_idempotent():
    df = make_th([
        {"Date": "2026-06-02", "Ticker": "AAA", "Tag": "Core_Dragon", "Price": "100.00",
         "Hold_Period": "5-12天", "Stop_Loss": "-5%", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
        {"Date": "2026-06-03", "Ticker": "BBB", "Tag": "Observation", "Price": "50.00",
         "Hold_Period": "观望", "Stop_Loss": "N/A", "Exit_Date": "", "Exit_Price": "", "Status": "Active"},
    ])
    r1 = deduplicate_trade_history(df)
    r2 = deduplicate_trade_history(r1)
    check("13. 重复执行幂等（两次结果一致）", r1.equals(r2), "两次输出不同")


# ---- field_is_informative 边界 ----
def test_field_informative():
    check("field_is_informative: 空 -> False", not field_is_informative(""))
    check("field_is_informative: N/A -> False", not field_is_informative("N/A"))
    check("field_is_informative: 观望 -> False", not field_is_informative("观望"))
    check("field_is_informative: nan -> False", not field_is_informative("nan"))
    check("field_is_informative: -5% -> True", field_is_informative("-5%"))
    check("field_is_informative: 5-12天 -> True", field_is_informative("5-12天"))


def main():
    _tests = [
        test_detect_duplicate,
        test_canonical_selection,
        test_dedup_idempotent,
        test_kpi_no_double_count,
        test_fmt_price_round,
        test_fmt_none,
        test_fmt_nan,
        test_price_source_unchanged,
        test_exit_not_lost,
        test_status_not_downgraded,
        test_pnl_unchanged,
        test_stop_loss_unchanged,
        test_idempotent,
        test_field_informative,
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
