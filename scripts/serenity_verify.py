#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""serenity-skill 供应链研究：联网核验层（只补证据，不改排名）。

输入：dashboard/data/skill_serenity.json（priorities[].ticker）
输出：dashboard/data/serenity_verified.json

核验项（全部 fail-closed，找不到就写 missing，不补结论）：
  · 下次财报日（yfinance calendar）
  · 最近 3 份 SEC 文件（8-K / 10-Q / 10-K，data.sec.gov）
  · 最近新闻标题（dashboard_data.json 的 ticker_news）

不调用 AI、不改 skill 的 priority_rank、不构成买入建议。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "dashboard" / "data" / "skill_serenity.json"
DATA = REPO / "dashboard" / "data" / "dashboard_data.json"
OUT = REPO / "dashboard" / "data" / "serenity_verified.json"
SEC_UA = {"User-Agent": "US-Dashboard research admin@example.com"}
FORMS = {"8-K", "10-Q", "10-K"}


def _get(url: str, headers=None, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=headers or SEC_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _json(url: str, headers=None, timeout: int = 20):
    return json.loads(_get(url, headers=headers, timeout=timeout))


_CIK_CACHE = None


def cik_for(ticker: str):
    global _CIK_CACHE
    if _CIK_CACHE is None:
        try:
            data = _json("https://www.sec.gov/files/company_tickers.json")
            _CIK_CACHE = {str(v.get("ticker", "")).upper(): int(v["cik_str"]) for v in data.values()}
        except Exception as exc:
            print(f"[WARN] SEC ticker map 失败：{exc}", file=sys.stderr)
            _CIK_CACHE = {}
    return _CIK_CACHE.get(ticker.upper())


def sec_filings(ticker: str):
    cik = cik_for(ticker)
    if not cik:
        return []
    try:
        sub = _json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        recent = sub.get("filings", {}).get("recent", {})
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accs = recent.get("accessionNumber") or []
        docs = recent.get("primaryDocument") or []
        out = []
        for i, form in enumerate(forms):
            if form not in FORMS:
                continue
            acc = (accs[i] or "").replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{docs[i]}" if docs[i] else ""
            out.append({"form": form, "date": dates[i], "url": url})
            if len(out) >= 3:
                break
        return out
    except Exception as exc:
        print(f"[WARN] SEC {ticker} 失败：{exc}", file=sys.stderr)
        return []


def earnings_date(ticker: str):
    try:
        import yfinance as yf
        cal = yf.Ticker(ticker).calendar or {}
        dates = cal.get("Earnings Date") or []
        if dates:
            d = dates[0]
            return str(getattr(d, "isoformat", d))[:10]
    except Exception:
        pass
    return None


def load_ticker_news():
    try:
        raw = json.loads(DATA.read_text(encoding="utf-8"))
        return (raw.get("news") or {}).get("ticker_news") or {}
    except Exception:
        return {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="serenity 研究优先级联网核验")
    ap.add_argument("--skill", default=str(SKILL))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    try:
        skill = json.loads(Path(args.skill).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] skill_serenity.json 读取失败：{exc}", file=sys.stderr)
        return 0

    priorities = skill.get("priorities") or []
    if not priorities:
        print("[WARN] 没有 priorities，跳过", file=sys.stderr)
        return 0

    news = load_ticker_news()
    items = []
    for p in priorities:
        tk = str(p.get("ticker") or "").upper()
        if not tk:
            continue
        filings = sec_filings(tk)
        ed = earnings_date(tk)
        nw = (news.get(tk) or [])[:3]
        missing = []
        if not ed:
            missing.append("财报日")
        if not filings:
            missing.append("SEC 文件")
        if not nw:
            missing.append("新闻")
        items.append({
            "ticker": tk,
            "earnings_date": ed,
            "filings": filings,
            "news": [{"title": n.get("headline") or n.get("headline_cn"), "url": n.get("url")} for n in nw],
            "missing": missing,
            "status": "verified" if len(missing) < 3 else "not_found",
        })
        time.sleep(0.2)

    payload = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "SEC EDGAR + yfinance + news_data",
        "mode": "online_verification",
        "count": len(items),
        "items": items,
    }
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    OUTP = Path(args.out)
    OUTP.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=OUTP.name + ".", suffix=".tmp", dir=str(OUTP.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, OUTP)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(f"[OK] 核验 {len(items)} 只 -> {OUTP}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
