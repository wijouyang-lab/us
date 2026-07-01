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
    
    prompt = f"""
你是首席定量分析师，请根据以下最新提取的交易记录，进行本期操作的回顾与复盘。
要求：
1. 分析 Active 持仓的整体胜率与盈亏分布。
2. 重点评估 Dropped 斩仓操作的有效性（斩仓后该股是继续下跌证明了风控有效，还是反弹打脸了我们的风控？）。
3. 给出后续优化策略。
输出格式要求直接为精美的 HTML 片段（无 markdown 外框）。

【持仓与风控拦截数据】：
{report_data}
"""
    
    response = client.messages.create(
        model=REVIEW_MODEL_PRO,
        max_tokens=4000,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()

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
        
    print("✅ 复盘生成完毕，请查收 review_report.html")
