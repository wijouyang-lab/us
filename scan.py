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

from clawsocket_compat import ClawSocketClient
import pandas as pd
import pandas_ta as ta
import requests
import yfinance as yf

# 统一期权引擎：Scan 生成真实可验证期权建议；期权链不可用时明确返回失败，不伪造报价。
from scan_us_option_engine import append_option_strategy, get_recent_option_recommendations

# ==================== 环境检查 ====================
TARGET_MODEL = os.environ.get("GPT_MODEL") or "gpt-6-astra"
TARGET_REGION = "美国市场"
DEFAULT_STOP_LOSS_PCT = -5.0
ATR_STOP_MULTIPLIER = 2.0
ATR_STOP_FLOOR_PCT = 3.0
ATR_STOP_CEIL_PCT = 12.0
REGIME_GATE_VERSION = "2026-08-31-US"

STRATEGY_PARAMS_FILE = "strategy_params.json"

def load_strategy_params():
    base = {
        "scoring": {"fundamental_weight": 35, "event_weight": 20, "technical_weight": 25, "risk_weight": 20,
                    "ai_weight": 30, "quant_weight": 70, "core_min_score": 65, "observation_min_score": 58,
                    "pre_ai_min_quant_score": 55, "min_technical_confirmations": 2, "stressed_min_technical_confirmations": 3},
        "regime": {"vix_tighten": 25, "vix_panic": 30, "spy_ma_buffer_pct": 0.0, "sector_rs_min_pct": 0.0, "recent_market_drop_pct": -2.0},
        "liquidity": {"min_market_cap": 5e8, "min_avg_dollar_volume": 5e6},
        "technical": {"ma20_slope_min_pct_5d": -0.20, "recent_volume_ratio": 1.15, "recent_bull_volume_ratio": 1.50, "atr_max_pct": 12.0},
        "exit": {"early_days": 3, "early_stop_pct": -5.0, "atr_multiplier": 2.0, "atr_floor_pct": 3.0, "atr_ceiling_pct": 12.0,
                 "profit_lock_1_pct": 15.0, "profit_lock_1_drawdown_pct": 10.0,
                 "profit_lock_2_pct": 30.0, "profit_lock_2_drawdown_pct": 8.0,
                 "profit_lock_3_pct": 50.0, "profit_lock_3_drawdown_pct": 12.0},
        "limits": {"max_core": 5, "max_observation": 7, "evolution_recent_rules": 4}
    }
    try:
        with open(STRATEGY_PARAMS_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        for section, values in loaded.items():
            if isinstance(values, dict) and isinstance(base.get(section), dict):
                base[section].update(values)
    except Exception as e:
        print(f"⚠️ strategy_params.json 读取失败，使用默认参数: {e}")
    return base

STRATEGY_PARAMS = load_strategy_params()
SCORING_PARAMS = STRATEGY_PARAMS["scoring"]
REGIME_PARAMS = STRATEGY_PARAMS["regime"]
TECH_PARAMS = STRATEGY_PARAMS["technical"]
LIQUIDITY_PARAMS = STRATEGY_PARAMS["liquidity"]
EXIT_PARAMS = STRATEGY_PARAMS["exit"]
LIMIT_PARAMS = STRATEGY_PARAMS["limits"]

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
            "Revenue_Growth": _safe_info_float(info, "revenueGrowth"),
            "ROE": _safe_info_float(info, "returnOnEquity"),
            "Profit_Margin": _safe_info_float(info, "profitMargins"),
            "Operating_Cashflow": _safe_info_float(info, "operatingCashflow"),
            "Free_Cashflow": _safe_info_float(info, "freeCashflow"),
            "Market_Cap": _safe_info_float(info, "marketCap"),
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
        for k in ("PE_TTM", "PE_Forward", "EPS_TTM", "EPS_Forward", "PB", "Earnings_Growth", "Revenue_Growth", "ROE", "Profit_Margin", "Operating_Cashflow", "Free_Cashflow", "Market_Cap"):
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
            ma50_s = ta.sma(df["Close"], length=50)
            atr_s = ta.atr(df["High"], df["Low"], df["Close"], length=14)
            df = df.copy()
            df["MACDh"] = macd_df.iloc[:, 1]
            df["RSI"] = rsi_s
            df["MA20"] = ma20_s
            df["MA50"] = ma50_s
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
            avg20_vol = float(pd.Series(vol[:-1]).tail(20).mean()) if len(vol) >= 21 else avg5
            near5 = df.tail(5).copy()
            bull_volume_event = False
            max_recent_vol_ratio = 0.0
            for _, rr in near5.iterrows():
                rv = float(rr.get("Volume", 0) or 0)
                rc = float(rr.get("Close", 0) or 0)
                ro = float(rr.get("Open", 0) or 0)
                ratio = rv / (avg20_vol + 1e-9) if avg20_vol > 0 else 0
                max_recent_vol_ratio = max(max_recent_vol_ratio, ratio)
                if rc > ro and ratio >= float(TECH_PARAMS.get("recent_bull_volume_ratio", 1.5)):
                    bull_volume_event = True
            ma20_now = float(latest["MA20"])
            ma20_prev5 = float(df["MA20"].iloc[-6]) if len(df) >= 26 and pd.notna(df["MA20"].iloc[-6]) else ma20_now
            ma20_slope_pct = (ma20_now / ma20_prev5 - 1) * 100 if ma20_prev5 else 0.0
            ma50_now = float(latest["MA50"]) if pd.notna(latest["MA50"]) else ma20_now

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
                "MA20": round(ma20_now, 2),
                "MA50": round(ma50_now, 2),
                "MA20_Slope_Pct_5D": round(ma20_slope_pct, 3),
                "Avg_Dollar_Volume_20D": round(avg20_vol * float(latest["Close"]), 2) if avg20_vol else None,
                "近5日最大量比": round(max_recent_vol_ratio, 2),
                "近5日放量阳线": bool(bull_volume_event),
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


# ==================== 5.5 市场环境 / 相对强弱 / 透明量化评分 ====================
def _download_close_series(ticker, period="30d"):
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True, threads=False)
        if df is None or df.empty:
            return pd.Series(dtype=float)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return pd.to_numeric(df["Close"], errors="coerce").dropna()
    except Exception:
        return pd.Series(dtype=float)


def get_market_regime_context():
    """用 SPY/VIX + 行业 ETF 相对强弱形成硬门控；失败时明确标记数据不足，不伪造。"""
    ctx = {
        "spy": None, "spy_ma20": None, "spy_above_ma20": None,
        "spy_5d_return": None, "vix": None, "regime": "UNKNOWN",
        "sector_rs": {}, "reason": []
    }
    spy = _download_close_series("SPY", "60d")
    if len(spy) >= 21:
        ctx["spy"] = float(spy.iloc[-1])
        ctx["spy_ma20"] = float(spy.rolling(20).mean().iloc[-1])
        ctx["spy_above_ma20"] = ctx["spy"] >= ctx["spy_ma20"] * (1 + float(REGIME_PARAMS.get("spy_ma_buffer_pct", 0))/100)
    if len(spy) >= 6:
        ctx["spy_5d_return"] = float((spy.iloc[-1] / spy.iloc[-6] - 1) * 100)
    vix = _download_close_series("^VIX", "15d")
    if len(vix):
        ctx["vix"] = float(vix.iloc[-1])
    if ctx["vix"] is None:
        ctx["regime"] = "UNKNOWN"
    elif ctx["vix"] >= float(REGIME_PARAMS["vix_panic"]):
        ctx["regime"] = "PANIC"
        ctx["reason"].append(f"VIX={ctx['vix']:.1f}≥{REGIME_PARAMS['vix_panic']}")
    elif ctx["vix"] >= float(REGIME_PARAMS["vix_tighten"]):
        ctx["regime"] = "STRESSED"
        ctx["reason"].append(f"VIX={ctx['vix']:.1f}≥{REGIME_PARAMS['vix_tighten']}")
    else:
        ctx["regime"] = "NORMAL"
    if ctx["spy_above_ma20"] is False:
        ctx["reason"].append("SPY低于MA20")
    if ctx["spy_5d_return"] is not None and ctx["spy_5d_return"] <= float(REGIME_PARAMS["recent_market_drop_pct"]):
        ctx["reason"].append(f"SPY近5日{ctx['spy_5d_return']:+.2f}%")

    etf_map = {
        "Technology":"XLK", "Communication":"XLC", "Consumer Discretionary":"XLY", "Consumer Staples":"XLP",
        "Financials":"XLF", "Healthcare":"XLV", "Industrials":"XLI", "Energy":"XLE",
        "Materials":"XLB", "Utilities":"XLU", "Real Estate":"XLRE"
    }
    for sector, etf in etf_map.items():
        s = _download_close_series(etf, "30d")
        if len(s) >= 21 and len(spy) >= 21:
            sr = float((s.iloc[-1] / s.iloc[-21] - 1) * 100)
            spr = float((spy.iloc[-1] / spy.iloc[-21] - 1) * 100)
            ctx["sector_rs"][sector] = round(sr - spr, 2)
    print(f"🧭 [Regime] {ctx['regime']} | SPY={ctx['spy']} MA20={ctx['spy_ma20']} 5D={ctx['spy_5d_return']}% | VIX={ctx['vix']} | {', '.join(ctx['reason']) or '正常'}")
    return ctx


def apply_market_context_to_pool(pool_data, market_ctx):
    for item in pool_data:
        sector = _US_SECTOR_MAP.get(item.get("Ticker"), "Other")
        item["Sector"] = sector
        item["Sector_RS_20D_Pct"] = market_ctx.get("sector_rs", {}).get(sector)
        item["SPY_Above_MA20"] = market_ctx.get("spy_above_ma20")
        item["VIX"] = market_ctx.get("vix")
        item["Market_Regime"] = market_ctx.get("regime")
    return pool_data


def _clip(v, lo, hi):
    return max(lo, min(hi, v))


def score_candidate_quality(item, market_ctx):
    """透明量化评分：基本面35 + 事件20 + 技术25 + 风险/流动性20。"""
    # ---------- Fundamental 35 ----------
    fs = 0.0
    rg = item.get("Revenue_Growth")
    eg = item.get("Earnings_Growth")
    roe = item.get("ROE")
    pm = item.get("Profit_Margin")
    ocf = item.get("Operating_Cashflow")
    fcf = item.get("Free_Cashflow")
    pe = item.get("PE_Forward")
    pb = item.get("PB")
    if isinstance(rg, (int,float)):
        fs += 8 if rg >= .15 else 5 if rg >= .08 else 2 if rg >= 0 else 0
    if isinstance(eg, (int,float)):
        fs += 7 if eg >= .15 else 4 if eg >= .08 else 2 if eg >= 0 else 0
    if isinstance(roe, (int,float)):
        fs += 7 if roe >= .15 else 4 if roe >= .08 else 2 if roe >= 0 else 0
    if isinstance(pm, (int,float)):
        fs += 4 if pm >= .10 else 2 if pm >= .05 else 0
    if isinstance(ocf, (int,float)) and ocf > 0: fs += 4
    if isinstance(fcf, (int,float)) and fcf > 0: fs += 3
    if isinstance(pe, (int,float)) and pe > 0:
        if pe <= 20: fs += 2
        elif pe <= 35: fs += 1
    if isinstance(pb, (int,float)) and pb > 0 and pb <= 5: fs += 1
    fundamental = _clip(fs, 0, 35)

    # ---------- Event 20 ----------
    news = " ".join(item.get("个股新闻", []) or []).lower()
    event_positive = sum(k in news for k in (
        "earnings beat", "guidance", "contract", "order", "approval", "upgrade", "partnership", "deal", "record revenue",
        "超预期", "订单", "批准", "合作", "上调指引", "创纪录"
    ))
    event_negative = sum(k in news for k in (
        "downgrade", "miss", "lawsuit", "investigation", "cut guidance", "warning", "recall",
        "下调指引", "诉讼", "调查", "警告", "召回"
    ))
    event = _clip(8 + event_positive * 3 - event_negative * 4, 0, 20)
    item["Event_Positive_Count"] = event_positive
    item["Event_Negative_Count"] = event_negative

    # ---------- Technical 25 ----------
    confirmations = int(item.get("技术确认数", 0))
    tech = _clip(confirmations * 5, 0, 20)
    if item.get("周线共振"): tech += 3
    if item.get("周期共振"): tech += 2
    technical = _clip(tech, 0, 25)

    # ---------- Risk / Liquidity 20 ----------
    risk = 10.0
    mcap = item.get("Market_Cap")
    adv = item.get("Avg_Dollar_Volume_20D")
    atrp = item.get("ATR_Pct")
    rs = item.get("Sector_RS_20D_Pct")
    if isinstance(mcap, (int,float)):
        risk += 2 if mcap >= 5e9 else 1 if mcap >= 5e8 else -4
    else: risk -= 2
    if isinstance(adv, (int,float)):
        risk += 4 if adv >= 2e7 else 2 if adv >= 5e6 else -4
    else: risk -= 2
    if isinstance(atrp, (int,float)):
        risk += 2 if atrp <= 5 else 0 if atrp <= 8 else -3
    if isinstance(rs, (int,float)):
        risk += 2 if rs > 0 else -3
    # 正常、浅回撤环境下，SPY跌破MA20不再直接否决非防御股；改为轻微风险扣分。
    # 只有市场进一步恶化（VIX压力或5日SPY跌幅达到硬阈值）时才走硬门槛。
    if market_ctx.get("spy_above_ma20") is False:
        risk -= 2
        item["SPY_Trend_Warning"] = True
    else:
        item["SPY_Trend_Warning"] = False
    risk = _clip(risk, 0, 20)

    quant = round(fundamental + event + technical + risk, 1)
    item["Fundamental_Score"] = round(fundamental, 1)
    item["Event_Score"] = round(event, 1)
    item["Technical_Score_25"] = round(technical, 1)
    item["Risk_Liquidity_Score"] = round(risk, 1)
    item["Quant_Score"] = quant
    return item


def apply_entry_quality_gate(pool_data, market_ctx, event_regime=None):
    out = []
    fail_counts = {}
    regime = market_ctx.get("regime", "UNKNOWN")
    event_regime = event_regime or {}
    hard_avoid = set(event_regime.get("hard_avoid_sectors", []) or [])

    def fail(item, status):
        item["Gate_Status"] = status
        fail_counts[status] = fail_counts.get(status, 0) + 1
    min_tech = int(SCORING_PARAMS.get("min_technical_confirmations", 2))
    if regime in {"STRESSED", "PANIC"}:
        min_tech = max(min_tech, int(SCORING_PARAMS.get("stressed_min_technical_confirmations", 3)))
    defensive = {"Healthcare", "Consumer Staples", "Utilities"}
    for item in pool_data:
        techn = int(item.get("技术确认数", 0))
        quant = float(item.get("Quant_Score", 0))
        if techn < min_tech:
            fail(item, "TECH_FAIL")
            continue
        if quant < float(SCORING_PARAMS.get("pre_ai_min_quant_score", 55)):
            fail(item, "QUANT_FAIL")
            continue
        if item.get("Sector") in hard_avoid:
            fail(item, "EVENT_HARD_AVOID")
            continue
        atrp = item.get("ATR_Pct")
        if isinstance(atrp, (int,float)) and atrp > float(TECH_PARAMS.get("atr_max_pct", 12)):
            fail(item, "ATR_FAIL")
            continue
        rs = item.get("Sector_RS_20D_Pct")
        if regime != "UNKNOWN" and isinstance(rs, (int,float)) and rs < float(REGIME_PARAMS.get("sector_rs_min_pct", 0)):
            fail(item, "SECTOR_RS_FAIL")
            continue
        # SPY仅温和跌破MA20时不再“一刀切”剔除所有非防御行业。
        # 当VIX进入压力/恐慌，或SPY近5日跌幅达到硬阈值时，再启用SPY趋势硬门槛。
        spy_hard = (
            market_ctx.get("spy_above_ma20") is False
            and (
                regime in {"STRESSED", "PANIC"}
                or (market_ctx.get("spy_5d_return") is not None and
                    market_ctx.get("spy_5d_return") <= float(REGIME_PARAMS.get("recent_market_drop_pct", -2.0)))
            )
        )
        if spy_hard and item.get("Sector") not in defensive:
            fail(item, "SPY_TREND_FAIL")
            continue
        if regime == "PANIC" and item.get("Sector") not in defensive and quant < 68:
            fail(item, "PANIC_FAIL")
            continue
        item["Gate_Status"] = "PASS_PRE_AI"
        out.append(item)
    print(f"🛡️ [硬门槛] {len(out)}/{len(pool_data)} 只通过；最低技术确认={min_tech}；Regime={regime}")
    if fail_counts:
        detail = " | ".join(f"{k}={v}" for k, v in sorted(fail_counts.items(), key=lambda kv: kv[1], reverse=True))
        print(f"   ↳ 失败原因分布：{detail}")
    return out


# ==================== 6. 技术评分 ====================
def check_period_resonance(stock):
    if not stock.get("日线MACD上升") or not stock.get("周线MACD上升"):
        return False, []
    valid = ["看涨吞没", "启明星", "刺穿线", "锤子线"]
    matched = [p for p in stock.get("看涨形态", []) if p in valid]
    return bool(matched), matched


def screen_technical_setups(pool_data):
    """透明技术确认：不只依赖经典金叉，允许 MACD 收敛/上升、KDJ、均线与放量结构参与。"""
    sector_groups = {}
    for stock in pool_data:
        reasons = []
        close = float(stock.get("Price", 0) or 0)
        ma20 = float(stock.get("MA20", close) or close)
        ma50 = float(stock.get("MA50", ma20) or ma20)
        ma20_slope = float(stock.get("MA20_Slope_Pct_5D", 0) or 0)
        h = float(stock.get("MACD_HIST_LAST", 0) or 0)
        hp = float(stock.get("MACD_HIST_PREV", 0) or 0)
        j = float(stock.get("KDJ_J", 50) or 50)
        vr = float(stock.get("量比", 1) or 1)
        confirmations = []

        # 1) 均线结构：价格站上 MA20 + MA20 不明显下斜
        if close > ma20 and ma20_slope >= float(TECH_PARAMS.get("ma20_slope_min_pct_5d", -0.2)):
            confirmations.append("MA20结构")
        # 2) MACD：经典金叉/绿柱收敛/红柱扩大三选一
        macd_improving = bool(stock.get("MACD金叉") or stock.get("MACD绿柱缩短") or h > hp)
        if macd_improving:
            confirmations.append("MACD改善")
        # 3) KDJ J 回升
        if bool(stock.get("KDJ_J回升")):
            confirmations.append("KDJ回升")
        # 4) 周线结构
        if bool(stock.get("周线共振")) or bool(stock.get("周线MACD上升")):
            confirmations.append("周线改善")
        # 5) 放量结构：不再要求“所有标的必须放量”，但作为强确认
        if bool(stock.get("量能放大")) or float(stock.get("近5日最大量比", 0) or 0) >= float(TECH_PARAMS.get("recent_volume_ratio", 1.15)):
            confirmations.append("量能确认")

        # 蜡烛形态 / 周日共振作为附加项
        if stock.get("看涨形态"):
            reasons.append("形态=" + "/".join(stock["看涨形态"]))
        if stock.get("周期共振"):
            reasons.append("周期共振")
        if stock.get("周线共振"):
            reasons.append("周线共振")

        stock["技术确认信号"] = confirmations
        stock["技术确认数"] = len(confirmations)
        stock["技术评分"] = min(40, len(confirmations) * 7 + (4 if stock.get("周线共振") else 0) + (3 if stock.get("周期共振") else 0))
        stock["技术信号"] = reasons + ["确认=" + ",".join(confirmations)]
        sector = _US_SECTOR_MAP.get(stock["Ticker"], "Other")
        sector_groups.setdefault(sector, []).append({"名称":stock["Name"],"代码":stock["Ticker"],"技术评分":stock["技术评分"],"技术确认数":len(confirmations),"技术信号":stock["技术信号"]})

    print("📊 [技术筛选] 技术确认 Top10：")
    for s in sorted(pool_data, key=lambda x: (x.get("技术确认数",0), x.get("技术评分",0)), reverse=True)[:10]:
        print(f"   {s['Name']}({s['Ticker']}) {s.get('技术评分',0)}/40 | 确认{s.get('技术确认数',0)}项 | {','.join(s.get('技术确认信号',[]))}")
    return {k: sorted(v, key=lambda x: (x.get("技术确认数",0),x.get("技术评分",0)), reverse=True) for k,v in sector_groups.items()}


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


def _fetch_bea_core_pce_webpage():
    """从 BEA 官方核心PCE页面读取最新公布的同比值。"""
    url = "https://bea.gov/data/personal-consumption-expenditures-price-index-excluding-food-and-energy"
    try:
        resp = get_robust_session().get(url, timeout=8)
        resp.raise_for_status()
        text = re.sub(r"\s+", " ", resp.text)
        # 页面当前会把最新月份写成：July 2026 | +3.3%
        months = "January|February|March|April|May|June|July|August|September|October|November|December"
        m = re.search(rf"({months})\s+(20\d{{2}})\s*\|\s*([+-]?[0-9]+(?:\.[0-9]+)?)%", text, re.I)
        if not m:
            return None
        month_year = f"{m.group(1)} {m.group(2)}"
        return {
            "value": float(m.group(3)),
            "yoy": float(m.group(3)),
            "date": month_year,
            "source": "BEA 官方网页",
            "unit": "%",
        }
    except Exception as e:
        print(f"   ⚠️ BEA 核心PCE备用失败: {e}")
        return None


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

    # ===== 3. 核心PCE：FRED → BEA官方网页 → 新闻文本 → Google News =====
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
        # 备用 1: BEA 官方核心PCE页面
        bea_pce = _fetch_bea_core_pce_webpage()
        if bea_pce:
            data["核心PCE指数"] = bea_pce
            lines.append(f"- 核心PCE指数：{bea_pce['yoy']:.2f}% YoY（BEA 官方网页，数据期 {bea_pce['date']}）")
            print(f"   ✅ 核心PCE指数: BEA 官方网页成功")
        else:
            # 备用 2: 从已抓取的新闻文本中提取
            pce_from_news = _extract_pce_from_news(combined_news_text if 'combined_news_text' in dir() else "")
            if pce_from_news:
                data["核心PCE指数"] = pce_from_news
                lines.append(f"- 核心PCE指数：{pce_from_news['value']:.2f}%（新闻文本提取，数据期 {pce_from_news['date']}）")
                print(f"   ✅ 核心PCE指数: 新闻文本提取成功")
            else:
                # 备用 3: Google News 提取
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


def _model_text(response):
    """兼容新版 Claude 的 TextBlock / ThinkingBlock 返回结构。"""
    parts = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _model_stream_text(client, **kwargs):
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
def _extract_json_object(text):
    """从 Claude 输出中提取第一个完整 JSON 对象，容忍 ```json、前后解释和字符串内花括号。"""
    raw = str(text or "").strip()
    if not raw:
        return None
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = raw[start:i+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    return None
    return None


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
        text = _model_stream_text(client, model=TARGET_MODEL, max_tokens=12000, messages=[{"role":"user","content":prompt}])
        data = _extract_json_object(text)
        if not isinstance(data, dict):
            print("⚠️ [市场信号] AI 返回不是有效 JSON，安全降级为空信号")
            return {"signals": []}
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
    """只注入最新且数量受控的历史规则，避免多年 prompt 补丁叠加冲突。"""
    path = "strategy_evolution.json"
    if not os.path.exists(path):
        path = "evolved_rules.json"
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data if isinstance(data, list) else []
        if not entries and isinstance(data, dict):
            rules = data.get("active_rules", [])
            entries = [{"applied_rules": rules}]
        rules = []
        for entry in reversed(entries):
            for rule in entry.get("applied_rules", []) if isinstance(entry, dict) else []:
                if rule and rule.get("description"):
                    rules.append(rule)
                if len(rules) >= int(LIMIT_PARAMS.get("evolution_recent_rules", 4)):
                    break
            if len(rules) >= int(LIMIT_PARAMS.get("evolution_recent_rules", 4)):
                break
        lines = [
            "【📈 最近有效绩效规则】",
            "只使用最近少量规则；历史规则不是永久黑名单。当前数据、当前技术与市场环境优先。",
        ]
        for r in reversed(rules):
            lines.append(f"- {r.get('type','')}: {r.get('description','')} | 证据: {r.get('evidence','')} | 执行: {r.get('prompt_patch','')}")
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

def get_review_risk_linkage_warning():
    """读取最近一次已完成 Review 的风控状态；仅把最近 Review 批次带入今日 Scan。

    规则：
    - STOP_TRIGGERED：今日硬禁入，禁止重新推荐。
    - STOP_NEAR：今日仍展示为强提醒，并在 AI 排名中降权。
    - 不再简单读取某只股票“最新交易行”，避免后续推荐行为空值把昨天的 Review 状态覆盖掉。
    """
    path='trade_history.csv'
    if not os.path.exists(path) or os.path.getsize(path)==0:
        return '',set(),set()
    try:
        df=pd.read_csv(path,keep_default_na=False,dtype=str)
    except Exception as e:
        print(f'⚠️ 读取 Review 风控联动失败: {e}'); return '',set(),set()
    required={'Ticker','Status','Review_Risk_Status','Review_Risk_Date'}
    if not required.issubset(df.columns): return '',set(),set()

    active=df[df['Status'].astype(str).str.strip().eq('Active')].copy()
    if active.empty: return '',set(),set()

    active['Review_Risk_Date_Norm']=pd.to_datetime(active['Review_Risk_Date'],errors='coerce')
    active['Date_Norm']=pd.to_datetime(active.get('Date',''),errors='coerce')
    valid=active[active['Review_Risk_Date_Norm'].notna()].copy()
    if valid.empty: return '',set(),set()

    # 当前 Scan 只消费最近一批已经完成的 Review，避免把更早日期的风险提醒无限向后沿用。
    today=pd.Timestamp(today_us_str())
    valid=valid[valid['Review_Risk_Date_Norm'] < today]
    if valid.empty:
        return '',set(),set()
    latest_review_date=valid['Review_Risk_Date_Norm'].max().normalize()
    batch=valid[valid['Review_Risk_Date_Norm'].dt.normalize().eq(latest_review_date)]

    triggered=set(); near=set(); lines=[]
    for ticker,grp in batch.groupby('Ticker',sort=False):
        # 同一 Review 日期若存在多行，优先取有明确风险状态的那一行。
        grp=grp.copy()
        grp['risk_rank']=grp['Review_Risk_Status'].map({'STOP_TRIGGERED':2,'STOP_NEAR':1}).fillna(0)
        row=grp.sort_values(['risk_rank','Date_Norm']).iloc[-1]
        st=str(row.get('Review_Risk_Status','')).strip(); note=str(row.get('Review_Risk_Note','')).strip()
        t=str(ticker).strip()
        name=str(row.get('Name',t)).strip()
        if st=='STOP_TRIGGERED':
            triggered.add(t)
            lines.append(f'🚨 {name} ({t})：昨日 Review 判定 STOP_TRIGGERED，今日禁止重新推荐。{note}')
        elif st=='STOP_NEAR':
            near.add(t)
            lines.append(f'⚠️ {name} ({t})：昨日 Review 判定 STOP_NEAR，今日强提醒并降权。{note}')

    if lines:
        header=f'【昨日 Review 风控联动｜{latest_review_date.strftime("%Y-%m-%d")}】'
        return header+'\n'+'\n'.join(lines),triggered,near
    return '',triggered,near


def build_review_risk_banner_html(review_risk_text, review_triggered, review_near):
    """确定性生成 Scan 邮件中的 Review→Scan 风控提醒，不能被 AI 输出覆盖或省略。"""
    if not review_risk_text and not review_triggered and not review_near:
        return ''
    rows=[]
    if review_risk_text:
        for line in review_risk_text.splitlines():
            if line.startswith('【'):
                continue
            if 'STOP_TRIGGERED' in line:
                rows.append(f'<div style="margin:8px 0;padding:10px 12px;background:#ffebee;border-left:5px solid #c62828;border-radius:5px;"><b style="color:#b71c1c;">{line}</b></div>')
            elif 'STOP_NEAR' in line:
                rows.append(f'<div style="margin:8px 0;padding:10px 12px;background:#fff8e1;border-left:5px solid #ef6c00;border-radius:5px;"><b style="color:#e65100;">{line}</b></div>')
    title='🚨 昨日 Review → 今日 Scan 风控提醒'
    summary=(f'硬禁入 {len(review_triggered)} 只｜强提醒 {len(review_near)} 只｜'
             '硬禁入标的不会进入今日 Top1-5；STOP_NEAR 标的继续参与数据分析，但必须降权。')
    return f'<div class="review-risk-banner"><h2>{title}</h2><p>{summary}</p>{"".join(rows)}</div>'

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

    client = ClawSocketClient(api_key=os.environ["CLAWSOCKET_API_KEY"], base_url=os.environ["CLAWSOCKET_BASE_URL"])
    prompt = f"""
你是美股宏观风控总监。判断当前活跃持仓是否存在真正的突发利空/逻辑证伪。
不要因为过去止损、过去低胜率就建议未来永久退出；只处理当前真实事件风险。

宏观：\n{macro_news_text[:6000]}\n\n市场：\n{macro_market_text}\n\n持仓：\n{'\n'.join(position_lines)}\n
仅输出：{{"decision":{{"TICKER":"Dropped|Active"}},"reason":"150字以内"}}
"""
    decisions = {}
    reason = ""
    try:
        txt = _model_stream_text(client, model=TARGET_MODEL, max_tokens=3000, messages=[{"role":"user","content":prompt}])
        obj = _extract_json_object(txt)
        if not isinstance(obj, dict):
            raise ValueError("Claude 风控返回不是有效 JSON")
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



def build_programmatic_fallback_report(pool_data, error_text):
    """AI不可用时仍输出可用的程序化报告，避免整封邮件只剩“API失败”。"""
    eligible = [x for x in pool_data if x.get("Gate_Status") == "PASS_PRE_AI"]
    eligible.sort(key=lambda x: (float(x.get("Quant_Score", 0) or 0), int(x.get("技术确认数", 0) or 0)), reverse=True)
    core_n = int(LIMIT_PARAMS.get("max_core", 5))
    obs_n = int(LIMIT_PARAMS.get("max_observation", 7))
    core = [x for x in eligible if float(x.get("Quant_Score",0) or 0) >= float(SCORING_PARAMS.get("core_min_score",65))][:core_n]
    used = {x.get("Ticker") for x in core}
    obs = [x for x in eligible if x.get("Ticker") not in used and float(x.get("Quant_Score",0) or 0) >= float(SCORING_PARAMS.get("observation_min_score",58))][:obs_n]

    def card(rank, x):
        return f'''<div class="top-card core-card">
<div class="top-title">{rank}. {html.escape(str(x.get("Name","")))} ({html.escape(str(x.get("Ticker","")))}) | RSI:{html.escape(str(x.get("RSI","N/A")))} | 乖离率:{html.escape(str(x.get("乖离率(%)","N/A")))}%</div>
<p><span class="highlight-label bg-red">🔗 产业链逻辑:</span>AI暂不可用，以下为程序化候选，不使用AI补全。</p>
<p><span class="highlight-label bg-blue">📈 技术确认:</span>{html.escape("、".join(map(str,x.get("技术确认信号",[]) or [])))} | 共{x.get("技术确认数",0)}项</p>
<p><span class="highlight-label bg-teal">⭐ 推荐评分:</span>程序 Quant {float(x.get("Quant_Score",0) or 0):.1f}/100 | AI=N/A</p>
<p><span class="highlight-label bg-blue">📊 量化拆解:</span>基本面:{x.get("Fundamental_Score",0)}/35 | 事件:{x.get("Event_Score",0)}/20 | 技术:{x.get("Technical_Score_25",0)}/25 | 风险/流动性:{x.get("Risk_Liquidity_Score",0)}/20 | MA20:{x.get("MA20","N/A")} | SectorRS20D:{x.get("Sector_RS_20D_Pct","N/A")}%</p>
<p><span class="highlight-label bg-orange">⚠️ 动态风控:</span>AI分析暂不可用；程序硬门槛已通过。不得仅凭此兜底报告扩大仓位。</p>
</div>'''

    parts = [f'<div class="header-card"><h2>⚠️ AI服务暂时不可用，以下为程序化安全兜底</h2><p>ClawSocket错误：{html.escape(str(error_text)[:500])}</p><p>本邮件仍展示程序计算的 Quant、技术确认、RSI 与乖离率，不伪造 AI 观点。</p></div>', '<h2>👑 核心精选 Top 1-5</h2>']
    if core:
        parts.extend(card(i, x) for i,x in enumerate(core,1))
    else:
        parts.append('<div class="header-card"><h3>今日没有达到 Core 硬门槛的标的</h3></div>')
    parts.append('<div class="compare-card"><div class="compare-title">🎖️ 观察池 - 程序化兜底</div><ul>')
    parts.extend(f'<li>{html.escape(str(x.get("Name","")))} ({html.escape(str(x.get("Ticker","")))}) | Quant:{float(x.get("Quant_Score",0) or 0):.1f}</li>' for x in obs)
    parts.append('</ul></div>')
    return "\n".join(parts)

# ==================== 13. 生成 AI 报告 ====================
def generate_ai_report(pool_data, combined_news, macro_market, dropped_info=None, embargo_text="", sector_tech_data=None, event_regime_text="", event_regime=None, market_signal_text="", key_people_text="", economic_text=""):
    print("🧠 [AI] 生成美股宏观穿透报告...")
    review_risk_text, _, review_near = get_review_risk_linkage_warning()
    client = ClawSocketClient(api_key=os.environ["CLAWSOCKET_API_KEY"], base_url=os.environ["CLAWSOCKET_BASE_URL"])
    pool_lines = []
    for x in pool_data:
        pool_lines.append(
            f"[{x['Ticker']}] {x['Name']} | ${x['Price']} | RSI:{x['RSI']} | Bias:{x['乖离率(%)']}% | MA20:{x.get('MA20')} slope5d:{x.get('MA20_Slope_Pct_5D')}% | MACD:{x['MACD趋势']} | KDJ:{x['KDJ_J']} | Vol:{x['量比']} recentVol:{x.get('近5日最大量比')} | 技术确认:{x.get('技术确认数',0)} | Quant:{x.get('Quant_Score',0)}/100 (F{x.get('Fundamental_Score',0)} E{x.get('Event_Score',0)} T{x.get('Technical_Score_25',0)} R{x.get('Risk_Liquidity_Score',0)}) | Market:{x.get('Market_Regime')} VIX:{x.get('VIX')} SectorRS20D:{x.get('Sector_RS_20D_Pct')} | 估值:{x.get('估值评分',0)}/20 | PE_F:{x.get('PE_Forward')} | EPS:{x.get('EPS_TTM')} | PB:{x.get('PB')} | 新闻:{' | '.join(x.get('个股新闻',[]))}"
        )
    evolved = load_evolved_rules()
    key_people_block = str(key_people_text or "暂无重要人物讲话数据")
    economic_block = str(economic_text or "暂无结构化美国经济数据")
    stop_warn = get_stop_loss_hit_warning()
    dropped_text = ""
    if review_risk_text:
        dropped_text += "\n【Review→Scan 风控联动】\n" + review_risk_text
    if dropped_info:
        dropped_text = "\n⚠️ 今日已因当前真实风险 Dropped：" + ", ".join(dropped_info)

    hard_avoid = ", ".join((event_regime or {}).get("hard_avoid_sectors", [])) or "无"
    prompt = f"""
【最高优先级】只从通过程序硬门槛的候选中选择；Core 最终量化分至少65，Observation最终量化分至少58。若合格数量不足，不得为了凑数放宽门槛。历史低胜率不是永久黑名单。

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

【程序化市场环境（硬门控数据）】
SPY={getattr(locals().get("market_ctx", {}), "get", lambda *_: None)("spy") if False else "见候选池逐项字段"}
VIX/Regime 与 SPY趋势已经由程序完成硬门控；候选池中的 Market/VIX/SectorRS20D 为准。

【板块表现】
{embargo_text}

【历史规则】
{evolved}

{stop_warn}
{dropped_text}

【STOP_NEAR 标的必须降权】
{", ".join(sorted(review_near)) or "无"}

【成交活跃 Top300 候选池】
{'\n'.join(pool_lines)}

【程序硬门槛（不可绕过）】
【封闭候选集】核心精选、观察池、诱多对照组都只能使用上方“成交活跃 Top300 候选池”中实际出现的 Ticker；候选池外股票即使新闻很强，也禁止出现在任何推荐位置。
- 技术确认通常至少2项；VIX≥25时至少3项。
- Quant_Score < 程序最低门槛不得进入最终推荐。
- SPY低于20日均线时，非防御行业不得进入Core。
- 行业20日相对SPY为负时不得进入Core；高波动/低流动性标的原则上剔除。
- AI评分只是辅助意见，不可覆盖程序硬门槛；最终分 = 70% Quant_Score + 30% AI评分。
- 推荐必须使用报告里真实展示的 Quant/Fundamental/Event/Technical/Risk 数据。

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
<p><span class="highlight-label bg-teal">⭐ 推荐评分:</span>评分:[XX]/100 — ...（最终评分由 Quant 70% + AI 30% 构成）</p>
<p><span class="highlight-label bg-blue">📊 量化拆解:</span>Quant:[XX]/100 | 基本面:[X]/35 | 事件:[X]/20 | 技术:[X]/25 | 风险/流动性:[X]/20 | 技术确认:[N]项 | MA20:[数值] | MA20斜率5日:[数值]% | Sector RS20D:[数值]%</p>
<p><span class="highlight-label bg-orange">⚠️ 动态风控:</span>持有:[趋势未破则继续] | 移动止损:[具体价格] | 依据:[MA20/MA50 + ATR + MACD/KDJ]</p>
<p><b>期权：</b>不要在AI正文中编造行权价、到期日、权利金、Delta或IV；真实期权策略由程序从期权链读取后统一插入。</p>
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
        out = _model_stream_text(client, model=TARGET_MODEL, max_tokens=30000, messages=[{"role":"user","content":prompt}]).replace("```html","").replace("```","").strip()
        idx = out.find("<div")
        if idx > 0:
            out = out[idx:]
        print(f"✅ AI 报告生成完成：{len(out)} 字符")
        return out
    except Exception as e:
        print(f"🚨 AI 报告失败：{type(e).__name__}: {e}")
        return "<!-- AI_UNAVAILABLE -->" + build_programmatic_fallback_report(pool_data, f"{type(e).__name__}: {e}")

# ==================== 14. Match / 写账 ====================
def match_pool_to_report(pool_data, ai_html, default_stop_loss_pct):
    ai_available = "AI_UNAVAILABLE" not in (ai_html or "")
    """
    程序验证版：AI 只负责给合格候选提供 AI_Score；候选集合、Core/Observation 标签和最终入账由程序决定。
    这样候选池外股票即使被 AI 写进 Top1-5，也不会进入 pending 或邮件 Core。
    """
    def title_hit(fragment, name, ticker):
        head = fragment[:260]
        return f"({ticker})" in head or str(name).lower() in head.lower()[:120]

    def parse_ai_score(fragment):
        sc = re.search(r'(?:评分|Score)\s*[:：]?\s*\[?(\d{1,3}(?:\.\d+)?)\]?\s*/\s*100', fragment or "", re.I)
        if not sc:
            return 60.0
        try:
            return max(0.0, min(100.0, float(sc.group(1))))
        except Exception:
            return 60.0

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

    # 保留原始 HTML，后续程序校验卡可以继续拿到 AI 的说明文本。
    core_cards = [x for x in re.split(r'(?=<div class="top-card)', core_zone) if "top-card" in x]
    obs_items = [x for x in re.split(r'(?=<li>)', obs_zone) if x.strip().startswith("<li>")]

    pool_tickers = {str(x.get("Ticker", "")).upper() for x in pool_data}
    mentioned_tickers = set(re.findall(r"\(([A-Z][A-Z0-9.\-]{1,9})\)", core_zone + "\n" + obs_zone))
    invalid_ai = sorted(t for t in mentioned_tickers if t not in pool_tickers)
    if invalid_ai:
        print(f"🚫 [AI校验] 忽略候选池外推荐：{', '.join(invalid_ai)}")

    def find_chunk(item):
        name, ticker = str(item.get("Name", "")), str(item.get("Ticker", ""))
        for chunk in core_cards:
            if title_hit(chunk, name, ticker):
                return "Core_Dragon", chunk
        for chunk in obs_items:
            if title_hit(chunk, name, ticker):
                return "Observation", chunk
        return None, None

    candidates = []
    for item in pool_data:
        ai_tag, chunk = find_chunk(item)
        ai_score = parse_ai_score(chunk) if chunk else 60.0
        quant = float(item.get("Quant_Score", 0) or 0)
        final = round(
            float(SCORING_PARAMS.get("quant_weight", 70)) / 100 * quant
            + float(SCORING_PARAMS.get("ai_weight", 30)) / 100 * ai_score,
            1,
        )
        tech_count = int(item.get("技术确认数", 0) or 0)
        gate_ok = item.get("Gate_Status") == "PASS_PRE_AI"
        core_ok = (
            ai_available
            and gate_ok
            and quant >= float(SCORING_PARAMS.get("core_min_score", 65))
            and final >= float(SCORING_PARAMS.get("core_min_score", 65))
            and tech_count >= int(SCORING_PARAMS.get("min_technical_confirmations", 2))
        )
        obs_ok = (
            gate_ok
            and quant >= float(SCORING_PARAMS.get("observation_min_score", 58))
            and final >= float(SCORING_PARAMS.get("observation_min_score", 58))
            and tech_count >= 1
        )
        if not core_ok and not obs_ok:
            continue

        out = dict(item)
        out["AI_Score"] = ai_score
        out["Final_Score"] = final
        out["Score"] = str(final)
        out["_AI_Chunk"] = chunk or ""
        out["_AI_Tag"] = ai_tag or ""
        out["Tag"] = "Core_Dragon" if core_ok else "Observation"

        if out["Tag"] == "Observation":
            out["Hold_Period"] = "观望"
            out["Stop_Loss"] = "观望"
        else:
            out["Hold_Period"] = "动态持有"
            sm = re.search(r'止损\s*[:：]\s*\[?(\$?\d+(?:\.\d+)?%?)', chunk or "")
            if sm:
                out["Stop_Loss"] = sm.group(1)
            else:
                atr = float(item.get("ATR_Pct", 5) or 5)
                pct = -max(
                    float(EXIT_PARAMS.get("atr_floor_pct", 3)),
                    min(float(EXIT_PARAMS.get("atr_ceiling_pct", 12)), atr * float(EXIT_PARAMS.get("atr_multiplier", 2)))
                )
                try:
                    out["Stop_Loss"] = "$" + str(round(float(item["Price"]) * (1 + pct / 100), 2))
                except Exception:
                    out["Stop_Loss"] = ""
        candidates.append(out)

    candidates.sort(
        key=lambda x: (
            1 if x.get("Tag") == "Core_Dragon" else 0,
            float(x.get("Final_Score", 0) or 0),
            float(x.get("Quant_Score", 0) or 0),
            int(x.get("技术确认数", 0) or 0),
        ),
        reverse=True,
    )

    core = [x for x in candidates if x.get("Tag") == "Core_Dragon"][: int(LIMIT_PARAMS.get("max_core", 5))]
    used = {x["Ticker"] for x in core}
    obs = [x for x in candidates if x.get("Tag") == "Observation" and x["Ticker"] not in used][: int(LIMIT_PARAMS.get("max_observation", 7))]
    print(f"🔒 [程序校验] Core={len(core)} / Observation={len(obs)} / AI候选池外忽略={len(invalid_ai)}")
    return core + obs


def build_verified_core_html(ai_html, verified_items):
    """用程序最终入账集合重建邮件 Core，避免 AI 候选池外股票占据 Top1-5。"""
    core_items = [x for x in verified_items if x.get("Tag") == "Core_Dragon"][: int(LIMIT_PARAMS.get("max_core", 5))]

    def fmt(v, digits=2):
        try:
            if v is None or str(v).strip() == "":
                return "N/A"
            return f"{float(v):.{digits}f}"
        except Exception:
            return str(v)

    def esc(v):
        return html.escape(str(v if v not in (None, "") else "N/A"))

    def ai_summary(chunk, label, fallback):
        if not chunk:
            return fallback
        clean = re.sub(r"<[^>]+>", " ", chunk)
        clean = re.sub(r"\s+", " ", clean).strip()
        m = re.search(re.escape(label) + r"\s*:?\s*(.{0,260})", clean, re.I)
        if m:
            return m.group(1).strip(" -—:：")
        return fallback

    cards = []
    for rank, item in enumerate(core_items, 1):
        chunk = str(item.get("_AI_Chunk", "") or "")
        news = "；".join(item.get("个股新闻", [])[:2]) if item.get("个股新闻") else "暂无最新新闻"
        logic = ai_summary(chunk, "产业链逻辑", "程序候选通过硬门槛；以程序量化数据为准。")
        tech = "、".join(map(str, item.get("技术确认信号", []) or [])) or "暂无"
        stop = item.get("Stop_Loss", "") or "N/A"
        cards.append(f"""
<div class="top-card core-card">
<div class="top-title">{rank}. {esc(item.get("Name"))} ({esc(item.get("Ticker"))}) | RSI:{esc(fmt(item.get("RSI"),1))} | 乖离率:{esc(fmt(item.get("乖离率(%)"),2))}%</div>
<p><span class="highlight-label bg-red">🔗 产业链逻辑:</span>{esc(logic)}</p>
<p><span class="highlight-label bg-green">📰 个股新闻核查:</span>{esc(news)}</p>
<p><span class="highlight-label bg-blue">📈 技术确认:</span>{esc(tech)} | 共{esc(item.get("技术确认数",0))}项</p>
<p><span class="highlight-label bg-teal">⭐ 推荐评分:</span>最终 {esc(fmt(item.get("Final_Score", item.get("Score")),1))}/100 | Quant {esc(fmt(item.get("Quant_Score"),1))} | AI {esc(fmt(item.get("AI_Score"),1))}</p>
<p><span class="highlight-label bg-blue">📊 量化拆解:</span>Quant:{esc(fmt(item.get("Quant_Score"),1))}/100 | 基本面:{esc(item.get("Fundamental_Score",0))}/35 | 事件:{esc(item.get("Event_Score",0))}/20 | 技术:{esc(item.get("Technical_Score_25",0))}/25 | 风险/流动性:{esc(item.get("Risk_Liquidity_Score",0))}/20 | 技术确认:{esc(item.get("技术确认数",0))}项 | MA20:{esc(fmt(item.get("MA20"),2))} | MA20斜率5日:{esc(fmt(item.get("MA20_Slope_Pct_5D"),3))}% | Sector RS20D:{esc(fmt(item.get("Sector_RS_20D_Pct"),2))}%</p>
<p><span class="highlight-label bg-orange">⚠️ 动态风控:</span>持有:{esc(item.get("Hold_Period","动态持有"))} | 移动止损:{esc(stop)} | ATR:{esc(fmt(item.get("ATR_Pct"),2))}% | Regime:{esc(item.get("Market_Regime","N/A"))}</p>
<p style="color:#607d8b;font-size:13px;"><b>程序校验：</b>RSI、乖离率、Quant 与技术确认均来自程序候选池；候选池外股票不会进入 Core。</p>
<p><b>期权：</b>不要在 AI 正文中编造行权价、到期日、权利金、Delta 或 IV；真实期权策略由程序从期权链读取后统一插入。</p>
</div>
""")

    verified_block = (
        '<h2>👑 核心精选（程序校验 Top 1-5）</h2>'
        + ("".join(cards) if cards else '<div class="header-card"><h3>今日没有达到 Core 硬门槛的新增标的</h3></div>')
        + '<div style="background:#eef7ee;border-left:5px solid #2e7d32;padding:10px 14px;margin:12px 0 20px 0;border-radius:6px;color:#2e7d32;">🔒 程序校验：邮件 Core 与 pending 使用同一程序候选集合；候选池外 AI 推荐已自动剔除。</div>'
    )

    start = ai_html.find("<h2>👑 核心精选 Top 1-5</h2>")
    if start < 0:
        start = ai_html.find("核心精选 Top 1-5")
    if start < 0:
        return ai_html
    obs_start = ai_html.find('class="compare-card"', start)
    if obs_start < 0:
        obs_start = ai_html.find("观察池", start)
    if obs_start < 0:
        return ai_html[:start] + verified_block
    return ai_html[:start] + verified_block + "\n" + ai_html[obs_start:]


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
    # Review 风控提醒必须确定性展示，不能依赖 AI 自己决定是否输出。
    review_risk_text, review_triggered, review_near = get_review_risk_linkage_warning()
    review_banner = build_review_risk_banner_html(review_risk_text, review_triggered, review_near)
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
    .review-risk-banner{background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #ef6c00;padding:18px 20px;margin:0 0 25px 0;border-radius:8px}
    .highlight-label{display:inline-block;font-weight:bold;color:#fff;padding:3px 8px;border-radius:4px;margin-right:6px;font-size:13px}
    .bg-red{background:#d32f2f}.bg-green{background:#2e7d32}.bg-blue{background:#1976d2}.bg-teal{background:#00897b}.bg-orange{background:#e64a19}
    </style>
    """
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>🎯 宏观驱动美股波段内参：{TARGET_REGION}</h1>{review_banner}{ai_html}<p style='text-align:center;color:#999;font-size:12px'>[END_OF_QUANT_REPORT]</p></div></body></html>"

# ==================== 17. 期权策略 ====================
def generate_option_recommendations(chosen_items):
    """仅为本次新产生的 Core_Dragon 生成可验证期权策略。"""
    created = []
    for item in chosen_items:
        if item.get("Tag") != "Core_Dragon":
            continue
        try:
            if append_option_strategy(item):
                created.append(item)
        except Exception as e:
            print(f"⚠️ {item.get('Ticker','')} 期权策略生成失败：{e}")
    print(f"🎯 Scan→Option 联动：{len(created)} 笔")
    # Scan 邮件只展示本次扫描新生成的期权建议，避免把旧期权重复冒充成今日推荐。
    recent = get_recent_option_recommendations(limit=50)
    today = today_us_str()
    today_records = [r for r in recent if str(r.get("EntryDate", ""))[:10] == today]
    return today_records, created


def build_option_recommendation_html(option_records):
    if not option_records:
        return (
            '<div style="background:#fff8e1;border:1px solid #ffe082;border-left:6px solid #ffb300;'
            'padding:18px;margin:0 0 25px 0;border-radius:8px;">'
            '<h2>🎲 美股期权实战策略</h2>'
            '<p>本次没有生成可验证的期权链策略。原因可能是：核心精选为空、'
            '45-90天到期窗口无合适合约，或行情源未提供可执行的买卖价。程序不会伪造期权报价。</p>'
            '</div>'
        )

    cards=[]
    for r in option_records:
        strategy=str(r.get("Strategy", "CALL_DEBIT_SPREAD"))
        spread=(f"{r.get('LongStrike')} / {r.get('ShortStrike')}" if r.get('ShortStrike') else f"{r.get('LongStrike')}")
        max_profit = r.get("MaxProfit") or "未限制"
        cards.append(
            '<div style="background:#fafafa;border:1px solid #e0e0e0;border-left:6px solid #7b1fa2;'
            'padding:16px;margin:0 0 12px 0;border-radius:8px;">'
            f'<div style="font-size:17px;font-weight:800;">🎯 {html.escape(str(r.get("Name", r.get("Ticker", ""))))} ({html.escape(str(r.get("Ticker", "")))})'
            f'｜{html.escape(strategy)}</div>'
            f'<div><b>到期日：</b>{html.escape(str(r.get("Expiry","N/A")))}（{html.escape(str(r.get("DTE","N/A")))}天）'
            f'　<b>执行价：</b>{html.escape(spread)}</div>'
            f'<div><b>权利金：</b>${html.escape(str(r.get("NetDebit","N/A")))}／股'
            f'　<b>最大风险：</b>${html.escape(str(r.get("MaxLoss","N/A")))}'
            f'　<b>盈亏平衡：</b>${html.escape(str(r.get("BreakEven","N/A")))}</div>'
            f'<div><b>Delta：</b>{html.escape(str(r.get("Delta","N/A")))}'
            f'　<b>IV：</b>{html.escape(str(r.get("IV","N/A")))}'
            f'　<b>IV状态：</b>{html.escape(str(r.get("IV_Regime","N/A")))}</div>'
            f'<div><b>Call Wall：</b>${html.escape(str(r.get("CallWall","N/A")))}'
            f'　<b>Put Wall：</b>${html.escape(str(r.get("PutWall","N/A")))}</div>'
            f'<div><b>财报：</b>{html.escape(str(r.get("EarningsDate","未确认")))}'
            f'　<b>事件距离：</b>{html.escape(str(r.get("EarningsDays","N/A")))}天</div>'
            f'<div><b>策略逻辑：</b>{html.escape(str(r.get("Reason","")))}</div>'
            '<div><b>仓位纪律：</b>1张起步；最大亏损以实际支付权利金为边界；若正股趋势破坏，Review重新评估。</div>'
        )
    return (
        '<h2 style="color:#7b1fa2;border-bottom:2px solid #7b1fa2;padding-bottom:6px;">🎲 美股期权实战策略</h2>'
        '<p style="color:#607d8b;">只展示程序从期权链中取得的真实合约与报价，不用AI虚构行权价或到期日。</p>'
        + ''.join(cards)
    )


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

    client = ClawSocketClient(api_key=os.environ["CLAWSOCKET_API_KEY"], base_url=os.environ["CLAWSOCKET_BASE_URL"])
    signal_analysis = analyze_market_signals(combined_news, client)
    signal_block = build_market_signal_text(signal_analysis)
    market_signal_text = signal_block[0] if signal_block else ""

    restricted_tickers, dropped_info, current_prices = pre_scan_portfolio_review(combined_news, macro_market)
    review_risk_text, review_triggered, review_near = get_review_risk_linkage_warning()
    restricted_tickers = set(restricted_tickers) | set(review_triggered)
    raw_tickers = get_scan_pool()
    pool_tickers = {t:n for t,n in raw_tickers.items() if t not in restricted_tickers}
    pool_data = build_stock_pool(pool_tickers)
    if not pool_data:
        empty = build_full_email_html('<div class="header-card"><h2>⚠️ 今日扫描无有效标的</h2><p>行情/技术数据不足，安全退出。</p></div>')
        send_mail(SUPER_ADMIN, f"【美股扫描】{today_us_str()} 无有效标的", empty)
        sys.exit(0)

    sector_tech_data = screen_technical_setups(pool_data)
    pool_data = enrich_pool_with_fundamentals(pool_data, limit=120)
    pool_data = enrich_pool_with_news(pool_data)
    market_ctx = get_market_regime_context()
    pool_data = apply_market_context_to_pool(pool_data, market_ctx)
    for _item in pool_data:
        score_candidate_quality(_item, market_ctx)
    pool_data = apply_entry_quality_gate(pool_data, market_ctx, event_regime)
    if not pool_data:
        empty = build_full_email_html('<div class="header-card"><h2>⚠️ 今日硬门槛后暂无合格新标的</h2><p>技术确认、市场环境、相对强弱或量化评分未达到准入标准；不为了凑满推荐数量而放宽条件。</p></div>')
        send_mail(SUPER_ADMIN, f"【美股扫描】{today_us_str()} 硬门槛后无合格新标的", empty)
        sys.exit(0)

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

    chosen = match_pool_to_report(pool_data, ai_html, DEFAULT_STOP_LOSS_PCT)

    # 安全兜底：绝不再用旧的“技术 Top10 强行凑 Core”逻辑绕过硬门槛。
    # match_pool_to_report 已经对所有程序候选执行统一 Core/Observation 准入。
    if not chosen:
        print("⚠️ 程序候选经过硬门槛后没有达到 Core/Observation 最低线，不凑数。")

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
                item["Score"] = str(round(0.7*float(item.get("Quant_Score",0)) + 0.3*float(item.get("AI_Score",60) or 60),1))
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

    # 关键：先完成“实际入账集合”的确定，再用同一集合渲染邮件 Core。
    # 因此候选池外 AI 推荐、历史持仓去重等都不会再导致邮件与 pending 分裂。
    ai_html = build_verified_core_html(ai_html, to_write)

    if to_write:
        pending_file = f"us_stocks_pending_{get_us_time().strftime('%Y%m%d')}.csv"
        header_cols = [
            "Date","Ticker","Name","Tag","RSI","Bias","技术评分","技术确认数","技术确认信号","估值评分","PE_TTM","PE_Forward","EPS_TTM","PB","Revenue_Growth","Earnings_Growth","ROE","Profit_Margin","Market_Cap","Avg_Dollar_Volume_20D","Fundamental_Score","Event_Score","Technical_Score_25","Risk_Liquidity_Score","Quant_Score","AI_Score","Final_Score","MACD金叉","周线共振","KDJ_J回升","量能放大","近5日放量阳线","Hold_Period","Stop_Loss","Stop_Method","Score","Status","Scan_Ref_Price","ATR_Pct","周期共振","Sector_RS_20D_Pct","Market_Regime","VIX"
        ]
        with open(pending_file,"w",encoding="utf-8",newline="") as f:
            f.write(",".join(header_cols)+"\n")
            for item in to_write:
                vals = [
                    today_us_str(), item.get("Ticker",""), item.get("Name",""), item.get("Tag",""),
                    item.get("RSI",""), item.get("乖离率(%)",""), item.get("技术评分",0), item.get("技术确认数",0), ",".join(item.get("技术确认信号",[]) or []), item.get("估值评分",0),
                    item.get("PE_TTM",""), item.get("PE_Forward",""), item.get("EPS_TTM",""), item.get("PB",""), item.get("Revenue_Growth",""), item.get("Earnings_Growth",""), item.get("ROE",""), item.get("Profit_Margin",""), item.get("Market_Cap",""), item.get("Avg_Dollar_Volume_20D",""),
                    item.get("Fundamental_Score",0), item.get("Event_Score",0), item.get("Technical_Score_25",0), item.get("Risk_Liquidity_Score",0), item.get("Quant_Score",0), item.get("AI_Score",60), item.get("Final_Score",item.get("Score","")),
                    item.get("MACD金叉",False), item.get("周线共振",False), item.get("KDJ_J回升",False), item.get("量能放大",False), item.get("近5日放量阳线",False), item.get("Hold_Period","动态持有"),
                    item.get("Stop_Loss",""), item.get("Stop_Method","ATR初始保护"), item.get("Score",""), "pending", item.get("Price",item.get("Open_Price","")), item.get("ATR_Pct",""), item.get("周期共振",False), item.get("Sector_RS_20D_Pct",""), item.get("Market_Regime",""), item.get("VIX","")
                ]
                safe_vals = [str(v).replace(","," ").replace("\n"," ") for v in vals]
                f.write(",".join(safe_vals)+"\n")
        print(f"✅ 已生成 {len(to_write)} 条美股待确认记录：{pending_file}")
    else:
        print("⚠️ 今日没有新增可入账推荐")

    option_records, option_created_items = generate_option_recommendations(to_write)
    option_html = build_option_recommendation_html(option_records)
    full_html = build_full_email_html(ai_html + option_html)
    send_mail(SUPER_ADMIN, f"【宏观驱动美股版】{TARGET_REGION} 核心打分、股票与期权实战 ({today_us_str()})", full_html)

    print("🎯 美股盘前扫描完成。")
