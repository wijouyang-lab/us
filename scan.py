# -*- coding: utf-8 -*-
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
    
    session = get_robust_session()
    lines = []
    for name, ticker in macro_tickers.items():
        try:
            df = yf.download(ticker, period="5d", progress=False, session=session)
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

    data = yf.download(tickers_list, period="1d", group_by='ticker', auto_adjust=True, progress=False, session=session, threads=False)

    vols = {}
    for t in tickers_list:
        try:
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
    session = get_robust_session()
    for attempt in range(3):
        try:
            df = yf.download(ts_code, period="6mo", progress=False, session=session)
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
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df = df.dropna()
            if len(df) < 6:
                continue

            latest, prev = df.iloc[-1], df.iloc[-2]
            bias = (latest['Close'] - latest['MA20']) / latest['MA20']
            macd_trend = "走强" if latest['MACDh'] > prev['MACDh'] else "走弱"

            clean_ticker = ts_code.split('.')[0] if '.' in ts_code else ts_code
            pool.append({
                "Ticker": clean_ticker,
                "ts_code": ts_code,
                "Name": name,
                "Price": round(latest['Close'], 2),
                "RSI": round(latest['RSI'], 1),
                "乖离率(%)": round(bias * 100, 2),
                "MACD趋势": macd_trend,
            })
        except Exception:
            continue

    print(f"✅ 技术面数据计算完毕，共 {len(pool)} 只标的进入新闻+逻辑分析阶段。")
    return pool


# ==========================================
# 新增功能：盘前现有持仓排雷审查相位（Phase 0）
# ==========================================
def pre_scan_portfolio_review(macro_news_text, macro_market_text):
    log_file = "trade_history.csv"
    if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
        print("📌 交易账本不存在或为空，自动跳过盘前现有持仓审查。")
        return set(), {}
        
    try:
        df = pd.read_csv(log_file)
    except Exception as e:
        print(f"⚠️ 读取 trade_history.csv 失败: {e}")
        return set(), {}
        
    # 自动向后兼容升级账本表头
    required_cols = ["Exit_Date", "Exit_Price", "Status"]
    headers_need_rewrite = False
    for col in required_cols:
        if col not in df.columns:
            df[col] = "Active" if col == "Status" else "N/A"
            headers_need_rewrite = True
            
    if headers_need_rewrite:
        df.to_csv(log_file, index=False, encoding="utf-8")
        
    # 筛选处于活跃持仓状态的股票
    active_rows = df[df['Status'] == 'Active'].copy()
    if active_rows.empty:
        print("📌 当前无可执行风控追踪的活跃持仓标的。")
        return set(), {}

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
        return set(), {}
        
    print(f"🔍 识别到 {len(active_rows)} 个活跃追踪头寸，开始提取个股最新动态进行宏观风控审查...")
    active_tickers = active_rows['Ticker'].unique().tolist()
    session = get_robust_session()
    
    # 获取实时现价作为可能卖出的执行参考价
    # 优先级：
    #   1. yf.Ticker.fast_info["last_price"] —— 实时/盘前价，只要市场有成交就有数据
    #   2. yf.download(period="1d") iloc[-1]  —— 盘后收盘价，盘前可能为空
    #   3. 买入价兜底                          —— 打印警告，盈亏=0
    current_prices = {}
    session = get_robust_session()

    # 方案1：逐只用 fast_info 拿实时价（含盘前/盘后延伸交易时段）
    realtime_success = []
    for t in active_tickers:
        try:
            info = yf.Ticker(t, session=session).fast_info
            price = info.get("last_price") or info.get("lastPrice")
            if price and float(price) > 0:
                current_prices[t] = round(float(price), 2)
                realtime_success.append(t)
        except Exception:
            pass

    if realtime_success:
        print(f"✅ 实时价拉取成功（fast_info），覆盖 {len(realtime_success)}/{len(active_tickers)} 只持仓")

    # 方案2：未拿到实时价的 ticker 用 yf.download 昨收兜底
    missing = [t for t in active_tickers if t not in current_prices]
    if missing:
        try:
            price_data = yf.download(missing, period="1d", progress=False, session=session, auto_adjust=True)
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
        
    return restricted_tickers, dropped_info


# ==========================================
# 5. Claude 宏观+个股新闻驱动深度推演（流式，Top5详细分析+1-100评分）
# ==========================================
def generate_ai_report(pool_data, macro_news_text, macro_market_text, dropped_info=None):
    print("开始调用 AI 大脑（宏观先行，个股新闻排雷，技术面确认，Top5详细分析+评分）...")
    client = anthropic.Anthropic(
        api_key=os.environ.get("CLAWSOCKET_API_KEY"),
        base_url=os.environ.get("CLAWSOCKET_BASE_URL")
    )
    today_str = datetime.datetime.now().strftime('%Y年%m月%d日')

    pool_text_lines = []
    for item in pool_data:
        news_str = " | ".join(item.get('个股新闻', ['暂无']))
        pool_text_lines.append(
            f"[{item['Ticker']}] {item['Name']} | 价格:${item['Price']} | RSI:{item['RSI']} | "
            f"乖离率:{item['乖离率(%)']}% | MACD:{item['MACD趋势']} | "
            f"最新新闻: {news_str}"
        )
    pool_formatted = "\n".join(pool_text_lines)
    pool_count = len(pool_data)

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

第三步（技术确认）：
只有通过新闻排雷且满足以下条件才能列为核心推荐，否则只能列观察池等待回调：
- 乖离率 < 12%（没有严重偏离均线）
- RSI < 75（没有严重超买）
- MACD走强（动能向上）
若产业链逻辑和新闻面都好但技术已经极度超买（乖离率>20%，RSI>80），列入诱多对照组，等回调再说。

第四步（推荐评分，1-100分，核心要求）：
对每一只进入【核心区】（Top 1-5）的标的，必须给出一个1-100的综合评分，评分依据：
- 产业链逻辑是否直接（直接受益方通常80分以上，二三手受益方但护城河更强可以70-85分，逻辑过于间接的应低于60分）
- 个股新闻是否强力佐证（有正面新闻共振+10~15分，新闻面干净不扣分，有任何负面信号应直接降到观察池）
- 技术面是否健康（乖离率和RSI越接近安全区间越加分，临近超买阈值应扣分）
评分必须客观区分质量差异，禁止5只全部给相近分数，必须体现你对不同标的确信程度的真实差异。

今天是{today_str}。

【盘前宏观与全球重大快讯】：
{macro_news_text}

【实时全球宏观经济指标（国债收益率、大宗商品、主要指数涨跌）】：
{macro_market_text}

【今日成交活跃的 Top {pool_count} 标的池】（含技术数据 + 个股最新新闻，每只票最多6条新闻标题）：
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

【严格按以下HTML骨架直出，不加markdown外框，Top1-5每只都要按这个模板写满】：

<div style="background: #e3f2fd; border-left: 6px solid #1565c0; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #0d47a1;">🌍 今日产业链主线研判</h3>
    <p><b>主线1：</b>(事件 → 传导逻辑 → 直接受益 → 二级受益，不少于150字)</p>
    <p><b>主线2：</b>(同上，如无第二条主线则说明)</p>
    <p><b>今日雷区：</b>(哪些板块/标的因宏观逆风、负面新闻或技术超买必须回避)</p>
</div>

<h2 style="color: #1a237e; border-bottom: 2px solid #1a237e; padding-bottom: 5px;">👑 产业链主线优选 (Top 1-5 详细分析)</h2>
<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">1. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (说明完整的传导链：宏观事件→产业受益→为什么是这只票而不是更直接的受益者，不少于100字)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (基于提供的新闻标题，逐条点评是否有风险，至少提及2-3条具体新闻内容)</p>
    <p><span class='highlight-label bg-blue'>📈 技术确认:</span> (乖离率/RSI/MACD数值具体分析，说明为何这个时点是安全的入场点)</p>
    <p><span class='highlight-label bg-teal'>⭐ 推荐评分:</span> 评分:[XX]/100 — [一句话说明评分理由：逻辑链是否直接、新闻是否强力佐证、技术是否健康]</p>
    <p><span class='highlight-label bg-orange'>⚠️ 风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(明确建议，给出具体strike和expiry时间窗口)</li><li><b>期权组合构建：</b>(单腿买入还是价差防守，说明理由)</li></ul>
    </div>
</div>

<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">2. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (同上详细程度)</p>
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
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (同上详细程度)</p>
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
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (同上详细程度)</p>
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
    <p><span class='highlight-label bg-red'>🔗 产业链逻辑:</span> (同上详细程度)</p>
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
        <li><b>6. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #1565c0;">产业链逻辑：</span>(说明逻辑) <span style="color: #2e7d32;">新闻面：</span>(是否干净) <span style="color: #388e3c;">未入选原因：</span>(技术超买/等回调/逻辑偏弱) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[观望等回调] | 止损:[回调到XX再买]</li>
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
        <li><b>倒数1. [股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">硬伤（技术超买/负面新闻/逻辑反转）：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[坚决空仓或等回调] | 止损:[绝对规避]</li>
        <li><b>倒数2. [股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">硬伤（技术超买/负面新闻/逻辑反转）：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[坚决空仓或等回调] | 止损:[绝对规避]</li>
    </ul>
</div>
"""

    ai_html = ""
    with client.messages.stream(
        model=TARGET_MODEL,
        max_tokens=16000,
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
        df = pd.read_csv(log_file)
        df['Date'] = pd.to_datetime(df['Date'])
        holdings = df[df['Status'] == 'Active'].copy()
        if holdings.empty:
            print("📋 [阶段0b] 当前无 Active 持仓，跳过规则卖出信号检测。")
            return [], []

        # 三字段完整性过滤（只处理新版本有效记录）
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

        # 每只股只取最新一条，排除阶段0a本轮已处理的
        holdings = holdings.sort_values('Date', ascending=False).drop_duplicates(subset='Ticker', keep='first')
        holdings = holdings[~holdings['Ticker'].astype(str).isin(exclude_tickers)]
        if holdings.empty:
            print("📋 [阶段0b] 持仓已被阶段0a全部处理，跳过规则卖出信号检测。")
            return [], []
    except Exception as e:
        print(f"⚠️ [阶段0b] 持仓读取失败: {e}")
        return [], []

    def _parse_hold_days(s):
        s = str(s).strip()
        if not s or s.lower() in _INVALID: return None
        nums = re.findall(r'\d+', s)
        return int(nums[-1]) if nums else None  # 取区间上限，如"5-10天"取10

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

    # 锁定 trade_history.csv 标签
    try:
        df_orig = pd.read_csv(log_file)
        for s in sell_signals:
            tag_to_set = 'Stop_Loss_Hit' if s['signal_type'] == '止损触发' else 'Period_Matured'
            df_orig.loc[df_orig['Ticker'] == s['ticker'], 'Status'] = tag_to_set
            df_orig.loc[df_orig['Ticker'] == s['ticker'], 'Exit_Date'] = datetime.datetime.now().strftime('%Y-%m-%d')
            df_orig.loc[df_orig['Ticker'] == s['ticker'], 'Exit_Price'] = s['current_price']
        df_orig.to_csv(log_file, index=False, encoding="utf-8")
        print(f"🔒 [阶段0b] 已锁定 {len(sell_signals)} 只标的状态（止损触发/持有到期），停止后续追踪")
    except Exception as e:
        print(f"⚠️ [阶段0b] trade_history.csv 状态更新失败: {e}")

    for s in sell_signals:
        icon = "🛑" if s['signal_type'] == '止损触发' else "⏰"
        print(f"{icon} [阶段0b] 卖出信号: {s['name']}({s['ticker']}) — {s['signal_type']} | 现价${s['current_price']} 买入价${s['buy_price']} 盈亏{s['pnl_pct']:+.2f}%")

    return sell_signals, removed_tickers


# ==========================================
# 0c. 统一渲染"今日卖出信号"卡片（阶段0a AI强清 + 阶段0b 规则信号）
# ==========================================
def build_sell_signal_card(dropped_info, rule_sell_signals):
    """
    把阶段0a（AI宏观突发利空强清）与阶段0b（止损触发/持有到期）两类信号
    汇总成一张醒目卡片，插在邮件最顶部，交易时段内可直接执行。
    """
    if not dropped_info and not rule_sell_signals:
        return ""

    rows_html = ""

    # 阶段0a：AI强清（有name和reason）
    for t, info in (dropped_info or {}).items():
        rows_html += f"""
        <tr style="border-bottom:1px solid #ffe0b2;">
            <td style="padding:8px 6px;"><b>{info['name']} ({t})</b></td>
            <td style="padding:8px 6px;"><span style="background:#c62828;color:#fff;padding:2px 7px;border-radius:4px;font-size:12px;">突发利空强清</span></td>
            <td style="padding:8px 6px;" colspan="2">{info['reason']}</td>
        </tr>"""

    # 阶段0b：规则信号
    for s in rule_sell_signals:
        pnl_color = "#d32f2f" if s['pnl_pct'] >= 0 else "#388e3c"
        badge_bg = "#e64a19" if s['signal_type'] == '止损触发' else "#607d8b"
        rows_html += f"""
        <tr style="border-bottom:1px solid #ffe0b2;">
            <td style="padding:8px 6px;"><b>{s['name']} ({s['ticker']})</b></td>
            <td style="padding:8px 6px;"><span style="background:{badge_bg};color:#fff;padding:2px 7px;border-radius:4px;font-size:12px;">{s['signal_type']}</span></td>
            <td style="padding:8px 6px;">买入${s['buy_price']} → 现价${s['current_price']}，<span style="color:{pnl_color};font-weight:bold;">{s['pnl_pct']:+.2f}%</span></td>
            <td style="padding:8px 6px;">{s['reason']}</td>
        </tr>"""

    total = len(dropped_info or {}) + len(rule_sell_signals)
    return f"""
<div style="background:#fff3e0; border-left:6px solid #e65100; padding:20px; margin-bottom:25px; border-radius:8px;">
    <h3 style="margin:0 0 12px 0; color:#bf360c;">🔔 今日卖出信号汇总（共{total}只 · 交易时段内可直接执行）</h3>
    <table style="width:100%; border-collapse:collapse; font-size:14px;">
        <tr style="text-align:left; color:#6d4c41; border-bottom:2px solid #ffb74d;">
            <th style="padding:6px;">标的</th>
            <th style="padding:6px;">触发类型</th>
            <th style="padding:6px;">价格/浮动盈亏</th>
            <th style="padding:6px;">理由</th>
        </tr>
        {rows_html}
    </table>
    <p style="margin:12px 0 0 0; font-size:13px; color:#6d4c41;">以上标的已在 trade_history.csv 中锁定状态并停止后续追踪，买卖价已归档供胜率统计。本卡片仅为系统信号，实际下单时机请结合盘口自行判断。</p>
</div>
"""


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

if __name__ == "__main__":
    macro_news = get_latest_macro_news()
    macro_market = get_macro_market_data()
    
    # 步骤 0a：AI 宏观/消息面驱动的持仓强制清仓审查
    restricted_tickers, dropped_info = pre_scan_portfolio_review(macro_news, macro_market)

    # 步骤 0b：规则驱动卖出信号检测（止损触发 / 持有到期）
    # 需要先拉一次持仓的实时价格供规则判断使用
    holding_price_map = {}
    try:
        log_file_tmp = "trade_history.csv"
        if os.path.exists(log_file_tmp):
            df_tmp = pd.read_csv(log_file_tmp)
            active_tmp = df_tmp[df_tmp['Status'] == 'Active']['Ticker'].dropna().unique().tolist()
            session_tmp = get_robust_session()
            for t in active_tmp:
                try:
                    info = yf.Ticker(t, session=session_tmp).fast_info
                    price = info.get("last_price") or info.get("lastPrice")
                    if price and float(price) > 0:
                        holding_price_map[t] = round(float(price), 2)
                except Exception:
                    pass
    except Exception as e:
        print(f"⚠️ 阶段0b 价格预拉取失败: {e}")

    rule_sell_signals, removed_tickers_rule = check_rule_based_sell_signals(
        holding_price_map, exclude_tickers=list(restricted_tickers)
    )
    # 将规则卖出的 ticker 也加入隔离集，避免今日被重新推荐
    restricted_tickers.update(removed_tickers_rule)

    # 步骤 0c：生成卖出信号卡片（两类信号合并）
    sell_signal_card_html = build_sell_signal_card(dropped_info, rule_sell_signals)

    raw_tickers = get_scan_pool()
    
    # 风控阻断：过滤掉当下属于活跃持仓或者今日因利空被丢弃的股票，避免产生逻辑追踪混淆
    filtered_tickers = {t: n for t, n in raw_tickers.items() if t not in restricted_tickers}

    pool_data = build_stock_pool(filtered_tickers)

    if not pool_data:
        print("无合规扫描数据，今日扫描提前安全熔断。")
        # 兜底：即使主选股流程因数据问题中止，只要有卖出信号也要单独发邮件
        if sell_signal_card_html:
            fallback_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>⚠️ 今日选股流程未完成，仅推送卖出信号</h1>{sell_signal_card_html}</div></body></html>"
            send_mail(SUPER_ADMIN, f"【美股卖出信号】{datetime.date.today()}", fallback_html)
        exit(0)

    pool_data = enrich_pool_with_news(pool_data)

    # 生成报告时 dropped_info 已经通过卡片注入，不再重复注入
    ai_generated_html = generate_ai_report(pool_data, macro_news, macro_market, dropped_info)
    # 卖出信号卡片插在最顶部（优先级高于 AI 报告内容）
    ai_generated_html = sell_signal_card_html + ai_generated_html
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>🎯 宏观驱动美股波段内参：{TARGET_REGION}</h1>\n{ai_generated_html}\n<p style='text-align:center; color:#999; font-size:12px; margin-top:40px;'>[END_OF_QUANT_REPORT]</p></div></body></html>"

    try:
        with open("report.html", "w", encoding="utf-8") as f:
            f.write(full_html)
        print("report.html 已成功存入本地！")
    except Exception as e:
        print(f"report.html 写入失败: {e}")

    mail_subject = f"【宏观驱动美股版】{TARGET_REGION} 核心打分与实战 ({datetime.date.today()})"
    send_mail(SUPER_ADMIN, mail_subject, full_html)

    # 入库入账
    chosen = []
    clean_html = re.sub(r'<[^>]+>', ' ', ai_generated_html)
    clean_html = re.sub(r'\s+', ' ', clean_html)

    for item in pool_data:
        ticker_str = str(item['Name'])
        idx = clean_html.find(ticker_str)
        if idx == -1:
            ticker_str = str(item['Ticker'])
            idx = clean_html.find(ticker_str)
        if idx == -1:
            continue

        chunk = clean_html[idx:idx+1500]
        context = clean_html[max(0, idx-300):idx] + chunk[:200]

        tag = None
        if "宏观主线优选" in context or "core-card" in context or "Top 1" in context or "Top 2" in context or "Top 3" in context or "Top 4" in context or "Top 5" in context:
            tag = "Core_Dragon"
        elif "观察池" in context or "Rank 6" in context or "Rank 7" in context or "Rank 8" in context or "Rank 9" in context or "Rank 10" in context or "Rank 11" in context or "Rank 12" in context:
            tag = "Observation"
        elif "诱多" in context or "坚决空仓" in context:
            tag = "Trap_Warning"

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
            stop_loss = sl_match.group(1).strip() if sl_match else f"{round(item['Price'] * (1 + DEFAULT_STOP_LOSS_PCT / 100), 2)}"
            score_match = re.search(r'评分\s*[:：]\s*\[?(\d{1,3})\s*/\s*100', chunk)
            score = score_match.group(1).strip() if score_match else "N/A"

        item['Tag'] = tag
        item['Hold_Period'] = hold_period
        item['Stop_Loss'] = stop_loss
        item['Score'] = score
        chosen.append(item)

    log_file = "trade_history.csv"
    need_header = not os.path.exists(log_file) or os.path.getsize(log_file) == 0
    try:
        # ── 写账前过滤：剔除已 Dropped（斩仓出局）的 ticker，历史行保留不动供胜率计算 ──
        # 同时过滤三字段不完整的 chosen 项，确保只有新版本有效推荐才写入。
        frozen_tickers: set = set()
        FROZEN_STATUSES = {'Dropped'}
        _INVALID_W = {'', 'n/a', 'nan', 'none', '观望'}
        if not need_header:
            try:
                df_hist_check = pd.read_csv(log_file, on_bad_lines='skip')
                if 'Status' in df_hist_check.columns and 'Ticker' in df_hist_check.columns:
                    frozen_tickers = set(
                        df_hist_check.loc[df_hist_check['Status'].isin(FROZEN_STATUSES), 'Ticker'].astype(str)
                    )
                    if frozen_tickers:
                        print(f"🔒 写账过滤：检测到 {len(frozen_tickers)} 只已斩仓标的 {frozen_tickers}，本次不追加新行（历史买卖价保留）")
            except Exception as e:
                print(f"⚠️ 写账过滤读取 trade_history.csv 失败，不执行冻结过滤: {e}")

        chosen_to_write = [
            i for i in chosen
            if str(i.get('Ticker', '')) not in frozen_tickers
            and str(i.get('Hold_Period', '')).strip().lower() not in _INVALID_W
            and str(i.get('Stop_Loss', '')).strip().lower() not in _INVALID_W
            and str(i.get('Score', '')).strip().lower() not in {'', 'n/a', 'nan', 'none'}
        ]
        skipped = len(chosen) - len(chosen_to_write)
        if skipped > 0:
            print(f"⏭️ 写账过滤：跳过 {skipped} 条（已斩仓或三字段不完整），不写入新追踪记录。")

        with open(log_file, "a", encoding="utf-8") as f:
            if need_header:
                f.write("Date,Ticker,Name,Tag,Score,Price,RSI,Bias,Hold_Period,Stop_Loss,Exit_Date,Exit_Price,Status\n")
            ts_date = datetime.datetime.now().strftime('%Y-%m-%d')
            for i in chosen_to_write:
                f.write(f"{ts_date},{i.get('Ticker','')},{i.get('Name','')},{i.get('Tag','')},{i.get('Score','N/A')},{i.get('Price','')},{i.get('RSI',0)},{i.get('乖离率(%)',0)},{i.get('Hold_Period','N/A')},{i.get('Stop_Loss','N/A')},N/A,N/A,Active\n")
        print(f"共安全记账 {len(chosen_to_write)} 条全新核心优选数据（过滤后）。")
    except Exception as e:
        print(f"新推荐数据入账失败: {e}")
