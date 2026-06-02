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

TARGET_MODEL = 'claude-sonnet-4-6'
SUPER_ADMIN = os.environ.get("TARGET_EMAILS")

def get_now():
    return datetime.datetime.now().strftime('%Y-%m-%d')

FMP_KEYS = [os.environ.get("FMP_KEY_1"), os.environ.get("FMP_KEY_2")]
FMP_KEYS = [k for k in FMP_KEYS if k]
if not FMP_KEYS: exit(1)

_key_index = 0
def get_api_key():
    global _key_index
    key = FMP_KEYS[_key_index % len(FMP_KEYS)]
    _key_index += 1
    return key

print("启动美股盘后复盘引擎...")

# ==========================================
# 1. 读取账本
# ==========================================
log_file = "trade_history.csv"
if not os.path.exists(log_file):
    print("⚠️ 尚未生成交易账本，跳过复盘。")
    exit(0)

try:
    df = pd.read_csv(log_file, names=["Date", "Ticker", "Name", "Tag", "Score", "Price", "RSI", "Bias", "Hold_Period", "Stop_Loss"], header=0)
    df['Date'] = pd.to_datetime(df['Date'])
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=14)
    recent_picks = df[df['Date'] >= cutoff_date].copy()
    if recent_picks.empty:
        print("⚠️ 近期无操作记录，跳过。")
        exit(0)
except Exception as e:
    print(f"⚠️ 账本读取失败: {e}")
    exit(1)

# ==========================================
# 2. 按票聚合，保留完整持仓轨迹摘要
# ==========================================
summary_list = []
for ticker, group in recent_picks.groupby('Ticker'):
    group = group.sort_values('Date')
    first_row = group.iloc[0]
    latest_row = group.iloc[-1]
    days_held = (datetime.datetime.now() - first_row['Date']).days

    # 优先取非 N/A 的周期和止损
    hold_period = 'N/A'
    stop_loss = 'N/A'
    for _, r in group.iterrows():
        if str(r.get('Hold_Period', 'N/A')).strip() not in ['N/A', 'nan', '']:
            hold_period = r['Hold_Period']
        if str(r.get('Stop_Loss', 'N/A')).strip() not in ['N/A', 'nan', '', '坚决空仓', '绝对规避']:
            stop_loss = r['Stop_Loss']

    summary_list.append({
        "Ticker": ticker,
        "Name": first_row['Name'],
        "Tag": latest_row['Tag'],
        "Hold_Period": hold_period,
        "Stop_Loss": stop_loss,
        "First_Rec_Date": first_row['Date'].strftime('%Y-%m-%d'),
        "First_Rec_Price": float(first_row['Price']),
        "Days_Held": days_held,
        "Rec_Count": len(group),
    })

if not summary_list:
    print("⚠️ 聚合后无数据，退出。")
    exit(0)

# ==========================================
# 3. 调取 FMP 现价，计算盈亏
# ==========================================
review_data = []
print("正在核对近期推荐标的当前表现...")
for item in summary_list:
    ticker = item['Ticker']
    rec_price = item['First_Rec_Price']
    url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={get_api_key()}"
    try:
        time.sleep(0.1)
        res = requests.get(url, timeout=5).json()
        if res and len(res) > 0:
            current_price = res[0]['price']
            pnl_pct = ((current_price - rec_price) / rec_price) * 100
            review_data.append({
                "Ticker": ticker,
                "Name": item['Name'],
                "Tag": item['Tag'],
                "Hold_Period": item['Hold_Period'],
                "Stop_Loss": item['Stop_Loss'],
                "First_Rec_Date": item['First_Rec_Date'],
                "Rec_Price": rec_price,
                "Cur_Price": current_price,
                "Days_Held": item['Days_Held'],
                "Rec_Count": item['Rec_Count'],
                "PnL": round(pnl_pct, 2)
            })
    except Exception as e:
        print(f"⚠️ {ticker} 现价拉取失败: {e}")

if not review_data:
    exit(0)

print(f"✅ 共复盘 {len(review_data)} 只标的")

# ==========================================
# 4. Claude 归因分析
# ==========================================
client = anthropic.Anthropic(
    api_key=os.environ.get("CLAWSOCKET_API_KEY"),
    base_url=os.environ.get("CLAWSOCKET_BASE_URL")
)
print("触发 Claude 执行盘后归因...")

prompt = f"""
你是量化风控总监。以下是系统近14天推荐的美股标的持仓摘要及当前真实盈亏数据：
{review_data}

字段说明：
- First_Rec_Date：首次推荐日期，即买入成本基准日
- Rec_Price：首次推荐价，即买入成本
- Days_Held：从首次推荐到今天的实际持仓天数
- Rec_Count：系统连续推荐次数，次数越多说明系统持续看好
- Hold_Period：建议持仓周期，N/A表示该票为Trap_Warning无需持仓
- Stop_Loss：止损位，N/A表示该票为Trap_Warning无需止损

请严格按以下 HTML 骨架输出复盘报告（直出HTML，禁加markdown框，看涨/盈利标红，看跌/亏损标绿）：

<div style="background: #eceff1; border-left: 6px solid #455a64; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #263238;">⚖️ 盘后总体风控审查</h3>
    <p>(总结整体胜率和盈亏，指出是否受大盘Beta拖累，哪些票出现洗盘特征)</p>
</div>

<h2 style="color: #37474f; border-bottom: 2px solid #cfd8dc; padding-bottom: 5px;">📊 核心标的独立归因</h2>
<div style="background: #fff; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
    <h3 style="margin: 0 0 10px 0;">[First_Rec_Date] | [Name] ([Ticker]) | 系统连续推荐[Rec_Count]次</h3>
    <p><b>持股周期:</b> [Hold_Period] (已持仓 [Days_Held] 天) | <b>止损位:</b> [Stop_Loss]</p>
    <p><b>买入成本:</b> $[Rec_Price] ➔ <b>现价:</b> $[Cur_Price] | <b>实际盈亏:</b> <span style="font-weight: bold; color: [盈利填#d32f2f, 亏损填#388e3c];">[PnL]%</span></p>
    <p><span style="background: #607d8b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">风控动作指令</span>
    (综合判断：1.现价是否跌破止损位 2.持仓天数是否超出周期 3.系统连续推荐次数是否说明仍有强度
    给出明确指令：如"触发止损无条件出局"、"持股周期内疑似洗盘可继续持有"、"超出持股周期建议止盈离场")</p>
</div>
"""

try:
    message = client.messages.create(
        model=TARGET_MODEL,
        max_tokens=3000,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )
    ai_html = message.content[0].text.replace("```html", "").replace("```", "").strip()
except Exception as e:
    ai_html = f"<p>复盘生成失败: {e}</p>"

# ==========================================
# 5. 复盘结果写入 review_history.csv
# ==========================================
review_log = "review_history.csv"
need_header = not os.path.exists(review_log) or os.path.getsize(review_log) == 0
try:
    with open(review_log, "a", encoding="utf-8") as f:
        if need_header:
            f.write("Review_Date,Ticker,Name,Tag,Rec_Date,Rec_Price,Cur_Price,Days_Held,PnL_Pct,Hold_Period,Stop_Loss,Rec_Count\n")
        review_date = get_now()
        for item in review_data:
            f.write(f"{review_date},{item['Ticker']},{item['Name']},{item['Tag']},{item['First_Rec_Date']},{item['Rec_Price']},{item['Cur_Price']},{item['Days_Held']},{item['PnL']},{item['Hold_Period']},{item['Stop_Loss']},{item['Rec_Count']}\n")
    print("✅ 复盘结果已写入 review_history.csv")
except Exception as e:
    print(f"⚠️ 复盘写入失败: {e}")

# ==========================================
# 6. 封装发送
# ==========================================
style = "body{font-family:sans-serif; background:#f4f6f9; padding:20px; color:#333; line-height:1.6} .container{max-width:900px; margin:0 auto; background:#fff; padding:30px; border-radius:10px; box-shadow:0 4px 15px rgba(0,0,0,0.05)}"
full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{style}</style></head><body><div class='container'><h1 style='color:#37474f; text-align:center;'>Alpha 雷达美股盘后复盘</h1>{ai_html}</div></body></html>"

def send_mail():
    user, pwd = os.environ.get("EMAIL_ACCOUNT"), os.environ.get("EMAIL_PASSWORD")
    if not user or not SUPER_ADMIN: return
    msg = MIMEMultipart()
    msg['From'] = user
    msg['Subject'] = f"【盘后清算】美股策略复盘与风控纪律 ({datetime.date.today()})"
    msg.attach(MIMEText(full_html, 'html'))
    targets = [e.strip() for e in SUPER_ADMIN.split(',')]
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.sendmail(user, targets, msg.as_string())
            print("✅ 复盘报告发送成功！")
    except Exception as e:
        print(f"❌ 发送失败: {e}")

send_mail()
