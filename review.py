# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
import re

# ==========================================
# 1. 基础配置与时区初始化
# ==========================================
US_TZ = datetime.timezone(datetime.timedelta(hours=-4))

def get_us_time():
    """获取美东当前时间"""
    return datetime.datetime.now(US_TZ)

# 周末检查逻辑
current_time = get_us_time()
if current_time.weekday() >= 5:
    print(f"当前时间为周{current_time.weekday() + 1}，属于周末休市时间，退出盘后复盘程序。")
    import sys
    sys.exit(0)

TARGET_MODEL = 'claude-opus-4-8'
print("=" * 50)
print("🚀 启动美股盘后复盘与风控审查引擎 (全功能工程版)...")
print("=" * 50)

# ==========================================
# 2. 账本文件检查与加载
# ==========================================
log_file = "trade_history.csv"
if not os.path.exists(log_file):
    print(f"⚠️ 警告：未检测到交易账本文件 [{log_file}]，跳过本次复盘。")
    import sys
    sys.exit(0)

try:
    print(f"📂 正在加载交易账本: {log_file} ...")
    df = pd.read_csv(log_file)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # 筛选最近 30 天的记录
    cutoff_date = get_us_time() - datetime.timedelta(days=30)
    recent_picks = df[df['Date'] >= cutoff_date.replace(tzinfo=None)].copy()
    
    if recent_picks.empty:
        print("⚠️ 提示：最近 30 天内无任何操作记录，跳过复盘。")
        import sys
        sys.exit(0)
    print(f"✅ 成功加载最近 30 天交易记录，共计 {len(recent_picks)} 行原始数据。")
except Exception as e:
    print(f"❌ 错误：账本读取失败，异常原因: {e}")
    import sys
    sys.exit(1)

# ==========================================
# 3. 版本过滤与字段清洗校验
# ==========================================
print("🔍 正在进行版本过滤与字段合法性校验...")
# 改用 Hold_Period 判断是否为新版本完整记录（原来用 Score，但 Score 解析曾有正则bug
# 导致恒为N/A，会把本该正常追踪的记录当"旧版本"误删；Hold_Period 没受过那个bug影响）。
_INVALID = {'', 'n/a', 'nan', 'none'}
for _col in ['Hold_Period', 'Stop_Loss', 'Score']:
    if _col not in recent_picks.columns:
        recent_picks[_col] = ''

_schema_valid = recent_picks['Hold_Period'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID)
_dropped = (~_schema_valid).sum()
if _dropped > 0:
    print(f"🗂️ 版本过滤提示：成功剔除 {_dropped} 条 Hold_Period 缺失的旧版本/不完整记录，不纳入本次复盘。")
recent_picks = recent_picks[_schema_valid].copy()

# Score=N/A 仅提示，不剔除（可能只是历史评分bug导致这一列是N/A）
_no_score = recent_picks['Score'].astype(str).str.strip().str.lower().isin(_INVALID)
if _no_score.sum() > 0:
    tickers_no_score = recent_picks.loc[_no_score, 'Ticker'].tolist()
    print(f"⚠️ 提示：以下 {_no_score.sum()} 条记录 Score=N/A（可能是历史评分bug所致），仍会继续追踪：{tickers_no_score[:10]}")

# 检查 Stop_Loss 是否为 N/A
_no_stoploss = recent_picks['Stop_Loss'].astype(str).str.strip().str.lower().isin(_INVALID)
if _no_stoploss.sum() > 0:
    tickers_no_sl = recent_picks.loc[_no_stoploss, 'Ticker'].tolist()
    print(f"⚠️ 警告：以下 {_no_stoploss.sum()} 条记录的 Stop_Loss 属性为 N/A，将继续追踪但无法进行精确止损价核查。涉及标的: {tickers_no_sl[:10]}")

if recent_picks.empty:
    print("⚠️ 警告：经过版本过滤后，无有效的新版本记录可供复盘，程序退出。")
    import sys
    sys.exit(0)

# ==========================================
# 4. 行情数据拉取与价格映射准备
# ==========================================
all_tickers_raw = recent_picks['Ticker'].unique().tolist()
# 美股特有：清洗带 $ 符号的 Ticker
clean_map = {t: t.lstrip('$') for t in all_tickers_raw}
clean_tickers = list(set(clean_map.values()))

print(f"📡 正在通过 yfinance 批量拉取美股历史行情数据，标的列表: {clean_tickers}")
df_hist_all = pd.DataFrame()
price_map_today = {}

if clean_tickers:
    try:
        hist_data = yf.download(clean_tickers, period="60d", progress=False, auto_adjust=True, group_by='ticker')
        if len(clean_tickers) == 1:
            t = clean_tickers[0]
            temp_df = hist_data.copy()
            temp_df['ts_code'] = t
            temp_df['trade_date'] = temp_df.index
            df_hist_all = temp_df[['ts_code', 'trade_date', 'Close']].rename(columns={'Close': 'close'})
            if not df_hist_all.empty:
                price_map_today[t] = float(df_hist_all['close'].iloc[-1])
        else:
            records = []
            for t in clean_tickers:
                try:
                    s = hist_data[t]['Close'].dropna()
                    for date, val in s.items():
                        records.append({'ts_code': t, 'trade_date': date, 'close': float(val)})
                    if not s.empty:
                        price_map_today[t] = float(s.iloc[-1])
                except Exception as sub_e:
                    print(f"⚠️ 解析标的 {t} 历史行情出错: {sub_e}")
            df_hist_all = pd.DataFrame(records)
        print(f"✅ 行情数据拉取完毕，成功获取最新收盘价的标的数: {len(price_map_today)}")
    except Exception as e:
        print(f"❌ 严重错误：调用 yfinance 历史价格拉取失败: {e}")

# ==========================================
# 5. 核心辅助函数定义
# ==========================================
def parse_hold_days(hold_period_str):
    """从持股周期字符串中提取天数"""
    if not hold_period_str or str(hold_period_str).strip().lower() in ['n/a', 'nan', '坚决空仓', '观望']:
        return None
    nums = re.findall(r'\d+', str(hold_period_str))
    if nums:
        return int(nums[-1])
    return None

def get_price_on_date(clean_ticker, target_date_str):
    """获取指定历史日期的收盘价"""
    if df_hist_all.empty:
        return None
    ticker_data = df_hist_all[df_hist_all['ts_code'] == clean_ticker].copy()
    if ticker_data.empty:
        return None
    ticker_data['trade_date'] = pd.to_datetime(ticker_data['trade_date']).dt.tz_localize(None)
    target_date = pd.to_datetime(target_date_str)
    valid = ticker_data[ticker_data['trade_date'] <= target_date]
    if valid.empty:
        return None
    return float(valid.iloc[-1]['close'])

def get_live_quote(clean_ticker):
    """
    实时行情兜底：当天刚入账的新推荐，或 review.py 紧跟在 scan.py 后运行、
    yfinance 批量历史日线还没同步出"今天"这根K线时，price_map_today 里会
    查不到该标的，导致它在后面被 continue 跳过、从复盘报告里"消失"。
    这里对单个标的发起一次实时查询，兜底拿到开盘价/最新价。
    """
    try:
        fi = yf.Ticker(clean_ticker).fast_info
        try:
            open_p = float(fi["open"])
        except Exception:
            open_p = None
        try:
            last_p = float(fi["last_price"])
        except Exception:
            last_p = None
        return open_p, last_p
    except Exception as e:
        print(f"⚠️ 实时行情兜底查询失败 [{clean_ticker}]: {e}")
        return None, None

# ==========================================
# 6. 读取历史归档记录以实现去重
# ==========================================
already_archived = set()
review_log_path = "review_history.csv"

if os.path.exists(review_log_path) and os.path.getsize(review_log_path) > 0:
    try:
        existing_review = pd.read_csv(review_log_path, on_bad_lines='skip')
        if {'Status', 'Ticker', 'Rec_Date'}.issubset(existing_review.columns):
            archived_rows = existing_review[existing_review['Status'].isin(
                ['已超期归档', '突发清仓暂停', '止损触发清仓', '周期到期清仓']
            )]
            already_archived = set(zip(archived_rows['Ticker'].astype(str), archived_rows['Rec_Date'].astype(str)))
            print(f"📌 已加载历史归档去重库，共包含 {len(already_archived)} 笔已处理记录。")
    except Exception as e:
        print(f"⚠️ 读取历史归档记录出错，将跳过部分去重校验: {e}")

# ==========================================
# 7. 遍历分组持仓并分类处理（活跃 vs 超期）
# ==========================================
active_list = []
expired_list = []
skipped_duplicate = 0

print("🔄 开始逐个标的进行持仓状态与期满归档判定...")
for orig_ticker, group in recent_picks.groupby('Ticker'):
    group = group.sort_values('Date')
    first_row = group.iloc[0]
    latest_row = group.iloc[-1]
    days_held = (get_us_time().replace(tzinfo=None) - first_row['Date']).days

    latest_tag = str(latest_row.get('Tag', '')).strip()
    
    if latest_tag in ['Trap_Warning', 'Forced_Exit', 'Stop_Loss_Hit', 'Period_Matured']:
        print(f"⏸️ 标的 [{orig_ticker}] 已被防守端标签处理（{latest_tag}），跳过常规追踪。")
        continue

    hold_period_str = 'N/A'
    stop_loss = 'N/A'
    score_str = 'N/A'
    
    for _, r in group.iterrows():
        val = str(r.get('Hold_Period', 'N/A')).strip()
        if val not in ['N/A', 'nan', '', '坚决空仓']:
            hold_period_str = r['Hold_Period']
            break
            
    for _, r in group.iterrows():
        val = str(r.get('Stop_Loss', 'N/A')).strip()
        if val not in ['N/A', 'nan', '', '坚决空仓', '绝对规避', '观望']:
            stop_loss = r['Stop_Loss']
            break
            
    for _, r in group.iterrows():
        val = str(r.get('Score', 'N/A')).strip()
        if val not in ['N/A', 'nan', '']:
            score_str = r['Score']
            break

    hold_days = parse_hold_days(hold_period_str)
    clean_t = clean_map.get(orig_ticker, orig_ticker)
    
    try:
        rec_price = float(first_row.get('Price', first_row.get('Close_Price', 0)))
    except:
        rec_price = 0.0

    if hold_days is None:
        print(f"⏭️ 标的 [{orig_ticker}] 持股周期为 N/A，按要求从复盘列表中剔除。")
        continue

    rec_date_str = first_row['Date'].strftime('%Y-%m-%d')
    maturity_date_dt = first_row['Date'] + datetime.timedelta(days=hold_days)
    maturity_date = maturity_date_dt.strftime('%Y-%m-%d')

    if maturity_date_dt.replace(tzinfo=None) <= get_us_time().replace(tzinfo=None):
        if (str(orig_ticker), rec_date_str) in already_archived:
            skipped_duplicate += 1
            continue

        maturity_price = get_price_on_date(clean_t, maturity_date)
        maturity_pnl = round(((maturity_price - rec_price) / rec_price) * 100, 2) if maturity_price and rec_price > 0 else None

        expired_list.append({
            "代码": orig_ticker,
            "名称": first_row.get('Name', orig_ticker),
            "标签": latest_tag,
            "推荐评分": score_str,
            "持股周期建议": hold_period_str,
            "止损价": stop_loss,
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "期满日": maturity_date,
            "期满日价格": maturity_price if maturity_price else "无数据",
            "期满日盈亏(%)": maturity_pnl if maturity_pnl is not None else "无数据",
            "持仓天数": days_held,
            "系统连续推荐次数": len(group),
        })
    else:
        is_new_today = (rec_date_str == get_us_time().strftime('%Y-%m-%d'))
        today_open_price = None

        cur_price = price_map_today.get(clean_t)

        if not cur_price:
            cur_price = get_price_on_date(clean_t, get_us_time().strftime('%Y-%m-%d'))

        if not cur_price or is_new_today:
            # 批量历史下载可能还没有"今天"这根K线（新入账推荐尤其常见）：
            # 单独发起实时查询，拿到当天的开盘价/最新价兜底。
            live_open, live_last = get_live_quote(clean_t)
            today_open_price = live_open
            if not cur_price:
                cur_price = live_last or live_open

        # 修复：trade_history.csv 里 Price 列在盘前扫描时写入的是能拿到的最近一次收盘价
        # （不是真正的"今天买入价"，因为扫描发生在开盘前）。今天新增的推荐，如果这里
        # 成功拿到了当天真实开盘价，就用它覆盖 rec_price——否则"首次推荐价"和盈亏
        # 都是拿旧收盘价当买入价在算，会算出跟实际持仓完全对不上的盈亏结果。
        if is_new_today and today_open_price:
            rec_price = today_open_price

        if not cur_price:
            # 实时查询也失败，最后兜底用推荐价本身，保证该标的仍会出现在复盘报告里
            # （而不是被静默跳过），同时明确打印警告方便排查。
            print(f"⚠️ 标的 [{orig_ticker}] 现价/开盘价均获取失败，暂用推荐价代替显示，盈亏将显示为 0%。")
            cur_price = rec_price

        cur_pnl = round(((cur_price - rec_price) / rec_price) * 100, 2) if rec_price > 0 else 0
        remaining = (maturity_date_dt.replace(tzinfo=None) - get_us_time().replace(tzinfo=None)).days

        active_list.append({
            "代码": orig_ticker,
            "名称": first_row.get('Name', orig_ticker),
            "标签": latest_tag,
            "推荐评分": score_str,
            "持股周期建议": hold_period_str,
            "止损价": stop_loss,
            "首次推荐日": rec_date_str,
            "首次推荐价": rec_price,
            "今日开盘价": round(today_open_price, 2) if today_open_price else ("N/A" if not is_new_today else round(cur_price, 2)),
            "现价": cur_price,
            "持仓天数": days_held,
            "剩余天数": remaining,
            "当前盈亏(%)": cur_pnl,
            "系统连续推荐次数": len(group),
            "今日新增": "是" if is_new_today else "否",
        })

if skipped_duplicate > 0:
    print(f"📌 去重机制生效：本次成功跳过 {skipped_duplicate} 条已归档的历史到期交易。")

print(f"📊 分类统计结果 -> 持仓中: {len(active_list)} 只 | 已超期(本次新归档): {len(expired_list)} 只")

if not active_list and not expired_list:
    print("⚠️ 提示：当前没有需要复盘的有效标的，程序安全退出。")
    import sys
    sys.exit(0)

# ==========================================
# 8. 调用大模型生成风控报告内容
# ==========================================
print("🤖 正在调用 Claude 客户端生成美股盘后风控审查与策略复盘报告...")
client = anthropic.Anthropic(
    api_key=os.environ.get("CLAWSOCKET_API_KEY"),
    base_url=os.environ.get("CLAWSOCKET_BASE_URL")
)

prompt = f'''
你是顶级量化风控总监。以下是今日需要复盘的美股标的数据：

【持仓中（周期内，需要给出风控指令）】：
{active_list}

【已超期（本次新归档，只做策略复盘评价，不需要风控指令）】：
{expired_list}

在风控判断或策略复盘时，请结合推荐评分进行验证：高分票（80分以上）如果出现明显亏损，需要特别指出"高信心预期未兑现"；低分票（60分以下）如果反而盈利良好，也需要指出"评分体系可能过于保守"。

【今日新增标的特别说明】持仓列表中"今日新增"="是"的标的是当天刚生成的全新推荐，"现价"为当天的开盘价/实时价，尚未经历完整交易日，几乎不会有真实盈亏。这类标的请勿按亏损/止损逻辑给风控指令，只需确认开盘价已正确入账，风控动作指令统一给"新建仓，持有观察，明日起纳入正常止损监控"，摘要中也不要把它们的 0% 波动算作"高信心预期未兑现"。

请严格按以下 HTML 骨架输出复盘报告（直出HTML，禁加markdown框，盈利标红，亏损标绿）：

<div style="background: #eceff1; border-left: 6px solid #455a64; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #263238;">⚖️ 盘后总体风控审查</h3>
    <p>(总结持仓中标的整体盈亏状况，以及本次新归档标的的策略胜率评估，特别指出评分与实际表现是否存在明显反差；若有今日新增标的，在此提一句今日共新增几只)</p>
</div>

<h2 style="color: #1565c0; border-bottom: 2px solid #1565c0; padding-bottom: 5px;">📊 持仓中 - 风控纪律核对单</h2>
<div style="background: #fff; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
    <h3 style="margin: 0 0 10px 0;">[若"今日新增"="是"则在最前面加一个 🆕今日新增 徽章] [首次推荐日] | [股票名称] ([代码]) | 评分[推荐评分]/100 | 系统连续推荐[N]次 | 还剩[剩余天数]天到期</h3>
    <p><b>持股周期建议:</b> [持股周期建议] | <b>止损位:</b> [止损价]</p>
    <p><b>买入成本:</b> $[首次推荐价] ➔ <b>现价:</b> $[现价]（今日开盘价 $[今日开盘价]） | <b>当前盈亏:</b> <span style="font-weight:bold; color:[盈利#d32f2f/亏损#388e3c];">[当前盈亏(%)]%</span></p>
    <p><span style="background: #607d8b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">风控动作指令</span>
    (今日新增标的：给"新建仓，持有观察"；其余标的：判断现价是否跌破止损位，给出持有/止损/减仓指令)</p>
</div>

<h2 style="color: #37474f; border-bottom: 2px solid #cfd8dc; padding-bottom: 5px; margin-top: 40px;">📁 已超期归档 - 策略复盘评价</h2>
<div style="background: #f5f5f5; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #e0e0e0;">
    <h3 style="margin: 0 0 10px 0;">[首次推荐日] | [股票名称] ([代码]) | 评分[推荐评分]/100 | 期满日:[期满日]</h3>
    <p><b>持股周期建议:</b> [持股周期建议] | <b>止损位:</b> [止损价]</p>
    <p><b>买入成本:</b> $[首次推荐价] → <b>期满日价格:</b> $[期满日价格] | <b>策略实际盈亏:</b> <span style="font-weight:bold; color:[盈利#d32f2f/亏损#388e3c];">[期满日盈亏(%)]%</span></p>
    <p><span style="background: #455a64; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">策略复盘</span>
    (评价这次策略是否成功，归因分析盈亏原因)</p>
</div>

【极其重要】直接输出HTML代码，第一个字符必须是 < 符号，绝对不要输出任何思考过程。
'''

ai_html = ""
with client.messages.stream(
    model=TARGET_MODEL,
    max_tokens=30000,
    temperature=0.1,
    messages=[{"role": "user", "content": prompt}]
) as stream:
    for text in stream.text_stream:
        ai_html += text

ai_html = ai_html.replace("```html", "").replace("```", "").strip()

html_start = ai_html.find("<div")
if html_start > 0:
    print(f"⚠️ 警告：检测到 AI 输出前置了 {html_start} 字符的非 HTML 内容，已自动切片丢弃。")
    ai_html = ai_html[html_start:]

# ==========================================
# 9. 写入归档记录至 review_history.csv
# ==========================================
review_log = "review_history.csv"
new_header = "Review_Date,Ticker,Name,Tag,Rec_Date,Rec_Price,Cur_Price,Days_Held,PnL_Pct,Maturity_PnL,Hold_Period,Stop_Loss,Rec_Count,Status,Score\n"
review_file_exists = os.path.exists(review_log) and os.path.getsize(review_log) > 0
review_need_header = not review_file_exists

if review_file_exists:
    with open(review_log, "r", encoding="utf-8") as f:
        review_lines = f.readlines()
    if review_lines and "Score" not in review_lines[0]:
        review_lines[0] = new_header
        with open(review_log, "w", encoding="utf-8") as f:
            f.writelines(review_lines)
        print("📌 历史复盘日志表头已自动升级更新。")

try:
    with open(review_log, "a", encoding="utf-8") as f:
        if review_need_header:
            f.write(new_header)
        review_date = get_us_time().strftime('%Y-%m-%d')

        for item in active_list:
            f.write(f"{review_date},{item['代码']},{item['名称']},{item['标签']},{item['首次推荐日']},{item['首次推荐价']},{item['现价']},{item['持仓天数']},{item['当前盈亏(%)']},,{item['持股周期建议']},{item['止损价']},{item['系统连续推荐次数']},持仓中,{item['推荐评分']}\n")

        for item in expired_list:
            maturity_pnl = item['期满日盈亏(%)'] if item['期满日盈亏(%)'] != "无数据" else ""
            f.write(f"{review_date},{item['代码']},{item['名称']},{item['标签']},{item['首次推荐日']},{item['首次推荐价']},{item['期满日价格']},{item['持仓天数']},{maturity_pnl},{maturity_pnl},{item['持股周期建议']},{item['止损价']},{item['系统连续推荐次数']},已超期归档,{item['推荐评分']}\n")

    print("✅ 成功将本次复盘状态写入 review_history.csv 文件。")
except Exception as e:
    print(f"❌ 错误：复盘历史数据写入失败: {e}")

# ==========================================
# 10. 程序化 KPI 指标计算与 HTML 仪表盘渲染
# ==========================================
print("📈 正在计算核心 KPI 指标并组装 HTML 仪表盘...")
historical_closed = []
_INVALID_H = {'', 'n/a', 'nan', 'none'}

if os.path.exists(review_log) and os.path.getsize(review_log) > 0:
    try:
        existing_review = pd.read_csv(review_log, on_bad_lines='skip')
        closed_rows = existing_review[existing_review['Status'].isin(['已超期归档', '突发清仓暂停', '止损触发清仓', '周期到期清仓'])]
        for _, r in closed_rows.iterrows():
            try:
                pnl_val = r['PnL_Pct']
                if pd.notna(pnl_val) and str(pnl_val).strip().lower() not in _INVALID_H:
                    pnl = float(pnl_val)
                else:
                    pnl_mat = r['Maturity_PnL']
                    if pd.notna(pnl_mat) and str(pnl_mat).strip().lower() not in _INVALID_H:
                        pnl = float(pnl_mat)
                    else:
                        continue
            except:
                continue
                
            prevented = 0.0
            try:
                sl_val = str(r.get('Stop_Loss', 'N/A')).strip()
                cur_val = str(r.get('Cur_Price', 'N/A')).strip()
                if sl_val not in _INVALID_H and cur_val not in _INVALID_H:
                    sl_price = float(sl_val)
                    cur_price = float(cur_val)
                    prevented = round((sl_price - cur_price) / sl_price * 100, 2) if sl_price > 0 else 0.0
            except:
                pass
                
            historical_closed.append({
                'ticker': r.get('Ticker', ''),
                'name': r.get('Name', ''),
                'pnl': pnl,
                'prevented': prevented,
                'status': r.get('Status', '已超期归档')
            })
    except Exception as e:
        print(f"⚠️ 读取历史归档用于 KPI 计算时出错: {e}")

all_closed_trades = []
for h in historical_closed:
    all_closed_trades.append(h)
for item in expired_list:
    try:
        pnl = float(item['期满日盈亏(%)']) if item['期满日盈亏(%)'] != "无数据" else 0.0
    except:
        pnl = 0.0
    all_closed_trades.append({
        'ticker': item['代码'], 'name': item['名称'], 'pnl': pnl,
        'prevented': 0.0, 'status': '已超期归档'
    })

active_count = len(active_list)
closed_count = len(all_closed_trades)
total_count = active_count + closed_count

new_today_count = sum(1 for x in active_list if x.get('今日新增') == '是')
# 今日新增标的当天开盘即入账，几乎不会有真实盈亏，不计入胜率分母，避免拉低数据准确性
_win_rate_pool = [x for x in active_list if x.get('今日新增') != '是']
active_wins = sum(1 for x in _win_rate_pool if isinstance(x['当前盈亏(%)'], (int, float)) and x['当前盈亏(%)'] > 0)
active_win_rate = (active_wins / len(_win_rate_pool) * 100) if _win_rate_pool else 0.0

closed_wins = sum(1 for x in all_closed_trades if x['pnl'] > 0)
closed_win_rate = (closed_wins / closed_count * 100) if closed_count > 0 else 0.0

effective_risk = sum(1 for x in all_closed_trades if x['prevented'] >= -2.0)
risk_rate = (effective_risk / closed_count * 100) if closed_count > 0 else 0.0

# 美股超级赢家阈值设定为 50%
super_threshold = 50.0
all_pnl_list = [x['当前盈亏(%)'] for x in active_list if isinstance(x['当前盈亏(%)'], (int, float))] + [x['pnl'] for x in all_closed_trades]
super_winners = [p for p in all_pnl_list if p >= super_threshold]
super_winner_contribution = sum(super_winners)

other_winners = [p for p in all_pnl_list if 0.0 < p < super_threshold]
other_winner_avg = (sum(other_winners) / len(other_winners)) if other_winners else 0.0

losers = [p for p in all_pnl_list if p < 0.0]
loser_avg = (sum(losers) / len(losers)) if losers else 0.0

kpi_html = f"""
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 20px;">
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #1565c0;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">📊 总推荐笔数</div>
        <div style="font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 5px;">{total_count}</div>
        <div style="font-size: 12px; color: #95a5a6;">活跃持仓 {active_count} 笔（含今日新增 {new_today_count} 笔） · 历史归档 {closed_count} 笔</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #2ecc71;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">📈 活跃持仓胜率</div>
        <div style="font-size: 24px; font-weight: bold; color: #2ecc71; margin-bottom: 5px;">{active_win_rate:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">{active_wins} 赢 / {len(_win_rate_pool) - active_wins} 亏（不含今日新增 {new_today_count} 笔）</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #e67e22;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">📉 已归档实现胜率</div>
        <div style="font-size: 24px; font-weight: bold; color: #e67e22; margin-bottom: 5px;">{closed_win_rate:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">{closed_wins} 赢 / {closed_count - closed_wins} 亏</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #95a5a6;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">🛡️ 风控拦截率</div>
        <div style="font-size: 24px; font-weight: bold; color: #95a5a6; margin-bottom: 5px;">{risk_rate:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">{effective_risk}/{closed_count} 次避险离场有效防范深度回撤</div>
    </div>
</div>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 25px;">
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #9b59b6;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">🏆 超级赢家贡献</div>
        <div style="font-size: 24px; font-weight: bold; color: #9b59b6; margin-bottom: 5px;">+{super_winner_contribution:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">超级赢家(>{super_threshold}%)累计涨幅</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #1abc9c;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">💰 其余盈利平均</div>
        <div style="font-size: 24px; font-weight: bold; color: #1abc9c; margin-bottom: 5px;">+{other_winner_avg:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">扣除超级赢家后的盈利均值</div>
    </div>
    <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #e74c3c;">
        <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">⚠️ 亏损标的平均</div>
        <div style="font-size: 24px; font-weight: bold; color: #e74c3c; margin-bottom: 5px;">{loser_avg:.2f}%</div>
        <div style="font-size: 12px; color: #95a5a6;">所有亏损标的的平均跌幅</div>
    </div>
</div>
"""

full_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f4f6f8; padding: 20px; }}
    .card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); max-width: 1200px; margin: 0 auto; }}
</style></head>
<body>
    <div class='card'>
        <h2 style='color: #2c3e50; margin-top: 0; margin-bottom: 20px; font-size: 26px; border-bottom: 3px solid #1565c0; padding-bottom: 10px; display: flex; align-items: center; gap: 10px;'>
            <span>📊 美股盘后复盘与风控审查报告</span>
        </h2>
        {kpi_html}
        
        {ai_html}
    </div>
</body></html>"""

# ==========================================
# 11. 邮件发送模块
# ==========================================
def send_mail():
    """发送复盘报告邮件"""
    acc = os.environ.get("EMAIL_ACCOUNT")
    pwd = os.environ.get("EMAIL_PASSWORD")
    owner_email = os.environ.get("TARGET_EMAILS") or os.environ.get("OWNER_EMAIL")
    
    if not acc or not pwd or not owner_email:
        print("⚠️ 邮件发送配置缺失（缺少 ACCOUNT/PASSWORD/TARGET_EMAILS），跳过邮件发送。报告已安全保存在本地。")
        return

    msg = MIMEMultipart()
    msg['From'] = acc
    msg['To'] = owner_email
    msg['Subject'] = f"【盘后清算】美股风控纪律与复盘 ({get_us_time().strftime('%Y-%m-%d')})"
    msg.attach(MIMEText(full_html, 'html', 'utf-8'))
    
    to_list = [e.strip() for e in owner_email.split(',')]
    
    try:
        print(f"📧 正在通过 SSL 连接发送邮件至: {owner_email} ...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(acc, pwd)
            s.sendmail(acc, to_list, msg.as_string())
            print(f"✅ 邮件发送成功！收件人: {owner_email}")
    except Exception as e:
        print(f"❌ 错误：邮件发送失败，异常原因: {e}")

# 执行邮件分发
send_mail()
print("🎉 美股盘后复盘与风控审查程序顺利执行完毕。")
