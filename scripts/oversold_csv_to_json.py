#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 GPT/量化输出的 CSV 一键转成 Dashboard 可读的 oversold_candidates.json。

**纯格式转换，不含任何筛选/打分/阈值逻辑**：
  · 只做列名映射、数值清洗（$ , % 空格）、空行丢弃、ticker 大写；
  · ticker 缺失的行直接跳过并在 stderr 汇总（绝不补造 ticker）；
  · 输出严格遵循 docs/OVERSOLD_SIGNAL_CONTRACT.md 的 schema v1。

用法：
    python scripts/oversold_csv_to_json.py candidates.csv
    python scripts/oversold_csv_to_json.py candidates.csv --asof 2026-10-24 \
        --source "GPT 量化研究" --note "本周超跌候选"
    python scripts/oversold_csv_to_json.py candidates.csv --dry-run   # 只打印，不写文件

CSV 表头可用英文或中文（见 ALIASES），大小写/空格/下划线不敏感，例如：
    ticker,name,score,tag,rsi,bias_pct,drawdown_pct,ref_price,stop_loss,confirm,invalid,observe_until,reason
    代码,名称,超跌分,标签,RSI,偏离,回撤,参考价,止损,确认条件,失效条件,观察至,理由
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "dashboard" / "data" / "oversold_candidates.json"
SCHEMA = 1

NUM_FIELDS = ("score", "rsi", "bias_pct", "drawdown_pct", "ref_price", "stop_loss")
STR_FIELDS = ("name", "tag", "confirm", "invalid", "observe_until", "reason")

# 字段 → 可识别表头别名（比较前会统一小写并去掉 空格 _ - . / ( ) %）
ALIASES = {
    "ticker": ("ticker", "symbol", "code", "stock", "股票代码", "代码", "标的"),
    "name": ("name", "company", "companyname", "名称", "公司", "公司名称"),
    "score": ("score", "oversoldscore", "分数", "超跌分", "评分", "超跌评分"),
    "tag": ("tag", "label", "标签", "类型", "分类"),
    "rsi": ("rsi", "rsi14", "rsi14d", "RSI14", "RSI(14)"),
    "bias_pct": ("bias", "biaspct", "bias20", "偏离", "偏离度", "乖离", "乖离率"),
    "drawdown_pct": ("drawdown", "drawdownpct", "回撤", "回撤幅度", "最大回撤"),
    "ref_price": ("refprice", "price", "参考价", "现价", "价格", "最新价"),
    "stop_loss": ("stoploss", "stop", "止损", "止损价", "止损位"),
    "confirm": ("confirm", "trigger", "confirmation", "确认", "触发", "确认条件", "触发条件"),
    "invalid": ("invalid", "invalidation", "失效", "失效条件", "证伪", "证伪条件"),
    "observe_until": ("observeuntil", "expire", "expires", "观察至", "到期", "观察到期", "观察截止"),
    "reason": ("reason", "why", "理由", "原因", "说明", "入选理由"),
}


def _norm_key(s: str) -> str:
    """表头归一化：小写 + 去掉空格/下划线/连字符/点/斜杠/括号/百分号。"""
    t = str(s or "").strip().lower()
    for ch in (" ", "_", "-", ".", "/", "(", ")", "%", "\u3000"):
        t = t.replace(ch, "")
    return t


_ALIAS_LOOKUP = {_norm_key(a): f for f, aliases in ALIASES.items() for a in aliases}


def _clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _num(v):
    """'$1,234.5' / '22.4%' / '−14.2' / '' / 'N/A' → float 或 None。"""
    s = _clean(v).replace("−", "-").replace("$", "").replace(",", "").replace("%", "")
    s = s.replace(" ", "")
    if s == "" or s.lower() in {"na", "n/a", "none", "null", "nan", "-", "—"}:
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return None if f != f else f


def _read_csv(path: Path):
    """读取 CSV（utf-8-sig → utf-8 → gbk 依次尝试），返回 DictReader 行列表。"""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"无法解码 {path}")


def convert(rows, *, asof=None, source=None, note=None, generated_at=None):
    """把 CSV 行列表转成契约 payload；返回 (payload, stats)。

    stats: {"read": n, "kept": n, "skipped": [{"row": i, "why": "..."}]}
    """
    out = []
    skipped = []
    unknown = set()
    for i, raw in enumerate(rows, start=1):
        if not raw or not any(_clean(v) for v in raw.values()):
            continue  # 完全空行，不计入 skipped
        mapped = {}
        for k, v in raw.items():
            field = _ALIAS_LOOKUP.get(_norm_key(k))
            if field:
                mapped[field] = v
            elif _clean(k):
                unknown.add(_clean(k))
        ticker = _clean(mapped.get("ticker")).upper()
        if not ticker:
            skipped.append({"row": i, "why": "缺少 ticker"})
            continue
        cand = {"ticker": ticker}
        for f in NUM_FIELDS:
            cand[f] = _num(mapped.get(f))
        for f in STR_FIELDS:
            cand[f] = _clean(mapped.get(f)) or None
        out.append(cand)

    payload = {
        "schema": SCHEMA,
        "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asof": _clean(asof) or None,
        "source": _clean(source) or None,
        "note": _clean(note) or None,
        "candidates": out,
    }
    stats = {"read": len(rows), "kept": len(out), "skipped": skipped,
             "unknown_headers": sorted(unknown)}
    return payload, stats


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
    ap = argparse.ArgumentParser(description="CSV → oversold_candidates.json（纯格式转换）")
    ap.add_argument("csv", help="输入 CSV 路径")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出 JSON（默认 dashboard/data/oversold_candidates.json）")
    ap.add_argument("--asof", default=None, help="数据截止日 YYYY-MM-DD（原样写入）")
    ap.add_argument("--source", default=None, help="信号来源，如“GPT 量化研究”")
    ap.add_argument("--note", default=None, help="顶部说明")
    ap.add_argument("--generated-at", default=None, help="生成时间（默认当前 UTC）")
    ap.add_argument("--dry-run", action="store_true", help="只打印 JSON，不写文件")
    ap.add_argument("--allow-empty", action="store_true", help="允许 0 条候选（默认视为错误）")
    args = ap.parse_args(argv)

    src = Path(args.csv)
    if not src.exists():
        print(f"[ERROR] 找不到 CSV：{src}", file=sys.stderr)
        return 2

    try:
        rows = _read_csv(src)
    except Exception as e:
        print(f"[ERROR] 读取 CSV 失败：{e}", file=sys.stderr)
        return 2

    payload, stats = convert(rows, asof=args.asof, source=args.source,
                             note=args.note, generated_at=args.generated_at)

    if stats["unknown_headers"]:
        print(f"[WARN] 未识别的列（已忽略）：{', '.join(stats['unknown_headers'])}", file=sys.stderr)
    if stats["skipped"]:
        detail = "; ".join(f"第 {s['row']} 行 {s['why']}" for s in stats["skipped"][:10])
        more = "" if len(stats["skipped"]) <= 10 else f" 等 {len(stats['skipped'])} 行"
        print(f"[WARN] 跳过 {len(stats['skipped'])} 行：{detail}{more}", file=sys.stderr)

    if not payload["candidates"] and not args.allow_empty:
        print("[ERROR] 没有任何有效候选（ticker 全部缺失？）。如确实为空，加 --allow-empty。",
              file=sys.stderr)
        return 1

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.dry_run:
        print(text)
    else:
        out = Path(args.out)
        _atomic_write(out, payload)
        print(f"[OK] 写入 {out}：{stats['kept']} 条候选（读取 {stats['read']} 行，跳过 {len(stats['skipped'])} 行）",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
