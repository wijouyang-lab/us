# -*- coding: utf-8 -*-
"""
美股盘后复盘与风控审查引擎
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
import glob
import os
import re
import smtplib
import sys
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

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
TARGET_MODEL = "claude-opus-4-8"

def get_us_time():
    return datetime.datetime.now(US_TZ)

def today_us_str():
    return get_us_time().strftime("%Y-%m-%d")

if get_us_time().weekday() >= 5:
    print("当前为周末，美股休市，退出复盘。")
    sys.exit(0)

print("=" * 60)
print("启动美股盘后复盘与风控审查引擎")
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

def get_exact_date_ohlc(df_hist, ticker, target_date):
    try:
        if df_hist is None or df_hist.empty:
            return None
        target = pd.Timestamp(target_date).normalize()
        sub = df_hist[df_hist["Ticker"].astype(str).str.upper() == str(ticker).upper()].copy()
        if sub.empty:
            return None
        dates = pd.to_datetime(sub["Date"], errors="coerce", format="mixed")
        exact = sub.loc[dates.dt.normalize() == target].copy()
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
    "Close_Price","技术评分","估值评分","PE_TTM","PE_Forward","EPS_TTM","PB",
    "MA20","MA50","ATR_Pct","MACD金叉","周线共振","KDJ_J回升","量能放大","周期共振",
    "Review_Risk_Status","Review_Risk_Date","Review_Stop_Distance_Pct","Review_Risk_Note"
]

REVIEW_COLUMNS = [
    "Review_Date","Ticker","Name","Tag","Rec_Date","Rec_Price","Cur_Price",
    "Days_Held","PnL_Pct","Maturity_PnL","Hold_Period","Stop_Loss","Stop_Method",
    "Trail_Stop","Rec_Count","Status","Score","Review_Risk_Status",
    "Review_Risk_Date","Review_Stop_Distance_Pct","Review_Risk_Note",
    "Option_Type","Strike","Expiry"
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
    for c in ("Price", "Close_Price"):
        p = safe_float(row.get(c))
        if p is not None and p > 0:
            return p
    return None

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
                if target_date == today_us_str() and (op is None or cp is None):
                    live_op, live_last = get_live_quote_bootstrap(ticker)
                    op = op if op is not None else live_op
                    cp = cp if cp is not None else (live_last if live_last is not None else live_op)
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
                    "估值评分": clean_text(row.get("估值评分")),
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

df = load_trade_history()
if df.empty:
    print("无交易账本或账本为空，退出。")
    sys.exit(0)

cutoff_date = get_us_time().replace(tzinfo=None) - datetime.timedelta(days=30)
recent_picks = df[df["Date"].notna() & (df["Date"] >= cutoff_date)].copy()
if recent_picks.empty:
    print("最近30天无记录，退出。")
    sys.exit(0)

for c in ("Hold_Period","Stop_Loss","Score","Name","Tag","Price","Close_Price","Status"):
    if c not in recent_picks.columns:
        recent_picks[c] = ""
recent_picks["Hold_Period"] = "动态持有"


# ============================================================
# 6. 行情准备
# ============================================================

clean_tickers = []
for t in recent_picks["Ticker"].astype(str):
    rt = resolve_ticker(t)
    if rt and is_probable_us_ticker(rt):
        clean_tickers.append(rt)
clean_tickers = list(dict.fromkeys(clean_tickers))

print(f"📡 获取 {len(clean_tickers)} 只真实美股 ticker 的 60日 OHLC...")
df_hist_all, ohlc_map_today = download_ohlc_safe(clean_tickers, period="60d")

price_map_today = {}
for ticker in clean_tickers:
    exact = get_exact_date_ohlc(df_hist_all, ticker, today_us_str())
    if exact and exact.get("close") is not None:
        ohlc_map_today[ticker] = exact
        price_map_today[ticker] = exact["close"]

for ticker in clean_tickers:
    if ticker in price_map_today:
        continue
    op, last = get_live_quote_bootstrap(ticker)
    if last is not None:
        price_map_today[ticker] = last
        ohlc_map_today[ticker] = {
            "open": op if op is not None else last,
            "high": last,
            "low": last,
            "close": last,
        }
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
        mask = (
            d["Ticker"].astype(str).str.upper().eq(ticker) &
            dt.eq(target_s) &
            d["Status"].astype(str).str.strip().eq("Active")
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

option_closed_records = process_options(price_map_today)


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

def get_trailing_stop_context(ticker, current_stop=None, before_date=None):
    try:
        hist = yf.download(ticker, period="6mo", progress=False, auto_adjust=True, threads=False)
        if hist is None or hist.empty:
            return None
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)
        hist = hist.dropna(subset=["Open","High","Low","Close"]).copy()
        idx = pd.to_datetime(hist.index, errors="coerce")
        try:
            idx = idx.tz_localize(None)
        except Exception:
            pass
        hist.index = idx
        if len(hist) < 60:
            return None
        ref = pd.Timestamp(before_date).normalize() if before_date is not None else hist.index[-1]
        d = hist[hist.index < ref].copy()
        if d.empty:
            return None
        d["MA20"] = d["Close"].rolling(20, min_periods=20).mean()
        d["MA50"] = d["Close"].rolling(50, min_periods=50).mean()
        d["ATR14"] = _calc_atr(d)
        md = _calc_macd(d["Close"])
        d["MACD"] = md["MACD"]; d["MACD_SIGNAL"] = md["MACD_SIGNAL"]; d["MACD_HIST"] = md["MACD_HIST"]
        kd = _calc_kdj(d)
        d["KDJ_J"] = kd["J"]
        r = d.iloc[-1]
        close = float(r["Close"])
        atr = float(r["ATR14"]) if pd.notna(r["ATR14"]) else close*0.05
        ma20 = float(r["MA20"]) if pd.notna(r["MA20"]) else close
        ma50 = float(r["MA50"]) if pd.notna(r["MA50"]) else ma20
        pct = max(0.03, min(0.12, 2*atr/max(close,1e-9)))
        candidate = max(close*(1-pct), ma20-atr, ma50-1.5*atr)
        macd_bear = bool(pd.notna(r["MACD"]) and pd.notna(r["MACD_SIGNAL"]) and r["MACD"] < r["MACD_SIGNAL"])
        kdj_falling = bool(len(d) >= 2 and d["KDJ_J"].iloc[-1] < d["KDJ_J"].iloc[-2])
        if macd_bear and kdj_falling:
            candidate = max(candidate, close - 1.5*atr)
        candidate = min(candidate, close*0.98)
        old = safe_float(current_stop)
        if old and old > 0:
            candidate = max(old, candidate)
        return {
            "exec_stop": round(candidate,2),
            "ma20": round(ma20,2), "ma50": round(ma50,2),
            "atr_pct": round(atr/close*100,2) if close else None,
            "macd_hist": round(float(r["MACD_HIST"]),4) if pd.notna(r["MACD_HIST"]) else None,
            "macd_bear": macd_bear, "kdj_j": round(float(r["KDJ_J"]),2),
            "kdj_falling": kdj_falling,
            "trend_ok": bool(close >= ma20 and ma20 >= ma50),
        }
    except Exception as e:
        print(f"⚠️ 移动止损计算失败 {ticker}: {e}")
        return None

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
            d.loc[mask,"Exit_Date"] = today_us_str()
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
            if c not in d.columns: d[c] = ""
        dates = pd.to_datetime(d["Date"], errors="coerce", format="mixed")
        mask = (
            d["Ticker"].astype(str).str.upper().eq(str(ticker).upper()) &
            dates.dt.strftime("%Y-%m-%d").eq(str(rec_date_str)[:10]) &
            d["Status"].astype(str).str.strip().eq("Active")
        )
        if not mask.any(): return
        d.loc[mask,"Review_Risk_Status"] = risk_status
        d.loc[mask,"Review_Risk_Date"] = today_us_str()
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
# 9. 股票分类
# ============================================================

active_list, observation_list, expired_list, stopped_list = [], [], [], []

for orig_ticker, group in recent_picks.groupby("Ticker", sort=False):
    group = group.sort_values("Date").copy()
    if group.empty:
        continue
    ticker = resolve_ticker(orig_ticker, clean_text(group.iloc[0].get("Name")))
    if not ticker:
        continue

    first = group.iloc[0]
    latest = group.iloc[-1]
    rec_date = normalize_date(first.get("Date"))
    if rec_date is None:
        continue

    status = clean_text(latest.get("Status"))
    if status not in ("", "Active", "pending"):
        continue

    rec_date_str = rec_date.strftime("%Y-%m-%d")
    rec_price = safe_record_price(first)

    # ---- Observation：保留为有效 Scan 推荐，但不是实际持仓 ----
    if clean_text(latest.get("Tag")).strip() == "Observation":
        cur = safe_float(price_map_today.get(ticker))
        pnl = None
        if rec_price and rec_price > 0 and cur is not None:
            pnl = round((cur-rec_price)/rec_price*100, 2)
        observation_list.append({
            "代码": ticker,
            "名称": clean_text(first.get("Name"), ticker),
            "标签": "Observation",
            "推荐评分": clean_text(latest.get("Score"), "N/A"),
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "当前价格": cur,
            "推荐跟踪涨跌幅(%)": pnl,
            "RSI": clean_text(first.get("RSI"), "N/A"),
            "Bias": clean_text(first.get("Bias"), "N/A"),
            "技术评分": clean_text(first.get("技术评分"), "N/A"),
            "估值评分": clean_text(first.get("估值评分"), "N/A"),
            "PE_TTM": clean_text(first.get("PE_TTM"), "N/A"),
            "PE_Forward": clean_text(first.get("PE_Forward"), "N/A"),
            "EPS_TTM": clean_text(first.get("EPS_TTM"), "N/A"),
            "PB": clean_text(first.get("PB"), "N/A"),
            "MACD金叉": clean_text(first.get("MACD金叉"), "N/A"),
            "周线共振": clean_text(first.get("周线共振"), "N/A"),
            "KDJ_J回升": clean_text(first.get("KDJ_J回升"), "N/A"),
            "量能放大": clean_text(first.get("量能放大"), "N/A"),
            "周期共振": clean_text(first.get("周期共振"), "N/A"),
            "系统连续推荐次数": len(group),
            "今日新增": "是" if rec_date_str == today_us_str() else "否",
            "行情状态": "已取得" if cur is not None else "今日行情缺失",
        })
        continue

    if rec_price is None or rec_price <= 0:
        continue

    ohlc = ohlc_map_today.get(ticker)
    if ohlc is None:
        cur = price_map_today.get(ticker)
        if cur is None:
            active_list.append({
                "代码": ticker, "名称": clean_text(first.get("Name"), ticker),
                "标签": clean_text(latest.get("Tag")), "推荐评分": clean_text(latest.get("Score"),"N/A"),
                "持股周期建议": "动态持有", "止损价": safe_float(first.get("Stop_Loss")) or "N/A",
                "首次推荐日": rec_date_str, "首次推荐价": rec_price,
                "今日开盘价":"N/A", "现价":"N/A", "今日开盘→收盘%":None,
                "持仓天数":(pd.Timestamp(today_us_str())-rec_date).days, "剩余天数":"—",
                "当前盈亏(%)":None, "系统连续推荐次数":len(group),
                "今日新增":"是" if rec_date_str==today_us_str() else "否",
                "止损方法":"MA20/MA50 + ATR + MACD/KDJ",
                "MA20":None,"MA50":None,"KDJ_J":None,"MACD_Hist":None,
                "趋势状态":"今日行情缺失","风险提示":"今日行情未取得；暂不执行止损判断",
                "Review_Risk_Status":"DATA_MISSING","Review_Risk_Date":today_us_str(),
                "Review_Stop_Distance_Pct":"","Review_Risk_Note":"今日行情缺失，待下一次Review补算"
            })
            write_review_risk_linkage_us(ticker, rec_date_str, "DATA_MISSING", None, None, "今日行情缺失，暂不执行止损判断。")
            continue
        ohlc = {"open":cur,"high":cur,"low":cur,"close":cur}

    low, closep, openp = safe_float(ohlc.get("low")), safe_float(ohlc.get("close")), safe_float(ohlc.get("open"))
    if low is None or closep is None:
        active_list.append({
            "代码":ticker, "名称":clean_text(first.get("Name"),ticker), "标签":clean_text(latest.get("Tag")),
            "推荐评分":clean_text(latest.get("Score"),"N/A"), "持股周期建议":"动态持有",
            "止损价":safe_float(first.get("Stop_Loss")) or "N/A", "首次推荐日":rec_date_str, "首次推荐价":rec_price,
            "今日开盘价":"N/A","现价":"N/A","今日开盘→收盘%":None,
            "持仓天数":(pd.Timestamp(today_us_str())-rec_date).days,"剩余天数":"—","当前盈亏(%)":None,
            "系统连续推荐次数":len(group),"今日新增":"是" if rec_date_str==today_us_str() else "否",
            "止损方法":"MA20/MA50 + ATR + MACD/KDJ","MA20":None,"MA50":None,"KDJ_J":None,"MACD_Hist":None,
            "趋势状态":"行情不完整","风险提示":"今日OHLC不完整，暂不执行止损判断",
            "Review_Risk_Status":"DATA_MISSING","Review_Risk_Date":today_us_str(),
            "Review_Stop_Distance_Pct":"","Review_Risk_Note":"今日OHLC不完整，待下一次Review补算"
        })
        continue

    old_stop = safe_float(first.get("Stop_Loss"))
    ctx = get_trailing_stop_context(ticker, old_stop, today_us_str())
    exec_stop = ctx.get("exec_stop") if ctx else old_stop

    if exec_stop and exec_stop > 0 and low <= exec_stop:
        write_review_risk_linkage_us(
            ticker, rec_date_str, "STOP_TRIGGERED", exec_stop, closep,
            f"今日最低价 {low:.2f} 已触及/跌破移动止损 {exec_stop:.2f}；次日 Scan 禁止重新推荐。"
        )
        exitp = openp if openp is not None and openp < exec_stop else exec_stop
        pnl = round((exitp-rec_price)/rec_price*100,2)
        stopped_list.append({
            "代码":ticker,"名称":clean_text(first.get("Name"),ticker),
            "标签":clean_text(latest.get("Tag")),"推荐评分":clean_text(latest.get("Score"),"N/A"),
            "持股周期建议":"动态持有","止损价":exec_stop,"首次推荐日":rec_date_str,"首次推荐价":rec_price,
            "止损触发日":today_us_str(),"止损结算价":exitp,"止损盈亏(%)":pnl,
            "持仓天数":(pd.Timestamp(today_us_str())-rec_date).days,"系统连续推荐次数":len(group),
            "触发方式":"移动止损：前一交易日保护线","Stop_Method":"MA20/MA50 + ATR + MACD/KDJ"
        })
        update_trade_history_status(ticker, rec_date_str, "Stop_Loss_Hit", exitp)
        continue

    next_ctx = get_trailing_stop_context(ticker, exec_stop, None)
    next_stop = next_ctx.get("exec_stop") if next_ctx else exec_stop
    if next_stop:
        update_trade_history_trailing_stop(ticker, rec_date_str, next_stop, next_ctx or ctx or {})
    c = next_ctx or ctx or {}
    risk = []
    if c.get("macd_bear"): risk.append("MACD弱势")
    if c.get("kdj_falling"): risk.append("KDJ回落")
    days = (pd.Timestamp(today_us_str()) - rec_date).days
    distance = ((closep-next_stop)/closep*100) if next_stop and closep else None
    risk_status = "STOP_NEAR" if distance is not None and distance <= 3.0 else "CLEAR"
    risk_note = f"收盘距离移动止损约 {distance:.2f}%，次日 Scan 强提醒。" if risk_status == "STOP_NEAR" else "本次 Review 未发现触及或接近移动止损。"
    write_review_risk_linkage_us(ticker, rec_date_str, risk_status, next_stop, closep, risk_note)

    active_list.append({
        "代码":ticker,"名称":clean_text(first.get("Name"),ticker),"标签":clean_text(latest.get("Tag")),
        "推荐评分":clean_text(latest.get("Score"),"N/A"),"持股周期建议":"动态持有",
        "止损价":next_stop if next_stop else "N/A","首次推荐日":rec_date_str,"首次推荐价":rec_price,
        "今日开盘价":openp if openp is not None else "N/A","现价":closep,
        "今日开盘→收盘%":round((closep-openp)/openp*100,2) if openp and closep is not None else None,
        "持仓天数":days,"剩余天数":"—","当前盈亏(%)":round((closep-rec_price)/rec_price*100,2),
        "系统连续推荐次数":len(group),"今日新增":"是" if rec_date_str==today_us_str() else "否",
        "止损方法":"MA20/MA50 + ATR + MACD/KDJ","MA20":c.get("ma20"),"MA50":c.get("ma50"),
        "KDJ_J":c.get("kdj_j"),"MACD_Hist":c.get("macd_hist"),
        "趋势状态":"多头结构" if c.get("trend_ok") else "趋势转弱",
        "风险提示":"、".join(risk) if risk else "趋势未出现同步转弱",
        "Review_Risk_Status":risk_status,"Review_Risk_Date":today_us_str(),
        "Review_Stop_Distance_Pct":round(distance,2) if distance is not None else "",
        "Review_Risk_Note":risk_note
    })


# ============================================================
# 10. 确定性归因
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
# 11. review_history：逐次 Review 记录，但不重复同一 Review 事件
# ============================================================

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
    if not rows:
        return
    nd = pd.DataFrame(rows)
    for c in REVIEW_COLUMNS:
        if c not in nd.columns: nd[c] = ""
    nd = nd[REVIEW_COLUMNS]

    if os.path.exists(REVIEW_HISTORY) and os.path.getsize(REVIEW_HISTORY) > 0:
        try:
            od = pd.read_csv(REVIEW_HISTORY, dtype=str, keep_default_na=False, on_bad_lines="skip")
            for c in REVIEW_COLUMNS:
                if c not in od.columns: od[c] = ""
            od = od[REVIEW_COLUMNS]
        except Exception:
            od = pd.DataFrame(columns=REVIEW_COLUMNS)
    else:
        od = pd.DataFrame(columns=REVIEW_COLUMNS)

    existing_keys = {review_event_key(r) for _, r in od.iterrows()}
    out = []
    for _, r in nd.iterrows():
        k = review_event_key(r)
        if k not in existing_keys:
            existing_keys.add(k)
            out.append(r.to_dict())
    if out:
        pd.concat([od, pd.DataFrame(out, columns=REVIEW_COLUMNS)], ignore_index=True).to_csv(
            REVIEW_HISTORY, index=False, encoding="utf-8"
        )

review_rows = []

for item in active_list:
    review_rows.append({
        "Review_Date":today_us_str(),"Ticker":item["代码"],"Name":item["名称"],"Tag":item["标签"],
        "Rec_Date":item["首次推荐日"],"Rec_Price":item["首次推荐价"],"Cur_Price":item["现价"],
        "Days_Held":item["持仓天数"],"PnL_Pct":item["当前盈亏(%)"],"Maturity_PnL":"",
        "Hold_Period":"动态持有","Stop_Loss":item["止损价"],
        "Stop_Method":item.get("止损方法","MA20/MA50 + ATR + MACD/KDJ"),
        "Trail_Stop":item.get("止损价",""),"Rec_Count":item["系统连续推荐次数"],"Status":"持仓中",
        "Score":item["推荐评分"],"Review_Risk_Status":item.get("Review_Risk_Status",""),
        "Review_Risk_Date":item.get("Review_Risk_Date",""),
        "Review_Stop_Distance_Pct":item.get("Review_Stop_Distance_Pct",""),
        "Review_Risk_Note":item.get("Review_Risk_Note",""),
        "Option_Type":"","Strike":"","Expiry":""
    })

for item in stopped_list:
    review_rows.append({
        "Review_Date":today_us_str(),"Ticker":item["代码"],"Name":item["名称"],"Tag":item["标签"],
        "Rec_Date":item["首次推荐日"],"Rec_Price":item["首次推荐价"],"Cur_Price":item["止损结算价"],
        "Days_Held":item["持仓天数"],"PnL_Pct":item["止损盈亏(%)"],"Maturity_PnL":item["止损盈亏(%)"],
        "Hold_Period":"动态持有","Stop_Loss":item["止损价"],
        "Stop_Method":item.get("Stop_Method","MA20/MA50 + ATR + MACD/KDJ"),
        "Trail_Stop":item.get("止损价",""),"Rec_Count":item["系统连续推荐次数"],"Status":"移动止损清仓",
        "Score":item["推荐评分"],"Review_Risk_Status":"STOP_TRIGGERED","Review_Risk_Date":today_us_str(),
        "Review_Stop_Distance_Pct":0,"Review_Risk_Note":f"移动止损触发：{item.get('止损价','')}",
        "Option_Type":"","Strike":"","Expiry":""
    })

for item in observation_list:
    review_rows.append({
        "Review_Date":today_us_str(),"Ticker":item["代码"],"Name":item["名称"],"Tag":"Observation",
        "Rec_Date":item["首次推荐日"],"Rec_Price":item.get("首次推荐价",""),"Cur_Price":item.get("当前价格",""),
        "Days_Held":"","PnL_Pct":item.get("推荐跟踪涨跌幅(%)"),"Maturity_PnL":"",
        "Hold_Period":"观察","Stop_Loss":"","Stop_Method":"观察，不触发持仓止损","Trail_Stop":"",
        "Rec_Count":item.get("系统连续推荐次数","1"),"Status":"观察推荐","Score":item.get("推荐评分","N/A"),
        "Review_Risk_Status":"OBSERVATION","Review_Risk_Date":today_us_str(),
        "Review_Stop_Distance_Pct":"","Review_Risk_Note":"有效 Scan 推荐；不作为实际持仓，但纳入推荐绩效追踪。",
        "Option_Type":"","Strike":"","Expiry":""
    })

for opt in option_closed_records:
    review_rows.append({
        "Review_Date":today_us_str(),"Ticker":opt["ticker"],"Name":opt["ticker"]+" OPT","Tag":"期权平仓",
        "Rec_Date":opt["expiry"],"Rec_Price":opt["entry_price"],"Cur_Price":opt["close_price"],
        "Days_Held":"","PnL_Pct":opt["pnl"],"Maturity_PnL":opt["pnl"],"Hold_Period":"",
        "Stop_Loss":"","Stop_Method":"","Trail_Stop":"","Rec_Count":"","Status":"期权平仓","Score":opt["reason"],
        "Review_Risk_Status":"","Review_Risk_Date":"","Review_Stop_Distance_Pct":"","Review_Risk_Note":"",
        "Option_Type":opt["option_type"],"Strike":opt["strike"],"Expiry":opt["expiry"]
    })

append_review_rows(review_rows)


# ============================================================
# 12. 每次 Scan 推荐事件的独立追踪
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
    每一次 Scan 输出的一行推荐 = 一个独立推荐事件。

    事件键：推荐日期 + Ticker。

    推荐价格来自 Scan pending 原始文件，而不是 trade_history 的
    实际开盘价。这样统计的收益真正对应：
        Scan 推荐价 -> 当前价/退出价

    Observation 与实际持仓都是有效 Scan 推荐事件；
    Observation 不属于实际持仓，但必须进入推荐绩效。
    """
    raw_events = _load_scan_recommendation_files()
    trade_lookup = _load_trade_event_lookup()
    review_closed = _load_review_closed_lookup()

    events_by_key = {}

    for raw in raw_events:
        key = (raw["rec_date"], raw["ticker"])
        events_by_key[key] = raw

    # 若 pending 文件已被清理/未保存，则用 trade_history 做兜底。
    d = load_trade_history()
    if not d.empty:
        for _, row in d.iterrows():
            dt = normalize_date(row.get("Date"))
            ticker = resolve_ticker(row.get("Ticker"), row.get("Name"))
            if dt is None or not ticker:
                continue
            if dt < (pd.Timestamp(today_us_str()) - pd.Timedelta(days=30)):
                continue
            key = (dt.strftime("%Y-%m-%d"), ticker)
            if key not in events_by_key:
                rp = safe_float(row.get("Scan_Ref_Price"))
                if rp is None:
                    rp = safe_float(row.get("Price"))
                events_by_key[key] = {
                    "ticker": ticker,
                    "name": clean_text(row.get("Name"), ticker),
                    "rec_date": dt.strftime("%Y-%m-%d"),
                    "rec_price": rp,
                    "tag": clean_text(row.get("Tag")),
                    "score": clean_text(row.get("Score"), "N/A"),
                    "source_file": "trade_history.csv",
                }

    events = []

    for key in sorted(events_by_key.keys()):
        raw = events_by_key[key]
        trow = trade_lookup.get(key, {})
        hrow = review_closed.get(key, {})

        rec_price = safe_float(raw.get("rec_price"))
        if rec_price is None:
            rec_price = safe_float(trow.get("Scan_Ref_Price"))
        if rec_price is None:
            rec_price = safe_float(trow.get("Price"))

        ticker = raw["ticker"]
        status = clean_text(trow.get("Status"))
        tag = clean_text(raw.get("tag")) or clean_text(trow.get("Tag"))
        if not tag and clean_text(hrow.get("Tag")) == "Observation":
            tag = "Observation"

        exit_price = safe_float(trow.get("Exit_Price"))
        if exit_price is None:
            exit_price = safe_float(hrow.get("Cur_Price"))

        closed_status = status in {
            "Stop_Loss_Hit", "移动止损清仓", "止损触发清仓",
            "已超期归档", "突发清仓暂停", "周期到期清仓"
        }

        if closed_status and exit_price is not None:
            current_price = exit_price
        else:
            current_price = safe_float(price_map_today.get(ticker))

        pnl = None
        if rec_price is not None and rec_price > 0 and current_price is not None:
            pnl = round((current_price - rec_price) / rec_price * 100, 2)

        events.append({
            "ticker": ticker,
            "name": raw.get("name") or clean_text(trow.get("Name"), ticker),
            "rec_date": raw["rec_date"],
            "rec_price": rec_price,
            "status": status,
            "tag": "Observation" if tag == "Observation" else tag,
            "current_price": current_price,
            "pnl": pnl,
            "data_status": (
                "NO_REC_PRICE" if rec_price is None or rec_price <= 0
                else "PRICE_MISSING" if current_price is None
                else "OK"
            ),
            "score": raw.get("score", "N/A"),
            "source_file": raw.get("source_file", ""),
        })

    return events

scan_events = build_scan_recommendation_events()

# 只统计最近30天 Scan 推荐事件
recent_event_cutoff = pd.Timestamp(today_us_str()) - pd.Timedelta(days=30)
scan_events_30d = [
    e for e in scan_events
    if normalize_date(e["rec_date"]) is not None
    and normalize_date(e["rec_date"]) >= recent_event_cutoff
]


# ============================================================
# 13. KPI
# ============================================================

stock_events_valid = [e for e in scan_events_30d if e["pnl"] is not None]
stock_events_missing = [e for e in scan_events_30d if e["pnl"] is None]

event_pnl = [e["pnl"] for e in stock_events_valid]

recommendation_wins = sum(p > 0 for p in event_pnl)
recommendation_losses = sum(p < 0 for p in event_pnl)
recommendation_neutral = sum(p == 0 for p in event_pnl)

recommendation_win_rate = (
    recommendation_wins / len(event_pnl) * 100
    if event_pnl else 0.0
)

# 实际持仓：只统计非 Observation 的当前 Active/持仓事件
active_tracking = []
for e in scan_events_30d:
    if e["tag"] == "Observation":
        continue
    if e["status"] in ("Active", "持仓中", "") and e["pnl"] is not None:
        active_tracking.append(e["pnl"])

# Observation：全部进入推荐绩效
observation_tracking = [
    e["pnl"] for e in scan_events_30d
    if e["tag"] == "Observation" and e["pnl"] is not None
]

actual_active_wins = sum(p > 0 for p in active_tracking)
actual_active_win_rate = (
    actual_active_wins / len(active_tracking) * 100
    if active_tracking else 0.0
)

obs_wins = sum(p > 0 for p in observation_tracking)
obs_win_rate = (
    obs_wins / len(observation_tracking) * 100
    if observation_tracking else 0.0
)

current_tracking = active_tracking + observation_tracking
tracking_wins = sum(p > 0 for p in current_tracking)
tracking_losses = sum(p < 0 for p in current_tracking)
tracking_neutral = sum(p == 0 for p in current_tracking)
tracking_win_rate = (
    tracking_wins / len(current_tracking) * 100
    if current_tracking else 0.0
)

# 已了结股票：不是 Observation 且状态已经退出
closed_stock_events = [
    e for e in scan_events_30d
    if e["tag"] != "Observation"
    and e["status"] not in ("Active", "持仓中", "")
    and e["pnl"] is not None
]
closed_stock_pnl = [e["pnl"] for e in closed_stock_events]
closed_stock_wins = sum(p > 0 for p in closed_stock_pnl)
closed_stock_win_rate = (
    closed_stock_wins / len(closed_stock_pnl) * 100
    if closed_stock_pnl else 0.0
)

total_scan_recommendations = len(scan_events_30d)
valid_performance_samples = len(stock_events_valid)
data_insufficient_count = len(stock_events_missing)

all_stock_pnl = event_pnl
super_threshold = 50.0
super_contribution = sum(p for p in all_stock_pnl if p >= super_threshold)

other_winners = [p for p in all_stock_pnl if 0 < p < super_threshold]
losers = [p for p in all_stock_pnl if p < 0]
other_avg = sum(other_winners)/len(other_winners) if other_winners else 0.0
loser_avg = sum(losers)/len(losers) if losers else 0.0


# 期权独立 KPI
option_closed_pnl = [safe_float(x.get("pnl"),0.0) for x in option_closed_records]
option_wins = sum(p > 0 for p in option_closed_pnl)
option_win_rate = option_wins/len(option_closed_pnl)*100 if option_closed_pnl else 0.0


print(
    f"📊 Scan推荐事件：{total_scan_recommendations}；"
    f"有效绩效：{valid_performance_samples}；"
    f"数据不足：{data_insufficient_count}"
)
print(f"📊 Scan推荐综合胜率：{recommendation_win_rate:.2f}%")
print(f"📊 当前推荐跟踪胜率：{tracking_win_rate:.2f}%")
print(f"📊 实际持仓胜率：{actual_active_win_rate:.2f}%")
print(f"📊 Observation胜率：{obs_win_rate:.2f}%")
print(f"📊 已了结股票胜率：{closed_stock_win_rate:.2f}%")


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

kpi_html = f"""
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:15px;margin-bottom:20px;">

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #1565c0;">
<div style="font-size:13px;color:#7f8c8d;">总股票 Scan 推荐事件</div>
<div style="font-size:24px;font-weight:bold;">{total_scan_recommendations}</div>
<div style="font-size:12px;">有效绩效 {valid_performance_samples} · 数据不足 {data_insufficient_count}</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #2ecc71;">
<div style="font-size:13px;color:#7f8c8d;">Scan 推荐综合胜率</div>
<div style="font-size:24px;font-weight:bold;color:#2ecc71;">{recommendation_win_rate:.2f}%</div>
<div style="font-size:12px;">{recommendation_wins} 赢 / {recommendation_losses} 亏 / {recommendation_neutral} 持平</div>
<div style="font-size:11px;color:#607d8b;">每次 Scan 推荐事件独立计算</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #17a2b8;">
<div style="font-size:13px;color:#7f8c8d;">当前推荐跟踪胜率</div>
<div style="font-size:24px;font-weight:bold;color:#17a2b8;">{tracking_win_rate:.2f}%</div>
<div style="font-size:12px;">{tracking_wins} 赢 / {tracking_losses} 亏 / {tracking_neutral} 持平</div>
<div style="font-size:11px;color:#607d8b;">实际持仓 + Observation</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #e67e22;">
<div style="font-size:13px;color:#7f8c8d;">实际持仓胜率</div>
<div style="font-size:24px;font-weight:bold;color:#e67e22;">{actual_active_win_rate:.2f}%</div>
<div style="font-size:12px;">{actual_active_wins} 赢 / {len(active_tracking)-actual_active_wins} 亏</div>
<div style="font-size:11px;color:#607d8b;">仅真实持仓，不含 Observation</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #ff9800;">
<div style="font-size:13px;color:#7f8c8d;">Observation 跟踪胜率</div>
<div style="font-size:24px;font-weight:bold;color:#ff9800;">{obs_win_rate:.2f}%</div>
<div style="font-size:12px;">{obs_wins} 赢 / {len(observation_tracking)-obs_wins} 亏</div>
<div style="font-size:11px;color:#607d8b;">有效 Scan 推荐，不是实际持仓</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #8e44ad;">
<div style="font-size:13px;color:#7f8c8d;">已了结股票胜率</div>
<div style="font-size:24px;font-weight:bold;color:#8e44ad;">{closed_stock_win_rate:.2f}%</div>
<div style="font-size:12px;">{closed_stock_wins} 赢 / {len(closed_stock_pnl)-closed_stock_wins} 亏</div>
<div style="font-size:11px;color:#607d8b;">不含期权</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #9b59b6;">
<div style="font-size:13px;color:#7f8c8d;">期权已了结胜率</div>
<div style="font-size:24px;font-weight:bold;color:#9b59b6;">{option_win_rate:.2f}%</div>
<div style="font-size:12px;">{option_wins} 赢 / {len(option_closed_pnl)-option_wins} 亏</div>
<div style="font-size:11px;color:#607d8b;">完全独立于股票 Scan 推荐</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #9b59b6;">
<div style="font-size:13px;color:#7f8c8d;">超级赢家贡献</div>
<div style="font-size:24px;font-weight:bold;">+{super_contribution:.2f}%</div>
<div style="font-size:12px;">单笔股票推荐盈利 ≥ 50%</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #1abc9c;">
<div style="font-size:13px;color:#7f8c8d;">其余盈利平均</div>
<div style="font-size:24px;font-weight:bold;">+{other_avg:.2f}%</div>
<div style="font-size:12px;">排除超级赢家</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #e74c3c;">
<div style="font-size:13px;color:#7f8c8d;">亏损平均</div>
<div style="font-size:24px;font-weight:bold;">{loser_avg:.2f}%</div>
<div style="font-size:12px;">所有有效股票 Scan 推荐亏损</div>
</div>

</div>
"""


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
<div style="color:#607d8b;">Observation 不计入实际持仓，但属于有效 Scan 推荐，按首次推荐价持续追踪并计入 Scan 推荐绩效。</div>
</div>
""")
    return '<h2 style="color:#e65100;border-bottom:2px solid #e65100;padding-bottom:5px;">👀 最近30天 Observation 推荐</h2>' + "".join(blocks)


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
<b>今日开盘→收盘：</b>{_pct(x.get("今日开盘→收盘%"))}</div>
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
            "current_underlying": cur,
            "quantity": safe_float(r.get("Quantity"),1),
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

active_option_snapshot = load_active_options_snapshot(price_map_today)
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
美股盘后复盘与风控审查报告（Scan推荐事件独立追踪 / 含期权）
</h2>

{kpi_html}

{build_observation_html()}

{build_active_html()}

{build_stopped_html()}

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
    f"综合胜率 {recommendation_win_rate:.2f}%"
)
print("=" * 60)
