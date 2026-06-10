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
import io  # <--- 新增这行，用于处理文本流
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

today = datetime.datetime.now().weekday()
if today >= 5:
    print(f"[{datetime.datetime.now()}] 周末休市，脚本自动跳过。")
    exit()

# 已修正：严格执行模型引擎要求 (Pro / Flash)
TARGET_MODEL = 'claude-opus-4-8'
TARGET_REGION = "美国市场"
DEFAULT_STOP_LOSS_PCT = -5.0

SUPER_ADMIN = os.environ.get("TARGET_EMAILS")

if not SUPER_ADMIN:
    print("致命错误：未检测到 TARGET_EMAILS！")
    exit(1)

print(f"启动：宏观驱动美股扫描引擎 | 引擎: {TARGET_MODEL}")

# ==========================================
# 核心反爬组件：构造高健壮性的 Session
# ==========================================
# 在 get_robust_session 中添加代理配置
def get_robust_session():
    session = requests.Session()
    # 尝试使用免费的旋转代理池（如果无法使用，请删掉 proxies 部分）
    # 或者直接使用 yfinance 官方提供的 proxy 参数
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.yahoo.com/" # 雅虎现在要求referer
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
# 2. 个股新闻（Yahoo Finance RSS + 随机休眠）
# ==========================================
def get_stock_news(ticker, max_items=3):
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
        time.sleep(random.uniform(0.5, 1.5))  # 动态随机休眠，防反爬
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
            tables = pd.read_html(io.StringIO(html))  # <--- 修改这里，用 io.StringIO 包裹
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
    
    # 增加 threads=False 关闭并发，避免瞬间触发 429 IP 封禁
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
# 4. 拉取 K 线，计算技术指标 (yfinance接入)
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
    print(f"正在计算技术面风控数据，扫描 {len(tickers)} 只标的...")
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

    pool_sorted = sorted(pool, key=lambda x: abs(x['RSI'] - 55))
    return pool_sorted[:40]

# ==========================================
# 5. Claude/Gemini 宏观驱动深度推演（流式）
# ==========================================
def generate_ai_report(pool_data, macro_news_text):
    print("开始调用 AI 大脑（宏观先行，技术风控，个股新闻预警）...")
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

    prompt = f"""
你是华尔街顶级游资主力量化操盘手及高级期权策略师。你的交易哲学是：【宏观定方向，产业定主线，个股新闻排雷，技术定买卖】。
今天是{today_str}。

【盘前宏观与全球重大快讯（最高优先级）】：
{macro_news_text}

【今日美股成交最活跃的 Top 40 标的池】（含技术数据 + 个股最新新闻）：
{pool_formatted}

字段说明：
- 乖离率(%)：偏离20日均线的幅度，绝对值越小越安全，超过15%需警惕
- RSI：超过75为超买危险区，低于30为超卖
- MACD趋势：走强代表动能向上，走弱代表动能减弱
- 最新新闻：该股票最近的新闻标题，用于排查个股风险（如监管调查、业绩预警、CEO离职、诉讼等）

【核心推演任务】：
第一步（宏观选将）：深刻阅读盘前宏观新闻，判断今日美股的主线逻辑，从标的池中挑出与主线最契合的标的。
第二步（个股新闻排雷）：审查每只候选标队的个股新闻。若发现负面新闻（监管风险、业绩下调、内部人抛售、诉讼、CEO离职等），即使技术面健康也必须列入诱多对照组或降级处理。
第三步（技术风控）：对通过新闻排雷的标的进行技术审查。
- 技术面安全（乖离率<12%，RSI<75）→ 列为核心Top1-3或观察池Rank4-10
- 技术极度危险（乖离率>15%或RSI>80）→ 列入诱多对照组

【硬性纪律】：
1. 同一只股票绝对不能在报告中重复出现
2. 风控底线必须明确输出"周期:[X-Y天] | 止损:[具体价格或百分比]"
3. 个股新闻中若有任何负面信号，必须在分析中点名说明
4. 严格按以下HTML骨架直出，不加markdown外框：

<div style="background: #e3f2fd; border-left: 6px solid #1565c0; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #0d47a1;">🌍 宏观资金定调与主线研判</h3>
    <p>(深度穿透盘前快讯，明确指出今日美股应进攻的产业主线和必须回避的雷区，不少于150字)</p>
</div>

<h2 style="color: #1a237e; border-bottom: 2px solid #1a237e; padding-bottom: 5px;">👑 宏观主线优选 (Top 1-3)</h2>
<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">1. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔥 宏观驱动与主线逻辑:</span> (说明为什么它最契合今天的宏观主线)</p>
    <p><span class='highlight-label bg-blue'>📈 技术面安全垫:</span> (引用乖离率、RSI、MACD说明买点安全性)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (说明该股近期新闻是否有风险，若无负面则说明新闻面干净)</p>
    <p><span class='highlight-label bg-orange'>⚠️ 潜伏与风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(明确建议)</li><li><b>期权组合构建：</b>(单腿买入还是价差防守？)</li></ul>
    </div>
</div>

<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">2. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔥 宏观驱动与主线逻辑:</span> (...)</p>
    <p><span class='highlight-label bg-blue'>📈 技术面安全垫:</span> (...)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (...)</p>
    <p><span class='highlight-label bg-orange'>⚠️ 潜伏与风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li></ul>
    </div>
</div>

<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">3. [股票名] ([代码]) | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔥 宏观驱动与主线逻辑:</span> (...)</p>
    <p><span class='highlight-label bg-blue'>📈 技术面安全垫:</span> (...)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (...)</p>
    <p><span class='highlight-label bg-orange'>⚠️ 潜伏与风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li></ul>
    </div>
</div>

<div class="compare-card">
    <div class="compare-title">🎖️ 观察池及硬伤诊断 (Rank 4-10)</div>
    <ul>
        <li><b>4. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">宏观或技术硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[X-Y天或观望] | 止损:[具体价格]</li>
        <li><b>5. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[X-Y天或观望] | 止损:[具体价格]</li>
        <li><b>6. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[X-Y天或观望] | 止损:[具体价格]</li>
        <li><b>7. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[X-Y天或观望] | 止损:[具体价格]</li>
        <li><b>8. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[X-Y天或观望] | 止损:[具体价格]</li>
        <li><b>9. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[X-Y天或观望] | 止损:[具体价格]</li>
        <li><b>10. [股票名] ([代码]) - RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[X-Y天或观望] | 止损:[具体价格]</li>
    </ul>
</div>

<div style="background: #fbfcfe; border-left: 5px solid #388e3c; padding: 25px; margin-bottom: 25px; border-radius: 10px;">
    <h3 style="color: #388e3c; margin-top: 0;">🚨 诱多对照组（严禁接盘）</h3>
    <ul>
        <li><b>倒数1. [股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">宏观、技术或个股新闻硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[坚决空仓] | 止损:[绝对规避]</li>
        <li><b>倒数2. [股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">宏观、技术或个股新闻硬伤：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[坚决空仓] | 止损:[绝对规避]</li>
    </ul>
</div>
"""

    ai_html = ""
    with client.messages.stream(
        model=TARGET_MODEL,
        max_tokens=4096,
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
    .compare-card { border-left: 5px solid #ff9800; background: #fffdf7; padding: 25px; margin-bottom: 25px; border-radius: 10px; border: 1px solid #ffe0b2;}
    .compare-title { font-size: 19px; color: #e65100; font-weight: bold; margin-bottom: 15px; border-bottom: 1px solid #ffe0b2; padding-bottom: 10px;}
    ul { padding-left: 22px; margin-top: 0;}
    li { margin-bottom: 10px; font-size: 15px; }
</style>
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
    raw_tickers = get_scan_pool()
    pool_data = build_stock_pool(raw_tickers)

    if not pool_data:
        print("数据池为空，跳过执行。")
        exit(0)

    # 补充个股新闻
    pool_data = enrich_pool_with_news(pool_data)

    ai_generated_html = generate_ai_report(pool_data, macro_news)
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>🎯 宏观驱动美股波段内参：{TARGET_REGION}</h1>\n{ai_generated_html}\n<p style='text-align:center; color:#999; font-size:12px; margin-top:40px;'>[END_OF_QUANT_REPORT]</p></div></body></html>"

    try:
        with open("report.html", "w", encoding="utf-8") as f:
            f.write(full_html)
        print("report.html 已成功存入本地！")
    except Exception as e:
        print(f"report.html 写入失败: {e}")

    mail_subject = f"【宏观驱动美股版】{TARGET_REGION} 核心打分与实战 ({datetime.date.today()})"
    send_mail(SUPER_ADMIN, mail_subject, full_html)

    # 入库
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
        if "宏观主线优选" in context or "core-card" in context or "Top 1" in context or "Top 2" in context or "Top 3" in context:
            tag = "Core_Dragon"
        elif "观察池" in context or "Rank 4" in context or "Rank 5" in context or "Rank 6" in context or "Rank 7" in context or "Rank 8" in context or "Rank 9" in context or "Rank 10" in context:
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
        else:
            hold_period = period_match.group(1).strip() if period_match else "5-10天"
            stop_loss = sl_match.group(1).strip() if sl_match else f"{round(item['Price'] * (1 + DEFAULT_STOP_LOSS_PCT / 100), 2)}"

        item['Tag'] = tag
        item['Hold_Period'] = hold_period
        item['Stop_Loss'] = stop_loss
        chosen.append(item)

    log_file = "trade_history.csv"
    need_header = not os.path.exists(log_file) or os.path.getsize(log_file) == 0
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            if need_header:
                f.write("Date,Ticker,Name,Tag,Score,Price,RSI,Bias,Hold_Period,Stop_Loss\n")
            ts_date = datetime.datetime.now().strftime('%Y-%m-%d')
            for i in chosen:
                f.write(f"{ts_date},{i.get('Ticker','')},{i.get('Name','')},{i.get('Tag','')},0,{i.get('Price','')},{i.get('RSI',0)},{i.get('乖离率(%)',0)},{i.get('Hold_Period','N/A')},{i.get('Stop_Loss','N/A')}\n")
        print(f"共安全记账 {len(chosen)} 条核心数据。")
    except Exception as e:
        print(f"账本写入失败: {e}")
