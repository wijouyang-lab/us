# -*- coding: utf-8 -*-
"""AI 目标持仓 Feature（ENABLE_TARGET_FILE）—— 纯函数实现，独立可单测。

scan.py 在 ENABLE_TARGET_FILE == "1" 时调用本模块，把「scan 最终 Core 推荐 + 当前持仓对比」
落盘为 portfolio_50000_target.csv。本模块无任何市场时段守卫 / 环境变量校验 / 网络调用，
便于直接 import 单测。失败由调用方（scan.py）的 try/except 兜住，不阻断 scan 主流程。
"""
PORTFOLIO_TARGET_BUDGET = 50000  # $50k 模拟账户总预算


def _target_ref_price(item):
    """盘前参考价：优先 Scan_Ref_Price（昨收/盘前），与 pending CSV 口径一致。"""
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


def _target_shares(ref_price, n_targets):
    """等权目标股数：每个目标标的分到 50000/n 的市值，按参考价换算股数（向下取整）。"""
    if not ref_price or n_targets <= 0:
        return 0
    try:
        price = float(str(ref_price).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0
    if price <= 0:
        return 0
    per = PORTFOLIO_TARGET_BUDGET / n_targets
    return max(0, int(per // price))


def build_portfolio_target_rows(chosen_items, held_positions, scan_date):
    """构造目标持仓行（dict 列表）。幂等键 = Scan_Date + Ticker（整文件覆盖即幂等）。

    chosen_items: scan 最终推荐（to_write，Core/Observation）
    held_positions: 当前持仓 Ticker 列表（portfolio_50000_positions.csv OPEN）
    返回 (rows, n_targets)：rows 含 BUY/HOLD/SELL；n_targets = 推荐标的数（用于等权）。
    """
    held = {str(t).upper() for t in (held_positions or [])}
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
    rows = []
    for r in rec:
        action = "HOLD" if r["Ticker"] in held else "BUY"
        rows.append({
            "Scan_Date": scan_date,
            "Ticker": r["Ticker"],
            "Action": action,
            "Target_Shares": _target_shares(r["Ref_Price"], n_targets),
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


def write_portfolio_target_csv(chosen_items, held_positions, scan_date):
    """落盘 portfolio_50000_target.csv（整文件覆盖 → 同天重跑幂等）。返回路径或 None。"""
    rows, _ = build_portfolio_target_rows(chosen_items, held_positions, scan_date)
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
