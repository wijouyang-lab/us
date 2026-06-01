# -*- coding: utf-8 -*-
import pandas as pd
import datetime
import os
import smtplib
import time
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

# 周末不执行
if datetime.datetime.now().weekday() >= 5:
    exit()

TARGET_MODEL = 'claude-opus-4-7'
SUPER_ADMIN = os.environ.get("TARGET_EMAILS")

# ==========================================
# 🔑 密钥读取
# ==========================================
FMP_KEYS = [os.environ.get("FMP_KEY_1"), os.environ.get("FMP_KEY_2")]
FMP_KEYS = [k for k in FMP_KEYS if k]
if not FMP_KEYS: exit(1)

_key_index = 0
def get_api_key():
    global _key_index
    key = FMP_KEYS[_key_index % len(FMP_KEYS)]
    _key_index += 1
    return key

print("🔍 启动美股盘后复盘引擎 (Review Engine)...")

# ==========================================
# 📂 1. 读取历史账本 (只看最近 3 个交易日的推荐)
# ==========================================
log_file = "trade_history.csv"
if not os.path.exists(log_file):
    print("⚠️ 尚未生成交易账本，跳过复盘。")
    exit(0)

try:
    df = pd.read_csv(log_file, names=["Date", "Ticker", "Name", "Tag", "Score", "Price", "RSI", "Bias", "Hold_Period", "Stop_Loss"], header=0)
    df['Date'] = pd.to_datetime(df['Date'])
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=5)
    recent_picks = df[df['Date'] >= cutoff_date].copy()
    if recent_picks.empty:
        print("⚠️ 近期无操作记录，跳过。")
        exit(0)
except Exception as e:
    print(f"⚠️ 账本读取失败: {e}")
    exit(1)

# ==========================================
# 📈 2. 调取 FMP 现价，计算盈亏 (PnL)
# ==========================================
review_data = []
print("📡 正在核对近期推荐标的当前表现...")
for index, row in recent_picks.iterrows():
    ticker = row['Ticker']
    recommend_price = float(row['Price'])
    url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={get_api_key()}"
    try:
        time.sleep(0.1)
        res = requests.get(url, timeout=5).json()
        if res and len(res) > 0:
            current_price = res[0]['price']
            pnl_pct = ((current_price - recommend_price) / recommend_price) * 100
            review_data.append({
                "Date": row['Date'].strftime('%Y-%m-%d'),
                "Ticker": ticker,
                "Name": row['Name'],
                "Tag": row['Tag'],
                "Hold_Period": row.get('Hold_Period', 'N/A'),
                "Stop_Loss": row.get('Stop_Loss', 'N/A'),
                "Rec_Price": recommend_price,
                "Cur_Price": current_price,
                "PnL": round(pnl_pct, 2)
            })
    except Exception as e:
        print(f"⚠️ {ticker} 现价拉取失败: {e}")

if not review_data: exit(0)

# ==========================================
# 🧠 3. Claude 归因分析与纪律拷问
# ==========================================
client = anthropic.Anthropic(
    api_key=os.environ.get("CLAWSOCKET_API_KEY"),
    base_url=os.environ.get("CLAWSOCKET_BASE_URL")
)
print("🧠 触发 Claude 执行盘后归因...")

prompt = f"""
你是量化风控总监。以下是系统近几日推荐的美股标的及截止目前的真实盈亏表现（含持股周期和止损价）：
{review_data}

请严格按以下 HTML 骨架输出复盘报告（直出HTML，禁加markdown框，看涨/盈利标红，看跌/亏损标绿）：

<div style="background: #eceff1; border-left: 6px solid #455a64; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #263238;">⚖️ 盘后总体风控审查</h3>
    <p>(根据盈亏数据，总结近期策略的胜率，指出是否受到大盘Beta拖累或Alpha因子失效)</p>
</div>

<h2 style="color: #37474f; border-bottom: 2px solid #cfd8dc; padding-bottom: 5px;">📊 核心标的独立归因</h2>
<div style="background: #fff; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
    <h3 style="margin: 0 0 10px 0;">[推演日期] | [股票名称] ([代码])</h3>
    <p><b>预计周期:</b> [Hold_Period] | <b>止损位:</b> [Stop_Loss]</p>
    <p><b>推荐价:</b> $[价格] ➔ <b>现价:</b> $[价格] | <b>实际盈亏:</b> <span style="font-weight: bold; color: [盈利填#d32f2f, 亏损填#388e3c];">[PnL]%</span></p>
    <p><span style="background: #607d8b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">风控动作指令</span> (基于现价是否跌破止损位，给出最冷血的纪律应对：如"触发止损无条件出局"、"持股周期内正常洗盘"、"达到预期建议止盈")</p>
</div>
"""

try:
    message = client.messages.create(
        model=TARGET_MODEL,
        max_tokens=4096,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )
    ai_html = message.content[0].text.replace("```html", "").replace("```", "").strip()
except Exception as e:
    ai_html = f"<p>复盘生成失败: {e}</p>"

# ==========================================
# 📧 4. 封装发送
# ==========================================
style = "body{font-family:sans-serif; background:#f4f6f9; padding:20px; color:#333; line-height:1.6} .container{max-width:900px; margin:0 auto; background:#fff; padding:30px; border-radius:10px; box-shadow:0 4px 15px rgba(0,0,0,0.05)}"
full_html = f"<!DOCTYPE html><html><head><style>{style}</style></head><body><div class='container'><h1 style='color:#37474f; text-align:center;'>🛡️ Alpha 雷达美股盘后复盘</h1>{ai_html}</div></body></html>"

# 把复盘盈亏结果写回账本
review_log = "review_history.csv"
need_header = not os.path.exists(review_log) or os.path.getsize(review_log) == 0
try:
    with open(review_log, "a", encoding="utf-8") as f:
        if need_header:
            f.write("Review_Date,Ticker,Name,Tag,Rec_Date,Rec_Price,Cur_Price,Days_Held,PnL_Pct,Hold_Period,Stop_Loss\n")
        review_date = get_bj_time().strftime('%Y-%m-%d')
        for item in review_data:
            f.write(f"{review_date},{item['代码']},{item['名称']},{item['标签']},{item['推荐日期']},{item['推荐价']},{item['现价']},{item['已持仓天数']},{item['盈亏']},{item['持股周期']},{item['止损价']}\n")
    print("✅ 复盘结果已写入 review_history.csv")
except Exception as e:
    print(f"⚠️ 复盘写入失败: {e}")

def send_mail():
    user, pwd = os.environ.get("EMAIL_ACCOUNT"), os.environ.get("EMAIL_PASSWORD")
    if not user or not SUPER_ADMIN: return
    msg = MIMEMultipart(); msg['From'] = user; msg['Subject'] = f"🛡️【盘后清算】美股策略复盘与风控纪律 ({datetime.date.today()})"
    msg.attach(MIMEText(full_html, 'html'))
    targets = [e.strip() for e in SUPER_ADMIN.split(',')]
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.sendmail(user, targets, msg.as_string())
            print("✅ 复盘报告发送成功！")
    except Exception as e: print(f"❌ 发送失败: {e}")

send_mail()
