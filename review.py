# -*- coding: utf-8 -*-
"""
美股盘后复盘与风控审查引擎（终极可靠版）
================================================
功能：
1. 与 scan.py 的 us_stocks_pending_YYYYMMDD.csv 联动
2. 自动修复 pending 中 Ticker 被写成公司名称的问题
3. yfinance 下载失败不会导致整个 review.py 崩溃
4. 缺失价格安全回退，不再对空字符串执行 float('')
5. 股票采用 MA20/MA50 + ATR + MACD/KDJ 移动止损：当日 Low <= 前一交易日保护线即触发
6. 股票不再按固定持仓天数强制归档，趋势破坏/移动止损才退出
7. 今日新增标的正常计入盈亏/胜率
8. 股票仅按动态止损/趋势破坏退出，不设置固定持仓天数
9. review_history.csv 自动归档
10. KPI / 胜率统计
11. Claude 生成 HTML 风控报告
12. Gmail 邮件发送
"""

import csv
import datetime
import glob
import os
import re
import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import anthropic
import pandas as pd
import yfinance as yf


# ============================================================
# 0. 环境变量
# ============================================================

_missing_env = [
    k for k in ("CLAWSOCKET_API_KEY", "CLAWSOCKET_BASE_URL")
    if not os.environ.get(k)
]
if _missing_env:
    print(f"致命错误：未检测到环境变量 {', '.join(_missing_env)}！")
    sys.exit(1)


# ============================================================
# 1. 时间
# ============================================================

US_TZ = ZoneInfo("America/New_York")


def get_us_time():
    return datetime.datetime.now(US_TZ)


def today_us_str():
    return get_us_time().strftime("%Y-%m-%d")


if get_us_time().weekday() >= 5:
    print("当前为周末，美股休市，退出复盘。")
    sys.exit(0)


TARGET_MODEL = "claude-opus-4-8"

print("=" * 60)
print("启动美股盘后复盘与风控审查引擎（终极可靠版）")
print("=" * 60)


# ============================================================
# 2. 通用安全函数
# ============================================================

INVALID_STRINGS = {
    "",
    "nan",
    "none",
    "null",
    "n/a",
    "na",
    "nat",
    "观望",
    "坚决空仓",
    "绝对规避",
}


def clean_text(value, default=""):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value).strip()


def safe_float(value, default=None):
    """
    绝对禁止 float('') 导致 review.py 崩溃。
    """
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

    # 处理类似 "$123.45 USD"
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return default

    try:
        value_f = float(m.group(0))
        if pd.isna(value_f):
            return default
        return value_f
    except Exception:
        return default


def safe_int(value, default=None):
    f = safe_float(value, None)
    if f is None:
        return default
    try:
        return int(f)
    except Exception:
        return default


def normalize_date(value):
    try:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return None
        if getattr(dt, "tzinfo", None) is not None:
            dt = dt.tz_localize(None)
        return dt
    except Exception:
        return None


def normalize_ticker_text(value):
    """
    只负责清洗字符串，不负责公司名称 -> 股票代码。
    """
    s = clean_text(value)
    s = s.replace("\ufeff", "").strip()
    s = s.lstrip("$").strip()
    return s


def is_probable_us_ticker(value):
    """
    判断一个字符串是否像真正的美股 ticker。
    允许 BRK-B / BF-B / etc.
    """
    s = normalize_ticker_text(value).upper()

    if not s:
        return False

    if len(s) > 8:
        return False

    return bool(re.fullmatch(r"[A-Z]{1,6}(?:[-.][A-Z]{1,3})?", s))


# ============================================================
# 3. 公司名称 -> Ticker 修复
# ============================================================
#
# 你这次报错的根本原因：
#
# pending 中出现：
#   Nvidia
#   Pfizer
#   Apple Inc.
#   Supermicro
#   Charles Schwab Corporation
#
# review.py 原来直接把这些字符串送给 yfinance：
#   yf.download(["Nvidia", "Pfizer", ...])
#
# yfinance 当然把它们当成 ticker，于是出现：
#   $NVIDIA: possibly delisted
#
# 现在先 canonicalize 成：
#   Nvidia -> NVDA
#   Pfizer -> PFE
#   Apple Inc. -> AAPL
#   Supermicro -> SMCI
#   Charles Schwab Corporation -> SCHW
#
# ============================================================

COMPANY_TO_TICKER = {
    # Technology
    "nvidia": "NVDA",
    "nvidia corporation": "NVDA",
    "nvidia corp": "NVDA",
    "apple": "AAPL",
    "apple inc": "AAPL",
    "apple inc.": "AAPL",
    "intel": "INTC",
    "intel corporation": "INTC",
    "broadcom": "AVGO",
    "broadcom inc": "AVGO",
    "broadcom inc.": "AVGO",
    "supermicro": "SMCI",
    "super micro": "SMCI",
    "super micro computer": "SMCI",
    "super micro computer inc": "SMCI",
    "super micro computer inc.": "SMCI",
    "intuit": "INTU",
    "intuit inc": "INTU",
    "intuit inc.": "INTU",
    "sandisk": "SNDK",
    "sandisk corporation": "SNDK",
    "the trade desk": "TTD",
    "the trade desk (the)": "TTD",
    "trade desk": "TTD",
    "trade desk (the)": "TTD",
    "charles schwab corporation": "SCHW",
    "charles schwab": "SCHW",
    "charles schwab corp": "SCHW",

    # Healthcare
    "pfizer": "PFE",
    "pfizer inc": "PFE",
    "pfizer inc.": "PFE",

    # Industrials / Energy
    "halliburton": "HAL",
    "halliburton company": "HAL",
    "eqt": "EQT",
    "eqt corporation": "EQT",
}


def normalize_company_key(value):
    s = clean_text(value).lower()
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def lookup_ticker_by_company_name(name):
    """
    最后一层才调用 yfinance Search。
    常见公司优先走本地映射，避免大量 API 请求。
    """
    name = clean_text(name)
    if not name:
        return None

    key = normalize_company_key(name)

    # 先本地映射
    for k, ticker in COMPANY_TO_TICKER.items():
        if normalize_company_key(k) == key:
            return ticker

    # yfinance Search 兜底
    try:
        result = yf.Search(name, max_results=8)
        quotes = result.quotes if result is not None else []

        for q in quotes:
            symbol = clean_text(q.get("symbol"))
            quote_type = clean_text(q.get("quoteType")).upper()

            if quote_type in ("EQUITY", "ETF", "") and is_probable_us_ticker(symbol):
                return symbol.upper()

    except Exception as e:
        print(f"⚠️ 公司名称解析失败 [{name}]: {e}")

    return None


def resolve_ticker(raw_ticker, company_name=""):
    """
    最可靠的 Ticker 解析：
    1. 已经是 ticker -> 直接使用
    2. 本地公司名映射
    3. Name 列映射
    4. yfinance Search
    5. 最后保留原值，但绝不让它导致程序崩溃
    """
    raw = normalize_ticker_text(raw_ticker)

    if is_probable_us_ticker(raw):
        return raw.upper()

    candidates = [raw, clean_text(company_name)]

    for candidate in candidates:
        if not candidate:
            continue

        key = normalize_company_key(candidate)

        for k, ticker in COMPANY_TO_TICKER.items():
            if normalize_company_key(k) == key:
                return ticker

    for candidate in candidates:
        if not candidate:
            continue

        found = lookup_ticker_by_company_name(candidate)
        if found:
            return found

    return raw.upper() if raw else ""


# ============================================================
# 4. yfinance 数据获取
# ============================================================

def extract_single_ticker_df(hist_data, ticker, ticker_count):
    """
    兼容 yfinance 单 ticker / MultiIndex 两种返回格式。
    """
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

        for col in required:
            if col not in sub.columns:
                return pd.DataFrame()

        sub = sub.dropna(subset=required).copy()

        if sub.empty:
            return pd.DataFrame()

        return sub

    except Exception:
        return pd.DataFrame()


def download_ohlc_safe(tickers, period="60d", start=None, end=None):
    """
    一次批量下载。
    任何 ticker 失败都不能让整个程序退出。
    """
    tickers = [
        normalize_ticker_text(t).upper()
        for t in tickers
        if normalize_ticker_text(t)
    ]

    tickers = list(dict.fromkeys(tickers))

    if not tickers:
        return pd.DataFrame(), {}

    print(f"📡 yfinance 请求 {len(tickers)} 只真实 ticker...")

    try:
        kwargs = {
            "progress": False,
            "auto_adjust": True,
            "group_by": "ticker",
            "threads": False,
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

    all_records = []
    latest_map = {}

    for ticker in tickers:
        sub = extract_single_ticker_df(hist, ticker, len(tickers))

        if sub.empty:
            print(f"⚠️ 无法获取 {ticker} OHLC，跳过该 ticker。")
            continue

        for dt, row in sub.iterrows():
            try:
                o = safe_float(row.get("Open"))
                h = safe_float(row.get("High"))
                l = safe_float(row.get("Low"))
                c = safe_float(row.get("Close"))

                if None in (o, h, l, c):
                    continue

                all_records.append({
                    "Ticker": ticker,
                    "Date": dt,
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                })
            except Exception:
                continue

        if all_records:
            try:
                last = sub.iloc[-1]
                o = safe_float(last.get("Open"))
                h = safe_float(last.get("High"))
                l = safe_float(last.get("Low"))
                c = safe_float(last.get("Close"))

                if None not in (o, h, l, c):
                    latest_map[ticker] = {
                        "open": o,
                        "high": h,
                        "low": l,
                        "close": c,
                    }
            except Exception:
                pass

    df_all = pd.DataFrame(all_records)

    print(f"✅ 成功获得 {len(latest_map)} / {len(tickers)} 只 ticker 的 OHLC。")

    return df_all, latest_map


def get_live_quote_bootstrap(ticker):
    """
    单 ticker 实时/最近价格兜底。
    """
    ticker = normalize_ticker_text(ticker).upper()

    if not is_probable_us_ticker(ticker):
        return None, None

    try:
        fi = yf.Ticker(ticker).fast_info

        open_p = safe_float(
            fi.get("open") if hasattr(fi, "get") else None
        )

        last_p = safe_float(
            fi.get("last_price") if hasattr(fi, "get") else None
        )

        return open_p, last_p

    except Exception as e:
        print(f"⚠️ 实时价格获取失败 {ticker}: {e}")
        return None, None


def get_price_from_history_row(df_rows, ticker):
    if df_rows is None or df_rows.empty:
        return None

    try:
        sub = df_rows[df_rows["Ticker"] == ticker].copy()
        if sub.empty:
            return None

        sub = sub.sort_values("Date")
        row = sub.iloc[-1]

        return {
            "open": safe_float(row.get("open")),
            "high": safe_float(row.get("high")),
            "low": safe_float(row.get("low")),
            "close": safe_float(row.get("close")),
        }

    except Exception:
        return None


# ============================================================
# 5. CSV / 账本兼容
# ============================================================

TRADE_HISTORY = "trade_history.csv"
REVIEW_HISTORY = "review_history.csv"


def ensure_trade_history_columns():
    """
    不再用字符串拼接 CSV。
    pandas.to_csv 会正确处理公司名中的逗号。
    """
    required = [
        "Date", "Ticker", "Name", "Tag", "Score", "Price", "RSI", "Bias",
        "Hold_Period", "Stop_Loss", "Stop_Method", "Trail_Stop", "Exit_Date", "Exit_Price", "Status",
        "Close_Price", "技术评分", "估值评分", "PE_TTM", "PE_Forward", "EPS_TTM", "PB",
        "MA20", "MA50", "ATR_Pct", "MACD金叉", "周线共振", "KDJ_J回升",
        "量能放大", "周期共振"
    ]

    if not os.path.exists(TRADE_HISTORY) or os.path.getsize(TRADE_HISTORY) == 0:
        return

    try:
        df = pd.read_csv(TRADE_HISTORY, dtype=str, keep_default_na=False)

        for col in required:
            if col not in df.columns:
                df[col] = ""

        df = df[required]
        df.to_csv(TRADE_HISTORY, index=False, encoding="utf-8")

    except Exception as e:
        print(f"⚠️ trade_history.csv 表结构检查失败：{e}")


def load_trade_history():
    if not os.path.exists(TRADE_HISTORY):
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            TRADE_HISTORY,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="skip",
        )

        if "Date" not in df.columns:
            print("❌ trade_history.csv 缺少 Date 列。")
            return pd.DataFrame()

        if "Ticker" not in df.columns:
            print("❌ trade_history.csv 缺少 Ticker 列。")
            return pd.DataFrame()

        if "Name" not in df.columns:
            df["Name"] = ""

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).copy()

        return df

    except Exception as e:
        print(f"❌ 读取 trade_history.csv 失败：{e}")
        return pd.DataFrame()


# ============================================================
# 6. pending 文件处理
# ============================================================

def recalibrate_stop_loss(stop_loss_str, scan_ref_price, real_open_price):
    try:
        s = clean_text(stop_loss_str)

        if s.lower() in INVALID_STRINGS:
            return stop_loss_str

        old_val = safe_float(s)
        ref = safe_float(scan_ref_price)
        new_open = safe_float(real_open_price)

        if None in (old_val, ref, new_open):
            return stop_loss_str

        if old_val <= 0 or ref <= 0 or new_open <= 0:
            return stop_loss_str

        new_val = round(old_val * (new_open / ref), 2)

        if str(s).startswith("$"):
            return f"${new_val}"

        return str(new_val)

    except Exception:
        return stop_loss_str


def migrate_trade_history():
    """
    老版本账本缺列时补列。
    """
    ensure_trade_history_columns()


def find_existing_record(df_existing, date_value, ticker):
    if df_existing.empty:
        return False

    target_date = normalize_date(date_value)

    if target_date is None:
        return False

    try:
        mask_date = df_existing["Date"] == target_date
        mask_ticker = (
            df_existing["Ticker"].astype(str).str.upper()
            == str(ticker).upper()
        )

        return bool((mask_date & mask_ticker).any())

    except Exception:
        return False


def supplement_us_stocks_from_pending():
    """
    关键修复：
    - pending 的 Ticker 如果是公司名称，先解析成真实 ticker
    - 不把公司名称直接交给 yfinance
    - 价格获取失败时允许写空，但后续绝不 float('')
    - 使用 pandas.to_csv，避免 Name 中的逗号破坏 CSV
    """
    pending_files = sorted(
        f for f in glob.glob("us_stocks_pending_*.csv")
        if not f.endswith(".processed")
    )

    if not pending_files:
        print("📋 无待确认美股文件，跳过补充。")
        return

    print(f"📋 发现 {len(pending_files)} 份待确认文件。")

    migrate_trade_history()

    df_existing = load_trade_history()

    for pending_file in pending_files:
        m = re.search(
            r"us_stocks_pending_(\d{8})\.csv$",
            os.path.basename(pending_file),
        )

        if not m:
            print(f"⚠️ 无法识别 pending 文件日期：{pending_file}")
            continue

        date_raw = m.group(1)
        target_date = (
            f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"
        )

        print(f"处理 {pending_file}（交易日 {target_date}）")

        try:
            df_pending = pd.read_csv(
                pending_file,
                dtype=str,
                keep_default_na=False,
                on_bad_lines="skip",
            )

            if df_pending.empty:
                print("ℹ️ pending 文件为空，标记 processed。")
                os.rename(
                    pending_file,
                    pending_file + ".processed",
                )
                continue

            if "Ticker" not in df_pending.columns:
                print("❌ pending 文件没有 Ticker 列，跳过。")
                continue

            # ==================================================
            # 第一步：把 Ticker 统一解析成真实股票代码
            # ==================================================

            resolved = []

            for _, row in df_pending.iterrows():
                raw_ticker = clean_text(row.get("Ticker"))
                name = clean_text(row.get("Name"))

                real_ticker = resolve_ticker(raw_ticker, name)

                if not real_ticker:
                    print(
                        f"⚠️ 无法解析 ticker："
                        f"raw={raw_ticker}, name={name}"
                    )
                    continue

                if real_ticker != raw_ticker.upper().lstrip("$"):
                    print(
                        f"🔧 ticker 修复："
                        f"{raw_ticker} -> {real_ticker}"
                    )

                resolved.append(
                    (row, real_ticker)
                )

            real_tickers = list(
                dict.fromkeys(
                    ticker
                    for _, ticker in resolved
                    if is_probable_us_ticker(ticker)
                )
            )

            # ==================================================
            # 第二步：一次性下载真实 ticker 行情
            # ==================================================

            df_hist, latest_map = download_ohlc_safe(
                real_tickers,
                period="10d",
            )

            target_dt = pd.Timestamp(target_date)
            historical_target = {}

            if not df_hist.empty:
                df_hist["Date"] = pd.to_datetime(
                    df_hist["Date"],
                    errors="coerce",
                )

                for ticker in real_tickers:
                    sub = df_hist[
                        (df_hist["Ticker"] == ticker)
                        & (df_hist["Date"] <= target_dt)
                    ].copy()

                    if sub.empty:
                        continue

                    sub = sub.sort_values("Date")
                    r = sub.iloc[-1]

                    historical_target[ticker] = {
                        "open": safe_float(r.get("open")),
                        "high": safe_float(r.get("high")),
                        "low": safe_float(r.get("low")),
                        "close": safe_float(r.get("close")),
                    }

            new_rows = []
            missing_price = []

            for row, ticker in resolved:

                # ----------------------------------------------
                # 去重
                # ----------------------------------------------

                if find_existing_record(
                    df_existing,
                    target_date,
                    ticker,
                ):
                    print(
                        f"⏭️ {ticker} ({clean_text(row.get('Name'))}) "
                        f"已在账本，跳过。"
                    )
                    continue

                # ----------------------------------------------
                # 优先使用目标交易日 OHLC
                # ----------------------------------------------

                price_data = historical_target.get(ticker)

                open_price = (
                    safe_float(price_data.get("open"))
                    if price_data
                    else None
                )

                close_price = (
                    safe_float(price_data.get("close"))
                    if price_data
                    else None
                )

                # ----------------------------------------------
                # 今日文件额外尝试实时价格
                # ----------------------------------------------

                if (
                    target_date == today_us_str()
                    and (
                        open_price is None
                        or close_price is None
                    )
                ):
                    live_open, live_last = get_live_quote_bootstrap(
                        ticker
                    )

                    if open_price is None:
                        open_price = live_open

                    if close_price is None:
                        close_price = (
                            live_last
                            if live_last is not None
                            else live_open
                        )

                # ----------------------------------------------
                # 缺失价格不再崩溃
                # ----------------------------------------------

                if open_price is None or close_price is None:
                    missing_price.append(ticker)

                calibrated_stop = row.get(
                    "Stop_Loss",
                    "N/A",
                )

                scan_ref = row.get(
                    "Scan_Ref_Price",
                    row.get("Price", ""),
                )

                if open_price is not None:
                    calibrated_stop = recalibrate_stop_loss(
                        row.get("Stop_Loss", "N/A"),
                        scan_ref,
                        open_price,
                    )

                record = {
                    "Date": target_date,
                    "Ticker": ticker,
                    "Name": clean_text(row.get("Name")),
                    "Tag": clean_text(row.get("Tag")),
                    "Score": clean_text(
                        row.get("Score"),
                        "N/A",
                    ),
                    "Price": (
                        open_price
                        if open_price is not None
                        else ""
                    ),
                    "RSI": clean_text(row.get("RSI")),
                    "Bias": clean_text(row.get("Bias")),
                    "Hold_Period": clean_text(
                        row.get("Hold_Period"),
                        "N/A",
                    ),
                    "Stop_Loss": calibrated_stop,
                    "Stop_Method": clean_text(row.get("Stop_Method"), "移动止损"),
                    "Trail_Stop": calibrated_stop,
                    "Exit_Date": "",
                    "Exit_Price": "",
                    "Status": "Active",
                    "Close_Price": (
                        close_price
                        if close_price is not None
                        else ""
                    ),
                    "技术评分": clean_text(row.get("技术评分")),
                    "估值评分": clean_text(row.get("估值评分")),
                    "PE_TTM": clean_text(row.get("PE_TTM")),
                    "PE_Forward": clean_text(row.get("PE_Forward")),
                    "EPS_TTM": clean_text(row.get("EPS_TTM")),
                    "PB": clean_text(row.get("PB")),
                    "MA20": "",
                    "MA50": "",
                    "MACD金叉": clean_text(row.get("MACD金叉")),
                    "周线共振": clean_text(row.get("周线共振")),
                    "KDJ_J回升": clean_text(row.get("KDJ_J回升")),
                    "量能放大": clean_text(row.get("量能放大")),
                    "ATR_Pct": clean_text(row.get("ATR_Pct")),
                    "周期共振": clean_text(row.get("周期共振")),
                }

                new_rows.append(record)

            if missing_price:
                print(
                    f"⚠️ 以下 ticker 暂时没有 OHLC："
                    f"{missing_price}"
                )

            if new_rows:
                df_new = pd.DataFrame(new_rows)

                # 与现有表统一列
                required_cols = [
                    "Date", "Ticker", "Name", "Tag", "Score",
                    "Price", "RSI", "Bias", "Hold_Period",
                    "Stop_Loss", "Stop_Method", "Trail_Stop", "Exit_Date", "Exit_Price",
                    "Status", "Close_Price", "技术评分", "估值评分", "PE_TTM", "PE_Forward", "EPS_TTM", "PB",
                    "MA20", "MA50", "ATR_Pct", "MACD金叉", "周线共振", "KDJ_J回升",
                    "量能放大", "周期共振"
                ]

                for col in required_cols:
                    if col not in df_new.columns:
                        df_new[col] = ""

                df_new = df_new[required_cols]

                if df_existing.empty:
                    df_final = df_new
                else:
                    for col in required_cols:
                        if col not in df_existing.columns:
                            df_existing[col] = ""

                    df_existing = df_existing[required_cols]
                    df_final = pd.concat(
                        [df_existing, df_new],
                        ignore_index=True,
                    )

                df_final.to_csv(
                    TRADE_HISTORY,
                    index=False,
                    encoding="utf-8",
                    quoting=csv.QUOTE_MINIMAL,
                )

                df_existing = df_final

                print(
                    f"✅ 新增 {len(new_rows)} 条美股记录。"
                )

            # 只有成功处理后才标记 processed
            os.rename(
                pending_file,
                pending_file + ".processed",
            )

            print(
                f"✅ {pending_file} 已处理并标记 .processed"
            )

        except Exception as e:
            print(
                f"❌ 处理 {pending_file} 出错：{e}"
            )
            # 不删除、不 processed，下一次可以重试。


# ============================================================
# 7. 运行 pending 补充
# ============================================================

supplement_us_stocks_from_pending()


# ============================================================
# 8. 加载最近 30 天账本
# ============================================================

df = load_trade_history()

if df.empty:
    print("无交易账本或账本为空，退出。")
    sys.exit(0)


cutoff_date = (
    get_us_time()
    .replace(tzinfo=None)
    - datetime.timedelta(days=30)
)

recent_picks = df[
    df["Date"] >= cutoff_date
].copy()

if recent_picks.empty:
    print("最近30天无记录，退出。")
    sys.exit(0)


print(
    f"📊 加载最近30天记录 "
    f"{len(recent_picks)} 行。"
)


# ============================================================
# 9. 账本字段兼容
# ============================================================

for col in [
    "Hold_Period",
    "Stop_Loss",
    "Score",
    "Name",
    "Tag",
    "Price",
    "Close_Price",
    "Status",
]:
    if col not in recent_picks.columns:
        recent_picks[col] = ""


recent_picks["Hold_Period"] = "动态持有"


# ============================================================
# 10. 再次统一修复历史账本中错误的公司名称 Ticker
# ============================================================

ticker_changes = []

for idx, row in recent_picks.iterrows():
    raw_ticker = clean_text(row.get("Ticker"))
    name = clean_text(row.get("Name"))

    real_ticker = resolve_ticker(
        raw_ticker,
        name,
    )

    if real_ticker and real_ticker != raw_ticker.upper().lstrip("$"):
        ticker_changes.append(
            (raw_ticker, real_ticker, name)
        )
        recent_picks.at[idx, "Ticker"] = real_ticker


if ticker_changes:
    print("🔧 发现历史账本中存在公司名称型 Ticker：")

    shown = set()

    for old, new, name in ticker_changes:
        key = (old, new)

        if key not in shown:
            print(
                f"   {old} -> {new}"
                f" ({name})"
            )
            shown.add(key)


# ============================================================
# 11. 获取行情
# ============================================================

all_tickers = []

for t in recent_picks["Ticker"].astype(str):
    resolved = resolve_ticker(t)
    if resolved and is_probable_us_ticker(resolved):
        all_tickers.append(resolved)

clean_tickers = list(dict.fromkeys(all_tickers))

print(
    f"📡 获取 {len(clean_tickers)} 只真实美股 ticker 的 "
    f"60日 OHLC..."
)

df_hist_all, ohlc_map_today = download_ohlc_safe(
    clean_tickers,
    period="60d",
)

price_map_today = {}

for ticker, ohlc in ohlc_map_today.items():
    close = safe_float(ohlc.get("close"))

    if close is not None:
        price_map_today[ticker] = close


# ============================================================
# 12. 缺失价格安全补全
# ============================================================

for ticker in clean_tickers:

    if ticker in price_map_today:
        continue

    live_open, live_last = get_live_quote_bootstrap(
        ticker
    )

    if live_last is not None:
        price_map_today[ticker] = live_last

        ohlc_map_today[ticker] = {
            "open": (
                live_open
                if live_open is not None
                else live_last
            ),
            "high": live_last,
            "low": live_last,
            "close": live_last,
        }

        print(
            f"🔄 {ticker} 使用实时价格兜底："
            f"{live_last}"
        )


# ============================================================
# 14. 持仓解析
# ============================================================

def parse_hold_days(value):
    s = clean_text(value)

    if s.lower() in INVALID_STRINGS:
        return None

    nums = re.findall(
        r"\d+",
        s,
    )

    if not nums:
        return None

    try:
        return int(nums[-1])
    except Exception:
        return None


def parse_stop_loss_price(value):
    s = clean_text(value)

    if s.lower() in INVALID_STRINGS:
        return None

    return safe_float(s)


def get_first_valid_value(group, column, extra_invalid=None):
    invalid = set(INVALID_STRINGS)

    if extra_invalid:
        invalid.update(extra_invalid)

    for _, row in group.iterrows():
        value = clean_text(row.get(column))

        if value.lower() not in invalid:
            return value

    return "N/A"


def safe_record_price(row):
    """
    优先 Price，其次 Close_Price。
    两者都为空时返回 None。
    """
    p = safe_float(row.get("Price"))

    if p is not None and p > 0:
        return p

    p = safe_float(row.get("Close_Price"))

    if p is not None and p > 0:
        return p

    return None


# ============================================================
# 15. 更新 trade_history 状态
# ============================================================

def update_trade_history_status(
    ticker,
    buy_date,
    new_status,
    exit_price,
):
    if not os.path.exists(TRADE_HISTORY):
        return

    try:
        df_orig = pd.read_csv(
            TRADE_HISTORY,
            dtype=str,
            keep_default_na=False,
        )

        if "Ticker" not in df_orig.columns:
            return

        if "Status" not in df_orig.columns:
            df_orig["Status"] = "Active"

        if "Exit_Date" not in df_orig.columns:
            df_orig["Exit_Date"] = ""

        if "Exit_Price" not in df_orig.columns:
            df_orig["Exit_Price"] = ""

        target_date = pd.to_datetime(
            buy_date,
            errors="coerce",
        )

        df_dates = pd.to_datetime(
            df_orig["Date"],
            errors="coerce",
        )

        ticker_mask = (
            df_orig["Ticker"].astype(str).str.upper()
            == str(ticker).upper()
        )

        date_mask = (
            df_dates.dt.strftime("%Y-%m-%d")
            == target_date.strftime("%Y-%m-%d")
            if not pd.isna(target_date)
            else False
        )

        active_mask = (
            df_orig["Status"].astype(str).str.strip()
            == "Active"
        )

        mask = (
            ticker_mask
            & date_mask
            & active_mask
        )

        if mask.any():
            df_orig.loc[
                mask,
                "Status"
            ] = new_status

            df_orig.loc[
                mask,
                "Exit_Date"
            ] = today_us_str()

            df_orig.loc[
                mask,
                "Exit_Price"
            ] = str(exit_price)

            df_orig.to_csv(
                TRADE_HISTORY,
                index=False,
                encoding="utf-8",
            )

            print(
                f"✅ 更新 {ticker} "
                f"状态={new_status} "
                f"退出价={exit_price}"
            )

    except Exception as e:
        print(
            f"⚠️ 更新 trade_history 状态失败 "
            f"{ticker}: {e}"
        )


# ============================================================
# 16. 历史 review 去重
# ============================================================

already_archived = set()

if (
    os.path.exists(REVIEW_HISTORY)
    and os.path.getsize(REVIEW_HISTORY) > 0
):
    try:
        existing_review = pd.read_csv(
            REVIEW_HISTORY,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="skip",
        )

        required = {
            "Status",
            "Ticker",
            "Rec_Date",
        }

        if required.issubset(
            existing_review.columns
        ):
            closed_statuses = {
                "已超期归档",
                "突发清仓暂停",
                "止损触发清仓",
                "周期到期清仓",
            }

            archived = existing_review[
                existing_review["Status"].isin(
                    closed_statuses
                )
            ].copy()

            already_archived = set(
                zip(
                    archived["Ticker"].astype(str),
                    archived["Rec_Date"].astype(str),
                )
            )

            print(
                f"📌 历史已归档交易 "
                f"{len(already_archived)} 条。"
            )

    except Exception as e:
        print(
            f"⚠️ 读取 review_history 失败：{e}"
        )


# ============================================================
# 16.5 移动止损：MA20/MA50 + ATR + MACD/KDJ
# ============================================================

def _calc_atr(df, length=14):
    """纯 pandas 实现 ATR（Average True Range）"""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=length, min_periods=length).mean()
    return atr


def _calc_macd(close, fast=12, slow=26, signal=9):
    """纯 pandas 实现 MACD（12,26,9）"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame({
        "MACD": macd_line,
        "MACD_SIGNAL": signal_line,
        "MACD_HIST": hist,
    })


def _calc_kdj(df, n=9):
    """纯 pandas/NumPy 实现 KDJ（K, D, J）"""
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    K = 50.0
    D = 50.0
    ks = []
    ds = []
    js = []
    for i in range(len(c)):
        if i < n - 1:
            ks.append(K)
            ds.append(D)
            js.append(3 * K - 2 * D)
            continue
        h_n = h[max(0, i - n + 1):i + 1].max()
        l_n = l[max(0, i - n + 1):i + 1].min()
        rsv = (c[i] - l_n) / (h_n - l_n + 1e-9) * 100 if (h_n - l_n) != 0 else 50.0
        K = 2 / 3 * K + 1 / 3 * rsv
        D = 2 / 3 * D + 1 / 3 * K
        ks.append(K)
        ds.append(D)
        js.append(3 * K - 2 * D)
    return pd.DataFrame({"K": ks, "D": ds, "J": js}, index=df.index)


def get_trailing_stop_context(ticker, entry_date=None, current_stop=None, before_date=None):
    try:
        hist = yf.download(ticker, period="6mo", progress=False, auto_adjust=True, threads=False)
        if hist is None or hist.empty:
            return None
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)
        hist = hist.dropna(subset=["Open", "High", "Low", "Close"]).copy()
        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        if entry_date is not None:
            hist = hist[hist.index >= pd.Timestamp(entry_date)]
        if len(hist) < 35:
            return None

        ref = pd.Timestamp(before_date).normalize() if before_date is not None else hist.index[-1]
        d = hist[hist.index < ref].copy()
        if d.empty:
            return None

        # 纯 pandas 指标计算
        d["MA20"] = d["Close"].rolling(window=20, min_periods=20).mean()
        d["MA50"] = d["Close"].rolling(window=50, min_periods=50).mean()
        d["ATR14"] = _calc_atr(d, length=14)

        macd_df = _calc_macd(d["Close"])
        d["MACD"] = macd_df["MACD"]
        d["MACD_SIGNAL"] = macd_df["MACD_SIGNAL"]
        d["MACD_HIST"] = macd_df["MACD_HIST"]

        kdj_df = _calc_kdj(d, n=9)
        d["KDJ_J"] = kdj_df["J"]

        r = d.iloc[-1]
        close = float(r["Close"])
        atr = float(r["ATR14"]) if pd.notna(r["ATR14"]) else close * 0.05
        ma20 = float(r["MA20"]) if pd.notna(r["MA20"]) else close
        ma50 = float(r["MA50"]) if pd.notna(r["MA50"]) else ma20
        pct = max(0.03, min(0.12, 2 * atr / max(close, 1e-9)))
        candidate = max(close * (1 - pct), ma20 - atr, ma50 - 1.5 * atr)

        macd_bear = bool(
            pd.notna(r["MACD"]) and pd.notna(r["MACD_SIGNAL"]) and float(r["MACD"]) < float(r["MACD_SIGNAL"])
        )
        kdj_falling = bool(
            len(d) >= 2 and float(d["KDJ_J"].iloc[-1]) < float(d["KDJ_J"].iloc[-2])
        )

        if macd_bear and kdj_falling:
            candidate = max(candidate, close - 1.5 * atr)

        candidate = min(candidate, close * 0.98)
        old = safe_float(current_stop)
        if old and old > 0:
            candidate = max(old, candidate)

        return {
            "exec_stop": round(candidate, 2),
            "ma20": round(ma20, 2),
            "ma50": round(ma50, 2),
            "atr_pct": round(atr / close * 100, 2) if close else None,
            "macd_hist": round(float(r["MACD_HIST"]), 4) if pd.notna(r["MACD_HIST"]) else None,
            "macd_bear": macd_bear,
            "kdj_j": round(float(r["KDJ_J"]), 2),
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
        for col in ["Stop_Loss", "Stop_Method", "Trail_Stop", "MA20", "MA50", "ATR_Pct"]:
            if col not in d.columns:
                d[col] = ""
        dates = pd.to_datetime(d["Date"], errors="coerce")
        mask = (
            (d["Ticker"].astype(str).str.upper() == str(ticker).upper())
            & (dates.dt.strftime("%Y-%m-%d") == str(buy_date))
            & (d["Status"].astype(str).str.strip() == "Active")
        )
        if mask.any():
            d.loc[mask, "Stop_Loss"] = str(stop_price)
            d.loc[mask, "Trail_Stop"] = str(stop_price)
            d.loc[mask, "Stop_Method"] = "MA20/MA50 + ATR + MACD/KDJ"
            d.loc[mask, "MA20"] = str(ctx.get("ma20", ""))
            d.loc[mask, "MA50"] = str(ctx.get("ma50", ""))
            d.loc[mask, "ATR_Pct"] = str(ctx.get("atr_pct", ""))
            d.to_csv(TRADE_HISTORY, index=False, encoding="utf-8")
    except Exception as e:
        print(f"⚠️ 更新移动止损失败 {ticker}: {e}")



# ============================================================
# 16.5 Review → Scan 风控联动 + 确定性逐笔归因
# ============================================================
def write_review_risk_linkage_us(ticker, rec_date_str, risk_status, stop_price=None, current_price=None, note=""):
    if not os.path.exists(TRADE_HISTORY): return
    try:
        d=pd.read_csv(TRADE_HISTORY,dtype=str,keep_default_na=False)
        for col in ["Review_Risk_Status","Review_Risk_Date","Review_Stop_Distance_Pct","Review_Risk_Note"]:
            if col not in d.columns: d[col]=""
            d[col]=d[col].astype(object)
        dates=pd.to_datetime(d.get("Date",""),errors="coerce")
        mask=(d["Ticker"].astype(str).str.strip().str.upper()==str(ticker).strip().upper())&(dates.dt.strftime("%Y-%m-%d")==str(rec_date_str)[:10])
        if not mask.any(): return
        d.loc[mask,"Review_Risk_Status"]=risk_status; d.loc[mask,"Review_Risk_Date"]=today_us_str()
        d.loc[mask,"Review_Risk_Note"]=note
        if stop_price is not None and current_price is not None and float(current_price)>0:
            d.loc[mask,"Review_Stop_Distance_Pct"]=round((float(current_price)-float(stop_price))/float(current_price)*100,2)
        else: d.loc[mask,"Review_Stop_Distance_Pct"]=0 if risk_status=="STOP_TRIGGERED" else ""
        d.to_csv(TRADE_HISTORY,index=False,encoding="utf-8")
    except Exception as e: print(f"⚠️ {ticker} Review→Scan 联动写回失败: {e}")

def build_us_attribution(item):
    pnl=safe_float(item.get("当前盈亏(%)")); cur=safe_float(item.get("现价"))
    ma20=safe_float(item.get("MA20")); ma50=safe_float(item.get("MA50"))
    macd=clean_text(item.get("MACD状态")); kdj=clean_text(item.get("KDJ状态"))
    stop=safe_float(item.get("止损价"))
    if pnl is None: reason="当前盈亏数据不足，无法可靠归因。"
    elif pnl<0:
        parts=[]
        if ma20 is not None and cur is not None and cur<ma20: parts.append("跌破MA20")
        if ma50 is not None and cur is not None and cur<ma50: parts.append("跌破MA50")
        if "偏空" in macd: parts.append("MACD偏空")
        if "回落" in kdj: parts.append("KDJ走弱")
        reason=f"当前持仓亏损 {pnl:.2f}%，主要来自建仓后的价格回撤。"
        if parts: reason+=" 技术原因："+"、".join(parts)+"。"
    elif pnl>0:
        parts=[]
        if ma20 is not None and cur is not None and cur>ma20: parts.append("站在MA20上方")
        if ma50 is not None and cur is not None and cur>ma50: parts.append("站在MA50上方")
        if "偏空" not in macd: parts.append("MACD未确认转空")
        reason=f"当前持仓盈利 {pnl:.2f}%。"
        if parts: reason+=" 主要支撑："+"、".join(parts)+"。"
    else: reason="当前盈亏接近持平，暂无明显方向性归因。"
    if stop is not None and cur is not None and cur>0:
        gap=(cur-stop)/cur*100
        action="止损距离较近，继续收紧风控。" if gap<=3 else "继续动态持有，以移动止损、MA20/MA50及MACD/KDJ趋势破坏作为退出依据。"
    else: action="继续动态持有；技术数据不足时沿用已有保护线。"
    return reason,action

# ============================================================
# 17. 股票风控
# ============================================================

active_list = []
expired_list = []
stopped_list = []

skipped_duplicate = 0
missing_entry_price = []


print("开始股票风控检查：采用 MA20/MA50 + ATR + MACD/KDJ 移动止损，不设置股票到期日...")

for orig_ticker, group in recent_picks.groupby("Ticker", sort=False):
    group=group.sort_values("Date").copy()
    if group.empty: continue
    ticker=resolve_ticker(orig_ticker,clean_text(group.iloc[0].get("Name")))
    if not ticker: continue
    first=group.iloc[0]; latest=group.iloc[-1]; rec_date=normalize_date(first.get("Date"))
    if rec_date is None: continue
    if clean_text(latest.get("Status")) not in {"", "Active", "pending"}: continue
    rec_date_str=rec_date.strftime("%Y-%m-%d"); rec_price=safe_record_price(first)
    if rec_price is None or rec_price<=0: missing_entry_price.append(ticker); continue
    ohlc=ohlc_map_today.get(ticker)
    if ohlc is None:
        cur=price_map_today.get(ticker)
        if cur is None: continue
        ohlc={"open":cur,"high":cur,"low":cur,"close":cur}
    low=safe_float(ohlc.get("low")); closep=safe_float(ohlc.get("close")); openp=safe_float(ohlc.get("open"))
    if low is None or closep is None: continue
    old_stop=safe_float(first.get("Stop_Loss")); ctx=get_trailing_stop_context(ticker,rec_date,old_stop,today_us_str()); exec_stop=ctx.get("exec_stop") if ctx else old_stop
    if exec_stop is not None and exec_stop>0 and low<=exec_stop:
        write_review_risk_linkage_us(ticker, rec_date_str, "STOP_TRIGGERED", exec_stop, closep, f"今日最低价 {low:.2f} 已触及/跌破移动止损 {exec_stop:.2f}；次日 Scan 禁止重新推荐。")
        exitp=openp if openp is not None and openp<exec_stop else exec_stop; pnl=round((exitp-rec_price)/rec_price*100,2)
        stopped_list.append({"代码":ticker,"名称":clean_text(first.get("Name"),ticker),"标签":clean_text(latest.get("Tag")),"推荐评分":clean_text(latest.get("Score"),"N/A"),"持股周期建议":"动态持有","止损价":exec_stop,"首次推荐日":rec_date_str,"首次推荐价":rec_price,"止损触发日":today_us_str(),"止损结算价":exitp,"止损盈亏(%)":pnl,"持仓天数":(pd.Timestamp(today_us_str())-rec_date).days,"系统连续推荐次数":len(group),"触发方式":"移动止损：前一交易日保护线","Stop_Method":"MA20/MA50 + ATR + MACD/KDJ"})
        update_trade_history_status(ticker,rec_date_str,"Stop_Loss_Hit",exitp); continue
    next_ctx=get_trailing_stop_context(ticker,rec_date,exec_stop,None); next_stop=next_ctx.get("exec_stop") if next_ctx else exec_stop
    if next_stop is not None and next_stop>0: update_trade_history_trailing_stop(ticker,rec_date_str,next_stop,next_ctx or ctx or {})
    c=next_ctx or ctx or {}; risk=[]
    if c.get("macd_bear"): risk.append("MACD弱势")
    if c.get("kdj_falling"): risk.append("KDJ回落")
    days=(pd.Timestamp(today_us_str())-rec_date).days
    risk_distance=((closep-next_stop)/closep*100) if next_stop and closep else None
    risk_status="STOP_NEAR" if risk_distance is not None and risk_distance<=3.0 else "CLEAR"
    risk_note=(f"收盘距离移动止损约 {risk_distance:.2f}%，次日 Scan 强提醒。" if risk_status=="STOP_NEAR" else "本次 Review 未发现触及或接近移动止损。")
    write_review_risk_linkage_us(ticker, rec_date_str, risk_status, next_stop, closep, risk_note)
    active_list.append({"代码":ticker,"名称":clean_text(first.get("Name"),ticker),"标签":clean_text(latest.get("Tag")),"推荐评分":clean_text(latest.get("Score"),"N/A"),"持股周期建议":"动态持有","止损价":next_stop if next_stop else "N/A","首次推荐日":rec_date_str,"首次推荐价":rec_price,"今日开盘价":openp if openp is not None else "N/A","现价":closep,"持仓天数":days,"剩余天数":"—","当前盈亏(%)":round((closep-rec_price)/rec_price*100,2),"系统连续推荐次数":len(group),"今日新增":"是" if rec_date_str==today_us_str() else "否","止损方法":"MA20/MA50 + ATR + MACD/KDJ","MA20":c.get("ma20"),"MA50":c.get("ma50"),"KDJ_J":c.get("kdj_j"),"MACD_Hist":c.get("macd_hist"),"趋势状态":"多头结构" if c.get("trend_ok") else "趋势转弱","风险提示":"、".join(risk) if risk else "趋势未出现同步转弱","Review_Risk_Status":risk_status,"Review_Risk_Date":today_us_str(),"Review_Stop_Distance_Pct":round(risk_distance,2) if risk_distance is not None else "","Review_Risk_Note":risk_note})


for _item in active_list:
    _reason,_action=build_us_attribution(_item)
    _item["盈利/亏损原因"]=_reason; _item["风控动作指令"]=_action
for _item in stopped_list:
    _item["盈利/亏损原因"]=f"移动止损触发，策略盈亏 {_item.get('止损盈亏(%)',0):.2f}%。"
    _item["风控动作指令"]="已触发移动止损，次日 Scan 禁止重新推荐。"

print(
    f"📊 股票分类："
    f"持仓 {len(active_list)}，"
    f"超期 {len(expired_list)}，"
    f"止损 {len(stopped_list)}，"
    f"历史重复跳过 {skipped_duplicate}"
)

if missing_entry_price:
    print(
        f"⚠️ 缺少有效建仓价的 ticker："
        f"{missing_entry_price}"
    )


if not any([
    active_list,
    stopped_list,

]):
    print("无任何复盘数据，退出。")
    sys.exit(0)


# ============================================================
# 18. review_history.csv
# ============================================================

REVIEW_COLUMNS = [
    "Review_Date",
    "Ticker",
    "Name",
    "Tag",
    "Rec_Date",
    "Rec_Price",
    "Cur_Price",
    "Days_Held",
    "PnL_Pct",
    "Maturity_PnL",
    "Hold_Period",
    "Stop_Loss",
    "Rec_Count",
    "Status",
    "Score",
]


def append_review_rows(rows):
    """
    使用 pandas 写 CSV，避免逗号破坏 CSV。
    """
    if not rows:
        return

    df_new = pd.DataFrame(
        rows,
        columns=REVIEW_COLUMNS,
    )

    if (
        os.path.exists(REVIEW_HISTORY)
        and os.path.getsize(REVIEW_HISTORY) > 0
    ):
        try:
            df_old = pd.read_csv(
                REVIEW_HISTORY,
                dtype=str,
                keep_default_na=False,
                on_bad_lines="skip",
            )

            for col in REVIEW_COLUMNS:
                if col not in df_old.columns:
                    df_old[col] = ""

            df_old = df_old[
                REVIEW_COLUMNS
            ]

            df_final = pd.concat(
                [df_old, df_new],
                ignore_index=True,
            )

        except Exception:
            df_final = df_new

    else:
        df_final = df_new

    df_final.to_csv(
        REVIEW_HISTORY,
        index=False,
        encoding="utf-8",
        quoting=csv.QUOTE_MINIMAL,
    )


review_rows = []
review_date = today_us_str()

for item in active_list:
    review_rows.append({
        "Review_Date": review_date,
        "Ticker": item["代码"],
        "Name": item["名称"],
        "Tag": item["标签"],
        "Rec_Date": item["首次推荐日"],
        "Rec_Price": item["首次推荐价"],
        "Cur_Price": item["现价"],
        "Days_Held": item["持仓天数"],
        "PnL_Pct": item["当前盈亏(%)"],
        "Maturity_PnL": "",
        "Hold_Period": "动态持有",
        "Stop_Loss": item["止损价"],
        "Stop_Method": item.get("止损方法", "MA20/MA50 + ATR + MACD/KDJ"),
        "Trail_Stop": item.get("止损价", ""),
        "Rec_Count": item["系统连续推荐次数"],
        "Status": "持仓中",
        "Score": item["推荐评分"],
    })

for item in stopped_list:
    review_rows.append({
        "Review_Date": review_date,
        "Ticker": item["代码"],
        "Name": item["名称"],
        "Tag": item["标签"],
        "Rec_Date": item["首次推荐日"],
        "Rec_Price": item["首次推荐价"],
        "Cur_Price": item["止损结算价"],
        "Days_Held": item["持仓天数"],
        "PnL_Pct": item["止损盈亏(%)"],
        "Maturity_PnL": item["止损盈亏(%)"],
        "Hold_Period": "动态持有",
        "Stop_Loss": item["止损价"],
        "Stop_Method": item.get("止损方法", "MA20/MA50 + ATR + MACD/KDJ"),
        "Trail_Stop": item.get("止损价", ""),
        "Rec_Count": item["系统连续推荐次数"],
        "Status": "移动止损清仓",
        "Score": item["推荐评分"],
    })

# 股票不再按固定期限生成 expired_list 新记录；仅保留历史兼容读取。



try:
    append_review_rows(review_rows)
    print(
        f"✅ review_history.csv "
        f"写入 {len(review_rows)} 条记录。"
    )
except Exception as e:
    print(
        f"❌ review_history.csv 写入失败：{e}"
    )


# ============================================================
# 19. Claude AI 风控报告
# ============================================================

print("🤖 调用 Claude 生成风控报告...")

client = anthropic.Anthropic(
    api_key=os.environ.get(
        "CLAWSOCKET_API_KEY"
    ),
    base_url=os.environ.get(
        "CLAWSOCKET_BASE_URL"
    ),
)


prompt = f"""
你是顶级量化风控总监。

以下是今日美股盘后复盘数据。

【股票持仓中】
{active_list}

【股票因移动止损退出】
{stopped_list}


要求：

1. 高分票（80以上）若亏损，要指出高预期未兑现。
2. 低分票（60以下）若盈利，要指出评分可能偏保守。
3. 今日新增标的要纳入正常盈亏分析。
4. 移动止损触发必须评价执行纪律，并检查止损是否随趋势抬升。
6. 不要编造不存在的数据。
7. 如果某只股票价格数据缺失，不要自行猜价格。
8. 输出中文。
9. 直接输出 HTML，不要 markdown 代码框。
10. 第一个字符必须是 <。

报告结构：

<div style="background:#eceff1;border-left:6px solid #455a64;padding:20px;margin-bottom:25px;border-radius:8px;">
<h3>盘后总体风控审查</h3>
<p>总结今日整体表现。</p>
</div>

<h2>持仓中 - 动态风控核对单</h2>
<p>股票不设置固定持仓到期日；持仓天数仅做统计，退出以移动止损和趋势破坏为准。</p>

对每一只 active_list 输出：
- 推荐日期
- 评分
- 系统连续推荐次数
- 动态持有状态（不设置固定到期天数）
- 当前移动止损位及止损方法
- 买入成本
- 当前价格
- 当前盈亏
- 持仓天数（仅记录，不作为退出条件）
- MA20/MA50、MACD、KDJ 状态
- 今日新增
- 风控动作指令

<h2>移动止损清仓 - 策略复盘</h2>

说明：
- 止损触发原因
- 触发价格
- 盈亏
- 评分
- 是否执行纪律

<h2>趋势转弱复盘</h2>

逐只评价；不因持仓天数达到某个值而强制卖出。

盈利用红色，亏损用绿色。
"""


ai_html = ""

try:
    with client.messages.stream(
        model=TARGET_MODEL,
        max_tokens=30000,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    ) as stream:

        for text in stream.text_stream:
            ai_html += text

except Exception as e:
    print(
        f"⚠️ Claude 报告生成失败：{e}"
    )

    # AI 失败不能让整个 review 工作流失败
    ai_html = """
<div style="background:#fff3cd;border-left:6px solid #f0ad4e;padding:20px;border-radius:8px;">
<h3>AI 风控报告暂时不可用</h3>
<p>行情、持仓、止损和归档数据已经完成处理；Claude 本次调用失败。</p>
</div>
"""


ai_html = (
    ai_html
    .replace("```html", "")
    .replace("```HTML", "")
    .replace("```", "")
    .strip()
)

html_start = ai_html.find("<")

if html_start > 0:
    ai_html = ai_html[
        html_start:
    ]


# ============================================================
# 20. KPI
# ============================================================

print("📊 计算 KPI...")

historical_closed = []

INVALID_H = {
    "",
    "n/a",
    "nan",
    "none",
}


if (
    os.path.exists(REVIEW_HISTORY)
    and os.path.getsize(REVIEW_HISTORY) > 0
):

    try:
        existing_review = pd.read_csv(
            REVIEW_HISTORY,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="skip",
        )

        closed_statuses = {
            "已超期归档",
            "突发清仓暂停",
            "止损触发清仓",
            "移动止损清仓",
            "周期到期清仓",
        }

        if "Status" in existing_review.columns:

            closed_rows = existing_review[
                existing_review["Status"].isin(
                    closed_statuses
                )
            ]

            for _, row in closed_rows.iterrows():

                pnl = safe_float(
                    row.get("PnL_Pct")
                )

                if pnl is None:
                    pnl = safe_float(
                        row.get(
                            "Maturity_PnL"
                        )
                    )

                if pnl is None:
                    continue

                historical_closed.append({
                    "ticker": clean_text(
                        row.get("Ticker")
                    ),
                    "name": clean_text(
                        row.get("Name")
                    ),
                    "pnl": pnl,
                    "status": clean_text(
                        row.get("Status")
                    ),
                })

    except Exception as e:
        print(
            f"⚠️ KPI 历史数据读取失败：{e}"
        )


# 本次新增关闭交易
for item in stopped_list:
    historical_closed.append({
        "ticker": item["代码"],
        "name": item["名称"],
        "pnl": item["止损盈亏(%)"],
        "status": "止损触发清仓",
    })

for item in expired_list:

    pnl = safe_float(
        item["期满日盈亏(%)"]
    )

    if pnl is None:
        continue

    historical_closed.append({
        "ticker": item["代码"],
        "name": item["名称"],
        "pnl": pnl,
        "status": "已超期归档",
    })


closed_count = len(
    historical_closed
)

active_count = len(
    active_list
)

total_count = (
    active_count
    + closed_count
)

new_today_count = sum(
    1
    for item in active_list
    if item.get("今日新增") == "是"
)


# 当前持仓胜率
active_pnl = [
    safe_float(
        item.get("当前盈亏(%)")
    )
    for item in active_list
]

active_pnl = [
    p for p in active_pnl
    if p is not None
]

active_wins = sum(
    1
    for p in active_pnl
    if p > 0
)

active_win_rate = (
    active_wins
    / len(active_pnl)
    * 100
    if active_pnl
    else 0.0
)


# 已了结胜率
closed_wins = sum(
    1
    for item in historical_closed
    if item["pnl"] > 0
)

closed_win_rate = (
    closed_wins
    / closed_count
    * 100
    if closed_count
    else 0.0
)


# 全部 PnL
all_pnl = (
    active_pnl
    + [
        item["pnl"]
        for item in historical_closed
    ]
)


super_threshold = 50.0

super_winners = [
    p
    for p in all_pnl
    if p >= super_threshold
]

super_contribution = sum(
    super_winners
)

other_winners = [
    p
    for p in all_pnl
    if 0 < p < super_threshold
]

other_avg = (
    sum(other_winners)
    / len(other_winners)
    if other_winners
    else 0.0
)

losers = [
    p
    for p in all_pnl
    if p < 0
]

loser_avg = (
    sum(losers)
    / len(losers)
    if losers
    else 0.0
)


# ============================================================
# 21. KPI HTML
# ============================================================

kpi_html = f"""
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:20px;">

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #1565c0;">
<div style="font-size:13px;color:#7f8c8d;">总推荐笔数</div>
<div style="font-size:24px;font-weight:bold;">{total_count}</div>
<div style="font-size:12px;">持仓 {active_count}（今日新增 {new_today_count}） · 了结 {closed_count}</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #2ecc71;">
<div style="font-size:13px;color:#7f8c8d;">持仓胜率</div>
<div style="font-size:24px;font-weight:bold;color:#2ecc71;">{active_win_rate:.2f}%</div>
<div style="font-size:12px;">{active_wins} 赢 / {len(active_pnl)-active_wins} 亏</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #e67e22;">
<div style="font-size:13px;color:#7f8c8d;">已了结胜率</div>
<div style="font-size:24px;font-weight:bold;color:#e67e22;">{closed_win_rate:.2f}%</div>
<div style="font-size:12px;">{closed_wins} 赢 / {closed_count-closed_wins} 亏（）</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #9b59b6;">
<div style="font-size:13px;color:#7f8c8d;">超级赢家贡献</div>
<div style="font-size:24px;font-weight:bold;color:#9b59b6;">+{super_contribution:.2f}%</div>
<div style="font-size:12px;">单笔盈利 ≥ {super_threshold:.0f}% 的累计贡献</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #1abc9c;">
<div style="font-size:13px;color:#7f8c8d;">其余盈利平均</div>
<div style="font-size:24px;font-weight:bold;color:#1abc9c;">+{other_avg:.2f}%</div>
<div style="font-size:12px;">排除超级赢家</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #e74c3c;">
<div style="font-size:13px;color:#7f8c8d;">亏损平均</div>
<div style="font-size:24px;font-weight:bold;color:#e74c3c;">{loser_avg:.2f}%</div>
<div style="font-size:12px;">所有亏损标的平均</div>
</div>

</div>
"""


# ============================================================
# 22. 完整 HTML
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
    box-shadow:0 4px 6px rgba(0,0,0,0.05);
    max-width:1200px;
    margin:0 auto;
}}
</style>
</head>
<body>
<div class="card">

<h2 style="color:#2c3e50;margin-bottom:20px;border-bottom:3px solid #1565c0;padding-bottom:10px;">
美股盘后复盘与风控审查报告（）
</h2>

{kpi_html}

{ai_html}

</div>
</body>
</html>
"""


# ============================================================
# 23. 邮件
# ============================================================

def send_mail():
    account = os.environ.get(
        "EMAIL_ACCOUNT"
    )

    password = os.environ.get(
        "EMAIL_PASSWORD"
    )

    owner_email = (
        os.environ.get("TARGET_EMAILS")
        or os.environ.get("OWNER_EMAIL")
    )

    if not account or not password or not owner_email:
        print(
            "⚠️ 邮件配置缺失，"
            "本次不发送邮件。"
        )
        return

    msg = MIMEMultipart()

    msg["From"] = account
    msg["To"] = owner_email
    msg["Subject"] = (
        "盘后清算 美股风控纪律与复盘 "
        f"({today_us_str()})"
    )

    msg.attach(
        MIMEText(
            full_html,
            "html",
            "utf-8",
        )
    )

    to_list = [
        x.strip()
        for x in owner_email.split(",")
        if x.strip()
    ]

    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            timeout=30,
        ) as server:

            server.login(
                account,
                password,
            )

            server.sendmail(
                account,
                to_list,
                msg.as_string(),
            )

        print(
            f"✅ 邮件发送成功："
            f"{owner_email}"
        )

    except Exception as e:
        print(
            f"❌ 邮件发送失败：{e}"
        )


# ============================================================
# 24. 完成
# ============================================================

send_mail()

print("=" * 60)
print(
    "✅ 美股盘后复盘完成。"
    "（硬止损 + pending 联动 + "
    "Ticker 自动修复 + KPI）"
)
print("=" * 60)
