#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成动态 watchlist（只读，不写仓库文件，输出到 stdout）。

优先级：K（持仓）> M（当日 Quant_Score Top10）> N（watchlist.txt 固定名单）
输出格式：每行一个 ticker；头部用 '#' 注释说明来源与降级情况。
上限：24 只（超出截断 N）。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
POSITIONS = REPO / "portfolio_50000_positions.csv"
SNAP = REPO / "quant_factor_snapshot.csv"
FIXED = REPO / "watchlist.txt"

MAX_TOTAL = 24
TOP_N = 10
NA = "N/A"


def read_csv(path: Path) -> list:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main() -> int:
    # ---------- K：持仓 ----------
    k_items = []
    for r in read_csv(POSITIONS):
        tk = (r.get("Ticker") or "").strip().upper()
        shares = fnum(r.get("Shares"))
        status = (r.get("Status") or "").strip().upper()
        if not tk or shares is None or shares <= 0:
            continue
        if status == "CLOSED":
            continue
        mv = fnum(r.get("Market_Value")) or 0.0
        k_items.append((tk, mv))
    k_items.sort(key=lambda x: -x[1])
    k_list = [t for t, _ in k_items]

    # ---------- M：当日 Quant_Score Top10 ----------
    rows = read_csv(SNAP)
    dates = sorted({(r.get("Scan_Date") or "") for r in rows if r.get("Scan_Date")})
    m_list, snap_date, stale = [], NA, False
    if rows and dates:
        snap_date = dates[-1]
        day = [r for r in rows if (r.get("Scan_Date") or "") == snap_date]
        scored = []
        for r in day:
            tk = (r.get("Ticker") or "").strip().upper()
            sc = fnum(r.get("Quant_Score"))
            if tk and sc is not None:
                scored.append((tk, sc))
        scored.sort(key=lambda x: -x[1])
        seen = set()
        for tk, _ in scored:
            if tk in seen:
                continue
            seen.add(tk)
            m_list.append(tk)
            if len(m_list) >= TOP_N:
                break
        # 是否"非今日"：以今天 ET 日期比较
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
            stale = snap_date != today
        except Exception:
            stale = False

    # ---------- N：固定名单 ----------
    n_list = []
    if FIXED.exists():
        for line in FIXED.read_text(encoding="utf-8-sig").splitlines():
            s = line.strip().upper()
            if not s or s.startswith("#"):
                continue
            n_list.append(s)

    # ---------- 去重（K > M > N）----------
    order, origin = [], {}
    for grp, tag in ((k_list, "K"), (m_list, "M"), (n_list, "N")):
        for tk in grp:
            if tk in origin:
                continue
            origin[tk] = tag
            order.append(tk)

    # 上限：截断 N
    if len(order) > MAX_TOTAL:
        keep = [t for t in order if origin[t] != "N"]
        rest = [t for t in order if origin[t] == "N"]
        order = (keep + rest)[:MAX_TOTAL]

    # ---------- 输出 ----------
    # stdout 只输出纯 ticker（ticker_brief.py --watchlist 按空白/逗号切分，不能含注释）
    out = sys.stdout
    for tk in order:
        out.write(tk + "\n")

    # 元信息写到 sidecar + stderr（不污染 watchlist 文件本身）
    meta_lines = [
        "# 动态 watchlist 元信息（scripts/build_watchlist.py 生成）",
        f"# 来源：K=持仓 {len(k_list)} / M=当日Top {len(m_list)} / N=固定 {len(n_list)}"
        f" ⇒ 去重后 {len(order)} 只（上限 {MAX_TOTAL}）",
        f"# 快照日期：{snap_date}",
    ]
    if stale:
        meta_lines.append(f"# ⚠️ 使用 {snap_date} 快照（非今日）")
    if not order:
        meta_lines.append("# 无可用数据")
    meta_lines.append("")
    meta_lines.append("Ticker,Source")
    for tk in order:
        meta_lines.append(f"{tk},{origin[tk]}")
    meta_path = REPO / "watchlist.dynamic.meta.txt"
    try:
        meta_path.write_bytes(("\n".join(meta_lines) + "\n").encode("utf-8"))
    except Exception:
        pass

    print(f"[build_watchlist] K={len(k_list)} M={len(m_list)} N={len(n_list)} "
          f"⇒ 去重后 {len(order)} 只 | 快照={snap_date}"
          f"{' (⚠️ 非今日)' if stale else ''}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
