# 美股自动进化版本 | 时间: 2026-06-12 19:03 | 触发胜率: 15.4%

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
DEFAULT_STOP_LOSS_PCT = -3.0  # 收紧止损从-5%到-3%

SUPER_ADMIN = os.environ.get("TARGET_EMAILS")

if not SUPER_ADMIN:
    print("致命错误：未检测到 TARGET_EMAILS！")
    exit(1)

print(f"启动：宏观驱动美股扫描引擎 v2.0 | 引擎: {TARGET_MODEL}")

# ==========================================
# 核心反爬组件：构造高健壮性的 Session
# ==========================================
def get_robust_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.yahoo.com/"
    })
    return session
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
        root = ET.f   items = root.findall('.//item')[:max_items]
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
# 4. 拉取 K 线，计算技术指标 + 趋势/动量/量能综合评分
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
    print(f"正在计算技术面风控数据（含趋势+量能过滤），扫描 {len(tickers)} 只标的...")
    for ts_code, name in tickers.items():
        try:
            df = get_kline_data(ts_code)
            if df is None or df.empty or len(df) < 40:
                continue

            # 核心技术指标计算
            df['MACDh'] = ta.macd(df['Close']).iloc[:, 1]
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df['MA5'] = ta.sma(df['Close'], length=5)
            df['Vol_MA5'] = ta.sma(df['Volume'], length=5)
            df['Vol_MA20'] = ta.sma(df['Volume'], length=20)
            df = df.dropna()
            if len(df) < 6:
                continue

            latest = df.iloc[-1]
            prev = df.iloc[-2]
            prev2 = df.iloc[-3]

            # === 趋势过滤器（新增）===
            # 条件1：价格必须在MA20上方
            price_above_ma20 = latest['Close'] > latest['MA20']
            # 条件2：MA20必须向上（5日斜率 > 0）
            ma20_slope = (df['MA20'].iloc[-1] - df['MA20'].iloc[-5]) / df['MA20'].iloc[-5] * 100
            ma20_rising = ma20_slope > 0
            # 条件3：价格在MA5上方（短期趋势确认）
            price_above_ma5 = latest['Close'] > latest['MA5']

            # 如果不满足趋势条件，直接跳过
            if not (price_above_ma20 and ma20_rising):
                continue

            # === 乖离率（仅接受正乖离 0%~8%）===
            bias = (latest['Close'] - latest['MA20']) / latest['MA20'] * 100
            if bias < 0 or bias > 8:
                continue

            # === RSI过滤（收紧到40-68区间）===
            rsi_val = latest['RSI']
            if rsi_val < 40 or rsi_val > 68:
                continue

            # === 成交量动能确认（新增）===
            vol_ratio = latest['Vol_MA5'] / latest['Vol_MA20'] if latest['Vol_MA20'] > 0 else 0
            vol_confirmed = vol_ratio >= 1.2

            # === MACD强确认（新增：要求柱状图连续2日放大）===
            macd_expanding = (latest['MACDh'] > prev['MACDh']) and (prev['MACDh'] > prev2['MACDh'])
            macd_positive = latest['MACDh'] > 0  # MACD柱状图为正（多头区间）

            # === 综合评分公式（新增）===
            # 趋势强度分(40%)：基于MA20斜率和价格相对位置
            trend_score = min(ma20_slope * 10, 40)  # MA20斜率越陡越好，封顶40分

            # 动量分(30%)：基于RSI位置和MACD状态
            rsi_momentum = (rsi_val - 40) / 28 * 15  # RSI在40-68之间映射到0-15分
            macd_momentum = 15 if macd_expanding and macd_positive else (8 if macd_positive else 0)
            momentum_score = rsi_momentum + macd_momentum

            # 量能分(30%)：基于成交量比率
            volume_score = min(vol_ratio * 15, 30)  # 量比越大越好，封顶30分

            total_score = round(trend_score + momentum_score + volume_score, 1)

            # === MACD趋势描述（细化）===
            if macd_expanding and macd_positive:
                macd_trend = "强势放大"
            elif maend = "多头区间"
            elif latest['MACDh'] > prev['MACDh']:
                macd_trend = "底部收敛"
            else:
                macd_trend = "走弱"

            clean_ticker = ts_code.split('.')[0] if '.' in ts_code else ts_code
            pool.append({
                "Ticker": clean_ticker,
                "ts_code": ts_code,
                "Name": name,
                "Price": round(latest['Close'], 2),
                "RSI": round(rsi_val, 1),
                "乖离率(%)": round(bias, 2),
                "MACD趋势": macd_trend,
                "量比": round(vol_ratio, 2),
                "MA20斜率(%)": round(ma20_slope, 2),
                "综合评分": total_score,
                "成交量确认": "✅" if vol_confirmed else "⚠️",
                "MACD连续放大": "✅" if macd_expanding else "❌",
                "价格>MA5": "✅" if price_above_ma5 else "❌",
            })
        except Exception:
            continue

    # 按综合评分降序排列（替代原来的abs(RSI-55)排序）
    pool_sorted = sorted(pool, key=lambda x: x['综合评分'], reverse=True)
    print(f"✅ 通过趋势+量能+动量三重过滤后，剩余 {len(pool_sorted)} 只合格标的")
    return pool_sorted[:30]  # 只传Top30给AI，减少噪音

# ==========================================
# 5. Claude 宏观驱动深度推演（流式）
# ==========================================
def generate_ai_report(pool_data, macro_news_text):
    print("开始调用 AI 大脑（趋势确认型选股，严禁逆势抄底）...")
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
            f"量比:{item['量比']} | MA20斜率:{item['MA20斜率(%)']}% | "
            f"综合评分:{item['综合评分']}分 | 成交量确认:{item['成交量确认']} | "
            f"MACD连续放大:{item['MACD连续放大']} | 价格>MA5:{item['价格>MA5']} | "
            f"最新新闻: {news_str}"
        )
    pool_formatted = "\n".join(pool_text_lines)

    prompt = f"""
你是华尔街顶级游资主力量化操盘手及高级期权策略师。你的交易哲学是：【只做趋势确认后的顺势交易，绝不逆势抄底】。
今天是{today_str}。

【核心铁律 - 不可违反】：
1. 只推荐趋势已确认（价格在MA20上方、MA20上升）的标的
2. 绝对不推荐"超跌反弹"、"抄底"、"逆势"类标的
3. 持仓周期严格控制在3-5天，不推荐超过7天的持仓
4. 止损线统一设为买入价下方-3%，不允许更宽的止损
5. 优先选择综合评分最高的标的（评分已基于趋势+动量+量能计算）

【盘前宏观与全球重大快讯（最高优先级）】：
{macro_news_text}

【今日通过趋势+量能+动量三重过滤的合格标的池】（所有标的均已满足：价格>MA20、MA20上升、RSI在40-68、乖离率0-8%）：
{pool_formatted}

字段说明：
- 综合评分：趋势强度(40%)+动量(30%)+量能(30%)加权得分，越高越好
- 量比：近5日均量/20日均量，>1.2代表资金明显流入
- MA20斜率(%)：20日均线5日变化率，越大代表上升趋势越强
- 成交量确认：✅=量比>1.2资金流入确认，⚠️=量能不足需警惕
- MACD连续放大：✅=柱状图连续2日放大动能强劲，❌=动能尚未连续确认
- 价格>MA5：✅=短期趋势健康，❌=短期可能回调

【核心推演任务】：
第一步（宏观选将）：阅读盘前宏观新闻，判断今日美股的主线逻辑，从标的池中挑出与主线最契合且综合评分最高的标的。
第二步（个股新闻排雷）：审查每只候选标的的个股新闻。若发现负面新闻（监管风险、业绩下调、内部人抛售、诉讼、CEO离职等），即使评分高也必须降级或排除。
第三步（技术优中选优）：从通过前两步的标的中，优先选择同时满足以下条件的：
- 综合评分≥50分
- 成交量确认为✅
- MACD连续放大为✅
- 价格>MA5为✅

【硬性纪律】：
1. 同一只股票绝对不能在报告中重复出现
2. Core_Dragon的Top1-3必须是评分最高且完全满足趋势条件的标的
3. 风控底线格式："周期:[3-5天] | 止损:[$具体价格]"（止损=当前价×0.97）
4. 观察池标的的风控格式："周期:[观望] | 止损:[不参与]"
5. 严格按以下HTML骨架直出，不加markdown外框：

<div style="background: #e3f2fd; border-left: 6px solid #1565c0; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #0d47a1;">🌍 宏观资金定调与主线研判</h3>
    <p>(深度穿透盘前快讯，明确指出今日美股应进攻的产业主线和必须回避的雷区，不少于150字)</p>
</div>

<h2 style="color: #1a237e; border-bottom: 2px solid #1a237e; padding-bottom: 5px;">👑 宏观主线优选 (Top 1-3)</h2>
<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">1. [股票名] ([代码]) | 综合评分:[X]分 | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔥 宏观驱动与主线逻辑:</span> (说明为什么它最契合今天的宏观主线)</p>
    <p><span class='highlight-label bg-blue'>📈 趋势确认与技术安全垫:</span> (引用MA20斜率、量比、MACD连续放大状态说明趋势已确认)</p>
    <p><span class='highlight-label bg-green'>📰 个股新闻核查:</span> (说明该股近期新闻是否有风险)</p>
    <p><span class='highlight-label bg-orange'>⚠️ 潜伏与风控底线:</span> 周期:[3-5天] | 止损:[$具体价格]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(明确建议，到期日不超过2周)</li><li><b>期权组合构建：</b>(单腿买入还是价差防守？)</li></ul>
    </div>
</div>

<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">2. [股票名] ([代码]) | 综合评分:[X]分 | RSI:[数值] | 乖离率:[数值]%</div>
    <p><span class='highlight-label bg-red'>🔥 宏观驱动与主线逻辑:</span> (...)</p>
    bg-blue'>📈 趋势确认与技术安全垫:</span> (...)</p>
    bg-green'>📰 个股新闻核查:</span> (...)</p>
 bel bg-orange'>⚠️ 潜伏与风控底线:</span> 周期:[3-5天] | 止损:[$具体价格]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li></ul>
    </div>
</div>

<div class="top-card core-card">
    <div class="top-title" style="color: #d32f2f;">3. [股票名] ([代码]) | 综合评分:[X]分 | RSI:[数值] | 乖离率:[数值]%</dght-label bg-red'>🔥 宏观驱动与主线逻辑:</span> (...)</p>
    <p><span class='highlight-label bg-blue'>📈 趋势确认与技术安全垫:</span> (...)</p>
 bel bg-green'>📰 个股新闻核查:</span> (...)</p>
    <p><span class='highlight-label bg-orange'>⚠️ 潜伏与风控底线:</span> 周期:[3-5天] | 止损:[$具体价格]</p>
    <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
        <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li></ul>
    </div>
</div>

<div class="compare-card">
    <div class="compare-title">🎖️ 观察池及硬伤诊断 (Rank 4-10)</div>
    <ul>
        <li><b>4. [股票名] ([代码]) - 评分:[X]分 RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">未入选原因：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[观望] | 止损:[不参与]</li>
        <li><b>5. [股票名] ([代码]) - 评分:[X]分 RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">未入选原因：</span>(...) <br><snge'>⚠️ 风控:</span> 周期:[观望] | 止损:[不参与]</li>
        <li><b>6. [股票名] ([代码]) - 评分:[X]分 RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">未入选原因：</span>(...) <br><snge'>⚠️ 风控:</span> 周期:[观望] | 止损:[不参与]</li>
        <li><b>7. [股票名] ([代码]) - 评分:[X]分 RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">未入选原因：</span>(...) <br><snge'>⚠️ 风控:</span> 周期:[观望] | 止损:[不参与]</li>
        <li><b>8. [股票名] ([代码]) - 评分:[X]分 RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">未入选原因：</span>(...) <br><snge'>⚠️ 风控:</span> 周期:[观望] | 止损:[不参与]</li>
        <li><b>9. [股票名] ([代码]) - 评分:[X]分 RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">未入选原因：</span>(...) <br><snge'>⚠️ 风控:</span> 周期:[观望] | 止损:[不参与]</li>
        <li><b>10. [股票名] ([代码]) - 评分:[X]分 RSI:[数值] 乖离率:[数值]%:</b> <span style="color: #388e3c;">未入选原因：</span>(...) <br><snge'>⚠️ 风控:</span> 周期:[观望] | 止损:[不参与]</li>
    </ul>
</div>

<div style="background: #fbfcfe; border-left: 5px solid #388e3c; padding: 25px; margin-bottom: 25px; border-radius: 10px;">
    <h3 style="color: #388e3c; margin-top: 0;">🚨 诱多对照组（严禁接盘）</h3>
    <p style="font-size:13px; color:#666;">以下标的虽在活跃标的池中，但因新闻风险、趋势未确认或技术背离等原因被剔除：</p>
    <ul>
        <li><b>倒数1. [股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">剔除原因：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[坚决空仓] | 止损:[绝对规避]</li>
        <li><b>倒数2. [股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">剔除原因：</span>(...) <br><span class='highlight-label bg-orange'>⚠️ 风控:</span> 周期:[坚决空仓] | 止损:[绝对规避]</li>
    </ul>
</div>
"""

    ai_html = ""
    with client.messages.stream(
        model=TARGET_MODEL,
        max_tokens=4096,
        temperature=0.2,  # 降低温度，减少随机性
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for text in stream.text_stream:
            ai_html += text

    print("AI 趋势确认型报告生成完毕")
    return ai_html.replace("html", "").replace("", "").strip()

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
        print("数据池为空（无标的通过趋势过滤），跳过执行。")
        exit(0)

    # 补充个股新闻
    pool_data = enrich_pool_with_news(pool_data)

    ai_generated_html = generate_ai_report(pool_data, macro_news)
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>🎯 宏观驱动美股波段内参 v2.0：{TARGET_REGION}</h1>\n{ai_generated_html}\n<p style='text-align:center; color:#999; font-size:12px; margin-top:40px;'>[END_OF_QUANT_REPORT]</p></div></body></html>"

    try:
        with open("report.html", "w", encoding="utf-8") as f:
            f.write(full_html)
        print("report.html 已成功存入本地！")
    except Exception as e:
        print(f"report.html 写入失败: {e}")

    mail_subject = f"【趋势确认美股版v2.0】{TARGET_REGION} 核心打分与实战 ({datetime.date.today()})"
    send_mail(SUPER_ADMIN, mail_subject, full_html)

    # 入库（仅Core_Dragon入库，Observation不入库）
    chosen = []
    clean_html = re.sub(r'<[^>]+>', ' ', ai_generated_html)
    clean_html = re.sub(r'\s+', ' ', clean_html)

    for item in pool_data:
        ticker_str = str(item['Ticker'])
        name_str = str(item['Name'])
        
        # 先搜索Ticker，再搜索Name
        idx = clean_html.find(f"({ticker_str})")
        if idx == -1:
            idx = clean_html.find(ticker_str)
        if idxean_html.find(name_str)
        if idx == -1:
            continue

        # 限制上下文范围，避免跨标的污染
        chunk_start = idx
        chunk_end = min(idx + 800, len(clean_html))  # 缩小搜索范围从1500到800
        chunk = clean_html[chunk_start:chunk_end]
        
        # 上下文判断标签（缩小上文范围避免污染）
        context_before = clean_html[max(0, idx-200):idx]
        context = context_before + chunk[:300]

        tag = None
        if "宏观主线优选" in context or "Top 1-3" in context:
            # 确认是在Top区域且直接提到了这个Ticker
            tag = "Core_Dragon"
        elif "观察池" in context or "Rank 4" in context:
            tag = "Observation"
        elif "诱多" in context or "坚决空仓" in context or "严禁接盘" in context:
            tag = "Trap_Warning"

        if tag is None:
            continue

        # 仅Core_Dragon入库，Observation和Trap_Warning不入库跟踪
        if tag != "Core_Dragon":
            continue

        # 改进止损解析：在有限范围内搜索，避免跨标的
        period_match = re.search(r'周期\s*[:：]\s*\[?(\d+[-~]\d+天|\d+天)', chunk[:500])
        sl_match = re.search(r'止损\s*[:：]\s*\[?\$?([\d\.]+)', chunk[:500])

        hold_period = period_match.group(1).strip() if period_match else "3-5天"
        
        if sl_match:
            stop_loss = f"${sl_match.group(1)}"
        else:
            # 默认止损：当前价×0.97（-3%）
            stop_loss = f"${round(item['Price'] * 0.97, 2)}"

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
                f.write(f"{ts_date},{i.get('Ticker','')},{i.get('Name','')},{i.get('Tag','')},{i.get('综合评分',0)},{i.get('Price','')},{i.get('RSI',0)},{i.get('乖离率(%)',0)},{i.get('Hold_Period','N/A')},{i.get('Stop_Loss','N/A')}\n")
        print(f"共安全记账 {len(chosen)} 条核心数据（仅Core_Dragon入库）。")
    except Exception as e:
        print(f"账本写入失败: {e}")
