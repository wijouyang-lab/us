"""前端"已止损记录"板块测试（node 验证真实 app.js 的 renderStopped，磁盘 app.js 不变）。

复用 test_news_frontend_filter.py 的 node harness 思路：内存注入 document.querySelector
捕获钩子，用真实 app.js 代码断言渲染语义，不改动磁盘上的 app.js。

覆盖三态：
  1) 空 / 缺失 transactions → 显示「暂无止损记录」
  2) 含 SELL + Stop Loss → 正确渲染（筛选 / 统计 / 排序 / 入场价反推）
  3) 单条字段缺失 → 不崩、显示「—」
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
    js = REPO_ROOT / "tests" / "_stopped_harness.js"
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
        "\n  globalThis.__setData = function(d){ DATA = d; };\n"
        "  globalThis.__renderStopped = renderStopped;\n")
    assert "__renderStopped" in out, "未能注入 renderStopped 暴露钩子"
    return out


def _tail(data_json):
    return (
        "\nglobalThis.__setData(" + data_json + ");\n"
        "globalThis.__renderStopped();\n"
        "var els = globalThis.__els || {};\n"
        "console.log(JSON.stringify({\n"
        "  sub: els['#stoppedSub'] ? els['#stoppedSub'].textContent : null,\n"
        "  body: els['#stoppedBody'] ? els['#stoppedBody'].innerHTML : null\n"
        "}));\n"
    )


def test_stopped_empty_and_missing():
    """空 / 缺失 transactions → 显示「暂无止损记录」，不崩。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)

    # 1a) transactions 为空数组
    r1 = _run_node(exposed, _tail(json.dumps({"portfolio": {"transactions": []}})))
    assert "暂无止损记录" in (r1["body"] or ""), r1
    assert r1["sub"] == "—", r1

    # 1b) portfolio 整体缺失（null）
    r2 = _run_node(exposed, _tail(json.dumps({})))
    assert "暂无止损记录" in (r2["body"] or ""), r2

    # 1c) 只有 BUY、无 SELL → 过滤后为空 → 暂无
    payload_c = {"portfolio": {"transactions": [
        {"date": "2026-10-07", "ticker": "ADSK", "action": "BUY", "shares": 43,
         "price": 231.42, "amount": 9951.06, "realized_pnl": 0.0, "reason": "Core recommendation"}]}}
    r3 = _run_node(exposed, _tail(json.dumps(payload_c)))
    assert "暂无止损记录" in (r3["body"] or ""), r3


def test_stopped_render_with_stats():
    """含 SELL + Stop Loss → 正确渲染：筛选 / 统计 / 入场价反推 / 排序。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)

    # 入场价反推校验：ADSK SELL 43 股 @214，amount=9202(=43*214)，realized_pnl=-258.0
    #   cost_basis = 9202 - (-258) = 9460 → entry = 9460/43 = 220.0；ret% = -258/9460 = -2.7%
    data = {"portfolio": {"transactions": [
        {"date": "2026-10-01", "ticker": "ADSK", "action": "BUY", "shares": 43,
         "price": 220.0, "amount": 9460.0, "realized_pnl": 0.0, "reason": "Core"},
        {"date": "2026-10-05", "ticker": "ADSK", "action": "SELL", "shares": 43,
         "price": 214.0, "amount": 9202.0, "realized_pnl": -258.0, "reason": "Intraday Stop Loss"},
        {"date": "2026-10-06", "ticker": "INTC", "action": "SELL", "shares": 100,
         "price": 23.1, "amount": 2310.0, "realized_pnl": 50.0, "reason": "Trailing Stop Loss"},
        {"date": "2026-10-07", "ticker": "NVDA", "action": "SELL", "shares": 10,
         "price": 140.0, "amount": 1400.0, "realized_pnl": 120.0, "reason": "Profit Take"},
    ]}}
    r = _run_node(exposed, _tail(json.dumps(data)))
    body = r["body"] or ""
    sub = r["sub"] or ""

    # 筛选：只保留 2 条含 "Stop Loss" 的 SELL（ADSK/INTC），排除 BUY 与 Profit Take
    assert "总计: 2 笔" in sub, sub
    assert "胜率: —" in sub, sub            # 样本 < 10 → "—"
    assert "平均:" in sub, sub
    assert "ADSK" in body and "INTC" in body, body
    assert "NVDA" not in body, body         # Profit Take 被排除
    assert "Intraday Stop Loss" in body and "Trailing Stop Loss" in body, body

    # 入场价反推：ADSK $220.00 → $214.00；ret -2.7%
    assert "$220.00 → $214.00" in body, body
    assert "-2.7%" in body, body
    # 按日期降序：INTC(10-06) 在 ADSK(10-05) 之前
    assert body.find("INTC") < body.find("ADSK"), body

    # 胜率逻辑（构造 ≥10 样本验证数字胜率）—— 复用同一函数路径的单元验证
    many = {"portfolio": {"transactions": [
        {"date": "2026-10-0%d" % i, "ticker": "T%d" % i, "action": "SELL",
         "shares": 10, "price": 10.0, "amount": 100.0,
         "realized_pnl": (20.0 if i % 3 == 0 else -10.0),
         "reason": "Stop Loss %d" % i}
        for i in range(1, 13)
    ]}}
    # 12 条 SELL-Stop：i=3,6,9,12 为盈利(4 胜) → 胜率 33%
    r2 = _run_node(exposed, _tail(json.dumps(many)))
    assert "总计: 12 笔" in (r2["sub"] or ""), r2["sub"]
    assert "胜率: 33%" in (r2["sub"] or ""), r2["sub"]


def test_stopped_missing_fields_no_crash():
    """单条字段缺失 → 不崩，缺值显示「—」。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)

    # 一条 SELL-Stop 但 price/realized_pnl/shares 全部缺失（无法反推入场价与收益）
    data = {"portfolio": {"transactions": [
        {"date": "2026-10-05", "ticker": "ADSK", "action": "SELL",
         "reason": "Stop Loss"},  # 缺 price/shares/amount/realized_pnl
        {"date": "2026-10-06", "ticker": "INTC", "action": "SELL", "shares": 100,
         "price": 23.1, "amount": 2310.0, "realized_pnl": 50.0, "reason": "Trailing Stop Loss"},
    ]}}
    r = _run_node(exposed, _tail(json.dumps(data)))   # 不抛异常即通过（returncode==0）
    body = r["body"] or ""
    sub = r["sub"] or ""
    assert "总计: 2 笔" in sub, sub
    assert "ADSK" in body and "INTC" in body, body
    # 缺字段的那条：入场价区与收益区应出现「—」
    assert "—" in body, body
    assert "Stop Loss" in body, body
