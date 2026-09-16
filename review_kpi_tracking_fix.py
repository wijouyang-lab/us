# -*- coding: utf-8 -*-
"""
Apply the US Review KPI fix to the current repository review.py.

Goal:
- Every Scan stock recommendation, including Observation, participates in return tracking.
- Observation return = current price / first Scan recommendation price - 1.
- Stock recommendation KPIs exclude option trades; option results can be shown separately.
- Keep actual holding win rate as a secondary metric, but add an overall stock recommendation tracking win rate.
"""
from pathlib import Path
import re

P = Path("review.py")
if not P.exists():
    raise SystemExit("review.py not found")
s = P.read_text(encoding="utf-8")

# 1) Observation current return helper injected before KPI section.
marker = "# ============================================================\n# 20. KPI\n# ============================================================\n"
if marker not in s:
    raise SystemExit("KPI marker not found")

helper = r'''# ============================================================
# 19.5 统一 Scan 推荐追踪收益
# ============================================================
def _recommendation_tracking_pnl(item):
    """对任何 Scan 推荐计算当前跟踪涨跌幅；没有价格则返回 None。"""
    rec = safe_float(item.get("首次推荐价", item.get("Rec_Price")))
    cur = safe_float(item.get("当前价格", item.get("Cur_Price", item.get("现价"))))
    if rec is None or rec <= 0 or cur is None:
        return None
    return round((cur - rec) / rec * 100, 2)


def _is_scan_stock_status(status):
    return clean_text(status) not in {"期权平仓", "期权持仓", "Option"}


'''
if "def _recommendation_tracking_pnl" not in s:
    s = s.replace(marker, helper + marker, 1)

# 2) Replace KPI body from historical_closed init until KPI HTML.
start = s.index(marker) + len(marker)
end_marker = "# ============================================================\n# 21. KPI HTML\n# ============================================================\n"
end = s.index(end_marker, start)
new_kpi = r'''print("📊 计算 KPI...")

historical_closed = []

if os.path.exists(REVIEW_HISTORY) and os.path.getsize(REVIEW_HISTORY) > 0:
    try:
        existing_review = pd.read_csv(
            REVIEW_HISTORY,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="skip",
        )
        closed_statuses = {
            "已超期归档", "突发清仓暂停", "止损触发清仓",
            "移动止损清仓", "周期到期清仓", "期权平仓",
        }
        if "Status" in existing_review.columns:
            closed_rows = existing_review[existing_review["Status"].isin(closed_statuses)]
            for _, row in closed_rows.iterrows():
                pnl = safe_float(row.get("PnL_Pct"))
                if pnl is None:
                    pnl = safe_float(row.get("Maturity_PnL"))
                if pnl is None:
                    continue
                historical_closed.append({
                    "ticker": clean_text(row.get("Ticker")),
                    "name": clean_text(row.get("Name")),
                    "pnl": pnl,
                    "status": clean_text(row.get("Status")),
                    "is_option": clean_text(row.get("Status")) == "期权平仓",
                })
    except Exception as e:
        print(f"⚠️ KPI 历史数据读取失败：{e}")

for item in stopped_list:
    historical_closed.append({
        "ticker": item["代码"],
        "name": item["名称"],
        "pnl": item["止损盈亏(%)"],
        "status": "止损触发清仓",
        "is_option": False,
    })

for item in expired_list:
    pnl = safe_float(item.get("期满日盈亏(%)"))
    if pnl is None:
        continue
    historical_closed.append({
        "ticker": item["代码"],
        "name": item["名称"],
        "pnl": pnl,
        "status": "已超期归档",
        "is_option": False,
    })

for opt in option_closed_records:
    historical_closed.append({
        "ticker": opt["ticker"],
        "name": opt["ticker"] + " OPT",
        "pnl": opt["pnl"],
        "status": "期权平仓",
        "is_option": True,
    })

# ===== 股票Scan推荐：持仓 + Observation，全部纳入当前跟踪 =====
active_tracking = []
for item in active_list:
    pnl = safe_float(item.get("当前盈亏(%)"))
    if pnl is None:
        pnl = _recommendation_tracking_pnl(item)
    if pnl is not None:
        active_tracking.append(pnl)

observation_tracking = []
for item in observation_list:
    pnl = _recommendation_tracking_pnl(item)
    if pnl is not None:
        item["推荐跟踪涨跌幅(%)"] = pnl
        observation_tracking.append(pnl)
    else:
        item["推荐跟踪涨跌幅(%)"] = None

# 实际持仓单独保留，便于同时观察“持仓胜率”和“所有Scan推荐胜率”。
active_count = len(active_list)
observation_count = len(observation_list)
new_today_count = sum(1 for item in active_list if item.get("今日新增") == "是")
new_observation_today_count = sum(1 for item in observation_list if item.get("今日新增") == "是")

active_wins = sum(1 for p in active_tracking if p > 0)
active_win_rate = active_wins / len(active_tracking) * 100 if active_tracking else 0.0

# 已了结股票，不含期权。
closed_stock = [x for x in historical_closed if not x.get("is_option", False)]
closed_option = [x for x in historical_closed if x.get("is_option", False)]
closed_stock_count = len(closed_stock)
closed_stock_wins = sum(1 for x in closed_stock if x["pnl"] > 0)
closed_stock_win_rate = closed_stock_wins / closed_stock_count * 100 if closed_stock_count else 0.0

# 所有Scan股票推荐综合跟踪：持仓 + Observation + 已了结股票。
open_recommendation_pnl = active_tracking + observation_tracking
all_stock_recommendation_pnl = open_recommendation_pnl + [x["pnl"] for x in closed_stock]
recommendation_wins = sum(1 for p in all_stock_recommendation_pnl if p > 0)
recommendation_win_rate = recommendation_wins / len(all_stock_recommendation_pnl) * 100 if all_stock_recommendation_pnl else 0.0

# 推荐笔数：只统计股票Scan推荐，不把期权交易当股票推荐笔数。
total_stock_recommendations = active_count + observation_count + closed_stock_count

# 当前跟踪胜率：所有尚未结束的Scan推荐（持仓+Observation）。
tracking_wins = sum(1 for p in open_recommendation_pnl if p > 0)
tracking_losses = sum(1 for p in open_recommendation_pnl if p < 0)
tracking_win_rate = tracking_wins / len(open_recommendation_pnl) * 100 if open_recommendation_pnl else 0.0

# PnL统计只使用股票Scan推荐，避免期权损益污染股票系统。
all_pnl = all_stock_recommendation_pnl
super_threshold = 50.0
super_winners = [p for p in all_pnl if p >= super_threshold]
super_contribution = sum(super_winners)
other_winners = [p for p in all_pnl if 0 < p < super_threshold]
other_avg = sum(other_winners) / len(other_winners) if other_winners else 0.0
losers = [p for p in all_pnl if p < 0]
loser_avg = sum(losers) / len(losers) if losers else 0.0

# 期权统计单独保留，避免混入股票推荐胜率。
option_pnl = [x["pnl"] for x in closed_option]
option_wins = sum(1 for p in option_pnl if p > 0)
option_win_rate = option_wins / len(option_pnl) * 100 if option_pnl else 0.0
'''
s = s[:start] + new_kpi + "\n" + s[end:]

# 3) Replace the KPI HTML block to make the semantics explicit.
start = s.index(end_marker) + len(end_marker)
# Find next major section
next_marker = "# ============================================================\n# 21.5"
end = s.index(next_marker, start) if next_marker in s[start:] else s.index("# ============================================================\n# 22.", start)
new_html = r'''kpi_html = f"""
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:20px;">
<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #1565c0;">
<div style="font-size:13px;color:#7f8c8d;">总股票推荐笔数</div>
<div style="font-size:24px;font-weight:bold;">{total_stock_recommendations}</div>
<div style="font-size:12px;">持仓 {active_count} · 观察推荐 {observation_count} · 已了结 {closed_stock_count}</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #2ecc71;">
<div style="font-size:13px;color:#7f8c8d;">Scan推荐综合胜率</div>
<div style="font-size:24px;font-weight:bold;color:#2ecc71;">{recommendation_win_rate:.2f}%</div>
<div style="font-size:12px;">{recommendation_wins} 赢 / {len(all_stock_recommendation_pnl)-recommendation_wins} 亏（持仓+观察+已了结）</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #17a2b8;">
<div style="font-size:13px;color:#7f8c8d;">当前推荐跟踪胜率</div>
<div style="font-size:24px;font-weight:bold;color:#17a2b8;">{tracking_win_rate:.2f}%</div>
<div style="font-size:12px;">{tracking_wins} 赢 / {tracking_losses} 亏；持仓+Observation 均纳入</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #e67e22;">
<div style="font-size:13px;color:#7f8c8d;">已了结股票胜率</div>
<div style="font-size:24px;font-weight:bold;color:#e67e22;">{closed_stock_win_rate:.2f}%</div>
<div style="font-size:12px;">{closed_stock_wins} 赢 / {closed_stock_count-closed_stock_wins} 亏（不含期权）</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #8e44ad;">
<div style="font-size:13px;color:#7f8c8d;">超级赢家贡献</div>
<div style="font-size:24px;font-weight:bold;color:#8e44ad;">+{super_contribution:.2f}%</div>
<div style="font-size:12px;">股票Scan推荐中单笔盈利 ≥ {super_threshold:.0f}%</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #1abc9c;">
<div style="font-size:13px;color:#7f8c8d;">其余盈利平均</div>
<div style="font-size:24px;font-weight:bold;color:#1abc9c;">+{other_avg:.2f}%</div>
<div style="font-size:12px;">排除超级赢家</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #e74c3c;">
<div style="font-size:13px;color:#7f8c8d;">亏损平均</div>
<div style="font-size:24px;font-weight:bold;color:#e74c3c;">{loser_avg:.2f}%</div>
<div style="font-size:12px;">所有股票Scan推荐亏损</div>
</div>
</div>
"""
'''
s = s[:start] + new_html + "\n" + s[end:]

P.write_text(s, encoding="utf-8")
print("✅ review.py KPI tracking fix applied")
