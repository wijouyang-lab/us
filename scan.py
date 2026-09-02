# -*- coding: utf-8 -*-
"""
美股盘前扫描引擎（完整 Regime Gate 版）
- 保留 Top300 / 日线+周线 / MACD / RSI / KDJ / ATR
- 基于完整美股 scan 原版结构改造，不删除原有 pending / review / option / portfolio 功能
- 保留宏观新闻、Mega-Cap 新闻、重要人物讲话、结构化美国经济数据、全球大宗、板块 ETF、个股新闻
- 保留跨市场 AVOID / BUY_DIP / POSITIVE_CATALYST / ROTATION / CONTRARIAN
- 新增：事件驱动 Regime Gate
- 新增：Fed/Warsh/通胀/利率/美元→行业门控
- 新增：重要人物讲话 + 结构化 CPI/PCE/失业率/政策利率作为 Regime 证据层
- 新增：当前行业价格确认，避免“周线共振但行业正在崩”仍然进入 Top5
- 历史进化规则改为条件化参考，不把过去低胜率板块永久封禁
- 保留 pending / trade_history / option_strategies / review.py 联动
"""

import faulthandler
faulthandler.enable()

import datetime
import email.utils
import hashlib
import html
import io
import json
import os
import random
import re
import smtplib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import pandas as pd
import pandas_ta as ta
import requests
import yfinance as yf

# 可选：已有期权引擎存在时使用；不存在时仍允许股票 Scan 正常运行
try:
    from scan_us_option_engine import append_option_strategy
except Exception:
    append_option_strategy = None

# ==================== 环境检查 ====================
TARGET_MODEL = "claude-opus-4-8"
TARGET_REGION = "美国市场"
DEFAULT_STOP_LOSS_PCT = -5.0
ATR_STOP_MULTIPLIER = 2.0
ATR_STOP_FLOOR_PCT = 3.0
ATR_STOP_CEIL_PCT = 12.0
REGIME_GATE_VERSION = "2026-08-31-US"

SUPER_ADMIN = os.environ.get("TARGET_EMAILS")
if not SUPER_ADMIN:
    print("致命错误：未检测到 TARGET_EMAILS！")
    sys.exit(1)

_missing_env = [k for k in ("CLAWSOCKET_API_KEY", "CLAWSOCKET_BASE_URL") if not os.environ.get(k)]
if _missing_env:
    print(f"致命错误：未检测到环境变量 {', '.join(_missing_env)}！")
    sys.exit(1)

# ==================== 美东时间 ====================
US_TZ = datetime.timezone(datetime.timedelta(hours=-4))

def get_us_time():
    return datetime.datetime.now(US_TZ)

def today_us_str():
    return get_us_time().strftime("%Y-%m-%d")

if get_us_time().weekday() >= 5:
    print(f"[{get_us_time()}] 周末休市，脚本自动跳过。")
    sys.exit(0)

print(f"启动：宏观驱动美股扫描引擎 | 引擎: {TARGET_MODEL}")

# ==================== 版本标记 ====================
def update_version_marker():
    version_file = "scan_version.txt"
    try:
        with open("scan.py", "rb") as f:
            current_hash = hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        print(f"⚠️ 版本标记读取失败: {e}")
        return

    old_hash = None
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                old_hash = content.split(",")[0]
        except Exception:
            pass

    if old_hash != current_hash:
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(f"{current_hash},{today_us_str()}")
        print(f"📌 检测到 scan.py 变化，新版本起始日期: {today_us_str()}")
    else:
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                existing = f.read().strip()
            version_date = existing.split(",")[1] if "," in existing else "未知"
            print(f"📌 scan.py 版本未变，起始日期: {version_date}")
        except Exception:
            pass

update_version_marker()

# ==================== 通用网络会话 ====================
def get_robust_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        "Referer": "https://finance.yahoo.com/",
    })
    return session

# ==================== 1. 宏观新闻 ====================
def _parse_rss_date(date_str):
    if not date_str:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(str(date_str).strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(str(date_str).strip()[:19], fmt).replace(tzinfo=datetime.timezone.utc)
            except Exception:
                pass
    return None


def _news_age_tag(dt):
    if dt is None:
        return "[时间未知]"
    delta_hours = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() / 3600
    if delta_hours <= 6:
        return "[🔥今日最新-权重最高]"
    if delta_hours <= 24:
        return "[📰今日-高权重]"
    if delta_hours <= 48:
        return "[📄昨日-中等权重]"
    if delta_hours <= 72:
        return "[📑前日-低权重]"
    return None


def get_latest_macro_news():
    print("📡 [阶段1] 正在抓取 CNBC/Reuters/MarketWatch 全球财经快讯...")
    sources = [
        ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
        ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
        ("Google News Macro", "https://news.google.com/rss/search?q=Federal+Reserve+inflation+tariff+economy+markets&hl=en-US&gl=US&ceid=US:en"),
    ]
    session = get_robust_session()
    news_lines = []

    for source_name, url in sources:
        try:
            response = session.get(url, timeout=12)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for item in root.findall(".//item")[:20]:
                title = item.findtext("title", default="").strip()
                date_text = item.findtext("pubDate", default="")
                dt = _parse_rss_date(date_text)
                tag = _news_age_tag(dt)
                if not title or tag is None:
                    continue
                ts = dt.astimezone(US_TZ).strftime("%m-%d %H:%M") if dt else "时间未知"
                news_lines.append(f"{tag}[{source_name}] {ts} - {title}")
            print(f"   ✅ {source_name} 节点抓取成功")
        except Exception as e:
            print(f"   ⚠️ {source_name} 节点抓取失败: {e}")

    if not news_lines:
        return "暂无实时英文财经新闻，请基于昨收盘及底层产业逻辑进行推演。"

    # 简单去重，保留更近的
    dedup = []
    seen = set()
    for line in news_lines:
        key = re.sub(r"[^a-z0-9]+", "", line.lower())[-180:]
        if key not in seen:
            seen.add(key)
            dedup.append(line)
    print(f"✅ 盘前英文宏观新闻矩阵完成，共 {len(dedup)} 条")
    return "\n".join(dedup[:50])


def get_megacap_breaking_news():
    """Mega-Cap 新闻：优先使用 Yahoo Finance RSS headline feed，失败时安全降级。"""
    megacap = {
        "META": "Meta（AI/算力/社交）", "NVDA": "NVIDIA（GPU/AI芯片）",
        "MSFT": "Microsoft（Azure/AI）", "GOOGL": "Alphabet（云/AI）",
        "AMZN": "Amazon（AWS/AI）", "AAPL": "Apple（消费电子）",
        "TSLA": "Tesla（电动车/AI）", "AMD": "AMD（CPU/GPU）",
        "INTC": "Intel（代工/PC）", "MU": "Micron（内存/HBM）",
    }
    cutoff = time.time() - 36 * 3600
    out = []
    session = get_robust_session()

    for ticker, desc in megacap.items():
        try:
            # 首选：Yahoo Finance RSS headline feed
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
            resp = session.get(url, timeout=8)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:8]:
                title = item.findtext("title", default="").strip()
                pub = item.findtext("pubDate", default="")
                dt = _parse_rss_date(pub)
                if dt:
                    ts = dt.timestamp()
                    if ts < cutoff:
                        continue
                    pub_time = dt.astimezone(US_TZ).strftime("%m-%d %H:%M")
                else:
                    pub_time = "时间未知"
                if title:
                    out.append(f"[{ticker}/{desc}] [Yahoo] {pub_time} — {title}")
        except Exception as e:
            print(f"⚠️ {ticker} RSS 新闻抓取失败: {e}")
            # 备用：尝试 yfinance news（如果可用）
            try:
                for item in (yf.Ticker(ticker).news or [])[:5]:
                    ts = item.get("providerPublishTime", 0)
                    if ts < cutoff:
                        continue
                    title = str(item.get("title", "")).strip()
                    publisher = str(item.get("publisher", "Yahoo")).strip()
                    if title:
                        pub_time = datetime.datetime.fromtimestamp(ts, tz=US_TZ).strftime("%m-%d %H:%M")
                        out.append(f"[{ticker}/{desc}] [{publisher}] {pub_time} — {title}")
            except Exception:
                pass
    print(f"✅ Mega-Cap 公司新闻：{len(out)} 条")
    return "\n".join(out[:60])

# ==================== 2. 全球宏观市场数据 ====================
def _yf_scalar(v):
    try:
        if isinstance(v, pd.Series):
            return float(v.iloc[0])
        if isinstance(v, pd.DataFrame):
            return float(v.iloc[0, 0])
        return float(v)
    except Exception:
        return None


def get_macro_market_data():
    print("🌐 [阶段2] 正在抓取全球大宗、利率、美元替代代理和指数数据...")
    tickers = {
        "美10年国债收益率": "^TNX",
        "美5年国债收益率": "^FVX",
        "恐慌指数VIX": "^VIX",
        "黄金期货": "GC=F",
        "白银期货": "SI=F",
        "铜期货": "HG=F",
        "WTI原油期货": "CL=F",
        "布伦特原油期货": "BZ=F",
        "标普500": "^GSPC",
        "纳斯达克": "^IXIC",
        "美元指数": "DX-Y.NYB",
    }
    lines = []
    market = {}
    vix = None

    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, period="7d", progress=False, auto_adjust=False, threads=False)
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = _yf_scalar(df["Close"].iloc[-1])
            prev = _yf_scalar(df["Close"].iloc[-2]) if len(df) >= 2 else None
            if close is None:
                continue
            pct = ((close - prev) / prev * 100) if prev not in (None, 0) else None
            market[name] = {"value": close, "pct": pct, "ticker": ticker}
            pct_text = f"{pct:+.2f}%" if pct is not None else "N/A"
            lines.append(f"- {name} ({ticker}): {close:.4f} | 变动 {pct_text}")
            if ticker == "^VIX":
                vix = close
        except Exception as e:
            print(f"⚠️ 宏观因子 {name} 抓取受阻: {e}")

    if vix is not None:
        if vix >= 30:
            lines.append(f"【VIX风控】VIX={vix:.2f}：极高波动环境，降低追涨突破权重。")
        elif vix >= 25:
            lines.append(f"【VIX风控】VIX={vix:.2f}：偏高波动环境，提高入场门槛。")

    return "\n".join(lines) if lines else "暂无实时宏观市场数据。"

# ==================== 3. 个股新闻 ====================
def get_stock_news(ticker, max_items=6):
    session = get_robust_session()
    urls = [
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
        f"https://news.google.com/rss/search?q={requests.utils.quote(ticker + ' stock')}&hl=en-US&gl=US&ceid=US:en",
    ]
    headlines = []
    for url in urls:
        try:
            resp = session.get(url, timeout=8)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:max_items + 5]:
                title = item.findtext("title", default="").strip()
                dt = _parse_rss_date(item.findtext("pubDate", default=""))
                tag = _news_age_tag(dt)
                if title and tag:
                    headlines.append(f"{tag}{title}")
        except Exception:
            continue
        if len(headlines) >= max_items:
            break
    # 去重
    out = []
    seen = set()
    for h in headlines:
        key = re.sub(r"[^a-z0-9]+", "", h.lower())
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out[:max_items]


def _news_worker(item):
    ticker = item["Ticker"]
    news = get_stock_news(ticker, 6)
    return ticker, (news if news else ["暂无最新新闻"])


def enrich_pool_with_news(pool):
    print(f"📰 [新闻] 并行抓取 {len(pool)} 只标的的最新新闻...")
    by_ticker = {}
    workers = min(12, max(4, len(pool)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_news_worker, item) for item in pool]
        for future in as_completed(futures):
            try:
                ticker, news = future.result()
                by_ticker[ticker] = news
            except Exception:
                pass
    for item in pool:
        item["个股新闻"] = by_ticker.get(item["Ticker"], ["暂无最新新闻"])
    with_news = sum(1 for x in pool if x.get("个股新闻") and x["个股新闻"] != ["暂无最新新闻"])
    print(f"✅ 个股新闻补充完毕：{with_news}/{len(pool)}")
    return pool

# ==================== 4. 标的池 ====================
_US_SECTOR_MAP = {
    "AAPL":"Technology","MSFT":"Technology","NVDA":"Technology","AMD":"Technology","INTC":"Technology","AVGO":"Technology","QCOM":"Technology","TXN":"Technology","MU":"Technology","AMAT":"Technology","LRCX":"Technology","KLAC":"Technology","MRVL":"Technology","ON":"Technology","PLTR":"Technology","PANW":"Technology","CRWD":"Technology","ZS":"Technology","FTNT":"Technology","DDOG":"Technology","CRM":"Technology","ORCL":"Technology","SNOW":"Technology","NOW":"Technology","ARM":"Technology","SMCI":"Technology",
    "META":"Communication","GOOGL":"Communication","GOOG":"Communication","NFLX":"Communication","DIS":"Communication","T":"Communication","VZ":"Communication",
    "AMZN":"Consumer Discretionary","TSLA":"Consumer Discretionary","HD":"Consumer Discretionary","MCD":"Consumer Discretionary","NKE":"Consumer Discretionary","BKNG":"Consumer Discretionary",
    "WMT":"Consumer Staples","COST":"Consumer Staples","PG":"Consumer Staples","KO":"Consumer Staples","PEP":"Consumer Staples",
    "JPM":"Financials","BAC":"Financials","WFC":"Financials","GS":"Financials","MS":"Financials","V":"Financials","MA":"Financials","PYPL":"Financials","COIN":"Financials",
    "LLY":"Healthcare","JNJ":"Healthcare","UNH":"Healthcare","MRK":"Healthcare","ABBV":"Healthcare","PFE":"Healthcare","AMGN":"Healthcare","GILD":"Healthcare","MRNA":"Healthcare","REGN":"Healthcare","VRTX":"Healthcare",
    "GE":"Industrials","HON":"Industrials","CAT":"Industrials","RTX":"Industrials","LMT":"Industrials","BA":"Industrials","NOC":"Industrials","GD":"Industrials",
    "XOM":"Energy","CVX":"Energy","COP":"Energy","SLB":"Energy","OXY":"Energy",
    "LIN":"Materials","NEM":"Materials","FCX":"Materials",
    "AMT":"Real Estate","PLD":"Real Estate","EQIX":"Real Estate",
    "NEE":"Utilities","DUK":"Utilities","POWL":"Utilities","VRT":"Utilities","VST":"Utilities",
}


def get_scan_pool():
    print("🔍 [阶段3] 正在获取 S&P500 + Nasdaq100 + Dow 标的池并按成交量取 Top300...")
    session = get_robust_session()

    def fetch(url):
        try:
            html_text = session.get(url, timeout=15).text
            tables = pd.read_html(io.StringIO(html_text))
            for df in tables:
                cols = [str(c) for c in df.columns]
                sym_col = next((c for c in df.columns if str(c) in ["Symbol", "Ticker", "Ticker symbol"]), None)
                name_col = next((c for c in df.columns if str(c) in ["Security", "Company", "Name"]), None)
                if sym_col is not None and name_col is not None:
                    return {str(s).replace(".", "-"): str(n) for s, n in zip(df[sym_col], df[name_col])}
        except Exception as e:
            print(f"⚠️ 维基抓取失败 {url}: {e}")
        return {}

    all_tickers = {}
    for url in [
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "https://en.wikipedia.org/wiki/Nasdaq-100",
        "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
    ]:
        all_tickers.update(fetch(url))

    if not all_tickers:
        print("⚠️ 维基百科受限，使用备用核心池")
        return {"NVDA":"NVIDIA","AAPL":"Apple","MSFT":"Microsoft","AMZN":"Amazon","META":"Meta","TSLA":"Tesla","GOOGL":"Alphabet"}

    tickers = list(all_tickers)
    try:
        data = yf.download(tickers, period="5d", group_by="ticker", auto_adjust=True, progress=False, threads=True)
    except Exception as e:
        print(f"⚠️ 批量成交量下载失败：{e}")
        return dict(list(all_tickers.items())[:300])

    vols = {}
    for t in tickers:
        try:
            if len(tickers) == 1:
                val = data["Volume"].iloc[-1]
            else:
                val = data[t]["Volume"].iloc[-1]
            val = _yf_scalar(val)
            if val is not None and val > 0:
                vols[t] = val
        except Exception:
            continue

    top300 = pd.Series(vols).nlargest(300).index.tolist()
    result = {t: all_tickers[t] for t in top300}
    print(f"✅ 标的池完成：{len(result)} 只")
    return result

# ==================== 4.5 基本面估值 ====================
def _safe_info_float(info, *keys):
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


def _fetch_fundamental_one(ticker):
    """轻量读取估值指标；失败只返回缺失，不影响主扫描。"""
    try:
        info = yf.Ticker(ticker).info
        return ticker, {
            "PE_TTM": _safe_info_float(info, "trailingPE"),
            "PE_Forward": _safe_info_float(info, "forwardPE"),
            "EPS_TTM": _safe_info_float(info, "trailingEps", "epsTrailingTwelveMonths"),
            "PB": _safe_info_float(info, "priceToBook"),
            "EPS_Forward": _safe_info_float(info, "epsForward"),
            "Earnings_Growth": _safe_info_float(info, "earningsGrowth"),
        }
    except Exception as e:
        return ticker, {"error": str(e)}


def enrich_pool_with_fundamentals(pool_data, limit=80):
    """
    在技术筛选之后补充 PE / EPS / PB。
    只对技术面最强的一小部分调用 yfinance info，避免 Top300 逐只请求过慢。
    """
    if not pool_data:
        return pool_data

    ranked = sorted(pool_data, key=lambda x: x.get("技术评分", 0), reverse=True)
    targets = ranked[:max(20, min(limit, len(ranked)))]
    fund_map = {}
    workers = min(10, max(4, len(targets)))
    print(f"💰 [估值] 并行获取 {len(targets)} 只技术候选的 PE/EPS/PB...")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_fetch_fundamental_one, x["Ticker"]) for x in targets]
        for future in as_completed(futures):
            try:
                ticker, data = future.result()
                fund_map[ticker] = data
            except Exception:
                pass

    # 先写入原始指标，再计算行业内相对估值评分
    by_sector = {}
    for item in pool_data:
        t = item["Ticker"]
        d = fund_map.get(t, {})
        for k in ("PE_TTM", "PE_Forward", "EPS_TTM", "EPS_Forward", "PB", "Earnings_Growth"):
            item[k] = d.get(k)
        sector = _US_SECTOR_MAP.get(t, "Other")
        by_sector.setdefault(sector, []).append(item)

    for sector_items in by_sector.values():
        pe_vals = [x["PE_Forward"] for x in sector_items if isinstance(x.get("PE_Forward"), (int,float)) and x["PE_Forward"] > 0]
        pb_vals = [x["PB"] for x in sector_items if isinstance(x.get("PB"), (int,float)) and x["PB"] > 0]
        pe_ttm_vals = [x["PE_TTM"] for x in sector_items if isinstance(x.get("PE_TTM"), (int,float)) and x["PE_TTM"] > 0]
        pe_med = float(pd.Series(pe_vals).median()) if pe_vals else None
        pb_med = float(pd.Series(pb_vals).median()) if pb_vals else None
        pe_ttm_med = float(pd.Series(pe_ttm_vals).median()) if pe_ttm_vals else None

        for item in sector_items:
            fs = 0
            labels = []
            eps = item.get("EPS_TTM")
            pe_f = item.get("PE_Forward")
            pe_t = item.get("PE_TTM")
            pb = item.get("PB")
            eg = item.get("Earnings_Growth")

            if isinstance(eps, (int,float)) and eps > 0:
                fs += 5; labels.append("EPS盈利")
            elif isinstance(eps, (int,float)) and eps < 0:
                fs -= 4; labels.append("EPS为负")

            if isinstance(pe_f, (int,float)) and pe_f > 0:
                if pe_med is not None and pe_f <= pe_med * 1.15:
                    fs += 5; labels.append("远期PE低于行业中枢")
                elif pe_f <= 25:
                    fs += 3; labels.append("远期PE尚可")
                elif pe_f > 45:
                    fs -= 3; labels.append("远期PE偏高")
            
            if isinstance(pb, (int,float)) and pb > 0:
                if pb_med is not None and pb <= pb_med * 1.15:
                    fs += 4; labels.append("PB低于行业中枢")
                elif pb > 12:
                    fs -= 2; labels.append("PB偏高")

            if isinstance(pe_t, (int,float)) and pe_t > 0 and pe_ttm_med is not None and pe_t <= pe_ttm_med * 1.15:
                fs += 3; labels.append("TTM PE合理")
            if isinstance(eg, (int,float)) and eg > 0.10:
                fs += 2; labels.append("盈利增长>10%")

            item["估值评分"] = int(max(0, min(20, fs)))
            item["估值结论"] = "、".join(labels) if labels else "估值数据不足/偏贵待核实"
            item["综合基础评分"] = int(item.get("技术评分", 0)) + item["估值评分"]

    print("✅ 估值补充完成：PE / EPS / PB 已纳入候选池")
    return pool_data


# ==================== 5. K线与技术指标 ====================
def get_kline_data(ticker):
    for attempt in range(3):
        try:
            df = yf.download(ticker, period="6mo", progress=False, auto_adjust=True, threads=False)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.index.name = "Date"
                return df
        except Exception:
            time.sleep(1.0 + attempt)
    return pd.DataFrame()


def build_stock_pool(tickers):
    pool = []
    print(f"📈 [技术面] 计算 {len(tickers)} 只标的日线/周线指标...")
    for ticker, name in tickers.items():
        try:
            df = get_kline_data(ticker)
            if df is None or df.empty or len(df) < 40:
                continue

            macd_df = ta.macd(df["Close"])
            rsi_s = ta.rsi(df["Close"], length=14)
            ma20_s = ta.sma(df["Close"], length=20)
            atr_s = ta.atr(df["High"], df["Low"], df["Close"], length=14)
            df = df.copy()
            df["MACDh"] = macd_df.iloc[:, 1]
            df["RSI"] = rsi_s
            df["MA20"] = ma20_s
            df["ATR"] = atr_s
            df = df.dropna()
            if len(df) < 10:
                continue

            latest, prev, prev2 = df.iloc[-1], df.iloc[-2], df.iloc[-3]
            h_last = float(latest["MACDh"])
            h_prev = float(prev["MACDh"])
            h_prev2 = float(prev2["MACDh"])
            macd_line = macd_df.iloc[:, 0].reindex(df.index).dropna()
            signal_line = macd_df.iloc[:, 2].reindex(df.index).dropna()
            macd_cross = bool(float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) and float(macd_line.iloc[-2]) <= float(signal_line.iloc[-2])) if len(macd_line) >= 2 and len(signal_line) >= 2 else False
            macd_green_shrink = bool(h_last < 0 and h_last > h_prev and h_prev < h_prev2)

            daily_v = bool(h_prev2 > h_prev and h_prev < h_last)
            bias = ((float(latest["Close"]) - float(latest["MA20"])) / float(latest["MA20"])) * 100

            # 周线
            weekly_bullish = False
            weekly_rising = False
            weekly_v = False
            try:
                dw = yf.download(ticker, period="1y", interval="1wk", progress=False, auto_adjust=True, threads=False)
                if dw is not None and not dw.empty:
                    if isinstance(dw.columns, pd.MultiIndex):
                        dw.columns = dw.columns.get_level_values(0)
                    wc = dw["Close"].astype(float).dropna()
                    if len(wc) >= 12:
                        wma5 = wc.rolling(5).mean().iloc[-1]
                        wma10 = wc.rolling(10).mean().iloc[-1]
                        wm1 = wc.ewm(span=12, adjust=False).mean()
                        wm2 = wc.ewm(span=26, adjust=False).mean()
                        wh = (wm1 - wm2 - (wm1 - wm2).ewm(span=9, adjust=False).mean()) * 2
                        weekly_rising = float(wh.iloc[-1]) > float(wh.iloc[-2])
                        weekly_bullish = bool(wma5 > wma10 and weekly_rising)
                        weekly_v = bool(len(wh) >= 3 and float(wh.iloc[-3]) > float(wh.iloc[-2]) < float(wh.iloc[-1]))
            except Exception:
                pass

            # KDJ
            closes = df["Close"].values.astype(float)
            highs = df["High"].values.astype(float)
            lows = df["Low"].values.astype(float)
            K, D = 50.0, 50.0
            j = []
            for i in range(len(closes)):
                if i < 8:
                    j.append(3*K - 2*D)
                    continue
                h9 = max(highs[i-8:i+1])
                l9 = min(lows[i-8:i+1])
                rsv = (closes[i] - l9) / (h9 - l9 + 1e-9) * 100
                K = 2/3*K + 1/3*rsv
                D = 2/3*D + 1/3*K
                j.append(3*K - 2*D)
            j_last, j_prev, j_prev2 = j[-1], j[-2], j[-3]

            vol = df["Volume"].values.astype(float)
            avg5 = float(pd.Series(vol[:-1]).tail(5).mean()) if len(vol) >= 6 else 0
            vol_ratio = float(vol[-1] / (avg5 + 1e-9)) if avg5 > 0 else 1.0

            # 蜡烛形态
            opens = df["Open"].values.astype(float)
            o, c = opens[-1], closes[-1]
            o1, c1 = opens[-2], closes[-2]
            h, l = highs[-1], lows[-1]
            body = abs(c - o)
            rng = h - l + 1e-9
            lower = min(o, c) - l
            upper = h - max(o, c)
            patterns = []
            if c1 < o1 and c > o and o <= c1 and c >= o1:
                patterns.append("看涨吞没")
            if body/rng < 0.35 and lower >= 2*body and upper <= body*0.5:
                patterns.append("锤子线")
            if c1 < o1 and c > o and o < c1 and c > (o1+c1)/2 and c < o1:
                patterns.append("刺穿线")
            if len(opens) >= 3:
                o2, c2 = opens[-3], closes[-3]
                if c2 < o2 and abs(c2-o2) > rng*0.3 and abs(c1-o1) < abs(c2-o2)*0.4 and c > o and c > (o2+c2)/2:
                    patterns.append("启明星")

            pool.append({
                "Ticker": ticker,
                "ts_code": ticker,
                "Name": name,
                "Price": round(float(latest["Close"]), 2),
                "Open_Price": round(float(latest["Open"]), 2),
                "RSI": round(float(latest["RSI"]), 1),
                "ATR_Pct": round(float(latest["ATR"]) / float(latest["Close"]) * 100, 2) if float(latest["Close"]) else 5.0,
                "乖离率(%)": round(bias, 2),
                "MACD趋势": "走强" if h_last > h_prev else "走弱",
                "MACD_HIST_LAST": round(h_last, 4),
                "MACD_HIST_PREV": round(h_prev, 4),
                "MACD金叉": macd_cross,
                "MACD绿柱缩短": macd_green_shrink,
                "周线共振": weekly_bullish,
                "周线MACD上升": weekly_rising,
                "周线MACD_V型反转": weekly_v,
                "日线MACD上升": h_last > h_prev,
                "日线MACD_V型反转": daily_v,
                "KDJ_J": round(float(j_last), 2),
                "KDJ_J回升": bool(j_last < 80 and j_last > j_prev and j_prev <= j_prev2),
                "KDJ_J超卖": bool(j_prev2 < 20),
                "量能放大": bool(avg5 > 0 and vol[-1] >= avg5 * 1.3),
                "量比": round(vol_ratio, 2),
                "看涨形态": patterns,
            })
        except Exception:
            continue
    print(f"✅ 技术面完成：{len(pool)} 只")
    return pool

# ==================== 6. 技术评分 ====================
def check_period_resonance(stock):
    if not stock.get("日线MACD上升") or not stock.get("周线MACD上升"):
        return False, []
    valid = ["看涨吞没", "启明星", "刺穿线", "锤子线"]
    matched = [p for p in stock.get("看涨形态", []) if p in valid]
    return bool(matched), matched


def screen_technical_setups(pool_data):
    sector_groups = {}
    for stock in pool_data:
        score = 0
        reasons = []
        resonance, patterns = check_period_resonance(stock)
        stock["周期共振"] = resonance
        stock["共振形态"] = patterns

        h = stock.get("MACD_HIST_LAST", 0)
        hp = stock.get("MACD_HIST_PREV", 0)
        if stock.get("MACD金叉"):
            if h < -0.5:
                score += 18; reasons.append(f"MACD零轴下金叉({h:.2f})(+18)")
            elif abs(h) <= 0.5:
                score += 14; reasons.append(f"MACD零轴附近金叉({h:.2f})(+14)")
            else:
                score += 6; reasons.append(f"⚠️MACD高位金叉({h:.2f})(+6)")
        elif stock.get("MACD绿柱缩短"):
            score += 12 if h < 0 and abs(h) < abs(hp)*0.85 else 8
            reasons.append("MACD绿柱快速收敛" if score >= 12 else "MACD绿柱缩短")
        elif stock.get("MACD趋势") == "走强" and h > 0:
            score += 2 if h > 3 else 4
            reasons.append("MACD红柱走强")

        j = stock.get("KDJ_J", 50)
        if stock.get("KDJ_J回升"):
            if stock.get("KDJ_J超卖") or j < 20:
                score += 10; reasons.append(f"KDJ超卖回升J={j:.0f}(+10)")
            elif j < 50:
                score += 7; reasons.append(f"KDJ低位回升J={j:.0f}(+7)")
            else:
                score += 3; reasons.append(f"KDJ中位回升J={j:.0f}(+3)")

        vr = stock.get("量比", 1.0)
        if stock.get("量能放大"):
            score += 10 if vr >= 2 else 7
            reasons.append(f"量比{vr:.1f}倍放量")

        if stock.get("看涨形态"):
            score += max({"看涨吞没":5,"启明星":5,"刺穿线":4,"锤子线":3}.get(p,2) for p in stock["看涨形态"])
            reasons.append("/".join(stock["看涨形态"]))

        if stock.get("周线共振"):
            score = min(int(score * 1.25), 40)
            reasons.append("✅周日共振×1.25")
        elif score > 0:
            score = int(score * 0.6)
            reasons.append("⚠️仅日线×0.6")

        if stock.get("日线MACD_V型反转"):
            score = min(score + 8, 40); reasons.append("日线V型反转")
        if stock.get("周线MACD_V型反转"):
            score = min(score + 4, 40); reasons.append("周线V型反转")
        if resonance:
            score = min(score + 15, 40); reasons.append("🔥周期共振(+15)")

        stock["技术评分"] = min(score, 40)
        stock["技术信号"] = reasons
        sector = _US_SECTOR_MAP.get(stock["Ticker"], "Other")
        sector_groups.setdefault(sector, []).append({"名称":stock["Name"],"代码":stock["Ticker"],"技术评分":score,"技术信号":reasons})

    print("📊 [技术筛选] 技术评分 Top10：")
    for s in sorted(pool_data, key=lambda x: x.get("技术评分",0), reverse=True)[:10]:
        if s.get("技术评分",0) > 0:
            print(f"   {s['Name']}({s['Ticker']}) {s['技术评分']}/40 | 周日共振={'是' if s.get('周线共振') else '否'}")

    return {k: sorted(v, key=lambda x: x["技术评分"], reverse=True) for k,v in sector_groups.items()}


# ==================== 6.5 重要人物讲话与宏观预期变化 ====================
def _rss_search_google(query, max_items=8):
    """通过 Google News RSS 抓取指定人物/政策关键词的近期新闻；503时重试，失败时安全降级。"""
    session = get_robust_session()
    q = requests.utils.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    out = []
    last_err = None
    for attempt in range(2):  # 503 时重试 1 次
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for item in root.findall('.//item')[:max_items * 2]:
                title = item.findtext('title', default='').strip()
                pub = item.findtext('pubDate', default='')
                dt = _parse_rss_date(pub)
                tag = _news_age_tag(dt)
                if not title or tag is None:
                    continue
                ts = dt.astimezone(US_TZ).strftime('%m-%d %H:%M') if dt else '时间未知'
                out.append((dt, f"{tag}[Google News] {ts} - {title}"))
            break  # 成功则跳出重试
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(2)  # 503 时等待 2 秒后重试
    if not out and last_err:
        print(f"   ⚠️ Google News 查询失败 {query}: {last_err}")
    out.sort(key=lambda x: x[0] or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), reverse=True)
    return [x[1] for x in out[:max_items]]


def get_key_people_policy_news(macro_news_text=""):
    """
    重要人物/政策预期监控：重点覆盖 Fed 官员、特朗普及市场高度敏感政策表述。
    不直接把人物名字当成利空；真正的方向判断交给 Regime Gate + AI。
    Google News 失败时，从已抓取的宏观新闻中过滤备用。
    """
    print("🎙️ [阶段2.4] 正在抓取重要人物讲话与政策预期变化...")
    queries = [
        "Kevin Warsh Federal Reserve rate inflation speech",
        "Jerome Powell Federal Reserve speech rates inflation",
        "Christopher Waller Federal Reserve rate speech",
        "Michelle Bowman Federal Reserve rate speech",
        "Trump tariffs inflation Federal Reserve interest rates",
        "Federal Reserve officials hawkish dovish September rate decision",
    ]
    rows = []
    seen = set()
    for q in queries:
        for line in _rss_search_google(q, max_items=6):
            key = re.sub(r"[^a-z0-9]+", "", line.lower())
            if key in seen:
                continue
            seen.add(key)
            rows.append(line)
        time.sleep(1.0)  # 增加间隔到 1 秒，减少 503 概率

    # 如果 Google News 全部失败，从已抓取的宏观新闻中过滤备用
    if not rows and macro_news_text:
        print("   🔄 Google News 全部失败，从宏观新闻中过滤人物讲话...")
        priority_terms = ("warsh", "powell", "waller", "bowman", "federal reserve", "rate", "inflation", "tariff", "hawkish", "dovish")
        for line in macro_news_text.split("\n"):
            line_lower = line.lower()
            if any(t in line_lower for t in priority_terms):
                key = re.sub(r"[^a-z0-9]+", "", line_lower)
                if key not in seen:
                    seen.add(key)
                    rows.append(line)

    # 优先保留高信息密度条目
    priority_terms = ("warsh", "powell", "waller", "bowman", "federal reserve", "rate", "inflation", "tariff", "hawkish", "dovish")
    rows.sort(key=lambda x: sum(t in x.lower() for t in priority_terms), reverse=True)
    rows = rows[:50]
    print(f"✅ 重要人物讲话监控完成：{len(rows)} 条")
    return "\n".join(rows) if rows else "暂无重要人物最新讲话/政策预期新闻。"


# ==================== 6.6 美联储关键经济数据（无付费 API 依赖） ====================

    """BLS 公共 API 作为 CPI/失业率等 FRED 失败时的备用数据源。增加重试。"""
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    payload = json.dumps({
        "seriesid": [series_id],
        "startyear": str(datetime.datetime.now().year - 2),
        "endyear": str(datetime.datetime.now().year),
    })
    last_err = None
    for attempt in range(2):
        try:
            resp = get_robust_session().post(url, data=payload, timeout=timeout, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            obj = resp.json()
            rows = obj.get("Results", {}).get("series", [{}])[0].get("data", [])
            parsed = []
            for row in rows:
                try:
                    period = row.get("period", "")
                    if period.startswith("M"):
                        dt = pd.Timestamp(f"{row['year']}-{period[1:]}-01")
                    else:
                        continue
                    parsed.append((dt, float(row["value"])))
                except Exception:
                    continue
            if not parsed:
                return None, None, None
            parsed.sort(key=lambda x: x[0])
            dt, val = parsed[-1]
            prev = parsed[-2][1] if len(parsed) >= 2 else None
            return val, prev, dt
        except Exception as e:
            last_err = e
            time.sleep(1)
    print(f"   ⚠️ BLS {series_id} 最终失败: {last_err}")
    return None, None, None


def _fetch_yahoo_scalar(ticker, timeout=8):
    """Yahoo 作为利率/指数的轻量备用源。"""
    try:
        df = yf.download(ticker, period="5d", progress=False, auto_adjust=False, threads=False)
        if df is None or df.empty:
            return None, None, None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        closes = pd.to_numeric(df['Close'], errors='coerce').dropna()
        if closes.empty:
            return None, None, None
        dt = pd.Timestamp(df.index[-1])
        val = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
        return val, prev, dt
    except Exception:
        return None, None, None


def get_us_economic_data(combined_news_text=""):
    """
    美国经济数据获取 —— 多层备用方案：
    1. 利率：Yahoo Finance（首选，<3秒）
    2. CPI/核心CPI/失业率：FRED → BLS API → BLS 网页 → Google News 提取
    3. 核心PCE：FRED → Google News 提取
    4. 联邦基金利率：Yahoo ^IRX → New York Fed
    每层失败立即进入下一层，不阻塞主流程。
    """
    print("📊 [阶段2.5] 正在抓取美国关键经济数据（多层备用方案）...")
    data = {}
    lines = []

    # ===== 1. 利率数据：Yahoo Finance =====
    yahoo_rates = {
        "10Y国债": "^TNX",
        "5Y国债": "^FVX",
        "13周国债": "^IRX",
    }
    for label, ticker in yahoo_rates.items():
        val, prev, dt = _fetch_yahoo_scalar(ticker)
        if val is not None:
            data[label] = {"value": val, "prev": prev, "date": dt.strftime('%Y-%m-%d'), "source": "Yahoo Finance"}
            lines.append(f"- {label}：{val:.3f}%（Yahoo Finance，数据期 {dt.strftime('%Y-%m-%d')}）")
            print(f"   ✅ {label}: Yahoo Finance {val:.3f}%")

    # ===== 2. CPI / 核心CPI / 失业率：多层备用 =====
    # 2a. FRED 快速尝试（3秒超时）
    fred_map = {
        "CPI指数": "CPIAUCSL",
        "核心CPI指数": "CPILFESL",
        "失业率": "UNRATE",
    }
    fred_missing = {}
    for label, sid in fred_map.items():
        result = _quick_fred(sid)
        if result:
            val, date, df = result["value"], result["date"], result["df"]
            item = {"value": val, "date": date, "source": "FRED"}
            if sid in {"CPIAUCSL", "CPILFESL"} and len(df) >= 13:
                prev12 = float(df.iloc[-13][sid])
                yoy = (val / prev12 - 1) * 100 if prev12 else None
                item["yoy"] = yoy
                if yoy is not None:
                    lines.append(f"- {label}：{yoy:.2f}% YoY（FRED，数据期 {date}）")
                else:
                    lines.append(f"- {label}：指数 {val:.3f}（FRED，数据期 {date}）")
            else:
                lines.append(f"- {label}：{val:.3f}（FRED，数据期 {date}）")
            data[label] = item
            print(f"   ✅ {label}: FRED 成功")
        else:
            fred_missing[label] = sid
            print(f"   ⏭️ {label}: FRED 失败，进入 BLS 备用")

    # 2b. BLS API 备用（仅对 FRED 失败的项）
    bls_map = {
        "CPI指数": "CUUR0000SA0",
        "核心CPI指数": "CUSR0000SA0L1E",
        "失业率": "LNS14000000",
    }
    bls_missing = {}
    for label, sid in fred_missing.items():
        if label in bls_map:
            val, prev, dt = _fetch_bls_api(bls_map[label])
            if val is not None:
                item = {"value": val, "date": dt.strftime('%Y-%m-%d'), "source": "BLS API", "prev": prev}
                if label in {"CPI指数", "核心CPI指数"}:
                    # BLS 返回的是指数值，尝试从网页获取同比
                    yoy = _fetch_bls_yoy_from_web(label)
                    if yoy is not None:
                        item["yoy"] = yoy
                        lines.append(f"- {label}：{yoy:.2f}% YoY（BLS API+网页，数据期 {dt.strftime('%Y-%m-%d')}）")
                    else:
                        lines.append(f"- {label}：指数 {val:.3f}（BLS API，数据期 {dt.strftime('%Y-%m-%d')}）")
                else:
                    lines.append(f"- {label}：{val:.3f}（BLS API，数据期 {dt.strftime('%Y-%m-%d')}）")
                data[label] = item
                print(f"   ✅ {label}: BLS API 成功")
            else:
                bls_missing[label] = sid
                print(f"   ⏭️ {label}: BLS API 失败，进入网页爬取")
        else:
            bls_missing[label] = sid

    # 2c. BLS 网页爬取（仅对 BLS API 也失败的 CPI/核心CPI/失业率）
    for label in list(bls_missing.keys()):
        if label in {"CPI指数", "核心CPI指数", "失业率"}:
            result = _fetch_bls_webpage(label)
            if result:
                data[label] = result
                if result.get("yoy") is not None:
                    lines.append(f"- {label}：{result['yoy']:.2f}% YoY（BLS 网页，数据期 {result['date']}）")
                else:
                    lines.append(f"- {label}：{result['value']:.3f}（BLS 网页，数据期 {result['date']}）")
                print(f"   ✅ {label}: BLS 网页爬取成功")
                del bls_missing[label]
            else:
                print(f"   ⏭️ {label}: BLS 网页失败，进入 Google News 提取")

    # 2d. Google News 提取（最后的备用）
    for label in list(bls_missing.keys()):
        result = _fetch_macro_from_google_news(label)
        if result:
            data[label] = result
            lines.append(f"- {label}：{result['value']:.2f}{result.get('unit', '%')}（Google News 提取，数据期 {result['date']}）")
            print(f"   ✅ {label}: Google News 提取成功")
            del bls_missing[label]
        else:
            print(f"   ❌ {label}: 所有备用源均失败")

    # ===== 3. 核心PCE：FRED → 新闻文本提取 → Google News 提取 =====
    pce_result = _quick_fred("PCEPILFE")
    if pce_result:
        val, date, df = pce_result["value"], pce_result["date"], pce_result["df"]
        item = {"value": val, "date": date, "source": "FRED"}
        if len(df) >= 13:
            prev12 = float(df.iloc[-13]["PCEPILFE"])
            yoy = (val / prev12 - 1) * 100 if prev12 else None
            item["yoy"] = yoy
            if yoy is not None:
                lines.append(f"- 核心PCE指数：{yoy:.2f}% YoY（FRED，数据期 {date}）")
            else:
                lines.append(f"- 核心PCE指数：指数 {val:.3f}（FRED，数据期 {date}）")
        else:
            lines.append(f"- 核心PCE指数：{val:.3f}（FRED，数据期 {date}）")
        data["核心PCE指数"] = item
        print(f"   ✅ 核心PCE指数: FRED 成功")
    else:
        # 备用 1: 从已抓取的新闻文本中提取
        pce_from_news = _extract_pce_from_news(combined_news_text if 'combined_news_text' in dir() else "")
        if pce_from_news:
            data["核心PCE指数"] = pce_from_news
            lines.append(f"- 核心PCE指数：{pce_from_news['value']:.2f}%（新闻文本提取，数据期 {pce_from_news['date']}）")
            print(f"   ✅ 核心PCE指数: 新闻文本提取成功")
        else:
            # 备用 2: Google News 提取
            result = _fetch_macro_from_google_news("核心PCE指数")
            if result:
                data["核心PCE指数"] = result
                lines.append(f"- 核心PCE指数：{result['value']:.2f}{result.get('unit', '%')}（Google News 提取，数据期 {result['date']}）")
                print(f"   ✅ 核心PCE指数: Google News 提取成功")
            else:
                print(f"   ❌ 核心PCE指数: 所有备用源均失败")

    # ===== 4. 联邦基金利率：Yahoo ^IRX → New York Fed =====
    if "13周国债" not in data:
        try:
            ny_url = ("https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json?startDate="
                      + (datetime.datetime.now()-datetime.timedelta(days=10)).strftime('%Y-%m-%d')
                      + "&endDate=" + datetime.datetime.now().strftime('%Y-%m-%d'))
            resp = get_robust_session().get(ny_url, timeout=5)
            resp.raise_for_status()
            obj = resp.json()
            rows = obj.get("refRates", obj.get("rates", []))
            rows = [r for r in rows if str(r.get("type", "")).lower() in {"effr", "effective federal funds rate", ""}]
            if rows:
                r = rows[-1]
                val = r.get("percentRate", r.get("effectiveRate", r.get("rate")))
                dt = r.get("effectiveDate", r.get("date"))
                if val is not None:
                    data["联邦基金有效利率"] = {"value": float(val), "date": str(dt), "source": "New York Fed"}
                    lines.append(f"- 联邦基金有效利率：{float(val):.3f}%（New York Fed，数据期 {dt}）")
                    print(f"   ✅ 联邦基金利率: New York Fed 成功")
        except Exception as e:
            print(f"   ⏭️ New York Fed EFFR 跳过: {e}")

    # ===== 5. Regime 确认行 =====
    cpi_yoy = data.get("CPI指数", {}).get("yoy")
    core_cpi_yoy = data.get("核心CPI指数", {}).get("yoy")
    core_pce_yoy = data.get("核心PCE指数", {}).get("yoy")
    unemployment = data.get("失业率", {}).get("value")
    effr = data.get("13周国债", {}).get("value") or data.get("联邦基金有效利率", {}).get("value")
    ten_y = data.get("10Y国债", {}).get("value")

    if core_pce_yoy is not None:
        lines.append(f"【Regime确认】核心PCE同比={core_pce_yoy:.2f}%")
    if core_cpi_yoy is not None:
        lines.append(f"【Regime确认】核心CPI同比={core_cpi_yoy:.2f}%")
    if cpi_yoy is not None:
        lines.append(f"【Regime确认】CPI同比={cpi_yoy:.2f}%")
    if unemployment is not None:
        lines.append(f"【Regime确认】失业率={unemployment:.1f}%")
    if effr is not None:
        lines.append(f"【Regime确认】有效联邦基金利率={effr:.2f}%")
    if ten_y is not None:
        lines.append(f"【Regime确认】10Y国债收益率={ten_y:.2f}%")

    if not lines:
        return "暂无结构化美国宏观经济数据。", data
    print(f"✅ 美国经济数据抓取完成：{len(data)} 项（多层备用）")
    return "\n".join(lines), data


def _quick_fred(sid):
    """快速单次 FRED 获取，3秒超时，零重试。"""
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
        resp = get_robust_session().get(url, timeout=3)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        if 'observation_date' not in df.columns or sid not in df.columns:
            return None
        df['observation_date'] = pd.to_datetime(df['observation_date'], errors='coerce')
        df[sid] = pd.to_numeric(df[sid], errors='coerce')
        df = df.dropna(subset=['observation_date', sid]).sort_values('observation_date')
        if df.empty:
            return None
        last = df.iloc[-1]
        return {
            "value": float(last[sid]),
            "date": last['observation_date'].strftime('%Y-%m-%d'),
            "df": df
        }
    except Exception:
        return None


def _fetch_bls_api(series_id, timeout=10):
    """BLS 公共 API。之前日志证明在此网络环境下可用。"""
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    payload = json.dumps({
        "seriesid": [series_id],
        "startyear": str(datetime.datetime.now().year - 2),
        "endyear": str(datetime.datetime.now().year),
    })
    try:
        resp = get_robust_session().post(url, data=payload, timeout=timeout, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        obj = resp.json()
        rows = obj.get("Results", {}).get("series", [{}])[0].get("data", [])
        parsed = []
        for row in rows:
            try:
                period = row.get("period", "")
                if period.startswith("M"):
                    dt = pd.Timestamp(f"{row['year']}-{period[1:]}-01")
                else:
                    continue
                parsed.append((dt, float(row["value"])))
            except Exception:
                continue
        if not parsed:
            return None, None, None
        parsed.sort(key=lambda x: x[0])
        dt, val = parsed[-1]
        prev = parsed[-2][1] if len(parsed) >= 2 else None
        return val, prev, dt
    except Exception:
        return None, None, None


def _fetch_bls_yoy_from_web(label):
    """从 BLS CPI 首页爬取最新同比数据。"""
    try:
        session = get_robust_session()
        resp = session.get("https://www.bls.gov/cpi/", timeout=8)
        resp.raise_for_status()
        text = resp.text
        if label == "CPI指数":
            # 查找 "rose X.X percent over the last 12 months" 或类似模式
            m = re.search(r"CPI for All Urban Consumers.*?rose [\\d.]+ percent.*?over the last 12 months.*?up ([\\d.]+) percent", text, re.S|re.I)
            if m:
                return float(m.group(1))
            m = re.search(r"All items.*?([\\d.]+)%", text)
            if m:
                return float(m.group(1))
        elif label == "核心CPI指数":
            m = re.search(r"all items less food and energy.*?up ([\\d.]+) percent", text, re.S|re.I)
            if m:
                return float(m.group(1))
            m = re.search(r"less food and energy.*?([\\d.]+)%", text)
            if m:
                return float(m.group(1))
    except Exception:
        pass
    return None


def _fetch_bls_webpage(label):
    """从 BLS 网页爬取 CPI/失业率数据。"""
    try:
        session = get_robust_session()
        if label == "CPI指数":
            resp = session.get("https://www.bls.gov/cpi/", timeout=8)
            resp.raise_for_status()
            text = resp.text
            # 提取 All items 12-month percent change
            m = re.search(r"All items.*?([\\d.]+)%", text)
            if m:
                yoy = float(m.group(1))
                # 尝试提取日期
                dm = re.search(r"(\w+ \d{4})", text)
                date_str = dm.group(1) if dm else "未知"
                return {"value": yoy, "yoy": yoy, "date": date_str, "source": "BLS 网页"}
        elif label == "核心CPI指数":
            resp = session.get("https://www.bls.gov/cpi/", timeout=8)
            resp.raise_for_status()
            text = resp.text
            m = re.search(r"less food and energy.*?up ([\\d.]+) percent", text, re.S|re.I)
            if m:
                yoy = float(m.group(1))
                dm = re.search(r"(\w+ \d{4})", text)
                date_str = dm.group(1) if dm else "未知"
                return {"value": yoy, "yoy": yoy, "date": date_str, "source": "BLS 网页"}
        elif label == "失业率":
            resp = session.get("https://www.bls.gov/web/empsit/cpseea01.htm", timeout=8)
            resp.raise_for_status()
            text = resp.text
            # 失业率通常在表格中
            m = re.search(r"Unemployment rate.*?([\\d.]+)", text, re.S|re.I)
            if m:
                val = float(m.group(1))
                dm = re.search(r"(\w+ \d{4})", text)
                date_str = dm.group(1) if dm else "未知"
                return {"value": val, "date": date_str, "source": "BLS 网页"}
            # 备用：从 BLS 首页 Latest Numbers 提取
            resp = session.get("https://www.bls.gov/", timeout=8)
            text = resp.text
            m = re.search(r"Unemployment Rate:\\s*([\\d.]+)%", text)
            if m:
                val = float(m.group(1))
                return {"value": val, "date": "最新", "source": "BLS 首页"}
    except Exception:
        pass
    return None


def _extract_pce_from_news(news_text):
    """从已抓取的新闻文本中提取核心PCE数据。"""
    if not news_text:
        return None
    patterns = [
        r"core\s*PCE.*?([\d.]+)\s*%",
        r"PCE\s*price\s*index.*?([\d.]+)\s*%",
        r"personal\s*consumption\s*expenditures.*?([\d.]+)\s*%",
        r"core\s*personal\s*consumption.*?([\d.]+)\s*%",
        r"excluding\s*food\s*and\s*energy.*?([\d.]+)\s*%",
    ]
    for pattern in patterns:
        m = re.search(pattern, news_text, re.I)
        if m:
            val = float(m.group(1))
            if 0 <= val <= 15:  # 合理性检查
                return {"value": val, "date": "最新", "source": "新闻文本提取", "unit": "%"}
    return None


def _fetch_macro_from_google_news(label):
    """从 Google News 搜索提取最新宏观经济数据数值。"""
    queries = {
        "CPI指数": "US CPI inflation rate latest 2026",
        "核心CPI指数": "US core CPI inflation rate latest 2026",
        "核心PCE指数": "US core PCE inflation rate latest 2026",
        "失业率": "US unemployment rate latest 2026",
    }
    query = queries.get(label)
    if not query:
        return None
    try:
        session = get_robust_session()
        q = requests.utils.quote(query)
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        resp = session.get(url, timeout=8)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        # 遍历前 10 条新闻，尝试提取数值
        patterns = {
            "CPI指数": [
                r"CPI.*?([\\d.]+)\\s*%",
                r"inflation.*?([\\d.]+)\\s*%",
                r"consumer price.*?([\\d.]+)\\s*%",
            ],
            "核心CPI指数": [
                r"core CPI.*?([\\d.]+)\\s*%",
                r"core inflation.*?([\\d.]+)\\s*%",
                r"excluding food and energy.*?([\\d.]+)\\s*%",
            ],
            "核心PCE指数": [
                r"core PCE.*?([\\d.]+)\\s*%",
                r"PCE.*?([\\d.]+)\\s*%",
            ],
            "失业率": [
                r"unemployment rate.*?([\\d.]+)\\s*%",
                r"jobless rate.*?([\\d.]+)\\s*%",
                r"unemployment.*?([\\d.]+)\\s*%",
            ],
        }
        for item in root.findall(".//item")[:10]:
            title = item.findtext("title", default="").strip()
            desc = item.findtext("description", default="").strip()
            combined = f"{title} {desc}".lower()
            for pattern in patterns.get(label, []):
                m = re.search(pattern, combined, re.I)
                if m:
                    val = float(m.group(1))
                    # 合理性检查
                    if label == "失业率" and not (2 <= val <= 15):
                        continue
                    if label in {"CPI指数", "核心CPI指数", "核心PCE指数"} and not (0 <= val <= 15):
                        continue
                    pub = item.findtext("pubDate", default="")
                    dt = _parse_rss_date(pub)
                    date_str = dt.strftime("%Y-%m-%d") if dt else "未知"
                    return {
                        "value": val,
                        "date": date_str,
                        "source": "Google News 提取",
                        "unit": "%",
                        "raw_title": title,
                    }
    except Exception:
        pass
    return None


    """统一使用 stream，规避长请求的 SDK 超时限制。"""
    out = []
    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            out.append(text)
    return "".join(out).strip()


def _anthropic_text(response):
    """兼容新版 Claude 的 TextBlock / ThinkingBlock 返回结构。"""
    parts = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _anthropic_stream_text(client, **kwargs):
    """统一使用 stream，规避长请求的 SDK 超时限制。"""
    out = []
    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            out.append(text)
    return "".join(out).strip()


# ==================== 6.7 事件证据汇总 ====================
def build_event_evidence_text(key_people_text, economic_text, macro_market_text):
    """将人物讲话、结构化经济数据、市场价格放入同一证据层，供 Regime Gate 与 AI 共用。"""
    return (
        "【重要人物/政策讲话】\n" + str(key_people_text or "暂无") +
        "\n\n【结构化美国经济数据】\n" + str(economic_text or "暂无") +
        "\n\n【市场价格确认】\n" + str(macro_market_text or "暂无")
    )

# ==================== 7. Regime Gate ====================
def build_event_regime_gate(macro_news_text, macro_market_text, sector_text, key_people_text="", economic_text=""):
    text = f"{macro_news_text}\n{macro_market_text}\n{sector_text}\n{key_people_text}\n{economic_text}".lower()
    gate = {
        "version": REGIME_GATE_VERSION,
        "market_regime": "NEUTRAL",
        "confidence": "low",
        "hard_avoid_sectors": [],
        "watch_sectors": [],
        "buy_dip_sectors": [],
        "reasons": [],
        "event_flags": [],
    }

    hawkish_terms = [
        "kevin warsh", "warsh", "jerome powell", "powell", "waller", "bowman",
        "hawkish", "higher for longer", "rate hike", "rate hikes", "higher rates",
        "inflation remains", "tariff inflation", "加息", "偏鹰", "高利率", "通胀仍高",
    ]
    dovish_terms = [
        "rate cut", "rate cuts", "easing", "lower rates", "dovish", "disinflation",
        "降息", "偏鸽", "货币宽松", "通胀回落",
    ]
    hawkish = any(x in text for x in hawkish_terms)
    dovish = any(x in text for x in dovish_terms)

    def num(pattern):
        m = re.search(pattern, text, re.I)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None

    pce = num(r"(?:core[\s]*pce|核心pce|pce)[^0-9]{0,30}([0-9]+(?:\.[0-9]+)?)[\s]*%?")
    cpi = num(r"(?:cpi|消费者价格)[^0-9]{0,30}([0-9]+(?:\.[0-9]+)?)[\s]*%?")
    ten = num(r"(?:10y|10-year|10年|10年期)[^0-9+-]{0,30}([0-9]+(?:\.[0-9]+)?)")
    vix = num(r"(?:vix)[^0-9]{0,15}([0-9]+(?:\.[0-9]+)?)")

    hawkish_confirmed = hawkish and (pce is not None or cpi is not None or ten is not None)
    if hawkish_confirmed:
        gate["market_regime"] = "HAWKISH_REPRICING"
        gate["confidence"] = "high"
        gate["event_flags"].append("Fed高等级鹰派事件")
        gate["reasons"].append("高等级政策事件与通胀/利率信息同向")
    elif hawkish:
        gate["market_regime"] = "HAWKISH_WATCH"
        gate["confidence"] = "medium"
        gate["event_flags"].append("Fed鹰派事件待价格确认")
    elif dovish:
        gate["market_regime"] = "DOVISH_WATCH"
        gate["confidence"] = "medium"
        gate["event_flags"].append("Fed鸽派事件")

    if ten is not None and ten >= 4.50 and hawkish_confirmed:
        gate["watch_sectors"] += ["Technology", "Communication"]
        gate["reasons"].append(f"10Y={ten:.2f}偏高，成长估值压力增强")

    if vix is not None and vix >= 25:
        gate["reasons"].append(f"VIX={vix:.1f}，风险偏好偏弱")

    sector_to_us = {
        "SOXX":["Technology"], "SMH":["Technology"], "XLK":["Technology"], "ARKK":["Technology","Communication"],
        "XLB":["Materials"], "XLE":["Energy"], "XLI":["Industrials"], "XLF":["Financials"],
        "XLV":["Healthcare"], "XLY":["Consumer Discretionary"],
    }
    negative = set()
    for line in str(sector_text or "").splitlines():
        m = re.search(r"(?:📉|📈)[\s]*([A-Z]+)[\s]*:[\s]*([+-]?[0-9]+(?:\.[0-9]+)?)%", line)
        if not m:
            continue
        etf, pct = m.group(1), float(m.group(2))
        if pct <= -1.5:
            negative.update(sector_to_us.get(etf, []))

    if hawkish_confirmed:
        # 这里不是永久黑名单：只在当前事件+当前行业价格同时确认时硬回避
        for sector in ["Technology", "Communication", "Materials"]:
            if sector in negative:
                gate["hard_avoid_sectors"].append(sector)

    for sector in negative:
        if sector not in gate["hard_avoid_sectors"]:
            gate["buy_dip_sectors"].append(sector)

    # 若材料/贵金属当前下跌且鹰派高等级确认，Materials 直接进入当前日硬回避
    if hawkish_confirmed and "Materials" in negative and "Materials" not in gate["hard_avoid_sectors"]:
        gate["hard_avoid_sectors"].append("Materials")
        gate["reasons"].append("鹰派重定价+材料ETF当前走弱，禁止把商品单日上涨当作主线确认")

    for key in ("hard_avoid_sectors","watch_sectors","buy_dip_sectors"):
        gate[key] = list(dict.fromkeys(gate[key]))
    return gate


def format_event_regime_gate(gate):
    return (
        "════════════════════════════════════════\n"
        "【🚦 事件驱动 Regime Gate】\n"
        f"状态={gate.get('market_regime')} | 置信度={gate.get('confidence')}\n"
        f"硬回避={', '.join(gate.get('hard_avoid_sectors', [])) or '无'}\n"
        f"观察={', '.join(gate.get('watch_sectors', [])) or '无'}\n"
        f"BUY_DIP={', '.join(gate.get('buy_dip_sectors', [])) or '无'}\n"
        f"事件={', '.join(gate.get('event_flags', [])) or '无'}\n"
        f"原因={'; '.join(gate.get('reasons', [])) or '无'}\n"
        "历史低胜率规则不形成永久黑名单；硬回避必须依赖当前事件/宏观+当前行业价格确认。\n"
        "════════════════════════════════════════"
    )

# ==================== 8. 美股板块表现 ====================
def get_us_sector_performance():
    print("🇺🇸 [板块数据] 正在抓取美股核心行业 ETF 最新表现...")
    sector_map = {
        "SOXX":"半导体", "SMH":"半导体", "XLK":"科技", "ARKK":"创新科技",
        "XLF":"金融", "XLE":"能源", "XLV":"医疗", "XLY":"非必需消费",
        "XLI":"工业", "XLB":"材料",
    }
    results = []
    for ticker, desc in sector_map.items():
        try:
            df = yf.download(ticker, period="5d", progress=False, auto_adjust=True, threads=False)
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) < 2:
                continue
            c = _yf_scalar(df["Close"].iloc[-1])
            p = _yf_scalar(df["Close"].iloc[-2])
            if c is None or p in (None,0):
                continue
            pct = (c-p)/p*100
            sign = "📈" if pct > 0 else "📉"
            results.append(f"{sign} {ticker}: {pct:+.2f}% — {desc}")
        except Exception as e:
            print(f"⚠️ {ticker} 板块抓取失败: {e}")
    return "\n".join(results) if results else "暂无板块数据"

# ==================== 9. 新闻驱动市场信号 ====================
def analyze_market_signals(combined_news_text, client):
    if not combined_news_text or len(combined_news_text.strip()) < 50:
        return {"signals": []}
    prompt = f"""
你是顶级跨资产策略研究员。请识别新闻背后的真实结构性信号，区分 AVOID、BUY_DIP、POSITIVE_CATALYST、ROTATION、CONTRARIAN。
不要因为短期价格下跌就自动认定基本面受损；也不要因为商品短期上涨就自动认定产业链利多。

【过去36小时新闻】
{combined_news_text[:10000]}

仅输出 JSON：
{{
  "signals": [
    {{
      "type":"AVOID|BUY_DIP|POSITIVE_CATALYST|ROTATION|CONTRARIAN",
      "sector":"英文板块",
      "sector_cn":"中文板块",
      "affected_subsectors":[],
      "unaffected_subsectors":[],
      "surface_news":"",
      "real_signal":"",
      "transmission_chain":"",
      "reasoning":"",
      "actionable":"",
      "confidence":"high|medium|low",
      "duration_days":1
    }}
  ]
}}
"""
    try:
        text = _anthropic_stream_text(client, model=TARGET_MODEL, max_tokens=12000, messages=[{"role":"user","content":prompt}])
        a, b = text.find("{"), text.rfind("}")
        if a < 0 or b < 0:
            return {"signals": []}
        data = json.loads(text[a:b+1])
        signals = data.get("signals", [])
        print(f"📡 [市场信号] 识别到 {len(signals)} 个跨市场信号")
        return {"signals": signals}
    except Exception as e:
        print(f"⚠️ [市场信号] 调用失败：{e}")
        return {"signals": []}


def build_market_signal_text(analysis_result):
    signals = (analysis_result or {}).get("signals", [])
    if not signals:
        return ["【跨市场信号分析】暂无结构性信号", []]
    grouped = {}
    for s in signals:
        grouped.setdefault(s.get("type","AVOID"), []).append(s)
    sections = []
    avoid_keywords = []
    if "AVOID" in grouped:
        lines = []
        for s in grouped["AVOID"]:
            avoid_keywords += [s.get("sector",""), s.get("sector_cn","")] + s.get("affected_subsectors",[])
            lines.append(
                f"🔴 {s.get('sector_cn','')}({s.get('sector','')}) | {s.get('real_signal','')} | 传导: {s.get('transmission_chain','')} | 持续{s.get('duration_days','?')}天"
            )
        sections.append("【今日回避（AVOID）】\n" + "\n".join(lines))
    if "BUY_DIP" in grouped:
        lines = []
        for s in grouped["BUY_DIP"]:
            lines.append(f"💚 {s.get('sector_cn','')}({s.get('sector','')}) | 错杀逻辑: {s.get('real_signal','')} | 建议: {s.get('actionable','')}")
        sections.append("【逢低买入（BUY_DIP）】\n" + "\n".join(lines))
    for typ, title in [("POSITIVE_CATALYST","【正向催化】"),("ROTATION","【资金轮动】"),("CONTRARIAN","【反向机会】")]:
        if typ in grouped:
            sections.append(title + "\n" + "\n".join(f"• {s.get('sector_cn','')}：{s.get('real_signal','')} → {s.get('actionable','')}" for s in grouped[typ]))
    return ["【跨市场信号分析】\n\n" + "\n\n".join(sections), list(dict.fromkeys([x for x in avoid_keywords if x]))]

# ==================== 10. 进化规则：条件化，不永久封板 ====================
def load_conditional_evolved_rules():
    path = "evolved_rules.json"
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("active_rules", [])
        patches = data.get("prompt_patches", [])
        lines = [
            "【📈 历史绩效规则——条件化参考】",
            "过去低胜率只用于识别历史失败条件，不构成永久板块或股票黑名单。只有当前条件再次出现时才降权。",
        ]
        for rule, patch in zip(rules, patches):
            lines.append(f"- {rule.get('type','')}: {rule.get('description','')} | 证据: {rule.get('evidence','')} | 当前条件化执行: {patch}")
        return "\n".join(lines)
    except Exception as e:
        print(f"⚠️ 进化规则读取失败: {e}")
        return ""


def load_evolved_rules():
    return load_conditional_evolved_rules()

# ==================== 11. 昨日止损联动警告 ====================
def get_stop_loss_hit_warning():
    path = "trade_history.csv"
    if not os.path.exists(path):
        return ""
    try:
        df = pd.read_csv(path, keep_default_na=False)
        if "Tag" not in df.columns or "Exit_Date" not in df.columns:
            return ""
        hits = df[df["Tag"].astype(str).str.strip() == "Stop_Loss_Hit"].copy()
        if hits.empty:
            return ""
        hits = hits.sort_values("Exit_Date", ascending=False).head(5)
        details = [f"{r.get('Name',r['Ticker'])}({r['Ticker']}) @{r.get('Exit_Date','未知')}" for _,r in hits.iterrows()]
        return "⚠️ 最近止损联动警告：这些标的最近触发 Stop_Loss_Hit，今日仅作为反面案例，不自动代表未来永久回避：" + ", ".join(details)
    except Exception:
        return ""

# ==================== 12. 盘前持仓审查 ====================
def pre_scan_portfolio_review(macro_news_text, macro_market_text):
    path = "trade_history.csv"
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return set(), {}, {}
    try:
        df = pd.read_csv(path, keep_default_na=False)
    except Exception as e:
        print(f"⚠️ 读取 trade_history.csv 失败: {e}")
        return set(), {}, {}

    for col in ["Exit_Date","Exit_Price","Status","Price"]:
        if col not in df.columns:
            df[col] = "Active" if col == "Status" else ("" if col != "Price" else 0)

    # pandas 2.x 可能将混合列推断为 StringDtype；后续风控需要向 Exit_Price 写入数值，
    # 因此这里显式使用 object，避免“Invalid value ... for dtype 'str'”崩溃。
    df["Exit_Date"] = df["Exit_Date"].astype(object)
    df["Exit_Price"] = df["Exit_Price"].astype(object)
    df["Status"] = df["Status"].astype(object)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0.0).astype(object)

    active = df[df["Status"].astype(str).str.strip() == "Active"].copy()
    if active.empty:
        return set(), {}, {}

    active_tickers = active["Ticker"].astype(str).unique().tolist()
    prices = {}
    for t in active_tickers:
        try:
            info = yf.Ticker(t).fast_info
            p = info.get("last_price") or info.get("lastPrice")
            if p and float(p) > 0:
                prices[t] = round(float(p),2)
        except Exception:
            pass
    missing = [t for t in active_tickers if t not in prices]
    if missing:
        try:
            batch = yf.download(missing, period="2d", progress=False, auto_adjust=True, threads=True)
            for t in missing:
                try:
                    val = batch["Close"][t].iloc[-1] if len(missing) > 1 else batch["Close"].iloc[-1]
                    val = _yf_scalar(val)
                    if val:
                        prices[t] = round(val,2)
                except Exception:
                    pass
        except Exception:
            pass
    for t in active_tickers:
        if t not in prices:
            rr = active[active["Ticker"] == t].iloc[-1]
            prices[t] = _yf_scalar(rr.get("Price",0)) or 0

    position_lines = []
    for _, r in active.iterrows():
        t = r["Ticker"]
        news = get_stock_news(t, 4)
        position_lines.append(f"- {r.get('Name',t)}({t}) | 买入${r.get('Price','N/A')} | 现价${prices.get(t,0)} | 新闻: {' | '.join(news) if news else '无'}")

    client = anthropic.Anthropic(api_key=os.environ["CLAWSOCKET_API_KEY"], base_url=os.environ["CLAWSOCKET_BASE_URL"])
    prompt = f"""
你是美股宏观风控总监。判断当前活跃持仓是否存在真正的突发利空/逻辑证伪。
不要因为过去止损、过去低胜率就建议未来永久退出；只处理当前真实事件风险。

宏观：\n{macro_news_text[:6000]}\n\n市场：\n{macro_market_text}\n\n持仓：\n{'\n'.join(position_lines)}\n
仅输出：{{"decision":{{"TICKER":"Dropped|Active"}},"reason":"150字以内"}}
"""
    decisions = {}
    reason = ""
    try:
        txt = _anthropic_stream_text(client, model=TARGET_MODEL, max_tokens=3000, messages=[{"role":"user","content":prompt}])
        a,b = txt.find("{"), txt.rfind("}")
        obj = json.loads(txt[a:b+1])
        decisions = obj.get("decision", {})
        reason = obj.get("reason", "")
    except Exception as e:
        print(f"⚠️ 持仓风控 AI 失败: {e}")

    dropped = {}
    restricted = set(active_tickers)
    changed = False
    for idx, row in df.iterrows():
        t = row.get("Ticker")
        if row.get("Status") == "Active" and decisions.get(t) == "Dropped":
            df.at[idx,"Status"] = "Dropped"
            df.at[idx,"Exit_Date"] = today_us_str()
            exit_price = prices.get(t, row.get("Price", 0))
            try:
                exit_price = float(exit_price)
            except (TypeError, ValueError):
                exit_price = 0.0
            df.at[idx,"Exit_Price"] = exit_price
            dropped[t] = {"name":row.get("Name",t),"reason":reason or "当前事件风险"}
            changed = True
    if changed:
        df.to_csv(path, index=False, encoding="utf-8")
        print(f"🚨 持仓风控：Dropped {len(dropped)} 只")
    else:
        print("✅ 活跃持仓通过盘前风控")
    return restricted, dropped, prices

# ==================== 13. 生成 AI 报告 ====================
def generate_ai_report(pool_data, combined_news, macro_market, dropped_info=None, embargo_text="", sector_tech_data=None, event_regime_text="", event_regime=None, market_signal_text="", key_people_text="", economic_text=""):
    print("🧠 [AI] 生成美股宏观穿透报告...")
    client = anthropic.Anthropic(api_key=os.environ["CLAWSOCKET_API_KEY"], base_url=os.environ["CLAWSOCKET_BASE_URL"])
    pool_lines = []
    for x in pool_data:
        pool_lines.append(
            f"[{x['Ticker']}] {x['Name']} | ${x['Price']} | RSI:{x['RSI']} | Bias:{x['乖离率(%)']}% | MACD:{x['MACD趋势']} | KDJ:{x['KDJ_J']} | Vol:{x['量比']} | 周日共振:{'是' if x.get('周线共振') else '否'} | 技术:{x.get('技术评分',0)}/40 | 估值:{x.get('估值评分',0)}/20 | PE_TTM:{x.get('PE_TTM')} | PE_F:{x.get('PE_Forward')} | EPS:{x.get('EPS_TTM')} | PB:{x.get('PB')} | 估值结论:{x.get('估值结论','数据不足')} | 新闻:{' | '.join(x.get('个股新闻',[]))}"
        )
    evolved = load_evolved_rules()
    key_people_block = str(key_people_text or "暂无重要人物讲话数据")
    economic_block = str(economic_text or "暂无结构化美国经济数据")
    stop_warn = get_stop_loss_hit_warning()
    dropped_text = ""
    if dropped_info:
        dropped_text = "\n⚠️ 今日已因当前真实风险 Dropped：" + ", ".join(dropped_info)

    hard_avoid = ", ".join((event_regime or {}).get("hard_avoid_sectors", [])) or "无"
    prompt = f"""
【最高优先级】输出 5 只 Top1-5；若池不足5只则实际输出，禁止输出“今日无推荐”。历史低胜率不是永久黑名单。

你是顶级美股产业链+宏观事件驱动交易员。
今天是 {today_us_str()}。

【🚦事件驱动 Regime Gate】
{event_regime_text}
当前硬回避行业：{hard_avoid}

【跨市场信号】
{market_signal_text}

【宏观新闻】
{combined_news[:12000]}

【宏观市场数据】
{macro_market}

【重要人物讲话 / 政策预期】
{key_people_block}

【结构化美国经济数据】
{economic_block}

【数据可靠性纪律】FRED单项失败不得伪造数值；优先使用BLS备用或Yahoo利率代理，并标明来源。

【板块表现】
{embargo_text}

【历史规则】
{evolved}

{stop_warn}
{dropped_text}

【成交活跃 Top300 候选池】
{'\n'.join(pool_lines)}

【强制决策顺序】
1. 先 Regime Gate：高等级事件+宏观价格确认优先于单一商品方向。
2. Regime Gate 是当前交易状态，不是历史黑名单；硬回避只在当前事件+行业价格共同确认时生效。
3. 行业硬回避不得进 Top1-5；但 BUY_DIP/CONTRARIAN 可以作为观察逻辑，除非当前又出现新的基本面证伪。
4. 不能因为周线共振就忽略行业当前下跌；行业价格环境是个股技术之前的确认层。
5. 先从事件得到1-2个产业链主线，再选个股。
6. 个股新闻优先于纯技术信号做排雷。
7. RSI>70、Bias>15%、5日已大涨属于追高风险，不得无条件追涨。
8. 基本面估值必须参与最终排序：至少核对 PE(TTM/Forward)、EPS、PB；估值明显过高且盈利无法匹配时降权，便宜但基本面恶化时也不得仅凭低PE加分。
9. 股票不设固定持仓天数；只要 MA20/MA50 趋势仍在、MACD/KDJ 未同步破坏且移动止损未触发，可以继续持有，避免过早卖出。
10. 过去低胜率板块只在当前同样的失败条件重新出现时降权，不允许永久封板。
11. 高等级 Fed/Warsh 鹰派事件如果与通胀/利率数据同向，必须明确降低 Technology/Communication 等高久期资产权重；若 Materials 当前也同步大跌，则不得因为单一铜价夜盘上涨而重新推荐 Materials。

【HTML 输出格式 - 严格遵循】
从第一个字符开始必须是HTML，不要输出任何 markdown 代码块标记（如 ```html）。

<div class="header-card">
<h2>🌍 今日宏观事件与 Regime Gate</h2>
<p><b>事件主线1：</b>...</p>
<p><b>事件主线2：</b>...</p>
<p><b>Regime：</b>明确说明鹰派/鸽派/中性及是否形成行业硬回避。</p>
<p><b>今日雷区：</b>...</p>
</div>

<h2>👑 核心精选 Top 1-5</h2>

<!-- 每只标的必须用这个精确格式，Ticker 必须放在括号中 -->
<div class="top-card core-card">
<div class="top-title">1. [公司名称] ([TICKER]) | RSI:[数值] | 乖离率:[数值]%</div>
<p><span class="highlight-label bg-red">🔗 产业链逻辑:</span>...</p>
<p><span class="highlight-label bg-green">📰 个股新闻核查:</span>...</p>
<p><span class="highlight-label bg-blue">📈 技术确认:</span>...</p>
<p><span class="highlight-label bg-teal">⭐ 推荐评分:</span>评分:[XX]/100 — ...</p>
<p><span class="highlight-label bg-orange">⚠️ 动态风控:</span>持有:[趋势未破则继续] | 移动止损:[具体价格] | 依据:[MA20/MA50 + ATR + MACD/KDJ]</p>
<div><h4>🎲 美股专属期权实战策略</h4><ul><li><b>建议行权价与到期日：</b>...</li><li><b>期权组合构建：</b>...</li></ul></div>
</div>

<!-- 重复上述 div 结构至第5只，确保每只都有 class="top-card core-card" -->

<div class="compare-card">
<div class="compare-title">🎖️ 观察池 - Rank 6-12</div>
<ul>
<li>[公司名称] ([TICKER]) | 理由...</li>
<li>[公司名称] ([TICKER]) | 理由...</li>
</ul>
</div>

<div class="trap-card">
<h3>🚨 诱多对照组</h3>
<ul>
<li>[公司名称] ([TICKER]) | 风险...</li>
<li>[公司名称] ([TICKER]) | 风险...</li>
</ul>
</div>

【格式纪律】
1. 核心精选每只必须用 <div class="top-card core-card"> 包裹
2. 标题行必须包含 "([TICKER])" 格式，如 "NVIDIA (NVDA)"
3. 观察池和诱多池必须用 <li> 包裹，且包含 "([TICKER])"
4. 不要输出 ```html 或 ``` 标记
5. 从第一个字符开始就是 <div

只输出HTML，不输出解释性前言。
"""
    try:
        out = _anthropic_stream_text(client, model=TARGET_MODEL, max_tokens=30000, messages=[{"role":"user","content":prompt}]).replace("```html","").replace("```","").strip()
        idx = out.find("<div")
        if idx > 0:
            out = out[idx:]
        print(f"✅ AI 报告生成完成：{len(out)} 字符")
        return out
    except Exception as e:
        print(f"🚨 AI 报告失败：{e}")
        return '<div class="header-card"><h2>⚠️ AI报告生成失败</h2><p>请检查 API 和网络。</p></div>'

# ==================== 14. Match / 写账 ====================
def match_pool_to_report(pool_data, ai_html, default_stop_loss_pct):
    def clean(t):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()
    def title_hit(fragment, name, ticker):
        head = fragment[:140]
        return f"({ticker})" in head or name in head[:40]

    obs_start = ai_html.find('class="compare-card"')
    if obs_start < 0:
        obs_start = ai_html.find("观察池")
    if obs_start < 0:
        obs_start = len(ai_html)
    trap_start = ai_html.find("诱多对照组")
    if trap_start < 0 or trap_start < obs_start:
        trap_start = len(ai_html)

    core_zone = ai_html[:obs_start]
    obs_zone = ai_html[obs_start:trap_start]
    trap_zone = ai_html[trap_start:]
    core_cards = [clean(x) for x in re.split(r'(?=<div class="top-card")', core_zone) if "top-card" in x]
    obs_items = [clean(x) for x in re.split(r'(?=<li>)', obs_zone) if x.strip().startswith("<li>")]
    trap_items = [clean(x) for x in re.split(r'(?=<li>)', trap_zone) if x.strip().startswith("<li>")]

    chosen = []
    for item in pool_data:
        name, ticker = str(item["Name"]), str(item["Ticker"])
        tag, chunk = None, None
        for c in core_cards:
            if title_hit(c,name,ticker):
                tag, chunk = "Core_Dragon", c; break
        if tag is None:
            for c in obs_items:
                if title_hit(c,name,ticker):
                    tag, chunk = "Observation", c; break
        if tag is None:
            for c in trap_items:
                if title_hit(c,name,ticker):
                    tag, chunk = "Trap_Warning", c; break
        if tag is None or tag == "Trap_Warning":
            continue

        if tag == "Observation":
            hp, sl, score = "观望", "观望", "N/A"
        else:
            hp = "动态持有"
            sm = re.search(r'止损[\s]*[:：][\s]*\[?(\$?\d+(?:\.\d+)?%?)', chunk)
            if sm:
                sl = sm.group(1)
            else:
                atr = item.get("ATR_Pct",5.0)
                pct = -max(ATR_STOP_FLOOR_PCT, min(ATR_STOP_CEIL_PCT, atr*ATR_STOP_MULTIPLIER))
                sl = f"${round(item['Price']*(1+pct/100),2)}"
            sc = re.search(r'评分[\s]*[:：][\s]*\[?(\d{1,3})\]?[\s]*/[\s]*100', chunk)
            score = sc.group(1) if sc else str(min(100, int(item.get("技术评分",0))+50))

        item = dict(item)
        item["Tag"] = tag
        item["Hold_Period"] = hp
        item["Stop_Loss"] = sl
        item["Score"] = score
        chosen.append(item)
    return chosen

# ==================== 15. 邮件 ====================
def send_mail(to_emails, subject, content):
    user = os.environ.get("EMAIL_ACCOUNT")
    pwd = os.environ.get("EMAIL_PASSWORD")
    if not user or not pwd or not to_emails:
        print("⚠️ 邮件配置不完整，跳过邮件发送")
        return
    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = to_emails
    msg["Subject"] = subject
    msg.attach(MIMEText(content,"html","utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com",465,timeout=30) as s:
            s.login(user,pwd)
            s.sendmail(user,[x.strip() for x in to_emails.split(",") if x.strip()],msg.as_string())
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 邮件发送失败：{e}")

# ==================== 16. HTML 样式 ====================
def build_full_email_html(ai_html):
    style = """
    <style>
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:#f0f2f5;padding:20px;color:#2c3e50;line-height:1.7}
    .container{max-width:1000px;margin:0 auto;background:#fff;padding:35px;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.08)}
    .header-card{background:#e3f2fd;border-left:6px solid #1565c0;padding:22px;margin-bottom:25px;border-radius:8px}
    .top-card{padding:25px;margin-bottom:30px;border-radius:10px;background:#fafafa;border:1px solid #e0e0e0;border-left:6px solid #78909c}
    .core-card{border-left-color:#d32f2f;background:#fffcfc}
    .compare-card{border-left:5px solid #ff9800;background:#fffdf7;padding:25px;margin-bottom:25px;border-radius:10px}
    .trap-card{border-left:5px solid #607d8b;background:#fbfcfe;padding:25px;margin-bottom:25px;border-radius:10px}
    .top-title{font-size:20px;font-weight:800;border-bottom:1px dashed #cfd8dc;padding-bottom:10px;margin-bottom:15px}
    .highlight-label{display:inline-block;font-weight:bold;color:#fff;padding:3px 8px;border-radius:4px;margin-right:6px;font-size:13px}
    .bg-red{background:#d32f2f}.bg-green{background:#2e7d32}.bg-blue{background:#1976d2}.bg-teal{background:#00897b}.bg-orange{background:#e64a19}
    </style>
    """
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>🎯 宏观驱动美股波段内参：{TARGET_REGION}</h1>{ai_html}<p style='text-align:center;color:#999;font-size:12px'>[END_OF_QUANT_REPORT]</p></div></body></html>"

# ==================== 17. 期权策略 ====================
def _write_option_strategy_fallback(item):
    """外部期权引擎不可用时，保留原版内联逻辑写入 option_strategies.csv。"""
    try:
        opt_file = "option_strategies.csv"
        # 期权到期日独立于股票持仓逻辑；股票已经改为动态持有。
        hp = str(item.get("Hold_Period", "动态持有"))
        nums = [int(x) for x in re.findall(r"\d+", hp)]
        max_days = max(nums) if nums else 45
        max_days = max(30, min(60, max_days))
        expiry = (get_us_time() + datetime.timedelta(days=max_days)).strftime("%Y-%m-%d")
        price = float(item.get("Price", 0) or 0)
        stop = item.get("Stop_Loss", "N/A")
        strike = round(price * 1.05, 2)
        entry_price = round(strike * 0.02, 2)
        header = "Ticker,OptionType,Strike,Expiry,EntryPrice,Status,EntryDate,Quantity,Direction,UnderlyingPrice,StopLoss,HoldPeriod,Reason,ScanScore\n"
        need_header = (not os.path.exists(opt_file)) or os.path.getsize(opt_file) == 0
        with open(opt_file, "a", encoding="utf-8", newline="") as f:
            if need_header:
                f.write(header)
            reason = "美股 scan 核心精选：事件/Regime/技术共振，偏多。"
            safe_reason = reason.replace(",", "；")
            f.write(f"{item.get('Ticker','')},CALL,{strike},{expiry},{entry_price},Active,{today_us_str()},1,BULLISH,{price},{stop},{hp},{safe_reason},{item.get('Score','N/A')}\n")
        print(f"📝 [期权备用] {item.get('Ticker','')} CALL {strike} @ {expiry}")
        return True
    except Exception as e:
        print(f"⚠️ {item.get('Ticker','')} 期权备用策略失败：{e}")
        return False


def safe_generate_option_strategy(item):
    if append_option_strategy is not None:
        try:
            result = append_option_strategy(
                ticker=item["Ticker"], name=item["Name"], direction="BULLISH",
                scan_score=item.get("Score","N/A"), scan_date=today_us_str(),
                underlying_price=item.get("Price",0), underlying_stop=item.get("Stop_Loss","N/A"),
                hold_period="45天",
                strategy_reason="美股 scan 核心精选：事件/Regime/技术共振，偏多。", contracts=1,
            )
            if result:
                return True
        except Exception as e:
            print(f"⚠️ {item.get('Ticker','')} 外部期权引擎失败，切换内联备用：{e}")
    return _write_option_strategy_fallback(item)

# ==================== 主程序 ====================
if __name__ == "__main__":
    macro_news = get_latest_macro_news()
    megacap_news = get_megacap_breaking_news()
    key_people_news = get_key_people_policy_news(macro_news)
    preliminary_news = macro_news
    if megacap_news:
        preliminary_news += "\n\n【Mega-Cap 最新动态】\n" + megacap_news
    if key_people_news:
        preliminary_news += "\n\n【重要人物讲话/政策预期】\n" + key_people_news
    economic_text, economic_structured = get_us_economic_data(preliminary_news)
    combined_news = preliminary_news
    if economic_text:
        combined_news += "\n\n【结构化美国经济数据】\n" + economic_text

    macro_market = get_macro_market_data()
    sector_text = get_us_sector_performance()

    # Regime Gate：真正进入决策流程；人物讲话 + 经济数据 + 价格三者共同确认
    event_regime = build_event_regime_gate(
        combined_news, macro_market, sector_text,
        key_people_text=key_people_news, economic_text=economic_text
    )
    event_regime_text = format_event_regime_gate(event_regime)
    print(event_regime_text)

    client = anthropic.Anthropic(api_key=os.environ["CLAWSOCKET_API_KEY"], base_url=os.environ["CLAWSOCKET_BASE_URL"])
    signal_analysis = analyze_market_signals(combined_news, client)
    signal_block = build_market_signal_text(signal_analysis)
    market_signal_text = signal_block[0] if signal_block else ""

    restricted_tickers, dropped_info, current_prices = pre_scan_portfolio_review(combined_news, macro_market)
    raw_tickers = get_scan_pool()
    pool_tickers = {t:n for t,n in raw_tickers.items() if t not in restricted_tickers}
    pool_data = build_stock_pool(pool_tickers)
    if not pool_data:
        empty = build_full_email_html('<div class="header-card"><h2>⚠️ 今日扫描无有效标的</h2><p>行情/技术数据不足，安全退出。</p></div>')
        send_mail(SUPER_ADMIN, f"【美股扫描】{today_us_str()} 无有效标的", empty)
        sys.exit(0)

    sector_tech_data = screen_technical_setups(pool_data)
    pool_data = enrich_pool_with_fundamentals(pool_data, limit=80)
    pool_data = enrich_pool_with_news(pool_data)

    # 将 Regime Gate 硬回避行业转成 AI 明确的硬约束文字
    gate_hard = (event_regime or {}).get("hard_avoid_sectors", [])
    gate_text = event_regime_text + "\n当前硬回避行业必须阻止进入Top1-5：" + (", ".join(gate_hard) if gate_hard else "无")

    ai_html = generate_ai_report(
        pool_data,
        combined_news,
        macro_market,
        dropped_info,
        gate_text,
        sector_tech_data,
        gate_text,
        event_regime,
        market_signal_text,
        key_people_news,
        economic_text,
    )

    full_html = build_full_email_html(ai_html)
    send_mail(SUPER_ADMIN, f"【宏观驱动美股版】{TARGET_REGION} 核心打分与实战 ({today_us_str()})", full_html)

    chosen = match_pool_to_report(pool_data, ai_html, DEFAULT_STOP_LOSS_PCT)

    # Fallback: 如果 AI HTML 匹配完全失败，从技术评分 Top10 中分层取标的
    if not chosen:
        print("⚠️ AI HTML 匹配失败，启用技术评分 Fallback...")
        top_pool = sorted(
            [x for x in pool_data if x.get("技术评分", 0) > 0],
            key=lambda x: (x.get("综合基础评分", x.get("技术评分", 0)), x.get("技术评分", 0)), reverse=True
        )
        # Top 5 作为 Core_Dragon，6-10 作为 Observation
        for rank, item in enumerate(top_pool[:10], 1):
            copy_item = dict(item)
            if rank <= 5:
                copy_item["Tag"] = "Core_Dragon"
                atr = copy_item.get("ATR_Pct", 5.0)
                pct = -max(ATR_STOP_FLOOR_PCT, min(ATR_STOP_CEIL_PCT, atr * ATR_STOP_MULTIPLIER))
                copy_item["Stop_Loss"] = f"${round(copy_item['Price']*(1+pct/100),2)}"
                copy_item["Hold_Period"] = "动态持有"
                copy_item["Score"] = str(min(100, 40 + int(copy_item.get("技术评分", 0)) + int(copy_item.get("估值评分", 0))))
                print(f"   🔄 Fallback Core: {copy_item['Name']}({copy_item['Ticker']}) 评分:{copy_item['技术评分']}/40")
            else:
                copy_item["Tag"] = "Observation"
                copy_item["Hold_Period"] = "观望"
                copy_item["Stop_Loss"] = "观望"
                copy_item["Score"] = "N/A"
                print(f"   👁️ Fallback 观察: {copy_item['Name']}({copy_item['Ticker']}) 评分:{copy_item['技术评分']}/40")
            chosen.append(copy_item)

    log_file = "trade_history.csv"
    to_write = []
    for item in chosen:
        if item.get("Tag") not in {"Core_Dragon","Observation"}:
            continue
        item = dict(item)
        if item.get("Tag") == "Core_Dragon":
            if not item.get("Hold_Period") or item.get("Hold_Period") in {"观望","N/A"}:
                item["Hold_Period"] = "动态持有"
            if not item.get("Stop_Loss") or item.get("Stop_Loss") in {"观望","N/A"}:
                atr = item.get("ATR_Pct",5.0)
                pct = -max(ATR_STOP_FLOOR_PCT,min(ATR_STOP_CEIL_PCT,atr*ATR_STOP_MULTIPLIER))
                item["Stop_Loss"] = f"${round(item['Price']*(1+pct/100),2)}"
            if not item.get("Score") or item.get("Score") in {"N/A","观望"}:
                item["Score"] = str(min(100,40 + int(item.get("技术评分",0)) + int(item.get("估值评分",0))))
        to_write.append(item)

    if os.path.exists(log_file) and to_write:
        try:
            old = pd.read_csv(log_file, keep_default_na=False)
            active_tags = {"Core_Double_Dragon","Sub_Pioneer","Core_Dragon"}
            active = set(old[old.get("Tag","").isin(active_tags)]["Ticker"].astype(str).tolist()) if "Tag" in old.columns else set()
            before = len(to_write)
            to_write = [x for x in to_write if x["Ticker"] not in active]
            print(f"📋 跳过 {before-len(to_write)} 只已在持仓中的标的")
        except Exception as e:
            print(f"⚠️ 持仓去重失败：{e}")

    if to_write:
        pending_file = f"us_stocks_pending_{get_us_time().strftime('%Y%m%d')}.csv"
        header_cols = [
            "Date","Ticker","Name","Tag","RSI","Bias","技术评分","估值评分","PE_TTM","PE_Forward","EPS_TTM","PB","MACD金叉","周线共振","KDJ_J回升","量能放大","Hold_Period","Stop_Loss","Stop_Method","Score","Status","Scan_Ref_Price","ATR_Pct","周期共振"
        ]
        with open(pending_file,"w",encoding="utf-8",newline="") as f:
            f.write(",".join(header_cols)+"\n")
            for item in to_write:
                vals = [
                    today_us_str(), item.get("Ticker",""), item.get("Name",""), item.get("Tag",""),
                    item.get("RSI",""), item.get("乖离率(%)",""), item.get("技术评分",0), item.get("估值评分",0),
                    item.get("PE_TTM",""), item.get("PE_Forward",""), item.get("EPS_TTM",""), item.get("PB",""),
                    item.get("MACD金叉",False), item.get("周线共振",False), item.get("KDJ_J回升",False), item.get("量能放大",False), item.get("Hold_Period","动态持有"),
                    item.get("Stop_Loss",""), item.get("Stop_Method","ATR初始保护"), item.get("Score",""), "pending", item.get("Price",item.get("Open_Price","")),
                    item.get("ATR_Pct",""), item.get("周期共振",False)
                ]
                safe_vals = [str(v).replace(","," ").replace("\n"," ") for v in vals]
                f.write(",".join(safe_vals)+"\n")
        print(f"✅ 已生成 {len(to_write)} 条美股待确认记录：{pending_file}")

        option_created = 0
        for item in to_write:
            if item.get("Tag") == "Core_Dragon" and safe_generate_option_strategy(item):
                option_created += 1
        print(f"🎯 Scan→Option 联动：{option_created} 笔")
    else:
        print("⚠️ 今日没有新增可入账推荐")

    print("🎯 美股盘前扫描完成。")
