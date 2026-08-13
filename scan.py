# -*- coding: utf-8 -*-
import faulthandler
faulthandler.enable()  # 一旦再发生底层段错误(segfault)，会在stderr打印Python调用栈定位到具体哪一行，而不是只有"exit code 139"
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
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

today = datetime.datetime.now().weekday()
if today >= 5:
    print(f"[{datetime.datetime.now()}] 周末休市，脚本自动跳过。")
    exit()

TARGET_MODEL = 'claude-opus-4-8'
TARGET_REGION = "美国市场"
DEFAULT_STOP_LOSS_PCT = -5.0

SUPER_ADMIN = os.environ.get("TARGET_EMAILS")

if not SUPER_ADMIN:
    print("致命错误：未检测到 TARGET_EMAILS！")
    exit(1)

# 启动前置校验：AI 凭证（缺失则立即报错退出，避免跑完前面耗时的数据抓取阶段后才在AI调用阶段崩溃）
_missing_env = [k for k in ("CLAWSOCKET_API_KEY", "CLAWSOCKET_BASE_URL") if not os.environ.get(k)]
if _missing_env:
    print(f"致命错误：未检测到环境变量 {', '.join(_missing_env)}！请检查 GitHub Actions 仓库的 Secrets 配置（Settings → Secrets and variables → Actions），并确认 workflow yml 中已通过 env: 正确传递。")
    exit(1)

print(f"启动：宏观驱动美股扫描引擎 | 引擎: {TARGET_MODEL}")

# ==========================================
# 版本标记：检测 scan.py 内容是否变化，记录"当前版本"起始日期
# 供 evolve.py 做公平评估时过滤数据，避免新旧版本混在一起算胜率
# ==========================================
def update_version_marker():
    version_file = "scan_version.txt"
    try:
        with open("scan.py", "rb") as f:
            current_hash = hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        print(f"⚠️ 版本标记读取自身失败，跳过: {e}")
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
        print(f"📌 检测到 scan.py 内容已变化，记录新版本起始日期: {today_str}")
    else:
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                existing = f.read().strip()
            version_date = existing.split(",")[1] if "," in existing else "未知"
            print(f"📌 scan.py 版本未变化，当前版本起始日期: {version_date}")
        except Exception:
            pass

update_version_marker()

def get_robust_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.yahoo.com/"
    })
    return session

# ==========================================
# 1. 宏观新闻（CNBC + Reuters RSS）
# ==========================================
def get_latest_macro_news():
    print("正在抓取 CNBC/Reuters 英文财经快讯...")
    import xml.etree.ElementTree as ET

    sources = [
        ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
        ("Reuters", "https://feeds.reuters.com/reuters/businessNews"),
        ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ]

    session = get_robust_session()
    news_lines = []
    for source_name, url in sources:
        try:
            response = session.get(url, timeout=10)
            root = ET.fromstring(response.content)
            items = root.findall('.//item')[:5]
            for item in items:
                title = item.find('title')
                pub_date = item.find('pubDate')
                if title is not None:
                    time_str = pub_date.text[:16] if pub_date is not None else ""
                    news_lines.append(f"[{source_name}] {time_str} - {title.text}")
        except Exception as e:
            print(f"⚠️ {source_name} 抓取失败: {e}")

    if news_lines:
        print(f"✅ 成功抓取 {len(news_lines)} 条宏观财经快讯")
        return "\n".join(news_lines)

    return "暂无实时英文财经新闻，请基于昨收盘及底层产业逻辑进行推演。"


def get_megacap_breaking_news():
    """
    用 yfinance .news 抓取 mega-cap 公司最近 36 小时内的新闻标题。

    为什么需要这个：
    - CNBC/Reuters RSS 通常只有通稿摘要，彭博/华尔街日报的独家内容很少出现在免费 RSS 里。
    - 但彭博的报道会在数小时内被 Yahoo Finance 新闻流引用（带标题），yfinance .news 能抓到这层。
    - 对于"Meta 宣布自建算力"这类公司级消息，直接看 META 的新闻 feed 比看宏观 RSS 灵敏得多。
    - 这些 mega-cap 的任何重大公告都可能引发板块联动（META 建算力 → 减少 GPU 外购 → 半导体需求下降）。

    覆盖范围：AI/云算力/半导体产业链上最具影响力的 10 家公司。
    输出：过去 36h 内的新闻标题（含来源、时间），供 analyze_news_for_sector_embargo() 做 AI 分析。
    """
    MEGACAP_TICKERS = {
        "META":  "Meta（算力/AI/社交）",
        "NVDA":  "NVIDIA（GPU/AI芯片）",
        "MSFT":  "Microsoft（Azure/AI/云）",
        "GOOGL": "Alphabet（云/AI/搜索）",
        "AMZN":  "Amazon（AWS/电商/AI）",
        "AAPL":  "Apple（消费电子/芯片）",
        "TSLA":  "Tesla（电动车/AI/储能）",
        "AMD":   "AMD（CPU/GPU/数据中心）",
        "INTC":  "Intel（代工/PC芯片）",
        "MU":    "Micron（内存/HBM）",
    }

    cutoff_ts = time.time() - 36 * 3600  # 36小时前的unix timestamp
    news_lines = []
    fetched = 0

    for ticker, desc in MEGACAP_TICKERS.items():
        try:
            raw_news = yf.Ticker(ticker).news or []
            for item in raw_news[:8]:  # 每只票最多取8条
                pub_ts = item.get("providerPublishTime", 0)
                if pub_ts < cutoff_ts:
                    continue  # 超过36小时的跳过
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
        print(f"✅ mega-cap 公司新闻：抓取 {fetched} 条（过去36小时内），覆盖 {len(MEGACAP_TICKERS)} 只标的")
        return "\n".join(news_lines)
    return ""


# ==========================================
# 新增功能：引入全球大宗商品、国债收益率及核心大盘指数的多维宏观数据
# ==========================================
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
    for name, ticker in macro_tickers.items():
        try:
            df = yf.download(ticker, period="5d", progress=False)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                latest_close = df['Close'].iloc[-1]
                prev_close = df['Close'].iloc[-2]
                pct_change = ((latest_close - prev_close) / prev_close) * 100

                if "^" in ticker and "VIX" not in name and "指数" not in name:
                    lines.append(f"- {name} ({ticker}): 当前收益率 {round(latest_close, 3)}% | 当日变动幅度: {round(pct_change, 2)}%")
                else:
                    lines.append(f"- {name} ({ticker}): 当前价/值 {round(latest_close, 2)} | 当日涨跌幅: {round(pct_change, 2)}%")
        except Exception as e:
            print(f"⚠️ 宏观因子 {name}({ticker}) 抓取受阻: {e}")

    if lines:
        print(f"✅ 成功提取 {len(lines)} 项全球关键宏观底层指标数据")
        return "\n".join(lines)
    return "暂无实时大宗商品与国债收益率宏观数据。"


# ==========================================
# 2. 个股新闻（Yahoo Finance RSS + 随机休眠）
# ==========================================
def get_stock_news(ticker, max_items=6):
    import xml.etree.ElementTree as ET
    session = get_robust_session()
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    try:
        response = session.get(url, timeout=8)
        root = ET.fromstring(response.content)
        items = root.findall('.//item')[:max_items]
        headlines = []
        for item in items:
            title = item.find('title')
            if title is not None and title.text:
                headlines.append(title.text.strip())
        return headlines
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

# ==========================================
# 3. 获取美股标的池（全免费：三大指数 + 成交量过滤）
# ==========================================
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

    # 修复：移除 threads=False（新版 yfinance 已不支持该参数）
    data = yf.download(tickers_list, period="1d", group_by='ticker', auto_adjust=True, progress=False)

    vols = {}
    for t in tickers_list:
        try:
            # 兼容单只与多只标的返回结构差异
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

# ==========================================
# 4. 拉取 K 线，计算技术指标（仅作参考，不预先淘汰）
# ==========================================
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
            # ── 日线数据（6个月）──
            df = get_kline_data(ts_code)
            if df is None or df.empty or len(df) < 40:
                continue

            df['MACDh'] = ta.macd(df['Close']).iloc[:, 1]
            df['RSI']   = ta.rsi(df['Close'], length=14)
            df['MA20']  = ta.sma(df['Close'], length=20)
            df = df.dropna()
            if len(df) < 6:
                continue

            latest, prev = df.iloc[-1], df.iloc[-2]
            bias       = (latest['Close'] - latest['MA20']) / latest['MA20']
            h_last     = float(latest['MACDh'])
            h_prev     = float(prev['MACDh'])
            h_prev2    = float(df.iloc[-3]['MACDh'])
            macd_trend = "走强" if h_last > h_prev else "走弱"

            # ── MACD 精准判断：金叉 or 刚开始上行（绿柱缩短）──
            # MACD线和信号线
            macd_df    = ta.macd(df['Close'])
            macd_line  = macd_df.iloc[:, 0]   # MACD line (fast-slow EMA)
            signal_line= macd_df.iloc[:, 2]   # Signal line
            macd_cross = False
            macd_green_shrink = False
            if len(macd_line) >= 3:
                # 金叉：MACD线今天在信号线上方，昨天在下方
                macd_cross = bool(
                    float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) and
                    float(macd_line.iloc[-2]) <= float(signal_line.iloc[-2])
                )
                # 即将金叉或刚启动：柱为负且持续向0收敛（连续2日）
                macd_green_shrink = bool(
                    h_last < 0 and h_last > h_prev and h_prev < h_prev2
                )

            # ── 周线计算（共振过滤）──
            weekly_bullish = False
            try:
                df_w = yf.download(ts_code, period="1y", interval="1wk", progress=False, auto_adjust=True)
                if df_w is not None and not df_w.empty and len(df_w) >= 12:
                    if isinstance(df_w.columns, pd.MultiIndex):
                        df_w.columns = df_w.columns.get_level_values(0)
                    w_close = df_w['Close'].values.astype(float)
                    # 周线MA5 > MA10（周线均线多头排列）
                    wma5  = float(pd.Series(w_close).rolling(5).mean().iloc[-1])
                    wma10 = float(pd.Series(w_close).rolling(10).mean().iloc[-1])
                    # 周线MACD柱向上
                    w_exp1 = pd.Series(w_close).ewm(span=12, adjust=False).mean()
                    w_exp2 = pd.Series(w_close).ewm(span=26, adjust=False).mean()
                    w_hist = ((w_exp1 - w_exp2) - (w_exp1 - w_exp2).ewm(span=9, adjust=False).mean()) * 2
                    w_hist_rising = float(w_hist.iloc[-1]) > float(w_hist.iloc[-2])
                    weekly_bullish = bool(wma5 > wma10 and w_hist_rising)
            except Exception:
                weekly_bullish = False

            # ── KDJ（手动迭代）──
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

            # ── 量能放大 ──
            vols      = df['Volume'].values.astype(float)
            avg5      = float(pd.Series(vols[:-1]).tail(5).mean())
            vol_today = float(vols[-1])
            vol_ratio = round(vol_today / (avg5 + 1e-9), 2)
            vol_surge = bool(avg5 > 0 and vol_today >= avg5 * 1.3)

            # ── 看涨K线形态 ──
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
                "Open_Price":      round(latest['Open'], 2),  # 修正：补充当天的开盘价格字段
                "RSI":             round(latest['RSI'], 1),
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
            })
        except Exception:
            continue
        finally:
            time.sleep(random.uniform(0.3, 0.7))

    print(f"✅ 技术面数据计算完毕，共 {len(pool)} 只标的进入新闻+逻辑分析阶段。")
    return pool


# ── 常用美股GICS板块映射 ──
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


def screen_technical_setups(pool_data):
    """
    技术形态筛选：0-40分客观评分 + 周日共振过滤。

    评分规则（满分40分）：
      MACD金叉或刚启动（绿柱连续收敛）  0-15分  ← 核心信号权重最高
      KDJ的J值从低位/超卖区回升          0-10分
      量能放大（量比≥1.3）               0-10分
      看涨K线形态                          0-5分

    周日共振要求（过滤器，非加分）：
      weekly_bullish=True（周线MA5>MA10 且 周线MACD柱上行）时，
      技术评分×1.25加成（上限仍为40）；
      weekly_bullish=False时，技术评分×0.6惩罚（日线信号但周线逆势）。
    """
    sector_groups = {}

    for stock in pool_data:
        tech_score   = 0
        tech_reasons = []

        # 1. MACD信号（权重最高）
        if stock.get("MACD金叉"):
            tech_score += 15
            tech_reasons.append("MACD金叉(+15)")
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
            tech_score += 4
            tech_reasons.append("MACD红柱走强(+4)")

        # 2. KDJ J值回升
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

        # 3. 量能放大
        vol_ratio = stock.get("量比", 1.0)
        if stock.get("量能放大"):
            pts = 10 if vol_ratio >= 2.0 else 7
            tech_score += pts
            tech_reasons.append(f"量比{vol_ratio:.1f}倍放量(+{pts})")

        # 4. 看涨K线形态
        patterns = stock.get("看涨形态", [])
        if patterns:
            score_map = {"看涨吞没": 5, "启明星": 5, "刺穿线": 4, "锤子线": 3}
            base = max(score_map.get(p, 2) for p in patterns)
            tech_score += base
            tech_reasons.append(f"{'&'.join(patterns)}形态(+{base})")

        # 5. 周日共振加成/惩罚
        weekly = stock.get("周线共振", False)
        if weekly:
            tech_score = min(int(tech_score * 1.25), 40)
            tech_reasons.append("✅周日共振加成×1.25")
        elif tech_score > 0:
            tech_score = int(tech_score * 0.6)
            tech_reasons.append("⚠️周线逆势惩罚×0.6")

        tech_score = min(tech_score, 40)
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


# ==========================================
# 新增功能：盘前现有持仓排雷审查相位（Phase 0）
# ==========================================
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

    # 自动向后兼容升级账本表头
    required_cols = ["Exit_Date", "Exit_Price", "Status"]
    headers_need_rewrite = False
    for col in required_cols:
        if col not in df.columns:
            df[col] = "Active" if col == "Status" else "N/A"
            headers_need_rewrite = True

    # 强制把 Exit_Date / Exit_Price 锁定为 object dtype：
    # 这两列目前可能全部是占位字符串 "N/A"，若不显式锁定，pandas会把整列推断为
    # float64（配合 keep_default_na=False 则反过来推断为纯字符串 str dtype），
    # 之后无论写入真实日期字符串还是真实卖出价(float)，都会触发严格的dtype类型检查报错。
    # 锁定为 object 后，同一列可以混存字符串"N/A"和后续真实写入的字符串/浮点值，不再受限。
    for col in ["Exit_Date", "Exit_Price"]:
        df[col] = df[col].astype(object)

    if headers_need_rewrite:
        df.to_csv(log_file, index=False, encoding="utf-8")

    # 筛选处于活跃持仓状态的股票
    active_rows = df[df['Status'] == 'Active'].copy()
    if active_rows.empty:
        print("📌 当前无可执行风控追踪的活跃持仓标的。")
        return set(), {}, {}

    # ── 新版本标记过滤：Hold_Period / Stop_Loss / Score 三字段缺一不可 ──
    # 旧版本记录缺少这三个字段，视为无效持仓，不纳入风控审查。
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

    # 获取实时现价作为可能卖出的执行参考价
    # 优先级：
    #   1. yf.Ticker.fast_info["last_price"] —— 实时/盘前价，只要市场有成交就有数据
    #   2. yf.download(period="1d") iloc[-1]  —— 盘后收盘价，盘前可能为空
    #   3. 买入价兜底                          —— 打印警告，盈亏=0
    current_prices = {}

    # 方案1：逐只用 fast_info 拿实时价（含盘前/盘后延伸交易时段）
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

    # 方案2：未拿到实时价的 ticker 用 yf.download 昨收兜底
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

    # 方案3：仍未拿到价格的 ticker 用买入价兜底，并打印警告
    for t in active_tickers:
        if t not in current_prices:
            match_row = active_rows[active_rows['Ticker'] == t].iloc[-1]
            current_prices[t] = match_row['Price']
            print(f"🚨 {t} 价格全部拉取失败，回退买入价 ${match_row['Price']}（盈亏将显示 0%，请手动核查）")

    # 汇编个股持仓状况与最新的个股爆料快讯
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
请密切结合今天的整体宏观环境（例如美债收益率大涨大跌、关键经济数据如PCE或CPI对指数带来的严重冲击、金银铜油等大宗商品的异常突破或见顶反转）以及个股最新的新闻动向，客观评估哪些活跃持仓标的已经发生突发利空、逻辑全面证伪或系统性负面冲击，应当立即予以【彻底抛弃/斩仓出局 (Dropped)】；哪些并无实质硬伤，可以【继续追踪持仓 (Active)】。

特别提示：你需要理性审视类似昨晚PCE数据引发的大盘指数回调，这究竟是短线情绪面的正常噪音释放，还是中长周期宏观紧缩/宽松逻辑的根本性方向逆转？若属于短线噪声干扰且个股产业链底层依然健康，请保持 Active。若个股头条触发硬伤负面或宏观逻辑逆风无法逆转，请果断判罚 Dropped。

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
    # 记录下所有当前已经在追踪的股票，返回给主程序进行新推荐隔离，防止重复扫描
    restricted_tickers = set(active_tickers)
    # dropped_info: {ticker: {"name": ..., "reason": ...}} 供邮件卡片展示
    dropped_info = {}

    try:
        response = client.messages.create(
            model=TARGET_MODEL,
            max_tokens=2000,
            temperature=0.1,
            messages=[{"role": "user", "content": review_prompt}]
        )
        resp_text = response.content[0].text.strip()

        # 清洗可能夹带的冗余外壳
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

        # 逐条更新账本状态，不删除行，而是改状态并追加卖出记录
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

    # current_prices 在此一并返回，供 __main__ 阶段0b 直接复用——
    # 避免对同一批持仓再发起一轮 yf.Ticker(...).fast_info 请求，
    # 减少对 yfinance(curl_cffi) 的总调用次数。
    return restricted_tickers, dropped_info, current_prices


# ==========================================
# 5. Claude 宏观+个股新闻驱动深度推演（流式，Top5详细分析+1-100评分）
# ==========================================
def get_us_sector_performance():
    """
    抓取昨日美股主要板块ETF的涨跌幅。
    用于生成今日板块联动封禁清单：某板块ETF昨日大跌，则该板块个股今日禁止进入Top5。
    数据源：stooq.com（无需API key，稳定性好于直接访问Yahoo）
    """
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
            # 修复：URL 被错误地插入了 markdown 链接语法，恢复为纯 URL 字符串
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


# ETF → 美股个股所属板块关键词映射
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

EMBARGO_THRESHOLD_PCT = -1.5  # 跌幅超过此值触发封禁

def analyze_market_signals(combined_news_text, client):
    """
    全市场双向信号解读引擎，在主推荐 AI 之前运行。

    核心设计原则：新闻不只产生风险，也暴露机会。
    同一事件对不同板块可以同时产生截然相反的信号。
    关键是判断"基本面有没有真正改变"——没变就是买入机会，变了才是回避信号。

    五类信号：
      AVOID            基本面确实受损，需求/盈利真实下降 → 今日不买
      BUY_DIP          情绪/联动导致的错杀，基本面未变 → 加仓机会
      POSITIVE_CATALYST 新闻直接利好某板块需求或盈利 → 积极关注
      ROTATION         资金从 A 流出必然流向 B → 识别 B
      CONTRARIAN       市场反应明显过度 → 关注反转

    Meta 算力案例的正确解读（示范）：
      ❌ 错误：Meta 出租算力 → 半导体需求下降 → AVOID 半导体
      ✅ 正确：Meta 只是一家公司资源错配，NVDA 的收入来自 Microsoft/Google/Amazon 等整个生态，
               这些超大规模厂商的 AI capex 计划完全没变。SOXX 的下跌是情绪传染，不是基本面。
               → 半导体应判断为 BUY_DIP，不是 AVOID。
               → 真正的 AVOID 是云厂商（AWS/Azure/GCP）被英伟达直租模式去中间化。
    """
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
  例：半导体整体 SOXX 下跌，但：
  · GPU/数据中心芯片：视具体新闻判断
  · 汽车芯片/工业芯片/消费芯片：需求驱动独立，联动跌反而是机会

第三步：覆盖所有行业（不只是科技/半导体）
  扫描范围：semiconductor / cloud / AI / energy / financials / healthcare / 
  consumer / industrials / materials / real_estate / utilities / defense / 
  biotech / crypto / bonds / commodities / forex / China / emerging_markets

════════════════════════════════════════════
必须只返回以下 JSON，不输出任何其他文字：
{{
  "signals": [
    {{
      "type": "AVOID 或 BUY_DIP 或 POSITIVE_CATALYST 或 ROTATION 或 CONTRARIAN",
      "sector": "板块英文",
      "sector_cn": "板块中文",
      "affected_subsectors": ["精确到受影响的子板块，如 cloud_providers, GPU_datacenter"],
      "unaffected_subsectors": ["明确不受影响的子板块，如 auto_chips, industrial_semis"],
      "surface_news": "新闻表面说了什么（一句话）",
      "real_signal": "真实业务含义——基本面有没有变？为什么？（这是核心，两句话以内）",
      "transmission_chain": "A → B → C 传导链",
      "reasoning": "为什么是这个类型？特别是 BUY_DIP 必须说明基本面为何未变",
      "actionable": "具体可执行建议（如：等 SOXX 跌至 200MA 附近分批建仓汽车芯片）",
      "confidence": "high 或 medium 或 low",
      "duration_days": 信号有效天数（整数）
    }}
  ]
}}

若今日新闻无结构性信号，返回 {{"signals": []}}。"""

        response = client.messages.create(
            model="claude-opus-4-8",   # haiku在此代理不可用，统一用opus
            max_tokens=2000,
            temperature=0,
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
    """
    把五类信号转换成主推荐 AI 的上下文文本（放在候选池之前）。
    AVOID → 硬性封禁（约束）
    BUY_DIP → 错杀加仓机会（正向参考）
    POSITIVE_CATALYST / ROTATION / CONTRARIAN → 各类机会提示
    """
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




def parse_us_sector_embargo(sector_text):
    """
    解析板块ETF涨跌数据，生成今日不可推荐的板块封禁清单和注入AI prompt的封禁通知。
    跌幅 >= -3%: 强封（高度联动，情绪不可抗拒）
    跌幅 -1.5% ~ -3%: 预警封禁
    """
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
3. 今日宏观事件导致某板块大跌（如 Meta 宣布自建算力→冲击半导体需求预期），该事件的逻辑冲击不会因一天就结束，短期持续1-5天，避免接飞刀。
4. 可以出现在"今日雷区"里做点名分析，但不能进入推荐区。
封禁相关关键词：{', '.join(embargo_keywords[:20])}
"""
    print(f"🚫 美股封禁触发：{len(embargo_lines)}个板块，关键词共{len(embargo_keywords)}个")
    return embargo_keywords, text


def load_evolved_rules() -> str:
    """
    读取 evolve_us.py 生成的 evolved_rules.json，把有效规则注入 AI 选股 prompt。
    这是进化闭环的最后一步：
      evolve.py 分析历史交易 → 写 evolved_rules.json
      scan.py   读取该文件   → 注入 prompt → 影响今日选股
    文件不存在时静默返回空字符串。
    """
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
        # ✅ 【改动】同A股版：优先展示"最近一次进化之后"的胜率，不是混合全部历史
        # （包括进化前原始策略）的总胜率，避免误导AI以为自己上一轮调整没用/有用。
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

    # 进化规则（来自历史交易数据，evolve_us.py生成）
    evolved_rules_block = load_evolved_rules()

    prompt = f"""
你是华尔街顶级产业链研究员兼游资操盘手。你的选股方法论是：

【三步选股法】：
第一步（事件驱动）：从宏观新闻与全球底层资产（国债收益率走势、PCE等关键宏观变量带来的大盘剧烈波动、金银铜油等大宗商品价格走势）中提炼出今日最强的1-2条产业链主线。
特别注意：需要敏锐剖析宏观数据（如PCE数据导致的指数下跌）代表的本质。分析此次指数下跌究竟是短暂的情绪面过度反应（提供了黄金黄金买点），还是底层趋势已经发生不可逆的改变？
例如：
- AI算力爆发 → GPU需求激增 → HBM/DRAM内存长期供应紧张（2025-2028缺货） → 美光(MU)、Arm(ARM)
- 美联储降息预期升温 → 资金回流成长股 → 科技/半导体板块受益
- 地缘冲突缓和 → 原油回落 → 航空(DAL/UAL)、航运成本下降受益的零售商(AMZN)

第二步（产业链传导 + 个股新闻排雷）：
沿着主线找到直接受益的上中下游标的，关键是找"二级受益者"——护城河更强、估值更低的：
- 英伟达GPU热销 → 不买英伟达（已过热），买内存供应商MU（供需缺口持续到2028）
- AI数据中心扩张 → 不买AI芯片（贵），买给数据中心供电的电力设备商（POWL/VRT）
同时，必须逐一审查候选标的的"最新新闻"字段（每只票最多6条标题）。若发现负面新闻（监管调查、业绩预警、CEO离职、诉讼、内部人大额抛售等），即使产业链逻辑再好，也必须降级处理或移入诱多对照组。新闻面排雷的优先级高于技术面。

第三步（技术面双向验证 + 周日共振过滤）：
每只候选标的已附带「技术评分:XX/40」「🟢周日共振 / 🔴仅日线」标签，这是代码客观计算的，你不得修改这些数值。

【核心过滤规则】：
✅ 优先推荐：技术评分≥20 且 🟢周日共振（周线MA5>MA10 + 周线MACD柱上行 + 日线MACD金叉/绿柱缩短）
🟡 次级候选：技术评分10-20，仅日线信号但宏观/消息面极强时可入
🔴 禁止推荐：🔴仅日线标签 + 技术评分<10，即使消息面再好也不进Top5
⚠️ 强制降级：乖离率>20% 且 RSI>80，即使技术分高也列入雷区

MACD信号优先级（从高到低）：
  1. MACD金叉（今天MACD线上穿信号线）→ 最强入场信号
  2. MACD绿柱连续收敛（柱值为负但持续向0靠拢）→ 即将金叉的预信号
  3. MACD红柱走强 → 趋势延续，已在途中

第四步（双维度综合评分，1-100分）：

【评分权重体系 — 总分100分】：

■ 技术面（40分，直接读取「技术评分」字段，你不能修改）：
  · MACD金叉           0-15分（最强信号）
  · MACD绿柱快速收敛   0-12分
  · KDJ超卖区回头      0-10分（超卖满分）
  · 量能放大           0-10分（量比≥2倍满分）
  · K线形态            0-5分
  · 周日共振加成×1.25 / 仅日线惩罚×0.6（已计入）

■ 消息面（60分，由你评估）：
  · 产业链逻辑直接度      0-25分（直接受益=满分，二手受益=15-20分）
  · 个股新闻共振度        0-25分（正面公告=满分；干净=15分；负面=-10分）
  · 技术与逻辑三重共振奖  0-10分（金叉+量能+产业链同向=额外加分）

评分格式：评分:[XX]/100（XX为整数）
例：技术评分26分 + 消息面48分 → 写 评分:[74]/100

今天是{today_str}。

【盘前宏观与全球重大快讯】：
{macro_news_text}

【实时全球宏观经济指标（国债收益率、大宗商品、主要指数涨跌）】：
{macro_market_text}

{evolved_rules_block}

{embargo_text}

{tech_sector_block}

【今日成交活跃的 Top {pool_count} 标的池】（含技术评分+周日共振+个股新闻）：
{pool_formatted}

【你的任务】：
1. 从宏观新闻和全球债市、商品市场中提炼出今日1-2条最强产业链主线，并对宏观波动的可持续性做出研判。
2. 沿主线在标的池中找到直接和间接受益标的（优先找二级受益者），逐一核查其个股新闻是否有负面信号
3. 用技术面确认入场时机
4. 对核心入选的【前5只】标的（Top 1-5）进行展开式详细分析，每只票的产业链逻辑、新闻核查、技术确认、推荐评分都要写得具体、有数据支撑，不要写空话套话
5. 按以下HTML骨架输出报告

注意：如果标的池里没有5只能完美符合产业链逻辑且新闻面干净的票，可以少于5只进入核心区，把空出来的名额放入观察池详细说明原因，不要为了凑数硬塞逻辑不充分的票进核心区。

【硬性纪律】：
1. 评分格式必须严格为：评分:[XX]/100（XX是1-100的整数，必须用这个精确格式，不要写成"XX分"等变体）。
2. 同一只股票绝对不能重复出现。
3. 风控底线格式：周期:[X-Y天] | 止损:[具体价格或百分比]。

【严格按以下HTML骨架直出，不加markdown外框，Top1-5每只都要按这个模板写满；括号里的字数是上限不是下限，越精简越好，禁止凑字数】：

<div style="background: #e3f2fd; border-left: 6px solid #1565c0; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #0d47a1;">🌍 今日产业链主线研判</h3>
    <p><b>主线1：</b>(事件 → 传导逻辑 → 直接受益 → 二级受益，80字以内)</p>
    <p><b>主线2：</b>(同上，如无第二条主线则说明，40字以内)</p>
    <p><b>今日雷区：</b>(哪些板块/标的因宏观逆风、负面新闻或技术超买必须回避，40字以内)</p>
</div>

<h2 style="color: #1a237e; border-bottom: 2px solid #1a237e; padding-bottom: 5px;">👑 产业链主线优选 (Top 1-5 详细分析)</h2>
<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">1. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (说明完整的传导链：宏观事件→产业受益→为什么是这只票而不是更直接的受益者，50字以内)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (基于提供的新闻标题，点评是否有风险，提及1-2条最关键的新闻内容，25字以内)</p>
    <p><span class='highlight-label bg-blue'>📈 技术确认:</span> (乖离率/RSI/MACD数值具体分析，说明为何这个时点是安全的入场点，25字以内)</p>
    <p><span class='highlight-label bg-teal'>⭐ 推荐评分:</span> 评分:[XX]/100 — [一句话说明评分理由，15字以内]</p>
    <p><span class='highlight-label bg-orange'>⚠️ 风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(明确给出具体strike和expiry时间窗口，20字以内)</li><li><b>期权组合构建：</b>(单腿买入还是价差防守，说明理由，20字以内)</li></ul>
    </div>
</div>

<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">2. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (同上详细程度，50字以内)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (...)</p>
    <p><span class='highlight-label bg-blue'>📈 技术确认:</span> (...)</p>
    <p><span class='highlight-label bg-teal'>⭐ 推荐评分:</span> 评分:[XX]/100 — (...)</p>
    <p><span class='highlight-label bg-orange'>⚠️ 风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li></ul>
    </div>
</div>

<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">3. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (同上详细程度，50字以内)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (...)</p>
    <p><span class='highlight-label bg-blue'>📈 技术确认:</span> (...)</p>
    <p><span class='highlight-label bg-teal'>⭐ 推荐评分:</span> 评分:[XX]/100 — (...)</p>
    <p><span class='highlight-label bg-orange'>⚠️ 风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li></ul>
    </div>
</div>

<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">4. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (同上详细程度，50字以内)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (...)</p>
    <p><span class='highlight-label bg-blue'>📈 技术确认:</span> (...)</p>
    <p><span class='highlight-label bg-teal'>⭐ 推荐评分:</span> 评分:[XX]/100 — (...)</p>
    <p><span class='highlight-label bg-orange'>⚠️ 风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li></ul>
    </div>
</div>

<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">5. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (同上详细程度，50字以内)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (...)</p>
    <p><span class='highlight-label bg-blue'>📈 技术确认:</span> (...)</p>
    <p><span class='highlight-label bg-teal'>⭐ 推荐评分:</span> 评分:[XX]/100 — (...)</p>
    <p><span class='highlight-label bg-orange'>⚠️ 风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li></ul>
    </div>
</div>

<div class="compare-card">
    <div class="compare-title">🎖️ 观察池 - 逻辑对 but 技术未到位 (Rank 6-12)</div>
    <ul>
        <li><b>6. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #1565c0;">产业链逻辑：</span>(说明逻辑，15字以内) <span style="color: #2e7d32;">新闻面：</span>(是否干净，10字以内) <span style="color: #388e3c;">未入选原因：</span>(技术超买/等回调/逻辑偏弱，10字以内) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[观望等回调] | 止损:[回调到XX再买]</li>
        <li><b>7. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #1565c0;">逻辑：</span>(...) <span style="color: #2e7d32;">新闻面：</span>(...) <span style="color: #388e3c;">未入选：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[观望] | 止损:[观望]</li>
        <li><b>8. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #1565c0;">逻辑：</span>(...) <span style="color: #2e7d32;">新闻面：</span>(...) <span style="color: #388e3c;">未入选：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[观望] | 止损:[观望]</li>
        <li><b>9. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #1565c0;">逻辑：</span>(...) <span style="color: #2e7d32;">新闻面：</span>(...) <span style="color: #388e3c;">未入选：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[观望] | 止损:[观望]</li>
        <li><b>10. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #1565c0;">逻辑：</span>(...) <span style="color: #2e7d32;">新闻面：</span>(...) <span style="color: #388e3c;">未入选：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[观望] | 止损:[观望]</li>
        <li><b>11. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #1565c0;">逻辑：</span>(...) <span style="color: #2e7d32;">新闻面：</span>(...) <span style="color: #388e3c;">未入选：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[观望] | 止损:[观望]</li>
        <li><b>12. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #1565c0;">逻辑：</span>(...) <span style="color: #2e7d32;">新闻面：</span>(...) <span style="color: #388e3c;">未入选：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[观望] | 止损:[观望]</li>
    </ul>
</div>

<div style="background: #fbfcfe; border-left: 5px solid #388e3c; padding: 25px; margin-bottom: 25px; border-radius: 10px;">
    <h3 style="color: #388e3c; margin-top: 0;">🚨 诱多对照组（逻辑或技术或新闻面有硬伤，严禁接盘）</h3>
    <ul>
        <li><b>倒数1. [股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">硬伤（技术超买/负面新闻/逻辑反转）：</span>(15字以内) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[坚决空仓或等回调] | 止损:[绝对规避]</li>
        <li><b>倒数2. [股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">硬伤（技术超买/负面新闻/逻辑反转）：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[坚决空仓或等回调] | 止损:[绝对规避]</li>
    </ul>
</div>
"""


    ai_html = ""
    with client.messages.stream(
        model=TARGET_MODEL,
        max_tokens=80000,
        temperature=0.25,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for text in stream.text_stream:
            ai_html += text

    print("AI 宏观穿透报告生成完毕")
    return ai_html.replace("```html", "").replace("```", "").strip()


# ==========================================
# 6. HTML 封装
# ==========================================
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

# ==========================================
# 0b. 规则驱动卖出信号检测（止损触发 / 持有到期）—— 纯数值判断，不依赖 AI
# ==========================================
def check_rule_based_sell_signals(current_prices_map, exclude_tickers=None):
    """
    对阶段0a AI宏观审查后仍在 Active 的持仓做规则检测：
      1. 现价已跌破 Stop_Loss 止损价  → "止损触发"
      2. 距买入日已达到 Hold_Period 上限 → "持有到期"
    命中后：
      - trade_history.csv：Status 锁定为 'Stop_Loss_Hit' 或 'Period_Matured'，停止后续推荐
      - review_history.csv（若存在）：归档买入价/现价供胜率统计
    返回: (sell_signals: List[dict], removed_tickers: List[str])
    """
    log_file = "trade_history.csv"
    exclude_tickers = set(exclude_tickers or [])
    _INVALID = {'', 'n/a', 'nan', 'none', '观望'}

    if not os.path.exists(log_file):
        print("📋 [阶段0b] trade_history.csv 不存在，跳过规则卖出信号检测。")
        return [], []

    try:
        df = pd.read_csv(log_file, keep_default_na=False)
        df['Date'] = pd.to_datetime(df['Date'])
        holdings = df[df['Status'] == 'Active'].copy()
        if holdings.empty:
            print("📋 [阶段0b] 当前无 Active 持仓，跳过规则卖出信号检测。")
            return [], []

        for _col in ['Hold_Period', 'Stop_Loss', 'Score']:
            if _col not in holdings.columns:
                holdings[_col] = ''
        _valid = (
            holdings['Hold_Period'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID) &
            holdings['Stop_Loss'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID) &
            holdings['Score'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID)
        )
        holdings = holdings[_valid].copy()
        if holdings.empty:
            print("📋 [阶段0b] 过滤后无有效新版本持仓，跳过规则卖出信号检测。")
            return [], []
    except Exception as e:
        print(f"⚠️ [阶段0b] 持仓读取失败: {e}")
        return [], []

    def _parse_hold_days(s):
        s = str(s).strip()
        if not s or s.lower() in _INVALID: return None
        nums = re.findall(r'\d+', s)
        return int(nums[-1]) if nums else None

    def _parse_stop_loss_price(s):
        s = str(s).strip().lstrip('$')
        if not s or s.lower() in _INVALID: return None
        nums = re.findall(r'\d+\.?\d*', s)
        return float(nums[0]) if nums else None

    now = datetime.datetime.now()
    sell_signals = []
    removed_tickers = []

    for _, row in holdings.iterrows():
        ticker = str(row['Ticker'])
        buy_price = float(row['Price'])
        buy_date = row['Date']
        hold_days = _parse_hold_days(row.get('Hold_Period'))
        stop_loss_val = _parse_stop_loss_price(row.get('Stop_Loss'))
        cur_price = current_prices_map.get(ticker, buy_price)

        signal_type = None
        reason = ""
        if stop_loss_val is not None and cur_price <= stop_loss_val:
            signal_type = "止损触发"
            reason = f"现价${cur_price}已跌破止损位${stop_loss_val}，按风控纪律应立即止损离场"
        elif hold_days is not None:
            maturity_date = buy_date + datetime.timedelta(days=hold_days)
            if now >= maturity_date:
                signal_type = "持有到期"
                days_held_now = (now - buy_date).days
                reason = f"已持有{days_held_now}天，达到/超过建议持股周期（{row.get('Hold_Period')}）上限，按纪律应清仓离场"

        if signal_type is None:
            continue

        pnl_pct = round(((cur_price - buy_price) / buy_price) * 100, 2)
        sell_signals.append({
            "ticker": ticker,
            "name": str(row.get('Name', ticker)),
            "signal_type": signal_type,
            "buy_price": buy_price,
            "buy_date": buy_date.strftime('%Y-%m-%d'),
            "current_price": cur_price,
            "pnl_pct": pnl_pct,
            "days_held": (now - buy_date).days,
            "hold_period": row.get('Hold_Period', 'N/A'),
            "stop_loss": row.get('Stop_Loss', 'N/A'),
            "score": row.get('Score', 'N/A'),
            "reason": reason,
        })
        removed_tickers.append(ticker)

    if not sell_signals:
        print("✅ [阶段0b] 规则审查：当前持仓无止损触发或持有到期信号。")
        return [], []

    try:
        df_orig = pd.read_csv(log_file, keep_default_na=False)
        for col in ["Exit_Date", "Exit_Price"]:
            if col in df_orig.columns:
                df_orig[col] = df_orig[col].astype(object)
        # ✅ 【修复】原来按 Ticker 一个条件匹配、没管 Status 是不是还是 Active——如果这只票
        # 之前已经平仓过一次（有一行历史 Stop_Loss_Hit/Dropped），这次是它重新入选后的
        # 新一轮持仓触发退出，会把旧的那行也一起改写 Status/Exit_Date/Exit_Price，等于
        # 历史成交记录被今天的价格覆盖掉了（这也是当前 trade_history.csv 里 MU 一只票
        # 有9行全部标成 Stop_Loss_Hit 的原因）。加上 Status=='Active' 这个条件，只改
        # 当前真正还在持仓中的那一行/几行。
        for s in sell_signals:
            tag_to_set = 'Stop_Loss_Hit' if s['signal_type'] == '止损触发' else 'Period_Matured'
            _mask = (df_orig['Ticker'] == s['ticker']) & (df_orig['Status'] == 'Active')
            df_orig.loc[_mask, 'Status'] = tag_to_set
            df_orig.loc[_mask, 'Exit_Date'] = datetime.datetime.now().strftime('%Y-%m-%d')
            df_orig.loc[_mask, 'Exit_Price'] = s['current_price']
        df_orig.to_csv(log_file, index=False, encoding="utf-8")
        print(f"🔒 [阶段0b] 已锁定 {len(sell_signals)} 只标的状态（止损触发/持有到期），停止后续追踪")
    except Exception as e:
        print(f"⚠️ [阶段0b] trade_history.csv 状态更新失败: {e}")

    for s in sell_signals:
        icon = "🛑" if s['signal_type'] == '止损触发' else "⏰"
        print(f"{icon} [阶段0b] 卖出信号: {s['name']}({s['ticker']}) — {s['signal_type']} | 现价${s['current_price']} 买入价${s['buy_price']} 盈亏{s['pnl_pct']:+.2f}%")

    return sell_signals, removed_tickers


def build_sell_signal_card(dropped_info, rule_sell_signals):
    if not dropped_info and not rule_sell_signals:
        return ""
    rows_html = ""
    for t, info in (dropped_info or {}).items():
        rows_html += f'<tr style="border-bottom:1px solid #ffe0b2;"><td style="padding:8px 6px;"><b>{info["name"]} ({t})</b></td><td style="padding:8px 6px;"><span style="background:#c62828;color:#fff;padding:2px 7px;border-radius:4px;font-size:12px;">突发利空强清</span></td><td style="padding:8px 6px;" colspan="2">{info["reason"]}</td></tr>'
    for s in rule_sell_signals:
        pnl_color = "#d32f2f" if s['pnl_pct'] >= 0 else "#388e3c"
        badge_bg = "#e64a19" if s['signal_type'] == '止损触发' else "#607d8b"
        rows_html += f'<tr style="border-bottom:1px solid #ffe0b2;"><td style="padding:8px 6px;"><b>{s["name"]} ({s["ticker"]})</b></td><td style="padding:8px 6px;"><span style="background:{badge_bg};color:#fff;padding:2px 7px;border-radius:4px;font-size:12px;">{s["signal_type"]}</span></td><td style="padding:8px 6px;">买入${s["buy_price"]} → 现价${s["current_price"]}，<span style="color:{pnl_color};font-weight:bold;">{s["pnl_pct"]:+.2f}%</span></td><td style="padding:8px 6px;">{s["reason"]}</td></tr>'
    total = len(dropped_info or {}) + len(rule_sell_signals)
    return f'<div style="background:#fff3e0; border-left:6px solid #e65100; padding:20px; margin-bottom:25px; border-radius:8px;"><h3 style="margin:0 0 12px 0; color:#bf360c;">🔔 今日卖出信号汇总（共{total}只 · 交易时段内可直接执行）</h3><table style="width:100%; border-collapse:collapse; font-size:14px;"><tr style="text-align:left; color:#6d4c41; border-bottom:2px solid #ffb74d;"><th style="padding:6px;">标的</th><th style="padding:6px;">触发类型</th><th style="padding:6px;">价格/浮动盈亏</th><th style="padding:6px;">理由</th></tr>{rows_html}</table><p style="margin:12px 0 0 0; font-size:13px; color:#6d4c41;">以上标的已在 trade_history.csv 中锁定状态并停止后续追踪，买卖价已归档供胜率统计。本卡片仅为系统信号，实际下单时机请结合盘口自行判断。</p></div>'


def build_current_holdings_card(current_prices_map):
    log_file = "trade_history.csv"
    if not os.path.exists(log_file):
        return ""
    try:
        df = pd.read_csv(log_file, keep_default_na=False)
        active_rows = df[df['Status'] == 'Active']
        if active_rows.empty:
            return ""
        rows_html = ""
        for _, row in active_rows.iterrows():
            ticker = row['Ticker']
            try:
                buy_price = float(row['Price']) if str(row['Price']).strip() else 0.0
            except ValueError:
                buy_price = 0.0
            cur_price = current_prices_map.get(ticker, buy_price)
            pnl_pct = round(((cur_price - buy_price) / buy_price) * 100, 2) if buy_price > 0 else 0.0
            pnl_color = "#d32f2f" if pnl_pct >= 0 else "#388e3c"
            rows_html += f'<tr style="border-bottom:1px solid #c8e6c9;"><td style="padding:8px 6px;"><b>{row.get("Name", ticker)} ({ticker})</b></td><td style="padding:8px 6px;">${buy_price}</td><td style="padding:8px 6px;">${cur_price} (<span style="color:{pnl_color};font-weight:bold;">{pnl_pct:+.2f}%</span>)</td><td style="padding:8px 6px;">{row["Date"]}</td><td style="padding:8px 6px;">{row.get("Hold_Period", "N/A")}</td><td style="padding:8px 6px;">{row.get("Stop_Loss", "N/A")}</td></tr>'
        return f'<div style="background:#e8f5e9; border-left:6px solid #2e7d32; padding:20px; margin-bottom:25px; border-radius:8px;"><h3 style="margin:0 0 12px 0; color:#1b5e20;">🛡️ 当前活跃持仓 (Active Holdings)</h3><table style="width:100%; border-collapse:collapse; font-size:14px;"><tr style="text-align:left; color:#1b5e20; border-bottom:2px solid #a5d6a7;"><th style="padding:6px;">标的</th><th style="padding:6px;">买入价(开盘)</th><th style="padding:6px;">现价 (盈亏)</th><th style="padding:6px;">买入日期</th><th style="padding:6px;">持股周期</th><th style="padding:6px;">止损价</th></tr>{rows_html}</table></div>'
    except Exception as e:
        print(f"⚠️ 生成持仓卡片失败: {e}")
        return ""


def send_mail(to_emails, subject, content):
    user, pwd = os.environ.get("EMAIL_ACCOUNT"), os.environ.get("EMAIL_PASSWORD")
    if not user: return
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


# ==========================================
# 5b. 入库入账：把 AI 报告逐项匹配回 pool_data（结构化切块版）
# ==========================================
def match_pool_to_report(pool_data, ai_generated_html, default_stop_loss_pct):
    """
    原来的实现是在整篇清洗后的纯文本里 find 票名/代码，再用"前300字符+后200字符"的
    固定窗口去猜这只票属于 Top1-5 / 观察池 / 诱多对照组中的哪一块。这在 Top1-5 小节里
    只有开头一次"Top 1-5"字样、后面几张卡片离标题太远时会导致 Top2-5 全部判不到标签
    （连候选池 chosen 都进不去），评分正则也没处理"评分:[74]/100"里的方括号，导致
    Score 恒为 N/A、写账时又被过滤掉——两个问题叠加，Top1-5 基本无法正常入账。

    这里改成按 HTML 结构先切成"核心区 / 观察池 / 诱多对照组"三个互不重叠的区域，
    核心区再按每张 <div class="top-card..."> 卡片切块，观察池/诱多对照组按每个
    <li> 切块，然后只在每只票"自己的"那一小块里查找和解析，不再靠字符数猜。
    """
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

    core_cards = [clean_fragment(c) for c in re.split(r'(?=<div class="top-card)', core_zone_raw) if 'top-card' in c]
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

        if tag is None:
            continue
        if tag == "Trap_Warning":
            continue

        period_match = re.search(r'周期\s*[:：]\s*\[?(\d+[-~]\d+天|\d+天|观望)', chunk)
        sl_match = re.search(r'止损\s*[:：]\s*\[?(\$?[\d\.]+[元%]?|-[\d\.]+%?)', chunk)

        if tag == "Observation":
            hold_period = "观望"
            stop_loss = "观望"
            score = "N/A"
        else:
            hold_period = period_match.group(1).strip() if period_match else "5-10天"
            stop_loss = sl_match.group(1).strip() if sl_match else f"{round(item['Price'] * (1 + default_stop_loss_pct / 100), 2)}"
            score_match = re.search(r'评分\s*[:：]\s*\[?(\d{1,3})\]?\s*/\s*100', chunk)
            score = score_match.group(1).strip() if score_match else "N/A"

        item['Tag'] = tag
        item['Hold_Period'] = hold_period
        item['Stop_Loss'] = stop_loss
        item['Score'] = score
        chosen.append(item)

    return chosen


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

    rule_sell_signals, removed_tickers_rule = check_rule_based_sell_signals(
        current_prices, exclude_tickers=list(dropped_info.keys())
    )
    restricted_tickers.update(removed_tickers_rule)

    sell_signal_card_html = build_sell_signal_card(dropped_info, rule_sell_signals)
    current_holdings_card_html = ""

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
        if sell_signal_card_html or current_holdings_card_html:
            fallback_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>⚠️ 今日选股流程未完成，仅推送风控信号与持仓</h1>{sell_signal_card_html}{current_holdings_card_html}</div></body></html>"
            send_mail(SUPER_ADMIN, f"【美股风控信号与持仓】{datetime.date.today()}", fallback_html)
        exit(0)

    sector_tech_data = screen_technical_setups(pool_data)
    pool_data = enrich_pool_with_news(pool_data)

    ai_generated_html = generate_ai_report(pool_data, combined_news, macro_market, dropped_info, combined_embargo_text, sector_tech_data)
    ai_generated_html = sell_signal_card_html + current_holdings_card_html + ai_generated_html
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>🎯 宏观驱动美股波段内参：{TARGET_REGION}</h1>\n{ai_generated_html}\n<p style='text-align:center; color:#999; font-size:12px; margin-top:40px;'>[END_OF_QUANT_REPORT]</p></div></body></html>"

    try:
        with open("report.html", "w", encoding="utf-8") as f:
            f.write(full_html)
        print("report.html 已成功存入本地！")
    except Exception as e:
        print(f"report.html 写入失败: {e}")

    mail_subject = f"【宏观驱动美股版】{TARGET_REGION} 核心打分与实战 ({datetime.date.today()})"
    send_mail(SUPER_ADMIN, mail_subject, full_html)

    chosen = match_pool_to_report(pool_data, ai_generated_html, DEFAULT_STOP_LOSS_PCT)

    log_file = "trade_history.csv"
    need_header = not os.path.exists(log_file) or os.path.getsize(log_file) == 0
    try:
        FROZEN_STATUSES = {'Dropped', 'Stop_Loss_Hit'}
        REQUALIFY_MARGIN = 10
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

        chosen_to_write = [
            i for i in chosen
            if _requalifies(i)
            and str(i.get('Hold_Period', '')).strip().lower() not in _INVALID_W
            and str(i.get('Stop_Loss', '')).strip().lower() not in _INVALID_W
            and str(i.get('Score', '')).strip().lower() not in {'', 'n/a', 'nan', 'none'}
        ]
        skipped = len(chosen) - len(chosen_to_write)
        if skipped > 0:
            print(f"⏭️ 写账过滤：跳过 {skipped} 条（已斩仓或三字段不完整），不写入新追踪记录。")

        ts_date = datetime.datetime.now().strftime('%Y-%m-%d')
        ts_date_file = datetime.datetime.now().strftime('%Y%m%d')

        if chosen_to_write:
            pending_file = f"us_stocks_pending_{ts_date_file}.csv"
            # ✅ 【改动】不再写入"买入价"：这里的 Open_Price/Price 是盘前拿到的最近一次行情
            # （build_stock_pool 里 latest['Open']/latest['Close']），不是今天的真实开盘/收盘价，
            # 写进待确认文件会被当成买入成本使用，导致盈亏算错。真实开盘价+收盘价改由盘后
            # review.py 用 yfinance 的完整行情数据统一补齐写入 trade_history.csv。
            # 同时去掉了 Industry/Amount/Daily_Pct（在 trade_history.csv 里本来就没有对应列，
            # 写了也到不了账本），改成写 RSI/Bias 以及 evolve.py 真正会用到、但之前从没被
            # 传下去过的 5 个技术信号字段（技术评分/MACD金叉/周线共振/KDJ_J回升/量能放大——
            # 这些值在 screen_technical_setups 里已经算好了，只是没接进 pending 文件）。
            #
            # ✅ 【新增】Scan_Ref_Price 同样不是给人看的"价格"，是给 review.py 校准止损位用的
            # 内部锚点：Stop_Loss 本身也是在这里、用同一个盘前参考价算出来的兜底公式
            # （item['Price'] * (1+default_stop_loss_pct/100)，见 match_pool_to_report）。
            # 参考价不准，止损位这个"锚点"从一开始就偏了。review.py 拿到真实开盘价后会按比例
            # （真实开盘价/Scan_Ref_Price）平移止损位，这个字段只用于那一次计算。
            pending_header = "Date,Ticker,Name,Tag,RSI,Bias,技术评分,MACD金叉,周线共振,KDJ_J回升,量能放大,Hold_Period,Stop_Loss,Score,Status,Scan_Ref_Price\n"
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
                    f.write(f"{ts_date},{ticker},{name},{tag},{rsi},{bias},{tech_score},{macd_cross},{weekly_sync},{kdj_rising},{vol_surge},{hold_period},{stop_loss},{score},pending,{scan_ref_price}\n")

            print(f"✅ 共生成 {len(chosen_to_write)} 条美股推荐记录（已保存至 {pending_file}，不含价格）")
            print(f"⏳ 开盘价/收盘价将在盘后 review.py 执行时用完整行情数据补充写入 trade_history.csv")
        else:
            print(f"⚠️ 未生成任何推荐记录（全部被过滤）")

    except Exception as e:
        print(f"新推荐数据入账失败: {e}")
