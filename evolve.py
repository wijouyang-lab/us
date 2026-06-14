# -*- coding: utf-8 -*-
import pandas as pd
import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

print("启动美股 scan.py 自动进化引擎...")

def get_now_str():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

def get_today_str():
    return datetime.datetime.now().strftime('%Y-%m-%d')

review_log = "review_history.csv"
if not os.path.exists(review_log):
    print("⚠️ 复盘账本不存在，跳过进化。需要先积累复盘数据。")
    exit(0)

try:
    df = pd.read_csv(review_log, on_bad_lines='skip')
    df['Review_Date'] = pd.to_datetime(df['Review_Date'])
    cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
    recent = df[df['Review_Date'] >= cutoff].copy()
    if len(recent) < 10:
        print(f"⚠️ 近30天复盘样本只有 {len(recent)} 条，不足10条，跳过进化。")
        exit(0)
except Exception as e:
    print(f"⚠️ 复盘账本读取失败: {e}")
    exit(1)

# 只统计真正执行买卖的标签，排除观望的 Observation
overall_win_rate = 0
if 'PnL_Pct' in recent.columns:
    recent['PnL_Pct'] = pd.to_numeric(recent['PnL_Pct'], errors='coerce')
    valid = recent[
        recent['PnL_Pct'].notna() &
        recent['Tag'].isin(['Core_Dragon'])
    ].copy()
    if len(valid) > 0:
        overall_win_rate = round((valid['PnL_Pct'] > 0).sum() / len(valid) * 100, 1)

stats = {}
for tag in ['Core_Dragon']:
    group = recent[recent['Tag'] == tag].copy()
    group['PnL_Pct'] = pd.to_numeric(group['PnL_Pct'], errors='coerce')
    valid_group = group.dropna(subset=['PnL_Pct'])
    if len(valid_group) > 0:
        win = (valid_group['PnL_Pct'] > 0).sum()
        stats[tag] = {
            "总数": len(valid_group),
            "胜率": round(win / len(valid_group) * 100, 1),
            "平均盈亏": round(valid_group['PnL_Pct'].mean(), 2),
            "平均持仓天数": round(pd.to_numeric(valid_group['Days_Held'], errors='coerce').mean(), 1)
        }

print(f"📊 近30天真实胜率: {overall_win_rate}% | 各标签: {stats}")

EVOLVE_THRESHOLD = 60
if overall_win_rate >= EVOLVE_THRESHOLD:
    print(f"✅ 胜率 {overall_win_rate}% 达标，本周无需进化。")
    exit(0)

print(f"⚠️ 胜率 {overall_win_rate}% 低于 {EVOLVE_THRESHOLD}%，触发进化引擎...")

try:
    with open("scan.py", "r", encoding="utf-8") as f:
        current_scan_code = f.read()
except Exception as e:
    print(f"⚠️ 读取 scan.py 失败: {e}")
    exit(1)

client = anthropic.Anthropic(
    api_key=os.environ.get("CLAWSOCKET_API_KEY"),
    base_url=os.environ.get("CLAWSOCKET_BASE_URL")
)

prompt = f"""
你是一个美股量化策略优化专家。以下是当前系统的真实持仓盈亏数据和代码。

【近30天真实持仓表现】：
整体胜率：{overall_win_rate}%（目标>60%）
各标签细分：{stats}
近期20条复盘样本：
{recent.tail(20).to_string()}

【当前 scan.py 代码】：
{current_scan_code}

【任务】：
基于真实持仓盈亏数据分析胜率低的原因，调整参数或逻辑，输出改进后的完整代码。
可以调整：RSI阈值、乖离率门槛、MACD权重、评分公式、筛选条件等。
不要改变代码的整体结构、API调用方式、邮件发送逻辑、入库逻辑。

【严格按以下格式输出，不要加任何其他内容】：

===REPORT_START===
<div style="background:#e8f5e9; border-left:6px solid #388e3c; padding:20px; border-radius:8px; margin-bottom:20px;">
<h3 style="color:#1b5e20; margin-top:0;">🔬 胜率诊断</h3>
<p>(基于真实盈亏数据说明胜率低的核心原因)</p>
</div>
<div style="background:#e3f2fd; border-left:6px solid #1976d2; padding:20px; border-radius:8px;">
<h3 style="color:#0d47a1; margin-top:0;">🔧 本次改进内容</h3>
<ul>
<li>(改动1：具体参数变化)</li>
<li>(改动2：...)</li>
</ul>
</div>
===REPORT_END===

===CODE_START===
(完整的改进后 scan.py 代码)
===CODE_END===
"""

# 流式输出，避免524超时
raw_output = ""
with client.messages.stream(
    model="claude-fable-5",
    max_tokens=8000,
    temperature=0.2,
    messages=[{"role": "user", "content": prompt}]
) as stream:
    for text in stream.text_stream:
        raw_output += text

print("✅ Claude 进化方案生成完毕。")

report_html = ""
new_code = ""

try:
    if "===REPORT_START===" in raw_output and "===REPORT_END===" in raw_output:
        report_html = raw_output.split("===REPORT_START===")[1].split("===REPORT_END===")[0].strip()
    if "===CODE_START===" in raw_output and "===CODE_END===" in raw_output:
        new_code = raw_output.split("===CODE_START===")[1].split("===CODE_END===")[0].strip()
        new_code = new_code.replace("```python", "").replace("```", "").strip()
    if not new_code:
        print("⚠️ 未能提取到新代码，终止进化。")
        exit(1)
except Exception as e:
    print(f"⚠️ 解析失败: {e}")
    exit(1)

try:
    backup_name = f"scan_backup_us_{datetime.datetime.now().strftime('%Y%m%d')}.py"
    with open(backup_name, "w", encoding="utf-8") as f:
        f.write(current_scan_code)
    print(f"✅ 旧版本已备份至 {backup_name}")
    with open("scan.py", "w", encoding="utf-8") as f:
        f.write(f"# 美股自动进化版本 | 时间: {get_now_str()} | 触发胜率: {overall_win_rate}%\n\n")
        f.write(new_code)
    print("✅ scan.py 已自动更新！")
except Exception as e:
    print(f"❌ 文件写入失败: {e}")
    exit(1)

def send_evolve_mail(report_html, win_rate, backup_name):
    user = os.environ.get("EMAIL_ACCOUNT")
    pwd = os.environ.get("EMAIL_PASSWORD")
    if not user or not pwd:
        return

    notice = f"""
    <div style="background:#fff3e0; border-left:6px solid #ff9800; padding:20px; margin:20px 0; border-radius:8px;">
        <h3 style="color:#e65100; margin-top:0;">已自动覆盖 scan.py</h3>
        <p>旧版本已备份为 <b>{backup_name}</b>，可在 GitHub 仓库找到。</p>
        <p>如果发现新版本有问题，把备份文件内容复制回 scan.py 即可回滚。</p>
    </div>
    """
    style = "<style>body{font-family:sans-serif;background:#f4f6f9;color:#333;padding:20px;line-height:1.6}.container{max-width:900px;margin:0 auto;background:#fff;padding:30px;border-radius:10px;}</style>"
    full_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head>
    <body><div class='container'>
    <h1 style='color:#1a237e;text-align:center;'>美股 scan.py 已自动进化</h1>
    <p style='text-align:center;color:#666;'>近30天真实胜率 <b style='color:#d32f2f;'>{win_rate}%</b>，系统已自动优化</p>
    {notice}
    <hr>
    <h2>本次改进报告</h2>
    {report_html}
    </div></body></html>"""

    msg = MIMEMultipart()
    msg['From'] = user
    msg['To'] = user
    msg['Subject'] = f"【美股自动进化完成】scan.py 已更新 ({get_today_str()})"
    msg.attach(MIMEText(full_html, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.sendmail(user, [user], msg.as_string())
            print("✅ 进化通知邮件已发送至本人！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

send_evolve_mail(report_html, overall_win_rate, backup_name)
