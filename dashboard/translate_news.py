#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把金融新闻标题翻译成中文（带缓存，只翻新增）。

输入：dashboard/data/news_data.json（market_news + ticker_news）
缓存：dashboard/data/news_translations.json（原文 → 中文）
输出：回写 news_data.json 的 headline_cn（前端优先显示中文）

行为：
  · 先套用缓存，已有的不再调用 AI；
  · 只把「缓存里没有」的标题批量交给 ClawSocket 翻译（每次最多 40 条）；
  · 无密钥 / 模型失败 → 只套缓存，退出 0，绝不清空已有翻译。
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

REPO = Path(__file__).resolve().parent.parent
NEWS = REPO / "dashboard" / "data" / "news_data.json"
CACHE = REPO / "dashboard" / "data" / "news_translations.json"
BATCH = 50

SYSTEM = (
    "你是财经新闻翻译。把用户给的英文标题逐条翻成简洁中文（不超过 40 字），"
    "保留公司名/代码/数字。只输出 JSON 字符串数组，顺序与输入一致，不要解释。"
)


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _atomic_write(path: Path, payload):
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def iter_items(news):
    for it in news.get("market_news") or []:
        if isinstance(it, dict):
            yield it
    for items in (news.get("ticker_news") or {}).values():
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    yield it


def translate_batch(titles):
    try:
        from ai_router import gpt_generate_text
        text = gpt_generate_text(
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": json.dumps(titles, ensure_ascii=False)}],
            max_tokens=6000,
            reasoning_effort="low",
            model=os.environ.get("NEWS_TRANSLATE_MODEL") or None,
        )
        m = re.search(r"\[.*\]", text or "", re.S)
        arr = json.loads(m.group(0)) if m else []
        return [str(x).strip() for x in arr]
    except Exception as exc:
        print(f"[WARN] 翻译失败：{exc}", file=sys.stderr)
        return []


def main(argv=None) -> int:
    news = _load(NEWS, None)
    if not isinstance(news, dict):
        print("[WARN] news_data.json 缺失/损坏，跳过", file=sys.stderr)
        return 0
    cache = _load(CACHE, {})
    if not isinstance(cache, dict):
        cache = {}

    items = list(iter_items(news))
    # 重要人物讲话（macro_data.json）也走同一缓存
    try:
        macro = _load(REPO / "macro_data.json", {}) or {}
        for sp in (macro.get("speakers") or []):
            if isinstance(sp, dict) and sp.get("content"):
                items.append({"headline": sp["content"], "content_cn": sp.get("content_cn")})
    except Exception:
        pass
    pending = []
    for it in items:
        h = (it.get("headline") or "").strip()
        if not h:
            continue
        if not it.get("headline_cn") and cache.get(h):
            it["headline_cn"] = cache[h]
        if not it.get("headline_cn") and h not in pending:
            pending.append(h)

    todo = pending[:BATCH]
    if todo:
        arr = translate_batch(todo)
        for src, cn in zip(todo, arr):
            if cn:
                cache[src] = cn
        for it in items:
            h = (it.get("headline") or "").strip()
            if h and not it.get("headline_cn") and cache.get(h):
                it["headline_cn"] = cache[h]

    if not pending and not any(it.get("headline_cn") for it in items):
        print("[SKIP] 没有可翻译的标题", file=sys.stderr)
        return 0

    # 只写翻译缓存，绝不回写 news_data.json（避免与新闻刷新工作流互相覆盖）。
    _atomic_write(CACHE, cache)
    done = sum(1 for it in items if it.get("headline_cn") or cache.get((it.get("headline") or "").strip()))
    print(f"[OK] 标题中文 {done}/{len(items)}（本次新增 {len(todo)}）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
