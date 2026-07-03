# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

# 严格执行引擎配置：复盘深度推理使用 3.1 pro，轻量化数据清洗使用 3 flash
REVIEW_MODEL_PRO = 'claude-opus-4-8'

SUPER_ADMIN = os.environ.get("TARGET_EMAILS")
HISTORY_FILE = "trade_history.csv"

def get_latest_prices(tickers):
    if not tickers:
        return {}
    # 清洗 ticker：去掉 yfinance 不认识的 $ 前缀，然后建立"原始→清洗后"的映射，
    # 确保回填价格时用的还是 trade_history.csv 里原始的 ticker 格式
    clean_map = {t: t.lstrip('$') for t in tickers}
    clean_tickers = list(set(clean_map.values()))

    prices = {}
    try:
        df = yf.download(clean_tickers, period="1d", progress=False, auto_adjust=True)
        for orig_t, clean_t in clean_map.items():
            try:
                val = df['Close'][clean_t].iloc[-1] if len(clean_tickers) > 1 else df['Close'].iloc[-1]
                if pd.notna(val) and float(val) > 0:
                    prices[orig_t] = round(float(val), 2)
            except Exception:
                pass
    except Exception as e:
        print(f"价格批量获取失败: {e}")

    missing = [t for t in tickers if t not in prices]
    if missing:
        print(f"⚠️ 以下 {len(missing)} 只标的无法获取现价（可能已退市或 ticker 有误），复盘中将以买入价代替现价：{missing}")
    return prices

def generate_review_report(df, current_prices):
    print(f"正在调用 {REVIEW_MODEL_PRO} 引擎进行深度复盘推理...")
    client = anthropic.Anthropic(
        api_key=os.environ.get("CLAWSOCKET_API_KEY"),
        base_url=os.environ.get("CLAWSOCKET_BASE_URL")
    )
    
    # 构建输入数据
    stats_lines = []
    for idx, row in df.iterrows():
        t = row['Ticker']
        status = str(row.get('Status', 'Active')).strip()

        # buy_price 安全转换：数据脏行 Price=0 或 "N/A" 时跳过，避免后续除以 0
        try:
            buy_price = float(row['Price'])
            if buy_price <= 0:
                print(f"⚠️ 跳过 {t}：买入价为 {buy_price}，无法计算盈亏")
                continue
        except (ValueError, TypeError):
            print(f"⚠️ 跳过 {t}：买入价不是有效数字（{row['Price']}）")
            continue

        cur_price = current_prices.get(t, buy_price)  # 拿不到现价时用买入价（盈亏=0%）

        if status == 'Active':
            profit_pct = round((cur_price - buy_price) / buy_price * 100, 2)
            price_note = "（现价为买入价估算，可能已退市）" if t not in current_prices else ""
            stats_lines.append(f"[Active] {row['Name']}({t}) | 买入价: ${buy_price} → 现价: ${cur_price}{price_note} | 浮动盈亏: {profit_pct}%")

        elif status in ('Dropped', 'Stop_Loss_Hit', 'Period_Matured', 'Forced_Exit'):
            # 安全转换 Exit_Price：可能是 "N/A" 字符串或空值
            try:
                exit_price = float(row.get('Exit_Price', buy_price))
                if exit_price <= 0:
                    exit_price = buy_price
            except (ValueError, TypeError):
                exit_price = buy_price

            pnl_pct = round((exit_price - buy_price) / buy_price * 100, 2)
            post_exit_price = current_prices.get(t, exit_price)
            prevented = round((exit_price - post_exit_price) / exit_price * 100, 2) if exit_price > 0 else 0.0

            label_map = {
                'Dropped':        '宏观利空强清',
                'Stop_Loss_Hit':  '止损触发清仓',
                'Period_Matured': '持有到期清仓',
                'Forced_Exit':    '突发事件强清',
            }
            label = label_map.get(status, status)
            stats_lines.append(
                f"[{label}] {row['Name']}({t}) | 买入: ${buy_price} → 清仓: ${exit_price} | 实现盈亏: {pnl_pct}% | 清仓后继续变化: {prevented}%（验证风控有效性）"
            )

        else:
            # 未知状态，仅展示基础信息，不做计算
            stats_lines.append(f"[{status}] {row['Name']}({t}) | 买入价: ${buy_price}")

    report_data = "\n".join(stats_lines)

    # 防止超时：report_data 过大会导致 Anthropic API 响应超过 Cloudflare 120s 硬限制（524错误）
    # 按字符数截断，保留最新的记录（head保最新，tail保最旧——这里我们要最新的在前）
    MAX_REPORT_CHARS = 16000
    if len(report_data) > MAX_REPORT_CHARS:
        report_data = report_data[:MAX_REPORT_CHARS]
        last_newline = report_data.rfind('\n')
        if last_newline > 0:
            report_data = report_data[:last_newline]
        report_data += f"\n... （已截断，仅展示最近 {len(stats_lines)} 条中的前若干条，完整数据见 trade_history.csv）"
        print(f"⚠️ report_data 超过 {MAX_REPORT_CHARS} 字符，已截断以防止API超时")

    prompt = f"""
你是首席定量分析师，请根据以下最新提取的交易记录，进行本期操作的回顾与复盘。
要求：
1. 分析 Active 持仓的整体胜率与盈亏分布。
2. 重点评估已清仓操作的有效性（清仓后该股是继续下跌证明了风控有效，还是反弹说明过早离场？）。
3. 给出后续优化策略（不超过3条，要具体可执行）。
输出格式要求直接为精美的 HTML 片段（无 markdown 外框），控制在1500字以内。

【持仓与风控拦截数据】：
{report_data}
"""

    # 重试逻辑：最多3次，指数退避，每次失败后降低 max_tokens 减少响应时长
    import time as _time
    last_err = None
    for attempt in range(3):
        try:
            tokens = [2000, 1500, 1000][attempt]  # 每次重试降低token上限，缩短响应时间
            response = client.messages.create(
                model=REVIEW_MODEL_PRO,
                max_tokens=tokens,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            last_err = e
            wait = 2 ** attempt * 5  # 5s, 10s, 20s
            print(f"⚠️ API调用失败（第{attempt+1}次），{wait}秒后重试: {type(e).__name__}: {str(e)[:120]}")
            _time.sleep(wait)

    # 三次都失败：返回简易降级报告，不崩溃，邮件仍然发出
    print(f"❌ AI复盘API三次调用均失败，使用降级文字报告。最后错误: {last_err}")
    active_count = sum(1 for l in stats_lines if l.startswith('[Active]'))
    closed_count = len(stats_lines) - active_count
    return f"""
<div style="background:#fff3e0;border-left:4px solid #ff9800;padding:15px;border-radius:6px;">
    <h3>⚠️ AI复盘引擎暂时不可用（API超时）</h3>
    <p>当前持仓 <b>{active_count}</b> 只 | 已清仓记录 <b>{closed_count}</b> 条</p>
    <p>原始数据已保存在 trade_history.csv，请稍后手动触发 review.py 或等待下次自动运行。</p>
    <pre style="font-size:12px;background:#f5f5f5;padding:10px;overflow:auto;max-height:400px;">{report_data[:3000]}</pre>
</div>"""

def send_mail(to_emails, subject, content):
    user = os.environ.get("EMAIL_ACCOUNT")
    pwd = os.environ.get("EMAIL_PASSWORD")
    if not user or not pwd:
        print("⚠️ 未检测到 EMAIL_ACCOUNT / EMAIL_PASSWORD，跳过邮件发送。")
        return
    to_list = [e.strip() for e in to_emails.split(',')]
    msg = MIMEMultipart()
    msg['From'] = user
    msg['To'] = to_emails
    msg['Subject'] = subject
    msg.attach(MIMEText(content, 'html', 'utf-8'))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.sendmail(user, to_list, msg.as_string())
            print(f"✅ 复盘报告已发送至: {to_emails}")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")


if __name__ == "__main__":
    if not os.path.exists(HISTORY_FILE):
        print("未检测到交易记录，复盘取消。")
        exit()
        
    df = pd.read_csv(HISTORY_FILE, keep_default_na=False)

    # ── 新版本标记过滤：Hold_Period / Stop_Loss / Score 三字段缺一不可 ──
    # 旧版本记录缺少这三个字段，视为无效行，不纳入复盘与胜率计算。
    _INVALID_R = {'', 'n/a', 'nan', 'none'}
    for _col in ['Hold_Period', 'Stop_Loss', 'Score']:
        if _col not in df.columns:
            df[_col] = ''
    _valid_mask_r = (
        df['Hold_Period'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID_R) &
        df['Stop_Loss'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID_R) &
        df['Score'].astype(str).str.strip().str.lower().map(lambda v: v not in _INVALID_R)
    )
    _dropped_r = (~_valid_mask_r).sum()
    if _dropped_r > 0:
        print(f"🗂️ 三字段过滤：剔除 {_dropped_r} 条旧版本/不完整记录（Hold_Period/Stop_Loss/Score 任意缺失），不纳入复盘。")
    df = df[_valid_mask_r].copy()

    if df.empty:
        print("⚠️ 过滤后无有效新版本记录，复盘取消。")
        exit()
    tickers = df['Ticker'].unique().tolist()
    prices = get_latest_prices(tickers)
    
    report_html = generate_review_report(df, prices)
    
    
    full_html = f"""
    <!DOCTYPE html><html><head><meta charset='utf-8'>
    <style>
        body {{ font-family: sans-serif; background: #f4f6f8; padding: 20px; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    </style></head>
    <body>
        <div class='card'>
            <h2 style='color: #2c3e50;'>📊 资产全景复盘报告</h2>
            {report_html}
        </div>
    </body></html>
    """
    
    with open("review_report.html", "w", encoding="utf-8") as f:
        f.write(full_html)

    print("✅ 复盘生成完毕，正在发送邮件...")

    if SUPER_ADMIN:
        today_str = datetime.datetime.now().strftime('%Y-%m-%d')
        send_mail(SUPER_ADMIN, f"📊 美股持仓复盘报告 {today_str}", full_html)
    else:
        print("⚠️ TARGET_EMAILS 未设置，已跳过邮件发送，报告已保存至 review_report.html")
