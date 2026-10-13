# -*- coding: utf-8 -*-
"""serenity-skill **v2（市场发掘 / 研究优先级排序）** 测试。

v2 相对 v1 的结构变更：
  · 输入：候选池（`dashboard/data/dashboard_data.json` 的 stocks[]，44 只）—— 不再是 4 只持仓
  · 输出：`priorities[]`（TOP 10 排序）—— 不再是 `positions[]`
  · schema_version：`skill_serenity.v2`；mode：`offline_screening`

保留的护栏：flag 门控零副作用 / R1 全失败不写文件 / 数字纪律正则 / 脚本模式 import /
workflow job 级 flag / dashboard_export 哨兵。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_V2 = "skill_serenity.v2"
MODE_V2 = "offline_screening"
SOURCE = "serenity-skill by muxuuu (MIT)"


def _load_runner():
    p = REPO_ROOT / "skills" / "run_serenity.py"
    spec = importlib.util.spec_from_file_location("run_serenity_v2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stocks(n=44):
    """造 n 只候选（前 14 只 Core，其余 Observation），模拟真实池构成。"""
    return [{
        "ticker": f"T{i:02d}", "name": f"Company {i}",
        "bucket": "Core" if i < 14 else "Observation",
        "final_score": 90 - i * 0.5, "quant_score": 80 - i * 0.4,
        "ai_score": 70 - i * 0.3, "sector_rs_20d_pct": 5 - i * 0.1,
    } for i in range(n)]


def _write_payload(tmp_path, stocks=None, held=("T00", "T01")):
    d = tmp_path / "dashboard" / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "dashboard_data.json").write_text(json.dumps({
        "generated_at": "2026-10-13T07:00:00Z",
        "stocks": stocks if stocks is not None else _stocks(),
        "portfolio": {"positions": [{"ticker": t} for t in held]},
    }, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def _good_ai(n=10):
    return json.dumps({"priorities": [
        {"ticker": f"T{i:02d}", "priority_rank": i + 1,
         "why": f"处于难替代的瓶颈环节 #{i}，下游需求加速，产品已进入认证/交付阶段",
         "what_to_verify": f"核验 T{i:02d} 最新 10-Q 的分部收入与客户集中度披露"}
        for i in range(n)
    ]}, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# 1) flag 门控 —— 零副作用
# --------------------------------------------------------------------------- #
def test_flag_unset_returns_early(tmp_path, capsys):
    r = _load_runner()
    out = tmp_path / "skill_serenity.json"
    rc = r.main(["--data-dir", str(tmp_path), "--out", str(out)])
    assert rc == 0
    assert not out.exists(), "flag 关时绝不能写文件"
    assert "跳过" in capsys.readouterr().out


def test_flag_off_zero_side_effect_even_without_input(tmp_path, capsys):
    """flag 关时连候选池都不用存在 —— 证明它确实没做任何 I/O。"""
    r = _load_runner()
    out = tmp_path / "o.json"
    rc = r.main(["--data-dir", str(tmp_path / "nope"), "--out", str(out)])
    assert rc == 0 and not out.exists()
    assert "跳过" in capsys.readouterr().out


@pytest.mark.parametrize("val", ["0", "true", "yes", "", "2", "TRUE"])
def test_only_exactly_1_enables(monkeypatch, val):
    r = _load_runner()
    monkeypatch.setenv("ENABLE_SKILL_SERENITY", val)
    assert r.skill_enabled() is False


# --------------------------------------------------------------------------- #
# 2) 输入源：候选池（不是持仓）
# --------------------------------------------------------------------------- #
def test_load_universe_reads_pool_not_positions(tmp_path):
    r = _load_runner()
    _write_payload(tmp_path)
    uni, n = r.load_universe(tmp_path)
    assert n == 44, f"应读出 44 只候选，实得 {n}"
    assert len(uni) == 44
    assert sum(1 for u in uni if u["bucket"] == "Core") == 14
    assert sum(1 for u in uni if u["bucket"] == "Observation") == 30
    first = uni[0]
    for f in ("ticker", "name", "bucket", "final_score", "quant_score",
              "ai_score", "sector_rs_20d_pct", "held"):
        assert f in first, f"候选精简字段缺少 {f}"
    for bad in ("ohlcv", "technical", "ai"):
        assert bad not in first, f"不应把 {bad} 塞进输入（token 会爆）"


def test_load_universe_marks_held(tmp_path):
    r = _load_runner()
    _write_payload(tmp_path, held=("T00",))
    uni, _ = r.load_universe(tmp_path)
    assert {u["ticker"] for u in uni if u["held"]} == {"T00"}


def test_load_universe_missing_file_is_empty(tmp_path):
    r = _load_runner()
    assert r.load_universe(tmp_path) == ([], 0)


def test_main_does_not_write_when_universe_empty(tmp_path, monkeypatch, capsys):
    r = _load_runner()
    monkeypatch.setenv("ENABLE_SKILL_SERENITY", "1")
    out = tmp_path / "dashboard" / "data" / "skill_serenity.json"
    rc = r.main(["--data-dir", str(tmp_path), "--out", str(out)])
    assert rc == 0 and not out.exists()
    assert "候选池为空" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# 3) 输出结构：priorities[]（TOP 10）
# --------------------------------------------------------------------------- #
def test_output_is_priorities_top10(tmp_path, monkeypatch):
    r = _load_runner()
    monkeypatch.setenv("ENABLE_SKILL_SERENITY", "1")
    _write_payload(tmp_path)
    monkeypatch.setattr(r, "_default_ask", lambda *a, **k: _good_ai(10))
    out = tmp_path / "dashboard" / "data" / "skill_serenity.json"
    assert r.main(["--data-dir", str(tmp_path), "--out", str(out)]) == 0
    j = json.loads(out.read_text(encoding="utf-8"))

    assert j["schema_version"] == SCHEMA_V2
    assert j["mode"] == MODE_V2
    assert j["universe_size"] == 44
    assert j["source"] == SOURCE
    assert j["error"] is None
    assert "priorities" in j and "positions" not in j, "v2 必须是 priorities[]，不能再有 positions[]"
    assert len(j["priorities"]) == 10
    for i, p in enumerate(j["priorities"], 1):
        assert p["priority_rank"] == i, f"rank 必须连续 1..10，实得 {p['priority_rank']}"
        assert set(p) == {"ticker", "priority_rank", "why", "what_to_verify"}, p


def test_priorities_sorted_and_capped():
    r = _load_runner()
    pri = [
        {"ticker": "T05", "priority_rank": 5, "why": "e", "what_to_verify": "v"},
        {"ticker": "T00", "priority_rank": 9, "why": "e", "what_to_verify": "v"},
        {"ticker": "T02", "priority_rank": 2, "why": "e", "what_to_verify": "v"},
    ] + [{"ticker": f"T{i:02d}", "priority_rank": 20 + i, "why": "e", "what_to_verify": "v"}
         for i in range(10, 25)]
    raw = json.dumps({"priorities": pri}, ensure_ascii=False)
    pri = r.parse_result(raw, valid_tickers={f"T{i:02d}" for i in range(44)})["priorities"]
    assert len(pri) == 10, "必须截断到 TOP 10"
    assert [p["priority_rank"] for p in pri] == list(range(1, 11))
    assert [p["ticker"] for p in pri[:3]] == ["T02", "T05", "T00"]   # 按原 rank 升序并归一化


def test_parse_dedupes_and_rejects_unknown_ticker():
    r = _load_runner()
    raw = json.dumps({"priorities": [
        {"ticker": "T01", "priority_rank": 1, "why": "a", "what_to_verify": "v"},
        {"ticker": "T01", "priority_rank": 2, "why": "dup", "what_to_verify": "v"},
        {"ticker": "FAKE", "priority_rank": 3, "why": "幻觉造股票", "what_to_verify": "v"},
        {"ticker": "T03", "priority_rank": 4, "why": "b", "what_to_verify": "v"},
    ]}, ensure_ascii=False)
    got = r.parse_result(raw, valid_tickers={"T01", "T03"})
    assert [p["ticker"] for p in got["priorities"]] == ["T01", "T03"], "去重 + 拒绝池外 ticker"


def test_parse_raises_on_garbage():
    r = _load_runner()
    for bad in ("", "   ", "完全不是 JSON", '{"priorities": []}', '{"nope": 1}'):
        with pytest.raises(Exception):
            r.parse_result(bad)


# --------------------------------------------------------------------------- #
# 4) 数字纪律（正则清洗器，v1 复用 + 补中文数字盲区）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", [
    "收入 $7.21B", "份额 24%", "P/E 约 28.5", "EPS $1.02", "营收 1472 亿美元",
    "一万一千七百台装机", "百分之十五增长", "占了四成份额",
])
def test_sanitizer_strips_numbers_from_why(text):
    r = _load_runner()
    got = r.sanitize_priorities([{"ticker": "T00", "priority_rank": 1,
                                  "why": text, "what_to_verify": ""}])
    why = got[0]["why"]
    assert r.DIGIT_REMOVED in why, f"未命中数字：{text}"
    assert r.SANITIZED_SUFFIX in why
    assert r._NUMERIC_RE.search(why) is None, f"仍有残留：{why}"


@pytest.mark.parametrize("text", [
    "CEO 在财报电话会上表示「需求强劲」",
    '管理层说"产能仍是瓶颈"',
])
def test_sanitizer_strips_quotes(text):
    r = _load_runner()
    got = r.sanitize_priorities([{"ticker": "T00", "priority_rank": 1, "why": text, "what_to_verify": ""}])
    assert "[引语已剔除]" in got[0]["why"]


def test_sanitizer_leaves_clean_text_untouched():
    r = _load_runner()
    clean = "处于难替代的瓶颈环节，下游需求加速，产品已进入认证阶段"
    got = r.sanitize_priorities([{"ticker": "T00", "priority_rank": 1,
                                  "why": clean, "what_to_verify": "核验最新 10-Q 的分部收入"}])
    assert got[0]["why"] == clean


# --------------------------------------------------------------------------- #
# 5) prompt 契约
# --------------------------------------------------------------------------- #
def test_prompt_contains_universe_and_discipline():
    r = _load_runner()
    uni = [{"ticker": "ADSK", "name": "Autodesk", "bucket": "Core", "final_score": 69.9,
            "quant_score": 70, "ai_score": 65, "sector_rs_20d_pct": 1.2, "held": True}]
    p = r.build_prompt("SKILL_MD_TEXT", "", uni, "2026-10-13")
    assert "SKILL_MD_TEXT" in p
    assert "ADSK" in p and "Core" in p
    assert "供应链瓶颈猎手" in p
    assert "TOP 10" in p
    assert "不是买入建议" in p
    assert "数字纪律" in p and "禁止收入" in p and "禁止 P/E" in p
    assert "只能使用上表提供的字段" in p
    assert '"priorities"' in p
    assert "禁止引用管理层原话" in p
    assert "无法核验的，一律写进" in p
    assert "[方法论推理]" not in p


# --------------------------------------------------------------------------- #
# 6) R1 + 脚本模式 import
# --------------------------------------------------------------------------- #
def test_all_fail_does_not_write(tmp_path, monkeypatch):
    r = _load_runner()
    monkeypatch.setenv("ENABLE_SKILL_SERENITY", "1")
    _write_payload(tmp_path)
    monkeypatch.setattr(r, "_default_ask",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("all dead")))
    out = tmp_path / "dashboard" / "data" / "skill_serenity.json"
    assert r.main(["--data-dir", str(tmp_path), "--out", str(out)]) == 1
    assert not out.exists(), "R1：失败绝不能写文件"


def test_script_mode_import_resolves():
    """回归：以 `python skills/run_serenity.py` 运行时 clawsocket_compat 必须可导入。"""
    script = REPO_ROOT / "skills" / "run_serenity.py"
    code = (
        "import importlib.util,sys,os;"
        f"ROOT=os.path.normcase(os.path.abspath(r'{REPO_ROOT}'));"
        "sys.path=[p for p in sys.path if p and os.path.normcase(os.path.abspath(p))!=ROOT];"
        f"sys.path.insert(0, r'{script.parent}');"
        f"spec=importlib.util.spec_from_file_location('rr', r'{script}');"
        "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
        "import clawsocket_compat;print('OK')"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0 and "OK" in proc.stdout, (
        f"脚本模式下 clawsocket_compat 无法导入。\nstdout={proc.stdout}\nstderr={proc.stderr}")


def test_clawsocket_import_is_deferred():
    src = (REPO_ROOT / "skills" / "run_serenity.py").read_text(encoding="utf-8")
    for line in src.splitlines():
        if line.startswith("from clawsocket_compat") or line.startswith("import clawsocket_compat"):
            raise AssertionError(f"clawsocket_compat 出现在模块级：{line!r}")
    assert any(l.lstrip().startswith("from clawsocket_compat") for l in src.splitlines())


# --------------------------------------------------------------------------- #
# 7) dashboard_export 哨兵 + workflow
# --------------------------------------------------------------------------- #
def test_export_sentinel_when_file_missing(tmp_path):
    import dashboard_export as de
    assert de._read_skill_serenity(tmp_path) is de._SKILL_SERENITY_MISSING


def test_workflow_flag_is_job_level_and_gated():
    import re
    yml = (REPO_ROOT / ".github" / "workflows" / "skill-weekly.yml").read_text(encoding="utf-8")
    assert "ENABLE_SKILL_SERENITY: ${{ vars.ENABLE_SKILL_SERENITY }}" in yml
    assert "if: env.ENABLE_SKILL_SERENITY == '1'" in yml
    assert re.search(r"^\s*group:\s*skill-weekly\s*(#.*)?$", yml, re.M)
    assert not re.search(r"^\s*group:\s*us-stock-portfolio-ledger", yml, re.M)
    assert "git add dashboard/data/skill_serenity.json" in yml


# --------------------------------------------------------------------------- #
# 8) 前端：TOP 10 优先级卡片（非持仓卡片）
# --------------------------------------------------------------------------- #
_HARNESS = (
    "'use strict';\n"
    "globalThis.document={\n"
    "  addEventListener(){},querySelectorAll(){return[]},getElementById(){return null},\n"
    "  querySelector(sel){\n"
    "    globalThis.__els = globalThis.__els || {};\n"
    "    if(!globalThis.__els[sel]) globalThis.__els[sel] = {innerHTML:'',textContent:'',style:{}};\n"
    "    return globalThis.__els[sel];\n"
    "  }\n"
    "};\n"
    "globalThis.window={addEventListener(){},IT:null};\n"
    "globalThis.fetch=()=>Promise.resolve({json:()=>Promise.resolve({})});\n"
)


def _expose(app_js):
    out = app_js.replace(
        "\n  boot();\n",
        "\n  globalThis.__setSK = function(m){ if(!DATA) DATA={}; DATA.skill_serenity = m; };\n"
        "  globalThis.__renderSK = renderSkillSerenity;\n")
    assert "__renderSK" in out, "未能注入 renderSkillSerenity 暴露钩子"
    return out


def _run_node(exposed, tail):
    js = REPO_ROOT / "tests" / "_sk_harness.js"
    js.write_text(_HARNESS + exposed + tail, encoding="utf-8")
    try:
        proc = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"node 执行失败：{proc.stderr}"
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        js.unlink(missing_ok=True)


def _render_sk(sk):
    exposed = _expose((REPO_ROOT / "app.js").read_text(encoding="utf-8"))
    tail = (
        "\nglobalThis.__setSK(" + json.dumps(sk, ensure_ascii=False) + ");\n"
        "globalThis.__renderSK();\n"
        "var els = globalThis.__els || {};\n"
        "console.log(JSON.stringify({"
        " card_display: els['#skillSerenityCard'] ? els['#skillSerenityCard'].style.display : null,"
        " body: els['#skillSerenityBody'] ? els['#skillSerenityBody'].innerHTML : null,"
        " sub: els['#skillSerenitySub'] ? els['#skillSerenitySub'].textContent : null }));\n"
    )
    return _run_node(exposed, tail)


def test_frontend_hidden_when_no_priorities():
    for sk in (None, {}, {"priorities": []}):
        r = _render_sk(sk)
        assert r["card_display"] == "none", r
        assert not (r["body"] or ""), r


def test_frontend_renders_top10_priority_cards():
    r = _render_sk({
        "schema_version": SCHEMA_V2, "mode": MODE_V2, "skill_version": "1.1.0",
        "asof": "2026-10-13", "universe_size": 44, "error": None,
        "priorities": [
            {"ticker": "AMZN", "priority_rank": i + 1,
             "why": f"为什么第{i + 1}名：卡在网络/算力瓶颈层",
             "what_to_verify": f"核验 AMZN 第{i + 1}项材料"}
            for i in range(10)
        ],
    })
    assert r["card_display"] == "block", r
    body = r["body"]
    assert body.count('class="ss-card"') == 10, body
    assert "🎯 1" in body and "🎯 10" in body, body
    assert "为什么" in body and "待核验" in body, body
    assert "AMZN" in body, body
    assert "非买入建议" in body, body
    assert "未联网核验" in body, body
    for gone in ("业务定位", "盈利含义", "估值压力", "替代路线", "何时降级", "缺口"):
        assert gone not in body, f"v1 字段 {gone} 不应再渲染"
    assert r["sub"] and "TOP 10" in r["sub"], r


def test_frontend_no_offline_note_when_online_mode():
    r = _render_sk({
        "schema_version": SCHEMA_V2, "mode": "online",
        "priorities": [{"ticker": "X", "priority_rank": 1, "why": "a", "what_to_verify": "b"}],
    })
    assert "未联网核验" not in r["body"], r
