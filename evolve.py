# -*- coding: utf-8 -*-
import pandas as pd
import datetime
import os
import ast
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

print("启动美股 scan.py 自动进化引擎（版本公平评估）...")

def get_now_str():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

def get_today_str():
    return datetime.datetime.now().strftime('%Y-%m-%d')


def get_version_start_date():
    """
    读取 scan_version.txt，获取当前 scan.py 版本的生效起始日期。
    找不到标记文件时保守按"今天"计算，这样在没有可靠版本信息时，
    evolve.py 会因为找不到当前版本产生的已完成交易样本而自动跳过本次进化。
    """
    version_file = "scan_version.txt"
    if not os.path.exists(version_file):
        print("⚠️ 未找到 scan_version.txt，无法确认当前版本起始日期，保守按今天计算。")
        return datetime.datetime.now()
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if "," in content:
            date_str = content.split(",")[1]
            return datetime.datetime.strptime(date_str, '%Y-%m-%d')
    except Exception as e:
        print(f"⚠️ 读取版本标记失败: {e}，保守按今天计算。")
    return datetime.datetime.now()


version_start_date = get_version_start_date()
print(f"📌 当前 scan.py 版本生效起始日期: {version_start_date.strftime('%Y-%m-%d')}")
print("📌 评估方法：只统计该日期之后首次推荐、且已到期归档的交易，持仓中的票不计入胜率")

review_log = "review_history.csv"
if not os.path.exists(review_log):
    print("⚠️ 复盘账本不存在，跳过进化。需要先积累复盘数据。")
    exit(0)

try:
    df = pd.read_csv(review_log, on_bad_lines='skip')
    df['Rec_Date'] = pd.to_datetime(df['Rec_Date'])
except Exception as e:
    print(f"⚠️ 复盘账本读取失败: {e}")
    exit(1)

# ==========================================
# 第一层过滤：只看"当前版本"产生的推荐
# ==========================================
current_version_picks = df[df['Rec_Date'] >= version_start_date].copy()

if current_version_picks.empty:
    print("⚠️ 当前版本下还没有任何推荐记录（可能刚切换版本不久），跳过进化。")
    exit(0)

distinct_tickers = current_version_picks['Ticker'].nunique()
print(f"📊 当前版本下共有 {distinct_tickers} 只不同标的产生过推荐记录")

# ==========================================
# 第二层过滤：只用"已超期归档"（真正走完一轮）的数据算胜率
# ==========================================
ALL_CORE_TAGS = ['Core_Dragon']

if 'Status' not in current_version_picks.columns:
    print("⚠️ review_history.csv 缺少 Status 列，无法区分持仓中/已到期，跳过进化。")
    exit(0)

matured = current_version_picks[
    (current_version_picks['Status'] == '已超期归档') &
    current_version_picks['Tag'].isin(ALL_CORE_TAGS)
].copy()
matured['PnL_Pct'] = pd.to_numeric(matured['PnL_Pct'], errors='coerce')
matured = matured.dropna(subset=['PnL_Pct'])

still_active = current_version_picks[
    (current_version_picks['Status'] == '持仓中') &
    current_version_picks['Tag'].isin(ALL_CORE_TAGS)
].copy()
still_active_tickers = still_active['Ticker'].nunique()

print(f"📊 已到期归档（计入胜率）: {len(matured)} 条 | 仍持仓中（不计入，仅作参考）: {still_active_tickers} 只标的")

MIN_MATURED_SAMPLES = 10
if len(matured) < MIN_MATURED_SAMPLES:
    print(f"⚠️ 当前版本下已完成交易（已超期归档）样本只有 {len(matured)} 条，不足 {MIN_MATURED_SAMPLES} 条。")
    print("⚠️ 可能是版本刚切换不久，多数持仓还在进行中，暂不评判，跳过本次进化。")
    exit(0)

overall_win_rate = round((matured['PnL_Pct'] > 0).sum() / len(matured) * 100, 1)

stats = {}
for tag in ALL_CORE_TAGS:
    group = matured[matured['Tag'] == tag]
    if len(group) > 0:
        win = (group['PnL_Pct'] > 0).sum()
        stats[tag] = {
            "总数": len(group),
            "胜率": round(win / len(group) * 100, 1),
            "平均盈亏": round(group['PnL_Pct'].mean(), 2),
            "平均持仓天数": round(pd.to_numeric(group['Days_Held'], errors='coerce').mean(), 1)
        }

score_stats = {}
if 'Score' in matured.columns:
    score_valid = matured.copy()
    score_valid['Score'] = pd.to_numeric(score_valid['Score'], errors='coerce')
    score_valid = score_valid.dropna(subset=['Score'])
    if len(score_valid) >= 5:
        def score_bucket(s):
            if s >= 80:
                return "80-100分(高信心)"
            elif s >= 60:
                return "60-79分(中信心)"
            else:
                return "60分以下(低信心)"
        score_valid['Bucket'] = score_valid['Score'].apply(score_bucket)
        for bucket, grp in score_valid.groupby('Bucket'):
            if len(grp) >= 2:
                win_rate = round((grp['PnL_Pct'] > 0).sum() / len(grp) * 100, 1)
                avg_pnl = round(grp['PnL_Pct'].mean(), 2)
                score_stats[bucket] = {"胜率": win_rate, "平均盈亏": avg_pnl, "样本数": len(grp)}

print(f"📊 当前版本真实胜率（仅已到期归档）: {overall_win_rate}% | 各标签: {stats}")
if score_stats:
    print(f"📊 评分区间胜率分布: {score_stats}")

EVOLVE_THRESHOLD = 60
if overall_win_rate >= EVOLVE_THRESHOLD:
    print(f"✅ 胜率 {overall_win_rate}% 达标，本次无需进化。")
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

loss_samples = matured[matured['PnL_Pct'] < 0].copy()
win_samples = matured[matured['PnL_Pct'] > 0].copy()

score_section = f"\n【推荐评分区间胜率分布（用于判断评分体系是否有真实预测力）】：\n{score_stats}\n" if score_stats else "\n【推荐评分区间胜率分布】：暂无足够样本\n"

prompt = f"""
你是一个美股量化策略优化专家。当前系统是【产业链逻辑驱动版】，核心逻辑是：
从宏观事件提炼产业链主线，找到二级受益标的，新闻面排雷，技术面只作为入场时机确认，对Top1-5给出1-100推荐评分，观察池覆盖Rank6-12。

【重要评估说明】：以下数据严格只包含本版本scan.py（自{version_start_date.strftime('%Y-%m-%d')}起生效）产生的、且已经持有到期满（已超期归档，真实结果已知）的交易，不包含仍在持仓中尚未到期的票，也不包含旧版本的历史数据，这样才能公平评判当前这一版策略的真实表现。

当前版本下还有 {still_active_tickers} 只标的仍在持仓中，尚未到期，暂不计入本次评估。

【当前版本真实持仓表现（仅已到期归档样本）】：
整体胜率：{overall_win_rate}%（目标>60%，样本数：{len(matured)}）
各标签细分：{stats}
{score_section}

【亏损样本（最近{len(loss_samples.tail(10))}条，均为已到期归档的真实结果）】：
{loss_samples.tail(10).to_string()}

【盈利样本（最近{len(win_samples.tail(10))}条，均为已到期归档的真实结果）】：
{win_samples.tail(10).to_string()}

【当前 scan.py 代码】：
{current_scan_code}

【任务】：
基于真实持仓盈亏数据分析胜率低的原因，调整参数或逻辑，输出改进后的完整代码。
重要约束：
1. 不要把选股逻辑退回纯技术指标驱动，产业链逻辑推演必须保留为第一步
2. 不要把核心展开分析的数量从 Top 5 改回 Top 3 或更少，详细分析的覆盖范围必须维持 Top 1-5
3. 不得删除1-100推荐评分机制，且评分提取格式必须严格保持为"评分:[XX]/100"，必须与正则表达式 r'评分\\s*[:：]\\s*\\[?(\\d{{1,3}})\\s*/\\s*100' 保持完全兼容
4. 不得删除scan.py顶部的版本标记机制（update_version_marker函数），这是evolve.py公平评估的基础设施
5. 可以调整的是：技术确认的阈值（RSI、乖离率门槛）、新闻排雷的严格程度、止损止盈的计算方式、评分标准的权重描述
6. 不要改变代码的整体结构、API调用方式、邮件发送逻辑、入库逻辑

如果"60分以下"区间的胜率反而高于"80-100分"区间，说明评分体系存在严重偏差，应在改进内容中重新校准评分标准描述。

【严格按以下格式输出，不要加任何其他内容】：

===REPORT_START===
<div style="background:#e8f5e9; border-left:6px solid #388e3c; padding:20px; border-radius:8px; margin-bottom:20px;">
<h3 style="color:#1b5e20; margin-top:0;">🔬 胜率诊断（仅基于本版本已到期数据）</h3>
<p>(基于真实盈亏数据说明胜率低的核心原因，是产业链逻辑判断错误，还是技术确认阈值不合理，还是评分体系校准问题)</p>
</div>
<div style="background:#e3f2fd; border-left:6px solid #1976d2; padding:20px; border-radius:8px;">
<h3 style="color:#0d47a1; margin-top:0;">🔧 本次改进内容</h3>
<ul>
<li>(改动1：具体参数变化，需说明为什么不破坏产业链逻辑选股的核心方法论)</li>
<li>(改动2：...)</li>
</ul>
</div>
===REPORT_END===

===CODE_START===
(完整的改进后 scan.py 代码)
===CODE_END===
"""

raw_output = ""
with client.messages.stream(
    model="claude-opus-4-8",
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

# ==========================================
# 语法检查：生成的代码必须通过才能覆盖
# ==========================================
try:
    ast.parse(new_code)
    print("✅ 语法检查通过，准备覆盖 scan.py")
except SyntaxError as e:
    print(f"❌ 生成的代码有语法错误，终止进化，scan.py 保持不变: {e}")
    report_html += f"""
    <div style="background:#ffebee; border-left:6px solid #c62828; padding:20px; border-radius:8px; margin-top:20px;">
    <h3 style="color:#b71c1c; margin-top:0;">❌ 语法错误，本次进化已中止</h3>
    <p>生成的代码存在语法错误，scan.py 未被修改，系统继续使用原版本。</p>
    <p>错误详情：{str(e)}</p>
    </div>
    """
    def send_error_mail(report_html, win_rate):
        user = os.environ.get("EMAIL_ACCOUNT")
        pwd = os.environ.get("EMAIL_PASSWORD")
        if not user or not pwd:
            return
        style = "<style>body{font-family:sans-serif;background:#f4f6f9;color:#333;padding:20px;line-height:1.6}.container{max-width:900px;margin:0 auto;background:#fff;padding:30px;border-radius:10px;}</style>"
        full_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head>
        <body><div class='container'>
        <h1 style='color:#c62828;text-align:center;'>⚠️ 美股进化失败 - 语法错误</h1>
        <p style='text-align:center;color:#666;'>触发胜率 <b style='color:#d32f2f;'>{win_rate}%</b>，但生成代码有语法错误，scan.py 未被修改</p>
        {report_html}
        </div></body></html>"""
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = user
        msg['Subject'] = f"【美股进化失败】语法错误，scan.py 未修改 ({get_today_str()})"
        msg.attach(MIMEText(full_html, 'html'))
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login(user, pwd)
                s.sendmail(user, [user], msg.as_string())
                print("✅ 错误通知邮件已发送！")
        except Exception as e:
            print(f"❌ 邮件发送失败: {e}")
    send_error_mail(report_html, overall_win_rate)
    exit(1)

try:
    backup_name = f"scan_backup_us_{datetime.datetime.now().strftime('%Y%m%d')}.py"
    with open(backup_name, "w", encoding="utf-8") as f:
        f.write(current_scan_code)
    print(f"✅ 旧版本已备份至 {backup_name}")
    with open("scan.py", "w", encoding="utf-8") as f:
        f.write(f"# 美股自动进化版本 | 时间: {get_now_str()} | 触发胜率: {overall_win_rate}%\n\n")
        f.write(new_code)
    print("✅ scan.py 已自动更新！下次运行时会自动检测内容变化并重新标记版本起始日期。")
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
        <p>注意：下次 scan.py 运行时会自动检测到内容变化，重新记录版本起始日期，本次改动之前的数据将不再计入未来的胜率评估。</p>
    </div>
    """
    style = "<style>body{font-family:sans-serif;background:#f4f6f9;color:#333;padding:20px;line-height:1.6}.container{max-width:900px;margin:0 auto;background:#fff;padding:30px;border-radius:10px;}</style>"
    full_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>{style}</head>
    <body><div class='container'>
    <h1 style='color:#1a237e;text-align:center;'>美股 scan.py 已自动进化</h1>
    <p style='text-align:center;color:#666;'>本版本真实胜率（仅已到期归档样本） <b style='color:#d32f2f;'>{win_rate}%</b>，系统已自动优化</p>
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
