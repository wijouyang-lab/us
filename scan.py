# -*- coding: utf-8 -*-
import pandas as pd
import pandas_ta as ta
import datetime
import os
import smtplib
import time
import requests
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai 
from google.genai import types

today = datetime.datetime.now().weekday()
if today >= 5:
    print(f"[{datetime.datetime.now()}] 周末休市，脚本自动跳过。")
    exit()

# ==========================================
# ⚙️ 核心引擎锁定与配置
# ==========================================
TARGET_MODEL = 'gemini-3.1-pro-preview' 
TARGET_REGION = "美国市场"
SUPER_ADMIN = "907359319@qq.com"

print(f"🚀 启动：相对强度(Alpha)排位赛引擎 | 当前市场: {TARGET_REGION} | 引擎: {TARGET_MODEL}")

# ==========================================
# 🔑 FMP API 密钥双路轮询池 (负载均衡)
# ==========================================
FMP_KEYS = [
    "ANZlJ0O7UyJ9uzMGcSs39VPQ9U7GWfQI",
    "gbtmW6aLjjWENY9h99W0aDpy3Mrz3SAm"
]
_key_index = 0

def get_api_key():
    global _key_index
    key = FMP_KEYS[_key_index % len(FMP_KEYS)]
    _key_index += 1
    return key

# 保底资产池
US_STOCKS = {
    "NVDA":"英伟达", "AAPL":"苹果", "MSFT":"微软", "AMZN":"亚马逊", "GOOGL":"谷歌-A",
    "META":"Meta", "TSLA":"特斯拉", "AVGO":"博通", "TSM":"台积电", "LLY":"礼来",
    "AMD":"超威半导体", "QCOM":"高通", "NFLX":"奈飞", "INTC":"英特尔", "SMCI":"超微电脑"
}

# ==========================================
# 📊 1. 智能底层池：FMP 获取当日成交额 Top 100
# ==========================================
def get_scan_pool():
    tickers = {}
    print("📡 正在调用 FMP 接口抓取美股高成交额标的...")
    try:
        url = f"https://financialmodelingprep.com/api/v3/stock-screener?marketCapMoreThan=1000000000&volumeMoreThan=5000000&exchange=NYSE,NASDAQ&limit=200&apikey={get_api_key()}"
        res = requests.get(url, timeout=10).json()
        sorted_stocks = sorted(res, key=lambda x: x.get('price', 0) * x.get('volume', 0), reverse=True)[:100]
        
        for s in sorted_stocks:
            tickers[s['symbol']] = s['companyName']
            
        if len(tickers) == 0: raise ValueError("Empty response")
        print(f"✅ 成功锁定 {len(tickers)} 只流动性最强的美股标的。")
    except Exception as e:
        print(f"⚠️ FMP 筛选器超时: {e}，启用核心资产池保底！")
        tickers = US_STOCKS
    return tickers

ACTIVE_STOCKS = get_scan_pool()

def get_kline_data(ticker):
    time.sleep(0.1) # 避免并发超限
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?timeseries=100&apikey={get_api_key()}"
    try:
        res = requests.get(url, timeout=5).json()
        if 'historical' in res:
            df = pd.DataFrame(res['historical'])
            df = df.iloc[::-1].reset_index(drop=True)
            df.rename(columns={'date':'Date', 'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume'}, inplace=True)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            return df
    except Exception:
        pass
    return pd.DataFrame()

# ==========================================
# 🧠 2. 1-100分 日线级波段雷达评分 (纯基于 FMP 数据)
# ==========================================
def run_quant_filter(tickers):
    scored_stocks = []
    print(f"🌊 启动全局波段评分引擎 ({len(tickers)} 只)...")
    
    for i, (ticker, name) in enumerate(tickers.items()):
        try:
            df = get_kline_data(ticker)
            if df is None or df.empty or len(df) < 40: continue
            
            df['MACDh'] = ta.macd(df['Close']).iloc[:, 1]
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df = df.dropna()
            if len(df) < 6: continue
            
            latest, prev = df.iloc[-1], df.iloc[-2]
            avg_vol_5d = df['Volume'].tail(5).mean()
            base_vol_20d = df['Volume'].rolling(20).mean().iloc[-1]
            if pd.isna(base_vol_20d) or base_vol_20d == 0: continue
            sustained_vol_ratio = avg_vol_5d / base_vol_20d
            price_change_5d = (latest['Close'] / df['Close'].iloc[-5]) - 1
            macd_buy = (latest['MACDh'] > prev['MACDh']) or (latest['MACDh'] > 0 and prev['MACDh'] < 0)
            bias = abs((latest['Close'] - latest['MA20']) / latest['MA20'])
            
            score = 0
            score += min(sustained_vol_ratio * 10, 30)
            if 0.02 < price_change_5d <= 0.15: score += 20
            elif price_change_5d > 0.15: score += 10 
            if macd_buy: score += 30
            elif latest['MACDh'] > 0: score += 10
            if bias < 0.10: score += 20
            elif bias < 0.20: score += 10
            
            scored_stocks.append({
                "Ticker": ticker, "Name": name, "Price": round(latest['Close'], 2), 
                "Score": round(score, 1),
                "Vol5d_Ratio": round(sustained_vol_ratio, 2)
            })
        except Exception: 
            continue
        
    scored_stocks = sorted(scored_stocks, key=lambda x: x['Score'], reverse=True)
    return scored_stocks[:5], scored_stocks[5:10]

top_5, next_5 = run_quant_filter(ACTIVE_STOCKS)

# ==========================================
# 🤖 3. 3.1 Pro 深度推演 (引入期权模块)
# ==========================================
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

if not top_5:
    ai_generated_html = "<div class='top-card'>数据获取异常</div>"
else:
    print(f"🧠 触发 3.1 Pro 引擎：执行【美股满编投研 + 期权看板】...")
    prompt = f"""
    你是华尔街顶级量化游资操盘手及高级期权策略师。系统已通过波段雷达对美股标的进行了 1-100 分的综合评分。
    请基于评分最高的核心标的，结合你的知识库补充基本面和消息面，并输出深度投研及期权实战策略。

    【排版与字数指令】（直出 HTML 代码，禁止 markdown 外框）：

    <div class="top-card core-card">
        <div class="top-title">👑 核心双龙: [股票名称] ([代码]) | 波段评分: [填入Score]分</div>
        <p><span class='highlight-label'>🔥 起爆逻辑：</span>(基本面催化剂剖析)</p>
        <p><span class='highlight-label'>⚔️ 行业博弈：</span>(分析核心竞争对手的影响)</p>
        <p><span class='highlight-label'>🕰️ 周期共振：</span>(长短周期结合的技术位推演)</p>
        <p><span class='highlight-label'>⚠️ 持仓风控策略：</span>(明确正股持仓周期，如3-5天，及具体止损价位)</p>
    </div>

    <div class="options-board">
        <div class="options-header">🎲 美股专属期权看板 (Options Dashboard)</div>
        
        <div class="options-card">
            <h3 style="color: #6a1b9a; margin-top: 0;">⚡ 【短线期权策略】</h3>
            <p><b>🎯 推荐标的与行权：</b> (指定1只核心标的，给出建议的到期日和具体的 Strike Price)</p>
            <p><b>📈 波动率(IV)诊断：</b> (推演当前隐含波动率高低，有无财报IV Crush风险)</p>
            <p><b>🧩 组合构建方案：</b> (给出单腿或垂直价差建议，并说明盈亏比逻辑)</p>
        </div>

        <div class="options-card" style="border-left: 5px solid #d32f2f;">
            <h3 style="color: #d32f2f; margin-top: 0;">🛡️ 【AI自动期权实战核对单】</h3>
            <ul class="checklist">
                <li><b>☑️ Delta/Theta 敞口：</b> (说明建议买入的 Delta 值范围及防时间耗损策略)</li>
                <li><b>☑️ 财报/事件避险：</b> (近期有无重大宏观数据或财报发布)</li>
                <li><b>☑️ 止损/止盈纪律：</b> (明确权利金止损/止盈比例纪律)</li>
            </ul>
        </div>
    </div>

    <div class="compare-card">
        <div class="compare-title">🎖️ 满编观察池及避雷诊断 (Rank 2-5)</div>
        <ul>
            <li><b>[股票名] ([代码]) - 评分:[Score]分:</b> (指出其得分不高或存在的波段隐患风险)</li>
        </ul>
    </div>

    【波段雷达输入数据 (纯FMP提取)】：
    🏆 核心突击池(Top 1-5): {top_5}
    """
    
    try:
        res = client.models.generate_content(model=TARGET_MODEL, contents=prompt, config=types.GenerateContentConfig(temperature=0.3))
        ai_generated_html = res.text.replace("```html", "").replace("```", "").strip()
        print("✅ 3.1 Pro 美股期权波段审查完毕。")
    except Exception as e: 
        ai_generated_html = f"<div class='top-card'><div class='top-title'>❌ API 崩溃</div><p>日志：{str(e)}</p></div>"

# ==========================================
# 🎨 4. 极致美学 HTML 封装 (期权专属CSS)
# ==========================================
style = """
<style>
    body { font-family: 'Helvetica Neue', 'PingFang SC', sans-serif; background-color: #f0f2f5; padding: 20px; color: #2c3e50; line-height: 1.7;}
    .container { max-width: 900px; margin: 0 auto; background: #ffffff; padding: 35px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
    h1 { text-align: center; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 15px; margin-bottom: 35px; font-size: 28px; font-weight: 800; }
    .top-card { padding: 25px; margin-bottom: 30px; border-radius: 10px; background: #fafafa; border: 1px solid #e0e0e0; border-left: 6px solid #78909c; }
    .core-card { border-left: 6px solid #d32f2f; background: #fffcfc; box-shadow: 0 4px 15px rgba(211, 47, 47, 0.08); }
    .top-title { font-size: 22px; font-weight: 800; color: #37474f; border-bottom: 1px dashed #cfd8dc; padding-bottom: 10px; margin-bottom: 15px; }
    .core-card .top-title { color: #b71c1c; border-bottom: 1px dashed #d32f2f; }
    .highlight-label { display: inline-block; font-weight: bold; color: #fff; background: #455a64; padding: 3px 8px; border-radius: 4px; margin-right: 6px; font-size: 14px;}
    .core-card .highlight-label { background: #c62828; }
    
    /* 期权看板 UI */
    .options-board { background: #f3e5f5; border-radius: 12px; padding: 25px; margin-bottom: 30px; border: 1px solid #ce93d8; box-shadow: 0 5px 15px rgba(106, 27, 154, 0.1);}
    .options-header { font-size: 24px; font-weight: 900; color: #4a148c; border-bottom: 2px solid #ab47bc; padding-bottom: 10px; margin-bottom: 20px; text-align: center; letter-spacing: 1px;}
    .options-card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 15px; border-left: 5px solid #8e24aa; }
    .checklist { list-style: none; padding-left: 0; }
    .checklist li { background: #fafafa; margin-bottom: 8px; padding: 10px 15px; border-radius: 6px; border: 1px solid #eeeeee; color: #424242;}
    
    .compare-card { border-left: 5px solid #ff9800; background: #fffdf7; padding: 25px; margin-bottom: 25px; border-radius: 10px; border: 1px solid #ffe0b2;}
    .compare-title { font-size: 19px; color: #e65100; font-weight: bold; margin-bottom: 15px; border-bottom: 1px solid #ffe0b2; padding-bottom: 10px;}
</style>
"""

full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>🎯 Alpha 雷达波段内参：{TARGET_REGION}</h1>\n{ai_generated_html}\n<p style='text-align:center; color:#999; font-size:12px; margin-top:40px;'>[END_OF_QUANT_REPORT - STRATEGIC COMMAND AI]</p></div></body></html>"

# ==========================================
# 📧 5. 邮件分发与账本持久化
# ==========================================
def send_mail(to, subject, content):
    user, pwd = os.environ.get("EMAIL_ACCOUNT"), os.environ.get("EMAIL_PASSWORD")
    if not user: return
    msg = MIMEMultipart(); msg['From'] = user; msg['To'] = to; msg['Subject'] = subject
    msg.attach(MIMEText(content, 'html'))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd); s.send_message(msg)
            print(f"✅ 内参已精准发送至: {to}")
    except Exception as e: print(f"❌ 发送失败 ({to}): {e}")

if __name__ == "__main__":
    mail_subject = f"🔥【期权满编版】{TARGET_REGION} 核心打分与策略 ({datetime.date.today()})"
    send_mail(SUPER_ADMIN, mail_subject, full_html)
    
    # 🗂️ 核心修正：写入历史账本 CSV (Trade History)
    chosen = []
    # 通过匹配 AI 的输出，判断哪些股票最终被选为了核心/观察标的
    for item in top_5 + next_5:
        if item['Ticker'] in ai_generated_html:
            tag = "Watchlist"
            if re.search(r'\[核心双龙\][^<]*?' + re.escape(item['Ticker']), ai_generated_html): tag = "Core_Dragon"
            elif re.search(r'\[梯队先锋\][^<]*?' + re.escape(item['Ticker']), ai_generated_html): tag = "Pioneer"
            item['Tag'] = tag
            chosen.append(item)
    
    log_file = "trade_history.csv"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
                f.write("Date,Ticker,Name,Tag,Score,Price,Vol_Ratio\n")
            ts = datetime.datetime.now().strftime('%Y-%m-%d')
            for i in chosen: 
                f.write(f"{ts},{i['Ticker']},{i['Name']},{i['Tag']},{i['Score']},{i['Price']},{i.get('Vol5d_Ratio', 0)}\n")
        print("✅ trade_history.csv 账本已更新！")
    except Exception as e:
        print(f"⚠️ 账本写入失败: {e}")

    # 🗂️ 核心修正：保存 HTML 到本地用于 GitHub 归档
    try:
        with open("report.html", "w", encoding="utf-8") as f:
            f.write(full_html)
        print("✅ report.html 本地存档已生成！")
    except Exception as e:
        print(f"⚠️ 网页存档备份失败: {e}")
