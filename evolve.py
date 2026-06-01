# -*- coding: utf-8 -*-
import pandas as pd
import datetime
import os
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

print("🧬 启动 scan.py 自动进化引擎...")

BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))
def get_bj_time():
    return datetime.datetime.now(BEIJING_TZ)

# ==========================================
# 1. 读取账本，计算胜率
# ==========================================
log_file = "trade_history.csv"
if not os.path.exists(log_file):
    print("⚠️ 账本不存在，跳过进化。")
    exit(0)

try:
    df = pd.read_csv(log_file)
    df['Date'] = pd.to_datetime(df['Date'])
    cutoff = get_bj_time() - datetime.timedelta(days=30)
    recent = df[df['Date'] >= cutoff.replace(tzinfo=None)].copy()
    if len(recent) < 10:
        print("⚠️ 样本不足10条，数据太少跳过进化。")
        exit(0)
except Exception as e:
    print(f"⚠️ 账本读取失败: {e}")
    exit(1)

# 计算整体胜率
overall_win_rate = 0
if 'Daily_Pct' in recent.columns:
    overall_win_rate = round((recent['Daily_Pct'] > 0).sum() / len(recent) * 100, 1)

# 各标签细分统计
stats = {}
for tag in recent['Tag'].unique():
    group = recent[recent['Tag'] == tag]
    if 'Daily_Pct' in group.columns:
        win = (group['Daily_Pct'] > 0).sum()
        total = len(group)
        stats[tag] = {
            "总数": total,
            "胜率": round(win / total * 100, 1) if total > 0 else 0,
            "平均涨跌幅": round(group['Daily_Pct'].mean(), 2)
        }

print(f"📊 近30天整体胜率: {overall_win_rate}% | 各标签: {stats}")

# ==========================================
# 2. 判断是否需要进化（胜率低于55%才触发）
# ==========================================
EVOLVE_THRESHOLD = 55

if overall_win_rate >= EVOLVE_THRESHOLD:
    print(f"✅ 胜率 {overall_win_rate}% 达标，本周无需进化。")
    exit(0)

print(f"⚠️ 胜率 {overall_win_rate}% 低于 {EVOLVE_THRESHOLD}%，触发进化引擎...")

# ==========================================
# 3. 读取当前 scan.py
# ==========================================
try:
    with open("scan.py", "r", encoding="utf-8") as f:
        current_scan_code = f.read()
except Exception as e:
    print(f"⚠️ 读取 scan.py 失败: {e}")
    exit(1)

# ==========================================
# 4. Claude 生成改进方案
# ==========================================
client = anthropic.Anthropic(
    api_key=os.environ.get("CLAWSOCKET_API_KEY"),
    base_url=os.environ.get("CLAWSOCKET_BASE_URL")
)

prompt = f"""
你是一个量化策略优化专家。以下是当前量化选股系统的表现数据和代码。

【近30天表现】：
整体胜率：{overall_win_rate}%（目标>55%）
各标签细分：{stats}
近期20条样本：
{recent.tail(20).to_string()}

【当前 scan.py 代码】：
{current_scan_code}

【任务】：
分析胜率低的原因，调整参数或逻辑，输出改进后的完整代码。
可以调整的方向包括：RSI阈值、乖离率门槛、MACD权重、评分公式、筛选条件等。
不要改变代码的整体结构、API调用方式、邮件发送逻辑。

【严格按以下格式输出，不要加任何其他内容】：

===REPORT_START===
<div style="background:#e8f5e9; border-left:6px solid #388e3c; padding:20px; border-radius:8px; margin-bottom:20px;">
<h3 style="color:#1b5e20; margin-top:0;">🔬 胜率诊断</h3>
<p>(说明胜率低的核心原因)</p>
</div>
<div style="background:#e3f2fd; border-left:6px solid #1976d2; padding:20px; border-radius:8px;">
<h3 style="color:#0d47a1; margin-top:0;">🔧 本次改进内容</h3>
<ul>
<li>(改动1：比如把RSI阈值从40-70调整为45-65)</li>
<li>(改动2：...)</li>
</ul>
</div>
===REPORT_END===

===CODE_START===
(完整的改进后 scan.py 代码)
===CODE_END===
"""

try:
    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8000,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )
    raw_output = message.content[0].text
    print("✅ Claude 进化方案生成完毕。")
except Exception as e:
    print(f"❌ Claude 调用失败: {e}")
    exit(1)

# ==========================================
# 5. 解析报告和代码
# ==========================================
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

# ==========================================
# 6. 备份旧版本，写入新代码，自动覆盖
# ==========================================
try:
    # 先备份旧的 scan.py
    backup_name = f"scan_backup_{get_bj_time().strftime('%Y%m%d')}.py"
    with open(backup_name, "w", encoding="utf-8") as f:
        f.write(current_scan_code)
    print(f"✅ 旧版本已备份至 {backup_name}")

    # 写入新的 scan.py
    with open("scan.py", "w", encoding="utf-8") as f:
        f.write(f"# 🧬 自动进化版本 | 时间: {get_bj_time().strftime('%Y-%m-%d %H:%M')} | 触发胜率: {overall_win_rate}%\n\n")
        f.write(new_code)
    print("✅ scan.py 已自动更新！")

except Exception as e:
    print(f"❌ 文件写入失败: {e}")
    exit(1)

# ==========================================
# 7. 发邮件通知你已自动更新
# ==========================================
def send_evolve_mail(report_html, win_rate, backup_name):
    user = os.environ.get("EMAIL_ACCOUNT")
    pwd = os.environ.get("EMAIL_PASSWORD")
    targets_str = os.environ.get("TARGET_EMAILS")
    if not user or not targets_str:
        return

    targets = [e.strip() for e in targets_str.split(",")]

    notice = f"""
    <div style="background:#fff3e0; border-left:6px solid #ff9800; padding:20px; margin:20px 0; border-radius:8px;">
        <h3 style="color:#e65100; margin-top:0;">⚡ 已自动覆盖 scan.py</h3>
        <p>旧版本已备份为 <b>{backup_name}</b>，可在 GitHub 仓库找到。</p>
        <p>如果发现新版本有问题，去仓库把 <b>{backup_name}</b> 的内容复制回 scan.py 即可回滚。</p>
    </div>
    """

    style = "<style>body{font-family:sans-serif;background:#f4f6f9;color:#333;padding:20px;line-height:1.6}.container{max-width:900px;margin:0 auto;background:#fff;padding:30px;border-radius:10px;}</style>"

    full_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head>
    <body><div class='container'>
    <h1 style='color:#d32f2f;text-align:center;'>🧬 scan.py 已自动进化</h1>
    <p style='text-align:center;color:#666;'>近30天胜率 <b style='color:#d32f2f;'>{win_rate}%</b>，系统已自动优化并覆盖代码</p>
    {notice}
    <hr>
    <h2>📊 本次改进报告</h2>
    {report_html}
    </div></body></html>"""

    msg = MIMEMultipart()
    msg['From'] = user
    msg['Subject'] = f"🧬【自动进化完成】scan.py 已更新 ({get_bj_time().strftime('%Y-%m-%d')})"
    msg.attach(MIMEText(full_html, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.sendmail(user, targets, msg.as_string())
            print("✅ 进化通知邮件已发送！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

send_evolve_mail(report_html, overall_win_rate, backup_name)
