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


def _expose_visible(app_js):
    out = app_js.replace(
        "\n  boot();\n",
        "\n  globalThis.__isNewsVisible = isNewsVisible;\n")
    assert "__isNewsVisible" in out, "未能注入 isNewsVisible 暴露钩子"
    return out


def test_is_news_visible_neutral_hidden():
    """sentiment === 'neutral' → 不渲染（无论 market_relevant 为何值）。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    transformed = _expose_visible(app_js)
    tail = (
        "\nconst f = globalThis.__isNewsVisible;\n"
        "console.log(JSON.stringify({\n"
        "  neutralHidden: f({headline:'n',sentiment:'neutral'}) === false,\n"
        "  neutralRelevantHidden: f({headline:'n',sentiment:'neutral',market_relevant:true}) === false,\n"
        "}));\n"
    )
    r = _run_node(transformed, tail)
    assert r["neutralHidden"] is True
    assert r["neutralRelevantHidden"] is True


def test_is_news_visible_bullish_shown():
    """sentiment === 'bullish' → 渲染；但若 market_relevant === false 仍隐藏。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    transformed = _expose_visible(app_js)
    tail = (
        "\nconst f = globalThis.__isNewsVisible;\n"
        "console.log(JSON.stringify({\n"
        "  bullishShown: f({headline:'n',sentiment:'bullish'}) === true,\n"
        "  bullishRelevantFalseHidden: f({headline:'n',sentiment:'bullish',market_relevant:false}) === false,\n"
        "}));\n"
    )
    r = _run_node(transformed, tail)
    assert r["bullishShown"] is True
    assert r["bullishRelevantFalseHidden"] is True


def test_is_news_visible_bearish_shown():
    """sentiment === 'bearish' → 渲染；但若 market_relevant === false 仍隐藏。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    transformed = _expose_visible(app_js)
    tail = (
        "\nconst f = globalThis.__isNewsVisible;\n"
        "console.log(JSON.stringify({\n"
        "  bearishShown: f({headline:'n',sentiment:'bearish'}) === true,\n"
        "  bearishRelevantFalseHidden: f({headline:'n',sentiment:'bearish',market_relevant:false}) === false,\n"
        "}));\n"
    )
    r = _run_node(transformed, tail)
    assert r["bearishShown"] is True
    assert r["bearishRelevantFalseHidden"] is True


def test_is_news_visible_missing_kept():
    """sentiment 缺失 → 保留（向后兼容旧数据：不误删）。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    transformed = _expose_visible(app_js)
    tail = (
        "\nconst f = globalThis.__isNewsVisible;\n"
        "console.log(JSON.stringify({\n"
        "  missingKept: f({headline:'n'}) === true,\n"
        "  nullKept: f(null) === true,\n"
        "  relevantFalseNoSentimentHidden: f({headline:'n',market_relevant:false}) === false,\n"
        "}));\n"
    )
    r = _run_node(transformed, tail)
    assert r["missingKept"] is True
    assert r["nullKept"] is True
    assert r["relevantFalseNoSentimentHidden"] is True


def _run_node_render(transformed, tail):
    """更完整的 harness：document.querySelector 按选择器持久化捕获元素（用于断言渲染结果）。"""
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
    js = REPO_ROOT / "tests" / "_news_render_harness.js"
    js.write_text(harness + transformed + tail, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["node", str(js)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"node 执行失败：{proc.stderr}"
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        js.unlink(missing_ok=True)


def test_render_news_all_neutral_shows_na():
    """市场新闻全部 neutral → 全部被过滤 → 显示『暂无相关市场新闻』，不崩、不残留 neutral 原文。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    transformed = app_js.replace(
        "\n  boot();\n",
        "\n  globalThis.__setData = function(d){ DATA = d; };\n"
        "  globalThis.__renderNews = renderNews;\n")
    assert "__renderNews" in transformed, "未能注入 renderNews 暴露钩子"

    news = {
        "generated_at": "2026-10-12T13:00:00Z",
        "market_news": [
            {"headline": "neutral-A", "sentiment": "neutral"},
            {"headline": "neutral-B", "sentiment": "neutral", "market_relevant": True},
        ],
        "positions": [],
    }
    tail = (
        "\nglobalThis.__setData({news:" + json.dumps(news) + "});\n"
        "globalThis.__renderNews();\n"
        "var els = globalThis.__els || {};\n"
        "console.log(JSON.stringify({\n"
        "  market: els['#newsMarket'] ? els['#newsMarket'].innerHTML : null\n"
        "}));\n"
    )
    r = _run_node_render(transformed, tail)
    market = r["market"] or ""
    assert "暂无相关市场新闻" in market, market
    # 任意一条 neutral 原文都不应残留（确认确实被过滤，而非仅文本未渲染）
    assert "neutral-A" not in market and "neutral-B" not in market, market
