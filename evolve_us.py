# -*- coding: utf-8 -*-
import pandas as pd
import datetime
import os
import smtplib
import anthropic
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

print("🧬 启动美股 scan.py 自动进化引擎...")

def get_bj_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

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
    cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
    recent = df[df['Date'] >= cutoff].copy()
    if len(recent) < 10:
        print("⚠️ 样本不足10条，跳过进化。")
        exit(0)
except Exception as e:
    print(f"⚠️ 账本读取失败: {e}")
    exit(1)

# 美股用 Bias 近似判断方向（Bias>0 且后来涨了算赢）
# 更准确的是看 Hold_Period 内的表现，这里用 Bias 作为替代指标
core_dragon = recent[recent['Tag'] == 'Core_Dragon']
observation = recent[recent['Tag'] == 'Observation']
trap = recent[recent['Tag'] == 'Trap_Warning']

stats = {}
for tag in ['Core_Dragon', 'Observation', 'Trap_Warning']:
    group = recent[recent['Tag'] == tag]
    if len(group) > 0:
        avg_bias = round(group['Bias'].mean(), 2) if 'Bias' in group.columns else 0
        avg_rsi = round(group['RSI'].mean(), 2) if 'RSI' in group.columns else 0
        avg_score = round(group['Score'].mean(), 2) if 'Score' in group.columns else 0
        stats[tag] = {
            "总数": len(group),
            "平均评分": avg_score,
            "平均RSI": avg_rsi,
            "平均乖离率": avg_bias
        }

# 用 Core_Dragon 的平均评分判断系统是否健康
core_avg_score = stats.get('Core_Dragon', {}).get('平均评分', 0)
print(f"📊 近30天统计: {stats}")
print(f"📊 Core_Dragon 平均评分: {core_avg_score}")

EVOLVE_THRESHOLD = 30  # 评分低于30分触发进化

if core_avg_score >= EVOLVE_THRESHOLD:
    print(f"✅ 平均评分 {core_avg_score} 达标，本周无需进化。")
    exit(0)

print(f"⚠️ 平均评分 {core_avg_score} 低于 {EVOLVE_THRESHOLD}，触发进化引擎...")

# ==========================================
# 2. 读取当前 scan.py
# ==========================================
try:
    with open("scan.py", "r", encoding="utf-8") as f:
        current_scan_code = f.read()
except Exception as e:
    print(f"⚠️ 读取 scan.py 失败: {e}")
    exit(1)

# ==========================================
# 3. Claude 生成改进方案
# ==========================================
client = anthropic.Anthropic(
    api_key=os.environ.get("CLAWSOCKET_API_KEY"),
    base_url=os.environ.get("CLAWSOCKET_BASE_URL")
)

prompt = f"""
你是一个美股量化策略优化专家。以下是当前系统的表现数据和代码。

【近30天表现统计】：
各标签细分：{stats}
Core_Dragon平均评分：{core_avg_score}（目标>30分）
近期20条样本：
{recent.tail(20).to_string()}

【当前 scan.py 代码】：
{current_scan_code}

【任务】：
分析评分偏低的原因，调整参数或评分逻辑，输出改进后的完整代码。
可以调整：RSI阈值、乖离率门槛、MACD权重、评分公式各项权重等。
不要改变代码结构、API调用方式、邮件和入库逻辑。

【严格按以下格式输出】：

===REPORT_START===
<div style="background:#e8f5e9; border-left:6px solid #388e3c; padding:20px; border-radius:8px; margin-bottom:20px;">
<h3 style="color:#1b5e20; margin-top:0;">🔬 评分诊断</h3>
<p>(说明评分偏低的核心原因)</p>
</div>
<div style="background:#e3f2fd; border-left:6px solid #1976d2; padding:20px; border-radius:8px;">
<h3 style="color:#0d47a1; margin-top:0;">🔧 本次改进内容</h3>
<ul>
<li>(改动1)</li>
<li>(改动2)</li>
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
# 4. 解析报告和代码
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
# 5. 备份旧版本，自动覆盖 scan.py
# ==========================================
try:
    backup_name = f"scan_backup_us_{datetime.datetime.now().strftime('%Y%m%d')}.py"
    with open(backup_name, "w", encoding="utf-8") as f:
        f.write(current_scan_code)
    print(f"✅ 旧版本已备份至 {backup_name}")

    with open("scan.py", "w", encoding="utf-8") as f:
        f.write(f"# 🧬 美股自动进化版本 | 时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | 触发评分: {core_avg_score}\n\n")
        f.write(new_code)
    print("✅ scan.py 已自动更新！")
except Exception as e:
    print(f"❌ 文件写入失败: {e}")
    exit(1)

# ==========================================
# 6. 发邮件通知
# ==========================================
def send_evolve_mail(report_html, score, backup_name):
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
        <p>如需回滚，把备份文件内容复制回 scan.py 即可。</p>
    </div>
    """

    style = "<style>body{font-family:sans-serif;background:#f4f6f9;color:#333;padding:20px;line-height:1.6}.container{max-width:900px;margin:0 auto;background:#fff;padding:30px;border-radius:10px;}</style>"

    full_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head>
    <body><div class='container'>
    <h1 style='color:#1a237e;text-align:center;'>🧬 美股 scan.py 已自动进化</h1>
    <p style='text-align:center;color:#666;'>Core_Dragon 平均评分 <b style='color:#d32f2f;'>{score}</b>，系统已自动优化</p>
    {notice}
    <hr>
    <h2>📊 本次改进报告</h2>
    {report_html}
    </div></body></html>"""

    msg = MIMEMultipart()
    msg['From'] = user
    msg['Subject'] = f"🧬【美股自动进化完成】scan.py 已更新 ({datetime.datetime.now().strftime('%Y-%m-%d')})"
    msg.attach(MIMEText(full_html, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.sendmail(user, targets, msg.as_string())
            print("✅ 进化通知邮件已发送！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

send_evolve_mail(report_html, core_avg_score, backup_name)
