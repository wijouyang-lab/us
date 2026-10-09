# -*- coding: utf-8 -*-
"""AI 目标持仓 Feature（ENABLE_TARGET_FILE）—— 纯函数实现，独立可单测。

scan.py 在 ENABLE_TARGET_FILE == "1" 时调用本模块，把「scan 最终 Core 推荐 + 当前持仓对比」
落盘为 portfolio_50000_target.csv。本模块无任何市场时段守卫 / 环境变量校验 / 网络调用，
便于直接 import 单测。失败由调用方（scan.py）的 try/except 兜住，不阻断 scan 主流程。

资金约束：
  · 初始资金 $50,000（模拟账户）
  · 单只上限 25% → $12,500（用户拍板，防等权 3 只时每只 33.3% 超限）
  · 等权目标金额受单只上限约束：budget = min(等权金额, MAX_POSITION_DOLLARS)
"""
import csv

INITIAL_CAPITAL = 50000
MAX_POSITION_PCT = 0.25
MAX_POSITION_DOLLARS = INITIAL_CAPITAL * MAX_POSITION_PCT  # 12500


def _to_float(v):
    """把价格字符串（$ / 逗号）转 float；失败返回 0.0。"""
    if v is None:
        return 0.0
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _target_ref_price(item):
    """盘前参考价：优先 Price（= 最近收盘，盘前即昨收），回退 Open_Price / Prev_Close。"""
    for k in ("Price", "Open_Price", "Prev_Close"):
        v = (item or {}).get(k)
        if v not in (None, "", "N/A"):
            return v
    return ""


def _target_reason(item):
    """AI 理由：优先盘前结论，回退产业链逻辑 / 催化剂；截断避免 CSV 膨胀。"""
    for k in ("AI_premarket_conclusion", "AI_industry_logic", "AI_catalysts"):
        v = ((item or {}).get(k) or "").strip()
        if v:
            return v[:240]
    return ""


def _target_shares(per_amount, price):
    """等权每只预算 per_amount，受单只 25% 上限（MAX_POSITION_DOLLARS）约束。

    per_amount: 该标的等权目标金额（= INITIAL_CAPITAL / n_targets）
    price: 参考价（Ref_Price）
    返回向下取整股数；任意异常 / 价格≤0 → 0。
    """
    p = _to_float(price)
    if p <= 0:
        return 0
    budget = min(per_amount, MAX_POSITION_DOLLARS)
    return max(0, int(budget // p))


def _load_held_shares(positions_csv="portfolio_50000_positions.csv"):
    """从持仓 CSV 读 {TICKER: shares} map（HOLD 行语义：目标股数=当前实际持股）。

    只读、容错：文件缺失 / 解析失败返回空 dict（此时 HOLD 行 Target_Shares 回退为 0）。
    不在 scan.py 内改调用，故 writer 自行读取同一持仓 CSV 获取 shares。
    """
    out = {}
    try:
        with open(positions_csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                t = (row.get("Ticker") or "").upper().strip()
                if not t:
                    continue
                try:
                    s = int(_to_float(row.get("Shares")))
                except (TypeError, ValueError):
                    s = 0
                out[t] = s
    except Exception:
        return {}
    return out


def build_portfolio_target_rows(chosen_items, held_positions, scan_date, held_shares=None):
    """构造目标持仓行（dict 列表）。幂等键 = Scan_Date + Ticker（整文件覆盖即幂等）。

    chosen_items: scan 最终推荐（to_write，Core/Observation）
    held_positions: 当前持仓 Ticker 列表（portfolio_50000_positions.csv OPEN）
    held_shares: 可选 {TICKER: shares} map；提供时 HOLD 行 Target_Shares = 当前持股数
    返回 (rows, n_targets)：rows 含 BUY/HOLD/SELL；n_targets = 推荐标的数（用于等权）。
    """
    held = {str(t).upper() for t in (held_positions or [])}
    shares_map = held_shares or {}
    rec = []
    seen = set()
    for it in (chosen_items or []):
        t = str((it or {}).get("Ticker", "")).upper()
        if not t or t in seen:
            continue
        seen.add(t)
        rec.append({
            "Ticker": t,
            "Ref_Price": _target_ref_price(it),
            "Stop_Loss": (it.get("Stop_Loss") or "") if str(it.get("Stop_Loss")) not in (None, "", "N/A") else "",
            "AI_Reason": _target_reason(it),
        })
    n_targets = len(rec)
    # 无推荐（n_targets==0）→ 不构成目标组合，避免误发「清仓所有持仓」信号
    if n_targets == 0:
        return [], 0
    per = INITIAL_CAPITAL / n_targets
    rows = []
    for r in rec:
        t = r["Ticker"]
        if t in held:
            # HOLD：维持现有持仓，目标股数 = 当前实际持股数（不新买，故不受单只上限约束）
            action = "HOLD"
            target_shares = shares_map.get(t, 0)
        else:
            # BUY：新标的，等权金额受 25% 上限约束
            action = "BUY"
            target_shares = _target_shares(per, r["Ref_Price"])
        rows.append({
            "Scan_Date": scan_date,
            "Ticker": t,
            "Action": action,
            "Target_Shares": target_shares,
            "Ref_Price": r["Ref_Price"],
            "Stop_Loss": r["Stop_Loss"],
            "AI_Reason": r["AI_Reason"],
        })
    # 当前持仓但不在今日推荐 → SELL（调出目标持仓）
    for t in sorted(held):
        if t not in seen:
            rows.append({
                "Scan_Date": scan_date,
                "Ticker": t,
                "Action": "SELL",
                "Target_Shares": 0,
                "Ref_Price": "",
                "Stop_Loss": "",
                "AI_Reason": "不在今日 Core 推荐列表，调出目标持仓",
            })
    return rows, n_targets


def write_portfolio_target_csv(chosen_items, held_positions, scan_date,
                               positions_csv="portfolio_50000_positions.csv"):
    """落盘 portfolio_50000_target.csv（整文件覆盖 → 同天重跑幂等）。返回路径或 None。

    HOLD 行实际持股数由持仓 CSV 自行读取（不依赖 scan.py 改调用）。
    """
    held_shares = _load_held_shares(positions_csv)
    rows, _ = build_portfolio_target_rows(chosen_items, held_positions, scan_date, held_shares=held_shares)
    if not rows:
        print("ℹ️ [Target] 今日无推荐，跳过目标持仓文件生成")
        return None
    cols = ["Scan_Date", "Ticker", "Action", "Target_Shares", "Ref_Price", "Stop_Loss", "AI_Reason"]
    path = "portfolio_50000_target.csv"
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(",".join(cols) + "\n")
            for r in rows:
                vals = [str(r.get(c, "")) for c in cols]
                safe = [v.replace("\r", " ").replace("\n", " ").replace(",", " ") for v in vals]
                f.write(",".join(safe) + "\n")
        print(f"✅ [Target] 已生成 {len(rows)} 条 AI 目标持仓：{path}")
        return path
    except Exception as e:
        print(f"⚠️ [Target] portfolio_50000_target.csv 写入失败（不影响 scan）：{type(e).__name__}: {e}")
        return None
