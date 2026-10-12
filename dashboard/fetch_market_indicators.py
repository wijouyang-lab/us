#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 CNN 恐惧贪婪指数（F&G）+ CME FedWatch，落盘 market_indicators.json。

设计要点
--------
· **flag 门控**：本脚本只在 CI（dashboard-data.yml）于 ENABLE_MARKET_INDICATORS=='1'
  时被调用；flag 关时该步骤被 `if:` 跳过，本脚本根本不执行，dashboard 输出与现在
  逐字节一致。
· **两源独立**：F&G 与 FedWatch 各自独立 try/except，单源失败 → 该字段 null，不阻断另一源。
· **R1（不发布脏数据）**：两源**都**失败 → **不写文件**（dashboard_export 读不到文件 →
  payload 不含 market_indicators 键 → 前端隐藏），避免用 stale/空数据污染仪表盘。
· **包缺失即降级**：fear_greed / cme_fedwatch 未安装（如本沙箱或首次 CI）时 import 失败 →
  该源 null，不崩溃。continue-on-error 保证不拖垮整体刷新。
· **不调用任何 AI**：纯行情/概率数据，与 AI 无关。

输出结构见 SCHEMA；子源失败时对应字段为 null，`error` 记录失败原因（部分失败时仍写文件）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "market_indicators.v1"


# --------------------------------------------------------------------------- #
# 数据源 1：CNN 恐惧贪婪指数（fear-greed 包，绕过 Cloudflare）
# --------------------------------------------------------------------------- #
def fetch_fear_greed():
    """返回 (data, error)。data=None 表示本源失败。"""
    try:
        import fear_greed
    except Exception as e:  # 包未安装 / import 失败 → 降级为 null
        return None, f"fear_greed 包不可用：{e}"

    try:
        snap = fear_greed.get()
        # 30 日逐日历史（best-effort，失败不影响主快照）
        history_30d = []
        try:
            for pt in fear_greed.get_history(last="30"):
                history_30d.append(pt.to_dict())
        except Exception:
            history_30d = []

        return {
            "score": snap.get("score"),
            "rating": snap.get("rating"),
            "timestamp": snap.get("timestamp"),
            "subindicators": snap.get("indicators", {}) or {},
            "history_30d": history_30d,
        }, None
    except Exception as e:
        return None, f"F&G 抓取失败：{e}"


# --------------------------------------------------------------------------- #
# 数据源 2：CME FedWatch（cme-fedwatch 包）
# --------------------------------------------------------------------------- #
def _parse_range(label: str):
    """'4.25%-4.50%' -> (4.25, 4.50)；无法解析返回 (None, None)。"""
    s = (label or "").replace("%", "")
    parts = s.split("-")
    if len(parts) != 2:
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except (ValueError, TypeError):
        return None, None


def _normalize_fedwatch_probs(probs: dict, current_target: str) -> dict:
    """把 FedWatch 的『目标区间标签→概率』归一化为动作语义。

    相对当前目标区间：相同 → hold；更低 → cut_Nbp；更高 → hike_Nbp。
    无法解析的标签原样保留（兜底，绝不丢弃数据）。
    """
    cur_lo, _ = _parse_range(current_target)
    out: dict = {}
    for label, pct in (probs or {}).items():
        lo, _ = _parse_range(label)
        if lo is None:
            out[label] = pct
            continue
        if label == current_target or cur_lo is None or lo == cur_lo:
            out["hold"] = pct
        elif lo < cur_lo:
            out[f"cut_{int(round((cur_lo - lo) * 100))}bp"] = pct
        else:
            out[f"hike_{int(round((lo - cur_lo) * 100))}bp"] = pct
    return out


def fetch_fedwatch():
    """返回 (data, error)。data=None 表示本源失败。"""
    try:
        import cme_fedwatch
    except Exception as e:  # 包未安装 / import 失败 → 降级为 null
        return None, f"cme_fedwatch 包不可用：{e}"

    try:
        raw = cme_fedwatch.get_probabilities("next")
        meetings = raw.get("meetings") or []
        if not meetings:
            return None, "FedWatch 无 upcoming meeting"
        m = meetings[0]
        current_target = raw.get("current_target") or ""
        return {
            "next_meeting": m.get("date"),
            "current_target": current_target or None,
            "effr": raw.get("effr"),
            "trade_date": raw.get("trade_date"),
            "probabilities": _normalize_fedwatch_probs(
                m.get("probabilities") or {}, current_target),
            "source": "cme",
        }, None
    except Exception as e:
        return None, f"FedWatch 抓取失败：{e}"


# --------------------------------------------------------------------------- #
# 组装 + 落盘
# --------------------------------------------------------------------------- #
def build_payload(fear_greed_data, fedwatch_data, errors: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fear_greed": fear_greed_data,
        "fedwatch": fedwatch_data,
        "error": errors or None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fetch CNN F&G + CME FedWatch")
    ap.add_argument("--out", default="dashboard/data/market_indicators.json",
                    help="输出 JSON 路径")
    ap.add_argument("--no-fear-greed", action="store_true",
                    help="跳过 F&G 抓取（测试 / 降级用）")
    ap.add_argument("--no-fedwatch", action="store_true",
                    help="跳过 FedWatch 抓取（测试 / 降级用）")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    errors: dict = {}
    fg, fw = None, None

    if args.no_fear_greed:
        errors["fear_greed"] = "skipped (--no-fear-greed)"
    else:
        fg, e = fetch_fear_greed()
        if e:
            errors["fear_greed"] = e

    if args.no_fedwatch:
        errors["fedwatch"] = "skipped (--no-fedwatch)"
    else:
        fw, e = fetch_fedwatch()
        if e:
            errors["fedwatch"] = e

    # R1：两源都失败 → 不写文件（dashboard_export 读不到 → payload 不含键 → 前端隐藏）
    if fg is None and fw is None:
        print(f"[market_indicators] 两数据源均失败，按 R1 不写文件。errors={errors}")
        return 1

    payload = build_payload(fg, fw, errors)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[market_indicators] 已写入 {out} "
          f"（fear_greed={'OK' if fg else 'null'}，"
          f"fedwatch={'OK' if fw else 'null'}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
