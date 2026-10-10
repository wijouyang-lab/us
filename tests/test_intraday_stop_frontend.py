"""前端"盘中止损横幅"测试（node 验证真实 app.js 的 renderIntradayStops，磁盘 app.js 不变）。

复用 test_stopped_frontend.py 的 node harness 思路：内存注入 document.querySelector
捕获钩子，用真实 app.js 代码断言横幅渲染语义，不改动磁盘上的 app.js。

覆盖：
  1) transactions 含 Intraday Stop Loss SELL → 横幅渲染，.is-row 数量正确
  2) 无 Intraday Stop Loss（仅 BUY / 其它原因 SELL）→ 横幅不渲染
  3) #pfTxns 缺失 → 函数提前 return，不崩、不渲染
"""
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _harness(null_pftxns=False):
    if null_pftxns:
        pf = "if(sel==='#pfTxns'){return null;}\n"
    else:
        pf = ("if(sel==='#pfTxns'){\n"
              "  globalThis.__els[sel]={innerHTML:'',textContent:'',parentNode:{inserted:null,insertBefore:function(n,r){this.inserted=n;}}};\n"
              "} else {\n"
              "  globalThis.__els[sel]={innerHTML:'',textContent:''};\n"
              "}\n")
    return (
        "globalThis.document={\n"
        "  addEventListener(){},querySelectorAll(){return[]},getElementById(){return null},\n"
        "  createElement(){return {className:'',innerHTML:''};},\n"
        "  querySelector(sel){\n"
        "    globalThis.__els = globalThis.__els || {};\n"
        "    if(!globalThis.__els[sel]){\n"
        + pf +
        "      }\n"
        "    return globalThis.__els[sel];\n"
        "  }\n"
        "};\n"
        "globalThis.window={addEventListener(){},IT:null};\n"
        "globalThis.fetch=()=>Promise.resolve({json:()=>Promise.resolve({})});\n"
    )


def _run_node(transformed, tail, null_pftxns=False):
    js = REPO_ROOT / "tests" / "_intraday_harness.js"
    js.write_text(_harness(null_pftxns) + transformed + tail, encoding="utf-8")
    try:
        proc = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"node 执行失败：{proc.stderr}"
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        js.unlink(missing_ok=True)


def _expose(transformed):
    out = transformed.replace(
        "\n  boot();\n",
        "\n  globalThis.__renderIntradayStops = renderIntradayStops;\n")
    assert "__renderIntradayStops" in out, "未能注入 renderIntradayStops 暴露钩子"
    return out


def _tail(portfolio_json):
    return (
        "\nglobalThis.__renderIntradayStops(" + portfolio_json + ");\n"
        "var els = globalThis.__els || {};\n"
        "var pftxns = els['#pfTxns'];\n"
        "var banner = (pftxns && pftxns.parentNode) ? pftxns.parentNode.inserted : null;\n"
        "var rows = banner ? (banner.innerHTML.match(/is-row/g) || []).length : 0;\n"
        "console.log(JSON.stringify({\n"
        "  bannerExists: !!banner,\n"
        "  bannerClass: banner ? banner.className : null,\n"
        "  isRows: rows,\n"
        "  html: banner ? banner.innerHTML : null\n"
        "}));\n"
    )


def test_intraday_banner_renders_two():
    """含 2 条 Intraday Stop Loss SELL → 横幅渲染，.is-row = 2。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)
    data = {"portfolio": {"transactions": [
        {"date": "2026-10-07", "ticker": "ADSK", "action": "BUY", "shares": 43,
         "price": 231.42, "amount": 9951.06, "realized_pnl": 0.0, "reason": "Core"},
        {"date": "2026-10-09", "ticker": "ADSK", "action": "SELL", "shares": 43,
         "price": 226.10, "amount": 9722.30, "realized_pnl": -228.76, "reason": "Intraday Stop Loss"},
        {"date": "2026-10-08", "ticker": "ANET", "action": "SELL", "shares": 15,
         "price": 139.40, "amount": 2091.00, "realized_pnl": -121.50, "reason": "Intraday Stop Loss"},
    ]}}
    r = _run_node(exposed, _tail(json.dumps(data["portfolio"])))
    assert r["bannerExists"] is True, r
    assert r["bannerClass"] == "intraday-stop", r
    assert r["isRows"] == 2, r
    assert "ADSK" in (r["html"] or "") and "ANET" in (r["html"] or ""), r
    assert "盘中机械止损" in (r["html"] or ""), r


def test_intraday_banner_absent_without_intraday():
    """无 Intraday Stop Loss（仅 BUY / 其它原因 SELL）→ 横幅不渲染。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)

    # 1a) 仅 BUY
    r1 = _run_node(exposed, _tail(json.dumps({"transactions": [
        {"date": "2026-10-07", "ticker": "ADSK", "action": "BUY", "shares": 43,
         "price": 231.42, "amount": 9951.06, "realized_pnl": 0.0, "reason": "Core"}]})))
    assert r1["bannerExists"] is False, r1

    # 1b) 有 SELL 但 reason 不是精确的 "Intraday Stop Loss"（如 Trailing Stop Loss）
    r2 = _run_node(exposed, _tail(json.dumps({"transactions": [
        {"date": "2026-10-08", "ticker": "INTC", "action": "SELL", "shares": 100,
         "price": 23.1, "amount": 2310.0, "realized_pnl": 50.0, "reason": "Trailing Stop Loss"}]})))
    assert r2["bannerExists"] is False, r2


def test_intraday_banner_missing_pftxns_no_crash():
    """#pfTxns 缺失 → 函数提前 return，不崩、不渲染。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)
    r = _run_node(exposed, _tail(json.dumps({"transactions": [
        {"date": "2026-10-09", "ticker": "ADSK", "action": "SELL", "shares": 43,
         "price": 226.10, "amount": 9722.30, "realized_pnl": -228.76, "reason": "Intraday Stop Loss"}]})),
        null_pftxns=True)
    assert r["bannerExists"] is False, r
