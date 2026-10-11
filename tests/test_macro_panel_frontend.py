"""前端"美股宏观板块"测试（node 验证真实 app.js 的 renderMacro，磁盘 app.js 不变）。

复用 test_stopped_frontend.py 的 node harness 思路：内存注入 document.querySelector
捕获钩子，用真实 app.js 代码断言渲染语义，不改动磁盘上的 app.js。

覆盖五态：
  1) MACRO 缺失 / null → 显示「宏观板块尚未开启」
  2) 含经济数据 + 讲话 + AI 判断 → 正确渲染（indicator/value/prev/delta/sentiment/rationale）
  3) economic/speakers 空数组 → 显示「暂无经济数据」「暂无重要讲话」
  4) macro.error 有值 → 显示「宏观数据暂不可用：...」
  5) 无 AI 判断（sentiment=null）→ 不渲染 🟢/🔴/⚪ 与 rationale，但板块头部正常
"""
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_node(transformed, tail):
    harness = (
        "globalThis.document={\n"
        "  addEventListener(){},querySelectorAll(){return[]},getElementById(){return null},\n"
        "  querySelector(sel){\n"
        "    globalThis.__els = globalThis.__els || {};\n"
        "    if(!globalThis.__els[sel]) globalThis.__els[sel] = {innerHTML:'',textContent:''};\n"
        "    return globalThis.__els[sel];\n"
        "  }\n"
        "};\n"
        "globalThis.window={addEventListener(){},IT:null};\n"
        "globalThis.fetch=()=>Promise.resolve({json:()=>Promise.resolve({})});\n"
    )
    js = REPO_ROOT / "tests" / "_macro_harness.js"
    js.write_text(harness + transformed + tail, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["node", str(js)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"node 执行失败：{proc.stderr}"
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        js.unlink(missing_ok=True)


def _expose(transformed):
    out = transformed.replace(
        "\n  boot();\n",
        "\n  globalThis.__setMacro = function(m){ MACRO = m; };\n"
        "  globalThis.__renderMacro = renderMacro;\n")
    assert "__renderMacro" in out, "未能注入 renderMacro 暴露钩子"
    return out


def _tail(macro_json):
    return (
        "\nglobalThis.__setMacro(" + macro_json + ");\n"
        "globalThis.__renderMacro();\n"
        "var els = globalThis.__els || {};\n"
        "console.log(JSON.stringify({\n"
        "  sub: els['#macroSub'] ? els['#macroSub'].textContent : null,\n"
        "  body: els['#macroBody'] ? els['#macroBody'].innerHTML : null\n"
        "}));\n"
    )


def _full_macro():
    return {
        "schema_version": "macro.v1",
        "generated_at": "2026-10-11T13:00:00Z",
        "economic": [
            {"indicator": "CPI", "value": "3.20%", "prev": None,
             "date": "2026-09", "source": "BLS",
             "sentiment": "bearish", "rationale": "通胀超预期施压"},
            {"indicator": "10Y国债", "value": "4.25%", "prev": "4.10%",
             "date": "2026-10-09", "source": "Yahoo Finance",
             "sentiment": "neutral", "rationale": "符合预期"},
        ],
        "speakers": [
            {"person": "Powell", "title": None,
             "content": "Powell says rates may stay higher for longer",
             "time": "10-09 14:30", "source": "Google News",
             "sentiment": "bearish", "rationale": "鹰派表态利空"},
            {"person": None, "title": None,
             "content": "Markets rally on soft landing hopes",
             "time": None, "source": None,
             "sentiment": "bullish", "rationale": "风险偏好回升"},
        ],
        "error": None,
    }


def test_macro_missing_and_null():
    """MACRO 缺失 / null → 显示「宏观板块尚未开启」，不崩。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)

    # 1a) MACRO 显式 null
    r1 = _run_node(exposed, _tail("null"))
    assert "宏观板块尚未开启" in (r1["body"] or ""), r1

    # 1b) MACRO 为空对象 {}（文件存在但无内容）→ 走空状态分支，不崩
    r2 = _run_node(exposed, _tail("{}"))
    assert "暂无经济数据" in (r2["body"] or ""), r2
    assert "暂无重要讲话" in (r2["body"] or ""), r2


def test_macro_render_with_ai():
    """含经济数据 + 讲话 + AI 判断 → 正确渲染 indicator/value/prev/delta/sentiment/rationale。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)

    r = _run_node(exposed, _tail(json.dumps(_full_macro())))
    body = r["body"] or ""
    sub = r["sub"] or ""

    # 头部
    assert "📊 经济数据" in body, body
    assert "🎙️ 重要人物讲话" in body, body
    # 更新时间
    assert "2026-10-11 13:00:00 UTC" in sub, sub

    # 经济数据：CPI 3.20%；10Y国债 4.25% + 前值 4.10% + 方向 ▲0.15pt（涨红 up）
    assert "CPI" in body and "3.20%" in body, body
    assert "10Y国债" in body and "4.25%" in body, body
    assert "前值 4.10%" in body, body
    assert "▲0.15pt" in body, body

    # 讲话：Powell 命中 + 原文；无 person 的条目也渲染原文
    assert "Powell" in body, body
    assert "Powell says rates may stay higher for longer" in body, body
    assert "Markets rally on soft landing hopes" in body, body

    # sentiment 图标：bearish🔴 / neutral⚪ / bullish🟢 均出现
    assert "🔴" in body, body
    assert "⚪" in body, body
    assert "🟢" in body, body

    # rationale 文本出现
    assert "通胀超预期施压" in body, body
    assert "鹰派表态利空" in body, body
    assert "风险偏好回升" in body, body


def test_macro_empty_arrays():
    """economic/speakers 空数组 → 显示「暂无经济数据」「暂无重要讲话」。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)

    macro = {"schema_version": "macro.v1", "generated_at": "2026-10-11T13:00:00Z",
             "economic": [], "speakers": [], "error": None}
    r = _run_node(exposed, _tail(json.dumps(macro)))
    body = r["body"] or ""
    assert "暂无经济数据" in body, body
    assert "暂无重要讲话" in body, body


def test_macro_error_shown():
    """macro.error 有值 → 显示「宏观数据暂不可用：...」。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)

    macro = {"schema_version": "macro.v1", "generated_at": "x",
             "economic": [{"indicator": "CPI", "value": "3.20%"}], "speakers": [],
             "error": "AI 超时"}
    r = _run_node(exposed, _tail(json.dumps(macro)))
    body = r["body"] or ""
    assert "宏观数据暂不可用：AI 超时" in body, body


def test_macro_no_ai_sentiment():
    """无 AI 判断（sentiment=null）→ 不渲染 🟢/🔴/⚪ 与 rationale，但板块头部与内容正常。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)

    macro = {"schema_version": "macro.v1", "generated_at": "2026-10-11T13:00:00Z",
             "economic": [{"indicator": "CPI", "value": "3.20%", "prev": None}],
             "speakers": [{"person": "Trump", "title": None, "content": "tariffs could spur inflation",
                           "time": None, "source": None, "sentiment": None, "rationale": None}],
             "error": None}
    r = _run_node(exposed, _tail(json.dumps(macro)))
    body = r["body"] or ""

    # 头部正常
    assert "📊 经济数据" in body, body
    assert "🎙️ 重要人物讲话" in body, body
    # 内容与 person 正常
    assert "CPI" in body and "3.20%" in body, body
    assert "Trump" in body, body
    assert "tariffs could spur inflation" in body, body
    # 无 AI 判断 → 不出现任何 sentiment 图标
    assert "🟢" not in body, body
    assert "🔴" not in body, body
    assert "⚪" not in body, body
    # 无 rationale 区块
    assert "news-rationale" not in body, body
