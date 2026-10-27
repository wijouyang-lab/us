#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CPI / 核心CPI 预期 vs 实际：自动写入 macro_forecast.json。

数据源：TradingEconomics 指标页正文
  · 实际值："... accelerated to 3.7% in September 2026 ..."
  · 预期值："... above market expectations of 3.6% ..."

只写 CPI 同比 / 核心CPI 同比两行；解析失败保留旧文件（fail-closed）。
不调用 AI、不改策略；前端已有「预期 vs 实际」渲染。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "dashboard" / "data" / "macro_forecast.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; US-Dashboard/1.0)"}

PAGES = [
    ("CPI 同比", "https://tradingeconomics.com/united-states/inflation-cpi"),
    ("核心CPI 同比", "https://tradingeconomics.com/united-states/core-inflation-rate"),
]

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse(text: str):
    """返回 (actual, forecast, previous, period) 或 None。"""
    m = re.search(r"(?:to|at) ([0-9]+\.[0-9])% in ([A-Z][a-z]+) (\d{4})", text)
    if not m:
        return None
    actual, month, year = float(m.group(1)), m.group(2), m.group(3)
    e = re.search(
        r"(?:above|below|exceeding|beating|missing|surpassing)[^.]{0,120}?"
        r"expectations? of ([0-9]+\.[0-9])%", text, re.I)
    p = re.search(r"from ([0-9]+\.[0-9])%", text)
    if not e:
        e = re.search(r"(?:expected|consensus)[^.]{0,60}?([0-9]+\.[0-9])%", text, re.I)
    if not e:
        return None
    period = f"{year}年{MONTHS.get(month, 0)}月"
    return actual, float(e.group(1)), (float(p.group(1)) if p else None), period


def build():
    rows = []
    for name, url in PAGES:
        try:
            got = parse(_get(url))
        except Exception as exc:
            print(f"[WARN] {name} 抓取失败：{exc}", file=sys.stderr)
            continue
        if not got:
            print(f"[WARN] {name} 解析失败（页面结构可能变了）", file=sys.stderr)
            continue
        actual, forecast, prev, period = got
        rows.append({
            "indicator": name,
            "period": period,
            "forecast": forecast,
            "actual": actual,
            "previous": prev,
            "unit": "%",
            "released_at": None,
            "impact": f"实际 {actual}% vs 预期 {forecast}%（{'+' if actual >= forecast else ''}"
                      f"{round(actual - forecast, 2)}pp）。",
        })
    if len(rows) < 2:
        return None
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of": None,
        "source": "TradingEconomics 指标页（自动解析）",
        "items": rows,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="自动更新 CPI 预期 vs 实际")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    payload = build()
    if not payload:
        print("[WARN] CPI 解析不足 2 条，保留旧 macro_forecast.json", file=sys.stderr)
        return 0
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=out.name + ".", suffix=".tmp", dir=str(out.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(f"[OK] 已更新 {len(payload['items'])} 条 CPI 预期差 -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
