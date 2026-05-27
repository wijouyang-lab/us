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

TARGET_MODEL = 'gemini-3.1-pro-preview' 
TARGET_REGION = "美国市场"

# 🔑 从 GitHub Secrets 读取收件人邮箱
SUPER_ADMIN = os.environ.get("TARGET_EMAILS")
if not SUPER_ADMIN:
    print("🚨 致命错误：未检测到目标收件邮箱！请检查 GitHub Secrets 中的 TARGET_EMAILS！")
    exit(1)

print(f"🚀 启动：相对强度(Alpha)强制排序引擎 | 当前市场: {TARGET_REGION} | 引擎: {TARGET_MODEL}")

# ==========================================
# 🔑 绝密：从环境变量读取 FMP 密钥
# ==========================================
FMP_KEYS = [
    os.environ.get("FMP_KEY_1"),
    os.environ.get("FMP_KEY_2")
]
FMP_KEYS = [k for k in FMP_KEYS if k]

if not FMP_KEYS:
    print("🚨 致命错误：未检测到 FMP API 密钥！请检查 GitHub Secrets！")
    exit(1)

_key_index = 0
def get_api_key():
    global _key_index
    key = FMP_KEYS[_key_index % len(FMP_KEYS)]
    _key_index += 1
    return key

# ==========================================
# 📊 1. 获取当日成交额 Top 100
# ==========================================
def get_scan_pool():
    tickers = {}
    print("📡 正在调用 FMP 双引擎抓取美股高成交额标的...")
    try:
        url = f"https://financialmodelingprep.com/api/v3/stock-screener?marketCapMoreThan=1000000000&volumeMoreThan=5000000&exchange=NYSE,NASDAQ&limit=200&apikey={get_api_key()}"
        res = requests.get(url, timeout=10).json()
        sorted_stocks = sorted(res, key=lambda x: x.get('price', 0) * x.get('volume', 0), reverse=True)[:100]
        for s in sorted_stocks:
            tickers[s['symbol']] = s['companyName']
        if not tickers: raise ValueError("Empty response")
        print(f"✅ 成功锁定 {len(tickers)} 只流动性最强标的。")
    except Exception as e:
        print(f"⚠️ 筛选器异常，启用核心备用池: {e}")
        tickers = {"NVDA":"英伟达", "AAPL":"苹果", "MSFT":"微软", "AMZN":"亚马逊", "TSLA":"特斯拉", "META":"Meta", "AVGO":"博通"}
    return tickers

ACTIVE_STOCKS = get_scan_pool()

# 🛡️ 核心升级：增加重试机制和安全的休眠时间，防止 API 瘫痪
def get_kline_data(ticker):
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?timeseries=100&apikey={get_api_key()}"
    for attempt in range(3): # 最多尝试 3 次
        try:
            time.sleep(0.5) # 延长休眠时间，降低触发 FMP 频率限制的风险
            res = requests.get(url, timeout=5).json()
            if 'historical' in res:
                df = pd.DataFrame(res['historical'])
                df = df.iloc[::-1].reset_index(drop=True)
                df.rename(columns={'date':'Date', 'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume'}, inplace=True)
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
                return df
        except Exception:
            time.sleep(2) # 如果报错，停顿 2 秒后再重试
    return pd.DataFrame()

# ==========================================
# 🧠 2. 全量相对打分引擎 (绝不空仓)
# ==========================================
def run_quant_filter(tickers):
    scored_stocks = []
    print(f"🌊 启动波段评分引擎，采用【全市场强制排序】，扫描 {len(tickers)} 只标的...")
    for ticker, name in tickers.items():
        try:
            df = get_kline_data(ticker)
            if df is None or df.empty or len(df) < 40: continue
            
            df['MACDh'] = ta.macd(df['Close']).iloc[:, 1] 
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df = df.dropna()
            if len(df) < 6: continue
            
            latest, prev = df.iloc[-1], df.iloc[-2]
            bias = (latest['Close'] - latest['MA20']) / latest['MA20']
            abs_bias = abs(bias)
            
            score = 0
            # 🚫 彻底取消一票否决，全部改为加减分机制
            # 1. MACD 动能判定
            if latest['MACDh'] > prev['MACDh']: score += 40
            elif latest['MACDh'] > 0: score += 15
            else: score -= 20 # 绿柱放大扣分
            
            # 2. RSI 状态判定
            if 40 <= latest['RSI'] <= 70: score += 30  
            elif latest['RSI'] > 70: score -= 20 # 超买区风险扣分
            elif latest['RSI'] < 40: score -= 20 # 弱势区风险扣分
            
            # 3. 乖离率判定 (偏离 20日线越远，扣分越狠)
            score += (0.15 - abs_bias) * 100 
            
            scored_stocks.append({
                "Ticker": ticker, "Name": name, "Price": round(latest['Close'], 2), 
                "Score": round(score, 1), "RSI": round(latest['RSI'], 1), "Bias": round(bias * 100, 2)
            })
        except Exception: 
            continue
        
    # 按照分数从高到低强制排序
    scored_stocks = sorted(scored_stocks, key=lambda x: x['Score'], reverse=True)
    
    # 无论多烂，强制返回相对最好的前3、前10，和倒数的坑货
    top = scored_stocks[:3]
    mid = scored_stocks[3:10]
    bottom = scored_stocks[-2:] if len(scored_stocks) >= 12 else []
    
    return top, mid, bottom

top_3, next_7, traps = run_quant_filter(ACTIVE_STOCKS)

# ==========================================
# 🤖 3. 3.1 Pro 深度推演 (美股定制排版)
# ==========================================
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

ai_generated_html = ""
if not top_3:
    ai_generated_html = "<div class='top-card'>API数据源完全瘫痪，且重试均失败，无法获取任何K线数据。</div>"
else:
    print(f"🧠 触发 3.1 Pro 引擎：执行【相对强度分析 + 持股周期 + 期权看板】...")
    prompt = f"""
    你是华尔街顶级量化游资操盘手及高级期权策略师。
    今日系统采用了【相对强度全市场横向对比】，即使在极端行情下，也为你“矮子里拔高个”筛选出了目前资金最活跃、相对形态最优的标的。
    请结合你的宏观和消息面数据库，对这批标的进行深度排版输出。看涨需标红(#d32f2f)，看跌需标绿(#388e3c)。
    注意：如果标的的波段评分较低或为负数，请在点评中明确指出当前是弱势行情，并在风控底线中给出极度保守的防守建议。

    【排版与字数指令】（必须严格直出以下 HTML 代码骨架，不得加 markdown 外框）：

    <div style="background: #e3f2fd; border-left: 6px solid #1565c0; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
        <h3 style="margin-top: 0; color: #0d47a1;">🌍 宏观资金定调与 Alpha 相对评级</h3>
        <p>(结合美股当前流动性、大盘走势，点评今日选股名单的整体强度)</p>
    </div>

    <h2 style="color: #1a237e; border-bottom: 2px solid #1a237e; padding-bottom: 5px;">👑 相对强度优选 (Top 1-3)</h2>
    <div class="top-card core-card">
        <div class="top-title" style="color: #d32f2f;">1. [中文股票名] ([代码]) | 波段评分: [Score]分</div>
        <p><span class='highlight-label bg-red'>🔥 基本面与消息面:</span> (剖析催化剂与基本面逻辑)</p>
        <p><span class='highlight-label bg-blue'>📈 技术面与量价:</span> (结合乖离率与MACD说明技术形态)</p>
        <p><span class='highlight-label bg-orange'>⚠️ 潜伏与风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
        
        <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
            <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
            <ul style="margin: 0; padding-left: 20px; font-size: 14px;">
                <li><b>建议行权价与到期日：</b>(明确建议)</li>
                <li><b>期权组合构建：</b>(单腿买入还是价差防守策略？)</li>
                <li><b>风控核对单：</b>(止损纪律与财报避险)</li>
            </ul>
        </div>
    </div>
    
    <div class="top-card core-card">
        <div class="top-title" style="color: #d32f2f;">2. [中文股票名] ([代码]) | 波段评分: [Score]分</div>
        <p><span class='highlight-label bg-red'>🔥 基本面与消息面:</span> (...)</p>
        <p><span class='highlight-label bg-blue'>📈 技术面与量价:</span> (...)</p>
        <p><span class='highlight-label bg-orange'>⚠️ 潜伏与风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
        <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
            <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
            <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li><li><b>风控核对单：</b>(...)</li></ul>
        </div>
    </div>
    
    <div class="top-card core-card">
        <div class="top-title" style="color: #d32f2f;">3. [中文股票名] ([代码]) | 波段评分: [Score]分</div>
        <p><span class='highlight-label bg-red'>🔥 基本面与消息面:</span> (...)</p>
        <p><span class='highlight-label bg-blue'>📈 技术面与量价:</span> (...)</p>
        <p><span class='highlight-label bg-orange'>⚠️ 潜伏与风控底线:</span> 周期:[X-Y天] | 止损:[具体价格或百分比]</p>
        <div style="background: #f3e5f5; padding: 15px; margin-top: 15px; border-radius: 6px; border-left: 4px solid #8e24aa;">
            <h4 style="margin: 0 0 10px 0; color: #6a1b9a;">🎲 美股专属期权实战策略</h4>
            <ul style="margin: 0; padding-left: 20px; font-size: 14px;"><li><b>建议行权价与到期日：</b>(...)</li><li><b>期权组合构建：</b>(...)</li><li><b>风控核对单：</b>(...)</li></ul>
        </div>
    </div>

    <div class="compare-card">
        <div class="compare-title">🎖️ 满编观察池及硬伤诊断 (Rank 4-10)</div>
        <ul>
            <li><b>4. [中文股票名] ([代码]) - 评分:[Score]分:</b> <span style="color: #388e3c;">硬伤：</span>(...)</li>
            <li><b>5. [中文股票名] ([代码]) - 评分:[Score]分:</b> <span style="color: #388e3c;">硬伤：</span>(...)</li>
            <li><b>6. [中文股票名] ([代码]) - 评分:[Score]分:</b> <span style="color: #388e3c;">硬伤：</span>(...)</li>
        </ul>
    </div>

    <div style="background: #fbfcfe; border-left: 5px solid #388e3c; padding: 25px; margin-bottom: 25px; border-radius: 10px;">
        <h3 style="color: #388e3c; margin-top: 0;">🚨 诱多对照组（严禁接盘）</h3>
        <ul>
            <li><b>倒数1. [中文股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">诱多陷阱：</span> (...)</li>
            <li><b>倒数2. [中文股票名] ([代码]):</b> ❌ <span style="color: #388e3c;">诱多陷阱：</span> (...)</li>
        </ul>
    </div>

    【注入的数据源】：
    🥇 相对最强前三名 (Top 1-3): {top_3}
    🎖️ 观察池 (Rank 4-10): {next_7}
    🚨 全市场最弱垫底 (Traps): {traps}
    """
    try:
        res = client.models.generate_content(model=TARGET_MODEL, contents=prompt, config=types.GenerateContentConfig(temperature=0.25))
        ai_generated_html = res.text.replace("```html", "").replace("```", "").strip()
        print("✅ 3.1 Pro 美股期权波段审查完毕。")
    except Exception as e: 
        ai_generated_html = f"<div class='top-card'><div class='top-title'>❌ API 崩溃</div><p>日志：{str(e)}</p></div>"

# ==========================================
# 🎨 4. HTML 封装
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
    .compare-card { border-left: 5px solid #ff9800; background: #fffdf7; padding: 25px; margin-bottom: 25px; border-radius: 10px; border: 1px solid #ffe0b2;}
    .compare-title { font-size: 19px; color: #e65100; font-weight: bold; margin-bottom: 15px; border-bottom: 1px solid #ffe0b2; padding-bottom: 10px;}
    ul { padding-left: 22px; margin-top: 0;}
    li { margin-bottom: 10px; font-size: 15px; }
</style>
"""

full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head><body><div class='container'><h1>🎯 Alpha 雷达波段内参：{TARGET_REGION}</h1>\n{ai_generated_html}\n<p style='text-align:center; color:#999; font-size:12px; margin-top:40px;'>[END_OF_QUANT_REPORT - STRATEGIC COMMAND AI]</p></div></body></html>"

# ==========================================
# 📧 5. 邮件分发与强制保存
# ==========================================
def send_mail(to_emails, subject, content):
    user, pwd = os.environ.get("EMAIL_ACCOUNT"), os.environ.get("EMAIL_PASSWORD")
    if not user: return
    
    to_list = [email.strip() for email in to_emails.split(',')]
    msg = MIMEMultipart(); msg['From'] = user; msg['Subject'] = subject
    msg.attach(MIMEText(content, 'html'))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd); 
            s.sendmail(user, to_list, msg.as_string())
            print(f"✅ 内参已精准密送至: {to_emails}")
    except Exception as e: print(f"❌ 发送失败 ({to_emails}): {e}")

if __name__ == "__main__":
    # 🌟 强制先存 HTML 到本地，确保绝对生成 report.html
    try:
        with open("report.html", "w", encoding="utf-8") as f:
            f.write(full_html)
        print("✅ report.html 已成功强制存入本地！")
    except Exception as e:
        print(f"🚨 report.html 写入失败: {e}")

    mail_subject = f"🔥【纯美股期权版】{TARGET_REGION} 核心打分与实战 ({datetime.date.today()})"
    send_mail(SUPER_ADMIN, mail_subject, full_html)
    
    # 🎯 核心升级：利用严谨正则抓取美股的周期和止损
    chosen = []
    blocks = re.split(r'<div class="top-card', ai_generated_html)
    all_scanned = top_3 + next_7 + traps
    
    for item in all_scanned:
        if item['Ticker'] in ai_generated_html:
            tag = "Trap_Warning" 
            if any(x['Ticker'] == item['Ticker'] for x in top_3): tag = "Core_Dragon"
            elif any(x['Ticker'] == item['Ticker'] for x in next_7): tag = "Observation"
            
            item['Tag'] = tag
            item['Hold_Period'] = "N/A"
            item['Stop_Loss'] = "N/A"
            
            if tag == "Core_Dragon":
                for block in blocks:
                    if item['Ticker'] in block or item['Name'] in block:
                        period_match = re.search(r'风控底线:</span>\s*周期:\[?([^\s|<,\]]+)', block)
                        sl_match = re.search(r'止损:\[?([^<\]]+)', block)
                        if not sl_match:
                            sl_match = re.search(r'风控底线:</span>\s*周期:[^|,<]+[|,<]\s*([^<]+)', block)
                        
                        if period_match: item['Hold_Period'] = period_match.group(1).strip()
                        if sl_match: 
                            raw_sl = sl_match.group(1).strip()
                            item['Stop_Loss'] = re.sub(r'</?p>', '', raw_sl).strip()
                        break
            
            chosen.append(item)
    
    # 🗂️ 写入带风控参数的历史账本
    log_file = "trade_history.csv"
    need_header = not os.path.exists(log_file) or os.path.getsize(log_file) == 0
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            if need_header:
                f.write("Date,Ticker,Name,Tag,Score,Price,RSI,Bias,Hold_Period,Stop_Loss\n")
            ts = datetime.datetime.now().strftime('%Y-%m-%d')
            for i in chosen: 
                f.write(f"{ts},{i['Ticker']},{i['Name']},{i['Tag']},{i['Score']},{i['Price']},{i.get('RSI',0)},{i.get('Bias',0)},{i.get('Hold_Period','N/A')},{i.get('Stop_Loss','N/A')}\n")
    except Exception as e:
        print(f"⚠️ 账本写入失败: {e}")
