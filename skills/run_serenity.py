#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""serenity-skill runner —— 对 $50k 账本持仓做供应链瓶颈分析（**flag 门控，默认关闭**）。

框架来源：serenity-skill by muxuuu (MIT) —— https://github.com/muxuuu/serenity-skill
本仓库只内嵌其 `SKILL.md` / `references/` / `assets/`（见 `skills/serenity/`），**未修改内容**。

铁律
----
1. `ENABLE_SKILL_SERENITY != "1"` → **首行直接 return，零副作用**
   （不读 CSV、不读 SKILL.md、不调 AI、不写文件）。
2. 单只持仓失败 → 该只记 `error`，**不阻断其他**。
3. **全部失败 → 不写文件**（R1：绝不发布脏数据）。
4. 不触碰 `scan.py` / `review.py` / `portfolio_50000.py` / 任何现有 workflow。

⚠️ 重要限制（必须如实记录，不得宣称未核验的"事实"）
--------------------------------------------------
`clawsocket_compat.py` 的 `_request_chat` / `_request_anthropic` / `_request_responses`
**不支持 tool use / function calling**（payload 里没有 `tools`；`extra` 形参被静默丢弃），
本 runner 也**没有联网能力**。而 serenity-skill 的 frontmatter 明确要求：
    compatibility: Requires a host agent with web search or access to current filings

因此本 runner 运行的是**离线降级模式**：只基于我们已有的数据（持仓 + 入场/现价/止损）
做结构推理。输出里显式标记 `mode="offline"`，并在 prompt 中要求模型
把每条 evidence 标注来源类型、把无法核验的写进 gaps、**禁止编造公告/财报数字**。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "skill_serenity.v1"
SKILL_SOURCE = "serenity-skill by muxuuu (MIT)"
FLAG_ENV = "ENABLE_SKILL_SERENITY"

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "serenity"
SKILL_MD = SKILL_DIR / "SKILL.md"

# `python skills/run_serenity.py` 时 sys.path[0] 是 skills/ 而非仓库根，
# 故显式把仓库根加进来，保证根目录的 clawsocket_compat 可导入。
# （真实事故：缺这段时 workflow 里 4 只持仓全部 ModuleNotFoundError。）
_REPO_ROOT_IMPORT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_IMPORT))
THESIS_TEMPLATE = SKILL_DIR / "assets" / "thesis-template.md"

DEFAULT_MODEL = "claude-opus-5-5"

# 每只持仓必须产出的字段（顺序即展示顺序）
RESULT_FIELDS = (
    "business_position",   # 业务定位：卡在产业链哪一层
    "evidence",            # 证据（列表）：已知事实 + 来源类型
    "gaps",                # 缺口（列表）：尚未核验 / 缺什么证据
    "earnings",            # 盈利含义
    "valuation",           # 估值压力
    "alternatives",        # 替代路线 / 竞争
    "what_would_change",   # 什么情况下这个判断应该降级
)


def skill_enabled() -> bool:
    """flag 门控：只有恰好 `"1"` 才启用。默认不设 = 关闭。"""
    return os.environ.get(FLAG_ENV) == "1"


# --------------------------------------------------------------------------- #
# 数据加载
# --------------------------------------------------------------------------- #
def load_positions(data_dir: Path) -> list[dict]:
    """读 `portfolio_50000_positions.csv` 的 OPEN 持仓（只读，绝不写回）。"""
    p = Path(data_dir) / "portfolio_50000_positions.csv"
    if not p.exists():
        return []
    out: list[dict] = []
    with open(p, "r", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if str(r.get("Status", "")).strip().upper() != "OPEN":
                continue
            tk = str(r.get("Ticker", "")).strip().upper()
            if not tk:
                continue
            out.append({
                "ticker": tk,
                "unit": str(r.get("Unit_ID", "")).strip(),
                "shares": str(r.get("Shares", "")).strip(),
                "entry_price": str(r.get("Entry_Price", "")).strip(),
                "entry_date": str(r.get("Entry_Date", "")).strip(),
                "current_price": str(r.get("Current_Price", "")).strip(),
                "stop_loss": str(r.get("Stop_Loss", "")).strip(),
                "unrealized_pnl_pct": str(r.get("Unrealized_PnL_Pct", "")).strip(),
                "weight_pct": str(r.get("Weight_Pct", "")).strip(),
            })
    return out


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
def build_prompt(skill_md: str, template: str, pos: dict, asof: str) -> str:
    tpl = f"\n\n【研究模板（serenity-skill assets/thesis-template.md）】\n{template}" if template else ""
    return f"""你是投研分析助手。请严格按下面这份 serenity-skill 方法论，对**一只美股持仓**做供应链瓶颈分析。

【serenity-skill 方法论（原文，MIT，by muxuuu）】
{skill_md}{tpl}

【数字纪律 —— 最高优先级，违反即整份作废】
你没有联网能力，也没有任何公告 / 财报 / 行情数据库。严格禁止出现任何具体数字，
**除非它来自 [持仓数据]**（= 下面「本次分析对象」里列出的字段）：
- 禁止收入 / 营收金额（如 $7.21B、$346.2 亿）
- 禁止增长率、百分比（如 +17.5%、42% 市场份额）
- 禁止 P/E、EPS、估值倍数（如「约 28.5 倍」）
- 禁止装机数、客户数、门店数、市场份额数字
- 禁止直接引用管理层原话或财报电话会措辞（你无法核验）
- 禁止具体事件名 / 日期 / 收购金额 / 诉讼金额

如果你「记得」某个数字，把它写进 source 为「数字待核验」的条目，**绝不要**写进「定性推理」。

【evidence 标签语义】
- source = "持仓数据"：直接来自下面「本次分析对象」的字段。**只有这一类可以含数字。**
- source = "定性推理"：基于产业链结构、竞争格局、技术路径的逻辑推理。**禁止包含任何具体数字。**
- source = "数字待核验"：你「记得」的数字（可能准确也可能过时），
  必须由用户自行核验 SEC filing / 10-K / 10-Q 之后才能使用；请在 text 里写明该查哪份文件。

【其它约束】
1. 优先级用**文字与理由**表达，**不要给综合数字评分**（这是 serenity-skill 的明确要求）。
2. 输出**只有**一个 JSON 对象，不要任何解释文字、不要 markdown 代码围栏。

【本次分析对象（截至 {asof}）】
- Ticker: {pos['ticker']}
- 持仓单元: {pos.get('unit') or '-'}  股数: {pos.get('shares') or '-'}
- 入场价: {pos.get('entry_price') or '-'}  入场日: {pos.get('entry_date') or '-'}
- 现价: {pos.get('current_price') or '-'}  浮动盈亏: {pos.get('unrealized_pnl_pct') or '-'}%
- 当前止损线: {pos.get('stop_loss') or '-'}  权重: {pos.get('weight_pct') or '-'}%

【必须返回的 JSON 结构】
{{
  "business_position": "这家公司卡在产业链哪一层、供给稀缺性来自哪里（文字，2-4 句，不含具体数字）",
  "evidence": [
    {{"text": "来自持仓字段的事实（入场价/现价/浮盈/权重）", "source": "持仓数据"}},
    {{"text": "基于产业链结构的推理，不含任何数字", "source": "定性推理"}},
    {{"text": "你记得但无法核验的某个数字，并写明该查哪份文件", "source": "数字待核验"}}
  ],
  "gaps": ["需要核验什么；缺哪类证据（如最新 10-Q 的某分部毛利率）"],
  "earnings": "这条逻辑如何转成盈利；需要看哪个财务科目（文字，不含具体数字）",
  "valuation": "当前估值压力来自哪里（文字，不含任何倍数）",
  "alternatives": "替代路线 / 竞争对手 / 客户自研等（文字）",
  "what_would_change": "出现什么情况说明这个判断应降级（文字，可用条件式描述，但不要编造当前数值）"
}}"""


# --------------------------------------------------------------------------- #
# AI 调用 + 解析
# --------------------------------------------------------------------------- #
def _default_ask(prompt: str, model: str, max_tokens: int) -> str:
    """默认 AI 调用：走 ClawSocket（与 scan.py 同一客户端）。

    注意：`clawsocket_compat` 不支持 tools，这里就是纯 prompt 调用。
    """
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


EVIDENCE_SOURCES = ("持仓数据", "定性推理", "数字待核验")


def _coerce_evidence(v) -> list[dict]:
    """把 evidence 规整成 `[{"text":..., "source":...}, ...]`。

    兼容两种输入：
      · 新格式：`{"text": ..., "source": "定性推理"}`
      · 旧格式：`"[持仓数据] ..."`（自动把方括号标签提升为 source）

    **fail-safe**：source 缺失或不在白名单 → 一律降级为「数字待核验」。
    宁可疑、不可信 —— 未标注来源的内容不该被当作已核验事实展示。
    """
    if v in (None, ""):
        return []
    items = v if isinstance(v, list) else [v]
    out: list[dict] = []
    for it in items:
        src = ""
        if isinstance(it, dict):
            text = str(it.get("text") or it.get("evidence") or "").strip()
            src = str(it.get("source") or "").strip()
        else:
            text = str(it).strip()
            m = re.match(r"^\[([^\]]{1,12})\]\s*(.*)$", text, re.DOTALL)
            if m:
                src, text = m.group(1).strip(), m.group(2).strip()
        if not text:
            continue
        if src not in EVIDENCE_SOURCES:
            src = "数字待核验"
        out.append({"text": text, "source": src})
    return out


def parse_result(text: str) -> dict:
    """从模型输出里抽出 JSON 对象并规整字段。失败则抛异常（由调用方记 eorror）。"""
    if not text or not text.strip():
        raise ValueError("模型返回为空")
    s = text.strip()
    # 容忍 ```json ... ``` 围栏
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)      # 退一步：截取第一个大括号块
        if not m:
            raise ValueError("模型输出里找不到 JSON 对象") from None
        obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError(f"模型输出不是 JSON 对象，而是 {type(obj).__name__}")

    out: dict = {}
    for f in RESULT_FIELDS:
        v = obj.get(f)
        if f == "evidence":
            out[f] = _coerce_evidence(v)          # → 对象数组 {text, source}
        elif f == "gaps":
            if isinstance(v, list):
                out[f] = [str(x).strip() for x in v if str(x).strip()]
            elif v not in (None, ""):
                out[f] = [str(v).strip()]
            else:
                out[f] = []
        else:
            out[f] = "" if v is None else str(v).strip()
    return out


# --------------------------------------------------------------------------- #
# 编排
# --------------------------------------------------------------------------- #
def run(data_dir: Path, out_path: Path, skill_md: str, positions: list[dict],
        ask, model: str, max_tokens: int, asof: str) -> dict:
    """逐只分析。返回 payload dict；调用方决定是否落盘。

    单只异常 → 该只带 `error` 字段，其余继续。
    """
    template = _read_text(THESIS_TEMPLATE)
    results: list[dict] = []
    ok = 0
    for pos in positions:
        tk = pos["ticker"]
        try:
            prompt = build_prompt(skill_md, template, pos, asof)
            text = ask(prompt, model, max_tokens)
            rec = parse_result(text)
            rec["ticker"] = tk
            rec["error"] = None
            ok += 1
            print(f"[serenity] ✅ {tk} 分析完成")
        except Exception as e:                      # noqa: BLE001 —— 单只失败不阻断
            rec = {f: ([] if f in ("evidence", "gaps") else "") for f in RESULT_FIELDS}
            rec["ticker"] = tk
            rec["error"] = f"{type(e).__name__}: {e}"
            print(f"⚠️ [serenity] {tk} 分析失败（不阻断其他）：{rec['error']}")
        results.append(rec)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asof": asof,
        "source": SKILL_SOURCE,
        "mode": "offline",          # 见模块 docstring：本 runner 无联网 / 无 tool use
        "model": model,
        "skill_version": _skill_version(skill_md),
        "positions": results,
        "error": None if ok else "全部持仓分析失败",
    }
    return payload


def _skill_version(skill_md: str) -> str:
    m = re.search(r'version:\s*"?([0-9][^"\n]*)"?', skill_md or "")
    return m.group(1).strip() if m else ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="serenity-skill runner (flag-gated, offline mode)")
    ap.add_argument("--data-dir", default=".", help="含 portfolio_50000_positions.csv 的目录")
    ap.add_argument("--out", default="dashboard/data/skill_serenity.json", help="输出 JSON 路径")
    ap.add_argument("--model", default=None, help=f"模型（默认 {DEFAULT_MODEL}）")
    ap.add_argument("--max-tokens", type=int, default=6000)
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

    positions = load_positions(data_dir)
    if not positions:
        print("[serenity] 无 OPEN 持仓，退出（不写文件）")
        return 0

    model = args.model or os.environ.get("SERENITY_MODEL") or DEFAULT_MODEL
    asof = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"[serenity] offline 模式 | model={model} | 持仓 {len(positions)} 只 | asof={asof}")

    payload = run(data_dir, out_path, skill_md, positions, _default_ask, model, args.max_tokens, asof)

    # R1：全部失败 → 不写文件
    if all(p.get("error") for p in payload["positions"]):
        print("[serenity] 全部持仓分析失败，按 R1 不写文件")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for p in payload["positions"] if not p.get("error"))
    print(f"[serenity] 已写入 {out_path}（成功 {ok}/{len(payload['positions'])}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
