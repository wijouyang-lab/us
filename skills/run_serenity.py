#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""serenity-skill runner **v2 —— 市场发掘（从候选池筛研究优先级）**（flag 门控，默认关闭）。

v1 是对 4 只**持仓**逐个做供应链分析；v2 改为对 scan 的**候选池（44 只）**做
供应链瓶颈视角的**研究优先级排序**，输出 TOP 10。**这是研究优先级，不是买入建议。**

框架来源：serenity-skill by muxuuu (MIT) —— https://github.com/muxuuu/serenity-skill
本仓库只内嵌其 `SKILL.md` / `references/` / `assets/`（见 `skills/serenity/`），未修改内容。

输入源：`dashboard/data/dashboard_data.json` 的 `stocks[]`
  （scan 的规范产物，恰好 44 只，含 bucket / 评分 / 板块相对强度；比 pending CSV 更权威）
  仅取精简字段；**不输入**完整技术面或 AI 六段（token 会爆）。

铁律
----
1. `ENABLE_SKILL_SERENITY != "1"` → **首行直接 return，零副作用**（不读文件、不调 AI、不写文件）。
2. **全部失败 / 无有效优先级 → 不写文件**（R1：绝不发布脏数据）。
3. 不触碰 `scan.py` / `review.py` / `portfolio_50000.py` / 任何 workflow。

⚠️ 能力限制（必须如实标注，不得宣称未核验的"事实"）
--------------------------------------------------
`clawsocket_compat.py` **不支持 tool use / function calling**，本 runner 也**没有联网能力**，
而 serenity-skill 的 frontmatter 要求 host agent 具备 web search。
故运行在**离线降级模式**（`mode="offline_screening"`）：只基于候选池字段 + 方法论推理，
prompt 强约束禁止编造数字，另有正则清洗器（方案 ③）兜底。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "serenity"
SKILL_MD = SKILL_DIR / "SKILL.md"
THESIS_TEMPLATE = SKILL_DIR / "assets" / "thesis-template.md"

# `python skills/run_serenity.py` 时 sys.path[0] 是 skills/ 而非仓库根，
# 故显式把仓库根加进来，保证根目录的 clawsocket_compat 可导入。
_REPO_ROOT_IMPORT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_IMPORT))

SCHEMA_VERSION = "skill_serenity.v2"
MODE = "offline_screening"
SKILL_SOURCE = "serenity-skill by muxuuu (MIT)"
FLAG_ENV = "ENABLE_SKILL_SERENITY"
DEFAULT_MODEL = "claude-opus-5-5"
TOP_N = 10


def skill_enabled() -> bool:
    """flag 门控：只有恰好 `"1"` 才启用。默认不设 = 关闭。"""
    return os.environ.get(FLAG_ENV) == "1"


# --------------------------------------------------------------------------- #
# 输入：候选池
# --------------------------------------------------------------------------- #
def load_universe(data_dir: Path) -> tuple[list[dict], int]:
    """从 `dashboard/data/dashboard_data.json` 读候选池（只读）。

    返回 (精简后的候选列表, 全池数量)。为空时调用方应退出且**不写文件**。
    """
    p = Path(data_dir) / "dashboard" / "data" / "dashboard_data.json"
    if not p.exists():
        return [], 0
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return [], 0

    # 已持有的 ticker（来自同一份 payload 的 portfolio 段）
    held: set[str] = set()
    folio = d.get("portfolio")
    if isinstance(folio, dict):
        for key in ("positions", "open_positions", "holdings"):
            for r in folio.get(key) or []:
                tk = str((r or {}).get("ticker") or (r or {}).get("Ticker") or "").strip().upper()
                if tk:
                    held.add(tk)

    out: list[dict] = []
    for s in d.get("stocks") or []:
        tk = str(s.get("ticker") or "").strip().upper()
        if not tk:
            continue
        out.append({
            "ticker": tk,
            "name": str(s.get("name") or "").strip(),
            "bucket": str(s.get("bucket") or "").strip() or "-",
            "final_score": s.get("final_score"),
            "quant_score": s.get("quant_score"),
            "ai_score": s.get("ai_score"),
            "sector_rs_20d_pct": s.get("sector_rs_20d_pct"),
            "held": tk in held,
        })
    return out, len(out)


def _fmt(v) -> str:
    return "-" if v in (None, "") else str(v)


def build_prompt(skill_md: str, template: str, universe: list[dict], asof: str) -> str:
    tpl = f"\n\n【研究模板（serenity-skill assets/thesis-template.md）】\n{template}" if template else ""
    rows = "\n".join(
        f"| {u['ticker']} | {u['name'][:28]} | {u['bucket']} | {_fmt(u['final_score'])} | "
        f"{_fmt(u['quant_score'])} | {_fmt(u['ai_score'])} | {_fmt(u['sector_rs_20d_pct'])} | "
        f"{'是' if u['held'] else '否'} |"
        for u in universe
    )
    return f"""你是**供应链瓶颈猎手**。下面这份 serenity-skill 方法论是你的分析框架。

【serenity-skill 方法论（原文，MIT，by muxuuu）】
{skill_md}{tpl}

【任务】
以下是当前候选池（{len(universe)} 只，来自 scan 的 Core / Observation 池）。请按 serenity 方法论分析：
1. 哪些处于"难扩产 / 难替代"的瓶颈层？
2. 哪些下游需求正在加速？
3. 谁的产品正在被认证 / 交付 / 货币化？
4. 哪些预期已经 price in？

输出 **TOP {TOP_N} 研究优先级（不是买入建议）**，按 priority_rank 1..{TOP_N} 排序。

【候选池（截至 {asof}）】
| ticker | name | bucket | final | quant | ai | sector_rs_20d | 已持有 |
|---|---|---|---|---|---|---|---|
{rows}

【数字纪律 —— 最高优先级，违反即整份作废】
你**没有联网能力**，也没有任何公告 / 财报 / 行情数据库。严格禁止出现任何具体数字：
- 禁止收入 / 营收金额、增长率、百分比、市场份额
- 禁止 P/E、EPS、估值倍数
- 禁止装机数、客户数、订单金额
- 禁止引用管理层原话或财报电话会措辞
- **只能使用上表提供的字段**（bucket / final / quant / ai / sector_rs_20d / 已持有）
  以及产业链结构、竞争格局、技术路径的**定性推理**
- 凡是你"记得"但无法核验的，一律写进 `what_to_verify`，不要写进 `why`

【输出】
只输出**一个 JSON 对象**，不要解释文字、不要 markdown 代码围栏：
{{
  "priorities": [
    {{"ticker": "ADSK", "priority_rank": 1,
      "why": "为什么值得优先研究：产业链位置 + 需求驱动 + 证据（纯定性，不含数字）",
      "what_to_verify": "需要核验的具体材料（如 10-Q 某分部收入、客户认证公告、产能披露）"}}
  ]
}}
必须正好 {TOP_N} 条，priority_rank 为 1..{TOP_N} 且不重复。`ticker` 必须来自上表。"""


# --------------------------------------------------------------------------- #
# 数字纪律正则（方案 ③，沿用 v1）
# --------------------------------------------------------------------------- #
NUMERIC_PATTERNS = [
    r"\$[\d.]+[BMK万亿]?",              # 金额
    r"[\d.]+%",                          # 百分比
    r"P/?E[^0-9\n]{0,8}[\d.]+",          # 估值倍数
    r"EPS[^0-9\n]{0,6}\$?[\d.]+",        # EPS
    r"[\d.]+\s*[BMK万亿]",               # 1472 亿 / 12.6B
    r"[一二三四五六七八九十百千万亿]+(?:成|台|美元|亿|万|个百分点|倍)",   # 中文数字（v1 盲区）
    r"百分之[一二三四五六七八九十百千零]+",
]
QUOTE_SPAN_PATTERN = r"[「『\"“][^」』\"”]{4,}[」』\"”]"
SPEAKER_PATTERN = r"(CEO|CFO|CTO|管理层|高管|财报电话会|电话会|earnings call|investor call)"
QUOTE_PATTERN = QUOTE_SPAN_PATTERN          # 向后兼容旧名

_NUMERIC_RE = re.compile("|".join(NUMERIC_PATTERNS))
_QUOTE_RE = re.compile(QUOTE_SPAN_PATTERN)
_SPEAKER_RE = re.compile(SPEAKER_PATTERN, re.IGNORECASE)
DIGIT_REMOVED = "[数字已剔除]"
SANITIZED_SUFFIX = "（数字已剔除，需核验 SEC filing）"


def _sanitize_text(t: str, add_suffix: bool) -> str:
    """剥离不可核验的数字与引语；`add_suffix` 决定是否追加需核验说明。"""
    if not t:
        return t
    has_num = bool(_NUMERIC_RE.search(t))
    has_quote = bool(_QUOTE_RE.search(t) and _SPEAKER_RE.search(t))
    if not (has_num or has_quote):
        return t
    t = _NUMERIC_RE.sub(DIGIT_REMOVED, t)
    if has_quote:
        t = _QUOTE_RE.sub("[引语已剔除]", t)
    return (t.rstrip() + SANITIZED_SUFFIX) if add_suffix else t


def sanitize_priorities(priorities: list[dict]) -> list[dict]:
    """对 priorities[] 逐条套用数字纪律。就地修改并返回。"""
    for p in priorities:
        p["why"] = _sanitize_text(p.get("why") or "", add_suffix=True)
        p["what_to_verify"] = _sanitize_text(p.get("what_to_verify") or "", add_suffix=False)
    return priorities


# --------------------------------------------------------------------------- #
# AI 调用 + 解析
# --------------------------------------------------------------------------- #
def _default_ask(prompt: str, model: str, max_tokens: int) -> str:
    """默认 AI 调用：走 ClawSocket（与 scan.py 同一客户端）。纯 prompt，无 tool use。"""
    from clawsocket_compat import ClawSocketClient  # 延迟导入：flag 关时零依赖副作用

    client = ClawSocketClient(
        api_key=os.environ.get("CLAWSOCKET_API_KEY"),
        base_url=os.environ.get("CLAWSOCKET_BASE_URL"),
    )
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return (getattr(resp, "output_text", "") or "").strip()


def _extract_json(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError("模型返回为空")
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if not m:
            raise ValueError("模型输出里找不到 JSON 对象") from None
        obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError(f"模型输出不是 JSON 对象，而是 {type(obj).__name__}")
    return obj


def parse_result(text: str, valid_tickers: set[str] | None = None) -> dict:
    """抽出 `priorities[]`：规整字段、去重、按 rank 排序、截断到 TOP_N。"""
    obj = _extract_json(text)
    raw = obj.get("priorities")
    if not isinstance(raw, list):
        raise ValueError("模型输出缺少 priorities 数组")

    seen: set[str] = set()
    items: list[dict] = []
    for i, p in enumerate(raw, 1):
        if not isinstance(p, dict):
            continue
        tk = str(p.get("ticker") or "").strip().upper()
        if not tk or tk in seen:
            continue
        if valid_tickers and tk not in valid_tickers:
            continue                       # 只接受候选池内的 ticker（防幻觉造股票）
        try:
            rank = int(p.get("priority_rank") or i)
        except (TypeError, ValueError):
            rank = i
        seen.add(tk)
        items.append({
            "ticker": tk,
            "priority_rank": rank,
            "why": str(p.get("why") or "").strip(),
            "what_to_verify": str(p.get("what_to_verify") or "").strip(),
        })

    items.sort(key=lambda x: x["priority_rank"])
    items = items[:TOP_N]
    for n, it in enumerate(items, 1):      # 归一化为连续的 1..N
        it["priority_rank"] = n
    if not items:
        raise ValueError("priorities 为空（或全部 ticker 不在候选池内）")
    return {"priorities": sanitize_priorities(items)}


# --------------------------------------------------------------------------- #
# 编排
# --------------------------------------------------------------------------- #
def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _skill_version(skill_md: str) -> str:
    m = re.search(r'version:\s*"?([0-9][^"\n]*)"?', skill_md or "")
    return m.group(1).strip() if m else ""


def run(data_dir: Path, skill_md: str, universe: list[dict], ask, model: str,
        max_tokens: int, asof: str) -> dict:
    """一次 AI 调用完成全池排序。失败抛异常，由 main 决定不写文件。"""
    template = _read_text(THESIS_TEMPLATE)
    prompt = build_prompt(skill_md, template, universe, asof)
    text = ask(prompt, model, max_tokens)
    got = parse_result(text, valid_tickers={u["ticker"] for u in universe})
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asof": asof,
        "source": SKILL_SOURCE,
        "mode": MODE,
        "model": model,
        "skill_version": _skill_version(skill_md),
        "universe_size": len(universe),
        "priorities": got["priorities"],
        "error": None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="serenity-skill runner v2 (market screening, flag-gated, offline)")
    ap.add_argument("--data-dir", default=".", help="含 dashboard/data/dashboard_data.json 的目录")
    ap.add_argument("--out", default="dashboard/data/skill_serenity.json", help="输出 JSON 路径")
    ap.add_argument("--model", default=None, help=f"模型（默认 {DEFAULT_MODEL}）")
    ap.add_argument("--max-tokens", type=int, default=12000)
    args = ap.parse_args(argv)

    # ---- flag 门控：必须在任何 I/O 之前 return（零副作用）----
    if not skill_enabled():
        print(f"[serenity] {FLAG_ENV} != '1'，跳过（零副作用：不读文件、不调 AI、不写文件）")
        return 0

    data_dir = Path(args.data_dir).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (data_dir / out_path).resolve() if args.data_dir != "." else (Path.cwd() / out_path).resolve()

    skill_md = _read_text(SKILL_MD)
    if not skill_md.strip():
        print(f"⚠️ [serenity] 找不到框架文件 {SKILL_MD}，退出（不写文件）")
        return 1

    universe, n = load_universe(data_dir)
    if not universe:
        print(f"[serenity] 候选池为空（{data_dir}/dashboard/data/dashboard_data.json 缺失或无 stocks[]），退出（不写文件）")
        return 0

    model = args.model or os.environ.get("SERENITY_MODEL") or DEFAULT_MODEL
    asof = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n_core = sum(1 for u in universe if u["bucket"] == "Core")
    print(f"[serenity] {MODE} | model={model} | 候选池 {n} 只（Core {n_core} / Observation {n - n_core}）| asof={asof}")

    try:
        payload = run(data_dir, skill_md, universe, _default_ask, model, args.max_tokens, asof)
    except Exception as e:                                   # noqa: BLE001
        print(f"⚠️ [serenity] 分析失败，按 R1 不写文件：{type(e).__name__}: {e}")
        return 1

    if not payload.get("priorities"):
        print("[serenity] 无有效优先级，按 R1 不写文件")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[serenity] 已写入 {out_path}（{len(payload['priorities'])} 条优先级，池 {payload['universe_size']} 只）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
