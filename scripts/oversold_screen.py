#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""超跌观察候选生成器（规则版，非量化研究产出）。

数据来源：`quant_factor_snapshot.csv`（Scan 落盘的全市场因子快照，只读）。
输出：`dashboard/data/oversold_candidates.json`（Dashboard 只读展示）。

规则（固定、透明、未做参数优化/回测）：
  · RSI_14        ≤ 32        超卖
  · Bias_Pct      ≤ -8        相对 MA20 明显偏离
  · ZScore_20D    ≤ -1.5      20 日标准分低位
  · Price         ≥ 5         剔除低价股
  · 1.5 ≤ ATR_Pct ≤ 9         剔除过静/过烈
  · Volume_Ratio_20D ≥ 0.6    保留基本流动性

评分 = 0.4×RSI 深度 + 0.3×Bias 深度 + 0.3×ZScore 深度（0-100，纯展示排序）。
参考止损 = Price × (1 − min(12%, 1.5×ATR%))，仅为观察用参考位。

注意：本脚本**不修改** quant_* 研究文件、不写 Quant 板块、不产生任何交易；
规则与阈值写死在这里，方便复核。若快照缺失/过期，保留旧文件并退出 0。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = REPO_ROOT / "quant_factor_snapshot.csv"
DEFAULT_OUT = REPO_ROOT / "dashboard" / "data" / "oversold_candidates.json"

MIN_RSI, MAX_RSI = 0.0, 32.0
MAX_BIAS = -8.0
MAX_Z = -1.5
MIN_PRICE = 5.0
MIN_ATR, MAX_ATR = 1.5, 9.0
MIN_VOL_RATIO = 0.6
MAX_CANDIDATES = 10
OBSERVE_DAYS = 10
SOURCE = "规则筛选（RSI/Bias/ZScore + 流动性 + ATR）· 未回测 · 仅供观察"
NOTE = (
    "规则版观察信号：由 scripts/oversold_screen.py 从 quant_factor_snapshot.csv 生成，"
    "不是量化研究产出、未做回测；阈值固定写在脚本里，不构成投资建议。"
)


def _f(v):
    try:
        if v in (None, "", "nan", "None"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def load_latest_rows(path: Path):
    """读快照，取最新 Scan_Date 的全部行。返回 (asof, rows)。"""
    if not path.exists():
        return None, []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None, []
    asof = max((r.get("Scan_Date") or "") for r in rows)
    if not asof:
        return None, []
    latest = [r for r in rows if (r.get("Scan_Date") or "") == asof]
    # 同 ticker 去重（保留第一条）
    seen, uniq = set(), []
    for r in latest:
        tk = (r.get("Ticker") or "").upper().strip()
        if not tk or tk in seen:
            continue
        seen.add(tk)
        uniq.append(r)
    return asof, uniq


def score_row(rsi: float, bias: float, z: float) -> float:
    s_rsi = max(0.0, min(1.0, (MAX_RSI - rsi) / MAX_RSI))
    s_bias = max(0.0, min(1.0, -bias / 25.0))
    s_z = max(0.0, min(1.0, -z / 3.5))
    return round((0.4 * s_rsi + 0.3 * s_bias + 0.3 * s_z) * 100, 1)


def screen(rows, asof: str, max_candidates: int = MAX_CANDIDATES):
    out = []
    for r in rows:
        tk = (r.get("Ticker") or "").upper().strip()
        rsi = _f(r.get("RSI_14"))
        bias = _f(r.get("Bias_Pct"))
        z = _f(r.get("ZScore_20D"))
        px = _f(r.get("Price"))
        atr = _f(r.get("ATR_Pct"))
        vr = _f(r.get("Volume_Ratio_20D"))
        if not tk or None in (rsi, bias, z, px, atr):
            continue
        if not (MIN_RSI <= rsi <= MAX_RSI):
            continue
        if bias > MAX_BIAS or z > MAX_Z:
            continue
        if px < MIN_PRICE or not (MIN_ATR <= atr <= MAX_ATR):
            continue
        if vr is not None and vr < MIN_VOL_RATIO:
            continue

        ma20 = _f(r.get("MA20"))
        stop = round(px * (1 - min(0.12, 1.5 * atr / 100.0)), 2)
        try:
            until = (date.fromisoformat(asof) + timedelta(days=OBSERVE_DAYS)).isoformat()
        except ValueError:
            until = None
        out.append({
            "ticker": tk,
            "name": (r.get("Name") or "").strip() or None,
            "score": score_row(rsi, bias, z),
            "tag": "深度超跌" if bias <= -15 else "超跌反弹",
            "rsi": round(rsi, 1),
            "bias_pct": round(bias, 2),
            "drawdown_pct": round(_f(r.get("Momentum_20D_Pct")) or 0.0, 2),
            "zscore": round(z, 2),
            "atr_pct": round(atr, 2),
            "momentum_60d_pct": round(_f(r.get("Momentum_60D_Pct")) or 0.0, 2),
            "volume_ratio_20d": round(vr, 2) if vr is not None else None,
            "beta": round(_f(r.get("Beta_60D_SPY")), 3) if _f(r.get("Beta_60D_SPY")) is not None else None,
            "rs_20d_vs_spy": round(_f(r.get("Stock_RS_20D_vs_SPY")), 2) if _f(r.get("Stock_RS_20D_vs_SPY")) is not None else None,
            "market_regime": (r.get("Market_Regime") or "").strip() or None,
            "technical_score": _f(r.get("Technical_Score_25")),
            "event_score": _f(r.get("Event_Score")),
            "quant_score": _f(r.get("Quant_Score")),
            "snapshot_sector": (r.get("Sector") or "").strip() or None,
            "sector": (r.get("Sector") or "").strip() or None,
            "ref_price": round(px, 2),
            "stop_loss": stop,
            "confirm": (
                "RSI 回升过 35" + (f" 且站回 MA20 ${ma20:.2f}" if ma20 else "")
            ),
            "invalid": f"跌破参考止损 ${stop:.2f} 或 RSI 继续下行",
            "observe_until": until,
            "reason": (
                f"RSI {rsi:.1f} / Bias {bias:.1f}% / ZScore {z:.2f}；"
                f"ATR {atr:.1f}% · 20日量比 {vr if vr is not None else '—'}；"
                f"板块 {r.get('Sector') or '—'}。规则版筛选，未回测。"
            ),
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:max_candidates]


def build_payload(asof: str, candidates) -> dict:
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asof": asof,
        "source": SOURCE,
        "note": NOTE,
        "candidates": candidates,
    }


def _atomic_write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="从因子快照生成超跌观察候选（规则版）")
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--max", type=int, default=MAX_CANDIDATES)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    asof, rows = load_latest_rows(Path(args.snapshot))
    if not rows:
        print("[WARN] 因子快照缺失或为空，保留现有候选文件不动", file=sys.stderr)
        return 0

    cands = screen(rows, asof, args.max)
    payload = build_payload(asof, cands)
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    _atomic_write(Path(args.out), payload)
    print(f"[OK] {asof}：{len(cands)} 条候选 -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
