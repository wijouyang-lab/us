#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CPI / 核心CPI「预期 vs 实际」AI 解读（仅在数据变化时调用一次）。

输入：dashboard/data/macro_forecast.json（预期/实际/差值，人工或脚本维护）
输出：dashboard/data/macro_cpi_ai.json（signature + analysis + model + generated_at）

规则：
  · 先算 signature（CPI 与核心CPI 的 期间/预期/实际）；
  · 与旧文件 signature 相同 → 直接退出 0，**不调用 AI**、不改文件；
  · 不同 → 调一次 ClawSocket 生成 2–4 句中文解读，写回；
  · 无密钥 / 模型失败 → 保留旧文件，退出 0（前端继续显示旧解读或空）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

REPO = Path(__file__).resolve().parent.parent
FORECAST = REPO / "dashboard" / "data" / "macro_forecast.json"
OUT = REPO / "dashboard" / "data" / "macro_cpi_ai.json"

SYSTEM = (
    "你是宏观数据解读助手。只根据给定事实写 2-4 句中文，解释 CPI/核心CPI 的"
    "预期差意味着什么、可能怎样影响利率预期与市场波动；不得编造数字、不得给买卖建议。"
    "输出纯文本，不要 JSON、不要标题。"
)


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def pick_rows(payload):
    rows = []
    for it in (payload or {}).get("items") or []:
        ind = str(it.get("indicator") or "")
        if "CPI" in ind:
            rows.append({
                "indicator": ind,
                "period": it.get("period"),
                "forecast": it.get("forecast"),
                "actual": it.get("actual"),
                "surprise": it.get("surprise"),
            })
    return rows


def signature(rows) -> str:
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_prompt(rows):
    lines = ["美国 CPI 数据（来自财经日历，单位 %）："]
    for r in rows:
        lines.append(
            f"- {r['indicator']} {r.get('period') or ''}：预期 {r['forecast']}，"
            f"实际 {r['actual']}，差值 {r['surprise']}pp"
        )
    lines.append("请用中文简要说明预期差的方向、对加息/降息预期的影响、以及市场可能如何反应。")
    return "\n".join(lines)


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
    ap = argparse.ArgumentParser(description="CPI 预期差 AI 解读（仅在变化时调用）")
    ap.add_argument("--forecast", default=str(FORECAST))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    payload = _load(Path(args.forecast))
    rows = pick_rows(payload)
    if not rows:
        print("[WARN] macro_forecast.json 没有 CPI 行，跳过", file=sys.stderr)
        return 0

    sig = signature(rows)
    old = _load(Path(args.out)) or {}
    if old.get("signature") == sig and old.get("analysis"):
        print("[SKIP] CPI 预期数据未变化，不调用 AI", file=sys.stderr)
        return 0

    result = {
        "schema": 1,
        "signature": sig,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": None,
        "analysis": None,
        "items": rows,
    }

    try:
        from ai_router import gpt_generate_text
        text = gpt_generate_text(
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": build_prompt(rows)}],
            max_tokens=500,
            reasoning_effort="low",
            model=os.environ.get("MACRO_CPI_AI_MODEL") or None,
        )
        result["analysis"] = (text or "").strip()[:800] or None
        result["model"] = os.environ.get("MACRO_CPI_AI_MODEL") or "default"
    except Exception as exc:
        print(f"[WARN] CPI AI 失败：{exc}", file=sys.stderr)
        return 0

    if not result["analysis"]:
        return 0
    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    _atomic_write(Path(args.out), result)
    print("[OK] CPI AI 解读已更新", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
