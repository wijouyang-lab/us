# -*- coding: utf-8 -*-
import pandas as pd
import datetime
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
import tushare as ts

if datetime.datetime.now().weekday() >= 5:
    exit()

TARGET_MODEL = 'claude-opus-4-8'
SUPER_ADMIN = os.environ.get("TARGET_EMAILS")

def get_now():
    return datetime.datetime.now().strftime('%Y-%m-%d')

print("启动美股盘后复盘引擎...")

log_file = "trade_history.csv"
if not os.path.exists(log_file):
    print("⚠️ 尚未生成交易账本，跳过复盘。")
    exit(0)

try:
    df = pd.read_csv(log_file, names=["Date", "Ticker", "Name", "Tag", "Score", "Price", "RSI", "Bias", "Hold_Period", "Stop_Loss"], header=0)
    df['Date'] = pd.to_datetime(df['Date'])
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=30)
    recent_picks = df[df['Date'] >= cutoff_date].copy()
    if recent_picks.empty:
        print("⚠️ 近期无操作记录，跳过。")
        exit(0)
except Exception as e:
    print(f"⚠️ 账本读取失败: {e}")
    exit(1)

ts.set_token(os.environ.get("TUSHARE_TOKEN"))
pro = ts.pro_api()

start_hist = (datetime.datetime.now() - datetime.timedelta(days=35)).strftime('%Y%m%d')
end_hist = datetime.datetime.now().strftime('%Y%m%d')

df_hist_all = pd.DataFrame()
try:
    df_hist_all = pro.us_daily(start_date=start_hist, end_date=end_hist)
    if df_hist_all is not None and not df_hist_all.empty:
        df_hist_all['clean_ticker'] = df_hist_all['ts_code'].apply(
            lambda x: x.split('.')[0] if '.' in x else x
        )
        df_hist_all = df_hist_all.sort_values(['clean_ticker', 'trade_date'])
except Exception as e:
    print(f"⚠️ 历史价格拉取失败: {e}")

price_map = {}
for i in range(1, 5):
    trade_date = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%Y%m%d')
    try:
        df_daily = pro.us_daily(trade_date=trade_date)
        if df_daily is not None and not df_daily.empty:
            print(f"✅ 获取到 {trade_date} 美股收盘价")
            for _, row in df_daily.iterrows():
                clean_ticker = row['ts_code'].split('.')[0] if '.' in row['ts_code'] else row['ts_code']
                price_map[clean_ticker] = row['close']
            break
    except Exception as e:
        print(f"⚠️ {trade_date} 数据拉取失败: {e}")

if not price_map:
    print("⚠️ 无法获取美股价格数据，退出。")
    exit(0)

def parse_hold_days(hold_period_str):
    if not hold_period_str or hold_period_str in ['N/A', 'nan', '坚决空仓', '观望']:
        return None
    nums = re.findall(r'\d+', str(hold_period_str))
    if nums:
        return int(nums[-1])
    return None

def get_price_on_date(ticker, target_date_str):
    if df_hist_all.empty:
        return None
    ticker_data = df_hist_all[df_hist_all['clean_ticker'] == ticker].copy()
    if ticker_data.empty:
        return None
    ticker_data['trade_date'] = pd.to_datetime(ticker_data['trade_date'])
    target_date = pd.to_datetime(target_date_str)
    valid = ticker_data[ticker_data['trade_date'] <= target_date]
    if valid.empty:
        return None
    return float(valid.iloc[-1]['close'])

# ==========================================
# 按票聚合，过滤不需要追踪的票
# ==========================================
active_list = []
expired_list = []

for ticker, group in recent_picks.groupby('Ticker'):
    group = group.sort_values('Date')
    first_row = group.iloc[0]
    latest_row = group.iloc[-1]
    days_held = (datetime.datetime.now() - first_row['Date']).days

    latest_tag = str(latest_row.get('Tag', '')).strip()
    if latest_tag == 'Trap_Warning':
        print(f"跳过 Trap_Warning: {ticker}")
        continue

    # 固定用第一次推荐的周期和止损
    hold_period_str = 'N/A'
    stop_loss = 'N/A'
    for _, r in group.iterrows():
        if str(r.get('Hold_Period', 'N/A')).strip() not in ['N/A', 'nan', '', '坚决空仓']:
            hold_period_str = r['Hold_Period']
            break
    for _, r in group.iterrows():
        if str(r.get('Stop_Loss', 'N/A')).strip() not in ['N/A', 'nan', '', '坚决空仓', '绝对规避']:
            stop_loss = r['Stop_Loss']
            break

    hold_days = parse_hold_days(hold_period_str)
    if hold_days is None:
        print(f"跳过无持仓周期: {ticker}")
        continue

    rec_price = float(first_row['Price'])
    maturity_date_dt = first_row['Date'] + datetime.timedelta(days=hold_days)
    maturity_date = maturity_date_dt.strftime('%Y-%m-%d')

    if maturity_date_dt <= datetime.datetime.now():
        # 已超期 → 归档
        maturity_price = get_price_on_date(ticker, maturity_date)
        maturity_pnl = round(((maturity_price - rec_price) / rec_price) * 100, 2) if maturity_price else None

        expired_list.append({
            "Ticker": ticker,
            "Name": first_row['Name'],
            "Tag": latest_tag,
            "Hold_Period": hold_period_str,
            "Stop_Loss": stop_loss,
            "First_Rec_Date": first_row['Date'].strftime('%Y-%m-%d'),
            "Rec_Price": rec_price,
            "Maturity_Date": maturity_date,
            "Maturity_Price": maturity_price if maturity_price else "无数据",
            "Maturity_PnL": maturity_pnl if maturity_pnl is not None else "无数据",
            "Days_Held": days_held,
            "Rec_Count": len(group),
        })
    else:
        # 持仓中 → 继续追踪
        cur_price = price_map.get(ticker)
        if not cur_price:
            continue

        cur_pnl = round(((cur_price - rec_price) / rec_price) * 100, 2)
        remaining = (maturity_date_dt - datetime.datetime.now()).days

        active_list.append({
            "Ticker": ticker,
            "Name": first_row['Name'],
            "Tag": latest_tag,
            "Hold_Period": hold_period_str,
            "Stop_Loss": stop_loss,
            "First_Rec_Date": first_row['Date'].strftime('%Y-%m-%d'),
            "Rec_Price": rec_price,
            "Cur_Price": cur_price,
            "Days_Held": days_held,
            "Remaining_Days": remaining,
            "PnL": cur_pnl,
            "Rec_Count": len(group),
        })

print(f"✅ 持仓中: {len(active_list)} 只 | 已超期(本次归档): {len(expired_list)} 只")

if not active_list and not expired_list:
    print("⚠️ 无需复盘的标的，退出。")
    exit(0)

# ==========================================
# Claude 归因分析（流式输出）
# ==========================================
client = anthropic.Anthropic(
    api_key=os.environ.get("CLAWSOCKET_API_KEY"),
    base_url=os.environ.get("CLAWSOCKET_BASE_URL")
)
print("触发 Claude 执行盘后归因...")

prompt = f"""
你是量化风控总监。以下是今日需要复盘的美股标的数据：

【持仓中（周期内，需要给出风控指令）】：
{active_list}

【已超期（本次归档，只做策略复盘评价，不需要风控指令）】：
{expired_list}

字段说明：
- Rec_Price：首次推荐价，即买入成本，后续重复推荐不改变此基准
- Hold_Period：建议持仓周期（第一次推荐时固定，不被后续推荐覆盖）
- Stop_Loss：止损位（第一次推荐时固定）
- Remaining_Days：距离期满还有多少天（持仓中才有）
- Maturity_PnL：期满日的真实盈亏（已超期才有，这才是策略真实表现）
- Rec_Count：系统连续推荐次数，次数越多说明持续看好

请严格按以下 HTML 骨架输出复盘报告（直出HTML，禁加markdown框，盈利标红，亏损标绿）：

<div style="background: #eceff1; border-left: 6px solid #455a64; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #263238;">⚖️ 盘后总体风控审查</h3>
    <p>(总结持仓中标的整体盈亏，以及已超期标的的策略胜率评估)</p>
</div>

<h2 style="color: #1565c0; border-bottom: 2px solid #1565c0; padding-bottom: 5px;">📊 持仓中 - 风控纪律核对单</h2>
<div style="background: #fff; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
    <h3 style="margin: 0 0 10px 0;">[First_Rec_Date] | [Name] ([Ticker]) | 系统连续推荐[Rec_Count]次 | 还剩[Remaining_Days]天到期</h3>
    <p><b>持股周期:</b> [Hold_Period] | <b>止损位:</b> [Stop_Loss]</p>
    <p><b>买入成本:</b> $[Rec_Price] ➔ <b>现价:</b> $[Cur_Price] | <b>当前盈亏:</b> <span style="font-weight:bold; color:[盈利#d32f2f/亏损#388e3c];">[PnL]%</span></p>
    <p><span style="background: #607d8b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">风控动作指令</span>
    (判断：现价是否跌破止损位？系统是否仍在持续推荐？给出持有/止损/减仓指令)</p>
</div>

<h2 style="color: #37474f; border-bottom: 2px solid #cfd8dc; padding-bottom: 5px; margin-top: 40px;">📁 已超期归档 - 策略复盘评价</h2>
<div style="background: #f5f5f5; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e0e0e0;">
    <h3 style="margin: 0 0 10px 0;">[First_Rec_Date] | [Name] ([Ticker]) | 期满日:[Maturity_Date]</h3>
    <p><b>持股周期:</b> [Hold_Period] | <b>止损位:</b> [Stop_Loss]</p>
    <p><b>买入成本:</b> $[Rec_Price] → <b>期满日价格:</b> $[Maturity_Price] | <b>策略实际盈亏:</b> <span style="font-weight:bold; color:[盈利#d32f2f/亏损#388e3c];">[Maturity_PnL]%</span></p>
    <p><span style="background: #455a64; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">策略复盘</span>
    (评价这次策略是否成功，归因分析盈亏原因，此票不再追踪)</p>
</div>
"""

ai_html = ""
with client.messages.stream(
    model=TARGET_MODEL,
    max_tokens=3000,
    temperature=0.1,
    messages=[{"role": "user", "content": prompt}]
) as stream:
    for text in stream.text_stream:
        ai_html += text

ai_html = ai_html.replace("```html", "").replace("```", "").strip()

# ==========================================
# 写入 review_history.csv
# ==========================================
review_log = "review_history.csv"
need_header = not os.path.exists(review_log) or os.path.getsize(review_log) == 0
try:
    with open(review_log, "a", encoding="utf-8") as f:
        if need_header:
            f.write("Review_Date,Ticker,Name,Tag,Rec_Date,Rec_Price,Cur_Price,Days_Held,PnL_Pct,Maturity_PnL,Hold_Period,Stop_Loss,Rec_Count,Status\n")
        review_date = get_now()

        for item in active_list:
            f.write(f"{review_date},{item['Ticker']},{item['Name']},{item['Tag']},{item['First_Rec_Date']},{item['Rec_Price']},{item['Cur_Price']},{item['Days_Held']},{item['PnL']},,{item['Hold_Period']},{item['Stop_Loss']},{item['Rec_Count']},持仓中\n")

        for item in expired_list:
            maturity_pnl = item['Maturity_PnL'] if item['Maturity_PnL'] != "无数据" else ""
            f.write(f"{review_date},{item['Ticker']},{item['Name']},{item['Tag']},{item['First_Rec_Date']},{item['Rec_Price']},{item['Maturity_Price']},{item['Days_Held']},{maturity_pnl},{maturity_pnl},{item['Hold_Period']},{item['Stop_Loss']},{item['Rec_Count']},已超期归档\n")

    print("✅ 复盘结果已写入 review_history.csv")
except Exception as e:
    print(f"⚠️ 复盘写入失败: {e}")

# ==========================================
# 封装发送
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
