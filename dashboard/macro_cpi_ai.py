#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经济数据「预期 vs 实际」AI 解读（只在数据变化时调用一次）。

输入：dashboard/data/macro_forecast.json（每条含 key/indicator/forecast/actual）
输出：dashboard/data/macro_cpi_ai.json
  {signature, model, generated_at, analyses: {key: "..."}, analysis: "CPI 汇总"}

行为：
  · signature = 所有行 (key,forecast,actual) 的哈希；与旧文件相同 → 跳过，不调用 AI；
  · 变化时才调一次模型，返回 JSON {key: 分析}；
  · 无密钥/失败 → 保留旧文件，退出 0。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
FORECAST = REPO / "dashboard" / "data" / "macro_forecast.json"
OUT = REPO / "dashboard" / "data" / "macro_cpi_ai.json"

SYSTEM = (
    "你是宏观数据解读助手。用户给出若干美国经济指标的预期与实际值。"
    "对每个指标写 1-2 句中文，解释预期差的方向及对利率预期/市场波动的含义；"
    "只输出 JSON 对象：{指标key: 解读文本}，不要多余字段、不要编造数字、不要给买卖建议。"
)


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def rows_of(payload):
    rows = []
    for it in (payload or {}).get("items") or []:
        key = str(it.get("key") or "").strip()
        if not key:
            continue
        rows.append({
            "key": key,
            "indicator": it.get("indicator"),
            "forecast": it.get("forecast"),
            "actual": it.get("actual"),
            "unit": it.get("unit") or "%",
        })
    return rows


def signature(rows) -> str:
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_prompt(rows):
    lines = ["美国经济数据（预期 vs 实际）："]
    for r in rows:
        lines.append(f"- key={r['key']} {r['indicator']}：预期 {r['forecast']}{r['unit']}，"
                     f"实际 {r['actual']}{r['unit']}")
    lines.append("请按 key 输出 JSON 对象，每个 key 一段 1-2 句中文解读。")
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
    ap = argparse.ArgumentParser(description="经济数据预期差 AI 解读（仅变化时）")
    ap.add_argument("--forecast", default=str(FORECAST))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    payload = _load(Path(args.forecast))
    rows = rows_of(payload)
    if not rows:
        print("[WARN] macro_forecast.json 无可用行，跳过", file=sys.stderr)
        return 0

    sig = signature(rows)
    old = _load(Path(args.out)) or {}
    if old.get("signature") == sig and old.get("analyses"):
        print("[SKIP] 经济数据未变化，不调用 AI", file=sys.stderr)
        return 0

    result = {
        "schema": 1,
        "signature": sig,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": None,
        "analyses": {},
        "analysis": None,
        "items": rows,
    }

    try:
        from ai_router import gpt_generate_text, extract_json_object
        text = gpt_generate_text(
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": build_prompt(rows)}],
            max_tokens=3000,
            reasoning_effort="low",
            model=os.environ.get("MACRO_CPI_AI_MODEL") or None,
        )
        obj = extract_json_object(text)
        if not isinstance(obj, dict):
            m = re.search(r"\{.*\}", text or "", re.S)
            try:
                obj = json.loads(m.group(0)) if m else {}
            except Exception:
                obj = {}
        for r in rows:
            v = obj.get(r["key"]) if isinstance(obj, dict) else None
            if isinstance(v, str) and v.strip():
                result["analyses"][r["key"]] = v.strip()[:400]
        result["model"] = os.environ.get("MACRO_CPI_AI_MODEL") or "default"
        result["analysis"] = result["analyses"].get("cpi_yoy")
    except Exception as exc:
        print(f"[WARN] 经济数据 AI 失败：{exc}", file=sys.stderr)
        return 0

    if not result["analyses"]:
        return 0
    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    _atomic_write(Path(args.out), result)
    print(f"[OK] 已更新 {len(result['analyses'])} 条解读", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
