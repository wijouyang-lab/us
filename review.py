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
    
    stats_lines = []
    for idx, row in df.iterrows():
        t = row['Ticker']
        status = str(row.get('Status', 'Active')).strip()

        try:
            buy_price = float(row['Price'])
            if buy_price <= 0:
                continue
        except (ValueError, TypeError):
            continue

        cur_price = current_prices.get(t, buy_price)

        if status == 'Active':
            profit_pct = round((cur_price - buy_price) / buy_price * 100, 2)
            stats_lines.append(f"[Active] {row['Name']}({t}) | 买入价: ${buy_price} → 现价: ${cur_price} | 浮动盈亏: {profit_pct}%")
        elif status in ('Dropped', 'Stop_Loss_Hit', 'Period_Matured', 'Forced_Exit'):
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
                f"[{label}] {row['Name']}({t}) | 买入: ${buy_price} → 清仓: ${exit_price} | 实现盈亏: {pnl_pct}% | 清仓后继续变化: {prevented}%"
            )

    report_data = "\n".join(stats_lines)

    MAX_REPORT_CHARS = 16000
    if len(report_data) > MAX_REPORT_CHARS:
        report_data = report_data[:MAX_REPORT_CHARS]
        last_newline = report_data.rfind('\n')
        if last_newline > 0:
            report_data = report_data[:last_newline]
        report_data += f"\n... （已截断，完整数据见 trade_history.csv）"

    prompt = f"""
你是首席定量分析师，请根据最新交易记录，进行本期操作的回顾与复盘。
要求：
1. 宏观与资产全景复盘：分析 Active 持仓的整体胜率、多头极化优势（大牛股撑起收益）与下行风控问题。
2. 给出后续量化交易改进建议（不超过3条，要具体可执行，包含具体交易纪律）。
输出格式要求直接为精美的 HTML 片段（无 markdown 外框，无需 `<html>` 或 `<body>` 标签），控制在1000字以内。
严格按照以下 HTML 框架结构返回：

<div style="background: #eceff1; border-left: 6px solid #455a64; padding: 20px; margin-bottom: 25px; border-radius: 8px;">
    <h3 style="margin-top: 0; color: #263238;">⚖️ 宏观与资产全景复盘</h3>
    <p>(总结整体多头盈利贡献与下行波动的核心逻辑，语言专业深度)</p>
</div>

<div style="background: #fff; padding: 20px; margin-bottom: 25px; border-radius: 8px; border: 1px solid #e0e0e0;">
    <h3 style="margin: 0 0 10px 0; color: #2c3e50;">💡 量化策略改进建议</h3>
    <ul style="padding-left: 20px; margin: 0;">
        (给出不超过3条的具体可执行策略，每一条用 <li> 标出，附带量化论据)
    </ul>
</div>

【持仓与风控拦截数据】：
{report_data}
"""

    import time as _time
    last_err = None
    for attempt in range(3):
        try:
            tokens = [2000, 1500, 1000][attempt]
            response = client.messages.create(
                model=REVIEW_MODEL_PRO,
                max_tokens=tokens,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            last_err = e
            wait = 2 ** attempt * 5
            print(f"⚠️ API调用失败（第{attempt+1}次），{wait}秒后重试: {type(e).__name__}: {str(e)[:120]}")
            _time.sleep(wait)

    print(f"❌ AI复盘API三次调用均失败，使用降级文字报告。最后错误: {last_err}")
    active_count = sum(1 for l in stats_lines if l.startswith('[Active]'))
    closed_count = len(stats_lines) - active_count
    return f"""
<div style="background:#fff3e0;border-left:4px solid #ff9800;padding:15px;border-radius:6px;">
    <h3>⚠️ AI复盘引擎暂时不可用（API超时）</h3>
    <p>当前持仓 <b>{active_count}</b> 只 | 已清仓记录 <b>{closed_count}</b> 条</p>
    <p>原始数据已保存在 trade_history.csv。</p>
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
    
    # ── 1. 核心数据程序化统计 ──
    active_rows = []
    closed_rows = []
    
    for idx, row in df.iterrows():
        t = row['Ticker']
        status = str(row.get('Status', 'Active')).strip()
        
        try:
            buy_price = float(row['Price'])
            if buy_price <= 0:
                continue
        except (ValueError, TypeError):
            continue
            
        cur_price = prices.get(t, buy_price)
        name = row.get('Name', t)
        tag_val = row.get('Tag', '') or row.get('Score', '')
        
        if status == 'Active':
            profit_pct = round((cur_price - buy_price) / buy_price * 100, 2)
            active_rows.append({
                'ticker': t, 'name': name, 'buy_price': buy_price, 'cur_price': cur_price,
                'pnl': profit_pct, 'tag': tag_val
            })
        elif status in ('Dropped', 'Stop_Loss_Hit', 'Period_Matured', 'Forced_Exit'):
            try:
                exit_price = float(row.get('Exit_Price', buy_price))
                if exit_price <= 0:
                    exit_price = buy_price
            except (ValueError, TypeError):
                exit_price = buy_price
                
            pnl_pct = round((exit_price - buy_price) / buy_price * 100, 2)
            post_exit_price = prices.get(t, exit_price)
            # 清仓后继续变化：清仓价 vs 现价 (若继续下跌，证明风控极度有效，防守成功)
            prevented = round((exit_price - post_exit_price) / exit_price * 100, 2) if exit_price > 0 else 0.0
            
            closed_rows.append({
                'ticker': t, 'name': name, 'buy_price': buy_price, 'exit_price': exit_price,
                'pnl': pnl_pct, 'prevented': prevented, 'cur_price': post_exit_price, 'status': status, 'tag': row.get('Tag', '')
            })

    # 计算指标
    active_count = len(active_rows)
    closed_count = len(closed_rows)
    total_count = active_count + closed_count
    
    active_wins = sum(1 for x in active_rows if x['pnl'] > 0)
    active_win_rate = (active_wins / active_count * 100) if active_count > 0 else 0.0
    
    closed_wins = sum(1 for x in closed_rows if x['pnl'] > 0)
    closed_win_rate = (closed_wins / closed_count * 100) if closed_count > 0 else 0.0
    
    # 风控有效性定义：清仓后继续下跌或微幅反弹 (跌幅 >= -2%)
    effective_risk = sum(1 for x in closed_rows if x['prevented'] >= -2.0)
    risk_rate = (effective_risk / closed_count * 100) if closed_count > 0 else 0.0
    
    # 极端赢家、其余赢家与亏损平均计算
    super_threshold = 50.0
    all_trades = active_rows + [{'pnl': x['pnl']} for x in closed_rows]
    super_winners = [x for x in all_trades if x['pnl'] >= super_threshold]
    super_winner_contribution = sum(x['pnl'] for x in super_winners)
    
    other_winners = [x for x in all_trades if 0.0 < x['pnl'] < super_threshold]
    other_winner_avg = (sum(x['pnl'] for x in other_winners) / len(other_winners)) if other_winners else 0.0
    
    losers = [x for x in all_trades if x['pnl'] < 0.0]
    loser_avg = (sum(x['pnl'] for x in losers) / len(losers)) if losers else 0.0

    # ── 2. 生成精美 KPI 统计卡片层 ──
    kpi_html = f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 20px;">
        <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #3498db;">
            <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">📊 总操作笔数</div>
            <div style="font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 5px;">{total_count}</div>
            <div style="font-size: 12px; color: #95a5a6;">活跃持仓 {active_count} 笔 · 已清仓 {closed_count} 笔</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #2ecc71;">
            <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">📈 活跃持仓胜率</div>
            <div style="font-size: 24px; font-weight: bold; color: #2ecc71; margin-bottom: 5px;">{active_win_rate:.2f}%</div>
            <div style="font-size: 12px; color: #95a5a6;">{active_wins} 赢 / {active_count - active_wins} 亏</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #e67e22;">
            <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">📉 已清仓实现胜率</div>
            <div style="font-size: 24px; font-weight: bold; color: #e67e22; margin-bottom: 5px;">{closed_win_rate:.2f}%</div>
            <div style="font-size: 12px; color: #95a5a6;">{closed_wins} 赢 / {closed_count - closed_wins} 亏</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #95a5a6;">
            <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">🛡️ 风控拦截率</div>
            <div style="font-size: 24px; font-weight: bold; color: #95a5a6; margin-bottom: 5px;">{risk_rate:.2f}%</div>
            <div style="font-size: 12px; color: #95a5a6;">{effective_risk}/{closed_count} 次斩仓后继续下跌或避险成功</div>
        </div>
    </div>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 25px;">
        <div style="background: #ffffff; border: 1px solid #eef2f5; border-radius: 10px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 4px solid #9b59b6;">
            <div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">🏆 极端赢家贡献</div>
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

    # ── 3. 活跃标的与已清仓明细表渲染 ──
    def get_eval_badge(pnl, is_active=True, status=""):
        if is_active:
            if pnl >= 50.0:
                return '<span style="background: #e8f8f5; color: #117a65; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">超级赢家</span>'
            elif pnl >= 20.0:
                return '<span style="background: #ebf5fb; color: #2980b9; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">丰厚收益</span>'
            elif pnl >= 5.0:
                return '<span style="background: #fef9e7; color: #b7950b; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">稳健盈利</span>'
            elif pnl > 0.0:
                return '<span style="background: #f4f6f7; color: #7f8c8d; padding: 2px 8px; border-radius: 12px; font-size: 12px;">小幅盈利</span>'
            elif pnl <= -15.0:
                return '<span style="background: #fdedec; color: #c0392b; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">高危标的</span>'
            elif pnl <= -5.0:
                return '<span style="background: #fdf2e9; color: #d35400; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">中危标的</span>'
            else:
                return '<span style="background: #f4f6f7; color: #7f8c8d; padding: 2px 8px; border-radius: 12px; font-size: 12px;">低危波动</span>'
        else:
            if pnl > 0:
                return '<span style="background: #e8f8f5; color: #117a65; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">盈利离场</span>'
            else:
                label_map = {'Dropped': '宏观强清', 'Stop_Loss_Hit': '触发止损', 'Period_Matured': '到期清仓', 'Forced_Exit': '突发强清'}
                lbl = label_map.get(status, '已清仓')
                return f'<span style="background: #fdedec; color: #c0392b; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">{lbl}</span>'
                
    def get_risk_control_badge(prevented):
        if prevented >= 5.0:
            return '<span style="background: #e8f8f5; color: #117a65; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">避险逃顶</span>'
        elif prevented >= 0.0:
            return '<span style="background: #ebf5fb; color: #2980b9; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">风控有效</span>'
        elif prevented >= -5.0:
            return '<span style="background: #fef9e7; color: #b7950b; padding: 2px 8px; border-radius: 12px; font-size: 12px;">微幅反弹</span>'
        else:
            return '<span style="background: #fdedec; color: #c0392b; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">过早割肉</span>'

    active_winners = sorted([x for x in active_rows if x['pnl'] > 0], key=lambda x: x['pnl'], reverse=True)
    active_losers = sorted([x for x in active_rows if x['pnl'] <= 0], key=lambda x: x['pnl'])

    winners_tbody = ""
    for w in active_winners:
        badge = get_eval_badge(w['pnl'])
        tag_str = f" | {w['tag']}" if w['tag'] else ""
        winners_tbody += f"""
        <tr style="border-bottom: 1px solid #f1f2f6;">
            <td style="padding: 12px; font-weight: bold; color: #2c3e50;">{w['ticker']}</td>
            <td style="padding: 12px; color: #34495e;">{w['name']}</td>
            <td style="padding: 12px; color: #7f8c8d;">${w['buy_price']:.2f}</td>
            <td style="padding: 12px; color: #2c3e50;">${w['cur_price']:.2f}</td>
            <td style="padding: 12px; font-weight: bold; color: #2ecc71;">+{w['pnl']:.2f}%</td>
            <td style="padding: 12px;">{badge}{tag_str}</td>
        </tr>
        """
        
    losers_tbody = ""
    for l in active_losers:
        badge = get_eval_badge(l['pnl'])
        tag_str = f" | {l['tag']}" if l['tag'] else ""
        losers_tbody += f"""
        <tr style="border-bottom: 1px solid #f1f2f6;">
            <td style="padding: 12px; font-weight: bold; color: #2c3e50;">{l['ticker']}</td>
            <td style="padding: 12px; color: #34495e;">{l['name']}</td>
            <td style="padding: 12px; color: #7f8c8d;">${l['buy_price']:.2f}</td>
            <td style="padding: 12px; color: #2c3e50;">${l['cur_price']:.2f}</td>
            <td style="padding: 12px; font-weight: bold; color: #e74c3c;">{l['pnl']:.2f}%</td>
            <td style="padding: 12px;">{badge}{tag_str}</td>
        </tr>
        """
        
    closed_tbody = ""
    for c in sorted(closed_rows, key=lambda x: x['pnl'], reverse=True)[:30]:
        badge = get_eval_badge(c['pnl'], is_active=False, status=c['status'])
        rc_badge = get_risk_control_badge(c['prevented'])
        pnl_color = "#2ecc71" if c['pnl'] > 0 else "#e74c3c"
        pnl_prefix = "+" if c['pnl'] > 0 else ""
        prev_color = "#2ecc71" if c['prevented'] >= 0 else "#e74c3c"
        prev_prefix = "+" if c['prevented'] > 0 else ""
        closed_tbody += f"""
        <tr style="border-bottom: 1px solid #f1f2f6;">
            <td style="padding: 10px; font-weight: bold; color: #2c3e50;">{c['ticker']}</td>
            <td style="padding: 10px; color: #34495e;">{c['name']}</td>
            <td style="padding: 10px; color: #7f8c8d;">${c['buy_price']:.2f}</td>
            <td style="padding: 10px; color: #2c3e50;">${c['exit_price']:.2f}</td>
            <td style="padding: 10px; font-weight: bold; color: {pnl_color};">{pnl_prefix}{c['pnl']:.2f}%</td>
            <td style="padding: 10px; font-weight: bold; color: {prev_color};">{prev_prefix}{c['prevented']:.2f}%</td>
            <td style="padding: 10px;">{badge} {rc_badge}</td>
        </tr>
        """

    active_winners_table = f"""
    <div style="background: #ffffff; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); margin-bottom: 25px; border: 1px solid #eef2f5;">
        <h3 style="color: #2c3e50; margin-top: 0; margin-bottom: 15px; border-bottom: 2px solid #2ecc71; padding-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <span>🟢 活跃持仓 - 盈利标的 ({len(active_winners)} 只)</span>
            <span style="font-size: 14px; color: #7f8c8d; font-weight: normal;">多头极化优势分析</span>
        </h3>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                <thead>
                    <tr style="background: #f8f9fa; border-bottom: 2px solid #eef2f5;">
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">股票代码</th>
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">股票名称</th>
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">买入价</th>
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">现价</th>
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">浮动盈亏</th>
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">评估标签</th>
                    </tr>
                </thead>
                <tbody>
                    {winners_tbody if winners_tbody else '<tr><td colspan="6" style="padding: 20px; text-align: center; color: #7f8c8d;">暂无盈利标的</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """
    
    active_losers_table = f"""
    <div style="background: #ffffff; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); margin-bottom: 25px; border: 1px solid #eef2f5;">
        <h3 style="color: #2c3e50; margin-top: 0; margin-bottom: 15px; border-bottom: 2px solid #e74c3c; padding-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <span>🔴 活跃持仓 - 亏损标的 ({len(active_losers)} 只)</span>
            <span style="font-size: 14px; color: #7f8c8d; font-weight: normal;">下行风险监测</span>
        </h3>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                <thead>
                    <tr style="background: #f8f9fa; border-bottom: 2px solid #eef2f5;">
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">股票代码</th>
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">股票名称</th>
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">买入价</th>
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">现价</th>
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">浮动盈亏</th>
                        <th style="padding: 12px; color: #34495e; font-weight: bold;">风险级别</th>
                    </tr>
                </thead>
                <tbody>
                    {losers_tbody if losers_tbody else '<tr><td colspan="6" style="padding: 20px; text-align: center; color: #7f8c8d;">暂无亏损标的</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """
    
    closed_table = f"""
    <div style="background: #ffffff; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); margin-bottom: 25px; border: 1px solid #eef2f5;">
        <h3 style="color: #2c3e50; margin-top: 0; margin-bottom: 15px; border-bottom: 2px solid #95a5a6; padding-bottom: 8px;">
            📁 已清仓交易风控校验明细 (最近30条记录)
        </h3>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
                <thead>
                    <tr style="background: #f8f9fa; border-bottom: 2px solid #eef2f5;">
                        <th style="padding: 10px; color: #34495e; font-weight: bold;">代码</th>
                        <th style="padding: 10px; color: #34495e; font-weight: bold;">名称</th>
                        <th style="padding: 10px; color: #34495e; font-weight: bold;">买入价</th>
                        <th style="padding: 10px; color: #34495e; font-weight: bold;">清仓价</th>
                        <th style="padding: 10px; color: #34495e; font-weight: bold;">实现盈亏</th>
                        <th style="padding: 10px; color: #34495e; font-weight: bold;">离场后变动%</th>
                        <th style="padding: 10px; color: #34495e; font-weight: bold;">风控评定</th>
                    </tr>
                </thead>
                <tbody>
                    {closed_tbody if closed_tbody else '<tr><td colspan="7" style="padding: 20px; text-align: center; color: #7f8c8d;">暂无已清仓历史明细</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """

    report_html = generate_review_report(df, prices)
    
    full_html = f"""
    <!DOCTYPE html><html><head><meta charset='utf-8'>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f4f6f8; padding: 20px; color: #333; }}
        .card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); max-width: 1200px; margin: 0 auto; }}
    </style></head>
    <body>
        <div class='card'>
            <h2 style='color: #2c3e50; margin-top: 0; margin-bottom: 20px; font-size: 26px; border-bottom: 3px solid #3498db; padding-bottom: 10px;'>
                📊 资产全景复盘报告 (美股)
            </h2>
            {kpi_html}
            
            {report_html}
            
            {active_winners_table}
            
            {active_losers_table}
            
            {closed_table}
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
