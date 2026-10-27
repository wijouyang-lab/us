#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经济数据「预期 vs 实际」自动写入 macro_forecast.json。

数据源：TradingEconomics 各指标页正文
  · 实际："... to 3.7% in September 2026" / "rose by 29K in September"
  · 预期："... above market expectations of 3.6%"

按 key 对齐 macro_indicators（unrate/nonfarm/cpi_yoy/core_cpi_yoy/cpi_mom/
umich/ism/adp/claims）。解析不到的指标跳过；全部失败则保留旧文件。
不调用 AI。
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

PAGES = {
    "unrate": ("失业率", "https://tradingeconomics.com/united-states/unemployment-rate"),
    "nonfarm": ("季调后非农", "https://tradingeconomics.com/united-states/nonfarm-payrolls"),
    "cpi_yoy": ("未季调CPI年率", "https://tradingeconomics.com/united-states/inflation-cpi"),
    "core_cpi_yoy": ("核心CPI年率", "https://tradingeconomics.com/united-states/core-inflation-rate"),
    "cpi_mom": ("季调后CPI月率", "https://tradingeconomics.com/united-states/inflation-rate-mom"),
    "umich": ("密歇根消费者信心", "https://tradingeconomics.com/united-states/consumer-confidence"),
    "ism": ("ISM制造业PMI", "https://tradingeconomics.com/united-states/manufacturing-pmi"),
    "adp": ("ADP就业人数", "https://tradingeconomics.com/united-states/adp-employment-change"),
    "claims": ("初请失业金", "https://tradingeconomics.com/united-states/initial-jobless-claims"),
}

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse(text: str):
    """返回 (actual, forecast, unit, period) 或 None。"""
    m = re.search(
        r"(?:rose|fell|increased|decreased|was|stood at|to|at|of|by)\s+(?:by\s+)?"
        r"([0-9]+(?:\.[0-9]+)?)(%|K)? in ([A-Z][a-z]+)(?: (\d{4}))?", text)
    if not m:
        return None
    actual = float(m.group(1))
    unit = m.group(2) or "%"
    month = m.group(3)
    year = m.group(4) or str(datetime.now().year)
    e = re.search(
        r"(?:above|below|exceeding|beating|missing|surpassing)[^.]{0,120}?"
        r"expectations? of ([0-9]+(?:\.[0-9]+)?)(%|K)?", text, re.I)
    if not e:
        e = re.search(r"(?:expected|consensus)[^.]{0,60}?([0-9]+(?:\.[0-9]+)?)(%|K)?",
                      text, re.I)
    if not e:
        return None
    period = f"{year}年{MONTHS.get(month, 0)}月"
    return actual, float(e.group(1)), unit, period


def build():
    rows = []
    for key, (name, url) in PAGES.items():
        try:
            got = parse(_get(url))
        except Exception as exc:
            print(f"[WARN] {name} 抓取失败：{exc}", file=sys.stderr)
            continue
        if not got:
            print(f"[WARN] {name} 解析不到预期/实际，跳过", file=sys.stderr)
            continue
        actual, forecast, unit, period = got
        diff = round(actual - forecast, 2)
        rows.append({
            "key": key,
            "indicator": name,
            "period": period,
            "forecast": forecast,
            "actual": actual,
            "previous": None,
            "unit": unit,
            "released_at": None,
            "impact": f"实际 {actual}{unit} vs 预期 {forecast}{unit}（{'+' if diff >= 0 else ''}{diff}）。",
        })
    if not rows:
        return None

    # 用 macro_indicators 的实际值覆盖 TE 页面解析值，保证卡片/AI/预期差一致
    try:
        mi = json.loads((REPO / "dashboard" / "data" / "macro_indicators.json")
                        .read_text(encoding="utf-8"))
        actual_map = {i.get("key"): i.get("value") for i in (mi.get("items") or [])}
        for r in rows:
            v = actual_map.get(r["key"])
            if v is not None:
                r["actual"] = round(float(v), 2)
                diff = round(r["actual"] - r["forecast"], 2)
                r["impact"] = (f"实际 {r['actual']}{r['unit']} vs 预期 {r['forecast']}{r['unit']}"
                               f"（{'+' if diff >= 0 else ''}{diff}）。")
    except Exception as exc:
        print(f"[WARN] 用宏观指标覆盖实际值失败：{exc}", file=sys.stderr)

    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of": None,
        "source": "TradingEconomics 指标页（自动解析）",
        "items": rows,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="自动更新经济数据预期 vs 实际")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    payload = build()
    if not payload:
        print("[WARN] 全部指标解析失败，保留旧 macro_forecast.json", file=sys.stderr)
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
    print(f"[OK] 已更新 {len(payload['items'])} 条预期差 -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
