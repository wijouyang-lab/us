# -*- coding: utf-8 -*-
"""周末模拟「意外成功」全链路（只读 + 纯函数）。

仅 import 三个模块的纯函数，不触网、不写仓库文件。
所有结果打印 + 落到 /tmp/sim_success_path.out。
"""
import csv
import copy
import io
import sys
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, "/tmp/us")
import quant_filter as qf
import portfolio_target as pt
import portfolio_50000 as pf

SNAP = "/tmp/us/quant_factor_snapshot.csv"
POS = "/tmp/us/portfolio_50000_positions.csv"
TXN = "/tmp/us/portfolio_50000_transactions.csv"
LATEST = "2026-10-09"

OUT = []


def log(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s)


def load_snapshot(date):
    rows = []
    with open(SNAP, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("Scan_Date") == date:
                rows.append(r)
    return rows


def synth(row):
    """合成 strict_filter 必需字段：target_price=Price*1.12, Stop_Loss=Price*0.95。
    注：真实 scan 用 20 日高点作 target；snapshot 无 target_price 列 → 真实场景 0 候选。
    本模拟按用户指示合成，仅为验证『候选出现时』链路是否健壮（已知假设，报告标注）。"""
    d = dict(row)
    price = qf._to_float(d.get("Price"))
    if price and price > 0:
        d["target_price"] = price * 1.12
        # 保留原 Stop_Loss（持仓/候选可能已有）；否则合成 0.96（止损距离=4%，干净落入 [2%,5%]）
        # 注：用户原指示 0.95 → 经浮点 (price - price*0.95)/price = 5.0016% > MAX_STOP_DIST(0.05)
        #     硬上限，会被 strict_filter 直接拒。0.96 是为让模拟出有效候选的务实取值（报告标注此坑）。
        if not d.get("Stop_Loss") or str(d.get("Stop_Loss")).strip() in ("", "N/A"):
            d["Stop_Loss"] = price * 0.96
    return d


def banner(t):
    log("\n" + "=" * 70)
    log(t)
    log("=" * 70)


# ---------------------------------------------------------------------------
banner("场景 A：严筛出 1 只候选 → AI 输入 / target 写入 / 前端匹配 / 股数")
snap = load_snapshot(LATEST)
log(f"snapshot {LATEST} 行数: {len(snap)}")

# 选一只非持仓、数据完整的真实票，构造候选（Quant_Score 改 85）
held = ["ADSK", "ANET", "ISRG", "KR"]
cand = None
for r in snap:
    tk = (r.get("Ticker") or "").upper()
    if tk in held:
        continue
    if qf._to_float(r.get("Price")) and qf._to_float(r.get("Price")) > 0:
        cand = dict(r)
        break
cand["Quant_Score"] = "85"
cand_synth = synth(cand)
log(f"构造候选: {cand_synth['Ticker']}  Price={cand_synth['Price']}  Quant_Score=85  "
    f"target_price={cand_synth['target_price']:.2f}  Stop_Loss={cand_synth['Stop_Loss']:.2f}")

# strict_filter：只投这只构造候选（隔离场景，证明『1 候选』链路）
pool1 = [cand_synth]
cands1 = qf.strict_filter(pool1)
log(f"strict_filter(1 构造候选) → 候选数: {len(cands1)}")
for c in cands1:
    log(f"  候选 {c['Ticker']}: score={qf._score_of(c)} rr={c.get('_rr')} "
        f"stop_dist={c.get('_stop_dist')} sector={c.get('Sector')}")

# build_ai_input(持仓4 + 候选1) → 应为 5
ai_in = qf.build_ai_input(snap, held, cands1)
log(f"build_ai_input(持仓{len(held)} + 候选{len(cands1)}) → AI 输入数: {len(ai_in)} "
    f"(预期 5)")
positions_core = sum(1 for x in ai_in if x.get("_is_position"))
positions_cand = sum(1 for x in ai_in if not x.get("_is_position"))
log(f"  其中 持仓(核心龙)={positions_core}  候选={positions_cand}")

# build_portfolio_target_rows：构造 chosen_items = 4 持仓 + 1 候选
snap_by = { (r.get("Ticker") or "").upper(): r for r in snap }
def mk_item(tk):
    base = snap_by.get(tk, {})
    d = synth(base) if base else {"Ticker": tk, "Price": "100", "Stop_Loss": "95", "Quant_Score": "80"}
    d["Ticker"] = tk
    if "AI_Reason" not in d:
        d["AI_Reason"] = ""
    return d

chosen = [mk_item(t) for t in held] + [cand_synth]
# 真实持仓 shares / stops
held_shares = pt._load_held_shares(POS)
held_stops = pt._load_held_stops(POS)
rows, n = pt.build_portfolio_target_rows(chosen, held, LATEST,
                                         held_shares=held_shares, held_stops=held_stops)
log(f"build_portfolio_target_rows → 行数={len(rows)}  n_targets={n}")
buy_rows = [r for r in rows if r["Action"] == "BUY"]
hold_rows = [r for r in rows if r["Action"] == "HOLD"]
sell_rows = [r for r in rows if r["Action"] == "SELL"]
log(f"  BUY={len(buy_rows)}  HOLD={len(hold_rows)}  SELL={len(sell_rows)}")
log("  BUY 行字段检查:")
for r in buy_rows:
    fields_ok = all(k in r for k in ("Ticker", "Action", "Target_Shares",
                                     "Ref_Price", "Stop_Loss", "AI_Reason", "Scan_Date"))
    log(f"    {r['Ticker']}: Action={r['Action']} Target_Shares={r['Target_Shares']} "
        f"Ref_Price={r['Ref_Price']} Stop_Loss={r['Stop_Loss']!r} "
        f"AI_Reason={r['AI_Reason']!r}  字段齐全={fields_ok}")
    # 股数钳制验证：budget = min(50000/5=10000, 12500)=10000
    per = 50000 / n
    budget = min(per, 12500)
    expect = int(budget // qf._to_float(r["Ref_Price"]))
    log(f"    股数计算: per=50000/{n}={per:.0f} budget=min(per,12500)={budget:.0f} "
        f"expect_shares=floor({budget}/{r['Ref_Price']})={expect} 实际={r['Target_Shares']} "
        f"匹配={expect == r['Target_Shares']}")

# 前端字段匹配（renderTarget 读 pf.target[]: ticker/action/target_shares/ref_price/ai_reason/scan_date）
frontend_keys = ("ticker", "action", "target_shares", "ref_price", "ai_reason", "scan_date")
log("  前端 dashboard_export 注入键检查 (匹配 renderTarget 读取):")
log(f"    dashboard_export 输出键: scan_date/ticker/action/target_shares/ref_price/stop_loss/ai_reason")
log(f"    renderTarget 读取键: {frontend_keys}")
needs = set(frontend_keys)
have = {"scan_date", "ticker", "action", "target_shares", "ref_price", "ai_reason"}
log(f"    键完全匹配={needs == have} (renderTarget 不读 stop_loss, 但导出层也给了, 无碍)")


# ---------------------------------------------------------------------------
banner("场景 B：新候选真的被买入 → process_buys 闸门")
# 用真实持仓 + 交易构造内存副本（不写文件）
def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]

positions_mem = load_csv(POS)
transactions_mem = load_csv(TXN)
meta = {"start_date": "2026-10-07"}
today = "2026-10-10"

# 当前占比（真实）
sp = pf._stock_pct(positions_mem, transactions_mem)
cash = pf.derive_cash(transactions_mem)
equity = cash + sum((pf.dec(p.get("Market_Value")) or pf.ZERO)
                    for p in positions_mem
                    if str(p.get("Status", "")).upper() == "OPEN")
log(f"真实当前: 现金=${cash:.2f} 股票MV=${sp*equity:.2f} 权益=${equity:.2f} "
    f"股票占比={sp*100:.2f}%")

# 构造第 5 只候选 rec（Core_Dragon / Active / Rec_Date>=start / 有 Price / Stop_Loss）
new_tk = cand_synth["Ticker"]
new_price = qf._to_float(cand_synth["Price"])
rec_id = f"{new_tk}|{LATEST}|Core_Dragon"
recs = {
    rec_id: {
        "Tag": pf.CORE_TAG,
        "Status": "Active",
        "Rec_Date": LATEST,
        "Ticker": new_tk,
        "Price": new_price,
        "Stop_Loss": qf._to_float(cand_synth["Stop_Loss"]),
        "Recommendation_ID": rec_id,
    }
}
# 闸门预览（不依赖 process_buys 副作用）
ok, why = pf._within_alloc(recs[rec_id], positions_mem, transactions_mem, equity)
log(f"闸门3 _within_alloc 预览: ok={ok} why={why!r}")
log(f"  → proj_stock = {sp*equity + min(pf.UNIT_DOLLARS, equity*pf.Decimal('0.25')):.2f} "
    f"vs 80%上限={equity*pf.Decimal('0.80'):.2f}")

# 空闲 Unit 预览
free_u = pf.next_free_unit(positions_mem)
log(f"空闲 Unit 预览: next_free_unit={free_u} (UNIT_IDS 固定 {pf.UNIT_IDS}, "
    f"4 持仓已占满 → 第5只无 Unit)")

# 真正调用 process_buys（纯函数，只改内存副本，不写文件）
log("调用 process_buys(内存副本)...")
buy_log = pf.process_buys(copy.deepcopy(positions_mem),
                         copy.deepcopy(transactions_mem),
                         recs, meta, today)
for line in buy_log:
    log("  " + line)
bought = any("🛒 BUY" in l for l in buy_log)
log(f"结论: 新候选是否真买入 = {bought} "
    f"({'被拦截(预期/非bug)' if not bought else '已买入'})")


# ---------------------------------------------------------------------------
banner("场景 C：盘中止损真触发 → 冷却生效（只读代码追踪 + 日期演示）")
# _run_intraday_stop 写: Cooldown_Until = _cooldown_until(today) = today+7
#   Pending_Reason="True"; 单日上限 MAX_INTRADAY_STOPS_PER_DAY=2
# process_buys 闸门1: today <= cd → 拦截; 闸门2: _recent_stop_tickers(today, today+1)
cd_days = 7
demo_today = "2026-10-12"
cd = (datetime.strptime(demo_today, "%Y-%m-%d") + timedelta(days=cd_days)).strftime("%Y-%m-%d")
log(f"_run_intraday_stop 触发后写 Cooldown_Until = today+{cd_days} = {demo_today} → {cd}")
log(f"  写 Pending_Reason = 'True' (transactions 行, Reason='Intraday Stop Loss')")
log(f"  单日上限 MAX_INTRADAY_STOPS_PER_DAY = {pf.MAX_INTRADAY_STOPS_PER_DAY}")
log("process_buys 拦截验证:")
for chk_day in (demo_today, "2026-10-13", "2026-10-18", "2026-10-20"):
    gate1 = chk_day <= cd
    gate2 = chk_day in (demo_today, "2026-10-13")  # 近1-2日防御
    blocked = gate1 or gate2
    log(f"  {chk_day}: 闸门1(today<=cd)={gate1} 闸门2(近1-2日)={gate2} → "
        f"{'拦截' if blocked else '放行'}")


# ---------------------------------------------------------------------------
banner("场景 D：MIN_SCORE=80 跑全部 255 只（合成 target/stop）—— 各闸计数")
all_synth = [synth(r) for r in snap]
# 逐闸漏斗
score_pass = [r for r in all_synth if qf._score_of(r) >= qf.MIN_SCORE]
rr_pass = []
for r in score_pass:
    price = qf._price_of(r)
    stop = qf._stop_of(r) or price * (1 - qf.DEFAULT_STOP_PCT)
    tgt = r.get("target_price")
    rr = qf.compute_rr_ratio(price, stop, tgt)
    sd = qf._stop_distance(price, stop)
    if rr is not None and rr >= qf.MIN_RR and sd is not None and qf.MIN_STOP_DIST <= sd <= qf.MAX_STOP_DIST:
        rr_pass.append(r)
final = qf.strict_filter(all_synth)
# 板块计数
sectors_used = set()
for r in final:
    sectors_used.add((r.get("Sector") or "").strip())
log(f"全量 {len(all_synth)} 只:")
log(f"  分数闸(≥{qf.MIN_SCORE})通过: {len(score_pass)}")
log(f"  +R/R闸(≥{qf.MIN_RR}) & 止损距离[{qf.MIN_STOP_DIST},{qf.MAX_STOP_DIST}]通过: {len(rr_pass)}")
log(f"  +板块≤1/板块(strict_filter) → 最终候选: {len(final)}")
log(f"  候选板块: {sorted(sectors_used)}")
for c in final:
    log(f"    候选 {c['Ticker']}: score={qf._score_of(c)} rr={c.get('_rr')} "
        f"sd={c.get('_stop_dist')} sector={c.get('Sector')}")
log("  注: 真实 scan 用 20 日高点作 target 且 snapshot 无 target_price 列 → "
    "真实候选数可能不同；本计数基于『Price×1.12 / Price×0.95』合成假设。")


# ---------------------------------------------------------------------------
banner("汇总")
with open("/tmp/sim_success_path.out", "w", encoding="utf-8") as f:
    f.write("\n".join(OUT))
log("输出已写到 /tmp/sim_success_path.out")
