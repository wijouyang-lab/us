from pathlib import Path
import sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else 'review.py')
s = p.read_text(encoding='utf-8')

# Replace only the KPI HTML so all existing data/price/risk/option logic stays intact.
start = s.find('kpi_html = f"""')
end = s.find('\n\n# ============================================================\n# 15. Observation HTML', start)
if start < 0 or end < start:
    raise SystemExit('找不到 kpi_html 区块，请确认这是当前 review.py。')

new_kpi = '''kpi_html = f"""
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:15px;margin-bottom:20px;">

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #1565c0;">
<div style="font-size:13px;color:#7f8c8d;">最近30天 Scan 推荐</div>
<div style="font-size:25px;font-weight:bold;">{total_scan_recommendations}</div>
<div style="font-size:14px;font-weight:700;">Core {core_event_count}　·　Observation {observation_event_count}</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">有价格 {valid_performance_samples} · 数据不足 {data_insufficient_count} · 无推荐价 {no_rec_price_count} · 无当前价 {price_missing_count}</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #1565c0;">
<div style="font-size:14px;color:#1565c0;font-weight:700;">👑 Core</div>
<div style="font-size:13px;margin-top:7px;">已完成胜率 <b>{core_closed_win_rate:.2f}%</b>　{core_closed_wins} 赢 / {core_closed_losses} 亏</div>
<div style="font-size:13px;margin-top:5px;">当前跟踪 <b>{core_open_win_rate:.2f}%</b>　{core_open_wins} 赢 / {core_open_losses} 亏 / {core_open_neutral} 平</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">已完成 {core_closed_count} 笔 · 当前 {core_open_count} 笔</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #ff9800;">
<div style="font-size:14px;color:#e65100;font-weight:700;">👀 Observation</div>
<div style="font-size:13px;margin-top:7px;">已完成胜率 <b>{obs_closed_win_rate:.2f}%</b>　{obs_closed_wins} 赢 / {obs_closed_losses} 亏</div>
<div style="font-size:13px;margin-top:5px;">当前跟踪 <b>{obs_win_rate:.2f}%</b>　{obs_open_wins} 赢 / {obs_open_losses} 亏 / {obs_open_neutral} 平</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">已完成 {observation_closed_count} 笔 · 当前 {observation_open_count} 笔 · 不计实际持仓</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #e67e22;">
<div style="font-size:14px;color:#e67e22;font-weight:700;">🟢 实际持仓</div>
<div style="font-size:25px;font-weight:bold;color:#e67e22;">{actual_active_win_rate:.2f}%</div>
<div style="font-size:13px;">{actual_active_wins} 赢 / {actual_active_losses} 亏 / {actual_active_neutral} 平</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">当前真实持仓 {actual_active_count} 笔；它是 Core 中已实际建仓的子集</div>
</div>

<div style="background:#fff;border:1px solid #eef2f5;border-radius:10px;padding:15px;border-top:4px solid #9b59b6;">
<div style="font-size:14px;color:#8e44ad;font-weight:700;">🎲 期权</div>
<div style="font-size:25px;font-weight:bold;color:#8e44ad;">{option_win_rate:.2f}%</div>
<div style="font-size:13px;">{option_wins} 赢 / {option_losses} 亏 / {option_neutral} 平</div>
<div style="font-size:11px;color:#607d8b;margin-top:8px;">只统计已经结束的期权，与股票 Scan 完全分开</div>
</div>

<div style="background:#f7f9fb;border:1px solid #dfe6ee;border-radius:10px;padding:15px;grid-column:1/-1;">
<div style="font-size:13px;font-weight:700;color:#455a64;">📌 统计口径</div>
<div style="font-size:12px;line-height:1.8;color:#546e7a;margin-top:5px;">
Core 与 Observation 不再混成一个主胜率。<br>
<strong>Core 已完成胜率</strong> = 已结束的 Core 推荐事件；<strong>Core 当前跟踪</strong> = 尚未结束的 Core 推荐事件。<br>
<strong>Observation 已完成胜率</strong> = 已结束的 Observation 推荐事件；<strong>Observation 当前跟踪</strong> = 尚未结束的 Observation 推荐事件。<br>
<strong>实际持仓胜率</strong> = 当前真实建仓且仍持有的 Core 子集，因此它与 Core 当前跟踪胜率可以不同；Observation 永远不进入实际持仓统计。<br>
当前浮盈/浮亏只用于“当前跟踪”，只有真实结束并有退出价格的事件才进入“已完成胜率”。
</div>
</div>

</div>
"""
'''
s = s[:start] + new_kpi + s[end:]

# Simplify console logs (no mixed aggregate headline).
s = s.replace('print(f"📊 已完成 Scan推荐胜率：{closed_win_rate:.2f}% ({closed_wins} 赢 / {closed_losses} 亏 / {closed_neutral} 平)")\n', '')
s = s.replace('print(f"📊 当前开放推荐跟踪：{tracking_win_rate:.2f}% ({tracking_wins} 赢 / {tracking_losses} 亏 / {tracking_neutral} 平)")\n', '')
s = s.replace('print(f"📊 已了结股票推荐胜率：{closed_win_rate:.2f}%")\n', '')

# Rename the report title only if it exists.
s = s.replace('美股盘后复盘与风控审查报告（Scan推荐事件独立追踪 / 含期权）',
              '美股盘后复盘与风控审查报告（Core / Observation 分层统计 / 含期权）', 1)

p.write_text(s, encoding='utf-8')
print(f'✅ 已更新 {p}')
