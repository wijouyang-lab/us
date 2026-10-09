"""前端市场相关度过滤测试（node 验证真实 app.js 的 isMarketRelevant，磁盘 app.js 不变）。

复用 test_fetch_news.py 的 node harness 思路：内存注入函数暴露钩子，
用真实 app.js 代码断言过滤语义，不改动磁盘上的 app.js。
"""
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_node(transformed, tail):
    harness = (
        "globalThis.document={addEventListener(){},querySelectorAll(){return[]},"
        "getElementById(){return null}};\n"
        "globalThis.window={addEventListener(){}};\n"
        "globalThis.fetch=()=>Promise.resolve({json:()=>Promise.resolve({})});\n"
        "globalThis.$=()=>({innerHTML:'',textContent:'',map:()=>[],forEach:()=>[]});\n"
    )
    js = REPO_ROOT / "tests" / "_news_filter_harness.js"
    js.write_text(harness + transformed + tail, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["node", str(js)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"node 执行失败：{proc.stderr}"
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        js.unlink(missing_ok=True)


def test_is_market_relevant_filter():
    """真实 app.js 的 isMarketRelevant：false → 过滤；缺失/true → 显示。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    transformed = app_js.replace(
        "\n  boot();\n", "\n  globalThis.__isMarketRelevant = isMarketRelevant;\n")
    assert "globalThis.__isMarketRelevant" in transformed, "未能注入 isMarketRelevant 暴露钩子"

    tail = (
        "\nconst f = globalThis.__isMarketRelevant;\n"
        # 仅含 true/false 的数组：3 条 → 仅 1 条 true 保留
        "const keepFalse = [{market_relevant:false},{market_relevant:true},{market_relevant:false}]\n"
        "  .filter(f).length;\n"
        # 混合：缺失 + true + 缺失 + false → 4 条 → 3 条保留（两个缺失 + true）
        "const keepMixed = [{headline:'a'},{market_relevant:true},{headline:'b'},{market_relevant:false}]\n"
        "  .filter(f).length;\n"
        "console.log(JSON.stringify({\n"
        "  falseHidden: f({market_relevant:false}) === false,\n"
        "  trueShown: f({market_relevant:true}) === true,\n"
        "  missingShown: f({headline:'x'}) === true,\n"
        "  nullShown: f(null) === true,\n"
        "  keepFalse: keepFalse,\n"
        "  keepMixed: keepMixed\n"
        "}));\n"
    )
    r = _run_node(transformed, tail)
    assert r["falseHidden"] is True
    assert r["trueShown"] is True
    assert r["missingShown"] is True
    assert r["nullShown"] is True
    assert r["keepFalse"] == 1
    assert r["keepMixed"] == 3
