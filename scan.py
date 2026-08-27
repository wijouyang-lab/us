# -*- coding: utf-8 -*-
"""
美股盘前扫描引擎（修复版）
- 修复写账过滤导致推荐被丢弃的问题
- 观察池强制写入，不再要求三字段完整
- 评分解析失败时自动兜底
- 移除 API temperature 参数
"""

import faulthandler
faulthandler.enable()
import pandas as pd
import pandas_ta as ta
import datetime
import os
import smtplib
import time
import re
import random
import requests
import yfinance as yf
import io
import hashlib
import email.utils
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
import sys

# ==================== 环境与时间检查 ====================
today = datetime.datetime.now().weekday()
if today >= 5:
    print(f"[{datetime.datetime.now()}] 周末休市，脚本自动跳过。")
    exit()

TARGET_MODEL = 'claude-opus-4-8'
TARGET_REGION = "美国市场"
DEFAULT_STOP_LOSS_PCT = -5.0
ATR_STOP_MULTIPLIER = 2.0
ATR_STOP_FLOOR_PCT = 3.0
ATR_STOP_CEIL_PCT = 12.0

SUPER_ADMIN = os.environ.get("TARGET_EMAILS")
if not SUPER_ADMIN:
    print("致命错误：未检测到 TARGET_EMAILS！")
    exit(1)

_missing_env = [k for k in ("CLAWSOCKET_API_KEY", "CLAWSOCKET_BASE_URL") if not os.environ.get(k)]
if _missing_env:
    print(f"致命错误：未检测到环境变量 {', '.join(_missing_env)}！")
    exit(1)

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
        today_str = datetime.datetime.now().strftime('%Y-%m-%d')
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(f"{current_hash},{today_str}")
        print(f"📌 检测到 scan.py 变化，新版本起始日期: {today_str}")
    else:
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                existing = f.read().strip()
            version_date = existing.split(",")[1] if "," in existing else "未知"
            print(f"📌 scan.py 版本未变，起始日期: {version_date}")
        except Exception:
            pass
update_version_marker()

# ==================== 工具函数 ====================
def get_robust_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.yahoo.com/"
    })
    return session

# ==================== 1. 宏观新闻 ====================
def get_latest_macro_news():
    print("正在抓取 CNBC/Reuters 英文财经快讯...")
    import xml.etree.ElementTree as ET
    def _parse_rss_date(date_str):
        if not date_str:
            return None
        try:
            dt = email.utils.parsedate_to_datetime(date_str.strip())
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc)
        except Exception:
            return None
    def _get_news_age_tag(date_str):
        dt = _parse_rss_date(date_str)
        if dt is None:
            return "[时间未知]"
        now = datetime.datetime.now(datetime.timezone.utc)
        delta_hours = (now - dt).total_seconds() / 3600
        if delta_hours <= 6:
            return "[🔥今日最新-权重最高]"
        elif delta_hours <= 24:
            return "[📰今日-高权重]"
        elif delta_hours <= 48:
            return "[📄昨日-中等权重]"
        elif delta_hours <= 72:
            return "[📑前日-低权重]"
        else:
            return None
    sources = [
        ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
        ("Reuters", "https://feeds.reuters.com/reuters/businessNews"),
        ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ]
    session = get_robust_session()
    news_lines = []
    skipped_old = 0
    for source_name, url in sources:
        try:
            response = session.get(url, timeout=10)
            root = ET.fromstring(response.content)
            items = root.findall('.//item')[:12]
            for item in items:
                title = item.find('title')
                pub_date = item.find('pubDate')
                if title is not None:
                    time_str = pub_date.text[:25] if pub_date is not None else ""
                    age_tag = _get_news_age_tag(time_str)
                    if age_tag is None:
                        skipped_old += 1
                        continue
                    news_lines.append(f"{age_tag}[{source_name}] {time_str[:16]} - {title.text}")
        except Exception as e:
            print(f"⚠️ {source_name} 抓取失败: {e}")
    if skipped_old > 0:
        print(f"📰 过滤掉 {skipped_old} 条超过72小时的旧新闻")
    if news_lines:
        print(f"✅ 成功抓取 {len(news_lines)} 条宏观财经快讯")
        return "\n".join(news_lines)
    return "暂无实时英文财经新闻，请基于昨收盘及底层产业逻辑进行推演。"

def get_megacap_breaking_news():
    MEGACAP_TICKERS = {
        "META": "Meta（算力/AI/社交）",
        "NVDA": "NVIDIA（GPU/AI芯片）",
        "MSFT": "Microsoft（Azure/AI/云）",
        "GOOGL": "Alphabet（云/AI/搜索）",
        "AMZN": "Amazon（AWS/电商/AI）",
        "AAPL": "Apple（消费电子/芯片）",
        "TSLA": "Tesla（电动车/AI/储能）",
        "AMD": "AMD（CPU/GPU/数据中心）",
        "INTC": "Intel（代工/PC芯片）",
        "MU": "Micron（内存/HBM）",
    }
    cutoff_ts = time.time() - 36 * 3600
    news_lines = []
    fetched = 0
    for ticker, desc in MEGACAP_TICKERS.items():
        try:
            raw_news = yf.Ticker(ticker).news or []
            for item in raw_news[:8]:
                pub_ts = item.get("providerPublishTime", 0)
                if pub_ts < cutoff_ts:
                    continue
                title = item.get("title", "").strip()
                publisher = item.get("publisher", "").strip()
                if not title:
                    continue
                pub_time = datetime.datetime.fromtimestamp(pub_ts).strftime("%m-%d %H:%M")
                news_lines.append(f"[{ticker}/{desc}] [{publisher}] {pub_time} — {title}")
                fetched += 1
            time.sleep(random.uniform(0.2, 0.5))
        except Exception as e:
            print(f"⚠️ {ticker} 新闻抓取失败: {e}")
    if news_lines:
        print(f"✅ mega-cap 公司新闻：抓取 {fetched} 条（过去36小时内）")
        return "\n".join(news_lines)
    return ""

# ==================== 2. 宏观市场数据 ====================
def get_macro_market_data():
    print("正在拉取全球大宗商品与美债收益率等核心宏观数据...")
    macro_tickers = {
        "美10年国债收益率": "^TNX",
        "美2年国债收益率": "^IRX",
        "恐慌指数VIX": "^VIX",
        "黄金期货": "GC=F",
        "白银期货": "SI=F",
        "高级铜期货": "HG=F",
        "WTI原油期货": "CL=F",
        "布伦特原油期货": "BZ=F",
        "标普500指数": "^GSPC",
        "纳斯达克指数": "^IXIC"
    }
    lines = []
    vix_value = None
    for name, ticker in macro_tickers.items():
        try:
            df = yf.download(ticker, period="5d", progress=False)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                latest_close = df['Close'].iloc[-1]
                prev_close = df['Close'].iloc[-2]
                pct_change = ((latest_close - prev_close) / prev_close) * 100
                if ticker == "^VIX":
                    vix_value = float(latest_close)
                if "^" in ticker and "VIX" not in name and "指数" not in name:
                    lines.append(f"- {name} ({ticker}): 当前收益率 {round(latest_close, 3)}% | 当日变动幅度: {round(pct_change, 2)}%")
                else:
                    lines.append(f"- {name} ({ticker}): 当前价/值 {round(latest_close, 2)} | 当日涨跌幅: {round(pct_change, 2)}%")
        except Exception as e:
            print(f"⚠️ 宏观因子 {name}({ticker}) 抓取受阻: {e}")
    if lines:
        print(f"✅ 成功提取 {len(lines)} 项全球关键宏观底层指标数据")
        guidance = ("\n【使用提示】以上大宗商品数据对不同行业相关性差异很大：原油/WTI/Brent"
                    "主要影响Energy（能源）及部分Industrials/Materials行业，对Technology、"
                    "Healthcare、Consumer等多数行业相关性很低，请结合每支标的自己的行业分类"
                    "判断，不要不分行业地把油价波动同等代入所有个股的评分。")
        if vix_value is not None:
            if vix_value >= 30:
                guidance += (f"\n【VIX风控提示】当前VIX={round(vix_value,1)}，处于极度恐慌区间"
                             f"（>=30）。这种环境下追高型/突破型技术形态失败率显著偏高，"
                             f"请大幅提高评分门槛，优先考虑防御性板块或明确的超跌反转设置，"
                             f"减少激进追涨型推荐的数量。")
            elif vix_value >= 25:
                guidance += (f"\n【VIX风控提示】当前VIX={round(vix_value,1)}，处于偏高波动区间"
                             f"（>=25）。请相应提高评分门槛，对追高型技术形态更加谨慎。")
        return "\n".join(lines) + guidance
    return "暂无实时大宗商品与国债收益率宏观数据。"

# ==================== 3. 个股新闻 ====================
def get_stock_news(ticker, max_items=6):
    import xml.etree.ElementTree as ET
    session = get_robust_session()
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    try:
        response = session.get(url, timeout=8)
        root = ET.fromstring(response.content)
        items = root.findall('.//item')[:max_items + 5]
        headlines = []
        for item in items:
            title = item.find('title')
            pub_date = item.find('pubDate')
            if title is not None and title.text:
                age_tag = ""
                if pub_date is not None and pub_date.text:
                    try:
                        dt = email.utils.parsedate_to_datetime(pub_date.text.strip())
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=datetime.timezone.utc)
                        now = datetime.datetime.now(datetime.timezone.utc)
                        delta_hours = (now - dt).total_seconds() / 3600
                        if delta_hours <= 6:
                            age_tag = "[🔥最新]"
                        elif delta_hours <= 24:
                            age_tag = "[📰今日]"
                        elif delta_hours <= 48:
                            age_tag = "[📄昨日]"
                        elif delta_hours <= 72:
                            age_tag = "[📑前日]"
                        else:
                            continue
                    except Exception:
                        age_tag = ""
                headlines.append(f"{age_tag}{title.text.strip()}")
        return headlines[:max_items]
    except Exception:
        return []

def enrich_pool_with_news(pool):
    print(f"正在抓取 {len(pool)} 只标的的个股新闻...")
    for item in pool:
        ticker = item['Ticker']
        headlines = get_stock_news(ticker)
        item['个股新闻'] = headlines if headlines else ["暂无最新新闻"]
        time.sleep(random.uniform(0.5, 1.5))
    print("✅ 个股新闻补充完毕")
    return pool

# ==================== 4. 获取美股标的池 ====================
def get_scan_pool():
    print("正在通过维基百科获取三大指数 (标普500, 纳指100, 道指) 标的池...")
    session = get_robust_session()
    def fetch_wiki_tickers(url):
        try:
            html = session.get(url, timeout=15).text
            tables = pd.read_html(io.StringIO(html))
            for df in tables:
                sym_col = next((col for col in df.columns if col in ['Symbol', 'Ticker', 'Ticker symbol']), None)
                name_col = next((col for col in df.columns if col in ['Security', 'Company', 'Name']), None)
                if sym_col and name_col:
                    symbols = df[sym_col].astype(str).tolist()
                    names = df[name_col].astype(str).tolist()
                    return {s.replace('.', '-'): n for s, n in zip(symbols, names)}
        except Exception as e:
            print(f"抓取 {url.split('/')[-1]} 失败: {e}")
        return {}
    sp500 = fetch_wiki_tickers('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    ndx100 = fetch_wiki_tickers('https://en.wikipedia.org/wiki/Nasdaq-100')
    dji = fetch_wiki_tickers('https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average')
    all_tickers_dict = {**sp500, **ndx100, **dji}
    tickers_list = list(all_tickers_dict.keys())
    if not tickers_list:
        print("维基百科拉取受限，启用备用核心池...")
        return {"NVDA": "NVIDIA", "AAPL": "Apple", "MSFT": "Microsoft", "TSLA": "Tesla"}
    print(f"✅ 成功获取三大指数共 {len(tickers_list)} 只去重标的。正在获取今日成交量，过滤出 Top 60...")
    data = yf.download(tickers_list, period="1d", group_by='ticker', auto_adjust=True, progress=False)
    vols = {}
    for t in tickers_list:
        try:
            if len(tickers_list) == 1:
                vol = data['Volume'].iloc[-1]
            else:
                vol = data[t]['Volume'].iloc[-1]
            if pd.notna(vol):
                vols[t] = vol
        except:
            continue
    top_60 = pd.Series(vols).nlargest(60).index.tolist()
    final_dict = {t: all_tickers_dict[t] for t in top_60}
    return final_dict

# ==================== 5. 技术指标计算 ====================
def get_kline_data(ts_code):
    for attempt in range(3):
        try:
            df = yf.download(ts_code, period="6mo", progress=False)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.index.name = 'Date'
                return df
        except Exception:
            time.sleep(random.uniform(1, 3))
    return pd.DataFrame()

def build_stock_pool(tickers):
    pool = []
    print(f"正在计算技术面参考数据，扫描 {len(tickers)} 只标的...")
    for ts_code, name in tickers.items():
        try:
            df = get_kline_data(ts_code)
            if df is None or df.empty or len(df) < 40:
                continue
            df['MACDh'] = ta.macd(df['Close']).iloc[:, 1]
            df['RSI']   = ta.rsi(df['Close'], length=14)
            df['MA20']  = ta.sma(df['Close'], length=20)
            df['ATR']   = ta.atr(df['High'], df['Low'], df['Close'], length=14)
            df = df.dropna()
            if len(df) < 6:
                continue
            latest, prev = df.iloc[-1], df.iloc[-2]
            bias       = (latest['Close'] - latest['MA20']) / latest['MA20']
            h_last     = float(latest['MACDh'])
            h_prev     = float(prev['MACDh'])
            h_prev2    = float(df.iloc[-3]['MACDh'])
            daily_v_reverse = (h_prev2 > h_prev) and (h_prev < h_last)
            macd_trend = "走强" if h_last > h_prev else "走弱"
            daily_macd_rising = h_last > h_prev
            macd_df    = ta.macd(df['Close'])
            macd_line  = macd_df.iloc[:, 0]
            signal_line= macd_df.iloc[:, 2]
            macd_cross = False
            macd_green_shrink = False
            if len(macd_line) >= 3:
                macd_cross = bool(
                    float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) and
                    float(macd_line.iloc[-2]) <= float(signal_line.iloc[-2])
                )
                macd_green_shrink = bool(
                    h_last < 0 and h_last > h_prev and h_prev < h_prev2
                )
            weekly_bullish = False
            weekly_macd_rising = False
            weekly_v_reverse = False
            try:
                df_w = yf.download(ts_code, period="1y", interval="1wk", progress=False, auto_adjust=True)
                if df_w is not None and not df_w.empty and len(df_w) >= 12:
                    if isinstance(df_w.columns, pd.MultiIndex):
                        df_w.columns = df_w.columns.get_level_values(0)
                    w_close = df_w['Close'].values.astype(float)
                    wma5  = float(pd.Series(w_close).rolling(5).mean().iloc[-1])
                    wma10 = float(pd.Series(w_close).rolling(10).mean().iloc[-1])
                    w_exp1 = pd.Series(w_close).ewm(span=12, adjust=False).mean()
                    w_exp2 = pd.Series(w_close).ewm(span=26, adjust=False).mean()
                    w_hist = ((w_exp1 - w_exp2) - (w_exp1 - w_exp2).ewm(span=9, adjust=False).mean()) * 2
                    w_hist_rising = float(w_hist.iloc[-1]) > float(w_hist.iloc[-2])
                    weekly_bullish = bool(wma5 > wma10 and w_hist_rising)
                    weekly_macd_rising = w_hist_rising
                    if len(w_hist) >= 3:
                        w_last  = float(w_hist.iloc[-1])
                        w_prev  = float(w_hist.iloc[-2])
                        w_prev2 = float(w_hist.iloc[-3])
                        weekly_v_reverse = (w_prev2 > w_prev) and (w_prev < w_last)
            except Exception:
                pass
            # KDJ
            closes = df['Close'].values.astype(float)
            highs  = df['High'].values.astype(float)
            lows   = df['Low'].values.astype(float)
            K, D   = 50.0, 50.0
            j_list = []
            for i in range(len(closes)):
                if i < 8:
                    j_list.append(3 * K - 2 * D)
                    continue
                h9  = max(highs[i-8: i+1])
                l9  = min(lows[i-8:  i+1])
                rsv = (closes[i] - l9) / (h9 - l9 + 1e-9) * 100
                K   = 2/3 * K + 1/3 * rsv
                D   = 2/3 * D + 1/3 * K
                j_list.append(3 * K - 2 * D)
            j_last, j_prev, j_prev2 = j_list[-1], j_list[-2], j_list[-3]
            kdj_j_rising   = bool(j_last < 80 and j_last > j_prev and j_prev <= j_prev2)
            kdj_j_oversold = bool(j_prev2 < 20)
            vols      = df['Volume'].values.astype(float)
            avg5      = float(pd.Series(vols[:-1]).tail(5).mean())
            vol_today = float(vols[-1])
            vol_ratio = round(vol_today / (avg5 + 1e-9), 2)
            vol_surge = bool(avg5 > 0 and vol_today >= avg5 * 1.3)
            opens_arr = df['Open'].values.astype(float)
            o, c      = opens_arr[-1], closes[-1]
            o1, c1    = opens_arr[-2], closes[-2]
            h_c, l_c  = highs[-1], lows[-1]
            body      = abs(c - o)
            rng       = h_c - l_c + 1e-9
            lower_shd = min(o, c) - l_c
            upper_shd = h_c - max(o, c)
            patterns  = []
            if c1 < o1 and c > o and o <= c1 and c >= o1:
                patterns.append("看涨吞没")
            if body / rng < 0.35 and lower_shd >= 2 * body and upper_shd <= body * 0.5:
                patterns.append("锤子线")
            if c1 < o1 and c > o and o < c1 and c > (o1 + c1) / 2 and c < o1:
                patterns.append("刺穿线")
            if len(opens_arr) >= 3:
                o2, c2 = opens_arr[-3], closes[-3]
                if abs(c2-o2) > rng*0.3 and c2 < o2 and abs(c1-o1) < abs(c2-o2)*0.4 and c > o and c > (o2+c2)/2:
                    patterns.append("启明星")
            clean_ticker = ts_code.split('.')[0] if '.' in ts_code else ts_code
            pool.append({
                "Ticker":          clean_ticker,
                "ts_code":         ts_code,
                "Name":            name,
                "Price":           round(latest['Close'], 2),
                "Open_Price":      round(latest['Open'], 2),
                "RSI":             round(latest['RSI'], 1),
                "ATR_Pct":         round((float(latest['ATR']) / float(latest['Close'])) * 100, 2) if latest['Close'] else 5.0,
                "乖离率(%)":       round(bias * 100, 2),
                "MACD趋势":        macd_trend,
                "MACD_HIST_LAST":  round(h_last, 4),
                "MACD_HIST_PREV":  round(h_prev, 4),
                "MACD金叉":        macd_cross,
                "MACD绿柱缩短":    macd_green_shrink,
                "周线共振":        weekly_bullish,
                "KDJ_J":           round(j_last, 2),
                "KDJ_J回升":       kdj_j_rising,
                "KDJ_J超卖":       kdj_j_oversold,
                "量能放大":        vol_surge,
                "量比":            vol_ratio,
                "看涨形态":        patterns,
                "日线MACD上升": daily_macd_rising,
                "周线MACD上升": weekly_macd_rising,
                "日线MACD_V型反转": daily_v_reverse,
                "周线MACD_V型反转": weekly_v_reverse,
            })
        except Exception:
            continue
        finally:
            time.sleep(random.uniform(0.3, 0.7))
    print(f"✅ 技术面数据计算完毕，共 {len(pool)} 只标的进入新闻+逻辑分析阶段。")
    return pool

# ==================== 6. 板块映射 ====================
_US_SECTOR_MAP = {
    "AAPL":"Technology","MSFT":"Technology","NVDA":"Technology","AMD":"Technology",
    "INTC":"Technology","AVGO":"Technology","QCOM":"Technology","TXN":"Technology",
    "MU":"Technology","AMAT":"Technology","LRCX":"Technology","KLAC":"Technology",
    "MRVL":"Technology","ON":"Technology","PLTR":"Technology","PANW":"Technology",
    "CRWD":"Technology","ZS":"Technology","FTNT":"Technology","DDOG":"Technology",
    "CRM":"Technology","ORCL":"Technology","SNOW":"Technology","NOW":"Technology",
    "META":"Communication","GOOGL":"Communication","GOOG":"Communication",
    "NFLX":"Communication","DIS":"Communication","T":"Communication","VZ":"Communication",
    "AMZN":"Consumer Discretionary","TSLA":"Consumer Discretionary",
    "HD":"Consumer Discretionary","MCD":"Consumer Discretionary",
    "NKE":"Consumer Discretionary","BKNG":"Consumer Discretionary",
    "WMT":"Consumer Staples","COST":"Consumer Staples","PG":"Consumer Staples",
    "KO":"Consumer Staples","PEP":"Consumer Staples",
    "JPM":"Financials","BAC":"Financials","WFC":"Financials","GS":"Financials",
    "MS":"Financials","V":"Financials","MA":"Financials","PYPL":"Financials",
    "LLY":"Healthcare","JNJ":"Healthcare","UNH":"Healthcare","MRK":"Healthcare",
    "ABBV":"Healthcare","PFE":"Healthcare","AMGN":"Healthcare","GILD":"Healthcare",
    "MRNA":"Healthcare","REGN":"Healthcare","VRTX":"Healthcare",
    "GE":"Industrials","HON":"Industrials","CAT":"Industrials","RTX":"Industrials",
    "LMT":"Industrials","BA":"Industrials","NOC":"Industrials","GD":"Industrials",
    "XOM":"Energy","CVX":"Energy","COP":"Energy","SLB":"Energy","OXY":"Energy",
    "LIN":"Materials","NEM":"Materials","FCX":"Materials",
    "AMT":"Real Estate","PLD":"Real Estate","EQIX":"Real Estate",
    "NEE":"Utilities","DUK":"Utilities","POWL":"Utilities","VRT":"Utilities",
    "COIN":"Financials","ARM":"Technology","SMCI":"Technology","VST":"Utilities",
}

# ==================== 7. 周期共振与评分 ====================
def check_period_resonance(stock):
    daily_rising = stock.get("日线MACD上升", False)
    weekly_rising = stock.get("周线MACD上升", False)
    if not daily_rising or not weekly_rising:
        return False, []
    patterns = stock.get("看涨形态", [])
    valid_patterns = ["看涨吞没", "启明星", "刺穿线", "锤子线"]
    matched = [p for p in patterns if p in valid_patterns]
    if not matched:
        return False, []
    return True, matched

def screen_technical_setups(pool_data):
    sector_groups = {}
    for stock in pool_data:
        tech_score   = 0
        tech_reasons = []
        is_resonance, resonance_patterns = check_period_resonance(stock)
        stock["周期共振"] = is_resonance
        stock["共振形态"] = resonance_patterns
        if stock.get("MACD金叉"):
            h_last = stock.get("MACD_HIST_LAST", 0)
            if h_last < -0.5:
                tech_score += 18
                tech_reasons.append(f"MACD零轴下金叉底背离({h_last:.2f})(+18)")
            elif abs(h_last) <= 0.5:
                tech_score += 14
                tech_reasons.append(f"MACD零轴附近金叉({h_last:.2f})(+14)")
            else:
                tech_score += 6
                tech_reasons.append(f"⚠️MACD高位金叉({h_last:.2f})(+6)")
        elif stock.get("MACD绿柱缩短"):
            h_last = stock.get("MACD_HIST_LAST", 0)
            h_prev = stock.get("MACD_HIST_PREV", 0)
            if h_last < 0 and abs(h_last) < abs(h_prev) * 0.85:
                tech_score += 12
                tech_reasons.append("MACD绿柱快速收敛(+12)")
            else:
                tech_score += 8
                tech_reasons.append("MACD绿柱初现缩短(+8)")
        elif stock.get("MACD趋势") == "走强" and stock.get("MACD_HIST_LAST", 0) > 0:
            h_last = stock.get("MACD_HIST_LAST", 0)
            if h_last > 3:
                tech_score += 2
                tech_reasons.append(f"⚠️MACD红柱高位({h_last:.2f})(+2)")
            else:
                tech_score += 4
                tech_reasons.append(f"MACD红柱走强({h_last:.2f})(+4)")
        j_val      = stock.get("KDJ_J", 50)
        j_rising   = stock.get("KDJ_J回升", False)
        j_oversold = stock.get("KDJ_J超卖", False)
        if j_rising:
            if j_oversold or j_val < 20:
                tech_score += 10
                tech_reasons.append(f"KDJ超卖回头J={j_val:.0f}(+10)")
            elif j_val < 50:
                tech_score += 7
                tech_reasons.append(f"KDJ低位回升J={j_val:.0f}(+7)")
            else:
                tech_score += 3
                tech_reasons.append(f"KDJ中位回升J={j_val:.0f}(+3)")
        vol_ratio = stock.get("量比", 1.0)
        if stock.get("量能放大"):
            pts = 10 if vol_ratio >= 2.0 else 7
            tech_score += pts
            tech_reasons.append(f"量比{vol_ratio:.1f}倍放量(+{pts})")
        patterns = stock.get("看涨形态", [])
        if patterns:
            score_map = {"看涨吞没": 5, "启明星": 5, "刺穿线": 4, "锤子线": 3}
            base = max(score_map.get(p, 2) for p in patterns)
            tech_score += base
            tech_reasons.append(f"{'&'.join(patterns)}形态(+{base})")
        weekly = stock.get("周线共振", False)
        if weekly:
            tech_score = min(int(tech_score * 1.25), 40)
            tech_reasons.append("✅周日共振加成×1.25")
        elif tech_score > 0:
            tech_score = int(tech_score * 0.6)
            tech_reasons.append("⚠️周线逆势惩罚×0.6")
        tech_score = min(tech_score, 40)
        daily_v = stock.get("日线MACD_V型反转", False)
        weekly_v = stock.get("周线MACD_V型反转", False)
        if daily_v and weekly_v:
            tech_score = min(tech_score + 20, 40)
            tech_reasons.append("🔥日周双V型反转共振(+20)")
        elif daily_v:
            tech_score = min(tech_score + 8, 40)
            tech_reasons.append("日线V型反转(+8)")
        elif weekly_v:
            tech_score = min(tech_score + 4, 40)
            tech_reasons.append("周线V型反转(+4)")
        if is_resonance:
            tech_score = min(tech_score + 15, 40)
            tech_reasons.append("🔥周期共振(+15)")
        stock["技术评分"]  = tech_score
        stock["技术信号"]  = tech_reasons
        stock["周线共振"]  = weekly
        sector = _US_SECTOR_MAP.get(stock.get("Ticker",""), "Other")
        sector_groups.setdefault(sector, []).append({
            "名称": stock["Name"], "代码": stock["Ticker"],
            "技术评分": tech_score, "技术信号": tech_reasons,
        })
    sector_summary = {
        sec: sorted(stks, key=lambda x: x["技术评分"], reverse=True)
        for sec, stks in sector_groups.items()
        if any(s["技术评分"] > 0 for s in stks)
    }
    top_tech = sorted(pool_data, key=lambda x: x.get("技术评分",0), reverse=True)[:10]
    print("📊 [技术筛选] Top10技术评分：")
    for s in top_tech:
        if s.get("技术评分", 0) > 0:
            weekly_tag = "🟢周日共振" if s.get("周线共振") else "🔴仅日线"
            print(f"   {s['Name']}({s['Ticker']}) 技术{s['技术评分']}分 {weekly_tag} | {' + '.join(s.get('技术信号',[]))}")
    return sector_summary

# ==================== 8. 盘前持仓审查（阶段0） ====================
def pre_scan_portfolio_review(macro_news_text, macro_market_text):
    log_file = "trade_history.csv"
    if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
        print("📌 交易账本不存在或为空，自动跳过盘前现有持仓审查。")
        return set(), {}, {}
    try:
        df = pd.read_csv(log_file, keep_default_na=False)
    except Exception as e:
        print(f"⚠️ 读取 trade_history.csv 失败: {e}")
        return set(), {}, {}
    required_cols = ["Exit_Date", "Exit_Price", "Status"]
    headers_need_rewrite = False
    for col in required_cols:
        if col not in df.columns:
            df[col] = "Active" if col == "Status" else "N/A"
            headers_need_rewrite = True
    for col in ["Exit_Date", "Exit_Price"]:
        df[col] = df[col].astype(object)
    if headers_need_rewrite:
        df.to_csv(log_file, index=False, encoding="utf-8")
    active_rows = df[df['Status'] == 'Active'].copy()
    if active_rows.empty:
        print("📌 当前无可执行风控追踪的活跃持仓标的。")
        return set(), {}, {}
    _INVALID_P0 = {'', 'n/a', 'nan', 'none'}
    for _col in ['Hold_Period', 'Stop_Loss', 'Score']:
        if _col not in active_rows.columns:
            active_rows[_col] = ''
    _valid_mask_p0 = (
        active_rows['Hold_Period'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID_P0) &
        active_rows['Stop_Loss'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID_P0) &
        active_rows['Score'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID_P0)
    )
    _dropped_p0 = (~_valid_mask_p0).sum()
    if _dropped_p0 > 0:
        print(f"📌 [阶段0] 三字段过滤：剔除 {_dropped_p0} 条旧版本/不完整持仓记录，不纳入风控审查。")
    active_rows = active_rows[_valid_mask_p0].copy()
    if active_rows.empty:
        print("📌 [阶段0] 过滤后无有效新版本持仓，跳过持仓审查。")
        return set(), {}, {}
    print(f"🔍 识别到 {len(active_rows)} 个活跃追踪头寸，开始提取个股最新动态进行宏观风控审查...")
    active_tickers = active_rows['Ticker'].unique().tolist()
    current_prices = {}
    realtime_success = []
    for t in active_tickers:
        try:
            info = yf.Ticker(t).fast_info
            price = info.get("last_price") or info.get("lastPrice")
            if price and float(price) > 0:
                current_prices[t] = round(float(price), 2)
                realtime_success.append(t)
        except Exception:
            pass
        finally:
            time.sleep(random.uniform(0.2, 0.5))
    if realtime_success:
        print(f"✅ 实时价拉取成功（fast_info），覆盖 {len(realtime_success)}/{len(active_tickers)} 只持仓")
    missing = [t for t in active_tickers if t not in current_prices]
    if missing:
        try:
            price_data = yf.download(missing, period="1d", progress=False, auto_adjust=True)
            for t in missing:
                try:
                    if len(missing) == 1:
                        val = price_data['Close'].iloc[-1]
                    else:
                        val = price_data['Close'][t].iloc[-1]
                    if pd.notna(val) and float(val) > 0:
                        current_prices[t] = round(float(val), 2)
                except Exception:
                    pass
            covered = [t for t in missing if t in current_prices]
            if covered:
                print(f"⚠️ 以下标的实时价失败，改用 yf.download 昨收兜底: {covered}")
        except Exception as e:
            print(f"⚠️ yf.download 批量价格也失败: {e}")
    for t in active_tickers:
        if t not in current_prices:
            match_row = active_rows[active_rows['Ticker'] == t].iloc[-1]
            current_prices[t] = match_row['Price']
            print(f"🚨 {t} 价格全部拉取失败，回退买入价 ${match_row['Price']}（盈亏将显示 0%，请手动核查）")
    positions_lines = []
    for idx, row in active_rows.iterrows():
        t = row['Ticker']
        cur_p = current_prices.get(t, row['Price'])
        headlines = get_stock_news(t, max_items=4)
        news_str = " | ".join(headlines) if headlines else "暂无个股重大消息披露"
        positions_lines.append(
            f"- 标的: {row['Name']} ({t}) | 推荐买入价: ${row['Price']} | 实时现价: ${cur_p} | 分类标签: {row['Tag']} | 头条新闻: {news_str}"
        )
    active_positions_text = "\n".join(positions_lines)
    print("🧠 提请 AI 专家开展盘前持仓排雷研判...")
    client = anthropic.Anthropic(
        api_key=os.environ.get("CLAWSOCKET_API_KEY"),
        base_url=os.environ.get("CLAWSOCKET_BASE_URL")
    )
    review_prompt = f"""
你是华尔街资深风控总监与首席宏观策略师。现在我们需要对目前的活跃持仓进行盘前紧急风控排雷。

【今日宏观财经快讯】：
{macro_news_text}

【实时全球宏观经济指标（国债收益率、大宗商品、主要指数涨跌）】：
{macro_market_text}

【当前活跃持仓列表】：
{active_positions_text}

【风控审查任务】：
请密切结合今天的整体宏观环境以及个股最新的新闻动向，客观评估哪些活跃持仓标的已经发生突发利空、逻辑全面证伪或系统性负面冲击，应当立即予以【彻底抛弃/斩仓出局 (Dropped)】；哪些并无实质硬伤，可以【继续追踪持仓 (Active)】。

【输出纪律】：
为了方便程序自动无缝解析，请严格、且仅能输出标准的 JSON 数据，绝对不要包含任何 markdown 语法外框（如 ```json）或任何前言解释性叙述、后记总结文字：
{{
  "decision": {{
    "TICKER1": "Dropped",
    "TICKER2": "Active"
  }},
  "reason": "清仓或保留的统一核心风控考量依据（150字以内简述）"
}}
"""
    restricted_tickers = set(active_tickers)
    dropped_info = {}
    try:
        # 修复：移除 temperature 参数（新版 Claude 不支持）
        response = client.messages.create(
            model=TARGET_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": review_prompt}]
        )
        resp_text = response.content[0].text.strip()
        start_idx = resp_text.find('{')
        end_idx = resp_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            resp_text = resp_text[start_idx:end_idx+1]
        decision_data = json.loads(resp_text)
        decisions = decision_data.get("decision", {})
        reason_summary = decision_data.get("reason", "未提供具体原由")
        print(f"📊 AI 风控风向标结论：{reason_summary}")
        today_str = datetime.datetime.now().strftime('%Y-%m-%d')
        updated_count = 0
        for idx, row in df.iterrows():
            if row['Status'] == 'Active':
                t = row['Ticker']
                if t in decisions and decisions[t] == "Dropped":
                    df.at[idx, 'Status'] = "Dropped"
                    df.at[idx, 'Exit_Date'] = today_str
                    df.at[idx, 'Exit_Price'] = current_prices.get(t, row['Price'])
                    print(f"🚨 斩仓风控响应：{row['Name']}({t}) 存在突发风控逆风，状态变更为 [Dropped]。保留买入价 ${row['Price']}，卖出收盘结算价 ${current_prices.get(t, row['Price'])}")
                    dropped_info[t] = {"name": row.get('Name', t), "reason": reason_summary}
                    updated_count += 1
        if updated_count > 0:
            df.to_csv(log_file, index=False, encoding="utf-8")
            print(f"💾 账本已精准同步，本次共风险对冲丢弃 {updated_count} 只标的，保留原始交易路径。")
        else:
            print("✅ 现有活跃头寸均安全通过宏观与个股风控排雷，继续保持追踪。")
    except Exception as e:
        print(f"⚠️ 持仓雷区决策在执行自动解析时发生异常: {e}，持仓状态将维持原状。")
    return restricted_tickers, dropped_info, current_prices

# ==================== 9. 板块数据与封禁 ====================
def get_us_sector_performance():
    print("🇺🇸 [板块数据] 正在抓取昨日美股板块ETF表现...")
    sector_map = {
        "SOXX": "半导体板块",
        "SMH":  "半导体制造(费城)",
        "XLK":  "科技板块（软件/硬件/云）",
        "ARKK": "创新科技（AI/基因/自驾）",
        "XLF":  "金融板块（银行/保险/券商）",
        "XLE":  "能源板块（石油/天然气）",
        "XLV":  "医疗健康板块",
        "XLY":  "非必需消费（零售/汽车）",
        "XLI":  "工业板块（航空/防务/制造）",
        "XLB":  "材料板块（矿业/化工）",
    }
    results = []
    import urllib.request
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    three_days_ago = (datetime.datetime.now() - datetime.timedelta(days=4)).strftime('%Y-%m-%d')
    for ticker, desc in sector_map.items():
        try:
            url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&d1={three_days_ago.replace('-','')}&d2={yesterday.replace('-','')}&i=d"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                content = resp.read().decode('utf-8')
            lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
            if len(lines) >= 3:
                last = lines[-1].split(',')
                prev = lines[-2].split(',')
                if len(last) >= 5 and len(prev) >= 5:
                    close = float(last[4])
                    prev_close = float(prev[4])
                    pct = round((close - prev_close) / prev_close * 100, 2)
                    sign = "📈" if pct > 0 else "📉"
                    results.append(f"{sign} {ticker}: {pct:+.2f}% — {desc}")
            time.sleep(0.3)
        except Exception:
            results.append(f"❓ {ticker}: 抓取失败 — {desc}")
    if results:
        print(f"✅ 板块数据获取完毕：{len(results)} 个板块")
        return "\n".join(results)
    return "暂无板块数据"

US_SECTOR_EMBARGO_MAP = {
    "SOXX": ["semiconductor", "chip", "wafer", "fab", "NVDA", "AMD", "INTC", "MU", "AMAT", "LRCX", "KLAC", "MRVL", "AVGO", "TXN", "QCOM", "半导体"],
    "SMH":  ["semiconductor", "chip", "NVDA", "AMD", "INTC", "MU", "TSM", "ASML", "半导体"],
    "XLK":  ["tech", "software", "cloud", "AI", "data center", "MSFT", "AAPL", "GOOGL", "META", "CRM", "NOW", "SNOW"],
    "ARKK": ["AI", "genomics", "autonomous", "fintech", "TSLA", "ROKU", "COIN", "PATH", "EXAS"],
    "XLF":  ["bank", "insurance", "broker", "JPM", "BAC", "GS", "MS", "WFC", "BRK"],
    "XLE":  ["oil", "gas", "energy", "XOM", "CVX", "COP", "SLB", "HAL"],
    "XLV":  ["pharma", "biotech", "health", "JNJ", "UNH", "LLY", "MRK", "ABBV"],
    "XLY":  ["retail", "auto", "consumer", "AMZN", "TSLA", "HD", "MCD", "NKE"],
    "XLI":  ["industrial", "aerospace", "defense", "GE", "HON", "CAT", "BA", "RTX", "LMT"],
    "XLB":  ["materials", "mining", "chemical", "LIN", "APD", "ECL", "NEM", "FCX"],
}
EMBARGO_THRESHOLD_PCT = -1.5

def parse_us_sector_embargo(sector_text):
    if not sector_text or "暂无" in sector_text:
        return [], ""
    embargo_keywords = []
    embargo_lines = []
    for line in sector_text.strip().split('\n'):
        if '📉' not in line:
            continue
        try:
            etf = line.replace('📉', '').strip().split(':')[0].strip()
            pct = float(line.split(':')[1].strip().split('%')[0])
        except Exception:
            continue
        if pct >= EMBARGO_THRESHOLD_PCT:
            continue
        kw_list = US_SECTOR_EMBARGO_MAP.get(etf, [])
        if not kw_list:
            continue
        embargo_keywords.extend(kw_list)
        strength = "⛔ 强封（跌幅≥3%）" if pct <= -3.0 else "🚫 预警封禁（跌幅≥1.5%）"
        embargo_lines.append(
            f"  {strength} {etf} 昨日 {pct:+.2f}% → 相关板块/个股今日禁入Top5"
        )
    if not embargo_lines:
        return [], ""
    embargo_keywords = list(dict.fromkeys(embargo_keywords))
    text = f"""
🚨【昨日板块大跌封禁名单 —— 硬性纪律，无例外】：
{chr(10).join(embargo_lines)}

执行规则（不可违反）：
1. 以上封禁板块内的任何标的，今日一律不得进入【核心区 Top1-5】。
2. 即使技术面健康、个股新闻利好、逻辑通顺，也绝对禁止。"有独立逻辑"不是例外理由——板块昨日大跌后，情绪面压制会在今日盘中形成强烈阻力，追入必然被套。
3. 今日宏观事件导致某板块大跌，该事件的逻辑冲击不会因一天就结束，短期持续1-5天，避免接飞刀。
4. 可以出现在"今日雷区"里做点名分析，但不能进入推荐区。
封禁相关关键词：{', '.join(embargo_keywords[:20])}
"""
    print(f"🚫 美股封禁触发：{len(embargo_lines)}个板块，关键词共{len(embargo_keywords)}个")
    return embargo_keywords, text

def analyze_market_signals(combined_news_text, client):
    if not combined_news_text or len(combined_news_text.strip()) < 50:
        return {"signals": []}
    try:
        prompt = f"""你是顶级对冲基金的跨市场策略研究员，覆盖全球所有主要资产类别。
你的职责是识别新闻背后的真实信号，并判断哪些是"基本面改变"（AVOID），
哪些是"情绪/联动错杀机会"（BUY_DIP），哪些是正向催化、轮动或过度反应。

【今日新闻（过去36小时）】：
{combined_news_text[:6000]}

════════════════════════════════════════════
【分析框架】
════════════════════════════════════════════

第一步：基本面判断（最关键）
  问：这条新闻是否真正改变了某个板块的需求/收入/利润基本面？

  判断方法：
  · 如果影响的是"整个行业的需求结构" → 基本面改变 → AVOID
  · 如果影响的是"单一公司的资源配置" → 基本面未变 → BUY_DIP（如果该板块因此下跌）
  · 如果是"新的需求/政策/技术催化" → POSITIVE_CATALYST
  · 如果资金因此从 A 流出必然流向 B → ROTATION
  · 如果市场反应幅度明显超过事件本身 → CONTRARIAN

  陷阱示例（务必避免）：
  ❌ Meta 出租闲置算力 → 错判为"算力需求下降 → AVOID 半导体"
  ✅ 正确：Meta 只是自己资源错配，NVDA/AMD 的需求来自整个超大规模厂商生态，
           微软/谷歌/亚马逊的 AI capex 完全未变。这是 BUY_DIP 信号，不是 AVOID。
  ✅ 真正的 AVOID：英伟达直租模式 → 云厂商被去中间化 → AWS/Azure/GCP 毛利真正受压

第二步：精确到子板块
  同一板块内不同子板块方向可能相反，必须区分。

第三步：覆盖所有行业（不只是科技/半导体）

════════════════════════════════════════════
必须只返回以下 JSON，不输出任何其他文字：
{{
  "signals": [
    {{
      "type": "AVOID 或 BUY_DIP 或 POSITIVE_CATALYST 或 ROTATION 或 CONTRARIAN",
      "sector": "板块英文",
      "sector_cn": "板块中文",
      "affected_subsectors": ["精确到受影响的子板块"],
      "unaffected_subsectors": ["明确不受影响的子板块"],
      "surface_news": "新闻表面说了什么（一句话）",
      "real_signal": "真实业务含义——基本面有没有变？为什么？",
      "transmission_chain": "A → B → C 传导链",
      "reasoning": "为什么是这个类型？",
      "actionable": "具体可执行建议",
      "confidence": "high 或 medium 或 low",
      "duration_days": 信号有效天数（整数）
    }}
  ]
}}

若今日新闻无结构性信号，返回 {{"signals": []}}。"""
        # 移除 temperature 参数
        response = client.messages.create(
            model=TARGET_MODEL,
            max_tokens=80000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        start = text.find('{')
        end = text.rfind('}') + 1
        if start == -1 or end == 0:
            return {"signals": []}
        data = json.loads(text[start:end])
        signals = data.get("signals", [])
        icons = {"AVOID":"🔴","BUY_DIP":"💚","POSITIVE_CATALYST":"✨","ROTATION":"🔄","CONTRARIAN":"⚡"}
        if signals:
            print(f"📡 [市场信号] 识别到 {len(signals)} 个跨市场信号：")
            for s in signals:
                icon = icons.get(s.get("type",""), "❓")
                print(f"   {icon} [{s.get('type')}] {s.get('sector_cn','')} | {s.get('real_signal','')[:70]}")
        else:
            print("✅ [市场信号] 未识别到结构性信号")
        return {"signals": signals}
    except Exception as ex:
        print(f"⚠️ [市场信号] 调用失败，降级为空: {ex}")
        return {"signals": []}

def build_market_signal_text(analysis_result):
    if not analysis_result:
        return []
    signals = analysis_result.get("signals", [])
    if not signals:
        return []
    icons = {"AVOID":"🔴","BUY_DIP":"💚","POSITIVE_CATALYST":"✨","ROTATION":"🔄","CONTRARIAN":"⚡"}
    grouped = {}
    for s in signals:
        grouped.setdefault(s.get("type","AVOID"), []).append(s)
    avoid_keywords = []
    sections = []
    if "AVOID" in grouped:
        lines = []
        for s in grouped["AVOID"]:
            avoid_keywords += [s.get("sector",""), s.get("sector_cn","")] + s.get("affected_subsectors",[])
            unsub = s.get("unaffected_subsectors",[])
            lines.append(
                f"  🔴 {s.get('sector_cn','')}({s.get('sector','')})\n"
                f"    真实信号: {s.get('real_signal','')}\n"
                f"    传导链: {s.get('transmission_chain','')}\n"
                f"    受影响子板块: {', '.join(s.get('affected_subsectors',[]) or ['全板块'])}\n"
                + (f"    ⚠️ 不受影响子板块（勿误杀）: {', '.join(unsub)}\n" if unsub else "")
                + f"    预计持续: {s.get('duration_days','?')}天 | 置信度: {s.get('confidence','?')}"
            )
        sections.append(
            "🚨【今日回避（AVOID）—— 基本面受损，不得进入推荐 Top1-5】：\n\n"
            + "\n\n".join(lines)
            + f"\n\n封禁关键词: {', '.join(dict.fromkeys(avoid_keywords))}"
        )
    if "BUY_DIP" in grouped:
        lines = []
        for s in grouped["BUY_DIP"]:
            lines.append(
                f"  💚 {s.get('sector_cn','')}({s.get('sector','')})\n"
                f"    为何是错杀: {s.get('real_signal','')}\n"
                f"    基本面未变的原因: {s.get('reasoning','')}\n"
                f"    具体机会子板块: {', '.join(s.get('unaffected_subsectors',[]) or [s.get('sector_cn','')])}\n"
                f"    可执行建议: {s.get('actionable','')}\n"
                f"    信号有效: {s.get('duration_days','?')}天 | 置信度: {s.get('confidence','?')}"
            )
        sections.append(
            "💚【逢低买入（BUY_DIP）—— 情绪/联动错杀，基本面未变，可积极关注】：\n\n"
            + "\n\n".join(lines)
        )
    for t, label in [
        ("POSITIVE_CATALYST", "✨【正向催化（POSITIVE_CATALYST）—— 直接利好，优先关注】："),
        ("ROTATION",          "🔄【资金轮动（ROTATION）—— 承接流出资金的方向】："),
        ("CONTRARIAN",        "⚡【反向机会（CONTRARIAN）—— 市场过度反应，关注反转】："),
    ]:
        if t not in grouped:
            continue
        lines = []
        for s in grouped[t]:
            lines.append(
                f"  {icons[t]} {s.get('sector_cn','')}({s.get('sector','')})\n"
                f"    逻辑: {s.get('real_signal','')}\n"
                f"    传导链: {s.get('transmission_chain','')}\n"
                f"    建议: {s.get('actionable','')}"
            )
        sections.append(label + "\n\n" + "\n\n".join(lines))
    header = (
        "════════════════════════════════════════\n"
        "【跨市场信号分析（请先阅读本节再看候选池）】\n"
        "注意：同一板块内子板块信号可能相反，请勿一刀切。\n"
        "════════════════════════════════════════"
    )
    full_text = header + "\n\n" + "\n\n─────────────────────\n\n".join(sections)
    return [full_text, avoid_keywords]

# ==================== 10. 进化规则加载 ====================
def load_evolved_rules() -> str:
    rules_file = "evolved_rules.json"
    if not os.path.exists(rules_file):
        return ""
    try:
        with open(rules_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        patches      = data.get("prompt_patches", [])
        active_rules = data.get("active_rules", [])
        if not patches:
            return ""
        last_updated = data.get("last_updated", "未知")
        recent = data.get("recent_win_rate")
        if recent and recent.get("胜率") is not None:
            win_rate_display = f"{recent['胜率']}%（最近{recent.get('样本数','?')}笔，当前规则的真实表现）"
        else:
            win_rate_display = f"{data.get('overall_win_rate', '未知')}%（全部历史混合，仅供参考）"
        lines = [
            f"【📈 历史绩效驱动进化规则（上次更新: {last_updated} | 胜率: {win_rate_display}）】",
            "以下规则由策略进化引擎基于真实交易数据自动生成，必须严格遵守：",
            ""
        ]
        for i, (rule, patch) in enumerate(zip(active_rules, patches), 1):
            lines.append(f"规则{i}【{rule.get('type','')}】{rule.get('description','')}")
            if rule.get("evidence"):
                lines.append(f"  数据依据: {rule['evidence']}")
            lines.append(f"  执行要求: {patch}")
            lines.append("")
        lines.append("（以上规则优先级高于一般选股偏好，但低于今日突发事件强制封禁）")
        print(f"📜 [进化规则] 已加载 {len(patches)} 条规则（{win_rate_display}）")
        return "\n".join(lines)
    except Exception as e:
        print(f"⚠️ [进化规则] 读取失败: {e}")
        return ""

# ==================== 11. 读取昨日止损联动警告 ====================
def get_stop_loss_hit_warning():
    """
    读取 trade_history.csv，提取近期被标记为 Stop_Loss_Hit 的标的，
    生成一条风险警告文本，供 AI 提示词使用。
    """
    log_file = "trade_history.csv"
    if not os.path.exists(log_file):
        return ""

    try:
        df = pd.read_csv(log_file, keep_default_na=False)
        if 'Tag' not in df.columns or 'Exit_Date' not in df.columns:
            return ""

        hit_df = df[df['Tag'].astype(str).str.strip() == 'Stop_Loss_Hit'].copy()
        if hit_df.empty:
            return ""

        hit_df = hit_df.sort_values('Exit_Date', ascending=False).head(5)
        tickers = hit_df['Ticker'].unique().tolist()
        if not tickers:
            return ""

        details = []
        for _, row in hit_df.iterrows():
            name = row.get('Name', row['Ticker'])
            exit_date = row.get('Exit_Date', '未知日期')
            details.append(f"{name}({row['Ticker']}) @ {exit_date}")

        return (
            f"\n⚠️ 【昨日/近期止损风控联动警告】：以下标的在最近交易中被系统标记为「止损触发清仓」（Stop_Loss_Hit），"
            f"今日选股严禁将其列入 Top 1-5 核心推荐，仅允许在「诱多对照组」中作为反面案例提及。\n"
            f"涉及标的：{', '.join(details)}\n"
        )
    except Exception as e:
        print(f"⚠️ 读取止损警告失败: {e}")
        return ""

# ==================== 12. AI 报告生成（强制 Top 5 + 联动警告） ====================
def generate_ai_report(pool_data, macro_news_text, macro_market_text, dropped_info=None, embargo_text="", sector_tech_data=None):
    print("开始调用 AI 大脑（宏观先行，个股新闻排雷，技术面确认，Top5详细分析+评分）...")
    client = anthropic.Anthropic(
        api_key=os.environ.get("CLAWSOCKET_API_KEY"),
        base_url=os.environ.get("CLAWSOCKET_BASE_URL")
    )
    today_str = datetime.datetime.now().strftime('%Y年%m月%d日')
    pool_text_lines = []
    for item in pool_data:
        news_str   = " | ".join(item.get('个股新闻', ['暂无']))
        tech_score = item.get("技术评分", 0)
        tech_sigs  = " / ".join(item.get("技术信号", [])) or "无"
        patterns   = " / ".join(item.get("看涨形态", [])) or "无"
        weekly_tag = "🟢周日共振" if item.get("周线共振") else "🔴仅日线"
        pool_text_lines.append(
            f"[{item['Ticker']}] {item['Name']} | ${item['Price']} | RSI:{item['RSI']} | "
            f"乖离率:{item['乖离率(%)']}% | MACD:{item['MACD趋势']} | "
            f"KDJ_J:{item.get('KDJ_J','N/A')} | 量比:{item.get('量比','N/A')} | "
            f"K线:{patterns} | {weekly_tag} | "
            f"技术评分:{tech_score}/40({tech_sigs}) | "
            f"新闻: {news_str}"
        )
    pool_formatted = "\n".join(pool_text_lines)
    pool_count     = len(pool_data)
    tech_sector_block = ""
    if sector_tech_data:
        lines = []
        for sec, stks in sorted(sector_tech_data.items(),
                                 key=lambda x: max(s["技术评分"] for s in x[1]), reverse=True)[:8]:
            top3 = [f"{s['名称']}({s['代码']})技术{s['技术评分']}分"
                    for s in stks[:3] if s["技术评分"] > 0]
            if top3:
                lines.append(f"  {sec}: {' / '.join(top3)}")
        if lines:
            tech_sector_block = "【技术形态板块共振归类（周日共振且技术评分>0，按GICS板块汇总）】：\n" + "\n".join(lines)
    evolved_rules_block = load_evolved_rules()

    # 读取昨日止损联动警告
    stop_loss_warning = get_stop_loss_hit_warning()

    prompt = f"""
【最高优先级指令 — 覆盖所有其他规则】：
你必须在 Top 1-5 中输出 5 只标的，禁止输出“暂停实盘推荐”或“今日无推荐”。
即使所有标的评分都低于 50，也必须挑出相对最好的 5 只，并如实标注低分和风险。
如果标的池少于 5 只，则按实际数量输出，但不得少于 3 只。

你是华尔街顶级产业链研究员兼游资操盘手。你的选股方法论是：

【三步选股法】：
第一步（事件驱动）：从宏观新闻与全球底层资产中提炼出今日最强的1-2条产业链主线。
第二步（产业链传导 + 个股新闻排雷）：
沿着主线找到直接受益的上中下游标的，关键是找"二级受益者"——护城河更强、估值更低的。
同时，必须逐一审查候选标的的"最新新闻"字段（每只票最多6条标题）。若发现负面新闻（监管调查、业绩预警、CEO离职、诉讼、内部人大额抛售等），即使产业链逻辑再好，也必须降级处理或移入诱多对照组。新闻面排雷的优先级高于技术面。
第三步（技术面双向验证 + 周日共振过滤）：
每只候选标的已附带「技术评分:XX/40」「🟢周日共振 / 🔴仅日线」标签，这是代码客观计算的，你不得修改这些数值。

【核心过滤规则】：
1. 新闻定板块（时效性权重递减）：
   · 你必须先从宏观新闻中提炼出1-2条最强产业链主线，然后**只在这些主线板块中寻找标的**。
   · **新闻时效权重规则**（每条新闻前面已标注时效标签，你必须严格遵守）：
     - [🔥今日最新-权重最高]：6小时内刚披露的重大催化，消息面评分可给满分（25分）
     - [📰今日-高权重]：24小时内的新闻，消息面评分给80%权重（20分）
     - [📄昨日-中等权重]：24-48小时的新闻，消息面评分给50%权重（12分）
     - [📑前日-低权重]：48-72小时的新闻，消息面评分给20%权重（5分），**仅作为辅助参考**
   · **时效性红线**：超过72小时的新闻，或该板块/个股在过去5个交易日已上涨超过12%，则视为"已充分定价/已发酵完毕"，**不得将其作为今日主线**。

2. 技术选个股：在主线板块中，**优先选择【周期共振】为 True 的标的**。如果不存在共振标的，选择技术评分≥10的标的。

3. 已涨幅降级（追高风险过滤）：
   · 如果某标的过去5日涨幅>12% 或 RSI>70 或 乖离率>15%，需在报告中注明"短期涨幅已大，等待回调确认"。

4. 【强制输出规则 — 无论技术面如何都必须遵守】：
   ⚠️ 即使技术评分普遍偏低、周期共振缺失、信号不达标，也必须输出完整的 Top 1-5 核心推荐，不得以"暂停实盘推荐"替代。
   评分可以低至 40-60 分，但必须诚实标注风险：技术面未达标、逻辑偏弱、仅作观察参考。
   评分格式：评分:[XX]/100，其中 XX 为 40-60 直接反映当前实际信号强度。
   在"风控底线"中明确写上"技术未达标，小仓位/观望"。
   报告中"今日产业链主线研判"需说明：当前市场环境下为何没有高确定性标的，以及低分推荐的理由。

{stop_loss_warning}

{evolved_rules_block}

{embargo_text}

{tech_sector_block}

【今日成交活跃的 Top {pool_count} 标的池】（含技术评分+周日共振+个股新闻）：
{pool_formatted}

【你的任务】：
1. 从宏观新闻和全球债市、商品市场中提炼出今日1-2条最强产业链主线，并对宏观波动的可持续性做出研判。
2. 沿主线在标的池中找到直接和间接受益标的，逐一核查其个股新闻是否有负面信号
3. 用技术面确认入场时机
4. 对核心入选的【前5只】标的（Top 1-5）进行展开式详细分析，每只票的产业链逻辑、新闻核查、技术确认、推荐评分都要写得具体、有数据支撑，不要写空话套话
5. 按以下HTML骨架输出报告

【硬性纪律】：
1. 评分格式必须严格为：评分:[XX]/100（XX是1-100的整数，必须用这个精确格式）。
2. 同一只股票绝对不能重复出现。
3. 风控底线格式：周期:[X-Y天] | 止损:[具体价格或百分比]。

【严格按以下HTML骨架直出，不加markdown外框】：

<div style="background: #e3f2fd; border-left: 6px solid #1565c0; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #0d47a1;">🌍 今日产业链主线研判</h3>
    <p><b>主线1：</b>(事件 → 传导逻辑 → 直接受益 → 二级受益，80字以内)</p>
    <p><b>主线2：</b>(同上，如无则说明，40字以内)</p>
    <p><b>今日雷区：</b>(哪些板块/标的因宏观逆风、负面新闻或技术超买必须回避，40字以内)</p>
</div>

<h2 style="color: #1a237e; border-bottom: 2px solid #1a237e;">👑 产业链主线优选 (Top 1-5 详细分析)</h2>
<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">1. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (...)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (...)</p>
    <p><span class='highlight-label bg-blue'>📈 技术确认:</span> (...)</p>
    <p><span class='highlight-label bg-teal'>⭐ 推荐评分:</span> 评分:[XX]/100 — (...)</p>
    <p><span class='highlight-label bg-orange'>⚠️ 风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li></ul>
    </div>
</div>

（重复至5只）

<div class="compare-card">
    <div class="compare-title">🎖️ 观察池 - 逻辑对 but 技术未到位 (Rank 6-12)</div>
    <ul>
        <li><b>6. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #1565c0;">产业链逻辑：</span>(...) <span style="color: #2e7d32;">新闻面：</span>(...) <span style="color: #388e3c;">未入选原因：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[观望] | 止损:[观望]</li>
        ...（至12）
    </ul>
</div>

<div style="background: #fbfcfe; border-left: 5px solid #388e3c; padding: 25px; margin-bottom: 25px; border-radius: 10px;">
    <h3 style="color: #388e3c; margin-top: 0;">🚨 诱多对照组（逻辑或技术或新闻面有硬伤，严禁接盘）</h3>
    <ul>
        <li><b>倒数1. [股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[坚决空仓] | 止损:[绝对规避]</li>
        <li><b>倒数2. [股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[坚决空仓] | 止损:[绝对规避]</li>
    </ul>
</div>

【严格输出纪律 · 必读】：
从你输出的第一个字符开始就必须是HTML标签（如 <div>），中间和结尾也一样。
绝对不要输出任何选股思路、筛选过程等叙述性文字——所有分析只能以HTML卡片形式呈现。
"""
    ai_html = ""
    with client.messages.stream(
        model=TARGET_MODEL,
        max_tokens=80000,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for text in stream.text_stream:
            ai_html += text
    ai_html = ai_html.replace("```html", "").replace("```", "").strip()
    html_start = ai_html.find("<div")
    if html_start > 0:
        print(f"⚠️ 检测到AI输出前置了 {html_start} 字符的非HTML内容（可能是思考过程），已自动截断丢弃")
        ai_html = ai_html[html_start:]
    print("AI 宏观穿透报告生成完毕")
    return ai_html

# ==================== 13. 工具函数（匹配、卡片、邮件） ====================
def match_pool_to_report(pool_data, ai_generated_html, default_stop_loss_pct):
    def clean_fragment(text):
        t = re.sub(r'<[^>]+>', ' ', text)
        return re.sub(r'\s+', ' ', t).strip()
    def title_hit(fragment, name, ticker):
        head = fragment[:110]
        if f"({ticker})" in head:
            return True
        if '.' in ticker and f"({ticker.split('.')[0]})" in head:
            return True
        return name in fragment[:30]
    obs_start = ai_generated_html.find('class="compare-card"')
    if obs_start == -1:
        obs_start = ai_generated_html.find('观察池')
    if obs_start == -1:
        obs_start = len(ai_generated_html)
    trap_start = ai_generated_html.find('诱多对照组')
    if trap_start == -1 or trap_start < obs_start:
        trap_start = len(ai_generated_html)
    core_zone_raw = ai_generated_html[:obs_start]
    obs_zone_raw = ai_generated_html[obs_start:trap_start]
    trap_zone_raw = ai_generated_html[trap_start:]
    core_cards = [clean_fragment(c) for c in re.split(r'(?=<div class="top-card")', core_zone_raw) if 'top-card' in c]
    obs_items = [clean_fragment(c) for c in re.split(r'(?=<li>)', obs_zone_raw) if c.strip().startswith('<li>')]
    trap_items = [clean_fragment(c) for c in re.split(r'(?=<li>)', trap_zone_raw) if c.strip().startswith('<li>')]
    print(f"📎 报告结构切分：核心卡片 {len(core_cards)} 张 | 观察池 {len(obs_items)} 条 | 诱多对照组 {len(trap_items)} 条")
    chosen = []
    for item in pool_data:
        name, ticker = str(item['Name']), str(item['Ticker'])
        tag, chunk = None, None
        for card in core_cards:
            if title_hit(card, name, ticker):
                tag, chunk = "Core_Dragon", card
                break
        if tag is None:
            for li in obs_items:
                if title_hit(li, name, ticker):
                    tag, chunk = "Observation", li
                    break
        if tag is None:
            for li in trap_items:
                if title_hit(li, name, ticker):
                    tag, chunk = "Trap_Warning", li
                    break
        if tag is None or tag == "Trap_Warning":
            continue
        period_match = re.search(r'周期\s*[:：]\s*\[?(\d+[-~]\d+天|\d+天|观望)', chunk)
        sl_match = re.search(r'止损\s*[:：]\s*\[?(\$?[\d\.]+[元%]?|-[\d\.]+%?)', chunk)
        if tag == "Observation":
            hold_period = "观望"
            stop_loss = "观望"
            score = "N/A"
        else:
            hold_period = period_match.group(1).strip() if period_match else "5-10天"
            atr_pct = item.get('ATR_Pct', 5.0)
            dynamic_stop_pct = -max(ATR_STOP_FLOOR_PCT, min(ATR_STOP_CEIL_PCT, atr_pct * ATR_STOP_MULTIPLIER))
            stop_loss = sl_match.group(1).strip() if sl_match else f"{round(item['Price'] * (1 + dynamic_stop_pct / 100), 2)}"
            # 修复评分解析：若无法解析，则用技术评分+50兜底
            score_match = re.search(r'评分\s*[:：]\s*\[?(\d{1,3})\]?\s*/\s*100', chunk)
            score = score_match.group(1).strip() if score_match else "N/A"
            if score == "N/A":
                tech_score = item.get('技术评分', 0)
                score = str(min(100, tech_score + 50))
        item['Tag'] = tag
        item['Hold_Period'] = hold_period
        item['Stop_Loss'] = stop_loss
        item['Score'] = score
        chosen.append(item)
    return chosen

def build_sell_signal_card(dropped_info, rule_sell_signals):
    return ""

def build_current_holdings_card(current_prices_map):
    return ""

def send_mail(to_emails, subject, content):
    user, pwd = os.environ.get("EMAIL_ACCOUNT"), os.environ.get("EMAIL_PASSWORD")
    if not user:
        print("邮件账号未配置，跳过发送。")
        return
    to_list = [email.strip() for email in to_emails.split(',')]
    msg = MIMEMultipart()
    msg['From'] = user
    msg['Subject'] = subject
    msg.attach(MIMEText(content, 'html'))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.sendmail(user, to_list, msg.as_string())
            print(f"内参已精准密送至: {to_emails}")
    except Exception as e:
        print(f"发送失败 ({to_emails}): {e}")

# ==================== 14. 期权策略生成函数（内联，与 review.py 联动） ====================
def generate_option_strategy(ticker, name, direction, scan_score, scan_date, underlying_price, underlying_stop, hold_period, strategy_reason, contracts=1):
    opt_file = "option_strategies.csv"
    days_match = re.findall(r'\d+', str(hold_period))
    max_days = max(map(int, days_match)) if days_match else 7
    expiry_date = (datetime.datetime.now() + datetime.timedelta(days=max_days)).strftime('%Y-%m-%d')
    if direction.upper() == 'BULLISH':
        opt_type = 'CALL'
        strike = round(underlying_price * 1.05, 2)
    else:
        opt_type = 'PUT'
        strike = round(underlying_price * 0.95, 2)
    entry_price = round(strike * 0.02, 2)
    header = "Ticker,OptionType,Strike,Expiry,EntryPrice,Status,EntryDate,Quantity,Direction,UnderlyingPrice,StopLoss,HoldPeriod,Reason,ScanScore\n"
    need_header = not os.path.exists(opt_file) or os.path.getsize(opt_file) == 0
    with open(opt_file, "a", encoding="utf-8") as f:
        if need_header:
            f.write(header)
        f.write(f"{ticker},{opt_type},{strike},{expiry_date},{entry_price},Active,{scan_date},{contracts},{direction},{underlying_price},{underlying_stop},{hold_period},{strategy_reason},{scan_score}\n")
    print(f"📝 期权策略记录：{ticker} {opt_type} {strike} @ {expiry_date}")

# ==================== 15. 主程序 ====================
if __name__ == "__main__":
    macro_news = get_latest_macro_news()
    megacap_news = get_megacap_breaking_news()
    combined_news = macro_news
    if megacap_news:
        combined_news = macro_news + "\n\n【Mega-Cap 公司最新动态（过去36h，含彭博/WSJ等外部来源引用）】：\n" + megacap_news

    _embargo_client = anthropic.Anthropic(
        api_key=os.environ.get("CLAWSOCKET_API_KEY"),
        base_url=os.environ.get("CLAWSOCKET_BASE_URL")
    )
    news_analysis = analyze_market_signals(combined_news, _embargo_client)
    news_embargo_result = build_market_signal_text(news_analysis)
    news_embargo_text = news_embargo_result[0] if news_embargo_result else ""

    macro_market = get_macro_market_data()

    restricted_tickers, dropped_info, current_prices = pre_scan_portfolio_review(combined_news, macro_market)

    raw_tickers = get_scan_pool()
    sector_text = get_us_sector_performance()
    _etf_embargo_kw, etf_embargo_text = parse_us_sector_embargo(sector_text)
    combined_embargo_text = "\n".join(filter(None, [news_embargo_text, etf_embargo_text]))
    if not combined_embargo_text:
        combined_embargo_text = ""

    filtered_tickers = {t: n for t, n in raw_tickers.items() if t not in restricted_tickers}
    pool_data = build_stock_pool(filtered_tickers)
    if not pool_data:
        print("无合规扫描数据，今日扫描提前安全熔断。")
        style = """
        <style>
            body { font-family: 'Helvetica Neue', 'PingFang SC', sans-serif; background-color: #f0f2f5; padding: 20px; color: #2c3e50; line-height: 1.7;}
            .container { max-width: 950px; margin: 0 auto; background: #ffffff; padding: 35px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
            h1 { text-align: center; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 15px; margin-bottom: 35px; font-size: 28px; font-weight: 800; }
        </style>
        """
        empty_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>⚠️ 今日扫描无有效标的，已暂停推荐</h1><p>原因：所有标的已被排除或技术数据不足。</p></div></body></html>"
        send_mail(SUPER_ADMIN, f"【美股扫描】{datetime.date.today()} 无推荐", empty_html)
        exit(0)

    sector_tech_data = screen_technical_setups(pool_data)
    pool_data = enrich_pool_with_news(pool_data)

    ai_generated_html = generate_ai_report(pool_data, combined_news, macro_market, dropped_info, combined_embargo_text, sector_tech_data)

    style = """
    <style>
        body { font-family: 'Helvetica Neue', 'PingFang SC', sans-serif; background-color: #f0f2f5; padding: 20px; color: #2c3e50; line-height: 1.7;}
        .container { max-width: 950px; margin: 0 auto; background: #ffffff; padding: 35px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
        h1 { text-align: center; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 15px; margin-bottom: 35px; font-size: 28px; font-weight: 800; }
        .top-card { padding: 25px; margin-bottom: 30px; border-radius: 10px; background: #fafafa; border: 1px solid #e0e0e0; border-left: 6px solid #78909c; }
        .core-card { border-left: 6px solid #d32f2f; background: #fffcfc; box-shadow: 0 4px 15px rgba(211, 47, 47, 0.08); }
        .top-title { font-size: 20px; font-weight: 800; color: #37474f; border-bottom: 1px dashed #cfd8dc; padding-bottom: 10px; margin-bottom: 15px; }
        .highlight-label { display: inline-block; font-weight: bold; color: #fff; padding: 3px 8px; border-radius: 4px; margin-right: 6px; font-size: 13px;}
        .bg-red { background: #d32f2f; }
        .bg-blue { background: #1976d2; }
        .bg-orange { background: #e64a19; }
        .bg-green { background: #2e7d32; }
        .bg-teal { background: #00897b; }
        .compare-card { border-left: 5px solid #ff9800; background: #fffdf7; padding: 25px; margin-bottom: 25px; border-radius: 10px; border: 1px solid #ffe0b2;}
        .compare-title { font-size: 19px; color: #e65100; font-weight: bold; margin-bottom: 15px; border-bottom: 1px solid #ffe0b2; padding-bottom: 10px;}
        ul { padding-left: 22px; margin-top: 0;}
        li { margin-bottom: 10px; font-size: 15px; }
    </style>
    """
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>🎯 宏观驱动美股波段内参：{TARGET_REGION}</h1>\n{ai_generated_html}\n<p style='text-align:center; color:#999; font-size:12px; margin-top:40px;'>[END_OF_QUANT_REPORT]</p></div></body></html>"

    try:
        with open("report.html", "w", encoding="utf-8") as f:
            f.write(full_html)
        print("report.html 已成功存入本地！")
    except Exception as e:
        print(f"report.html 写入失败: {e}")

    mail_subject = f"【宏观驱动美股版】{TARGET_REGION} 核心打分与实战 ({datetime.date.today()})"
    send_mail(SUPER_ADMIN, mail_subject, full_html)

    # 匹配推荐并写入 trade_history.csv 和期权记录
    chosen = match_pool_to_report(pool_data, ai_generated_html, DEFAULT_STOP_LOSS_PCT)
    log_file = "trade_history.csv"
    need_header = not os.path.exists(log_file) or os.path.getsize(log_file) == 0
    try:
        FROZEN_STATUSES = {'Dropped', 'Stop_Loss_Hit'}
        REQUALIFY_MARGIN = 5  # 从 10 降到 5，降低重新入选门槛
        _INVALID_W = {'', 'n/a', 'nan', 'none', '观望'}
        frozen_min_score = {}
        if not need_header:
            try:
                df_hist_check = pd.read_csv(log_file, on_bad_lines='skip', keep_default_na=False)
                if {'Status', 'Ticker', 'Score'}.issubset(df_hist_check.columns):
                    bad_exits = df_hist_check[df_hist_check['Status'].isin(FROZEN_STATUSES)].copy()
                    bad_exits['Score_num'] = pd.to_numeric(bad_exits['Score'], errors='coerce')
                    for tk, g in bad_exits.groupby('Ticker'):
                        tk = str(tk)
                        if g['Score_num'].notna().any():
                            frozen_min_score[tk] = float(g['Score_num'].max()) + REQUALIFY_MARGIN
                        else:
                            frozen_min_score[tk] = float('inf')
                    if frozen_min_score:
                        locked = sum(1 for v in frozen_min_score.values() if v == float('inf'))
                        print(f"🔒 写账过滤：{len(frozen_min_score)} 只曾斩仓/止损标的需评分达标才能重新入选（其中 {locked} 只因历史评分缺失暂无法解冻）")
            except Exception as e:
                print(f"⚠️ 写账过滤读取 trade_history.csv 失败，不执行冻结过滤: {e}")
        def _requalifies(item):
            tk = str(item.get('Ticker', ''))
            if tk not in frozen_min_score:
                return True
            try:
                cur_score = float(str(item.get('Score', '')).strip())
            except (ValueError, TypeError):
                return False
            return cur_score >= frozen_min_score[tk]

        # 【修复】写账过滤：观察池不要求三字段完整，直接写入；Core_Dragon 必须有完整的 Hold_Period/Stop_Loss/Score
        chosen_to_write = []
        for i in chosen:
            if not _requalifies(i):
                continue
            tag = str(i.get('Tag', '')).strip()
            # 观察池：只检查是否被斩仓过，不要求三字段完整
            if tag == 'Observation':
                chosen_to_write.append(i)
                continue
            # Core_Dragon：严格要求三字段完整
            if (str(i.get('Hold_Period', '')).strip().lower() not in _INVALID_W and
                str(i.get('Stop_Loss', '')).strip().lower() not in _INVALID_W and
                str(i.get('Score', '')).strip().lower() not in {'', 'n/a', 'nan', 'none'}):
                chosen_to_write.append(i)
        skipped = len(chosen) - len(chosen_to_write)
        if skipped > 0:
            print(f"⏭️ 写账过滤：跳过 {skipped} 条（观察池已写入或三字段不完整），不写入新追踪记录。")

        ts_date = datetime.datetime.now().strftime('%Y-%m-%d')
        ts_date_file = datetime.datetime.now().strftime('%Y%m%d')
        if chosen_to_write:
            pending_file = f"us_stocks_pending_{ts_date_file}.csv"
            pending_header = "Date,Ticker,Name,Tag,RSI,Bias,技术评分,MACD金叉,周线共振,KDJ_J回升,量能放大,Hold_Period,Stop_Loss,Score,Status,Scan_Ref_Price,ATR_Pct\n"
            with open(pending_file, "w", encoding="utf-8") as f:
                f.write(pending_header)
                for i in chosen_to_write:
                    ticker = i.get('Ticker', '')
                    name = i.get('Name', '')
                    tag = i.get('Tag', '')
                    rsi = i.get('RSI', '')
                    bias = i.get('乖离率(%)', '')
                    tech_score = i.get('技术评分', 0)
                    macd_cross = i.get('MACD金叉', False)
                    weekly_sync = i.get('周线共振', False)
                    kdj_rising = i.get('KDJ_J回升', False)
                    vol_surge = i.get('量能放大', False)
                    hold_period = i.get('Hold_Period', 'N/A')
                    stop_loss = i.get('Stop_Loss', 'N/A')
                    score = i.get('Score', 'N/A')
                    scan_ref_price = i.get('Price', i.get('Open_Price', ''))
                    atr_pct_val = i.get('ATR_Pct', '')
                    f.write(f"{ts_date},{ticker},{name},{tag},{rsi},{bias},{tech_score},{macd_cross},{weekly_sync},{kdj_rising},{vol_surge},{hold_period},{stop_loss},{score},pending,{scan_ref_price},{atr_pct_val}\n")

            print(f"✅ 共生成 {len(chosen_to_write)} 条美股推荐记录（已保存至 {pending_file}，不含价格）")
            print(f"⏳ 开盘价/收盘价将在盘后 review.py 执行时用完整行情数据补充写入 trade_history.csv")

            # 为每条 Core_Dragon 生成期权策略
            for item in chosen_to_write:
                if item.get('Tag') == 'Core_Dragon':
                    generate_option_strategy(
                        ticker=item['Ticker'],
                        name=item['Name'],
                        direction='BULLISH',
                        scan_score=item.get('Score', 'N/A'),
                        scan_date=ts_date,
                        underlying_price=item.get('Price', 0),
                        underlying_stop=item.get('Stop_Loss', 'N/A'),
                        hold_period=item.get('Hold_Period', '5-10天'),
                        strategy_reason="核心精选，事件+技术共振，偏多",
                        contracts=1
                    )
        else:
            print(f"⚠️ 未生成任何推荐记录（全部被过滤）")

    except Exception as e:
        print(f"新推荐数据入账失败: {e}")

    print("🎯 美股盘前扫描完成。")
