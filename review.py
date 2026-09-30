# -*- coding: utf-8 -*-
"""
美股盘后复盘与风控审查引擎 V32
================================================
核心统计口径：
1. 每次 Scan 推荐事件按「推荐日期 + Ticker」独立追踪。
2. Observation 是有效 Scan 推荐，必须追踪推荐价 -> 当前价。
3. 实际持仓与 Observation 分开，不把 Observation 算成持仓。
4. Scan 推荐综合胜率 = 当前持仓 + Observation + 已了结股票推荐。
5. 数据缺失的推荐不虚构收益，但保留为“数据不足”。
6. 期权完全独立，不混入股票 Scan 推荐胜率。
7. 同一 Review 日期不会重复写入相同推荐事件。
8. 股票不按固定持仓天数强制退出，采用 MA20/MA50 + ATR + MACD/KDJ 移动止损。
"""

import csv
import datetime
import json
import glob
import os
import re
import smtplib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo
import urllib.parse
import urllib.request

import anthropic
import pandas as pd
import yfinance as yf


# ============================================================
# 0. 环境与时间
# ============================================================

_missing_env = [
    k for k in ("CLAWSOCKET_API_KEY", "CLAWSOCKET_BASE_URL")
    if not os.environ.get(k)
]
if _missing_env:
    print(f"致命错误：未检测到环境变量 {', '.join(_missing_env)}！")
    sys.exit(1)

US_TZ = ZoneInfo("America/New_York")
TARGET_MODEL = "gpt-6-astra"

STRATEGY_PARAMS_FILE = "strategy_params.json"
def load_strategy_params():
    defaults = {"exit": {"early_days":3,"early_stop_pct":-5.0,"atr_multiplier":2.0,"atr_floor_pct":3.0,"atr_ceiling_pct":12.0,
                          "profit_lock_1_pct":15.0,"profit_lock_1_drawdown_pct":10.0,"profit_lock_2_pct":30.0,"profit_lock_2_drawdown_pct":8.0,
                          "profit_lock_3_pct":50.0,"profit_lock_3_drawdown_pct":12.0}}
    try:
        with open(STRATEGY_PARAMS_FILE,"r",encoding="utf-8") as f: d=json.load(f)
        if isinstance(d.get("exit"),dict): defaults["exit"].update(d["exit"])
    except Exception as e: print(f"⚠️ Review策略参数读取失败，使用默认值: {e}")
    return defaults

REVIEW_PARAMS = load_strategy_params()
EXIT_PARAMS = REVIEW_PARAMS["exit"]

def get_us_time():
    return datetime.datetime.now(US_TZ)

def today_us_str():
    return get_us_time().strftime("%Y-%m-%d")

def _previous_business_day(date_obj):
    d = date_obj
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d

def review_session_date():
    """返回本次盘后 Review 应该评估的最近一个已完成美股常规交易日。

    Review 可能在美东午夜后运行（例如 GitHub Actions 的 UTC cron），
    此时“美东今天”尚未开盘，不能把当天当成已完成交易日。
    16:00 ET 之后才把当天视为已完成常规交易日；此前统一评估上一交易日。
    """
    now = get_us_time()
    if now.weekday() >= 5:
        d = now.date() - datetime.timedelta(days=1)
        return _previous_business_day(d).strftime("%Y-%m-%d")
    if now.time() >= datetime.time(16, 0):
        return now.strftime("%Y-%m-%d")
    d = now.date() - datetime.timedelta(days=1)
    return _previous_business_day(d).strftime("%Y-%m-%d")

REVIEW_SESSION_DATE = review_session_date()

if get_us_time().weekday() >= 5:
    print("当前为周末，美股休市，退出复盘。")
    sys.exit(0)

print("=" * 60)
print("启动美股盘后复盘与风控审查引擎")
print(f"📅 本次复盘交易日：{REVIEW_SESSION_DATE}（美股最近已完成常规交易日）")
print(f"🕒 Review运行时间：{get_us_time().strftime('%Y-%m-%d %H:%M:%S %Z')}")
print("=" * 60)


# ============================================================
# 1. 通用安全函数
# ============================================================

INVALID_STRINGS = {
    "", "nan", "none", "null", "n/a", "na", "nat",
    "观望", "坚决空仓", "绝对规避",
}

def clean_text(value, default=""):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    s = str(value).strip()
    return default if s.lower() in INVALID_STRINGS and default != "" else s

def safe_float(value, default=None):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    s = str(value).strip().replace(",", "").replace("$", "")
    if s.lower() in INVALID_STRINGS:
        return default
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return default
    try:
        x = float(m.group(0))
        return default if pd.isna(x) else x
    except Exception:
        return default

def safe_int(value, default=None):
    x = safe_float(value, None)
    if x is None:
        return default
    try:
        return int(x)
    except Exception:
        return default

def normalize_date(value):
    try:
        dt = pd.to_datetime(value, errors="coerce", format="mixed")
        if pd.isna(dt):
            return None
        if getattr(dt, "tzinfo", None) is not None:
            dt = dt.tz_localize(None)
        return dt
    except Exception:
        return None

def normalize_ticker_text(value):
    return clean_text(value).replace("\ufeff", "").strip().lstrip("$").strip()

def is_probable_us_ticker(value):
    s = normalize_ticker_text(value).upper()
    return bool(s and len(s) <= 8 and re.fullmatch(r"[A-Z]{1,6}(?:[-.][A-Z]{1,3})?", s))


# ============================================================
# 2. 公司名 -> Ticker
# ============================================================

COMPANY_TO_TICKER = {
    "nvidia": "NVDA", "nvidia corporation": "NVDA", "nvidia corp": "NVDA",
    "apple": "AAPL", "apple inc": "AAPL", "apple inc.": "AAPL",
    "intel": "INTC", "intel corporation": "INTC",
    "broadcom": "AVGO", "broadcom inc": "AVGO", "broadcom inc.": "AVGO",
    "supermicro": "SMCI", "super micro": "SMCI",
    "super micro computer": "SMCI",
    "super micro computer inc": "SMCI",
    "super micro computer inc.": "SMCI",
    "intuit": "INTU", "intuit inc": "INTU", "intuit inc.": "INTU",
    "sandisk": "SNDK", "sandisk corporation": "SNDK",
    "the trade desk": "TTD", "trade desk": "TTD",
    "the trade desk (the)": "TTD", "trade desk (the)": "TTD",
    "charles schwab": "SCHW", "charles schwab corp": "SCHW",
    "charles schwab corporation": "SCHW",
    "pfizer": "PFE", "pfizer inc": "PFE", "pfizer inc.": "PFE",
    "halliburton": "HAL", "halliburton company": "HAL",
    "eqt": "EQT", "eqt corporation": "EQT",
    "palo alto networks": "PANW", "palo alto networks inc": "PANW",
    "palo alto networks inc.": "PANW",
    "apa corporation": "APA", "southwest airlines": "LUV",
    "best buy": "BBY", "best buy co": "BBY", "best buy co inc": "BBY",
    "l3harris technologies": "LHX", "l3harris": "LHX",
}

def normalize_company_key(value):
    s = clean_text(value).lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def lookup_ticker_by_company_name(name):
    name = clean_text(name)
    if not name:
        return None
    key = normalize_company_key(name)
    for k, ticker in COMPANY_TO_TICKER.items():
        if normalize_company_key(k) == key:
            return ticker
    try:
        result = yf.Search(name, max_results=8)
        quotes = result.quotes if result is not None else []
        for q in quotes:
            symbol = clean_text(q.get("symbol"))
            qt = clean_text(q.get("quoteType")).upper()
            if qt in ("EQUITY", "ETF", "") and is_probable_us_ticker(symbol):
                return symbol.upper()
    except Exception as e:
        print(f"⚠️ 公司名称解析失败 [{name}]: {e}")
    return None

def resolve_ticker(raw_ticker, company_name=""):
    raw = normalize_ticker_text(raw_ticker)
    if is_probable_us_ticker(raw):
        return raw.upper()
    for candidate in (raw, clean_text(company_name)):
        if not candidate:
            continue
        key = normalize_company_key(candidate)
        for k, ticker in COMPANY_TO_TICKER.items():
            if normalize_company_key(k) == key:
                return ticker
    for candidate in (raw, clean_text(company_name)):
        if candidate:
            found = lookup_ticker_by_company_name(candidate)
            if found:
                return found
    return raw.upper() if raw else ""


# ============================================================
# 3. 行情
# ============================================================

def extract_single_ticker_df(hist_data, ticker, ticker_count):
    try:
        if hist_data is None or hist_data.empty:
            return pd.DataFrame()
        if ticker_count == 1:
            sub = hist_data.copy()
        else:
            if not isinstance(hist_data.columns, pd.MultiIndex):
                return pd.DataFrame()
            if ticker not in hist_data.columns.get_level_values(0):
                return pd.DataFrame()
            sub = hist_data[ticker].copy()
        required = ["Open", "High", "Low", "Close"]
        if any(c not in sub.columns for c in required):
            return pd.DataFrame()
        return sub.dropna(subset=required).copy()
    except Exception:
        return pd.DataFrame()

def download_ohlc_safe(tickers, period="60d", start=None, end=None):
    tickers = list(dict.fromkeys(
        normalize_ticker_text(t).upper()
        for t in tickers if normalize_ticker_text(t)
    ))
    if not tickers:
        return pd.DataFrame(), {}
    print(f"📡 yfinance 请求 {len(tickers)} 只真实 ticker...")
    try:
        kwargs = {
            "progress": False, "auto_adjust": True,
            "group_by": "ticker", "threads": False,
        }
        if start is not None:
            kwargs["start"] = start
        if end is not None:
            kwargs["end"] = end
        if start is None and end is None:
            kwargs["period"] = period
        hist = yf.download(tickers, **kwargs)
    except Exception as e:
        print(f"⚠️ 批量行情下载失败：{e}")
        return pd.DataFrame(), {}
    if hist is None or hist.empty:
        print("⚠️ yfinance 没有返回任何行情。")
        return pd.DataFrame(), {}
    rows, latest = [], {}
    for ticker in tickers:
        sub = extract_single_ticker_df(hist, ticker, len(tickers))
        if sub.empty:
            print(f"⚠️ 无法获取 {ticker} OHLC，跳过该 ticker。")
            continue
        for dt, row in sub.iterrows():
            o, h, l, c = (safe_float(row.get(x)) for x in ("Open", "High", "Low", "Close"))
            if None in (o, h, l, c):
                continue
            rows.append({"Ticker": ticker, "Date": dt, "open": o, "high": h, "low": l, "close": c})
        try:
            r = sub.iloc[-1]
            o, h, l, c = (safe_float(r.get(x)) for x in ("Open", "High", "Low", "Close"))
            if None not in (o, h, l, c):
                latest[ticker] = {"open": o, "high": h, "low": l, "close": c}
        except Exception:
            pass
    df_all = pd.DataFrame(rows)
    print(f"✅ 成功获得 {len(latest)} / {len(tickers)} 只 ticker 的 OHLC。")
    return df_all, latest

def _normalize_market_dates(series):
    """统一把 yfinance 时间戳转换为美国东部本地的无时区日期，避免 TZ 导致目标日全匹配失败。"""
    dt = pd.to_datetime(series, errors="coerce", format="mixed")
    try:
        tz = getattr(dt.dt, "tz", None)
    except Exception:
        tz = None
    if tz is not None:
        try:
            dt = dt.dt.tz_convert(US_TZ).dt.tz_localize(None)
        except Exception:
            try:
                dt = dt.dt.tz_localize(None)
            except Exception:
                pass
    else:
        try:
            dt = dt.dt.tz_localize(None)
        except Exception:
            pass
    return dt.dt.normalize()


def get_exact_date_ohlc(df_hist, ticker, target_date):
    try:
        if df_hist is None or df_hist.empty:
            return None
        target = pd.Timestamp(target_date).normalize()
        sub = df_hist[df_hist["Ticker"].astype(str).str.upper() == str(ticker).upper()].copy()
        if sub.empty:
            return None
        dates = _normalize_market_dates(sub["Date"])
        exact = sub.loc[dates.eq(target)].copy()
        if exact.empty:
            return None
        r = exact.sort_values("Date").iloc[-1]
        return {k: safe_float(r.get(v)) for k, v in {
            "open": "open", "high": "high", "low": "low", "close": "close"
        }.items()}
    except Exception:
        return None

def get_live_quote_bootstrap(ticker):
    ticker = normalize_ticker_text(ticker).upper()
    if not is_probable_us_ticker(ticker):
        return None, None
    try:
        fi = yf.Ticker(ticker).fast_info
        op = safe_float(fi.get("open") if hasattr(fi, "get") else None)
        last = safe_float(fi.get("last_price") if hasattr(fi, "get") else None)
        return op, last
    except Exception as e:
        print(f"⚠️ 实时价格获取失败 {ticker}: {e}")
        return None, None


# ============================================================
# 4. 账本
# ============================================================

TRADE_HISTORY = "trade_history.csv"
REVIEW_HISTORY = "review_history.csv"
OPTION_LOG_FILE = "option_strategies.csv"

TRADE_COLUMNS = [
    "Date","Ticker","Name","Tag","Score","Price","RSI","Bias","Hold_Period",
    "Stop_Loss","Stop_Method","Trail_Stop","Exit_Date","Exit_Price","Status",
    "Close_Price","技术评分","技术确认数","技术确认信号","估值评分","PE_TTM","PE_Forward","EPS_TTM","PB","Revenue_Growth","Earnings_Growth","ROE","Profit_Margin","Market_Cap","Avg_Dollar_Volume_20D","Fundamental_Score","Event_Score","Technical_Score_25","Risk_Liquidity_Score","Quant_Score","AI_Score","Final_Score",
    "MA20","MA50","ATR_Pct","MACD金叉","周线共振","KDJ_J回升","量能放大","周期共振",
    "Review_Risk_Status","Review_Risk_Date","Review_Stop_Distance_Pct","Review_Risk_Note"
]

REVIEW_COLUMNS = [
    "Review_Date","Ticker","Name","Tag","Rec_Date","Rec_Price","Cur_Price",
    "Days_Held","PnL_Pct","Maturity_PnL","Hold_Period","Stop_Loss","Stop_Method",
    "Trail_Stop","Rec_Count","Status","Score","Review_Risk_Status",
    "Review_Risk_Date","Review_Stop_Distance_Pct","Review_Risk_Note",
    "Option_Type","Strike","Expiry",
    "Price_5D","PnL_5D","Price_10D","PnL_10D","Price_20D","PnL_20D","Review_Stage"
]

def ensure_trade_history_columns():
    if not os.path.exists(TRADE_HISTORY) or os.path.getsize(TRADE_HISTORY) == 0:
        return
    try:
        d = pd.read_csv(TRADE_HISTORY, dtype=str, keep_default_na=False)
        for c in TRADE_COLUMNS:
            if c not in d.columns:
                d[c] = ""
        d[TRADE_COLUMNS].to_csv(TRADE_HISTORY, index=False, encoding="utf-8")
    except Exception as e:
        print(f"⚠️ trade_history.csv 表结构检查失败：{e}")

def load_trade_history():
    if not os.path.exists(TRADE_HISTORY):
        return pd.DataFrame()
    try:
        d = pd.read_csv(TRADE_HISTORY, dtype=str, keep_default_na=False, on_bad_lines="skip")
        if "Date" not in d.columns or "Ticker" not in d.columns:
            return pd.DataFrame()
        if "Name" not in d.columns:
            d["Name"] = ""
        d["Date"] = pd.to_datetime(d["Date"], errors="coerce", format="mixed")
        return d.dropna(subset=["Date"]).copy()
    except Exception as e:
        print(f"❌ 读取 trade_history.csv 失败：{e}")
        return pd.DataFrame()

def safe_record_price(row):
    """正式买入价 = trade_history 的 Price 字段 = 推荐日真实 Open。

    禁止 fallback 到 Scan_Ref_Price / Close_Price / Prev_Close / 实时 quote：
    这些都不是正式买入价。Open 未产生（盘前新仓）→ 返回 None，等回补。
    """
    p = safe_float(row.get("Price"))
    return p if (p is not None and p > 0) else None

def find_existing_record(df_existing, date_value, ticker):
    if df_existing.empty:
        return False
    target = normalize_date(date_value)
    if target is None:
        return False
    try:
        return bool((
            (df_existing["Date"] == target) &
            (df_existing["Ticker"].astype(str).str.upper() == str(ticker).upper())
        ).any())
    except Exception:
        return False


# ============================================================
# 4.5 推荐价回填：避免早期 Observation 永久缺少 Rec_Price
# ============================================================
def _build_recommendation_price_lookup():
    """从 review_history / pending / trade_history 建立 Date+Ticker+Tag 推荐价兜底。"""
    lookup = {}

    # 优先读取 review_history：这里往往保留了早期事件的有效 Rec_Price。
    if os.path.exists(REVIEW_HISTORY) and os.path.getsize(REVIEW_HISTORY) > 0:
        try:
            rh = pd.read_csv(REVIEW_HISTORY, dtype=str, keep_default_na=False, on_bad_lines="skip")
            for _, row in rh.iterrows():
                rec_date = normalize_date(row.get("Rec_Date"))
                ticker = resolve_ticker(row.get("Ticker"), row.get("Name"))
                tag = clean_text(row.get("Tag"))
                price = safe_float(row.get("Rec_Price"))
                if rec_date is not None and ticker and price is not None and price > 0:
                    key = (rec_date.strftime("%Y-%m-%d"), ticker.upper(), tag)
                    lookup.setdefault(key, price)
        except Exception as e:
            print(f"⚠️ 推荐价回填：读取 review_history 失败：{e}")

    # pending 是 Scan 原始推荐价的更直接来源；只在没有有效值时覆盖。
    for filename in sorted(glob.glob("us_stocks_pending_*.csv") + glob.glob("us_stocks_pending_*.csv.processed")):
        m = re.search(r"us_stocks_pending_(\d{8})\.csv(?:\.processed)?$", os.path.basename(filename))
        if not m:
            continue
        rec_date = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
        try:
            d = pd.read_csv(filename, dtype=str, keep_default_na=False, on_bad_lines="skip")
            for _, row in d.iterrows():
                ticker = resolve_ticker(row.get("Ticker"), row.get("Name"))
                tag = clean_text(row.get("Tag"))
                price = safe_float(row.get("Scan_Ref_Price"))
                if price is None:
                    price = safe_float(row.get("Price"))
                if ticker and price is not None and price > 0:
                    key = (rec_date, ticker.upper(), tag)
                    lookup[key] = price
        except Exception:
            continue

    return lookup


def backfill_missing_trade_history_recommendation_prices():
    """把历史账本中缺失的 Price 用已有 Review/Scan 推荐价持久化补回。"""
    if not os.path.exists(TRADE_HISTORY) or os.path.getsize(TRADE_HISTORY) == 0:
        return 0
    try:
        d = pd.read_csv(TRADE_HISTORY, dtype=str, keep_default_na=False, on_bad_lines="skip")
        lookup = _build_recommendation_price_lookup()
        changed = 0
        for idx, row in d.iterrows():
            current = safe_float(row.get("Price"))
            if current is not None and current > 0:
                continue
            rec_date = normalize_date(row.get("Date"))
            ticker = resolve_ticker(row.get("Ticker"), row.get("Name"))
            tag = clean_text(row.get("Tag"))
            if rec_date is None or not ticker:
                continue
            key = (rec_date.strftime("%Y-%m-%d"), ticker.upper(), tag)
            fallback = lookup.get(key)
            if fallback is not None and fallback > 0:
                d.at[idx, "Price"] = str(fallback)
                changed += 1
        if changed:
            d.to_csv(TRADE_HISTORY, index=False, encoding="utf-8")
            print(f"🔧 [推荐价回填] trade_history.csv 持久化补回 {changed} 条缺失推荐价。")
        return changed
    except Exception as e:
        print(f"⚠️ 推荐价回填失败：{e}")
        return 0

# ============================================================
# 5. pending -> trade_history
# ============================================================

def recalibrate_stop_loss(stop_loss_str, scan_ref_price, real_open_price):
    try:
        old = safe_float(stop_loss_str)
        ref = safe_float(scan_ref_price)
        op = safe_float(real_open_price)
        if None in (old, ref, op) or old <= 0 or ref <= 0 or op <= 0:
            return stop_loss_str
        new_val = round(old * op / ref, 2)
        return f"${new_val}" if str(stop_loss_str).strip().startswith("$") else str(new_val)
    except Exception:
        return stop_loss_str

def supplement_us_stocks_from_pending():
    files = sorted(
        glob.glob("us_stocks_pending_*.csv") +
        glob.glob("us_stocks_pending_*.csv.processed")
    )
    cutoff = (get_us_time().replace(tzinfo=None) - datetime.timedelta(days=30)).date()
    pending = []
    for f in files:
        name = os.path.basename(f)
        m = re.search(r"us_stocks_pending_(\d{8})\.csv(?:\.processed)?$", name)
        if not m:
            continue
        try:
            day = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
        except Exception:
            continue
        if name.endswith(".processed") and day < cutoff:
            continue
        pending.append(f)
    if not pending:
        print("📋 无待确认/恢复美股文件，跳过补充。")
        return
    ensure_trade_history_columns()
    existing = load_trade_history()
    print(f"📋 发现 {len(pending)} 份待确认文件。")

    for pf in pending:
        m = re.search(r"us_stocks_pending_(\d{8})\.csv(?:\.processed)?$", os.path.basename(pf))
        if not m:
            continue
        raw_date = m.group(1)
        target_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        try:
            p = pd.read_csv(pf, dtype=str, keep_default_na=False, on_bad_lines="skip")
            if p.empty:
                if not pf.endswith(".processed"):
                    os.rename(pf, pf + ".processed")
                continue
            if "Ticker" not in p.columns:
                print(f"❌ {pf} 没有 Ticker 列。")
                continue

            resolved = []
            for _, row in p.iterrows():
                rt = resolve_ticker(row.get("Ticker"), row.get("Name"))
                if rt:
                    resolved.append((row, rt))
            tickers = list(dict.fromkeys(t for _, t in resolved if is_probable_us_ticker(t)))
            hist, _ = download_ohlc_safe(tickers, period="10d")
            target_map = {}
            for t in tickers:
                exact = get_exact_date_ohlc(hist, t, target_date)
                if exact:
                    target_map[t] = exact

            new_rows, missing = [], []
            for row, ticker in resolved:
                if find_existing_record(existing, target_date, ticker):
                    continue
                pdx = target_map.get(ticker)
                op = safe_float(pdx.get("open")) if pdx else None
                cp = safe_float(pdx.get("close")) if pdx else None
                if target_date == today_us_str() and cp is None:
                    _, live_last = get_live_quote_bootstrap(ticker)
                    cp = live_last
                # 注意：op（正式买入价 = 推荐日 Open）在盘前/盘中尚未产生时必须保持 None，
                # 绝不 get_live_quote_bootstrap() 把实时价假装成 Open。Price 列随之留空，
                # 由后续 Review 的 backfill_rec_price() 取得 Rec_Date 真实 Open 后幂等回填。
                if op is None or cp is None:
                    missing.append(ticker)
                scan_ref = row.get("Scan_Ref_Price", row.get("Price", ""))
                stop = row.get("Stop_Loss", "N/A")
                if op is not None:
                    stop = recalibrate_stop_loss(stop, scan_ref, op)
                new_rows.append({
                    "Date": target_date,
                    "Ticker": ticker,
                    "Name": clean_text(row.get("Name")),
                    "Tag": clean_text(row.get("Tag")),
                    "Score": clean_text(row.get("Score"), "N/A"),
                    "Price": op if op is not None else "",
                    "RSI": clean_text(row.get("RSI")),
                    "Bias": clean_text(row.get("Bias")),
                    "Hold_Period": "动态持有",
                    "Stop_Loss": stop,
                    "Stop_Method": clean_text(row.get("Stop_Method"), "MA20/MA50 + ATR + MACD/KDJ"),
                    "Trail_Stop": stop,
                    "Exit_Date": "",
                    "Exit_Price": "",
                    "Status": "Active",
                    "Close_Price": cp if cp is not None else "",
                    "技术评分": clean_text(row.get("技术评分")),
                    "技术确认数": clean_text(row.get("技术确认数")),
                    "技术确认信号": clean_text(row.get("技术确认信号")),
                    "估值评分": clean_text(row.get("估值评分")),
                    "Revenue_Growth": clean_text(row.get("Revenue_Growth")), "Earnings_Growth": clean_text(row.get("Earnings_Growth")), "ROE": clean_text(row.get("ROE")), "Profit_Margin": clean_text(row.get("Profit_Margin")), "Market_Cap": clean_text(row.get("Market_Cap")), "Avg_Dollar_Volume_20D": clean_text(row.get("Avg_Dollar_Volume_20D")), "Fundamental_Score": clean_text(row.get("Fundamental_Score")), "Event_Score": clean_text(row.get("Event_Score")), "Technical_Score_25": clean_text(row.get("Technical_Score_25")), "Risk_Liquidity_Score": clean_text(row.get("Risk_Liquidity_Score")), "Quant_Score": clean_text(row.get("Quant_Score")), "AI_Score": clean_text(row.get("AI_Score")), "Final_Score": clean_text(row.get("Final_Score")),
                    "PE_TTM": clean_text(row.get("PE_TTM")),
                    "PE_Forward": clean_text(row.get("PE_Forward")),
                    "EPS_TTM": clean_text(row.get("EPS_TTM")),
                    "PB": clean_text(row.get("PB")),
                    "MA20": "",
                    "MA50": "",
                    "ATR_Pct": clean_text(row.get("ATR_Pct")),
                    "MACD金叉": clean_text(row.get("MACD金叉")),
                    "周线共振": clean_text(row.get("周线共振")),
                    "KDJ_J回升": clean_text(row.get("KDJ_J回升")),
                    "量能放大": clean_text(row.get("量能放大")),
                    "周期共振": clean_text(row.get("周期共振")),
                    "Review_Risk_Status": "",
                    "Review_Risk_Date": "",
                    "Review_Stop_Distance_Pct": "",
                    "Review_Risk_Note": "",
                })
            if missing:
                print(f"⚠️ 以下 ticker 暂时没有 OHLC：{missing}")
            if new_rows:
                nd = pd.DataFrame(new_rows)
                for c in TRADE_COLUMNS:
                    if c not in nd.columns:
                        nd[c] = ""
                nd = nd[TRADE_COLUMNS]
                if existing.empty:
                    final = nd
                else:
                    for c in TRADE_COLUMNS:
                        if c not in existing.columns:
                            existing[c] = ""
                    final = pd.concat([existing[TRADE_COLUMNS], nd], ignore_index=True)
                final.to_csv(TRADE_HISTORY, index=False, encoding="utf-8")
                existing = final
                print(f"✅ 新增 {len(new_rows)} 条美股记录。")
            if not pf.endswith(".processed"):
                os.rename(pf, pf + ".processed")
        except Exception as e:
            print(f"❌ 处理 {pf} 出错：{e}")


supplement_us_stocks_from_pending()
backfill_missing_trade_history_recommendation_prices()


def is_active_holding(status, exit_date=None):
    """动态持有口径：Status 为 空/Active/pending 且未设置 Exit_Date 的持仓视为 active。

    股票已是“动态持有”，不能因持仓超过 30 天就停止风险检查。
    Exit_Date 为 "N/A"/nan/空 等占位符时，一律视为"未退出"（只有真实日期才算已退出）。
    """
    st = clean_text(status).strip()
    ex = clean_text(exit_date).strip()
    if ex and ex.lower() in INVALID_STRINGS:
        ex = ""
    return st in ("", "Active", "pending") and ex == ""


def select_current_stop_loss(group_rows):
    """取一个生命周期分组内「最新一条有效 Stop_Loss」。

    从最晚 Date 行向前扫描，返回第一个 >0 的 Stop_Loss；
    若最新行 Stop_Loss 为空/无效，回退到更早的有效止损；
    没有任何有效值时返回 None。绝不返回 0/负数/空。
    """
    try:
        g = group_rows.sort_values("Date", ascending=False) if hasattr(group_rows, "sort_values") else group_rows
        for _, r in g.iterrows():
            sv = safe_float(r.get("Stop_Loss"))
            if sv is not None and sv > 0:
                return sv
    except Exception:
        pass
    return None


# 移动止损合理上界：相对入场价最多 2 倍。
# 依据：profit_lock_3_pct=50%（最高利润锁定档，drawdown 12%）→ 移动止损 ≈ 1.32x 入场价；
# 2.0 留足余量，同时排除 3.3x+ 的跨 ticker 污染 / 明显写错（MSTR 965/116、BSX 980/44、ORCL 505/152）。
MAX_TRAILING_RATIO = 2.0


def is_valid_existing_stop(old_stop, rec_price, reference_price=None):
    """判断 old_stop 是否可作为 trailing-stop floor（fail-closed，纯函数）。

    返回 bool：
      - True：old_stop 是合理的历史止损，可进入 max(old_stop, candidate)；
      - False：old_stop 明显异常（如 MSTR $965 vs 入场 $116），丢弃该 floor，
        改用当前技术候选重新建立止损。

    reference_price 参数保留用于将来扩展；当前不参与判定，避免误伤
    “价格已跌破合理止损”的正常触发场景（如 BKNG stop=184 vs 现价 162）。
    """
    if old_stop is None:
        return False
    try:
        v = float(old_stop)
    except (ValueError, TypeError):
        return False
    if not (v > 0 and v == v and v not in (float("inf"), float("-inf"))):
        return False
    if rec_price is not None:
        try:
            rp = float(rec_price)
        except (ValueError, TypeError):
            rp = None
        if rp is not None and rp > 0 and v > rp * MAX_TRAILING_RATIO:
            return False
    return True


def evaluate_stop_trigger(low, closep, openp, exec_stop):
    """统一快照下的止损触发判定（纯函数，离线可测，无需联网）。

    入参必须是同一交易日的真实 OHLC（low/close/open）与当前有效 Stop_Loss。
    返回 (trigger_result, exit_price)：
      - ("STOP_TRIGGERED", exit_price)   已确认跌破止损
      - ("NO_TRIGGER_INVALID_STOP", None) Stop_Loss 无效，不触发（仅跟踪 + warning）
      - ("DATA_MISSING", None)           无可靠 OHLC，不能猜测，不触发
      - ("CLEAR", None)                  未跌破
    exit_price：Gap Down 时若 Open < Stop 取 Open，否则取 Stop；
    Low 缺失但有可靠 Close<=Stop 时确认触发，exit 取 Stop（无 Open 可判缺口，保守）。
    """
    if not exec_stop or exec_stop <= 0:
        return "NO_TRIGGER_INVALID_STOP", None
    if low is not None and low <= exec_stop:
        exit_price = openp if (openp is not None and openp < exec_stop) else exec_stop
        return "STOP_TRIGGERED", exit_price
    if low is None and closep is not None and closep <= exec_stop:
        return "STOP_TRIGGERED", exec_stop
    if low is None and closep is None:
        return "DATA_MISSING", None
    return "CLEAR", None


def compute_change_1d(close, prev_close):
    """Change_1D = (Close - Prev_Close) / Prev_Close * 100。

    Close 与 Prev_Close 必须来自同一份快照（同一交易日 OHLC 与前一真实交易日收盘），
    禁止跨数据源拼凑；否则无法得到自洽的涨跌幅（例如 BKNG 162.16 vs 207.74 应为 -21.94%，
    而不是 -0.11%）。
    """
    if close is None or prev_close is None or prev_close <= 0:
        return None
    return round((close - prev_close) / prev_close * 100, 4)


def _prior_regular_close(df_hist, ticker, before_date):
    """返回 before_date 之前最近一个真实交易日的收盘价（Prev_Close 的来源）。

    严格取 date < before_date 的最后一根真实 OHLCV bar 的 close；无则返回 None。
    """
    try:
        if df_hist is None or df_hist.empty:
            return None
        sub = df_hist[df_hist["Ticker"].astype(str).str.upper() == str(ticker).upper()].copy()
        if sub.empty:
            return None
        d = _normalize_market_dates(sub["Date"])
        base = pd.Timestamp(before_date).normalize()
        sub = sub[d < base].sort_values("Date")
        if sub.empty:
            return None
        return safe_float(sub.iloc[-1].get("close"))
    except Exception:
        return None


df = load_trade_history()
if df.empty:
    print("无交易账本或账本为空，退出。")
    sys.exit(0)

# 动态持有：active holdings 必须从完整 trade_history 识别，不能按“最近30天” cutoff 过滤。
# 已超过 30 天但仍 Status=Active（且未设置 Exit_Date）的真实持仓，必须进入今天的止损检查。
# 历史记录仍可继续用于 KPI / milestone；这里只决定“今天是否还要做风控”。
active_mask = df.apply(lambda r: is_active_holding(r.get("Status"), r.get("Exit_Date")), axis=1)
active_holdings = df[active_mask].copy()
# recent_picks 仍保留完整历史（closed / 已退出由下方 Status+Exit_Date 过滤排除）；
# 分类段依此重新计算，旧仓不会被 30 天 cutoff 挡在风控之外。
recent_picks = df.copy()
if recent_picks.empty:
    print("无交易记录，退出。")
    sys.exit(0)

for c in ("Hold_Period","Stop_Loss","Score","Name","Tag","Price","Close_Price","Status"):
    if c not in recent_picks.columns:
        recent_picks[c] = ""
recent_picks["Hold_Period"] = "动态持有"


# ============================================================
# 6. 行情准备
# ============================================================

# OHLC 只下载真实 active holdings（不受 30 天限制），避免对全量历史 ticker 拉取行情。
# active holdings 已包含“超 30 天但仍 Active”的持仓，因此它们今天的止损检查不会漏。
clean_tickers = []
_src = active_holdings if not active_holdings.empty else recent_picks
for t in _src["Ticker"].astype(str):
    rt = resolve_ticker(t)
    if rt and is_probable_us_ticker(rt):
        clean_tickers.append(rt)
clean_tickers = list(dict.fromkeys(clean_tickers))

print(f"📡 获取 {len(clean_tickers)} 只真实美股 ticker 的 90日 OHLC...")
df_hist_all, ohlc_map_today = download_ohlc_safe(clean_tickers, period="90d")

# price_map_today = 用于当前跟踪/期权正股报价：今天收盘 > 最近一个有效交易日收盘 > fast_info
# ohlc_map_today = 只有本次 Review 交易日（最近已完成常规交易日）的完整 OHLC 才能用于该交易日止损触发判断。
latest_regular_map = dict(ohlc_map_today)
price_map_today = {}
price_source_map = {}
verified_review_session_ohlc = set()
missing_review_session_tickers = []
for ticker in clean_tickers:
    exact = get_exact_date_ohlc(df_hist_all, ticker, REVIEW_SESSION_DATE)
    if exact and exact.get("close") is not None:
        ohlc_map_today[ticker] = exact
        price_map_today[ticker] = exact["close"]
        price_source_map[ticker] = "today_regular_close"
        verified_review_session_ohlc.add(ticker)
    else:
        missing_review_session_tickers.append(ticker)

# 第一轮批量数据若因 Yahoo 临时缓存/时间轴问题漏掉目标交易日，
# 再用明确 start/end 的目标日窗口做一次批量救援。
if missing_review_session_tickers:
    try:
        target_start = pd.Timestamp(REVIEW_SESSION_DATE).strftime("%Y-%m-%d")
        target_end = (pd.Timestamp(REVIEW_SESSION_DATE) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"🔁 [目标日OHLC救援] {REVIEW_SESSION_DATE} 仍缺 {len(missing_review_session_tickers)} 只，进行精确日期批量重取...")
        rescue_hist, rescue_latest = download_ohlc_safe(
            missing_review_session_tickers,
            start=target_start,
            end=target_end,
        )
        for ticker in missing_review_session_tickers:
            exact = get_exact_date_ohlc(rescue_hist, ticker, REVIEW_SESSION_DATE)
            if exact and exact.get("close") is not None:
                ohlc_map_today[ticker] = exact
                price_map_today[ticker] = exact["close"]
                price_source_map[ticker] = "today_regular_close"
                verified_review_session_ohlc.add(ticker)
    except Exception as e:
        print(f"⚠️ [目标日OHLC救援] 失败：{e}")

for ticker in clean_tickers:
    if ticker in verified_review_session_ohlc:
        continue
    latest = latest_regular_map.get(ticker)
    if latest and latest.get("close") is not None:
        price_map_today[ticker] = latest["close"]
        price_source_map[ticker] = "latest_regular_close"
        print(f"ℹ️ {ticker} {REVIEW_SESSION_DATE} OHLC未返回，使用最近有效交易日收盘价跟踪：{latest['close']}")

for ticker in clean_tickers:
    if ticker in price_map_today:
        continue
    op, last = get_live_quote_bootstrap(ticker)
    if last is not None:
        price_map_today[ticker] = last
        price_source_map[ticker] = "fast_info"
        # fast_info 只有报价时可用于当前跟踪，不足以作为完整当日OHLC触发止损。
        print(f"🔄 {ticker} 使用实时价格兜底：{last}")


# ============================================================
# 7. 期权
# ============================================================

def load_option_positions():
    if not os.path.exists(OPTION_LOG_FILE) or os.path.getsize(OPTION_LOG_FILE) == 0:
        return pd.DataFrame()
    try:
        d = pd.read_csv(OPTION_LOG_FILE, dtype=str, keep_default_na=False)
        required = [
            "Ticker","OptionType","Strike","LongStrike","ShortStrike","Strategy",
            "Expiry","EntryPrice","NetDebit","LongPrice","Status","EntryDate"
        ]
        for c in required:
            if c not in d.columns:
                d[c] = ""
        d = d[d["Status"].astype(str).str.strip() == "Active"].copy()
        if not d.empty:
            d["Expiry"] = pd.to_datetime(d["Expiry"], errors="coerce", format="mixed")
        return d
    except Exception as e:
        print(f"⚠️ 读取期权账本失败：{e}")
        return pd.DataFrame()

def close_option_position(row, close_price, close_date, reason):
    try:
        d = pd.read_csv(OPTION_LOG_FILE, dtype=str, keep_default_na=False)
        for c in ("Status","Close_Date","Close_Price","PnL"):
            if c not in d.columns:
                d[c] = ""
        ticker = clean_text(row.get("Ticker")).upper()
        expiry = clean_text(row.get("Expiry"))
        dt = pd.to_datetime(d["Expiry"], errors="coerce", format="mixed").dt.strftime("%Y-%m-%d")
        target = pd.to_datetime(expiry, errors="coerce", format="mixed")
        target_s = target.strftime("%Y-%m-%d") if not pd.isna(target) else ""
        row_strategy = clean_text(row.get("Strategy"), "LONG_CALL").upper()
        row_strike = clean_text(row.get("Strike"), clean_text(row.get("LongStrike"), ""))
        mask = (
            d["Ticker"].astype(str).str.upper().eq(ticker) &
            dt.eq(target_s) &
            d["Status"].astype(str).str.strip().eq("Active") &
            d["Strategy"].astype(str).str.upper().eq(row_strategy) &
            d["Strike"].astype(str).eq(row_strike)
        )
        if not mask.any():
            return 0.0
        entry = safe_float(row.get("EntryPrice"), 0.0) or 0.0
        qty = safe_float(row.get("Quantity"), 1.0) or 1.0
        opt_type = clean_text(row.get("OptionType")).upper()
        pnl = ((close_price - entry) if opt_type == "CALL" else (entry - close_price)) * qty * 100.0
        d.loc[mask, "Status"] = "Closed"
        d.loc[mask, "Close_Date"] = close_date
        d.loc[mask, "Close_Price"] = close_price
        d.loc[mask, "PnL"] = round(pnl, 2)
        d.to_csv(OPTION_LOG_FILE, index=False, encoding="utf-8")
        return round(pnl, 2)
    except Exception as e:
        print(f"⚠️ 期权平仓失败：{e}")
        return 0.0

def process_options(price_map):
    d = load_option_positions()
    if d.empty:
        print("📋 无活跃期权持仓。")
        return []
    today = get_us_time().date()
    out = []
    for _, row in d.iterrows():
        expiry_dt = pd.to_datetime(row.get("Expiry"), errors="coerce", format="mixed")
        if pd.isna(expiry_dt) or expiry_dt.date() > today:
            continue
        underlying = resolve_ticker(row.get("Ticker"))
        cur = price_map.get(underlying)
        if cur is None:
            _, cur = get_live_quote_bootstrap(underlying)
        if cur is None:
            continue
        opt_type = clean_text(row.get("OptionType")).upper()
        strategy = clean_text(row.get("Strategy"), "LONG_CALL").upper()
        strike = safe_float(row.get("Strike"), safe_float(row.get("LongStrike"), 0.0))
        short_strike = safe_float(row.get("ShortStrike"))
        if strategy == "CALL_DEBIT_SPREAD" and opt_type == "CALL" and short_strike and short_strike > strike:
            intrinsic = max(0.0, min(short_strike - strike, cur - strike))
        elif opt_type == "CALL":
            intrinsic = max(0.0, cur - strike)
        else:
            intrinsic = max(0.0, strike - cur)
        if strategy == "SHORT_PUT":
            reason = "到期价内/可能指派" if intrinsic > 0 else "到期价外/保留全部权利金"
        elif strategy == "CALL_DEBIT_SPREAD":
            reason = "价差到期结算" if intrinsic > 0 else "价差到期归零"
        else:
            reason = "价内行权" if intrinsic > 0 else "价外归零"
        pnl = close_option_position(row, intrinsic, today.strftime("%Y-%m-%d"), reason)
        out.append({
            "ticker": underlying, "option_type": opt_type, "strike": strike,
            "short_strike": short_strike, "strategy": strategy,
            "expiry": expiry_dt.strftime("%Y-%m-%d"),
            "entry_price": safe_float(row.get("EntryPrice"), 0.0) or 0.0,
            "close_price": intrinsic, "pnl": pnl, "reason": reason
        })
    return out

def _option_quote_mid(row):
    """优先 bid/ask mid，其次 last；只返回正数。"""
    try:
        bid=safe_float(row.get("bid")); ask=safe_float(row.get("ask")); last=safe_float(row.get("lastPrice"))
        if bid is not None and ask is not None and bid>0 and ask>=bid:
            return (bid+ask)/2.0
        if last is not None and last>0:
            return last
        if ask is not None and ask>0:
            return ask
        return bid
    except Exception:
        return None


def _load_option_chain_exact(ticker, expiry):
    """Review 专用：yfinance -> Yahoo options API 两层读取指定到期日真实期权链。"""
    target = pd.Timestamp(expiry).strftime("%Y-%m-%d")
    try:
        obj=yf.Ticker(ticker)
        chain=obj.option_chain(target)
        calls, puts = chain.calls.copy(), chain.puts.copy()
        if not calls.empty or not puts.empty:
            return calls, puts
    except Exception as e:
        print(f"⚠️ [期权Review] yfinance链读取失败 {ticker}: {e}")
    try:
        headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153.0 Safari/537.36",
            "Accept":"application/json,text/plain,*/*",
        }
        base=f"https://query2.finance.yahoo.com/v7/finance/options/{urllib.parse.quote(str(ticker),safe='')}"
        ts=int(pd.Timestamp(target, tz="UTC").timestamp())
        req=urllib.request.Request(base+"?"+urllib.parse.urlencode({"date":ts}), headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload=json.loads(resp.read().decode("utf-8",errors="ignore"))
        result=(((payload.get("optionChain") or {}).get("result") or [None])[0])
        if result:
            opt=(result.get("options") or [{}])[0]
            return pd.DataFrame(opt.get("calls") or []), pd.DataFrame(opt.get("puts") or [])
    except Exception as e:
        print(f"⚠️ [期权Review] Yahoo直连链读取失败 {ticker}: {e}")
    return pd.DataFrame(), pd.DataFrame()


def _review_wall_from_chain(chain):
    """返回可解释的实时 Wall：优先 OI Wall；OI 缺失时退化为成交量代理，不冒充 OI。"""
    if chain is None or chain.empty:
        return {"strike":None,"oi":None,"volume":None,"source":"NO_CHAIN"}
    w = chain.copy()
    w["strike"] = pd.to_numeric(w.get("strike"), errors="coerce")
    w["openInterest"] = pd.to_numeric(w.get("openInterest"), errors="coerce")
    w["volume"] = pd.to_numeric(w.get("volume"), errors="coerce").fillna(0)
    w = w[w["strike"].notna()].copy()
    oi = w[w["openInterest"].fillna(0) > 0]
    if not oi.empty:
        r = oi.sort_values(["openInterest","volume","strike"], ascending=[False,False,True]).iloc[0]
        return {"strike":safe_float(r.get("strike")),"oi":safe_float(r.get("openInterest")),"volume":safe_float(r.get("volume"),0),"source":"openInterest"}
    vol = w[w["volume"].fillna(0) > 0]
    if not vol.empty:
        r = vol.sort_values(["volume","strike"], ascending=[False,True]).iloc[0]
        return {"strike":safe_float(r.get("strike")),"oi":None,"volume":safe_float(r.get("volume"),0),"source":"volume_proxy"}
    return {"strike":None,"oi":None,"volume":None,"source":"NO_WALL_DATA"}


def build_active_option_reviews(price_map):
    """对所有 Active 期权做确定性盘后复盘；不依赖 AI 是否愿意输出期权段落。"""
    d=load_option_positions()
    if d.empty:
        return []
    out=[]
    for _,row in d.iterrows():
        ticker=resolve_ticker(row.get("Ticker"))
        expiry_dt=pd.to_datetime(row.get("Expiry"),errors="coerce",format="mixed")
        if not ticker or pd.isna(expiry_dt):
            continue
        spot=safe_float(price_map.get(ticker))
        if spot is None:
            # 期权账本历史回填可能缺失当前正股价；先用账本入场正股价，再尝试实时。
            spot=safe_float(row.get("UnderlyingPrice"))
        if spot is None:
            _, spot=get_live_quote_bootstrap(ticker)
        strategy=clean_text(row.get("Strategy"),"LONG_CALL").upper()
        opt_type=clean_text(row.get("OptionType")).upper()
        long_strike=safe_float(row.get("LongStrike"),safe_float(row.get("Strike")))
        short_strike=safe_float(row.get("ShortStrike"))
        entry=safe_float(row.get("EntryPrice"),safe_float(row.get("NetDebit")))
        qty=safe_float(row.get("Quantity"),1) or 1
        max_loss=safe_float(row.get("MaxLoss"),entry*100 if entry else None)
        max_profit=safe_float(row.get("MaxProfit"))
        breakeven=safe_float(row.get("BreakEven"))
        dte=max(0,(expiry_dt.date()-pd.Timestamp(REVIEW_SESSION_DATE).date()).days)

        mark=None; mark_source="N/A"; long_mark=None; short_mark=None
        intrinsic=None
        if spot is not None and long_strike is not None:
            if strategy=="CALL_DEBIT_SPREAD" and short_strike is not None and short_strike>long_strike:
                intrinsic=max(0.0,min(short_strike-long_strike,spot-long_strike))
            elif strategy=="SHORT_PUT":
                intrinsic=max(0.0,long_strike-spot)
            elif opt_type=="CALL":
                intrinsic=max(0.0,spot-long_strike)

        calls,puts=_load_option_chain_exact(ticker,expiry_dt)
        call_wall_live = _review_wall_from_chain(calls)
        put_wall_live = _review_wall_from_chain(puts)
        try:
            if strategy=="SHORT_PUT":
                if not puts.empty and long_strike is not None:
                    pr=puts.iloc[(pd.to_numeric(puts["strike"],errors="coerce")-long_strike).abs().argsort()[:1]].iloc[0]
                    long_mark=_option_quote_mid(pr)
            else:
                if not calls.empty and long_strike is not None:
                    lr=calls.iloc[(pd.to_numeric(calls["strike"],errors="coerce")-long_strike).abs().argsort()[:1]].iloc[0]
                    long_mark=_option_quote_mid(lr)
                if strategy=="CALL_DEBIT_SPREAD" and not calls.empty and short_strike is not None:
                    sr=calls.iloc[(pd.to_numeric(calls["strike"],errors="coerce")-short_strike).abs().argsort()[:1]].iloc[0]
                    short_mark=_option_quote_mid(sr)
        except Exception:
            long_mark=None; short_mark=None

        if strategy=="CALL_DEBIT_SPREAD" and long_mark is not None and short_mark is not None:
            mark=max(0.0,long_mark-short_mark); mark_source="Yahoo option chain mid/last"
        elif strategy in {"LONG_CALL","SHORT_PUT"} and long_mark is not None:
            mark=long_mark; mark_source="Yahoo option chain mid/last"
        unrealized=None
        if mark is not None and entry is not None:
            if strategy=="SHORT_PUT":
                unrealized=round((entry-mark)*qty*100,2)
            else:
                unrealized=round((mark-entry)*qty*100,2)
        intrinsic_floor_pnl=None
        if intrinsic is not None and entry is not None:
            intrinsic_floor_pnl=round(((entry-intrinsic) if strategy=="SHORT_PUT" else (intrinsic-entry))*qty*100,2)

        risk=[]
        if dte<=14: risk.append("临近到期")
        if strategy=="SHORT_PUT":
            if spot is not None and long_strike is not None and spot <= long_strike: risk.append("正股进入/低于执行价，存在指派风险")
            if breakeven is not None and spot is not None: risk.append("已站上有效接货价" if spot>=breakeven else "跌破有效接货价")
            if unrealized is not None and entry and mark is not None and mark>=entry*1.5: risk.append("回补成本较入场权利金上升≥50%")
            if dte<=7 and spot is not None and long_strike is not None and spot<long_strike: risk.append("临近到期且价内，提前/到期指派风险提高")
            earnings_days=safe_float(row.get("EarningsDays"))
            if earnings_days is not None and 0<=earnings_days<=14: risk.append("财报临近，跳空风险提高")
        else:
            if spot is not None and long_strike is not None and spot<long_strike: risk.append("正股低于Long Strike")
            if breakeven is not None and spot is not None:
                risk.append("已站上盈亏平衡" if spot>=breakeven else "尚未站上盈亏平衡")
            if unrealized is not None and entry and mark is not None and mark<=entry*0.5: risk.append("权利金回撤≥50%")
            if strategy=="CALL_DEBIT_SPREAD" and short_strike is not None and spot is not None and spot>=short_strike: risk.append("正股已进入/超过价差上限区")
        status="；".join(risk) if risk else "当前未触发程序化高风险条件"

        out.append({
            "ticker":ticker,"name":clean_text(row.get("Name"),ticker),"strategy":strategy,"option_type":opt_type,
            "expiry":expiry_dt.strftime("%Y-%m-%d"),"dte":dte,"spot":spot,
            "long_strike":long_strike,"short_strike":short_strike,"entry":entry,
            "mark":mark,"mark_source":mark_source,"unrealized_pnl":unrealized,
            "intrinsic":intrinsic,"intrinsic_floor_pnl":intrinsic_floor_pnl,"max_loss":max_loss,"max_profit":max_profit,
            "breakeven":breakeven,"delta":safe_float(row.get("Delta")),"iv":safe_float(row.get("IV")),
            "call_wall":call_wall_live.get("strike") if call_wall_live.get("strike") is not None else safe_float(row.get("CallWall")),
            "put_wall":put_wall_live.get("strike") if put_wall_live.get("strike") is not None else safe_float(row.get("PutWall")),
            "call_wall_oi":call_wall_live.get("oi") if call_wall_live.get("oi") is not None else safe_float(row.get("CallWallOI")),
            "put_wall_oi":put_wall_live.get("oi") if put_wall_live.get("oi") is not None else safe_float(row.get("PutWallOI")),
            "call_wall_volume":call_wall_live.get("volume"),"put_wall_volume":put_wall_live.get("volume"),
            "call_wall_source":call_wall_live.get("source"),"put_wall_source":put_wall_live.get("source"),
            "cash_secured":safe_float(row.get("CashSecured")),"assignment_price":safe_float(row.get("AssignmentPrice")),
            "effective_entry":safe_float(row.get("EffectiveEntry"),breakeven),"premium_yield_pct":safe_float(row.get("PremiumYieldPct")),
            "annualized_yield_pct":safe_float(row.get("AnnualizedYieldPct")),"assignment_risk":clean_text(row.get("AssignmentRisk")),
            "earnings_date":clean_text(row.get("EarningsDate")),"earnings_days":safe_float(row.get("EarningsDays")),
            "quantity":qty,"reason":clean_text(row.get("Reason")),"risk_status":status,
        })
    for _o in out:
        print(f"   ↳ {_o['ticker']} Wall: Call={_o.get('call_wall')}({ _o.get('call_wall_source') }), Put={_o.get('put_wall')}({ _o.get('put_wall_source') })")
    print(f"📊 [期权Review] 活跃期权复盘：{len(out)} 笔")
    return out


def load_option_closed_history(days=30):
    """从 option_strategies.csv 读取历史已结束期权；避免 KPI 只统计“今天刚过期”的期权。"""
    if not os.path.exists(OPTION_LOG_FILE) or os.path.getsize(OPTION_LOG_FILE)==0:
        return []
    try:
        d=pd.read_csv(OPTION_LOG_FILE,dtype=str,keep_default_na=False)
        if d.empty: return []
        status=d.get("Status",pd.Series("",index=d.index)).astype(str).str.strip().str.lower()
        d=d[status.isin({"closed","close","expired","已平仓"})].copy()
        if d.empty: return []
        date_cols=[c for c in ("Close_Date","EntryDate") if c in d.columns]
        cutoff=pd.Timestamp(REVIEW_SESSION_DATE)-pd.Timedelta(days=days)
        use=pd.Series(pd.NaT,index=d.index,dtype="datetime64[ns]")
        for c in date_cols:
            dtv=pd.to_datetime(d[c],errors="coerce",format="mixed")
            use=use.fillna(dtv)
        d=d[use>=cutoff].copy()
        d["_pnl"]=pd.to_numeric(d.get("PnL", ""),errors="coerce")
        out=[]
        for _,x in d.iterrows():
            pnl=safe_float(x.get("PnL"))
            if pnl is None: continue
            out.append({"ticker":resolve_ticker(x.get("Ticker")),"strategy":clean_text(x.get("Strategy"),"LONG_CALL"),"expiry":clean_text(x.get("Expiry")),"close_date":clean_text(x.get("Close_Date")),"entry_price":safe_float(x.get("EntryPrice")),"close_price":safe_float(x.get("Close_Price")),"pnl":pnl,"reason":clean_text(x.get("Reason"))})
        return out
    except Exception as e:
        print(f"⚠️ 读取历史期权平仓记录失败：{e}")
        return []


def _wall_display(x, side):
    value = x.get(f"{side}_wall")
    oi = x.get(f"{side}_wall_oi")
    volume = x.get(f"{side}_wall_volume")
    source = x.get(f"{side}_wall_source")
    if value is None:
        return "N/A（无可用Wall数据）"
    if oi is not None:
        return f"{_price(value)}（OI {int(oi)}）"
    if source == "volume_proxy":
        return f"{_price(value)}（成交量代理 {int(volume or 0)}；OI不可用）"
    return f"{_price(value)}（OI N/A）"


def build_option_review_html(active_reviews, closed_records, closed_history):
    cards=[]
    if active_reviews:
        for x in active_reviews:
            pnl=_price(x.get("unrealized_pnl"))
            pnl_pct=None
            if x.get("entry") is not None and x.get("entry")>0 and x.get("unrealized_pnl") is not None:
                pnl_pct=(x.get("unrealized_pnl")/(x.get("entry")*x.get("quantity",1)*100))*100
            pnl_html=(f'<span style="{_pnl_style(pnl_pct)}">{_pct(pnl_pct)}</span>' if pnl_pct is not None else '<span style="color:#607d8b">N/A</span>')
            spread=f'{x.get("long_strike")}' + (f' / {x.get("short_strike")}' if x.get("short_strike") is not None else '')
            if x.get("strategy")=="SHORT_PUT":
                body=f"""<div style="background:#f7fbf7;border:1px solid #c8e6c9;border-left:6px solid #2e7d32;padding:16px;margin-bottom:12px;border-radius:8px;">
<div style="font-size:17px;font-weight:800;color:#2e7d32;">🛡️ {x.get("name")} ({x.get("ticker")})｜现金担保 Short Put</div>
<div><b>到期：</b>{x.get("expiry")}（DTE {x.get("dte")}）　<b>正股：</b>{_price(x.get("spot"))}　<b>执行价：</b>{_price(x.get("assignment_price"))}</div>
<div><b>入场权利金：</b>{_price(x.get("entry"))}/股　<b>当前Put价格：</b>{_price(x.get("mark"))}/股　<b>当前浮盈亏：</b>{pnl_html}</div>
<div><b>有效接货价：</b>{_price(x.get("effective_entry"))}　<b>现金担保：</b>{_price(x.get("cash_secured"))}　<b>最大收益：</b>{_price(x.get("max_profit"))}</div>
<div><b>最大风险：</b>{_price(x.get("max_loss"))}　<b>盈亏平衡：</b>{_price(x.get("breakeven"))}　<b>Put Delta：</b>{x.get("delta") if x.get("delta") is not None else "N/A"}</div>
<div><b>权利金收益率：</b>{x.get("premium_yield_pct") if x.get("premium_yield_pct") is not None else "N/A"}%　<b>年化简单折算：</b>{x.get("annualized_yield_pct") if x.get("annualized_yield_pct") is not None else "N/A"}%　<b>指派：</b>{x.get("assignment_risk") or "存在"}</div>
<div><b>财报：</b>{x.get("earnings_date") or "未确认"}　<b>事件距离：</b>{x.get("earnings_days") if x.get("earnings_days") is not None else "N/A"}天</div>
<div><b>风控判断：</b>{x.get("risk_status")}</div>
<div style="font-size:12px;color:#607d8b;">报价来源：{x.get("mark_source")}; 若到期价内，可能按执行价获得100股/张；只有愿意长期持有该股票时才使用。</div>
</div>"""
            else:
                body=f"""<div style="background:#faf7ff;border:1px solid #d7bce8;border-left:6px solid #7b1fa2;padding:16px;margin-bottom:12px;border-radius:8px;">
<div style="font-size:17px;font-weight:800;color:#5e2b76;">🎲 {x.get("name")} ({x.get("ticker")})｜{x.get("strategy")}</div>
<div><b>到期：</b>{x.get("expiry")}（DTE {x.get("dte")}）　<b>正股：</b>{_price(x.get("spot"))}　<b>执行价：</b>{spread}</div>
<div><b>入场权利金：</b>{_price(x.get("entry"))}/股　<b>当前期权价格：</b>{_price(x.get("mark"))}/股　<b>当前浮盈亏：</b>{pnl_html}</div>
<div><b>最大风险：</b>{_price(x.get("max_loss"))}　<b>最大收益：</b>{_price(x.get("max_profit"))}　<b>盈亏平衡：</b>{_price(x.get("breakeven"))}</div>
<div><b>Delta：</b>{x.get("delta") if x.get("delta") is not None else "N/A"}　<b>IV：</b>{x.get("iv") if x.get("iv") is not None else "N/A"}　<b>Call Wall：</b>{_wall_display(x,"call")}　<b>Put Wall：</b>{_wall_display(x,"put")}</div>
<div><b>财报：</b>{x.get("earnings_date") or "未确认"}　<b>事件距离：</b>{x.get("earnings_days") if x.get("earnings_days") is not None else "N/A"}天</div>
<div><b>风控判断：</b>{x.get("risk_status")}</div>
<div style="font-size:12px;color:#607d8b;">报价来源：{x.get("mark_source")}; 若无真实期权报价，程序只显示内在价值底线，不把它冒充为市价。</div>
</div>"""
            cards.append(body)
    else:
        cards.append('<div style="background:#fafafa;border:1px solid #e0e0e0;padding:16px;border-radius:8px;color:#607d8b;">当前没有活跃期权持仓。</div>')

    closed_rows=[]
    for x in (closed_records or []):
        closed_rows.append(f'<li><b>{x.get("ticker")}</b>｜{x.get("strategy")}｜到期 {x.get("expiry")}｜平仓价 {x.get("close_price")}｜PnL {x.get("pnl"):+.2f}｜{x.get("reason")}</li>')
    # 只有当天 process_options 关闭记录时才追加，避免重复显示历史记录。
    if closed_history:
        seen={(x.get("ticker"),x.get("expiry"),x.get("close_date")) for x in (closed_records or [])}
        for x in closed_history:
            key=(x.get("ticker"),x.get("expiry"),x.get("close_date"))
            if key not in seen:
                closed_rows.append(f'<li><b>{x.get("ticker")}</b>｜{x.get("strategy")}｜平仓 {x.get("close_date") or "N/A"}｜PnL {x.get("pnl"):+.2f}｜{x.get("reason")}</li>')
    closed_html=''.join(closed_rows) if closed_rows else '<li>最近30天没有已完成期权平仓记录。</li>'
    return '<h2 style="color:#7b1fa2;border-bottom:2px solid #7b1fa2;padding-bottom:5px;">🎲 期权盘后复盘与风控</h2>'+''.join(cards)+f'<div style="background:#fff;border:1px solid #e0e0e0;border-left:6px solid #9b59b6;padding:16px;border-radius:8px;margin-top:12px;"><div style="font-weight:800;margin-bottom:8px;">✅ 最近30天期权已完成复盘</div><ul style="margin:0;padding-left:20px;">{closed_html}</ul></div>'


option_closed_records = process_options(price_map_today)
active_option_reviews=build_active_option_reviews(price_map_today)
option_closed_history=load_option_closed_history(days=30)
print(f"📒 [期权账本] option_strategies.csv：活跃 {len(active_option_reviews)} 笔，最近30天已结束 {len(option_closed_history)} 笔，本次刚平仓 {len(option_closed_records)} 笔。")


# ============================================================
# 8. 技术指标与移动止损
# ============================================================

def _calc_atr(d, length=14):
    h, l, c = d["High"], d["Low"], d["Close"]
    prev = c.shift(1)
    tr = pd.concat([(h-l), (h-prev).abs(), (l-prev).abs()], axis=1).max(axis=1)
    return tr.rolling(length, min_periods=length).mean()

def _calc_macd(close, fast=12, slow=26, signal=9):
    ef = close.ewm(span=fast, adjust=False).mean()
    es = close.ewm(span=slow, adjust=False).mean()
    macd = ef - es
    sig = macd.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"MACD": macd, "MACD_SIGNAL": sig, "MACD_HIST": macd-sig})

def _calc_kdj(d, n=9):
    h = d["High"].to_numpy(float)
    l = d["Low"].to_numpy(float)
    c = d["Close"].to_numpy(float)
    K = D = 50.0
    ks, ds, js = [], [], []
    for i in range(len(c)):
        if i < n-1:
            rsv = 50.0
        else:
            hn = h[max(0,i-n+1):i+1].max()
            ln = l[max(0,i-n+1):i+1].min()
            rsv = (c[i]-ln)/(hn-ln+1e-9)*100 if hn != ln else 50.0
        K = 2/3*K + 1/3*rsv
        D = 2/3*D + 1/3*K
        ks.append(K); ds.append(D); js.append(3*K-2*D)
    return pd.DataFrame({"K":ks,"D":ds,"J":js}, index=d.index)

def get_technical_snapshot_from_bulk(df_all, ticker, target_date):
    """从已经批量下载的60日OHLC中计算目标交易日技术指标；专供Review展示，不能单独触发止损。"""
    try:
        if df_all is None or df_all.empty:
            return None
        sub = df_all[df_all["Ticker"].astype(str).str.upper() == str(ticker).upper()].copy()
        if sub.empty:
            return None
        sub["_date"] = _normalize_market_dates(sub["Date"])
        target = pd.Timestamp(target_date).normalize()
        sub = sub[sub["_date"] <= target].sort_values("_date")
        if len(sub) < 50:
            return None
        d = pd.DataFrame({
            "Open": sub["open"].astype(float).to_numpy(),
            "High": sub["high"].astype(float).to_numpy(),
            "Low": sub["low"].astype(float).to_numpy(),
            "Close": sub["close"].astype(float).to_numpy(),
        }, index=sub["_date"].tolist())
        d["MA20"] = d["Close"].rolling(20, min_periods=20).mean()
        d["MA50"] = d["Close"].rolling(50, min_periods=50).mean()
        d["ATR14"] = _calc_atr(d)
        md = _calc_macd(d["Close"])
        d["MACD_HIST"] = md["MACD_HIST"]
        kd = _calc_kdj(d)
        d["KDJ_J"] = kd["J"]
        r = d.iloc[-1]
        return {
            "ma20": round(float(r["MA20"]), 2) if pd.notna(r["MA20"]) else None,
            "ma50": round(float(r["MA50"]), 2) if pd.notna(r["MA50"]) else None,
            "kdj_j": round(float(r["KDJ_J"]), 2) if pd.notna(r["KDJ_J"]) else None,
            "macd_hist": round(float(r["MACD_HIST"]), 4) if pd.notna(r["MACD_HIST"]) else None,
            "atr_pct": round(float(r["ATR14"]) / float(r["Close"]) * 100, 2) if pd.notna(r["ATR14"]) and float(r["Close"]) else None,
            "trend_ok": bool(pd.notna(r["MA20"]) and pd.notna(r["MA50"]) and float(r["Close"]) >= float(r["MA20"]) >= float(r["MA50"])),
            "source_date": str(sub.iloc[-1]["_date"].date()),
        }
    except Exception:
        return None


def get_trailing_stop_context(ticker, current_stop=None, before_date=None, entry_price=None, days_held=None):
    try:
        hist = yf.download(ticker, period="6mo", progress=False, auto_adjust=True, threads=False)
        if hist is None or hist.empty: return None
        if isinstance(hist.columns, pd.MultiIndex): hist.columns = hist.columns.get_level_values(0)
        hist = hist.dropna(subset=["Open","High","Low","Close"]).copy()
        idx = pd.to_datetime(hist.index, errors="coerce")
        try: idx=idx.tz_localize(None)
        except Exception: pass
        hist.index=idx
        if len(hist)<60: return None
        ref = pd.Timestamp(before_date).normalize() if before_date is not None else hist.index[-1]
        d = hist[hist.index < ref].copy()
        if d.empty: return None
        d["MA20"]=d["Close"].rolling(20,min_periods=20).mean(); d["MA50"]=d["Close"].rolling(50,min_periods=50).mean(); d["ATR14"]=_calc_atr(d)
        md=_calc_macd(d["Close"]); d["MACD"]=md["MACD"]; d["MACD_SIGNAL"]=md["MACD_SIGNAL"]; d["MACD_HIST"]=md["MACD_HIST"]
        kd=_calc_kdj(d); d["KDJ_J"]=kd["J"]
        r=d.iloc[-1]; close=float(r["Close"]); atr=float(r["ATR14"]) if pd.notna(r["ATR14"]) else close*.05
        ma20=float(r["MA20"]) if pd.notna(r["MA20"]) else close; ma50=float(r["MA50"]) if pd.notna(r["MA50"]) else ma20
        pct=max(float(EXIT_PARAMS.get("atr_floor_pct",3)),min(float(EXIT_PARAMS.get("atr_ceiling_pct",12)),float(EXIT_PARAMS.get("atr_multiplier",2))*atr/max(close,1e-9)))
        candidate=max(close*(1-pct/100), ma20-atr, ma50-1.5*atr)
        # 前3个交易日快速试错：-5%
        ep=safe_float(entry_price)
        dh=safe_int(days_held)
        if ep and dh is not None and dh <= int(EXIT_PARAMS.get("early_days",3)):
            candidate=max(candidate, ep*(1+float(EXIT_PARAMS.get("early_stop_pct",-5))/100))
        # 浮盈保护：盈利越高，止损抬升而不是简单强制止盈
        if ep and ep>0:
            pnl_pct=(close/ep-1)*100
            for threshold_key, dd_key in (("profit_lock_3_pct","profit_lock_3_drawdown_pct"),("profit_lock_2_pct","profit_lock_2_drawdown_pct"),("profit_lock_1_pct","profit_lock_1_drawdown_pct")):
                if pnl_pct >= float(EXIT_PARAMS.get(threshold_key,0)):
                    candidate=max(candidate, close*(1-float(EXIT_PARAMS.get(dd_key,10))/100))
                    break
        macd_bear=bool(pd.notna(r["MACD"]) and pd.notna(r["MACD_SIGNAL"]) and r["MACD"]<r["MACD_SIGNAL"])
        kdj_falling=bool(len(d)>=2 and d["KDJ_J"].iloc[-1]<d["KDJ_J"].iloc[-2])
        if macd_bear and kdj_falling: candidate=max(candidate, close-1.5*atr)
        candidate=min(candidate, close*0.98)
        old=safe_float(current_stop)
        if old and old>0:
            # 只有通过合理性校验的历史止损才作为 floor（保持 trailing 只升不降）；
            # 异常旧止损（跨 ticker 污染 / 明显高于入场价）丢弃，从当前技术候选重建。
            if is_valid_existing_stop(old, entry_price):
                candidate=max(old,candidate)
            else:
                print(f"[STOP_FLOOR_REJECT] ticker={ticker} old_stop={old} rec_price={entry_price} reason=stop_implausible_vs_entry")
        return {"exec_stop":round(candidate,2),"ma20":round(ma20,2),"ma50":round(ma50,2),"atr_pct":round(atr/close*100,2) if close else None,
                "macd_hist":round(float(r["MACD_HIST"]),4) if pd.notna(r["MACD_HIST"]) else None,"macd_bear":macd_bear,"kdj_j":round(float(r["KDJ_J"]),2),
                "kdj_falling":kdj_falling,"trend_ok":bool(close>=ma20 and ma20>=ma50),"pnl_pct":round((close/ep-1)*100,2) if ep else None}
    except Exception as e:
        print(f"⚠️ 移动止损计算失败 {ticker}: {e}"); return None


def update_trade_history_trailing_stop(ticker, buy_date, stop_price, ctx):
    if not os.path.exists(TRADE_HISTORY):
        return
    try:
        d = pd.read_csv(TRADE_HISTORY, dtype=str, keep_default_na=False)
        for c in ("Stop_Loss","Stop_Method","Trail_Stop","MA20","MA50","ATR_Pct"):
            if c not in d.columns: d[c] = ""
        dates = pd.to_datetime(d["Date"], errors="coerce", format="mixed")
        mask = (
            d["Ticker"].astype(str).str.upper().eq(str(ticker).upper()) &
            dates.dt.strftime("%Y-%m-%d").eq(str(buy_date)[:10]) &
            d["Status"].astype(str).str.strip().eq("Active")
        )
        if mask.any():
            d.loc[mask,"Stop_Loss"] = str(stop_price)
            d.loc[mask,"Trail_Stop"] = str(stop_price)
            d.loc[mask,"Stop_Method"] = "MA20/MA50 + ATR + MACD/KDJ"
            d.loc[mask,"MA20"] = str(ctx.get("ma20",""))
            d.loc[mask,"MA50"] = str(ctx.get("ma50",""))
            d.loc[mask,"ATR_Pct"] = str(ctx.get("atr_pct",""))
            d.to_csv(TRADE_HISTORY, index=False, encoding="utf-8")
    except Exception as e:
        print(f"⚠️ 更新移动止损失败 {ticker}: {e}")

def update_trade_history_status(ticker, buy_date, new_status, exit_price):
    if not os.path.exists(TRADE_HISTORY):
        return
    try:
        d = pd.read_csv(TRADE_HISTORY, dtype=str, keep_default_na=False)
        for c in ("Status","Exit_Date","Exit_Price"):
            if c not in d.columns: d[c] = ""
        dates = pd.to_datetime(d["Date"], errors="coerce", format="mixed")
        mask = (
            d["Ticker"].astype(str).str.upper().eq(str(ticker).upper()) &
            dates.dt.strftime("%Y-%m-%d").eq(str(buy_date)[:10]) &
            d["Status"].astype(str).str.strip().eq("Active")
        )
        if mask.any():
            d.loc[mask,"Status"] = new_status
            d.loc[mask,"Exit_Date"] = REVIEW_SESSION_DATE
            d.loc[mask,"Exit_Price"] = str(exit_price)
            d.to_csv(TRADE_HISTORY, index=False, encoding="utf-8")
    except Exception as e:
        print(f"⚠️ 更新状态失败 {ticker}: {e}")

def write_review_risk_linkage_us(ticker, rec_date_str, risk_status, stop_price=None, current_price=None, note=""):
    if not os.path.exists(TRADE_HISTORY):
        return
    try:
        d = pd.read_csv(TRADE_HISTORY, dtype=str, keep_default_na=False)
        for c in ("Review_Risk_Status","Review_Risk_Date","Review_Stop_Distance_Pct","Review_Risk_Note"):
            if c not in d.columns:
                d[c] = ""
            d[c] = d[c].astype("object")
        dates = pd.to_datetime(d["Date"], errors="coerce", format="mixed")
        mask = (
            d["Ticker"].astype(str).str.upper().eq(str(ticker).upper()) &
            dates.dt.strftime("%Y-%m-%d").eq(str(rec_date_str)[:10]) &
            d["Status"].astype(str).str.strip().eq("Active")
        )
        if not mask.any(): return
        d.loc[mask,"Review_Risk_Status"] = risk_status
        d.loc[mask,"Review_Risk_Date"] = REVIEW_SESSION_DATE
        d.loc[mask,"Review_Risk_Note"] = note
        if stop_price is not None and current_price is not None and safe_float(current_price,0) > 0:
            distance = round((float(current_price)-float(stop_price))/float(current_price)*100,2)
            d.loc[mask,"Review_Stop_Distance_Pct"] = str(distance)
        else:
            d.loc[mask,"Review_Stop_Distance_Pct"] = "0" if risk_status == "STOP_TRIGGERED" else ""
        d.to_csv(TRADE_HISTORY, index=False, encoding="utf-8")
    except Exception as e:
        print(f"⚠️ Review→Scan 联动写回失败 {ticker}: {e}")


# ============================================================
# 8.5 Observation 生命周期管理
# ============================================================
# Observation 是观察性推荐，不应无限期占用 Review 算力。
# 事件仍永久保留在 trade_history / review KPI 中，但“当前跟踪”会自动结束。
OBS_MAX_TRADING_SESSIONS = 10
OBS_TARGET_PCT = 10.0          # 达标即停止继续跟踪
OBS_INVALIDATION_PCT = -6.0    # 跌破即停止继续跟踪
OBS_CLOSE_STATUS = "Observation_Closed"
OBS_END_REASONS = {
    "TARGET_REACHED": "达到观察目标，停止继续跟踪",
    "THESIS_INVALIDATED": "观察期价格表现跌破失效阈值，停止继续跟踪",
    "MAX_TRACKING_SESSIONS": "达到最大观察交易日，停止继续跟踪",
    "SUPERSEDED_BY_NEW_OBSERVATION": "同一标的出现新的 Observation，结束旧事件",
    "SUPERSEDED_BY_CORE": "同一标的升级为 Core，结束旧 Observation",
}


def _observation_sessions_held(rec_date_str, review_date_str):
    try:
        a = pd.Timestamp(rec_date_str).normalize()
        b = pd.Timestamp(review_date_str).normalize()
        if b <= a:
            return 0
        return max(0, len(pd.bdate_range(a, b)) - 1)
    except Exception:
        return 0


def _historical_close_for_review_event(ticker, date_str):
    """尽量取指定推荐/替换交易日收盘价，给 Observation 事件做干净的结束结算。"""
    try:
        if 'df_hist_all' not in globals() or df_hist_all is None or df_hist_all.empty:
            return None
        d = df_hist_all.copy()
        d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
        target = pd.Timestamp(date_str).normalize()
        sub = d[
            d["Ticker"].astype(str).str.upper().eq(str(ticker).upper())
            & d["Date"].dt.normalize().eq(target)
        ]
        if sub.empty:
            return None
        return safe_float(sub.iloc[-1].get("close"))
    except Exception:
        return None


def manage_observation_lifecycle():
    """
    自动结束过老/已失效/被新推荐替代的 Observation。
    只结束当前仍 Active/pending 的 Observation；历史事件不反复修改。
    """
    if not os.path.exists(TRADE_HISTORY) or os.path.getsize(TRADE_HISTORY) == 0:
        return 0
    try:
        d = pd.read_csv(TRADE_HISTORY, dtype=str, keep_default_na=False, on_bad_lines='warn')
    except Exception as e:
        print(f"⚠️ Observation 生命周期读取失败：{e}")
        return 0

    for col in ["Status", "Exit_Date", "Exit_Price", "Observation_Status", "Observation_End_Reason"]:
        if col not in d.columns:
            d[col] = ""
        d[col] = d[col].astype(object)

    if "Date" not in d.columns or "Ticker" not in d.columns or "Tag" not in d.columns:
        return 0

    tmp = d.copy()
    tmp["_date"] = pd.to_datetime(tmp["Date"], errors="coerce")
    tmp["_ticker"] = tmp["Ticker"].astype(str).str.upper().str.strip()
    tmp["_tag"] = tmp["Tag"].astype(str).str.strip()
    tmp["_status"] = tmp["Status"].astype(str).str.strip()

    active_obs = tmp[
        (tmp["_tag"] == "Observation")
        & tmp["_status"].isin(["", "Active", "pending"])
        & tmp["_date"].notna()
    ].copy()
    if active_obs.empty:
        return 0

    # 仅比较同 ticker 的后续 Scan 事件。旧 Observation 被新的 Observation/Core 替代后关闭。
    closes = []
    for idx, row in active_obs.sort_values(["_ticker", "_date"]).iterrows():
        ticker = str(row["_ticker"]).strip()
        rec_date = row["_date"].strftime("%Y-%m-%d")
        rec_price = safe_record_price(row)
        if rec_price is None or rec_price <= 0:
            # 推荐价缺失时仍允许超期关闭，但无法形成收益数字。
            rec_price = None

        later = tmp[
            (tmp["_ticker"] == ticker)
            & tmp["_date"].notna()
            & (tmp["_date"] > row["_date"])
        ].copy()
        later = later.sort_values("_date")

        replacement = None
        if not later.empty:
            later_repl = later[later["_tag"].isin([
                "Core_Dragon", "Core_Double_Dragon", "Sub_Pioneer", "Observation"
            ])].sort_values("_date")
            if not later_repl.empty:
                first_repl = later_repl.iloc[0]
                if first_repl["_tag"] == "Observation":
                    replacement = ("SUPERSEDED_BY_NEW_OBSERVATION", first_repl)
                else:
                    replacement = ("SUPERSEDED_BY_CORE", first_repl)

        reason_code = None
        close_date = pd.Timestamp(REVIEW_SESSION_DATE).strftime("%Y-%m-%d")
        close_price = safe_float(price_map_today.get(ticker))

        # 新事件替代：尽量在“新事件的推荐日收盘”结束旧观察，而不是等到今天。
        if replacement is not None:
            reason_code, repl = replacement
            close_date = repl["_date"].strftime("%Y-%m-%d")
            close_price = _historical_close_for_review_event(ticker, close_date) or close_price
        else:
            if rec_price and close_price:
                pnl = (close_price - rec_price) / rec_price * 100.0
                if pnl >= OBS_TARGET_PCT:
                    reason_code = "TARGET_REACHED"
                elif pnl <= OBS_INVALIDATION_PCT:
                    reason_code = "THESIS_INVALIDATED"
            if reason_code is None:
                sessions = _observation_sessions_held(rec_date, REVIEW_SESSION_DATE)
                if sessions >= OBS_MAX_TRADING_SESSIONS:
                    reason_code = "MAX_TRACKING_SESSIONS"

        if reason_code is None:
            continue

        label = OBS_END_REASONS.get(reason_code, reason_code)
        mask = (
            d["Tag"].astype(str).str.strip().eq("Observation")
            & d["Ticker"].astype(str).str.upper().str.strip().eq(ticker)
            & pd.to_datetime(d["Date"], errors="coerce").dt.strftime("%Y-%m-%d").eq(rec_date)
            & d["Status"].astype(str).str.strip().isin(["", "Active", "pending"])
        )
        d.loc[mask, "Status"] = OBS_CLOSE_STATUS
        d.loc[mask, "Exit_Date"] = close_date
        if close_price is not None:
            d.loc[mask, "Exit_Price"] = str(round(float(close_price), 4))
        d.loc[mask, "Observation_Status"] = "Closed"
        d.loc[mask, "Observation_End_Reason"] = label
        closes.append((ticker, rec_date, reason_code, close_price))

    if closes:
        try:
            d.to_csv(TRADE_HISTORY, index=False, encoding="utf-8")
        except Exception as e:
            print(f"⚠️ Observation 生命周期写回失败：{e}")
            return 0

        reason_counts = {}
        for ticker, rec_date, code, close_price in closes:
            reason_counts[code] = reason_counts.get(code, 0) + 1
        detail = "；".join(f"{OBS_END_REASONS.get(k,k)} {v}笔" for k, v in reason_counts.items())
        print(f"📌 [Observation跟踪管理] 本次结束 {len(closes)} 笔，原因：{detail}")

    return len(closes)


# 事件生命周期管理必须先于分类和 KPI。
manage_observation_lifecycle()

# 生命周期写回后重新加载内存账本，避免本轮 Review 继续把已关闭 Observation 当作 Active。
df = load_trade_history()
# 动态持有：与行情准备段一致，从完整 trade_history 识别 active holdings（不按 30 天 cutoff）。
recent_picks = df.copy()
for c in ("Hold_Period","Stop_Loss","Score","Name","Tag","Price","Close_Price","Status"):
    if c not in recent_picks.columns:
        recent_picks[c] = ""
recent_picks["Hold_Period"] = "动态持有"

# ============================================================
# 9. 股票分类
# ============================================================

active_list, observation_list, expired_list, stopped_list = [], [], [], []
_recommendation_price_lookup = _build_recommendation_price_lookup()

# 关键修复：不能再按 Ticker 合并历史推荐。
# 每一次 Scan 推荐都是独立事件：推荐日期 + Ticker + Tag。
# 否则“9/21 NXPI Stop_Loss_Hit + 9/22 NXPI 新 Core”会被合并，
# 导致旧事件的止损状态污染新事件；同理 Observation 会被最新 Core 覆盖而消失。
recent_picks = recent_picks.copy()
_recent_event_groups = []
for (event_date, event_ticker, event_tag), g in recent_picks.groupby(
    ["Date", "Ticker", "Tag"], sort=False, dropna=False
):
    g = g.sort_values("Date").copy()
    if g.empty:
        continue
    # 同时保留完整生命周期分组，用于选取“当前有效 Stop_Loss”（最新一条有效值）。
    _recent_event_groups.append(((event_date, event_ticker, event_tag), g.iloc[-1].copy(), g.copy()))

for (_event_date, _event_ticker, _event_tag), latest, group in _recent_event_groups:
    ticker = resolve_ticker(latest.get("Ticker"), clean_text(latest.get("Name")))
    if not ticker:
        continue

    rec_date = normalize_date(latest.get("Date"))
    if rec_date is None:
        continue
    rec_date_str = rec_date.strftime("%Y-%m-%d")
    status = clean_text(latest.get("Status"))

    # 已经结束 / 已退出的旧生命周期不再作为 active 检查（含 Exit_Date 已设置的清仓）。
    # 统一用 is_active_holding 判定，确保 Exit_Date="N/A" 等占位符不会被误判为"已退出"。
    if not is_active_holding(status, latest.get("Exit_Date")):
        continue

    # 当前有效 Stop_Loss：取该生命周期内最新一条有效值（从最新行向前扫描）；
    # 最新行若为空/无效则回退到更早的有效止损；绝不用技术候选覆盖仍有效的历史止损
    #（避免“邮件显示184、内部实际拿更低值”）。
    current_stop = select_current_stop_loss(group)
    rec_price = safe_record_price(latest)

    # ---- Observation：每一条 Scan Observation 都独立追踪 ----
    if clean_text(latest.get("Tag")).strip() == "Observation":
        if rec_price is None or rec_price <= 0:
            rec_price = _recommendation_price_lookup.get((rec_date_str, ticker.upper(), "Observation"))
        cur = safe_float(price_map_today.get(ticker))
        pnl = None
        if rec_price and rec_price > 0 and cur is not None:
            pnl = round((cur-rec_price)/rec_price*100, 2)
        if rec_price is None:
            print(f"⚠️ [Observation] {ticker} {rec_date_str} 缺少可追溯推荐价，暂无法计算跟踪收益。")
        elif cur is None:
            print(f"⚠️ [Observation] {ticker} {rec_date_str} 缺少当前行情，暂无法计算跟踪收益。")
        observation_list.append({
            "代码": ticker,
            "名称": clean_text(latest.get("Name"), ticker),
            "标签": "Observation",
            "推荐评分": clean_text(latest.get("Score"), "N/A"),
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "当前价格": cur,
            "推荐跟踪涨跌幅(%)": pnl,
            "RSI": clean_text(latest.get("RSI"), "N/A"),
            "Bias": clean_text(latest.get("Bias"), "N/A"),
            "技术评分": clean_text(latest.get("技术评分"), "N/A"),
            "估值评分": clean_text(latest.get("估值评分"), "N/A"),
            "PE_TTM": clean_text(latest.get("PE_TTM"), "N/A"),
            "PE_Forward": clean_text(latest.get("PE_Forward"), "N/A"),
            "EPS_TTM": clean_text(latest.get("EPS_TTM"), "N/A"),
            "PB": clean_text(latest.get("PB"), "N/A"),
            "MACD金叉": clean_text(latest.get("MACD金叉"), "N/A"),
            "周线共振": clean_text(latest.get("周线共振"), "N/A"),
            "KDJ_J回升": clean_text(latest.get("KDJ_J回升"), "N/A"),
            "量能放大": clean_text(latest.get("量能放大"), "N/A"),
            "周期共振": clean_text(latest.get("周期共振"), "N/A"),
            "系统连续推荐次数": 1,
            "今日新增": "是" if rec_date_str == REVIEW_SESSION_DATE else "否",
            "行情状态": price_source_map.get(ticker, "missing") if cur is not None else "今日/最近行情缺失",
        })
        continue

    if rec_price is None or rec_price <= 0:
        continue

    # 只有经过“目标日期精确匹配”的完整 OHLC 才能做当日最低价止损判断。
    # price_map_today 的最近有效收盘价只能用于跟踪，绝不能触发今天的 STOP。
    ohlc = ohlc_map_today.get(ticker) if ticker in verified_review_session_ohlc and price_source_map.get(ticker) == "today_regular_close" else None
    if ohlc is None:
        cur = price_map_today.get(ticker)
        if cur is None:
            active_list.append({
                "代码": ticker, "名称": clean_text(latest.get("Name"), ticker),
                "标签": clean_text(latest.get("Tag")), "推荐评分": clean_text(latest.get("Score"),"N/A"),
                "持股周期建议": "动态持有", "止损价": safe_float(latest.get("Stop_Loss")) or "N/A",
                "首次推荐日": rec_date_str, "首次推荐价": rec_price,
                "今日开盘价":"N/A", "现价":"N/A", "今日开盘→收盘%":None,
                "持仓天数":(pd.Timestamp(REVIEW_SESSION_DATE)-rec_date).days, "剩余天数":"—",
                "当前盈亏(%)":None, "系统连续推荐次数":1,
                "今日新增":"是" if rec_date_str==REVIEW_SESSION_DATE else "否",
                "止损方法":"MA20/MA50 + ATR + MACD/KDJ",
                "MA20":None,"MA50":None,"KDJ_J":None,"MACD_Hist":None,
                "趋势状态":f"{REVIEW_SESSION_DATE}行情缺失","风险提示":f"{REVIEW_SESSION_DATE} 行情未取得；暂不执行该交易日止损判断",
                "Review_Risk_Status":"DATA_MISSING","Review_Risk_Date":REVIEW_SESSION_DATE,
                "Review_Stop_Distance_Pct":"","Review_Risk_Note":f"{REVIEW_SESSION_DATE} 行情缺失，待下一次Review补算"
            })
            write_review_risk_linkage_us(ticker, rec_date_str, "DATA_MISSING", None, None, f"{REVIEW_SESSION_DATE} 行情缺失，暂不执行该交易日止损判断。")
            continue

        cur_float = safe_float(cur)
        stop = current_stop
        pnl = round((cur_float-rec_price)/rec_price*100,2) if cur_float is not None else None
        active_list.append({
            "代码":ticker,"名称":clean_text(latest.get("Name"),ticker),"标签":clean_text(latest.get("Tag")),
            "推荐评分":clean_text(latest.get("Score"),"N/A"),"持股周期建议":"动态持有",
            "止损价":stop if stop else "N/A","首次推荐日":rec_date_str,"首次推荐价":rec_price,
            "今日开盘价":"N/A","现价":cur_float if cur_float is not None else "N/A","今日开盘→收盘%":None,
            "持仓天数":(pd.Timestamp(REVIEW_SESSION_DATE)-rec_date).days,"剩余天数":"—","当前盈亏(%)":pnl,
            "系统连续推荐次数":1,"今日新增":"是" if rec_date_str==REVIEW_SESSION_DATE else "否",
            "止损方法":"MA20/MA50 + ATR + MACD/KDJ","MA20":None,"MA50":None,"KDJ_J":None,"MACD_Hist":None,
            "趋势状态":"仅有最近有效价格","风险提示":f"{REVIEW_SESSION_DATE} OHLC未返回；仅跟踪价格，不执行该交易日止损触发",
            "Review_Risk_Status":"DATA_MISSING","Review_Risk_Date":REVIEW_SESSION_DATE,
            "Review_Stop_Distance_Pct":round((cur_float-stop)/cur_float*100,2) if stop and cur_float else "",
            "Review_Risk_Note":f"{REVIEW_SESSION_DATE} 完整OHLC未返回；已使用最近有效价格跟踪，不执行该交易日止损触发。"
        })
        write_review_risk_linkage_us(ticker, rec_date_str, "DATA_MISSING", None, cur_float, "今日完整OHLC未返回；使用最近有效价格跟踪，不执行当日止损触发。")
        continue

    # ---- 统一行情快照：ohlc 已确保来自本次 Review 交易日同一份 OHLC（见上文 ohlc_map_today 选取）----
    low, closep, openp = safe_float(ohlc.get("low")), safe_float(ohlc.get("close")), safe_float(ohlc.get("open"))
    highp = safe_float(ohlc.get("high"))
    old_stop = current_stop
    is_same_day_entry = rec_date_str == REVIEW_SESSION_DATE
    ctx = get_trailing_stop_context(ticker, old_stop, REVIEW_SESSION_DATE, entry_price=rec_price, days_held=(pd.Timestamp(REVIEW_SESSION_DATE)-rec_date).days)
    tech_snapshot = get_technical_snapshot_from_bulk(df_hist_all, ticker, REVIEW_SESSION_DATE)
    # 新推荐当日不允许用“入场前一个交易日”的技术结构把初始保护线瞬间抬高，
    # 否则会出现 NXPI 9/22：初始止损 213.51，但因为 9/21 收盘技术线抬到 226.61，
    # 9/22 当日最低 226.15 被错误判成止损。新仓当天只执行 Scan 已写入的初始保护线。
    exec_stop = old_stop if is_same_day_entry and old_stop and old_stop > 0 else (ctx.get("exec_stop") if ctx else old_stop)
    ohlc_src = price_source_map.get(ticker) or "?"
    # Prev_Close / Change_1D 从同一份快照重算：Prev_Close = 前一真实交易日收盘，Change_1D=(Close-Prev_Close)/Prev_Close*100。
    prev_close = _prior_regular_close(df_hist_all, ticker, REVIEW_SESSION_DATE)
    change_1d = compute_change_1d(closep, prev_close)

    # ---- 止损触发（统一快照 + 当前有效 Stop_Loss）----
    trigger_result, exitp = evaluate_stop_trigger(low, closep, openp, exec_stop)
    if trigger_result == "NO_TRIGGER_INVALID_STOP":
        # Stop_Loss 无效：不触发价格止损，但必须输出明确 warning。
        print(f"⚠️ [风控] {ticker} {rec_date_str} Stop_Loss 无效({exec_stop})，跳过价格止损（仅跟踪）。")
        write_review_risk_linkage_us(ticker, rec_date_str, "NO_STOP", None, closep,
                                     f"Stop_Loss 无效({exec_stop})，不触发价格止损，仅跟踪。")
    elif trigger_result == "STOP_TRIGGERED":
        # 已确认跌破止损（Low 或 可靠 Close）→ STOP_TRIGGERED。
        print(f"ℹ️ [风控] {ticker} {rec_date_str} 确认触及止损 {exec_stop:.2f}（Low={low} Close={closep} Open={openp}）-> Exit={exitp}。")
        write_review_risk_linkage_us(
            ticker, rec_date_str, "STOP_TRIGGERED", exec_stop, closep,
            f"今日最低价 {low:.2f} 已触及/跌破移动止损 {exec_stop:.2f}；次日 Scan 禁止重新推荐。"
        )
        pnl = round((exitp-rec_price)/rec_price*100,2)
        stopped_list.append({
            "代码":ticker,"名称":clean_text(latest.get("Name"),ticker),
            "标签":clean_text(latest.get("Tag")),"推荐评分":clean_text(latest.get("Score"),"N/A"),
            "持股周期建议":"动态持有","止损价":exec_stop,"首次推荐日":rec_date_str,"首次推荐价":rec_price,
            "止损触发日":REVIEW_SESSION_DATE,"止损结算价":exitp,"止损盈亏(%)":pnl,
            "持仓天数":(pd.Timestamp(REVIEW_SESSION_DATE)-rec_date).days,"系统连续推荐次数":1,
            "触发方式":"移动止损：今日完整OHLC触发","Stop_Method":"MA20/MA50 + ATR + MACD/KDJ"
        })
        update_trade_history_status(ticker, rec_date_str, "Stop_Loss_Hit", exitp)
    elif trigger_result == "DATA_MISSING":
        # 无任何可靠 OHLC：不能猜测，输出数据不足 warning（不触发）。
        write_review_risk_linkage_us(ticker, rec_date_str, "DATA_MISSING", None, None,
                                     f"{REVIEW_SESSION_DATE} 行情缺失，暂不执行该交易日止损判断。")
        cur = price_map_today.get(ticker); cur_float = safe_float(cur)
        active_list.append({
            "代码":ticker,"名称":clean_text(latest.get("Name"),ticker),"标签":clean_text(latest.get("Tag")),
            "推荐评分":clean_text(latest.get("Score"),"N/A"),"持股周期建议":"动态持有",
            "止损价":exec_stop if exec_stop else "N/A","首次推荐日":rec_date_str,"首次推荐价":rec_price,
            "今日开盘价":"N/A","现价":cur_float if cur_float is not None else "N/A","今日开盘→收盘%":None,
            "持仓天数":(pd.Timestamp(REVIEW_SESSION_DATE)-rec_date).days,"剩余天数":"—","当前盈亏(%)":None,
            "系统连续推荐次数":1,"今日新增":"是" if rec_date_str==REVIEW_SESSION_DATE else "否",
            "止损方法":"MA20/MA50 + ATR + MACD/KDJ","MA20":None,"MA50":None,"KDJ_J":None,"MACD_Hist":None,
            "趋势状态":f"{REVIEW_SESSION_DATE}行情缺失","风险提示":f"{REVIEW_SESSION_DATE} 行情未取得；暂不执行该交易日止损判断",
            "Review_Risk_Status":"DATA_MISSING","Review_Risk_Date":REVIEW_SESSION_DATE,
            "Review_Stop_Distance_Pct":"","Review_Risk_Note":f"{REVIEW_SESSION_DATE} 行情缺失，待下一次Review补算"
        })
    else:
        # CLEAR：Low > Stop 且 Close 未确认跌破 -> 进入下方常规 CLEAR/STOP_NEAR 流程。
        pass

    # ---- 风控诊断日志（统一快照，便于从 Actions log 直接定位“价破止损却未止损”）----
    print(f"[风控诊断] {ticker} Trade_Date={REVIEW_SESSION_DATE} Current_Close={closep} Prev_Close={prev_close} "
          f"Change_1D={change_1d} Open={openp} High={highp} Low={low} Stop_Loss={exec_stop} "
          f"Trigger={trigger_result} Exit={exitp} OHLC_Source={ohlc_src}")

    if trigger_result in ("STOP_TRIGGERED", "DATA_MISSING"):
        continue

    next_ctx = get_trailing_stop_context(ticker, exec_stop, None, entry_price=rec_price, days_held=(pd.Timestamp(REVIEW_SESSION_DATE)-rec_date).days)
    # 同日新仓保持原始保护线；从下一个 Review 日起才允许移动止损抬升。
    next_stop = exec_stop if is_same_day_entry and exec_stop else (next_ctx.get("exec_stop") if next_ctx else exec_stop)
    if next_stop and not is_same_day_entry:
        update_trade_history_trailing_stop(ticker, rec_date_str, next_stop, next_ctx or ctx or {})
    c = dict(next_ctx or ctx or {})
    # 展示指标以“复盘交易日收盘后的技术状态”为准；止损触发本身仍使用交易日前已知的 ctx。
    if tech_snapshot:
        for _k in ("ma20", "ma50", "kdj_j", "macd_hist", "atr_pct", "trend_ok"):
            if tech_snapshot.get(_k) is not None:
                c[_k] = tech_snapshot.get(_k)
    risk = []
    if c.get("macd_bear"): risk.append("MACD弱势")
    if c.get("kdj_falling"): risk.append("KDJ回落")
    days = (pd.Timestamp(today_us_str()) - rec_date).days
    distance = ((closep-next_stop)/closep*100) if next_stop and closep else None
    risk_status = "STOP_NEAR" if distance is not None and distance <= 3.0 else "CLEAR"
    risk_note = f"收盘距离移动止损约 {distance:.2f}%，次日 Scan 强提醒。" if risk_status == "STOP_NEAR" else "本次 Review 未发现触及或接近移动止损。"
    write_review_risk_linkage_us(ticker, rec_date_str, risk_status, next_stop, closep, risk_note)

    active_list.append({
        "代码":ticker,"名称":clean_text(latest.get("Name"),ticker),"标签":clean_text(latest.get("Tag")),
        "推荐评分":clean_text(latest.get("Score"),"N/A"),"持股周期建议":"动态持有",
        "止损价":next_stop if next_stop else "N/A","首次推荐日":rec_date_str,"首次推荐价":rec_price,
        "今日开盘价":openp if openp is not None else "N/A","现价":closep,
        "今日开盘→收盘%":round((closep-openp)/openp*100,2) if openp and closep is not None else None,
        "持仓天数":days,"剩余天数":"—","当前盈亏(%)":round((closep-rec_price)/rec_price*100,2),
        "系统连续推荐次数":1,"今日新增":"是" if rec_date_str==REVIEW_SESSION_DATE else "否",
        "止损方法":"MA20/MA50 + ATR + MACD/KDJ","MA20":c.get("ma20"),"MA50":c.get("ma50"),
        "KDJ_J":c.get("kdj_j"),"MACD_Hist":c.get("macd_hist"),
        "趋势状态":"多头结构" if c.get("trend_ok") else "趋势转弱",
        "风险提示":"、".join(risk) if risk else "趋势未出现同步转弱",
        "Review_Risk_Status":risk_status,"Review_Risk_Date":REVIEW_SESSION_DATE,
        "Review_Stop_Distance_Pct":round(distance,2) if distance is not None else "",
        "Review_Risk_Note":risk_note
    })


# ============================================================
# 10. Review 基本面补全
# ============================================================
# 原 Scan 的 Observation 可能没有进入当时的 Top80 基本面抓取窗口，导致
# PE/EPS/PB 等字段在 trade_history 中长期为空。Review 这里对报告里仍缺失
# 基本面的推荐做一次轻量补拉，并且只填空值，不覆盖 Scan 已记录的原始值。
def _safe_info_float_review(info, *keys):
    for key in keys:
        try:
            v = info.get(key) if hasattr(info, "get") else None
            if v is None:
                continue
            v = float(v)
            if pd.notna(v):
                return v
        except Exception:
            continue
    return None


def _fetch_review_fundamental_one(ticker):
    try:
        info = yf.Ticker(ticker).info
        return ticker, {
            "PE_TTM": _safe_info_float_review(info, "trailingPE"),
            "PE_Forward": _safe_info_float_review(info, "forwardPE"),
            "EPS_TTM": _safe_info_float_review(info, "trailingEps", "epsTrailingTwelveMonths"),
            "PB": _safe_info_float_review(info, "priceToBook"),
            "EPS_Forward": _safe_info_float_review(info, "epsForward"),
            "Earnings_Growth": _safe_info_float_review(info, "earningsGrowth"),
            "Revenue_Growth": _safe_info_float_review(info, "revenueGrowth"),
            "ROE": _safe_info_float_review(info, "returnOnEquity"),
            "Profit_Margin": _safe_info_float_review(info, "profitMargins"),
            "Market_Cap": _safe_info_float_review(info, "marketCap"),
        }
    except Exception as e:
        return ticker, {"_error": str(e)}


def _fill_missing_fundamentals_in_item(item, data):
    for key, value in data.items():
        if key.startswith("_") or value is None:
            continue
        existing = item.get(key)
        if existing in (None, "", "N/A", "nan", "NaN", "None"):
            item[key] = value


def enrich_review_missing_fundamentals():
    targets = {}
    collections = (active_list, observation_list, stopped_list)
    for rows in collections:
        for item in rows:
            ticker = str(item.get("代码", "")).strip().upper()
            if not ticker:
                continue
            # 只有真正缺失关键基本面时才请求，避免每次 Review 无条件重抓 80 只。
            missing = any(
                item.get(k) in (None, "", "N/A", "nan", "NaN", "None")
                for k in ("PE_TTM", "PE_Forward", "EPS_TTM", "PB")
            )
            if missing:
                targets[ticker] = True
    tickers = list(targets)
    if not tickers:
        return {}
    print(f"💰 [Review基本面补全] {len(tickers)} 只标的缺少 PE/EPS/PB，开始补拉 Yahoo fundamentals...")
    fund_map = {}
    workers = min(8, max(2, len(tickers)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_fetch_review_fundamental_one, t) for t in tickers]
        for future in as_completed(futures):
            try:
                ticker, data = future.result()
                fund_map[ticker] = data
            except Exception:
                pass
    for rows in collections:
        for item in rows:
            ticker = str(item.get("代码", "")).strip().upper()
            if ticker in fund_map:
                _fill_missing_fundamentals_in_item(item, fund_map[ticker])
    ok = sum(1 for t, d in fund_map.items() if any(d.get(k) is not None for k in ("PE_TTM", "PE_Forward", "EPS_TTM", "PB")))
    print(f"✅ [Review基本面补全] 成功补全 {ok}/{len(tickers)} 只标的的至少一项估值数据。")
    return fund_map


review_fundamental_map = enrich_review_missing_fundamentals()

# ============================================================
# 11. 确定性归因
# ============================================================

def build_us_attribution(item):
    pnl = safe_float(item.get("当前盈亏(%)"))
    cur = safe_float(item.get("现价"))
    stop = safe_float(item.get("止损价"))
    ma20 = safe_float(item.get("MA20"))
    ma50 = safe_float(item.get("MA50"))
    if pnl is None:
        reason = "当前盈亏数据不足，无法可靠归因。"
    elif pnl < 0:
        parts = []
        if ma20 is not None and cur is not None and cur < ma20: parts.append("跌破MA20")
        if ma50 is not None and cur is not None and cur < ma50: parts.append("跌破MA50")
        reason = f"当前持仓亏损 {pnl:.2f}%，主要来自建仓后的价格回撤。"
        if parts: reason += " 技术原因：" + "、".join(parts) + "。"
    else:
        reason = f"当前持仓盈利 {pnl:.2f}%。" if pnl > 0 else "当前盈亏接近持平。"
    if stop is not None and cur is not None and cur > 0:
        gap = (cur-stop)/cur*100
        action = "止损距离较近，继续收紧风控。" if gap <= 3 else "继续动态持有，以移动止损和趋势破坏作为退出依据。"
    else:
        action = "继续动态持有；技术数据不足时沿用已有保护线。"
    return reason, action

for item in active_list:
    item["盈利/亏损原因"], item["风控动作指令"] = build_us_attribution(item)

for item in stopped_list:
    item["盈利/亏损原因"] = f"移动止损触发，策略盈亏 {safe_float(item.get('止损盈亏(%)'),0):.2f}%。"
    item["风控动作指令"] = "已触发移动止损，次日 Scan 禁止重新推荐。"

print(f"📊 股票分类：持仓 {len(active_list)}，Observation {len(observation_list)}，止损 {len(stopped_list)}")


# ============================================================
# 12. review_history：逐次 Review 记录，但不重复同一 Review 事件
# ============================================================

# 里程碑字段（回补 / 更新只允许补齐空字段，绝不覆盖已有真实值）
MILESTONE_FIELDS = ("Price_5D", "PnL_5D", "Price_10D", "PnL_10D", "Price_20D", "PnL_20D")
# 里程碑窗口容错：rec_date 之后第一根真实 bar 与该 rec_date 的最大自然日距离。
# 超过说明历史窗口没有覆盖到 rec_date，必须 fail-closed（不取错误的第 N 根 bar）。
MILESTONE_WINDOW_TOLERANCE_DAYS = 7


def _milestone_stage(status, price_5d, price_10d, price_20d, cur_stage=""):
    """FINAL > 20D > 10D > 5D > OPEN；原有 FINAL 或状态已结束 → FINAL。"""
    if clean_text(cur_stage).upper() == "FINAL":
        return "FINAL"
    if clean_text(status) in CLOSED_STOCK_STATUSES:
        return "FINAL"
    if clean_text(price_20d):
        return "20D"
    if clean_text(price_10d):
        return "10D"
    if clean_text(price_5d):
        return "5D"
    return "OPEN"


def review_event_key(row):
    return (
        clean_text(row.get("Review_Date"))[:10],
        clean_text(row.get("Ticker")).upper(),
        clean_text(row.get("Rec_Date"))[:10],
        clean_text(row.get("Status")),
        clean_text(row.get("Option_Type")).upper(),
        clean_text(row.get("Strike")),
        clean_text(row.get("Expiry")),
    )

def append_review_rows(rows):
    """写入 review_history.csv。

    A. 新事件（key 不存在）→ append。
    B. 已存在事件（同一 Review_Date + Ticker + Rec_Date + Status…）→ 只允许补齐仍为空的
       里程碑字段（Price_5D/PnL_5D/Price_10D/PnL_10D/Price_20D/PnL_20D），已有真实值绝不覆盖；
       并按 FINAL > 20D > 10D > 5D > OPEN 同步 Review_Stage（原 FINAL 保持 FINAL）。
    绝不新建/改写任何业务字段（Rec_Price / Cur_Price / PnL_Pct / Status …）。
    """
    if not rows:
        return
    nd = pd.DataFrame(rows)
    for c in REVIEW_COLUMNS:
        if c not in nd.columns:
            nd[c] = ""
    nd = nd[REVIEW_COLUMNS]

    if os.path.exists(REVIEW_HISTORY) and os.path.getsize(REVIEW_HISTORY) > 0:
        try:
            od = pd.read_csv(REVIEW_HISTORY, dtype=str, keep_default_na=False, on_bad_lines="skip")
            for c in REVIEW_COLUMNS:
                if c not in od.columns:
                    od[c] = ""
            od = od[REVIEW_COLUMNS]
        except Exception:
            od = pd.DataFrame(columns=REVIEW_COLUMNS)
    else:
        od = pd.DataFrame(columns=REVIEW_COLUMNS)

    pos = {}
    for i, (_, r) in enumerate(od.iterrows()):
        pos.setdefault(review_event_key(r), i)

    out, updated = [], 0
    for _, r in nd.iterrows():
        k = review_event_key(r)
        if k in pos:
            i = pos[k]
            touched = False
            for f in MILESTONE_FIELDS:
                if not clean_text(od.at[i, f]) and clean_text(r.get(f)):
                    od.at[i, f] = clean_text(r.get(f))
                    touched = True
            st_old = clean_text(od.at[i, "Review_Stage"])
            st_new = _milestone_stage(r.get("Status"), od.at[i, "Price_5D"],
                                      od.at[i, "Price_10D"], od.at[i, "Price_20D"], st_old)
            if st_new != st_old:
                od.at[i, "Review_Stage"] = st_new
                touched = True
            if touched:
                updated += 1
        else:
            out.append(r.to_dict())

    if out:
        od = pd.concat([od, pd.DataFrame(out, columns=REVIEW_COLUMNS)], ignore_index=True)
        print(f"🧾 新增 review 行 {len(out)} 条" + (f"，补齐里程碑 {updated} 条" if updated else ""))
    elif updated:
        print(f"🧾 无新增行，补齐里程碑 {updated} 条")
    if out or updated:
        od.to_csv(REVIEW_HISTORY, index=False, encoding="utf-8")


# ============================================================
# 12b. 里程碑：5D / 10D / 20D / Review_Stage（历史客观计算，不调用 GPT）
# ============================================================

# 明确的股票结束状态（与下方 KPI 处共用同一份，提前定义供里程碑阶段使用）
CLOSED_STOCK_STATUSES = {
    "Stop_Loss_Hit",
    "Dropped",
    "Period_Matured",
    "Forced_Exit",
    "移动止损清仓",
    "止损触发清仓",
    "已超期归档",
    "周期到期清仓",
    "突发清仓暂停",
    "Observation_Closed",
}

DF_HIST_MILESTONE = None


def build_milestone_history():
    """里程碑专用宽窗口历史 OHLCV（覆盖最早需回补的 Rec_Date）。

    - 复用已有 df_hist_all，绝不重复下载已经存在的 90d 数据；
    - 只有当存在更早的 Rec_Date 时，才补下载
      「最早 Rec_Date − 5 个自然日 → df_hist_all 最早日 − 1 天」这一段历史；
    - df_hist_all 对实时行情 / 止损逻辑的用途完全不变；
    - 构建失败 → 退化为 df_hist_all（后续 get_nth_trading_day_close 会 fail-closed）。
    """
    global DF_HIST_MILESTONE
    if DF_HIST_MILESTONE is not None:
        return DF_HIST_MILESTONE

    base = df_hist_all if (df_hist_all is not None and not df_hist_all.empty) else pd.DataFrame()
    try:
        if base.empty:
            DF_HIST_MILESTONE = base
            return DF_HIST_MILESTONE

        # 需要回补的历史（Ticker, Rec_Date）：只挑里程碑字段仍为空的行，尽量少下载
        need_tickers, recs = [], []
        if os.path.exists(REVIEW_HISTORY) and os.path.getsize(REVIEW_HISTORY) > 0:
            try:
                _h = pd.read_csv(REVIEW_HISTORY, dtype=str, keep_default_na=False, on_bad_lines="skip")
                for _, r in _h.iterrows():
                    if any(not clean_text(r.get(f)) for f in MILESTONE_FIELDS):
                        t = clean_text(r.get("Ticker")).upper()
                        if t:
                            need_tickers.append(t)
                        d = clean_text(r.get("Rec_Date"))[:10]
                        if d:
                            recs.append(d)
            except Exception:
                pass

        base_min = _normalize_market_dates(base["Date"]).min()
        earliest = None
        for d in recs:
            try:
                t = pd.Timestamp(d).normalize()
            except Exception:
                continue
            if earliest is None or t < earliest:
                earliest = t

        if earliest is None or base_min is None or pd.isna(base_min) or earliest >= base_min:
            DF_HIST_MILESTONE = base          # 现有窗口已覆盖，无需补下载
            return DF_HIST_MILESTONE

        start = (earliest - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
        end = base_min.strftime("%Y-%m-%d")
        tickers = list(dict.fromkeys(list(base["Ticker"].astype(str).tolist()) + need_tickers))
        print(f"📡 [里程碑宽窗口] 补取 {start} → {end} 的历史 OHLC（{len(tickers)} 只，现有窗口最早 {base_min.date()}）...")
        # 分块下载：一次性请求过多 ticker 极易超时/被限流导致整批失败；分块保证部分成功也可使用。
        early_frames = []
        CHUNK = 30
        for i in range(0, len(tickers), CHUNK):
            chunk = tickers[i:i + CHUNK]
            part, _ = download_ohlc_safe(chunk, start=start, end=end)
            if part is not None and not part.empty:
                early_frames.append(part)
        if not early_frames:
            DF_HIST_MILESTONE = base
        else:
            early = pd.concat(early_frames, ignore_index=True)
            merged = pd.concat([early, base], ignore_index=True)
            # 去重：分块下载与 base 可能在边界日重叠，按 (Ticker, 交易日) 去重，避免取第 N 根 bar 错位
            _norm = _normalize_market_dates(merged["Date"])
            _key = merged["Ticker"].astype(str).str.upper() + "|" + _norm.dt.strftime("%Y-%m-%d")
            DF_HIST_MILESTONE = merged.loc[~_key.duplicated(keep="first")].reset_index(drop=True)
    except Exception as e:
        print(f"⚠️ [里程碑宽窗口] 构建失败，退化为现有窗口：{e}")
        DF_HIST_MILESTONE = base
    return DF_HIST_MILESTONE


def get_milestone_history():
    """里程碑计算统一入口（懒构建 + 缓存）。"""
    if DF_HIST_MILESTONE is None:
        return build_milestone_history()
    return DF_HIST_MILESTONE


def get_nth_trading_day_bar(df_hist, ticker, rec_date, n, asof=None):
    """Rec_Date 之后第 n 根有效 OHLCV bar 的 (日期, 收盘价)。

    交易日历 = OHLCV bar 的 Date 列（真实交易日），而不是自然日、也不是 pd.bdate_range。
    定义（不变）：date > rec_date、升序、iloc[n-1]。

    fail-closed（新增）：
      - rec_date 之后第一根 bar 与 rec_date 的自然日距离 > MILESTONE_WINDOW_TOLERANCE_DAYS
        → 说明历史窗口没有覆盖 rec_date，直接返回 (None, None)，绝不取错误的第 N 根 bar；
      - 不足 n 根 / 数据缺失 → (None, None)，绝不用当前价或最近价顶替。
    asof（新增，可选）：只允许使用 date <= asof 的 bar（历史行回补用，禁止预写未来 milestone）。
    """
    try:
        if df_hist is None or df_hist.empty or not n or n < 1:
            return None, None
        sub = df_hist[df_hist["Ticker"].astype(str).str.upper() == str(ticker).upper()].copy()
        if sub.empty:
            return None, None
        sub["_d"] = _normalize_market_dates(sub["Date"])
        base = pd.Timestamp(rec_date).normalize()
        sub = sub[sub["_d"] > base].sort_values("_d")
        if sub.empty or len(sub) < n:
            return None, None
        gap = (sub.iloc[0]["_d"] - base).days
        if gap is None or gap < 0 or gap > MILESTONE_WINDOW_TOLERANCE_DAYS:
            return None, None
        row = sub.iloc[n - 1]
        if asof is not None:
            limit = pd.Timestamp(asof).normalize()
            if row["_d"] > limit:
                return None, None
        return row["_d"].strftime("%Y-%m-%d"), safe_float(row.get("close"))
    except Exception:
        return None, None


def get_nth_trading_day_close(df_hist, ticker, rec_date, n, asof=None):
    """Rec_Date 之后第 n 根有效 OHLCV bar 的收盘价（get_nth_trading_day_bar 的收盘价视图）。"""
    _d, close = get_nth_trading_day_bar(df_hist, ticker, rec_date, n, asof=asof)
    return close


def compute_review_milestones(ticker, rec_date, rec_price, status):
    """计算单个推荐事件的 5D/10D/20D 里程碑客观收盘价 + PnL + Review_Stage。

    - 价格来自 OHLCV 的「Rec_Date 之后第 N 根 bar」客观收盘，与是否提前退出无关。
    - 未来 milestone 未到 → null；不猜未来价、不用当前价。
    - PnL_N = (Price_N - Rec_Price) / Rec_Price * 100，round(..., 2)；Rec_Price 缺失则 PnL 为 null。
    - Review_Stage：FINAL（status ∈ CLOSED_STOCK_STATUSES）> 20D > 10D > 5D > OPEN。
    - 期权不参与（调用方保证不传期权）。
    """
    out = {
        "Price_5D": "", "PnL_5D": "",
        "Price_10D": "", "PnL_10D": "",
        "Price_20D": "", "PnL_20D": "",
        "Review_Stage": "OPEN",
    }
    rp = safe_float(rec_price)
    for label, n in (("5", 5), ("10", 10), ("20", 20)):
        px = get_nth_trading_day_close(get_milestone_history(), ticker, rec_date, n)
        pnl = None
        if px is not None and rp is not None and rp > 0:
            pnl = round((px - rp) / rp * 100, 2)
        out[f"Price_{label}D"] = "" if px is None else str(px)
        out[f"PnL_{label}D"] = "" if pnl is None else str(pnl)

    if clean_text(status) in CLOSED_STOCK_STATUSES:
        out["Review_Stage"] = "FINAL"
    elif out["Price_20D"] != "":
        out["Review_Stage"] = "20D"
    elif out["Price_10D"] != "":
        out["Review_Stage"] = "10D"
    elif out["Price_5D"] != "":
        out["Review_Stage"] = "5D"
    else:
        out["Review_Stage"] = "OPEN"
    return out


def _compute_milestones_asof(hist, ticker, rec_date, rec_price, asof):
    """按 asof 上限计算单个推荐事件的 5D/10D/20D 里程碑（纯函数，供回补与离线测试复用）。

    返回 dict：Price_5D/PnL_5D/Price_10D/PnL_10D/Price_20D/PnL_20D（字符串，未达成为空串）。
    - 第 N 个交易日 bar 日期 > asof → 该 milestone 为空（尚未达成，绝不预写未来）。
    - 行情缺失 / 无法确认交易日 → 为空（fail-closed，绝不猜价 / 补价 / 用非交易日）。
    - Price_N <= 0 或 Rec_Price <= 0 → PnL 为空；Price_N <= 0 → Price 也为空。
    - PnL_N = round((Price_N - Rec_Price) / Rec_Price * 100, 2)。
    """
    out = {"Price_5D": "", "PnL_5D": "", "Price_10D": "", "PnL_10D": "", "Price_20D": "", "PnL_20D": ""}
    rp = safe_float(rec_price)
    for label, n in (("5", 5), ("10", 10), ("20", 20)):
        _d, px = get_nth_trading_day_bar(hist, ticker, rec_date, n, asof=asof)
        pnl = None
        if px is not None and px > 0 and rp is not None and rp > 0:
            pnl = round((px - rp) / rp * 100, 2)
        out["Price_%sD" % label] = "" if (px is None or px <= 0) else str(px)
        out["PnL_%sD" % label] = "" if pnl is None else str(pnl)
    return out


def compute_milestone_win_rate(events):
    """统计 5D / 10D / 20D milestone win rate（纯函数，离线可测）。

    events: list of dict，每项含 pnl_5d / pnl_10d / pnl_20d（float 或 None）。

    规则（只读统计，不修改 milestone 数据）：
      - Win  = PnL_N > 0；
      - Loss = PnL_N <= 0（含 0）；
      - Eligible = Wins + Losses，即只有「已有有效 PnL_N」的记录进入分母；
      - PnL_N 缺失 / 未达标 / Rec_Price 缺失 / Price_N 缺失 → 不进入分母（None 跳过）；
      - win_rate = Wins / Eligible * 100；Eligible == 0 → win_rate = None（前端显示 N/A）。

    返回 {"5D": {...}, "10D": {...}, "20D": {...}}，每个含 eligible/wins/losses/win_rate。
    """
    result = {}
    for label in ("5D", "10D", "20D"):
        key = "pnl_" + label.lower()
        vals = [safe_float(e.get(key)) for e in events]
        vals = [v for v in vals if v is not None]
        wins = sum(1 for v in vals if v > 0)
        losses = sum(1 for v in vals if v <= 0)
        eligible = len(vals)
        win_rate = (wins / eligible * 100) if eligible else None
        result[label] = {
            "eligible": eligible,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
        }
    return result


def backfill_review_milestones():
    """幂等回补 review_history.csv 中仍为空的里程碑字段（P0 修复版）。

    严格规则：
      - 只读已有行，绝不新建任何行（尤其是当前池内没有 review 行的事件，不会自动创建）；
      - as-of 上限：
          · CLOSED 事件（该事件存在 Status ∈ CLOSED_STOCK_STATUSES 的行）→ 上限 =
            实际 Close_Date（最早出现 CLOSED 状态的 Review_Date）；milestone 在 Close_Date
            之前已达成才回填，超过 Close_Date 才达成的保持空（不读取 Close_Date 之后的数据）。
          · OPEN 事件 → 上限 = 当前复盘交易日 REVIEW_SESSION_DATE；只要当前日期已实际
            经过 5D/10D/20D，就回填。
      - 只写真实 OHLCV bar 的收盘价；窗口未覆盖 rec_date / 行情缺失 → fail-closed 留空；
      - 已存在的真实值一律不覆盖；写入前校验 Price_N > 0、Rec_Price > 0、PnL 公式；
      - 期权行（Option_Type/Strike/Expiry 非空）不参与；
      - 回补后按 FINAL > 20D > 10D > 5D > OPEN 重算 Review_Stage（原 FINAL 保持 FINAL）。
    """
    if not os.path.exists(REVIEW_HISTORY) or os.path.getsize(REVIEW_HISTORY) == 0:
        print("ℹ️ [里程碑回补] review_history.csv 不存在或为空，跳过。")
        return 0
    try:
        od = pd.read_csv(REVIEW_HISTORY, dtype=str, keep_default_na=False, on_bad_lines="skip")
    except Exception as e:
        print(f"⚠️ [里程碑回补] 读取失败：{e}")
        return 0
    for c in REVIEW_COLUMNS:
        if c not in od.columns:
            od[c] = ""
    od = od[REVIEW_COLUMNS]

    hist = get_milestone_history()

    # P0：事件级 Close_Date。key=(Ticker, Rec_Date, Tag)；value=最早出现 CLOSED 状态的 Review_Date。
    # 一个事件可能有多行（每日快照），只有明确 CLOSED 的行才算真正关闭。
    close_dates = {}
    for _, r in od.iterrows():
        if clean_text(r.get("Status")) not in CLOSED_STOCK_STATUSES:
            continue
        _tk = clean_text(r.get("Ticker")).upper()
        _rec = clean_text(r.get("Rec_Date"))[:10]
        if not _tk or not _rec:
            continue
        _rd = clean_text(r.get("Review_Date"))[:10]
        if not _rd:
            continue
        key = (_tk, _rec, clean_text(r.get("Tag")))
        if key not in close_dates or _rd < close_dates[key]:
            close_dates[key] = _rd

    filled = {"5D": 0, "10D": 0, "20D": 0}
    stage_changed = 0
    rows_changed = 0

    for idx, row in od.iterrows():
        # 期权行不参与股票里程碑
        if clean_text(row.get("Option_Type")) or clean_text(row.get("Strike")) or clean_text(row.get("Expiry")):
            continue
        tk = clean_text(row.get("Ticker")).upper()
        rec = clean_text(row.get("Rec_Date"))[:10]
        if not tk or not rec:
            continue
        key = (tk, rec, clean_text(row.get("Tag")))
        # P0：CLOSED 事件回补到实际 Close_Date；OPEN 事件回补到当前复盘交易日
        # （不再用该行自己的 Review_Date 冻结，避免历史事件永远补不上已过去的 milestone）。
        asof = close_dates.get(key) or REVIEW_SESSION_DATE
        if not asof:
            continue
        rp = safe_float(row.get("Rec_Price"))
        computed = _compute_milestones_asof(hist, tk, rec, rp, asof)
        touched = False
        vals = {}
        for label in ("5", "10", "20"):
            cur_p = clean_text(row.get("Price_%sD" % label))
            cur_n = clean_text(row.get("PnL_%sD" % label))
            if cur_p and cur_n:
                vals[label] = (cur_p, cur_n)          # 已有真实值：不覆盖
                continue
            new_p = computed["Price_%sD" % label]
            new_n = computed["PnL_%sD" % label]
            if new_p != cur_p or new_n != cur_n:
                od.at[idx, "Price_%sD" % label] = new_p
                od.at[idx, "PnL_%sD" % label] = new_n
                if new_p:
                    filled["%sD" % label] += 1
                touched = True
            vals[label] = (new_p, new_n)

        st_old = clean_text(row.get("Review_Stage"))
        st_new = _milestone_stage(row.get("Status"), vals["5"][0], vals["10"][0], vals["20"][0], st_old)
        if st_new != st_old:
            od.at[idx, "Review_Stage"] = st_new
            stage_changed += 1
            touched = True
        if touched:
            rows_changed += 1

    if rows_changed:
        od.to_csv(REVIEW_HISTORY, index=False, encoding="utf-8")
    print(f"🔧 [里程碑回补] 影响 {rows_changed} 行 · 新增 5D={filled['5D']} 10D={filled['10D']} 20D={filled['20D']}"
          f" · Stage 更新 {stage_changed} 行")
    return rows_changed


def backfill_rec_price():
    """幂等：review_history.csv 的 Rec_Price 统一修正为 Rec_Date 真实 Open。

    - 只读已有行，绝不新建；
    - Rec_Date 有真实 OHLC → Rec_Price = Rec_Date Open（旧值无论是什么一律改成 Open）；
    - Rec_Date 无真实 OHLC（非交易日/停牌/数据缺失/限流导致抓取失败）→ fail-closed：
        · 旧 Rec_Price 已是有效正数 → **保留原值**，绝不因网络/限流/历史数据获取失败
          把已有有效买入价清空（P1 修复：此前误清空 1225 条历史数据）；
        · 旧 Rec_Price 为空或无效（0/负数/非数字）→ 继续为空；
      两种情况都不 fallback 到 Prev_Close / Close_Price / Scan_Ref_Price / 实时 quote /
      最近交易日价格，也不做任何估算；
    - 期权行跳过；
    - Rec_Price 数值变化后：重算 PnL_5D/10D/20D（round((PN-Rec_Price)/Rec_Price*100, 2) 不变），
      Price_N 为空或 Rec_Price 为空时 PnL 置空；
    - 重算 Review_Stage（FINAL > 20D > 10D > 5D > OPEN，原 FINAL 保持 FINAL）；
    - 幂等：Rec_Price 已等于 Open 的行跳过。
    """
    if not os.path.exists(REVIEW_HISTORY) or os.path.getsize(REVIEW_HISTORY) == 0:
        print("ℹ️ [买入价回填] review_history.csv 不存在或为空，跳过。")
        return 0
    try:
        od = pd.read_csv(REVIEW_HISTORY, dtype=str, keep_default_na=False, on_bad_lines="skip")
    except Exception as e:
        print(f"⚠️ [买入价回填] 读取失败：{e}")
        return 0
    for c in REVIEW_COLUMNS:
        if c not in od.columns:
            od[c] = ""
    od = od[REVIEW_COLUMNS]

    hist = get_milestone_history()
    changed = 0
    cleared = 0
    preserved = 0
    pnl_changed = {"5D": 0, "10D": 0, "20D": 0}
    stage_changed = 0

    for idx, row in od.iterrows():
        if clean_text(row.get("Option_Type")) or clean_text(row.get("Strike")) or clean_text(row.get("Expiry")):
            continue
        tk = clean_text(row.get("Ticker"))
        rec = clean_text(row.get("Rec_Date"))[:10]
        if not tk or not rec:
            continue
        ohlc = get_exact_date_ohlc(hist, tk, rec)
        new_price = safe_float(ohlc.get("open")) if ohlc else None
        if new_price is not None and new_price <= 0:
            new_price = None          # 非正数 Open 不是真实买入价，按“未可靠取得”处理
        old_price = safe_float(row.get("Rec_Price"))
        old_valid = old_price is not None and old_price > 0
        if new_price is None and old_valid:
            # P1 fail-closed：无法取得 Rec_Date 当天真实 OHLC 时，
            # 若已有有效买入价则原样保留（不因限流/网络/历史缺失清空有效值）。
            preserved += 1
            continue
        if (old_price is None and new_price is None) or \
           (old_price is not None and new_price is not None and abs(old_price - new_price) < 1e-6):
            continue
        od.at[idx, "Rec_Price"] = "" if new_price is None else str(new_price)
        changed += 1
        if new_price is None:
            cleared += 1
        rp = new_price
        for label, n in (("5", 5), ("10", 10), ("20", 20)):
            px = safe_float(row.get("Price_%sD" % label))
            old_pnl = clean_text(row.get("PnL_%sD" % label))
            if px is not None and rp is not None and rp > 0:
                new_pnl = str(round((px - rp) / rp * 100, 2))
            else:
                new_pnl = ""
            if new_pnl != old_pnl:
                od.at[idx, "PnL_%sD" % label] = new_pnl
                pnl_changed["%sD" % label] += 1
        st_old = clean_text(row.get("Review_Stage"))
        st_new = _milestone_stage(row.get("Status"), od.at[idx, "Price_5D"],
                                  od.at[idx, "Price_10D"], od.at[idx, "Price_20D"], st_old)
        if st_new != st_old:
            od.at[idx, "Review_Stage"] = st_new
            stage_changed += 1

    if changed:
        od.to_csv(REVIEW_HISTORY, index=False, encoding="utf-8")
    print(f"🔧 [买入价回填] 影响 {changed} 行（改为 Rec_Date Open，其中 {cleared} 行因无 OHLC 置空）· "
          f"保留 {preserved} 行（无 OHLC 但原值有效）· "
          f"PnL 重算 5D={pnl_changed['5D']} 10D={pnl_changed['10D']} 20D={pnl_changed['20D']} · "
          f"Stage 更新 {stage_changed}")
    return changed


review_rows = []

for item in active_list:
    _ms = compute_review_milestones(item["代码"], item["首次推荐日"], item["首次推荐价"], "持仓中")
    review_rows.append({
        "Review_Date":REVIEW_SESSION_DATE,"Ticker":item["代码"],"Name":item["名称"],"Tag":item["标签"],
        "Rec_Date":item["首次推荐日"],"Rec_Price":item["首次推荐价"],"Cur_Price":item["现价"],
        "Days_Held":item["持仓天数"],"PnL_Pct":item["当前盈亏(%)"],"Maturity_PnL":"",
        "Hold_Period":"动态持有","Stop_Loss":item["止损价"],
        "Stop_Method":item.get("止损方法","MA20/MA50 + ATR + MACD/KDJ"),
        "Trail_Stop":item.get("止损价",""),"Rec_Count":item["系统连续推荐次数"],"Status":"持仓中",
        "Score":item["推荐评分"],"Review_Risk_Status":item.get("Review_Risk_Status",""),
        "Review_Risk_Date":item.get("Review_Risk_Date",""),
        "Review_Stop_Distance_Pct":item.get("Review_Stop_Distance_Pct",""),
        "Review_Risk_Note":item.get("Review_Risk_Note",""),
        "Option_Type":"","Strike":"","Expiry":"",
        "Price_5D":_ms["Price_5D"],"PnL_5D":_ms["PnL_5D"],
        "Price_10D":_ms["Price_10D"],"PnL_10D":_ms["PnL_10D"],
        "Price_20D":_ms["Price_20D"],"PnL_20D":_ms["PnL_20D"],
        "Review_Stage":_ms["Review_Stage"]
    })

for item in stopped_list:
    _ms = compute_review_milestones(item["代码"], item["首次推荐日"], item["首次推荐价"], "移动止损清仓")
    review_rows.append({
        "Review_Date":REVIEW_SESSION_DATE,"Ticker":item["代码"],"Name":item["名称"],"Tag":item["标签"],
        "Rec_Date":item["首次推荐日"],"Rec_Price":item["首次推荐价"],"Cur_Price":item["止损结算价"],
        "Days_Held":item["持仓天数"],"PnL_Pct":item["止损盈亏(%)"],"Maturity_PnL":item["止损盈亏(%)"],
        "Hold_Period":"动态持有","Stop_Loss":item["止损价"],
        "Stop_Method":item.get("Stop_Method","MA20/MA50 + ATR + MACD/KDJ"),
        "Trail_Stop":item.get("止损价",""),"Rec_Count":item["系统连续推荐次数"],"Status":"移动止损清仓",
        "Score":item["推荐评分"],"Review_Risk_Status":"STOP_TRIGGERED","Review_Risk_Date":REVIEW_SESSION_DATE,
        "Review_Stop_Distance_Pct":0,"Review_Risk_Note":f"移动止损触发：{item.get('止损价','')}",
        "Option_Type":"","Strike":"","Expiry":"",
        "Price_5D":_ms["Price_5D"],"PnL_5D":_ms["PnL_5D"],
        "Price_10D":_ms["Price_10D"],"PnL_10D":_ms["PnL_10D"],
        "Price_20D":_ms["Price_20D"],"PnL_20D":_ms["PnL_20D"],
        "Review_Stage":_ms["Review_Stage"]
    })

for item in observation_list:
    _ms = compute_review_milestones(item["代码"], item["首次推荐日"], item.get("首次推荐价",""), "观察推荐")
    review_rows.append({
        "Review_Date":REVIEW_SESSION_DATE,"Ticker":item["代码"],"Name":item["名称"],"Tag":"Observation",
        "Rec_Date":item["首次推荐日"],"Rec_Price":item.get("首次推荐价",""),"Cur_Price":item.get("当前价格",""),
        "Days_Held":"","PnL_Pct":item.get("推荐跟踪涨跌幅(%)"),"Maturity_PnL":"",
        "Hold_Period":"观察","Stop_Loss":"","Stop_Method":"观察，不触发持仓止损","Trail_Stop":"",
        "Rec_Count":item.get("系统连续推荐次数","1"),"Status":"观察推荐","Score":item.get("推荐评分","N/A"),
        "Review_Risk_Status":"OBSERVATION","Review_Risk_Date":REVIEW_SESSION_DATE,
        "Review_Stop_Distance_Pct":"","Review_Risk_Note":"有效 Scan 推荐；不作为实际持仓，但纳入推荐绩效追踪。",
        "Option_Type":"","Strike":"","Expiry":"",
        "Price_5D":_ms["Price_5D"],"PnL_5D":_ms["PnL_5D"],
        "Price_10D":_ms["Price_10D"],"PnL_10D":_ms["PnL_10D"],
        "Price_20D":_ms["Price_20D"],"PnL_20D":_ms["PnL_20D"],
        "Review_Stage":_ms["Review_Stage"]
    })

for opt in option_closed_records:
    review_rows.append({
        "Review_Date":REVIEW_SESSION_DATE,"Ticker":opt["ticker"],"Name":opt["ticker"]+" OPT","Tag":"期权平仓",
        "Rec_Date":opt["expiry"],"Rec_Price":opt["entry_price"],"Cur_Price":opt["close_price"],
        "Days_Held":"","PnL_Pct":opt["pnl"],"Maturity_PnL":opt["pnl"],"Hold_Period":"",
        "Stop_Loss":"","Stop_Method":"","Trail_Stop":"","Rec_Count":"","Status":"期权平仓","Score":opt["reason"],
        "Review_Risk_Status":"","Review_Risk_Date":"","Review_Stop_Distance_Pct":"","Review_Risk_Note":"",
        "Option_Type":opt["option_type"],"Strike":opt["strike"],"Expiry":opt["expiry"]
    })

append_review_rows(review_rows)

# 历史行里程碑回补（幂等；milestone 达成日必须 <= 该行自己的 Review_Date）
backfill_review_milestones()

# 推荐买入价统一（幂等）：Rec_Price = Rec_Date 真实 Open；无 OHLC 则置空；变化后重算 PnL/Stage
backfill_rec_price()


# ============================================================
# 13. 每次 Scan 推荐事件的独立追踪
# ============================================================

def _load_scan_recommendation_files():
    """
    Scan 推荐事件的第一数据源：
    us_stocks_pending_YYYYMMDD.csv 及 .processed。

    这是 Scan 的原始输出，比 trade_history 更适合作为
    “每一次 Scan 推荐 = 一笔推荐事件”的统计来源。
    """
    files = sorted(
        glob.glob("us_stocks_pending_*.csv")
        + glob.glob("us_stocks_pending_*.csv.processed")
    )
    cutoff = pd.Timestamp(today_us_str()) - pd.Timedelta(days=30)
    records = []

    for filename in files:
        m = re.search(
            r"us_stocks_pending_(\d{8})\.csv(?:\.processed)?$",
            os.path.basename(filename),
        )
        if not m:
            continue

        try:
            file_date = pd.Timestamp(datetime.datetime.strptime(m.group(1), "%Y%m%d"))
        except Exception:
            continue

        if file_date < cutoff:
            continue

        try:
            d = pd.read_csv(
                filename,
                dtype=str,
                keep_default_na=False,
                on_bad_lines="skip",
            )
        except Exception as e:
            print(f"⚠️ 读取 Scan 推荐文件失败 {filename}: {e}")
            continue

        if d.empty or "Ticker" not in d.columns:
            continue

        for _, row in d.iterrows():
            ticker = resolve_ticker(row.get("Ticker"), row.get("Name"))
            if not ticker:
                continue

            # Scan 推荐价优先使用 Scan_Ref_Price；其次才是 Price。
            rec_price = safe_float(row.get("Scan_Ref_Price"))
            if rec_price is None:
                rec_price = safe_float(row.get("Price"))

            records.append({
                "ticker": ticker,
                "name": clean_text(row.get("Name"), ticker),
                "rec_date": file_date.strftime("%Y-%m-%d"),
                "rec_price": rec_price,
                "tag": clean_text(row.get("Tag")),
                "score": clean_text(row.get("Score"), "N/A"),
                "source_file": os.path.basename(filename),
            })

    return records


def _load_trade_event_lookup():
    """按 Date+Ticker 保存 trade_history 中与推荐事件对应的状态。"""
    d = load_trade_history()
    lookup = {}
    if d.empty:
        return lookup

    for _, row in d.iterrows():
        rec_date = normalize_date(row.get("Date"))
        ticker = resolve_ticker(row.get("Ticker"), row.get("Name"))
        if rec_date is None or not ticker:
            continue
        key = (rec_date.strftime("%Y-%m-%d"), ticker)
        lookup[key] = row.to_dict()

    return lookup


def _load_review_closed_lookup():
    """从 review_history 找已归档事件的退出价/PnL 兜底。"""
    lookup = {}
    if not os.path.exists(REVIEW_HISTORY) or os.path.getsize(REVIEW_HISTORY) == 0:
        return lookup
    try:
        d = pd.read_csv(
            REVIEW_HISTORY,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="skip",
        )
        if d.empty:
            return lookup
        for _, row in d.iterrows():
            rec_date = normalize_date(row.get("Rec_Date"))
            ticker = resolve_ticker(row.get("Ticker"), row.get("Name"))
            if rec_date is None or not ticker:
                continue
            status = clean_text(row.get("Status"))
            if status in {"移动止损清仓", "止损触发清仓", "已超期归档", "周期到期清仓", "突发清仓暂停"}:
                key = (rec_date.strftime("%Y-%m-%d"), ticker)
                lookup[key] = row.to_dict()
        return lookup
    except Exception as e:
        print(f"⚠️ 读取 review_history 归档兜底失败：{e}")
        return lookup


def build_scan_recommendation_events():
    """
    统一推荐事件账本：
    - 以 review_history.csv 的 Rec_Date + Ticker + Tag 作为推荐事件主键。
    - Review 每天重复记录同一推荐时只保留该推荐事件的最新状态。
    - Rec_Date 按推荐发生日过滤最近30天，而不是 Review_Date。
    - 当前仍开放的推荐使用当天真实价格；已退出推荐优先使用退出价格。
    - Observation 同样是有效 Scan 推荐，必须进入绩效追踪。
    - 不把期权记录纳入股票推荐事件。
    - 若 review_history 无法提供事件，则用 trade_history.csv 作为补充来源。
    """

    event_rows = []

    # --------------------------------------------------------
    # 主来源：review_history.csv
    # --------------------------------------------------------
    if os.path.exists(REVIEW_HISTORY) and os.path.getsize(REVIEW_HISTORY) > 0:
        try:
            rh = pd.read_csv(
                REVIEW_HISTORY,
                dtype=str,
                keep_default_na=False,
                on_bad_lines="skip",
            )
            if not rh.empty and {"Rec_Date", "Ticker", "Rec_Price"}.issubset(rh.columns):
                rh["_rec_dt"] = pd.to_datetime(
                    rh["Rec_Date"], errors="coerce", format="mixed"
                )
                rh["_review_dt"] = pd.to_datetime(
                    rh.get("Review_Date", ""), errors="coerce", format="mixed"
                )
                cutoff = pd.Timestamp(today_us_str()) - pd.Timedelta(days=30)
                rh = rh[rh["_rec_dt"].notna() & (rh["_rec_dt"] >= cutoff)].copy()

                if "Option_Type" not in rh.columns:
                    rh["Option_Type"] = ""
                if "Tag" not in rh.columns:
                    rh["Tag"] = ""
                if "Status" not in rh.columns:
                    rh["Status"] = ""
                if "Cur_Price" not in rh.columns:
                    rh["Cur_Price"] = ""
                if "Exit_Price" not in rh.columns:
                    rh["Exit_Price"] = ""

                # 股票推荐：排除期权记录。
                rh = rh[
                    rh["Option_Type"].astype(str).str.strip().eq("")
                ].copy()

                # 每次 Scan 推荐事件 = Rec_Date + Ticker + Tag。
                # 同一事件在后续 Review 中每天重复出现，只取最后一次状态。
                rh["_ticker_norm"] = rh["Ticker"].map(lambda x: resolve_ticker(x))
                rh["_tag_norm"] = rh["Tag"].astype(str).str.strip()
                rh = rh[rh["_ticker_norm"].astype(str).str.len() > 0].copy()
                rh = rh.sort_values(["_rec_dt", "_review_dt"])

                grouped = rh.groupby(
                    ["_rec_dt", "_ticker_norm", "_tag_norm"],
                    sort=True,
                    dropna=False,
                )

                for (_, _, _), g in grouped:
                    row = g.iloc[-1]
                    rec_dt = row["_rec_dt"]
                    ticker = row["_ticker_norm"]
                    rec_price = safe_float(row.get("Rec_Price"))
                    if rec_price is None or rec_price <= 0:
                        event_rows.append({
                            "ticker": ticker,
                            "name": clean_text(row.get("Name"), ticker),
                            "rec_date": rec_dt.strftime("%Y-%m-%d"),
                            "rec_price": None,
                            "status": clean_text(row.get("Status")),
                            "tag": clean_text(row.get("Tag")),
                            "current_price": None,
                            "pnl": None,
                            "data_status": "NO_REC_PRICE",
                        })
                        continue

                    status = clean_text(row.get("Status"))
                    exit_price = safe_float(row.get("Exit_Price"))

                    closed_statuses = {
                        "Stop_Loss_Hit",
                        "移动止损清仓",
                        "止损触发清仓",
                        "已超期归档",
                        "突发清仓暂停",
                        "周期到期清仓",
                        "Observation_Closed",
                    }

                    if status in closed_statuses and exit_price is not None:
                        cur = exit_price
                    else:
                        # 以当前真实行情刷新当前开放/Observation 推荐。
                        cur = safe_float(price_map_today.get(ticker))
                        if cur is None:
                            # review_history 中最后一次 Review 已有 Cur_Price 时可作为历史兜底，
                            # 但今天能取得真实行情时优先使用今天的价格。
                            cur = safe_float(row.get("Cur_Price"))

                    pnl = (
                        round((cur - rec_price) / rec_price * 100, 2)
                        if cur is not None and rec_price > 0
                        else None
                    )

                    event_rows.append({
                        "ticker": ticker,
                        "name": clean_text(row.get("Name"), ticker),
                        "rec_date": rec_dt.strftime("%Y-%m-%d"),
                        "rec_price": rec_price,
                        "status": status,
                        "tag": clean_text(row.get("Tag")),
                        "current_price": cur,
                        "pnl": pnl,
                        "data_status": "OK" if pnl is not None else "PRICE_MISSING",
                    })

        except Exception as e:
            print(f"⚠️ 从 review_history 重建 Scan 推荐事件失败：{e}")

    # --------------------------------------------------------
    # 补充来源：trade_history.csv
    # 某些刚产生、尚未写入 review_history 的事件也要纳入。
    # --------------------------------------------------------
    if os.path.exists(TRADE_HISTORY) and os.path.getsize(TRADE_HISTORY) > 0:
        try:
            th = load_trade_history()
            if not th.empty:
                cutoff = pd.Timestamp(today_us_str()) - pd.Timedelta(days=30)
                th = th[th["Date"] >= cutoff].copy()

                for _, row in th.iterrows():
                    ticker = resolve_ticker(row.get("Ticker"), row.get("Name"))
                    if not ticker:
                        continue
                    rec_dt = normalize_date(row.get("Date"))
                    if rec_dt is None:
                        continue
                    rec_price = safe_record_price(row)
                    tag = clean_text(row.get("Tag"))
                    key = (
                        ticker.upper(),
                        rec_dt.strftime("%Y-%m-%d"),
                        tag,
                    )

                    # 已存在的 review_history 事件不重复追加。
                    exists = any(
                        (e["ticker"].upper(), e["rec_date"], e["tag"]) == key
                        for e in event_rows
                    )
                    if exists:
                        continue

                    exit_price = safe_float(row.get("Exit_Price"))
                    status = clean_text(row.get("Status"))
                    if status in {
                        "Stop_Loss_Hit", "移动止损清仓", "止损触发清仓",
                        "已超期归档", "突发清仓暂停", "周期到期清仓", "Observation_Closed"
                    } and exit_price is not None:
                        cur = exit_price
                    else:
                        cur = safe_float(price_map_today.get(ticker))

                    pnl = (
                        round((cur-rec_price)/rec_price*100,2)
                        if rec_price and rec_price > 0 and cur is not None
                        else None
                    )
                    event_rows.append({
                        "ticker":ticker,
                        "name":clean_text(row.get("Name"),ticker),
                        "rec_date":rec_dt.strftime("%Y-%m-%d"),
                        "rec_price":rec_price,
                        "status":status,
                        "tag":tag,
                        "current_price":cur,
                        "pnl":pnl,
                        "data_status":"OK" if pnl is not None else ("NO_REC_PRICE" if rec_price is None else "PRICE_MISSING"),
                    })
        except Exception as e:
            print(f"⚠️ 从 trade_history 补充 Scan 推荐事件失败：{e}")

    # 最终稳定排序：推荐日期 -> ticker -> tag
    event_rows.sort(key=lambda x: (x.get("rec_date", ""), x.get("ticker", ""), x.get("tag", "")))
    return event_rows

scan_events = build_scan_recommendation_events()

# 用统一推荐事件账本中的最新价格刷新 Observation 展示，避免仅依赖第一次行情下载。
_event_price_map = {(e["ticker"].upper(), e["rec_date"], e["tag"]): e for e in scan_events}
for _obs in observation_list:
    _key = (clean_text(_obs.get("代码")).upper(), clean_text(_obs.get("首次推荐日")), "Observation")
    _evt = _event_price_map.get(_key)
    if _evt is not None and _evt.get("current_price") is not None:
        _obs["当前价格"] = _evt["current_price"]
        _obs["推荐跟踪涨跌幅(%)"] = _evt.get("pnl")


# 只统计最近30天 Scan 推荐事件
recent_event_cutoff = pd.Timestamp(today_us_str()) - pd.Timedelta(days=30)
scan_events_30d = [
    e for e in scan_events
    if normalize_date(e["rec_date"]) is not None
    and normalize_date(e["rec_date"]) >= recent_event_cutoff
]


# ============================================================
# ============================================================
# 13. KPI —— 精简版：Core / Observation / 实际持仓 / 期权
# ============================================================

# 说明：
# 1) Core 与 Observation 永久分开统计。
# 2) 实际持仓是 Core 的子集，不是第三种推荐类型。
# 3) 当前浮盈/浮亏只进入“当前跟踪”。
# 4) 只有真实结束、且有退出价格的推荐才进入“已完成胜率”。
# 5) 期权完全独立，不进入股票 KPI。

stock_events_valid = [
    e for e in scan_events_30d
    if e.get("pnl") is not None
]

stock_events_missing = [
    e for e in scan_events_30d
    if e.get("pnl") is None
]


# ============================================================
# 推荐类型拆分
# ============================================================

core_events_30d = [
    e for e in scan_events_30d
    if clean_text(e.get("tag")) != "Observation"
]

observation_events_30d = [
    e for e in scan_events_30d
    if clean_text(e.get("tag")) == "Observation"
]


# ============================================================
# 明确的股票结束状态（CLOSED_STOCK_STATUSES 已在 12b 里程碑阶段提前定义，这里复用）
# ============================================================


def _event_is_closed(e):
    """只有明确结束状态 + 有 PnL 才进入已完成胜率。"""
    status = clean_text(e.get("status"))
    return (
        status in CLOSED_STOCK_STATUSES
        and e.get("pnl") is not None
    )


# ============================================================
# Core 已完成
# ============================================================

core_closed = [
    e for e in core_events_30d
    if _event_is_closed(e)
]

core_closed_pnl = [
    safe_float(e.get("pnl"))
    for e in core_closed
    if safe_float(e.get("pnl")) is not None
]

core_closed_wins = sum(p > 0 for p in core_closed_pnl)
core_closed_losses = sum(p < 0 for p in core_closed_pnl)
core_closed_neutral = sum(p == 0 for p in core_closed_pnl)
core_closed_win_rate = (
    core_closed_wins / len(core_closed_pnl) * 100
    if core_closed_pnl else 0.0
)


# ============================================================
# Core 当前跟踪
# ============================================================

core_open = [
    e for e in core_events_30d
    if not _event_is_closed(e)
    and e.get("pnl") is not None
]

core_open_pnl = [
    safe_float(e.get("pnl"))
    for e in core_open
    if safe_float(e.get("pnl")) is not None
]

core_open_wins = sum(p > 0 for p in core_open_pnl)
core_open_losses = sum(p < 0 for p in core_open_pnl)
core_open_neutral = sum(p == 0 for p in core_open_pnl)
core_open_win_rate = (
    core_open_wins / len(core_open_pnl) * 100
    if core_open_pnl else 0.0
)


# ============================================================
# Observation 已完成
# ============================================================

obs_closed = [
    e for e in observation_events_30d
    if _event_is_closed(e)
]

obs_closed_pnl = [
    safe_float(e.get("pnl"))
    for e in obs_closed
    if safe_float(e.get("pnl")) is not None
]

obs_closed_wins = sum(p > 0 for p in obs_closed_pnl)
obs_closed_losses = sum(p < 0 for p in obs_closed_pnl)
obs_closed_neutral = sum(p == 0 for p in obs_closed_pnl)
obs_closed_win_rate = (
    obs_closed_wins / len(obs_closed_pnl) * 100
    if obs_closed_pnl else 0.0
)


# ============================================================
# Observation 当前跟踪
# ============================================================

obs_open = [
    e for e in observation_events_30d
    if not _event_is_closed(e)
    and e.get("pnl") is not None
]

obs_open_pnl = [
    safe_float(e.get("pnl"))
    for e in obs_open
    if safe_float(e.get("pnl")) is not None
]

obs_open_wins = sum(p > 0 for p in obs_open_pnl)
obs_open_losses = sum(p < 0 for p in obs_open_pnl)
obs_open_neutral = sum(p == 0 for p in obs_open_pnl)
obs_win_rate = (
    obs_open_wins / len(obs_open_pnl) * 100
    if obs_open_pnl else 0.0
)


# ============================================================
# 实际持仓
# ============================================================
# 实际持仓直接以 active_list 为准。
# 这是系统真正已经建仓并且目前仍持有的 Core 子集。
# 不再从全部 Core 推荐事件反推，避免把“未买入 Core”误算成持仓。

actual_active_pnl = []
for item in active_list:
    pnl = safe_float(item.get("当前盈亏(%)"))
    if pnl is None:
        rec = safe_float(item.get("首次推荐价"))
        cur = safe_float(item.get("现价"))
        if rec is not None and rec > 0 and cur is not None:
            pnl = (cur - rec) / rec * 100
    if pnl is not None:
        actual_active_pnl.append(round(pnl, 2))

actual_active_wins = sum(p > 0 for p in actual_active_pnl)
actual_active_losses = sum(p < 0 for p in actual_active_pnl)
actual_active_neutral = sum(p == 0 for p in actual_active_pnl)
actual_active_win_rate = (
    actual_active_wins / len(actual_active_pnl) * 100
    if actual_active_pnl else 0.0
)


# ============================================================
# 基础统计
# ============================================================

total_scan_recommendations = len(scan_events_30d)
core_event_count = len(core_events_30d)
observation_event_count = len(observation_events_30d)

core_closed_count = len(core_closed_pnl)
core_open_count = len(core_open_pnl)
observation_closed_count = len(obs_closed_pnl)
observation_open_count = len(obs_open_pnl)
actual_active_count = len(actual_active_pnl)

valid_performance_samples = len(stock_events_valid)
data_insufficient_count = len(stock_events_missing)

no_rec_price_count = sum(
    1 for e in stock_events_missing
    if e.get("data_status") == "NO_REC_PRICE"
)

price_missing_count = sum(
    1 for e in stock_events_missing
    if e.get("data_status") == "PRICE_MISSING"
)

other_missing_count = max(
    0,
    data_insufficient_count - no_rec_price_count - price_missing_count
)


# ============================================================
# 期权独立 KPI
# ============================================================

option_closed_pnl = [
    safe_float(x.get("pnl"))
    for x in option_closed_history
    if safe_float(x.get("pnl")) is not None
]

option_wins = sum(p > 0 for p in option_closed_pnl)
option_losses = sum(p < 0 for p in option_closed_pnl)
option_neutral = sum(p == 0 for p in option_closed_pnl)
option_win_rate = (
    option_wins / len(option_closed_pnl) * 100
    if option_closed_pnl else 0.0
)


# ============================================================
# Milestone Performance（5D/10D/20D 胜率，只读统计，不修改 milestone 数据）
# ============================================================

def _load_milestone_win_rate_events():
    """从 review_history.csv 读取唯一 milestone 事件（Rec_Date + Ticker + Tag）。

    同一事件在多次 Review 中重复出现，只取最后一次快照（与现有 KPI 口径一致）。
    期权记录排除。返回 list[dict]，每项含 pnl_5d/pnl_10d/pnl_20d（float 或 None）。
    """
    events = []
    if os.path.exists(REVIEW_HISTORY) and os.path.getsize(REVIEW_HISTORY) > 0:
        try:
            rh = pd.read_csv(REVIEW_HISTORY, dtype=str, keep_default_na=False)
            if not rh.empty and {"Rec_Date", "Ticker", "Tag"}.issubset(rh.columns):
                if "Option_Type" not in rh.columns:
                    rh["Option_Type"] = ""
                rh = rh[rh["Option_Type"].astype(str).str.strip().eq("")].copy()
                rh["_tk"] = rh["Ticker"].astype(str).str.upper()
                rh["_rd"] = rh["Rec_Date"].astype(str).str[:10]
                rh["_tag"] = rh["Tag"].astype(str).str.strip()
                if "Review_Date" not in rh.columns:
                    rh["Review_Date"] = rh["_rd"]
                rh = rh.sort_values(["_rd", "Review_Date"])
                for _, g in rh.groupby(["_rd", "_tk", "_tag"], sort=False, dropna=False):
                    row = g.iloc[-1]
                    events.append({
                        "pnl_5d": safe_float(row.get("PnL_5D")),
                        "pnl_10d": safe_float(row.get("PnL_10D")),
                        "pnl_20d": safe_float(row.get("PnL_20D")),
                    })
        except Exception as e:
            print(f"⚠️ 读取 milestone 统计失败：{e}")
    return events


milestone_events = _load_milestone_win_rate_events()
milestone_win_rate = compute_milestone_win_rate(milestone_events)

# 没有有效样本时显示 N/A，而不是误报为 0%。
core_closed_win_rate_text = f"{core_closed_win_rate:.2f}%" if core_closed_count else "N/A"
core_open_win_rate_text = f"{core_open_win_rate:.2f}%" if core_open_count else "N/A"
obs_closed_win_rate_text = f"{obs_closed_win_rate:.2f}%" if observation_closed_count else "N/A"
obs_win_rate_text = f"{obs_win_rate:.2f}%" if observation_open_count else "N/A"
actual_active_win_rate_text = f"{actual_active_win_rate:.2f}%" if actual_active_count else "N/A"
option_win_rate_text = f"{option_win_rate:.2f}%" if option_closed_pnl else "N/A"


# ============================================================
# 日志
# ============================================================

print(
    f"📊 Scan推荐事件：{total_scan_recommendations}；"
    f"Core {core_event_count} / Observation {observation_event_count}；"
    f"有效绩效：{valid_performance_samples}；"
    f"数据不足：{data_insufficient_count}"
)

print(
    f"📊 Core 已完成：{core_closed_win_rate_text} "
    f"({core_closed_wins}赢/{core_closed_losses}亏/{core_closed_neutral}平)"
)

print(
    f"📊 Core 当前跟踪：{core_open_win_rate_text} "
    f"({core_open_wins}赢/{core_open_losses}亏/{core_open_neutral}平)"
)

print(
    f"📊 Observation 已完成：{obs_closed_win_rate_text} "
    f"({obs_closed_wins}赢/{obs_closed_losses}亏/{obs_closed_neutral}平)"
)

print(
    f"📊 Observation 当前跟踪：{obs_win_rate_text} "
    f"({obs_open_wins}赢/{obs_open_losses}亏/{obs_open_neutral}平)"
)

print(
    f"📊 实际持仓当前跟踪：{actual_active_win_rate_text} "
    f"({actual_active_wins}赢/{actual_active_losses}亏/{actual_active_neutral}平)"
)

print(
    f"📊 期权已完成：{option_win_rate_text} "
    f"({option_wins}赢/{option_losses}亏/{option_neutral}平)"
)

# Milestone Performance 文本（只读统计）
print("📊 Milestone Performance")
for _label in ("5D", "10D", "20D"):
    _s = milestone_win_rate[_label]
    _rate = f"{_s['win_rate']:.2f}%" if _s["win_rate"] is not None else "N/A"
    print(
        f"  {_label}: Eligible={_s['eligible']} Wins={_s['wins']} "
        f"Losses={_s['losses']} Win Rate={_rate}"
    )
print("  （N/A / 未达标 milestone 不进入分母）")


# ============================================================
# 14. HTML 格式
# ============================================================

def _pnl_style(v):
    x = safe_float(v)
    if x is None:
        return "color:#607d8b;"
    if x > 0:
        return "color:#d32f2f;font-weight:700;"
    if x < 0:
        return "color:#2e7d32;font-weight:700;"
    return "color:#455a64;font-weight:700;"


def _price(v):
    x = safe_float(v)
    return "N/A" if x is None else f"${x:.2f}"


def _pct(v):
    x = safe_float(v)
    return "N/A" if x is None else f"{x:+.2f}%"


# Milestone Performance 胜率文案（HTML 用；None -> N/A）
def _mwr_text(label):
    s = milestone_win_rate[label]
    return f"{s['win_rate']:.2f}%" if s["win_rate"] is not None else "N/A"

_mwr_5d = _mwr_text("5D")
_mwr_10d = _mwr_text("10D")
_mwr_20d = _mwr_text("20D")


kpi_html = f"""
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:15px;margin-bottom:20px;">

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #1565c0;">
<div style="font-size:13px;color:#7f8c8d;">最近30天 Scan 推荐</div>
<div style="font-size:25px;font-weight:bold;">{total_scan_recommendations}</div>
<div style="font-size:14px;font-weight:700;">Core {core_event_count}　·　Observation {observation_event_count}</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">
有价格 {valid_performance_samples} · 数据不足 {data_insufficient_count}
· 无推荐价 {no_rec_price_count} · 无当前价 {price_missing_count}
</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #1565c0;">
<div style="font-size:14px;color:#1565c0;font-weight:700;">👑 Core</div>
<div style="font-size:13px;margin-top:7px;">已完成胜率 <b>{core_closed_win_rate:.2f}%</b>　{core_closed_wins} 赢 / {core_closed_losses} 亏 / {core_closed_neutral} 平</div>
<div style="font-size:13px;margin-top:5px;">当前跟踪 <b>{core_open_win_rate:.2f}%</b>　{core_open_wins} 赢 / {core_open_losses} 亏 / {core_open_neutral} 平</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">已完成 {core_closed_count} 笔 · 当前 {core_open_count} 笔</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #ff9800;">
<div style="font-size:14px;color:#e65100;font-weight:700;">👀 Observation</div>
<div style="font-size:13px;margin-top:7px;">已完成胜率 <b>{obs_closed_win_rate:.2f}%</b>　{obs_closed_wins} 赢 / {obs_closed_losses} 亏 / {obs_closed_neutral} 平</div>
<div style="font-size:13px;margin-top:5px;">当前跟踪 <b>{obs_win_rate:.2f}%</b>　{obs_open_wins} 赢 / {obs_open_losses} 亏 / {obs_open_neutral} 平</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">已完成 {observation_closed_count} 笔 · 当前 {observation_open_count} 笔 · 不计实际持仓</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #e67e22;">
<div style="font-size:14px;color:#e67e22;font-weight:700;">🟢 实际持仓</div>
<div style="font-size:25px;font-weight:bold;color:#e67e22;">{actual_active_win_rate:.2f}%</div>
<div style="font-size:13px;">{actual_active_wins} 赢 / {actual_active_losses} 亏 / {actual_active_neutral} 平</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">当前真实持仓 {actual_active_count} 笔；它是 Core 中真正建仓的子集</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #9b59b6;">
<div style="font-size:14px;color:#8e44ad;font-weight:700;">🎲 期权</div>
<div style="font-size:25px;font-weight:bold;color:#8e44ad;">{option_win_rate:.2f}%</div>
<div style="font-size:13px;">{option_wins} 赢 / {option_losses} 亏 / {option_neutral} 平</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">只统计已经结束的期权，与股票 Scan 完全分开</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #16a085;grid-column:1/-1;">
<div style="font-size:14px;color:#0e6655;font-weight:700;">📈 Milestone Performance</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:10px;">
<div><div style="font-size:13px;color:#7f8c8d;">5D 胜率</div><div style="font-size:22px;font-weight:bold;color:#0e6655;">{_mwr_5d}</div><div style="font-size:11px;color:#607d8b;">{milestone_win_rate['5D']['wins']} 赢 / {milestone_win_rate['5D']['losses']} 亏 · 样本 {milestone_win_rate['5D']['eligible']}</div></div>
<div><div style="font-size:13px;color:#7f8c8d;">10D 胜率</div><div style="font-size:22px;font-weight:bold;color:#0e6655;">{_mwr_10d}</div><div style="font-size:11px;color:#607d8b;">{milestone_win_rate['10D']['wins']} 赢 / {milestone_win_rate['10D']['losses']} 亏 · 样本 {milestone_win_rate['10D']['eligible']}</div></div>
<div><div style="font-size:13px;color:#7f8c8d;">20D 胜率</div><div style="font-size:22px;font-weight:bold;color:#0e6655;">{_mwr_20d}</div><div style="font-size:11px;color:#607d8b;">{milestone_win_rate['20D']['wins']} 赢 / {milestone_win_rate['20D']['losses']} 亏 · 样本 {milestone_win_rate['20D']['eligible']}</div></div>
</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">N/A / 未达标 milestone 不进入分母；Win=PnL&gt;0，Loss=PnL≤0</div>
</div>

<div style="background:#f7f9fb;border:1px solid #dfe6ee;border-radius:10px;padding:15px;grid-column:1/-1;">
<div style="font-size:13px;font-weight:700;color:#455a64;">📌 统计口径</div>
<div style="font-size:12px;line-height:1.8;color:#546e7a;margin-top:5px;">
<strong>Core</strong> = Scan 认定的核心推荐。<br>
<strong>Observation</strong> = 观察推荐，不进入实际持仓统计。<br>
<strong>Core 已完成</strong> = 已结束的 Core 推荐事件。<br>
<strong>Core 当前跟踪</strong> = 尚未结束且有最新价格的 Core 推荐事件。<br>
<strong>Observation 已完成</strong> = 已结束的 Observation 推荐事件。<br>
<strong>Observation 当前跟踪</strong> = 尚未结束且有最新价格的 Observation 推荐事件。<br>
<strong>实际持仓</strong> = 当前真正建仓并仍持有的 Core 子集，因此它与 Core 当前跟踪完全可以不同。<br>
当前浮盈/浮亏只进入当前跟踪；只有真实结束并有退出价格的事件才进入已完成胜率。
</div>
</div>

</div>
"""


# ============================================================
# 15. Observation HTML
# ============================================================
# 15. Observation HTML
# ============================================================

def build_observation_html():
    if not observation_list:
        return ""
    blocks = []
    for x in observation_list:
        pnl = safe_float(x.get("推荐跟踪涨跌幅(%)"))
        pnl_text = (
            f'<span style="{_pnl_style(pnl)}">{_pct(pnl)}</span>'
            if pnl is not None else "N/A"
        )
        blocks.append(f"""
<div style="background:#fffdf7;border:1px solid #ffe0b2;border-left:6px solid #ff9800;padding:16px;margin-bottom:12px;border-radius:8px;">
<div style="font-size:16px;font-weight:bold;color:#e65100;">👀 {clean_text(x.get("名称"),x.get("代码"))} ({x.get("代码")})</div>
<div><b>首次推荐：</b>{x.get("首次推荐日")} @ {_price(x.get("首次推荐价"))}　
<b>连续推荐：</b>{x.get("系统连续推荐次数","1")}　
<b>今日新增：</b>{x.get("今日新增","否")}</div>
<div><b>当前价格：</b>{_price(x.get("当前价格"))}　
<b>推荐跟踪涨跌幅：</b>{pnl_text}</div>
<div><b>RSI：</b>{x.get("RSI")}　<b>Bias：</b>{x.get("Bias")}　
<b>技术评分：</b>{x.get("技术评分")}　<b>估值评分：</b>{x.get("估值评分")}</div>
<div><b>PE：</b>{x.get("PE_TTM")}　
<b>Forward PE：</b>{x.get("PE_Forward")}　
<b>EPS：</b>{x.get("EPS_TTM")}　
<b>PB：</b>{x.get("PB")}</div>
<div><b>MACD金叉：</b>{x.get("MACD金叉")}　
<b>周线共振：</b>{x.get("周线共振")}　
<b>KDJ_J回升：</b>{x.get("KDJ_J回升")}　
<b>量能放大：</b>{x.get("量能放大")}　
<b>周期共振：</b>{x.get("周期共振")}</div>
<div style="color:#607d8b;">Observation 不计入实际持仓。当前跟踪有明确结束条件；结束后的事件仍保留在历史绩效统计中。</div>
</div>
""")
    return '<h2 style="color:#e65100;border-bottom:2px solid #e65100;padding-bottom:5px;">👀 当前 Observation 跟踪</h2><div style="background:#fff7e6;border:1px solid #ffd59a;padding:12px;margin-bottom:15px;border-radius:8px;color:#7a4b00;">当前只保留仍在跟踪的 Observation。自动取消跟踪条件：达到 +10% 目标、跌幅达到 -6% 失效、满 10 个交易日、被新的 Observation 替代、或升级为 Core。已结束事件仍保留在 KPI 历史统计中，不再持续占用当前跟踪资源。</div>' + "".join(blocks)


# ============================================================
# 16. 实际持仓 HTML
# ============================================================

def build_active_html():
    blocks = []
    for x in active_list:
        pnl = safe_float(x.get("当前盈亏(%)"))
        blocks.append(f"""
<div style="background:#fafafa;border:1px solid #e0e0e0;padding:16px;margin-bottom:12px;border-radius:8px;">
<div style="font-size:16px;font-weight:bold;">🟢 {x.get("名称")} ({x.get("代码")})</div>
<div><b>首次推荐：</b>{x.get("首次推荐日")} @ {_price(x.get("首次推荐价"))}　
<b>推荐评分：</b>{x.get("推荐评分")}　
<b>连续推荐：</b>{x.get("系统连续推荐次数")}</div>
<div><b>当前盈亏：</b><span style="{_pnl_style(pnl)}">{_pct(pnl)}</span>　
<b>当前价格：</b>{_price(x.get("现价"))}　
<b>复盘交易日开盘→收盘：</b>{_pct(x.get("今日开盘→收盘%"))}</div>
<div><b>移动止损：</b>{_price(x.get("止损价"))}　
<b>MA20：</b>{_price(x.get("MA20"))}　
<b>MA50：</b>{_price(x.get("MA50"))}　
<b>KDJ_J：</b>{x.get("KDJ_J","N/A")}　
<b>MACD_Hist：</b>{x.get("MACD_Hist","N/A")}</div>
<div><b>趋势状态：</b>{x.get("趋势状态","N/A")}　
<b>风险：</b>{x.get("风险提示","暂无")}</div>
<div><b>盈亏归因：</b>{x.get("盈利/亏损原因","暂无")}</div>
<div><b>风控动作：</b>{x.get("风控动作指令","继续动态监控")}</div>
</div>
""")
    return '<h2 style="color:#1565c0;border-bottom:2px solid #1565c0;padding-bottom:5px;">📊 实际持仓 - 逐只风控与盈亏归因</h2>' + "".join(blocks)


def build_stopped_html():
    blocks = []
    for x in stopped_list:
        pnl = safe_float(x.get("止损盈亏(%)"))
        blocks.append(f"""
<div style="background:#fff8f8;border:1px solid #ef9a9a;border-left:6px solid #b71c1c;padding:16px;margin-bottom:12px;border-radius:8px;">
<div style="font-size:16px;font-weight:bold;color:#b71c1c;">🔴 {x.get("名称")} ({x.get("代码")})</div>
<div><b>首次推荐：</b>{x.get("首次推荐日")} @ {_price(x.get("首次推荐价"))}</div>
<div><b>止损触发：</b>{x.get("止损触发日")}　
<b>止损结算价：</b>{_price(x.get("止损结算价"))}　
<b>策略盈亏：</b><span style="{_pnl_style(pnl)}">{_pct(pnl)}</span></div>
<div><b>执行纪律：</b>移动止损触发；次日 Scan 禁止重新推荐。</div>
</div>
""")
    return '<h2 style="color:#b71c1c;border-bottom:2px solid #b71c1c;padding-bottom:5px;">🔴 移动止损清仓</h2>' + "".join(blocks)


# ============================================================
# 17. Claude
# ============================================================

def load_active_options_snapshot(price_map):
    d = load_option_positions()
    if d.empty:
        return []
    out = []
    for _, r in d.iterrows():
        t = resolve_ticker(r.get("Ticker"))
        cur = price_map.get(t)
        if cur is None:
            _, cur = get_live_quote_bootstrap(t)
        out.append({
            "ticker": t,
            "option_type": clean_text(r.get("OptionType")).upper(),
            "strike": safe_float(r.get("Strike"), safe_float(r.get("LongStrike"))),
            "short_strike": safe_float(r.get("ShortStrike")),
            "strategy": clean_text(r.get("Strategy"), "LONG_CALL"),
            "expiry": clean_text(r.get("Expiry")),
            "entry_price": safe_float(r.get("EntryPrice"), safe_float(r.get("NetDebit"), safe_float(r.get("LongPrice")))),
            "premium_collected": safe_float(r.get("PremiumCollected")),
            "cash_secured": safe_float(r.get("CashSecured")),
            "assignment_price": safe_float(r.get("AssignmentPrice")),
            "effective_entry": safe_float(r.get("EffectiveEntry"), safe_float(r.get("BreakEven"))),
            "premium_yield_pct": safe_float(r.get("PremiumYieldPct")),
            "annualized_yield_pct": safe_float(r.get("AnnualizedYieldPct")),
            "current_underlying": cur,
            "quantity": safe_float(r.get("Quantity"),1),
            "assignment_risk": clean_text(r.get("AssignmentRisk")),
            "reason": clean_text(r.get("Reason")),
        })
    return out

def load_recent_option_recommendations(limit=20, days=7):
    try:
        if not os.path.exists(OPTION_LOG_FILE) or os.path.getsize(OPTION_LOG_FILE) == 0:
            return []
        d = pd.read_csv(OPTION_LOG_FILE, dtype=str, keep_default_na=False)
        if "EntryDate" not in d.columns:
            return []
        if "Status" in d.columns:
            d = d[d["Status"].astype(str).str.strip().eq("Active")].copy()
        d["_dt"] = pd.to_datetime(d["EntryDate"], errors="coerce", format="mixed")
        cutoff = pd.Timestamp(today_us_str()) - pd.Timedelta(days=days)
        d = d[d["_dt"].notna() & (d["_dt"] >= cutoff)].copy()
        return d.sort_values("_dt", ascending=False).drop(columns=["_dt"]).head(limit).to_dict("records")
    except Exception as e:
        print(f"⚠️ 读取近期义项权利推荐失败：{e}")
        return []

active_option_snapshot = active_option_reviews
recent_option_recommendations = load_recent_option_recommendations()

ai_html = ""
try:
    client = anthropic.Anthropic(
        api_key=os.environ.get("CLAWSOCKET_API_KEY"),
        base_url=os.environ.get("CLAWSOCKET_BASE_URL"),
    )
    prompt = f"""
你是顶级量化风控总监。
今日美股盘后数据如下：

【实际持仓】
{active_list}

【Observation】
{observation_list}

【移动止损清仓】
{stopped_list}

【活跃期权】
{active_option_snapshot}

【最近期权推荐】
{recent_option_recommendations}

【期权平仓】
{option_closed_records}

【最近30天历史已平仓期权】
{option_closed_history}

只输出两个部分：
1. 全局盘后风控总结。只讲市场环境和共性风险，不逐只重复股票。
2. 期权持仓风控 - 平仓复盘。只评价期权。

严禁编造数据。
直接输出 HTML，不要 Markdown，不要代码框。
"""
    with client.messages.stream(
        model=TARGET_MODEL,
        max_tokens=30000,
        messages=[{"role":"user","content":prompt}],
    ) as stream:
        for text in stream.text_stream:
            ai_html += text
except Exception as e:
    print(f"⚠️ Claude 报告生成失败：{e}")
    ai_html = """
<div style="background:#fff3cd;border-left:6px solid #f0ad4e;padding:20px;border-radius:8px;">
<h3>AI 风控报告暂时不可用</h3>
<p>行情、持仓、Observation、推荐绩效和止损数据已经完成处理。</p>
</div>
"""

ai_html = ai_html.replace("```html","").replace("```HTML","").replace("```","").strip()
i = ai_html.find("<")
if i > 0:
    ai_html = ai_html[i:]


# ============================================================
# 18. 完整 HTML
# ============================================================

full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
    background:#f4f6f8;
    padding:20px;
}}
.card {{
    background:white;
    padding:25px;
    border-radius:12px;
    max-width:1200px;
    margin:0 auto;
}}
</style>
</head>
<body>
<div class="card">
<h2 style="color:#2c3e50;margin-bottom:20px;border-bottom:3px solid #1565c0;padding-bottom:10px;">
美股盘后复盘与风控审查报告（Core / Observation 分层统计 / 含期权）
</h2>

{kpi_html}

{build_observation_html()}

{build_active_html()}

{build_stopped_html()}

{build_option_review_html(active_option_reviews, option_closed_records, option_closed_history)}

{ai_html}

</div>
</body>
</html>
"""

for path in ("report.html","review_report.html"):
    try:
        Path(path).write_text(full_html, encoding="utf-8")
    except Exception as e:
        print(f"⚠️ 保存 {path} 失败：{e}")


# ============================================================
# 19. 邮件
# ============================================================

def send_mail():
    account = os.environ.get("EMAIL_ACCOUNT")
    password = os.environ.get("EMAIL_PASSWORD")
    target = os.environ.get("TARGET_EMAILS") or os.environ.get("OWNER_EMAIL")
    if not account or not password or not target:
        print("⚠️ 邮件配置缺失，本次不发送邮件。")
        return
    msg = MIMEMultipart()
    msg["From"] = account
    msg["To"] = target
    msg["Subject"] = f"盘后清算 美股风控纪律与复盘 ({today_us_str()})"
    msg.attach(MIMEText(full_html, "html", "utf-8"))
    to_list = [x.strip() for x in target.split(",") if x.strip()]
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com",465,timeout=30) as server:
            server.login(account,password)
            server.sendmail(account,to_list,msg.as_string())
        print(f"✅ 邮件发送成功：{target}")
    except Exception as e:
        print(f"❌ 邮件发送失败：{e}")


send_mail()

print("=" * 60)
print("✅ 美股盘后复盘完成。")
print(
    f"Scan推荐 {total_scan_recommendations} 笔，"
    f"有效 {valid_performance_samples}，"
    f"数据不足 {data_insufficient_count}，"
    f"Core完成 {core_closed_win_rate_text} / Core当前 {core_open_win_rate_text} / "
    f"Observation完成 {obs_closed_win_rate_text} / Observation当前 {obs_win_rate_text} / "
    f"期权完成 {option_win_rate_text}"
)
print("=" * 60)
