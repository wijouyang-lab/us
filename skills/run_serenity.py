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

【硬性约束 —— 必须遵守】
1. **你没有联网能力，也没有任何公告/财报数据库。** 禁止编造任何具体的财务数字、公告标题、
   客户名称或订单金额。凡是你无法从下面给出的数据推出的，一律写进 `gaps`，不要写进 `evidence`。
2. `evidence` 里每一条都要标注来源类型，格式如 `[持仓数据] ...`、`[方法论推理] ...`、
   `[待核验] ...`。没有 `[持仓数据]` 依据的条目必须显式标 `[方法论推理]` 或 `[待核验]`。
3. 优先级用**文字与理由**表达，**不要给综合数字评分**（这是 serenity-skill 的明确要求）。
4. 输出**只有**一个 JSON 对象，不要任何解释文字、不要 markdown 代码围栏。

【本次分析对象（截至 {asof}）】
- Ticker: {pos['ticker']}
- 持仓单元: {pos.get('unit') or '-'}  股数: {pos.get('shares') or '-'}
- 入场价: {pos.get('entry_price') or '-'}  入场日: {pos.get('entry_date') or '-'}
- 现价: {pos.get('current_price') or '-'}  浮动盈亏: {pos.get('unrealized_pnl_pct') or '-'}%
- 当前止损线: {pos.get('stop_loss') or '-'}  权重: {pos.get('weight_pct') or '-'}%

【必须返回的 JSON 结构】
{{
  "business_position": "这家公司卡在产业链哪一层、供给稀缺性来自哪里（文字，2-4 句）",
  "evidence": ["[持仓数据] ...", "[方法论推理] ..."],
  "gaps": ["需要核验什么；缺哪类证据（如最新 10-Q 的某分部毛利率）"],
  "earnings": "这条逻辑如何转成盈利；需要看哪个财务科目（文字）",
  "valuation": "当前估值压力来自哪里（文字，不要编造倍数）",
  "alternatives": "替代路线 / 竞争对手 / 客户自研等（文字）",
  "what_would_change": "出现什么情况说明这个判断应降级（文字）"
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
        if f in ("evidence", "gaps"):
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
