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

def _norm_unit(u):
    if not u:
        return "%"
    u = u.strip()
    if u in ("thousand",):
        return "K"
    if u in ("million",):
        return "M"
    return u


MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


CAL_URL = "https://tradingeconomics.com/united-states/calendar"
CAL_EVENTS = {
    "nonfarm": "Non Farm Payrolls",
    "claims": "Initial Jobless Claims",
}


def calendar_consensus():
    """从 TE 日历抓一致性预期：{key: (forecast, unit)}；取第一条有 consensus 的行。"""
    try:
        text = _get(CAL_URL)
    except Exception as exc:
        print(f"[WARN] TE 日历抓取失败：{exc}", file=sys.stderr)
        return {}
    rows = re.split(r"<tr[^>]*>", text)
    out = {}
    for row in rows:
        m = re.search(r"calendar-event'[^>]*>\s*([^<]+?)\s*</a>", row)
        if not m:
            continue
        name = m.group(1).strip()
        key = next((k for k, v in CAL_EVENTS.items() if v == name), None)
        if not key:
            continue
        c = re.search(r"id=['\"]consensus['\"][^>]*>\s*([^<]*)<", row)
        a = re.search(r"id=['\"]actual['\"][^>]*>\s*([^<]*)<", row)
        if not c or not c.group(1).strip():
            continue
        raw = c.group(1).strip()
        mm = re.match(r"([-0-9.]+)\s*([KMB%]?)", raw)
        if not mm:
            continue
        released = bool(a and a.group(1).strip())
        prev = out.get(key)
        # 已发布行优先；否则保留第一条有 consensus 的
        if prev is None or (released and not prev[2]):
            out[key] = (float(mm.group(1)), mm.group(2) or "%", released)
    return {k: (v[0], v[1]) for k, v in out.items()}


def fmp_nfp():
    """FMP 经济日历：美国 Nonfarm Payrolls 的 estimate。优先 stable，再回退 v3。"""
    from datetime import date, timedelta
    keys = [os.environ.get("FMP_KEY_1"), os.environ.get("FMP_KEY_2")]
    keys = [k for k in keys if k]
    if not keys:
        return None
    start = (date.today() - timedelta(days=45)).isoformat()
    end = (date.today() + timedelta(days=15)).isoformat()
    urls = []
    for k in keys:
        urls.append(f"https://financialmodelingprep.com/stable/economic-calendar?from={start}&to={end}&apikey={k}")
        urls.append(f"https://financialmodelingprep.com/api/v3/economic_calendar?from={start}&to={end}&apikey={k}")
    for url in urls:
        try:
            data = _json(url)
        except Exception as exc:
            print(f"[WARN] FMP 日历失败：{exc}", file=sys.stderr)
            continue
        rows = data if isinstance(data, list) else (data.get("data") or [])
        if not rows:
            continue
        hits = []
        for r in rows:
            ev = str(r.get("event") or "").lower()
            if r.get("country") not in ("US", "United States"):
                continue
            if "nonfarm payroll" not in ev or "private" in ev:
                continue
            est = r.get("estimate")
            if est in (None, ""):
                continue
            try:
                val = float(str(est).replace(",", "").replace("%", ""))
            except ValueError:
                continue
            hits.append((str(r.get("date") or ""), val))
        if hits:
            hits.sort(key=lambda x: x[0])
            val = hits[-1][1]
            unit = "K" if abs(val) > 5 else "%"
            return {"forecast": val, "unit": unit}
    return None


def finnhub_nfp():
    """Finnhub 经济日历：美国 Nonfarm Payrolls 的 estimate。免费档可能不含该接口。"""
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        return None
    from datetime import date, timedelta
    start = (date.today() - timedelta(days=45)).isoformat()
    end = (date.today() + timedelta(days=15)).isoformat()
    url = (f"https://finnhub.io/api/v1/calendar/economic?from={start}&to={end}"
           f"&token={key}")
    try:
        data = _json(url)
    except Exception as exc:
        print(f"[WARN] Finnhub 日历失败：{exc}", file=sys.stderr)
        return None
    rows = data.get("economicCalendar") or []
    hits = []
    for r in rows:
        ev = str(r.get("event") or "").lower()
        if r.get("country") == "US" and "nonfarm payroll" in ev and not ev.startswith("private"):
            est = r.get("estimate")
            if est is None:
                continue
            raw = str(est).replace(",", "").replace("%", "")
            try:
                val = float(raw)
            except ValueError:
                continue
            unit = "K" if abs(val) > 5 else "%"
            hits.append((r.get("date") or "", val, unit))
    if not hits:
        return None
    hits.sort(key=lambda x: x[0])
    return {"forecast": hits[-1][1], "unit": hits[-1][2]}


def _json(url: str):
    return json.loads(_get(url))


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse(text: str):
    """返回 (actual, forecast, unit, period) 或 None。"""
    unit = "%"
    m = re.search(
        r"(?:added|gained|rose|fell|increased|decreased|was|stood at|to|at|of|by)\s+"
        r"(?:by\s+)?([0-9]+(?:\.[0-9]+)?)\s*(%|K|M|thousand|million)?\s+"
        r"(?:jobs\s+)?in\s+([A-Z][a-z]+)(?:\s+of)?\s*(\d{4})?", text)
    if m:
        actual = float(m.group(1))
        unit = _norm_unit(m.group(2))
        month = m.group(3)
        year = m.group(4) or str(datetime.now().year)
    else:
        m2 = re.search(
            r"(?:to|at)\s+([0-9]+(?:\.[0-9]+)?)\s*(%|K|M|thousand|million)?\s+"
            r"in the week", text)
        if not m2:
            return None
        actual = float(m2.group(1))
        unit = _norm_unit(m2.group(2))
        month, year = "Week", str(datetime.now().year)

    e = re.search(
        r"expectations?\s+of\s+([0-9]+(?:\.[0-9]+)?)\s*(%|K|M|thousand|million)?",
        text, re.I)
    if not e:
        e = re.search(
            r"expectations?\s+for\s+(?:a\s+)?([0-9]+(?:\.[0-9]+)?)\s*"
            r"(%|K|M|thousand|million)?", text, re.I)
    if not e:
        e = re.search(r"(?:expected|consensus)[^.]{0,60}?([0-9]+(?:\.[0-9]+)?)"
                      r"\s*(%|K|M|thousand|million)?", text, re.I)
    if not e:
        return None
    period = f"{year}年{MONTHS.get(month, 0)}月" if month in MONTHS else "当周"
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
    # 日历兜底：非农 / 初请（指标页没有 consensus 措辞）
    try:
        mi_now = json.loads((REPO / "dashboard" / "data" / "macro_indicators.json")
                            .read_text(encoding="utf-8"))
        actual_now = {i.get("key"): i.get("value") for i in (mi_now.get("items") or [])}
    except Exception:
        actual_now = {}
    names = {"nonfarm": "季调后非农", "claims": "初请失业金"}
    for key, (fc, unit) in calendar_consensus().items():
        if any(r["key"] == key for r in rows):
            continue
        act = actual_now.get(key)
        if act is None:
            continue
        rows.append({
            "key": key, "indicator": names.get(key, key), "period": "最新",
            "forecast": fc, "actual": round(float(act), 2), "previous": None,
            "unit": unit, "released_at": None, "impact": "",
        })

    fh = fmp_nfp() or finnhub_nfp()
    if fh and not any(r["key"] == "nonfarm" for r in rows):
        act = actual_now.get("nonfarm")
        if act is not None:
            rows.append({
                "key": "nonfarm", "indicator": "季调后非农", "period": "最新",
                "forecast": fh["forecast"], "actual": round(float(act), 2),
                "previous": None, "unit": fh["unit"], "released_at": None, "impact": "",
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
