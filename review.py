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
    prices = {}
    try:
        df = yf.download(tickers, period="1d", progress=False)
        for t in tickers:
            try:
                val = df['Close'][t].iloc[-1] if len(tickers) > 1 else df['Close'].iloc[-1]
                if pd.notna(val):
                    prices[t] = round(float(val), 2)
            except:
                pass
    except Exception as e:
        print(f"价格批量获取失败: {e}")
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
        buy_price = row['Price']
        status = row.get('Status', 'Active')
        
        if status == 'Active':
            cur_price = current_prices.get(t, buy_price)
            profit_pct = round((cur_price - buy_price) / buy_price * 100, 2)
            stats_lines.append(f"[{status}] {row['Name']}({t}) | 推荐价: ${buy_price} -> 现价: ${cur_price} | 浮动盈亏: {profit_pct}%")
        elif status == 'Dropped':
            exit_price = row.get('Exit_Price', buy_price)
            cur_price = current_prices.get(t, exit_price)
            # 计算如果没抛弃，现在会亏/赚多少，以验证风控有效性
            prevented_loss = round((exit_price - cur_price) / exit_price * 100, 2)
            stats_lines.append(f"[{status}] {row['Name']}({t}) | 抛弃价: ${exit_price} -> 现价(事后): ${cur_price} | 成功规避后续回撤: {prevented_loss}%")

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
        
    df = pd.read_csv(HISTORY_FILE)

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
    
    # 使用 Flash 模型进行快速的 HTML 标签检查与结构压缩
    print(f"正在调用 {REVIEW_MODEL_FLASH} 引擎进行报告格式化校验...")
    
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
