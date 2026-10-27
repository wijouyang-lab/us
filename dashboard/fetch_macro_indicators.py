#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取「美股宏观」九项指标 → dashboard/data/macro_indicators.json。

数据源（逐项 fail-closed，拿不到就 null，不猜）：
  1. 美国失业率                 FRED UNRATE
  2. 季调后非农业就业人口        FRED PAYEMS（展示月增，K）
  3. 未季调 CPI 年率            FRED CPIAUCNS（自算同月同比）
  4. 季调后 CPI 月率            FRED CPIAUCSL（自算环比）
  5. 密歇根消费者信心指数终值    FRED UMCSENT
  6. ISM 制造业 PMI             ISM 官网抓取（失败 → null）
  7. ADP 就业人数               FRED ADPMNUSNERSA（展示月增，K）
  8. 每周 EIA 原油库存          EIA 官网周表抓取（千桶）
  9. 每周初请失业金人数          FRED ICSA（展示 K）

只写这一个 JSON；不改 quant_*、不进账本、不调用 AI。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "dashboard" / "data" / "macro_indicators.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; US-Dashboard-Macro/1.0)"}


def _get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def fred_series(series_id: str):
    """返回 [(date_str, float)] 升序；失败返回 []。FRED 在部分 Runner 上很慢，重试并放宽超时。"""
    text = ""
    for attempt in range(1):
        try:
            text = _get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", timeout=8)
            break
        except Exception as exc:
            print(f"[WARN] FRED {series_id} 第 {attempt+1} 次失败：{exc}", file=sys.stderr)
            time.sleep(2)
    try:
        rows = []
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            d = (row.get("observation_date") or "").strip()
            v = (row.get(series_id) or "").strip()
            if not d or v in ("", "."):
                continue
            try:
                rows.append((d, float(v)))
            except ValueError:
                continue
        rows.sort(key=lambda x: x[0])
        return rows
    except Exception as exc:
        print(f"[WARN] FRED {series_id} 失败：{exc}", file=sys.stderr)
        return []


def _month_key(d: str) -> str:
    return d[:7]


def yoy(rows):
    """同月同比（%）：latest vs 去年同月。"""
    if not rows:
        return None
    latest_d, latest_v = rows[-1]
    target = _month_key(latest_d)[:4] + "-" + latest_d[5:7]
    ty, tm = int(target[:4]) - 1, int(target[5:7])
    for d, v in reversed(rows[:-1]):
        if d[:4] == str(ty) and int(d[5:7]) == tm and v:
            return round((latest_v / v - 1) * 100, 2)
    return None


def _item(key, name, value, unit, date, prev=None, change=None, source="", note=None):
    return {
        "key": key, "name": name, "value": value, "unit": unit,
        "date": date, "prev": prev, "change": change,
        "source": source, "note": note,
    }




TE_ALIASES = {
    "unrate": ["Unemployment Rate"],
    "core_cpi_yoy": ["Core Inflation Rate"],
    "nonfarm": ["Non Farm Payrolls", "Nonfarm Payrolls", "Nonfarm Payrolls Private"],
    "cpi_yoy": ["Inflation Rate"],
    "cpi_mom": ["Inflation Rate MoM"],
    "umich": ["Consumer Confidence", "Consumer Sentiment"],
    "adp": ["ADP Employment Change"],
    "claims": ["Initial Jobless Claims"],
}


def _te_values():
    """从 TradingEconomics 美国指标页抓 {key: 数值}（FRED 不可达时的兜底）。"""
    try:
        text = _get("https://tradingeconomics.com/united-states/indicators", timeout=30)
    except Exception as exc:
        print(f"[WARN] TE 指标页失败：{exc}", file=sys.stderr)
        return {}
    out = {}
    for key, aliases in TE_ALIASES.items():
        for name in aliases:
            pat = (r">\s*" + re.escape(name) + r"\s*</a></td>\s*<td[^>]*>\s*"
                   r"(?:<span[^>]*>)?\s*([-\d.,]+)")
            m = re.search(pat, text)
            if m:
                try:
                    out[key] = float(m.group(1).replace(",", ""))
                    break
                except ValueError:
                    continue
    return out


def build_items():
    items = []

    # 1. 失业率
    rows = fred_series("UNRATE")
    if rows:
        d, v = rows[-1]
        prev = rows[-2][1] if len(rows) > 1 else None
        items.append(_item("unrate", "美国失业率", round(v, 1), "%", d, prev,
                           round(v - prev, 1) if prev is not None else None, "FRED UNRATE"))
    else:
        items.append(_item("unrate", "美国失业率", None, "%", None, source="FRED UNRATE"))

    # 2. 季调后非农（月增，K）
    rows = fred_series("PAYEMS")
    if rows and len(rows) >= 2:
        d, v = rows[-1]
        prev = rows[-2][1]
        chg = round(v - prev, 0)
        prev_chg = round(rows[-2][1] - rows[-3][1], 0) if len(rows) >= 3 else None
        items.append(_item("nonfarm", "季调后非农业就业人口", chg, "K", d, prev_chg,
                           chg, "FRED PAYEMS（月增）", "单位：千人"))
    else:
        items.append(_item("nonfarm", "季调后非农业就业人口", None, "K", None,
                           source="FRED PAYEMS（月增）"))

    # 3. 未季调 CPI 年率
    rows = fred_series("CPIAUCNS")
    y = yoy(rows)
    if rows:
        d = rows[-1][0]
        prev_d = rows[-13][0] if len(rows) >= 13 else None
        prev_y = None
        if len(rows) >= 14:
            # 上一期同比（用上一期与其去年同月）
            sub = rows[:-1]
            prev_y = yoy(sub)
        items.append(_item("cpi_yoy", "未季调CPI年率", y, "%", d, prev_y,
                           round(y - prev_y, 2) if (y is not None and prev_y is not None) else None,
                           "FRED CPIAUCNS"))
    else:
        items.append(_item("cpi_yoy", "未季调CPI年率", None, "%", None, source="FRED CPIAUCNS"))

    # 3b. 核心 CPI 年率
    rows = fred_series("CPILFESL")
    y2 = yoy(rows)
    if rows:
        d2 = rows[-1][0]
        prev_y2 = yoy(rows[:-1]) if len(rows) >= 14 else None
        items.append(_item("core_cpi_yoy", "核心CPI年率", y2, "%", d2, prev_y2,
                           round(y2 - prev_y2, 2) if (y2 is not None and prev_y2 is not None) else None,
                           "FRED CPILFESL"))
    else:
        items.append(_item("core_cpi_yoy", "核心CPI年率", None, "%", None,
                           source="FRED CPILFESL"))

    # 4. 季调后 CPI 月率
    rows = fred_series("CPIAUCSL")
    if rows and len(rows) >= 2:
        d, v = rows[-1]
        prev = rows[-2][1]
        mom = round((v / prev - 1) * 100, 2) if prev else None
        items.append(_item("cpi_mom", "季调后CPI月率", mom, "%", d, None, None, "FRED CPIAUCSL"))
    else:
        items.append(_item("cpi_mom", "季调后CPI月率", None, "%", None, source="FRED CPIAUCSL"))

    # 5. 密歇根消费者信心指数终值
    rows = fred_series("UMCSENT")
    if rows:
        d, v = rows[-1]
        prev = rows[-2][1] if len(rows) > 1 else None
        items.append(_item("umich", "密歇根大学消费者信心指数终值", round(v, 1), "", d, prev,
                           round(v - prev, 1) if prev is not None else None, "FRED UMCSENT"))
    else:
        items.append(_item("umich", "密歇根大学消费者信心指数终值", None, "", None,
                           source="FRED UMCSENT"))

    # 6. ISM 制造业 PMI（官网抓取，失败 null）
    items.append(_ism_pmi())

    # 7. ADP 就业人数（月增，K）
    rows = fred_series("ADPMNUSNERSA")
    if rows and len(rows) >= 2:
        d, v = rows[-1]
        prev = rows[-2][1]
        scale = 1000.0 if v > 1e7 else 1.0   # 该序列可能以「人」或「千人」计，按量级归一
        chg = round((v - prev) / scale, 0)
        prev_chg = round((prev - rows[-3][1]) / scale, 0) if len(rows) >= 3 else None
        items.append(_item("adp", "ADP就业人数", chg, "K", d, prev_chg, chg,
                           "FRED ADPMNUSNERSA（月增）", "单位：千人"))
    else:
        items.append(_item("adp", "ADP就业人数", None, "K", None,
                           source="FRED ADPMNUSNERSA（月增）"))

    # 8. 每周 EIA 原油库存（千桶）
    items.append(_eia_crude())

    # 9. 每周初请失业金人数（K）
    rows = fred_series("ICSA")
    if rows:
        d, v = rows[-1]
        prev = rows[-2][1] if len(rows) > 1 else None
        items.append(_item("claims", "每周初请失业金人数", round(v / 1000, 0), "K", d,
                           round(prev / 1000, 0) if prev is not None else None,
                           round((v - prev) / 1000, 0) if prev is not None else None,
                           "FRED ICSA", "单位：千人"))
    else:
        items.append(_item("claims", "每周初请失业金人数", None, "K", None, source="FRED ICSA"))

    # FRED 被封 / 失败时，用 TradingEconomics 指标页兜底（只补空值）
    if any(i["value"] is None and i["key"] in TE_ALIASES for i in items):
        te = _te_values()
        for it in items:
            if it["value"] is None and it["key"] in te:
                it["value"] = te[it["key"]]
                it["source"] = "TradingEconomics（FRED 不可用时的兜底）"
        items_ok = sum(1 for i in items if i["value"] is not None)
        print(f"[INFO] TE 兜底后有值 {items_ok}/{len(items)}", file=sys.stderr)

    for it in items:
        if it["value"] is None:
            it["source_status"] = "missing"
        elif "TradingEconomics" in str(it.get("source") or ""):
            it["source_status"] = "fallback"
        else:
            it["source_status"] = "primary"
    return items


def _ism_pmi():
    urls = [
        "https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/",
        "https://tradingeconomics.com/united-states/manufacturing-pmi",
    ]
    for url in urls:
        try:
            text = _get(url, timeout=15)
            m = re.search(r"(?:ISM )?Manufacturing PMI[^0-9]{0,160}([0-9]{2}\.[0-9])", text)
            if not m:
                m = re.search(r"PMI[^0-9]{0,60}([0-9]{2}\.[0-9])", text)
            if m:
                v = float(m.group(1))
                if 20 <= v <= 80:
                    return _item("ism", "ISM制造业PMI", v, "", None, source=url.split("/")[2])
        except Exception as exc:
            print(f"[WARN] ISM 抓取失败 {url}: {exc}", file=sys.stderr)
    return _item("ism", "ISM制造业PMI", None, "", None, source="ISM 官网（暂不可用）")


def _eia_crude():
    try:
        text = _get("https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WCESTUS1&f=W",
                    timeout=25)
        pairs = re.findall(
            r"<td class='B5'>(\d{2})/(\d{2})&nbsp;</td>\s*<td class='B3'>([\d,]+)&nbsp;",
            text)
        if pairs:
            _, _, v = pairs[-1]
            val = int(v.replace(",", ""))
            prev = int(pairs[-2][2].replace(",", "")) if len(pairs) > 1 else None
            return _item("eia_crude", "每周EIA原油库存", val, "千桶", None,
                         prev, (val - prev) if prev is not None else None,
                         "EIA 周报", "不含战略储备（SPR）")
    except Exception as exc:
        print(f"[WARN] EIA 抓取失败：{exc}", file=sys.stderr)
    return _item("eia_crude", "每周EIA原油库存", None, "千桶", None, source="EIA 周报")


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
    ap = argparse.ArgumentParser(description="抓取美股宏观九项指标")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    items = build_items()
    ok = sum(1 for i in items if i["value"] is not None)
    payload = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "FRED + ISM + EIA",
        "count": len(items),
        "ok": ok,
        "items": items,
    }
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    _atomic_write(Path(args.out), payload)
    print(f"[OK] 宏观指标 {ok}/{len(items)} 项有值 -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
