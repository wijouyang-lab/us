# -*- coding: utf-8 -*-
"""serenity-skill runner + 展示层测试。

覆盖：
  1. flag 关 → `main()` 首行 return（零副作用：不读文件、不写文件、不调 AI）
  2. flag 开 + mock AI 成功 → 正确解析并落 JSON
  3. AI 失败 → 该只记 error，不崩；全部失败 → payload.error 标记（由 main 决定不落盘）
  4. 单只失败 → 其他 ticker 不受影响
  5. 模型输出非法 JSON / 带代码围栏 → 分别报错 / 正确剥离
  6. 前端：无数据 → 板块隐藏
  7. 前端：有数据 → 正确渲染（含离线提示）
  8. dashboard_export 哨兵：文件缺失 → 不注入 key（关闭时逐字节一致）
  9. workflow：flag 必须在 **job 级** env（step 级会让 `if` 恒 false）+ 独立 concurrency group
 10. clawsocket_compat 必须是延迟导入（flag 关时零依赖副作用）
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "skill_serenity.v1"
SOURCE = "serenity-skill by muxuuu (MIT)"


def _load_runner():
    p = REPO_ROOT / "skills" / "run_serenity.py"
    spec = importlib.util.spec_from_file_location("run_serenity_mod", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _positions():
    return [
        {"ticker": "ADSK", "unit": "U001", "shares": "43", "entry_price": "231.42",
         "entry_date": "2026-10-07", "current_price": "233.54", "stop_loss": "228.29",
         "unrealized_pnl_pct": "0.92", "weight_pct": "19.63"},
        {"ticker": "ANET", "unit": "U002", "shares": "47", "entry_price": "211.30",
         "entry_date": "2026-10-07", "current_price": "210.88", "stop_loss": "209.36",
         "unrealized_pnl_pct": "-0.20", "weight_pct": "19.37"},
    ]


_GOOD_AI = {
    "business_position": "卡在网络设备 / 数据中心交换层",
    "evidence": ["[持仓数据] 浮盈 0.92%", "[方法论推理] 需求来自 AI 数据中心资本开支"],
    "gaps": ["缺最新 10-Q 的园区网络分部毛利率", "缺客户集中度披露"],
    "earnings": "看网络设备分部收入增速与毛利率",
    "valuation": "无联网数据，不给倍数",
    "alternatives": "白盒交换机 / 客户自研",
    "what_would_change": "若数据中心资本开支指引下修，则降级",
}


# --------------------------------------------------------------------------- #
# 1) flag 关 —— 零副作用
# --------------------------------------------------------------------------- #
def test_flag_unset_returns_early(tmp_path, capsys):
    r = _load_runner()
    out = tmp_path / "skill_serenity.json"
    rc = r.main(["--data-dir", str(tmp_path), "--out", str(out)])
    assert rc == 0
    assert not out.exists(), "flag 关时绝不能写文件"
    assert "跳过" in capsys.readouterr().out


def test_flag_off_is_zero_side_effect_even_with_missing_dir(tmp_path, capsys):
    """flag 关时 data-dir 不存在也不应报错 —— 证明它确实没做任何 I/O。"""
    r = _load_runner()
    out = tmp_path / "o.json"
    rc = r.main(["--data-dir", str(tmp_path / "does-not-exist"), "--out", str(out)])
    assert rc == 0
    assert not out.exists()
    assert "跳过" in capsys.readouterr().out


@pytest.mark.parametrize("val", ["0", "true", "yes", "", "2", "TRUE"])
def test_only_exactly_1_enables(val, monkeypatch):
    r = _load_runner()
    monkeypatch.setenv("ENABLE_SKILL_SERENITY", val)
    assert r.skill_enabled() is False, f"只有 '1' 才应启用，val={val!r}"


def test_clawsocket_import_is_deferred():
    """`clawsocket_compat` 必须只在函数内部导入（延迟），不能是模块级。

    注意：不能用 strip() —— 缩进正是「在函数内」的标志。
    """
    src = (REPO_ROOT / "skills" / "run_serenity.py").read_text(encoding="utf-8")
    for line in src.splitlines():
        if line.startswith("from clawsocket_compat") or line.startswith("import clawsocket_compat"):
            raise AssertionError(f"clawsocket_compat 出现在模块级（第 1 列）：{line!r}")
    # 反向确认：确实存在一个缩进的延迟导入
    assert any(l.lstrip().startswith("from clawsocket_compat") for l in src.splitlines()), \
        "应当存在函数内的延迟导入"


# --------------------------------------------------------------------------- #
# 2) flag 开 + mock AI 成功
# --------------------------------------------------------------------------- #
def test_run_parses_ai_json(tmp_path):
    r = _load_runner()
    seen = {}

    def ask(prompt, model, max_tokens):
        seen["prompt"] = prompt
        seen["model"] = model
        return json.dumps(_GOOD_AI, ensure_ascii=False)

    got = r.run(tmp_path, tmp_path / "o.json", "SKILL_MD_TEXT", _positions()[:1],
                ask, "claude-opus-5-5", 6000, "2026-10-13")

    assert got["schema_version"] == SCHEMA
    assert got["source"] == SOURCE
    assert got["mode"] == "offline"          # 必须如实标注离线
    assert got["model"] == "claude-opus-5-5"
    assert got["error"] is None

    p = got["positions"][0]
    assert p["ticker"] == "ADSK" and p["error"] is None
    assert p["business_position"] == _GOOD_AI["business_position"]
    assert p["evidence"] == _GOOD_AI["evidence"]
    assert p["gaps"] == _GOOD_AI["gaps"]

    # prompt 必须真的带上框架文本 + 离线硬约束
    assert "SKILL_MD_TEXT" in seen["prompt"]
    assert "禁止编造" in seen["prompt"]
    assert "不要给综合数字评分" in seen["prompt"]


def test_main_writes_file_when_flag_on(tmp_path, monkeypatch):
    r = _load_runner()
    monkeypatch.setenv("ENABLE_SKILL_SERENITY", "1")
    # 造一个最小 positions.csv
    (tmp_path / "portfolio_50000_positions.csv").write_text(
        "Ticker,Status,Shares,Entry_Price,Current_Price,Stop_Loss,Recommendation_ID\n"
        "ADSK,OPEN,43,231.42,233.54,228.29,X\n",
        encoding="utf-8")
    monkeypatch.setattr(r, "_default_ask",
                        lambda prompt, model, max_tokens: json.dumps(_GOOD_AI, ensure_ascii=False))
    out = tmp_path / "dashboard" / "data" / "skill_serenity.json"
    rc = r.main(["--data-dir", str(tmp_path), "--out", str(out)])
    assert rc == 0
    assert out.exists()
    j = json.loads(out.read_text(encoding="utf-8"))
    assert j["schema_version"] == SCHEMA
    assert j["positions"][0]["ticker"] == "ADSK"


def test_load_positions_reads_only_open(tmp_path):
    r = _load_runner()
    (tmp_path / "portfolio_50000_positions.csv").write_text(
        "Ticker,Status,Shares,Entry_Price,Current_Price,Stop_Loss,Recommendation_ID\n"
        "ADSK,OPEN,43,231.42,233.54,228.29,X\n"
        "OLD,CLOSED,10,1,1,1,Y\n",
        encoding="utf-8")
    pos = r.load_positions(tmp_path)
    assert [p["ticker"] for p in pos] == ["ADSK"]


# --------------------------------------------------------------------------- #
# 3/4) 失败处理
# --------------------------------------------------------------------------- #
def test_ai_failure_records_error(tmp_path):
    r = _load_runner()

    def ask(*a, **k):
        raise RuntimeError("boom")

    got = r.run(tmp_path, tmp_path / "o.json", "S", _positions()[:1], ask, "m", 10, "2026-10-13")
    p = got["positions"][0]
    assert p["ticker"] == "ADSK"
    assert p["error"] and "boom" in p["error"]
    assert got["error"] == "全部持仓分析失败"


def test_single_failure_does_not_block_others(tmp_path):
    r = _load_runner()

    def ask(prompt, model, max_tokens):
        if "ANET" in prompt:
            raise RuntimeError("ANET 挂了")
        return json.dumps(_GOOD_AI, ensure_ascii=False)

    got = r.run(tmp_path, tmp_path / "o.json", "S", _positions(), ask, "m", 10, "2026-10-13")
    a, b = got["positions"]
    assert a["ticker"] == "ADSK" and a["error"] is None
    assert b["ticker"] == "ANET" and b["error"] and "ANET 挂了" in b["error"]
    assert got["error"] is None, "不是全部失败时 payload.error 应为 None"


def test_all_fail_does_not_write(tmp_path, monkeypatch, capsys):
    """R1：全部失败 → 不写文件。"""
    r = _load_runner()
    monkeypatch.setenv("ENABLE_SKILL_SERENITY", "1")
    (tmp_path / "portfolio_50000_positions.csv").write_text(
        "Ticker,Status,Shares,Entry_Price,Current_Price,Stop_Loss,Recommendation_ID\n"
        "ADSK,OPEN,43,231.42,233.54,228.29,X\n", encoding="utf-8")
    monkeypatch.setattr(r, "_default_ask", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("all dead")))
    out = tmp_path / "dashboard" / "data" / "skill_serenity.json"
    rc = r.main(["--data-dir", str(tmp_path), "--out", str(out)])
    assert rc == 1
    assert not out.exists(), "R1：全部失败绝不能写文件"


# --------------------------------------------------------------------------- #
# 5) 解析器
# --------------------------------------------------------------------------- #
def test_parse_result_strips_code_fence():
    r = _load_runner()
    got = r.parse_result('```json\n{"business_position":"x"}\n```')
    assert got["business_position"] == "x"
    assert got["evidence"] == [] and got["gaps"] == []


def test_parse_result_tolerates_surrounding_text():
    r = _load_runner()
    got = r.parse_result('好的，结果如下：\n{"business_position":"y","evidence":"单条"}\n以上。')
    assert got["business_position"] == "y"
    assert got["evidence"] == ["单条"]      # 非 list 会被包成单元素 list


@pytest.mark.parametrize("bad", ["", "   ", "完全不是 JSON"])
def test_parse_result_raises_on_garbage(bad):
    r = _load_runner()
    with pytest.raises(Exception):
        r.parse_result(bad)


# --------------------------------------------------------------------------- #
# 8) dashboard_export 哨兵：文件缺失 → 不注入 key
# --------------------------------------------------------------------------- #
def test_export_sentinel_when_file_missing(tmp_path):
    import dashboard_export as de
    assert de._read_skill_serenity(tmp_path) is de._SKILL_SERENITY_MISSING


def test_export_reads_when_present(tmp_path):
    import dashboard_export as de
    d = tmp_path / "dashboard" / "data"
    d.mkdir(parents=True)
    (d / "skill_serenity.json").write_text(json.dumps({"schema_version": SCHEMA}), encoding="utf-8")
    got = de._read_skill_serenity(tmp_path)
    assert got is not de._SKILL_SERENITY_MISSING
    assert got["schema_version"] == SCHEMA


def test_export_returns_none_on_bad_json(tmp_path):
    import dashboard_export as de
    d = tmp_path / "dashboard" / "data"
    d.mkdir(parents=True)
    (d / "skill_serenity.json").write_text("{ not json", encoding="utf-8")
    got = de._read_skill_serenity(tmp_path)
    assert got is None and got is not de._SKILL_SERENITY_MISSING


# --------------------------------------------------------------------------- #
# 9) workflow 结构
# --------------------------------------------------------------------------- #
def test_workflow_flag_is_job_level_and_gated():
    import re
    yml = (REPO_ROOT / ".github" / "workflows" / "skill-weekly.yml").read_text(encoding="utf-8")
    assert "ENABLE_SKILL_SERENITY: ${{ vars.ENABLE_SKILL_SERENITY }}" in yml
    assert "if: env.ENABLE_SKILL_SERENITY == '1'" in yml
    # 独立 concurrency group —— 只看**实际配置行**（注释里提到别的 group 不算违规）
    assert re.search(r"^\s*group:\s*skill-weekly\s*(#.*)?$", yml, re.M), "必须声明独立 group: skill-weekly"
    assert not re.search(r"^\s*group:\s*us-stock-portfolio-ledger", yml, re.M), \
        "不得与账本链路共享 concurrency group"
    # 只提交自己的产物
    assert "git add dashboard/data/skill_serenity.json" in yml


def test_workflow_flag_not_only_on_step_env():
    """回归：flag 若只写在 step 的 env: 里，该 step 的 `if` 读不到 → 永远跳过。"""
    yml = (REPO_ROOT / ".github" / "workflows" / "skill-weekly.yml").read_text(encoding="utf-8")
    steps_at = yml.find("    steps:")
    assert steps_at > 0
    assert "${{ vars.ENABLE_SKILL_SERENITY }}" in yml[:steps_at], (
        "flag 必须出现在 `steps:` 之前（= job 级 env），否则 if 恒为 false"
    )


# --------------------------------------------------------------------------- #
# 6/7) 前端
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
        " body: els['#skillSerenityBody'] ? els['#skillSerenityBody'].innerHTML : null }));\n"
    )
    return _run_node(exposed, tail)


def test_frontend_hidden_when_no_data():
    for sk in (None, {}, {"positions": []}):
        r = _render_sk(sk)
        assert r["card_display"] == "none", r
        assert not (r["body"] or ""), r


def test_frontend_renders_positions():
    r = _render_sk({
        "schema_version": SCHEMA, "source": SOURCE, "mode": "offline",
        "skill_version": "1.1.0", "asof": "2026-10-13", "error": None,
        "positions": [
            {"ticker": "ADSK", "business_position": "卡在网络交换层",
             "evidence": ["[持仓数据] 浮盈 0.92%"], "gaps": ["缺 10-Q 分部毛利率"],
             "earnings": "看分部增速", "valuation": "无联网数据", "alternatives": "白盒交换机",
             "what_would_change": "资本开支下修", "error": None},
            {"ticker": "ANET", "business_position": "", "evidence": [], "gaps": [],
             "earnings": "", "valuation": "", "alternatives": "", "what_would_change": "",
             "error": "RuntimeError: boom"},
        ],
    })
    assert r["card_display"] == "block", r
    body = r["body"]
    assert "ADSK" in body and "ANET" in body, body
    assert "业务定位" in body and "卡在网络交换层" in body, body
    assert "证据" in body and "[持仓数据] 浮盈 0.92%" in body, body
    assert "缺口" in body and "缺 10-Q 分部毛利率" in body, body
    assert "何时降级" in body and "资本开支下修" in body, body
    # 离线提示必须显示（不得暗示已联网核验）
    assert "未联网核验" in body, body
    # 单只失败要标出来，但不影响整块
    assert "分析失败" in body and "boom" in body, body


def test_frontend_no_offline_note_when_online_mode():
    r = _render_sk({
        "schema_version": SCHEMA, "mode": "online", "positions": [
            {"ticker": "ADSK", "business_position": "x", "evidence": [], "gaps": [],
             "earnings": "", "valuation": "", "alternatives": "", "what_would_change": "",
             "error": None}],
    })
    assert "未联网核验" not in r["body"], r


# --------------------------------------------------------------------------- #
# 11) 脚本模式 import 路径回归
#     真实事故：workflow 跑 `python skills/run_serenity.py` 时 sys.path[0] = skills/，
#     而 clawsocket_compat.py 在仓库根 → ModuleNotFoundError → 4 只全失败 → run 失败。
#     本地测试当时全绿，因为 (a) pytest 把 rootdir 放进 sys.path，
#     (b) 走 AI 的用例都把 _default_ask monkeypatch 掉了，真实 import 从未执行。
# --------------------------------------------------------------------------- #
def _script_mode_probe(extra: str) -> subprocess.CompletedProcess:
    """在真实子进程里复刻 `python skills/run_serenity.py` 的 sys.path，再执行 `extra`。

    ⚠️ 必须同时剔除 `''`：`python -c` 下 `sys.path[0]` 是空串（= cwd），
    只按字面路径过滤会漏掉它，cwd 会把仓库根偷偷带回来 → 测试**假通过**。
    （第一版测试就踩了这个坑：import 用例意外变绿，而静态用例才红。）
    """
    script = REPO_ROOT / "skills" / "run_serenity.py"
    code = (
        "import importlib.util,sys,os;"
        f"ROOT=os.path.normcase(os.path.abspath(r'{REPO_ROOT}'));"
        "sys.path=[p for p in sys.path if p and os.path.normcase(os.path.abspath(p))!=ROOT];"
        f"sys.path.insert(0, r'{script.parent}');"
        f"spec=importlib.util.spec_from_file_location('rr', r'{script}');"
        "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
        + extra
    )
    return subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, timeout=60)


def test_script_mode_import_resolves():
    """回归：以 `python skills/run_serenity.py` 运行时 clawsocket_compat 必须可导入。

    只验证 import 能否解析，不发起任何 AI 请求。修复前必须失败、修复后必须通过。
    """
    proc = _script_mode_probe("import clawsocket_compat;print('OK')")
    assert proc.returncode == 0 and "OK" in proc.stdout, (
        f"脚本模式下 clawsocket_compat 无法导入。\nstdout={proc.stdout}\nstderr={proc.stderr}")
