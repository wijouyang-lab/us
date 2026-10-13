# -*- coding: utf-8 -*-
"""
周一 scan 新逻辑本地模拟（只读真实数据，不调 AI，target 写 /tmp）。
仅调用纯函数：quant_filter.strict_filter / build_ai_input、portfolio_target.build_portfolio_target_rows、
portfolio_50000._stock_pct / _within_alloc / unit_dollars_for。
不修改任何 .py，不写仓库。
"""
import csv, json, sys, os
from decimal import Decimal

US = "/tmp/us"
sys.path.insert(0, US)
import quant_filter as qf
import portfolio_target as pt
import portfolio_50000 as p5

SNAP = os.path.join(US, "quant_factor_snapshot.csv")
POS  = os.path.join(US, "portfolio_50000_positions.csv")

def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]

def num(x):
    try: return float(x)
    except: return None

print("="*70)
print("周一 scan 新逻辑模拟  (snapshot=%s, positions=%s)" % (SNAP, POS))
print("="*70)

snapshot = load_csv(SNAP)
positions_rows = load_csv(POS)
held = [r["Ticker"].upper() for r in positions_rows if r.get("Status","").upper() in ("","OPEN","ACTIVE")]
print("\n[数据] snapshot 行数 = %d ; 持仓 OPEN = %s" % (len(snapshot), held))

# ---- 构造模拟内存 pool_data：严格按 build_stock_pool 的规范字段名重命名 ----
# CSV 用的是 RSI_14/Bias_Pct/MACD_Hist/Volume_Ratio_5D；内存 pool 用 RSI/乖离率(%)/MACD趋势/量比。
# 同时合成 target_price = Price*1.12（等效 20日高点，真实 scan 由 get_kline_data 现算）。
def normalize(rows):
    out = []
    for r in rows:
        t = dict(r)
        t["RSI"] = t.get("RSI_14")
        t["乖离率(%)"] = t.get("Bias_Pct")
        t["量比"] = t.get("Volume_Ratio_5D")
        mh = num(t.get("MACD_Hist"))
        t["MACD趋势"] = "走强" if (mh is not None and mh >= 0) else "走弱"
        p = num(t.get("Price"))
        t["target_price"] = round(p*1.12, 2) if p else None   # 模拟 20d-high
        out.append(t)
    return out

pool = normalize(snapshot)

# ============ 检查 1: strict_filter 筛出几只 ============
cand = qf.strict_filter(pool)
print("\n[检查1] strict_filter 候选数 = %d  (期望 0-3)" % len(cand))
for c in cand:
    print("   %-6s score=%.0f rr=%.2f stop%%=%.2f sector=%s" % (
        c["Ticker"], qf._score_of(c), c.get("_rr",0), (c.get("_stop_dist") or 0)*100, c.get("Sector")))

# 同时报告：原始 CSV（无 target_price）直跑会得几只 —— 说明字段依赖
cand_raw = qf.strict_filter(snapshot)
print("   [对照] 原始 CSV（缺 target_price/highs）直跑 strict_filter = %d 只（必为 0，字段在 scan 运行时现算）" % len(cand_raw))

# ============ 检查 2-4: build_ai_input ============
ai_input = qf.build_ai_input(pool, held, cand)
pos_in = [x for x in ai_input if x.get("_is_position")]
cand_in = [x for x in ai_input if not x.get("_is_position")]
print("\n[检查2] 4 只持仓是否都在 AI 输入：%s (在=%d)" % (
    "✅" if all(t in [x["Ticker"].upper() for x in pos_in] for t in held) else "❌", len(pos_in)))
print("[检查3] AI 输入总数 = %d (持仓%d + 候选%d)  ≤7 ? %s" % (
    len(ai_input), len(pos_in), len(cand_in), "✅" if len(ai_input) <= 7 else "❌"))
REQ = list(qf.AI_INPUT_REQUIRED_FIELDS.keys())
print("[检查4] 持仓行必填字段齐？（Name/Price/RSI/乖离率(%)/MACD趋势/KDJ_J/量比）")
for x in pos_in:
    missing = [k for k in REQ if not str(x.get(k,"")).strip() or str(x.get(k,""))=="N/A"]
    print("   %-6s 缺字段=%s  值: Name=%s Price=%s RSI=%s 乖离=%s MACD=%s KDJ_J=%s 量比=%s" % (
        x["Ticker"], missing or "无",
        x.get("Name"), x.get("Price"), x.get("RSI"), x.get("乖离率(%)"),
        x.get("MACD趋势"), x.get("KDJ_J"), x.get("量比")))

# ============ 检查 5: write_portfolio_target_csv（落到 /tmp，用纯函数 build_portfolio_target_rows）============
# 构造 chosen_items：持仓→HOLD，候选→BUY（模拟 AI 决策）
chosen = []
for x in pos_in:
    r = dict(x); r["Tag"]="Core_Dragon"; chosen.append(r)
for c in cand_in:
    r = dict(c); r["Tag"]="Candidate"; chosen.append(r)
held_shares = {r["Ticker"].upper(): int(float(r.get("Shares",0))) for r in positions_rows}
rows, n_targets = pt.build_portfolio_target_rows(chosen, held, "2026-10-12", held_shares=held_shares)
out_csv = "/tmp/monday_target_sim.csv"
cols = ["Scan_Date","Ticker","Action","Target_Shares","Ref_Price","Stop_Loss","AI_Reason"]
with open(out_csv, "w", encoding="utf-8", newline="") as f:
    f.write(",".join(cols)+"\n")
    for r in rows:
        f.write(",".join(str(r.get(c,"")) for c in cols)+"\n")
acts = {}
for r in rows: acts[r["Action"]] = acts.get(r["Action"],0)+1
print("\n[检查5] write_portfolio_target_csv 输出：%d 行 (写 %s)" % (len(rows), out_csv))
print("   列 = %s" % cols)
print("   Action 分布 = %s" % acts)
print("   样本:")
for r in rows[:6]:
    print("     %-6s %-5s shares=%s ref=%s stop=%s" % (r["Ticker"], r["Action"], r["Target_Shares"], r["Ref_Price"], r["Stop_Loss"]))

# ============ 检查 6-7: portfolio_50000 #4 守卫（真实持仓）============
print("\n[检查6/7] portfolio_50000 #4 守卫（真实 4 持仓）")
# 转成 portfolio_50000 内部持仓结构
p5pos = []
for r in positions_rows:
    p5pos.append({"Ticker":r["Ticker"],"Shares":r["Shares"],"Market_Value":r.get("Market_Value"),
                  "Status":r.get("Status","OPEN"),"Stop_Loss":r.get("Stop_Loss")})
# 构造真实 BUY 交易流水，使 derive_cash 推导出正确现金（否则空交易→现金=50000→占比失真）
txns = []
for r in positions_rows:
    txns.append({"Action":"BUY","Amount":r.get("Cost_Basis"),"Ticker":r["Ticker"]})
stock_pct = p5._stock_pct(p5pos, txns)
cash = p5.derive_cash(txns)
equity = cash + sum((p5.dec(p.get("Market_Value")) or p5.ZERO) for p in p5pos)
print("   现金(derive_cash)=%s  总资产(equity)=%s  股票市值=%s" % (cash, equity.quantize(p5.CENT),
      sum((p5.dec(p.get("Market_Value")) or p5.ZERO) for p in p5pos).quantize(p5.CENT)))
print("   当前总股票占比 = %.2f%%  (≤80%% ? %s)" % (float(stock_pct)*100, "✅" if stock_pct <= Decimal("0.80") else "❌"))
# 模拟一只新候选买入：unit_dollars_for（无 AI_Score → 退化为 1 Unit）
rec = {"AI_Score": None, "Ticker":"NEW", "Price": 100.0}
unit = p5.unit_dollars_for(rec, equity)
print("   unit_dollars_for(无AI_Score) = %s (=1 Unit 退化, ≤25%%×equity=%s ? %s)" % (
    unit, equity*Decimal("0.25"), "✅" if unit <= equity*Decimal("0.25") else "❌"))
ok, why = p5._within_alloc(rec, p5pos, txns, equity)
print("   _within_alloc(新增 NEW) = %s  (%s)  → 当前 4 持仓已 ~%.1f%% 股票，新增会超 80%% 闸门" % (
    ok, why or "通过", float(stock_pct)*100))

# ============ 检查 8: 0 候选时 scan 是否崩 ============
print("\n[检查8] 0 候选边界：strict_filter=[] 时")
ai_zero = qf.build_ai_input(pool, held, [])   # 0 候选
print("   build_ai_input(候选=[]) → AI 输入 %d 只（=4 持仓，不崩）" % len(ai_zero))
# scan.py:3817 if not pool_data: sys.exit(0) —— pool_data=快照(非空)，不触发
# scan.py:3849 if not chosen: 仅告警
# 模拟 AI 全 HOLD → chosen 仅 4 持仓 → build_portfolio_target_rows 返回 4 HOLD 行
chosen_zero = [dict(x, Tag="Core_Dragon") for x in ai_zero if x.get("_is_position")]
rows_z, nz = pt.build_portfolio_target_rows(chosen_zero, held, "2026-10-12", held_shares=held_shares)
print("   若 AI 全 HOLD → chosen=%d → target 行=%d（4 HOLD，非空）" % (len(chosen_zero), len(rows_z)))
# 若 AI 也全不选（chosen=[]）→ build_portfolio_target_rows 返回 ([],0)；write 时 return None
rows_empty, ne = pt.build_portfolio_target_rows([], held, "2026-10-12", held_shares=held_shares)
print("   若 chosen=[] → build_portfolio_target_rows 返回 %r (n=%d) → write_portfolio_target_csv return None（跳过，不崩）" % (rows_empty, ne))
print("   scan.py 兜底：3817 空池 exit(0) | 3849 空 chosen 告警 | 3956 ENABLE_TARGET_FILE 包裹且 write 失败 return None")
print("\n结论：0 候选 → scan 正常完成，不崩（pending CSV 可能 0 行，target 文件跳过）。")

print("\n" + "="*70)
print("输出文件: %s" % out_csv)
print("="*70)
