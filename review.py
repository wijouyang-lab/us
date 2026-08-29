# -*- coding: utf-8 -*-
"""
美股盘后复盘与风控审查引擎（终极可靠版）
================================================
功能：
1. 与 scan.py 的 us_stocks_pending_YYYYMMDD.csv 联动
2. 自动修复 pending 中 Ticker 被写成公司名称的问题
3. yfinance 下载失败不会导致整个 review.py 崩溃
4. 缺失价格安全回退，不再对空字符串执行 float('')
5. 股票硬止损：当日 Low <= Stop_Loss 即触发
6. 股票到期归档
7. 今日新增标的正常计入盈亏/胜率
8. 期权到期自动平仓
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
OPTION_LOG_FILE = "option_strategies.csv"


def ensure_trade_history_columns():
    """
    不再用字符串拼接 CSV。
    pandas.to_csv 会正确处理公司名中的逗号。
    """
    required = [
        "Date", "Ticker", "Name", "Tag", "Score", "Price", "RSI", "Bias",
        "Hold_Period", "Stop_Loss", "Exit_Date", "Exit_Price", "Status",
        "Close_Price", "技术评分", "MACD金叉", "周线共振", "KDJ_J回升",
        "量能放大", "ATR_Pct", "周期共振"
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
                    "Exit_Date": "",
                    "Exit_Price": "",
                    "Status": "Active",
                    "Close_Price": (
                        close_price
                        if close_price is not None
                        else ""
                    ),
                    "技术评分": clean_text(row.get("技术评分")),
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
                    "Stop_Loss", "Exit_Date", "Exit_Price",
                    "Status", "Close_Price", "技术评分",
                    "MACD金叉", "周线共振", "KDJ_J回升",
                    "量能放大", "ATR_Pct", "周期共振"
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


valid_mask = (
    recent_picks["Hold_Period"]
    .astype(str)
    .str.strip()
    .str.lower()
    .map(lambda x: x not in INVALID_STRINGS)
)

recent_picks = recent_picks[
    valid_mask
].copy()

if recent_picks.empty:
    print("无有效持仓，退出。")
    sys.exit(0)


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
# 13. 期权
# ============================================================

def load_option_positions():
    if (
        not os.path.exists(OPTION_LOG_FILE)
        or os.path.getsize(OPTION_LOG_FILE) == 0
    ):
        return pd.DataFrame()

    try:
        df_opt = pd.read_csv(
            OPTION_LOG_FILE,
            dtype=str,
            keep_default_na=False,
        )

        required = [
            "Ticker",
            "OptionType",
            "Strike",
            "Expiry",
            "EntryPrice",
            "Status",
            "EntryDate",
        ]

        for col in required:
            if col not in df_opt.columns:
                df_opt[col] = ""

        df_opt = df_opt[
            df_opt["Status"].astype(str).str.strip()
            == "Active"
        ].copy()

        if not df_opt.empty:
            df_opt["Expiry"] = pd.to_datetime(
                df_opt["Expiry"],
                errors="coerce",
            )

        return df_opt

    except Exception as e:
        print(f"⚠️ 读取期权账本失败：{e}")
        return pd.DataFrame()


def close_option_position(
    row,
    close_price,
    close_date,
    reason,
):
    try:
        df_opt = pd.read_csv(
            OPTION_LOG_FILE,
            dtype=str,
            keep_default_na=False,
        )

        for col in [
            "Status",
            "Close_Date",
            "Close_Price",
            "PnL",
        ]:
            if col not in df_opt.columns:
                df_opt[col] = ""

        ticker = clean_text(row.get("Ticker")).upper()
        expiry = clean_text(row.get("Expiry"))

        mask = (
            df_opt["Ticker"].astype(str).str.upper()
            == ticker
        ) & (
            pd.to_datetime(
                df_opt["Expiry"],
                errors="coerce",
            ).dt.strftime("%Y-%m-%d")
            == pd.to_datetime(
                expiry,
                errors="coerce",
            ).strftime("%Y-%m-%d")
        ) & (
            df_opt["Status"].astype(str).str.strip()
            == "Active"
        )

        if not mask.any():
            return 0.0

        entry = safe_float(row.get("EntryPrice"), 0.0)
        qty = safe_float(row.get("Quantity"), 1.0)

        if entry is None:
            entry = 0.0

        if qty is None:
            qty = 1.0

        qty_contracts = qty * 100.0

        option_type = (
            clean_text(row.get("OptionType"))
            .upper()
        )

        if option_type == "CALL":
            pnl = (
                (close_price - entry)
                * qty_contracts
            )
        else:
            pnl = (
                (entry - close_price)
                * qty_contracts
            )

        df_opt.loc[mask, "Status"] = "Closed"
        df_opt.loc[mask, "Close_Date"] = close_date
        df_opt.loc[mask, "Close_Price"] = close_price
        df_opt.loc[mask, "PnL"] = round(pnl, 2)

        df_opt.to_csv(
            OPTION_LOG_FILE,
            index=False,
            encoding="utf-8",
        )

        print(
            f"🔒 [期权] {ticker} "
            f"{option_type} "
            f"{row.get('Strike')} "
            f"平仓，原因：{reason}，"
            f"盈亏 ${pnl:.2f}"
        )

        return round(pnl, 2)

    except Exception as e:
        print(f"⚠️ 期权平仓失败：{e}")
        return 0.0


def process_options(price_map):
    df_opt = load_option_positions()

    if df_opt.empty:
        print("📋 无活跃期权持仓。")
        return []

    today = get_us_time().date()
    closed_records = []

    for _, row in df_opt.iterrows():

        expiry_dt = pd.to_datetime(
            row.get("Expiry"),
            errors="coerce",
        )

        if pd.isna(expiry_dt):
            print(
                f"⚠️ 期权到期日无效："
                f"{row.get('Ticker')}"
            )
            continue

        expiry_date = expiry_dt.date()

        if expiry_date > today:
            continue

        underlying = resolve_ticker(
            row.get("Ticker")
        )

        cur_price = price_map.get(
            underlying
        )

        if cur_price is None:
            _, cur_price = get_live_quote_bootstrap(
                underlying
            )

        if cur_price is None:
            print(
                f"⚠️ [期权] {underlying} "
                f"现价获取失败，暂不平仓。"
            )
            continue

        strike = safe_float(
            row.get("Strike"),
            0.0,
        )

        option_type = (
            clean_text(
                row.get("OptionType")
            ).upper()
        )

        if option_type == "CALL":
            intrinsic = max(
                0.0,
                cur_price - strike,
            )
        else:
            intrinsic = max(
                0.0,
                strike - cur_price,
            )

        reason = (
            "价内行权"
            if intrinsic > 0
            else "价外归零"
        )

        pnl = close_option_position(
            row,
            intrinsic,
            today.strftime("%Y-%m-%d"),
            reason,
        )

        closed_records.append({
            "ticker": underlying,
            "option_type": option_type,
            "strike": strike,
            "expiry": expiry_date.strftime(
                "%Y-%m-%d"
            ),
            "entry_price": safe_float(
                row.get("EntryPrice"),
                0.0,
            ),
            "close_price": intrinsic,
            "pnl": pnl,
            "reason": reason,
        })

    return closed_records


option_closed_records = process_options(
    price_map_today
)

if option_closed_records:
    print(
        f"✅ 今日自动平仓期权 "
        f"{len(option_closed_records)} 笔。"
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
# 17. 股票风控
# ============================================================

active_list = []
expired_list = []
stopped_list = []

skipped_duplicate = 0
missing_entry_price = []


print(
    "开始股票风控检查："
    "当日最低价触及止损即清仓..."
)


for orig_ticker, group in recent_picks.groupby(
    "Ticker",
    sort=False,
):

    group = group.sort_values("Date").copy()

    if group.empty:
        continue

    ticker = resolve_ticker(
        orig_ticker,
        clean_text(group.iloc[0].get("Name")),
    )

    if not ticker:
        continue

    first_row = group.iloc[0]
    latest_row = group.iloc[-1]

    rec_date = normalize_date(
        first_row.get("Date")
    )

    if rec_date is None:
        continue

    rec_date_str = rec_date.strftime(
        "%Y-%m-%d"
    )

    days_held = (
        get_us_time()
        .replace(tzinfo=None)
        - rec_date
    ).days

    latest_tag = clean_text(
        latest_row.get("Tag")
    )

    if latest_tag in {
        "Trap_Warning",
        "Forced_Exit",
        "Stop_Loss_Hit",
        "Period_Matured",
    }:
        continue

    hold_period_str = get_first_valid_value(
        group,
        "Hold_Period",
        extra_invalid={
            "坚决空仓",
        },
    )

    stop_loss_str = get_first_valid_value(
        group,
        "Stop_Loss",
        extra_invalid={
            "坚决空仓",
            "绝对规避",
        },
    )

    score_str = get_first_valid_value(
        group,
        "Score",
    )

    hold_days = parse_hold_days(
        hold_period_str
    )

    if hold_days is None:
        print(
            f"⏭️ {ticker} "
            f"Hold_Period 无法解析，跳过。"
        )
        continue

    rec_price = safe_record_price(
        first_row
    )

    if rec_price is None or rec_price <= 0:
        missing_entry_price.append(
            ticker
        )
        print(
            f"⚠️ {ticker} 缺少有效建仓价格，"
            f"跳过风控计算但不会崩溃。"
        )
        continue

    ohlc = ohlc_map_today.get(
        ticker
    )

    if ohlc is None:
        cur = price_map_today.get(
            ticker
        )

        if cur is None:
            print(
                f"⚠️ {ticker} 无今日行情，"
                f"跳过，不伪造价格。"
            )
            continue

        ohlc = {
            "open": cur,
            "high": cur,
            "low": cur,
            "close": cur,
        }

    today_low = safe_float(
        ohlc.get("low")
    )

    cur_price = safe_float(
        ohlc.get("close")
    )

    today_open = safe_float(
        ohlc.get("open")
    )

    if None in (
        today_low,
        cur_price,
    ):
        print(
            f"⚠️ {ticker} 今日 OHLC 不完整，"
            f"跳过。"
        )
        continue

    # ========================================================
    # 17.1 硬止损
    # ========================================================

    stop_loss_num = parse_stop_loss_price(
        stop_loss_str
    )

    if (
        stop_loss_num is not None
        and today_low <= stop_loss_num
    ):

        exit_price = stop_loss_num

        pnl_pct = round(
            (
                (exit_price - rec_price)
                / rec_price
            ) * 100,
            2,
        )

        stopped_list.append({
            "代码": ticker,
            "名称": clean_text(
                first_row.get(
                    "Name",
                    ticker,
                ),
                ticker,
            ),
            "标签": latest_tag,
            "推荐评分": score_str,
            "持股周期建议": hold_period_str,
            "止损价": stop_loss_str,
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "止损触发日": today_us_str(),
            "止损结算价": exit_price,
            "止损盈亏(%)": pnl_pct,
            "持仓天数": days_held,
            "系统连续推荐次数": len(group),
            "触发方式": "盘中最低价触及止损",
        })

        update_trade_history_status(
            ticker,
            rec_date_str,
            "Stop_Loss_Hit",
            exit_price,
        )

        continue

    # ========================================================
    # 17.2 到期
    # ========================================================

    maturity_date = (
        rec_date
        + datetime.timedelta(
            days=hold_days
        )
    )

    now_naive = (
        get_us_time()
        .replace(tzinfo=None)
    )

    if (
        maturity_date
        <= now_naive
    ):

        archive_key = (
            str(ticker),
            rec_date_str,
        )

        if archive_key in already_archived:
            skipped_duplicate += 1
            continue

        maturity_price = None

        if (
            not df_hist_all.empty
            and "Ticker" in df_hist_all.columns
        ):

            ticker_hist = df_hist_all[
                df_hist_all["Ticker"] == ticker
            ].copy()

            if not ticker_hist.empty:
                ticker_hist["Date"] = pd.to_datetime(
                    ticker_hist["Date"],
                    errors="coerce",
                )

                ticker_hist = ticker_hist.dropna(
                    subset=["Date"]
                )

                valid = ticker_hist[
                    ticker_hist["Date"]
                    <= pd.Timestamp(
                        maturity_date
                    )
                ].sort_values("Date")

                if not valid.empty:
                    maturity_price = safe_float(
                        valid.iloc[-1].get(
                            "close"
                        )
                    )

        maturity_pnl = None

        if (
            maturity_price is not None
            and rec_price > 0
        ):
            maturity_pnl = round(
                (
                    (
                        maturity_price
                        - rec_price
                    )
                    / rec_price
                )
                * 100,
                2,
            )

        expired_list.append({
            "代码": ticker,
            "名称": clean_text(
                first_row.get(
                    "Name",
                    ticker,
                ),
                ticker,
            ),
            "标签": latest_tag,
            "推荐评分": score_str,
            "持股周期建议": hold_period_str,
            "止损价": stop_loss_str,
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "期满日": maturity_date.strftime(
                "%Y-%m-%d"
            ),
            "期满日价格": (
                maturity_price
                if maturity_price is not None
                else "无数据"
            ),
            "期满日盈亏(%)": (
                maturity_pnl
                if maturity_pnl is not None
                else "无数据"
            ),
            "持仓天数": days_held,
            "系统连续推荐次数": len(group),
        })

        continue

    # ========================================================
    # 17.3 活跃持仓
    # ========================================================

    is_new_today = (
        rec_date_str == today_us_str()
    )

    effective_rec_price = rec_price

    if (
        is_new_today
        and today_open is not None
        and today_open > 0
    ):
        effective_rec_price = today_open

    remaining = (
        maturity_date
        - now_naive
    ).days

    cur_pnl = round(
        (
            (
                cur_price
                - effective_rec_price
            )
            / effective_rec_price
        )
        * 100,
        2,
    )

    active_list.append({
        "代码": ticker,
        "名称": clean_text(
            first_row.get(
                "Name",
                ticker,
            ),
            ticker,
        ),
        "标签": latest_tag,
        "推荐评分": score_str,
        "持股周期建议": hold_period_str,
        "止损价": stop_loss_str,
        "首次推荐日": rec_date_str,
        "首次推荐价": effective_rec_price,
        "今日开盘价": (
            round(today_open, 2)
            if is_new_today
            and today_open is not None
            else "N/A"
        ),
        "现价": cur_price,
        "持仓天数": days_held,
        "剩余天数": remaining,
        "当前盈亏(%)": cur_pnl,
        "系统连续推荐次数": len(group),
        "今日新增": (
            "是"
            if is_new_today
            else "否"
        ),
    })


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
    expired_list,
    stopped_list,
    option_closed_records,
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
    "Option_Type",
    "Strike",
    "Expiry",
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
        "Hold_Period": item["持股周期建议"],
        "Stop_Loss": item["止损价"],
        "Rec_Count": item["系统连续推荐次数"],
        "Status": "持仓中",
        "Score": item["推荐评分"],
        "Option_Type": "",
        "Strike": "",
        "Expiry": "",
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
        "Hold_Period": item["持股周期建议"],
        "Stop_Loss": item["止损价"],
        "Rec_Count": item["系统连续推荐次数"],
        "Status": "止损触发清仓",
        "Score": item["推荐评分"],
        "Option_Type": "",
        "Strike": "",
        "Expiry": "",
    })

for item in expired_list:
    pnl = (
        item["期满日盈亏(%)"]
        if item["期满日盈亏(%)"] != "无数据"
        else ""
    )

    review_rows.append({
        "Review_Date": review_date,
        "Ticker": item["代码"],
        "Name": item["名称"],
        "Tag": item["标签"],
        "Rec_Date": item["首次推荐日"],
        "Rec_Price": item["首次推荐价"],
        "Cur_Price": item["期满日价格"],
        "Days_Held": item["持仓天数"],
        "PnL_Pct": pnl,
        "Maturity_PnL": pnl,
        "Hold_Period": item["持股周期建议"],
        "Stop_Loss": item["止损价"],
        "Rec_Count": item["系统连续推荐次数"],
        "Status": "已超期归档",
        "Score": item["推荐评分"],
        "Option_Type": "",
        "Strike": "",
        "Expiry": "",
    })

for opt in option_closed_records:
    review_rows.append({
        "Review_Date": review_date,
        "Ticker": opt["ticker"],
        "Name": opt["ticker"] + " OPT",
        "Tag": "期权平仓",
        "Rec_Date": opt["expiry"],
        "Rec_Price": opt["entry_price"],
        "Cur_Price": opt["close_price"],
        "Days_Held": "",
        "PnL_Pct": opt["pnl"],
        "Maturity_PnL": opt["pnl"],
        "Hold_Period": "",
        "Stop_Loss": "",
        "Rec_Count": "",
        "Status": "期权平仓",
        "Score": opt["reason"],
        "Option_Type": opt["option_type"],
        "Strike": opt["strike"],
        "Expiry": opt["expiry"],
    })


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

【股票止损触发清仓】
{stopped_list}

【股票已超期】
{expired_list}

【期权自动平仓】
{option_closed_records}

要求：

1. 高分票（80以上）若亏损，要指出高预期未兑现。
2. 低分票（60以下）若盈利，要指出评分可能偏保守。
3. 今日新增标的要纳入正常盈亏分析。
4. 止损触发必须评价硬止损纪律。
5. 期权要点评价策略有效性。
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

<h2>持仓中 - 风控纪律核对单</h2>

对每一只 active_list 输出：
- 推荐日期
- 评分
- 系统连续推荐次数
- 持股周期
- 止损位
- 买入成本
- 当前价格
- 当前盈亏
- 持仓天数
- 剩余天数
- 今日新增
- 风控动作指令

<h2>止损触发清仓 - 策略复盘</h2>

说明：
- 止损触发原因
- 触发价格
- 盈亏
- 评分
- 是否执行纪律

<h2>已超期归档 - 策略复盘评价</h2>

逐只评价。

<h2>期权持仓风控 - 平仓复盘</h2>

逐只评价。

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
            "周期到期清仓",
            "期权平仓",
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

for opt in option_closed_records:
    historical_closed.append({
        "ticker": opt["ticker"],
        "name": opt["ticker"] + " OPT",
        "pnl": opt["pnl"],
        "status": "期权平仓",
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
<div style="font-size:12px;">{closed_wins} 赢 / {closed_count-closed_wins} 亏（含期权）</div>
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
美股盘后复盘与风控审查报告（含期权）
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
    "Ticker 自动修复 + 期权 + KPI）"
)
print("=" * 60)
