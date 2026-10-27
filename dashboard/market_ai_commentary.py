#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 AI 生成「市场情绪指标」解读（CNN 恐惧贪婪 + CME FedWatch）。

边界（重要）：
  · 只分析 `market_indicators.json` 里的情绪/利率数据，**不选股、不给买卖建议**，
    不进入 $50,000 账本，也不修改 Quant Phase 1–7；
  · 数据只来自本地文件，不联网抓行情；
  · 没有 API Key / 没有数据 → **不写文件**（前端保持 pending，不编造内容）；
  · 调用失败或模型输出不是合法 JSON → **不覆盖已有文件**，退出码 1（便于告警）。

用法：
    python dashboard/market_ai_commentary.py
    python dashboard/market_ai_commentary.py --dry-run
    python dashboard/market_ai_commentary.py --offline --input-json model_out.json  # 测试/回放
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import ai_router  # noqa: E402

DEFAULT_INDICATORS = REPO_ROOT / "dashboard" / "data" / "market_indicators.json"
DEFAULT_OUT = REPO_ROOT / "dashboard" / "data" / "market_ai_commentary.json"

RATING_CN = {
    "extreme fear": "极度恐惧",
    "fear": "恐惧",
    "neutral": "中性",
    "greed": "贪婪",
    "extreme greed": "极度贪婪",
}
SUB_CN = {
    "market_momentum_sp500": "标普动能",
    "stock_price_strength": "股价强度",
    "stock_price_breadth": "股价广度",
    "put_call_options": "看跌/看涨期权",
    "market_volatility_vix": "市场波动(VIX)",
    "junk_bond_demand": "垃圾债需求",
    "safe_haven_demand": "避险需求",
}


def _clean(v) -> str:
    return str(v).strip() if v is not None else ""


def _num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def load_indicators(path: Path):
    """读 market_indicators.json；缺失/损坏/无 F&G 与 FedWatch → None。"""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] 读取 {path} 失败：{e}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("fear_greed") and not data.get("fedwatch"):
        return None
    return data


def build_prompt(mi: dict) -> list[dict]:
    """把情绪/利率数据压成一段结构化文本（只含真实字段，缺失就跳过）。"""
    lines = []
    fg = mi.get("fear_greed") or {}
    if fg:
        score = _num(fg.get("score"))
        rating = RATING_CN.get(_clean(fg.get("rating")).lower(), _clean(fg.get("rating")))
        lines.append(f"【CNN 恐惧贪婪】总分 {score if score is not None else 'N/A'}"
                     f"（{rating or 'N/A'}），数据时间 {_clean(fg.get('timestamp')) or 'N/A'}")
        subs = fg.get("subindicators") or {}
        parts = []
        for k, v in subs.items():
            if not isinstance(v, dict):
                continue
            s = _num(v.get("score"))
            r = RATING_CN.get(_clean(v.get("rating")).lower(), _clean(v.get("rating")))
            parts.append(f"{SUB_CN.get(k, k)} {s if s is not None else 'N/A'}"
                         f"（{r or 'N/A'}）")
        if parts:
            lines.append("子项：" + "；".join(parts))
        hist = fg.get("history_30d") or []
        if hist:
            nums = [_num(h.get("score")) for h in hist if isinstance(h, dict)]
            nums = [n for n in nums if n is not None]
            if nums:
                lines.append(f"30 日区间：最高 {max(nums):.2f} / 最低 {min(nums):.2f}"
                             f" / 样本 {len(nums)} 天")
            recent = [h for h in hist[:5] if isinstance(h, dict)]
            if recent:
                lines.append("最近 5 日：" + "；".join(
                    f"{_clean(h.get('date'))} {_num(h.get('score'))}" for h in recent))

    fw = mi.get("fedwatch") or {}
    if fw:
        lines.append(f"【CME FedWatch】当前目标区间 {_clean(fw.get('current_target')) or 'N/A'}"
                     f"，EFFR {_num(fw.get('effr')) if _num(fw.get('effr')) is not None else 'N/A'}"
                     f"，数据日 {_clean(fw.get('trade_date')) or 'N/A'}")
        meetings = fw.get("meetings") or []
        if not meetings and fw.get("next_meeting"):
            meetings = [{"date": fw.get("next_meeting"),
                         "probabilities": fw.get("probabilities") or {}}]
        for m in meetings[:3]:
            if not isinstance(m, dict):
                continue
            probs = m.get("probabilities") or {}
            ps = "；".join(f"{k} {_num(v)}%" for k, v in probs.items() if _num(v) is not None)
            lines.append(f"会议 {_clean(m.get('date'))}：{ps}")

    data_text = "\n".join(lines) if lines else "（无可用数据）"
    system = (
        "你是美股市场情绪分析师。只根据用户提供的数据写中文解读，"
        "不引用数据之外的数字，不预测点位，不给买入/卖出建议。"
        "输出必须是 JSON 对象，格式："
        '{"summary":"一段总述","sections":[{"title":"小节标题","text":"小节正文"}]}；'
        "sections 2-3 段，每段 60-160 字；不要输出 JSON 之外的任何文字。"
    )
    user = (
        f"数据（{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}）：\n{data_text}\n\n"
        "请写：1) 情绪位置与结构（总分 + 子项分化）；2) 利率预期（近三次会议概率变化）；"
        "3) 对风险偏好的含义（只描述，不构成建议）。"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def normalize_model_payload(obj):
    """校验/清洗模型输出；不能使用时返回 None（不写文件）。"""
    if not isinstance(obj, dict):
        return None
    summary = _clean(obj.get("summary"))
    sections = []
    for s in (obj.get("sections") or [])[:5]:
        if not isinstance(s, dict):
            continue
        text = _clean(s.get("text"))
        if not text:
            continue
        sections.append({"title": _clean(s.get("title")) or None, "text": text})
    if not summary and not sections:
        return None
    return {"summary": summary or None, "sections": sections}


def build_payload(parsed: dict, *, model: str, generated_at: str | None = None) -> dict:
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": model or None,
        "summary": parsed.get("summary"),
        "sections": parsed.get("sections") or [],
    }


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
    ap = argparse.ArgumentParser(description="生成市场情绪 AI 解读（只读指标数据）")
    ap.add_argument("--indicators", default=str(DEFAULT_INDICATORS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--model", default=os.environ.get("MARKET_AI_MODEL") or None,
                    help="模型名（默认 MARKET_AI_MODEL / ai_router.GPT_MODEL）")
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true",
                    help="不调用 AI；配合 --input-json 回放模型输出（测试用）")
    ap.add_argument("--input-json", default=None, help="离线模式：模型输出 JSON 文件")
    args = ap.parse_args(argv)

    mi = load_indicators(Path(args.indicators))
    if mi is None:
        print("[WARN] 无可用市场情绪数据（market_indicators.json 缺失或为空），跳过", file=sys.stderr)
        return 0

    model = args.model or getattr(ai_router, "GPT_MODEL", None) or "unknown"
    try:
        if args.offline:
            if not args.input_json:
                print("[ERROR] --offline 需要 --input-json", file=sys.stderr)
                return 2
            raw = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
            text = json.dumps(raw, ensure_ascii=False)
        else:
            text = ai_router.gpt_generate_text(
                messages=build_prompt(mi),
                max_tokens=args.max_tokens,
                reasoning_effort="low",
                model=model,
            )
    except RuntimeError as e:
        # 未配置任何 AI 凭证 → 跳过且不覆盖已有文件（fail-closed，不阻断定时任务）
        print(f"[WARN] AI 不可用，跳过：{e}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"[ERROR] AI 调用失败：{e}", file=sys.stderr)
        return 1

    obj = ai_router.extract_json_object(text)
    parsed = normalize_model_payload(obj)
    if parsed is None:
        print("[ERROR] 模型输出无法解析为约定 JSON，保留旧文件不动", file=sys.stderr)
        return 1

    payload = build_payload(parsed, model=model)
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    out = Path(args.out)
    _atomic_write(out, payload)
    print(f"[OK] 写入 {out}：{len(payload['sections'])} 段 + summary", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
