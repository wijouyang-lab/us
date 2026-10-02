# -*- coding: utf-8 -*-
"""Review → Dashboard 字段透传回归测试（离线，纯函数 + fake provider）。

覆盖本轮定向修复：
  1. 独立买入价 rec_price 透传（不降级复用 Scan_Ref_Price）
  2. Market_Regime / VIX / Sector_RS_20D_Pct 三字段透传
  3. 旧数据（字段缺失）不产生 None/NaN 崩溃
  4. 回归：Current Price / Prev Close / Stop Loss 语义与取值不变

业务红线（测试中一并守护）：
  · rec_price = 正式买入价（推荐日真实 Open），不参与价格回退/止损/PnL/胜率
  · price（当前价）与 rec_price 是三个不同语义之一，不得互相替换
"""
import importlib.util
import os
import sys

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


de = _load("de", "dashboard_export.py")

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


class _FakeProvider:
    """离线 provider：不触网，可控返回当前价，用于验证 price vs rec_price 语义分离。"""

    def __init__(self, available=True, price=515.96):
        self.available = available
        self.name = "fake"
        self.backends = ["fake"]
        self.network_error = None
        self.last_source = "fake"
        self.last_error = None
        self.error_log = {}
        self._price = price

    def daily_bars(self, ticker, days=None):
        return []

    def quote(self, ticker):
        if not self.available:
            return None
        # ts=None -> build_stocks 判为 realtime_unverified，current_price 取 price
        return {"price": self._price, "ts": None, "source": "fake"}


def _trade_row(**over):
    """构造一条 trade_history 事件行（字段名与 TRADE_COLUMNS 一致）。"""
    row = {
        "Date": "2026-08-21", "Ticker": "MSFT", "Name": "Microsoft",
        "Tag": "Core_Dragon", "Score": "71",
        "Price": "479.8800048828125",              # 正式买入价 = 推荐日真实 Open
        "Close_Price": "483.239990234375",         # 前收
        "Stop_Loss": "493.94", "Stop_Method": "MA20/MA50 + ATR + MACD/KDJ",
        "Status": "Active", "RSI": "62.1", "Bias": "1.2", "ATR_Pct": "2.31",
        "Market_Regime": "Bullish", "VIX": "16.5", "Sector_RS_20D_Pct": "2.34",
    }
    row.update(over)
    return row


def _build(row, provider=None):
    cur = de.build_current_event_rows([row], [], {})
    if not cur:
        return None, None
    stocks, _ = de.build_stocks(cur, provider or _FakeProvider(), 180, [], [])
    return cur, stocks


# ---------------------------------------------------------------- Test 1
print("== Test 1. rec_price = 479.88 进入 stocks[].rec_price ==")
cur, stocks = _build(_trade_row())
check("1a. build_current_event_rows 生成事件", bool(cur), f"{len(cur) if cur else 0} 条")
check("1b. current_rows 含独立 Rec_Price 字段",
      bool(cur) and cur[0].get("Rec_Price") == "479.8800048828125",
      f"{cur[0].get('Rec_Price') if cur else None}")
check("1c. Scan_Ref_Price 仍保留（未删除旧逻辑）",
      bool(cur) and cur[0].get("Scan_Ref_Price") == "479.8800048828125",
      f"{cur[0].get('Scan_Ref_Price') if cur else None}")
check("1d. stocks[].rec_price = 479.88（两位小数）",
      bool(stocks) and abs(stocks[0]["rec_price"] - 479.88) < 0.005,
      f"{stocks[0].get('rec_price') if stocks else None}")

# ---------------------------------------------------------------- Test 2
print("== Test 2. Market_Regime 非空进入 stocks[].market_regime ==")
cur, stocks = _build(_trade_row(Market_Regime="Bullish"))
check("2a. current_rows 透传 Market_Regime",
      bool(cur) and cur[0].get("Market_Regime") == "Bullish",
      f"{cur[0].get('Market_Regime') if cur else None}")
check("2b. stocks[].market_regime = 'Bullish'",
      bool(stocks) and stocks[0]["market_regime"] == "Bullish",
      f"{stocks[0].get('market_regime') if stocks else None}")

# ---------------------------------------------------------------- Test 3
print("== Test 3. VIX 非空进入 Dashboard ==")
cur, stocks = _build(_trade_row(VIX="16.5"))
check("3a. current_rows 透传 VIX", bool(cur) and cur[0].get("VIX") == "16.5",
      f"{cur[0].get('VIX') if cur else None}")
check("3b. stocks[].vix = 16.5", bool(stocks) and abs(stocks[0]["vix"] - 16.5) < 0.001,
      f"{stocks[0].get('vix') if stocks else None}")

# ---------------------------------------------------------------- Test 4
print("== Test 4. Sector_RS_20D_Pct 非空进入 Dashboard ==")
cur, stocks = _build(_trade_row(Sector_RS_20D_Pct="2.34"))
check("4a. current_rows 透传 Sector_RS_20D_Pct",
      bool(cur) and cur[0].get("Sector_RS_20D_Pct") == "2.34",
      f"{cur[0].get('Sector_RS_20D_Pct') if cur else None}")
check("4b. stocks[].sector_rs_20d_pct = 2.34",
      bool(stocks) and abs(stocks[0]["sector_rs_20d_pct"] - 2.34) < 0.001,
      f"{stocks[0].get('sector_rs_20d_pct') if stocks else None}")

# ---------------------------------------------------------------- Test 5
print("== Test 5. 旧数据（rec_price / market_regime 缺失）不崩溃 ==")
# 5a: 无 context 字段的旧事件行
old = _trade_row()
for k in ("Market_Regime", "VIX", "Sector_RS_20D_Pct"):
    old.pop(k, None)
cur, stocks = _build(old)
check("5a. 旧事件仍能构建 stocks（不报错）", bool(stocks), f"{len(stocks) if stocks else 0}")
check("5b. market_regime = None（非 NaN/undefined）",
      bool(stocks) and stocks[0]["market_regime"] is None,
      f"{stocks[0].get('market_regime') if stocks else None}")
check("5c. vix = None", bool(stocks) and stocks[0]["vix"] is None,
      f"{stocks[0].get('vix') if stocks else None}")
check("5d. sector_rs_20d_pct = None", bool(stocks) and stocks[0]["sector_rs_20d_pct"] is None,
      f"{stocks[0].get('sector_rs_20d_pct') if stocks else None}")
# 5e: 完全无 Rec_Price 的 row（模拟 pending 新推荐/极旧数据）
bare = {"Ticker": "OLD", "Date": "2026-01-01", "Tag": "Core_Dragon", "Score": "70",
        "Stop_Loss": "100", "Prev_Close": "110"}
stocks2, _ = de.build_stocks([bare], _FakeProvider(), 180, [], [])
check("5e. 无 Rec_Price 时 rec_price = None（不报错）",
      bool(stocks2) and stocks2[0]["rec_price"] is None,
      f"{stocks2[0].get('rec_price') if stocks2 else None}")

# ---------------------------------------------------------------- Test 6
print("== Test 6. Current Price 仍来自 current price，未被 rec_price 替换 ==")
cur, stocks = _build(_trade_row(), provider=_FakeProvider(available=True, price=515.96))
check("6a. stocks[].price = 515.96（当前价）",
      bool(stocks) and abs(stocks[0]["price"] - 515.96) < 0.005,
      f"{stocks[0].get('price') if stocks else None}")
check("6b. stocks[].rec_price = 479.88（买入价）",
      bool(stocks) and abs(stocks[0]["rec_price"] - 479.88) < 0.005,
      f"{stocks[0].get('rec_price') if stocks else None}")
check("6c. price != rec_price（两者语义不同）",
      bool(stocks) and abs(stocks[0]["price"] - stocks[0]["rec_price"]) > 1,
      f"price={stocks[0].get('price')} rec_price={stocks[0].get('rec_price')}")
check("6d. price_source 为行情来源（非 rec_price）",
      bool(stocks) and stocks[0]["price_source"] in ("realtime", "realtime_unverified", "last_close"),
      f"{stocks[0].get('price_source') if stocks else None}")

# ---------------------------------------------------------------- Test 7
print("== Test 7. Prev Close 未改变 ==")
cur, stocks = _build(_trade_row())
check("7a. stocks[].prev_close = 483.24",
      bool(stocks) and abs(stocks[0]["prev_close"] - 483.24) < 0.005,
      f"{stocks[0].get('prev_close') if stocks else None}")
check("7b. prev_close != rec_price（前收与买入价不同）",
      bool(stocks) and abs(stocks[0]["prev_close"] - stocks[0]["rec_price"]) > 0.5,
      f"prev_close={stocks[0].get('prev_close')} rec_price={stocks[0].get('rec_price')}")

# ---------------------------------------------------------------- Test 8
print("== Test 8. Stop Loss 未改变 ==")
cur, stocks = _build(_trade_row())
check("8a. stocks[].stop_loss = 493.94",
      bool(stocks) and abs(stocks[0]["stop_loss"] - 493.94) < 0.005,
      f"{stocks[0].get('stop_loss') if stocks else None}")
check("8b. stop_loss 未使用 rec_price（493.94 != 479.88）",
      bool(stocks) and abs(stocks[0]["stop_loss"] - stocks[0]["rec_price"]) > 1,
      f"stop={stocks[0].get('stop_loss')} rec_price={stocks[0].get('rec_price')}")

# ---------------------------------------------------------------- 回归
print("== 9. 回归：review.py / dashboard_export.py / app.js 结构 ==")
rv = open(os.path.join(REPO, "review.py"), encoding="utf-8").read()
sj = open(os.path.join(REPO, "app.js"), encoding="utf-8").read()
check("9a. review.py TRADE_COLUMNS 含 Market_Regime", '"Market_Regime"' in rv)
check("9b. review.py TRADE_COLUMNS 含 VIX", '"VIX"' in rv)
check("9c. review.py TRADE_COLUMNS 含 Sector_RS_20D_Pct", '"Sector_RS_20D_Pct"' in rv)
check("9d. review.py 透传为原样取值（不重算）",
      'clean_text(row.get("Market_Regime"))' in rv and 'clean_text(row.get("VIX"))' in rv)
check("9e. _TRADE_TO_PENDING 含 Market_Regime 映射",
      '"Market_Regime": "Market_Regime"' in open(
          os.path.join(REPO, "dashboard_export.py"), encoding="utf-8").read())
check("9f. app.js 映射 recPrice = s.rec_price", "recPrice: num(s.rec_price)" in sj)
check("9g. app.js posMatrix 渲染买入价", "mx('买入价', nv(s.recPrice" in sj)
check("9h. app.js 用 nv()（null 安全，不会 null.toFixed 崩溃）",
      "nv(s.recPrice, 2)" in sj)
check("9i. app.js 未改 Price 语义（仍用 s.px）", "mx('Price', nv(s.px, 2))" in sj)
check("9j. app.js 未改 Prev Close 语义", "mx('Prev Close', nv(s.prevClose, 2))" in sj)

# ---------------------------------------------------------------- 红线
print("== 10. 红线：Options RR / 止损 / 胜率 未被触碰 ==")
eng = open(os.path.join(REPO, "scan_us_option_engine.py"), encoding="utf-8").read()
check("10a. MIN_REWARD_RISK 仍为 2.0", "MIN_REWARD_RISK = 2.0" in eng)
check("10b. MIN_SPREAD_REWARD_RISK 仍为 0.40", "MIN_SPREAD_REWARD_RISK = 0.40" in eng)
check("10c. Options Status 仍由 trade_status 判定", '"Status":trade_status' in eng)
check("10d. review.py 胜率公式未变", "win_rate = (wins / eligible * 100) if eligible else None" in rv)
check("10e. review.py safe_record_price 仍为 Price 取值",
      "p = safe_float(row.get(\"Price\"))" in rv)

# ---------------------------------------------------------------- 结果
print()
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"结果：通过 {passed} / {total}")
if passed == total:
    print("全部通过 ✅")
else:
    print("存在失败 ❌")
    for n, ok in results:
        if not ok:
            print(f"   FAILED: {n}")
    sys.exit(1)
