# -*- coding: utf-8 -*-
"""Recent Portfolio Transactions 前端渲染：成交时刻 + 持有时间 + 卖出时刻。

用真实 app.js 在 node 里跑（内存注入 document / window），断言 renderPortfolio：
  · 表头出现 Holding 列；
  · Date 列下方显示本笔 HH:MM（美东）；
  · Holding 列显示「买入 → 卖出」时刻与持有时间（两端有时刻 → 天+小时）；
  · 未平仓 BUY → 「持有中 · N 天」；
  · 历史无时刻（time=null）→ 只显示日期，绝不出现 undefined / NaN / 假 00:00。
"""
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _harness():
    return (
        "globalThis.document={\n"
        "  addEventListener(){},querySelectorAll(){return[]},getElementById(){return null},\n"
        "  createElement(){return {className:'',innerHTML:''};},\n"
        "  querySelector(sel){\n"
        "    globalThis.__els = globalThis.__els || {};\n"
        "    if(!globalThis.__els[sel]){\n"
        "      if(sel==='#pfTxns'){\n"
        "        globalThis.__els[sel]={innerHTML:'',textContent:'',parentNode:{inserted:null,insertBefore:function(n,r){this.inserted=n;}}};\n"
        "      } else {\n"
        "        globalThis.__els[sel]={innerHTML:'',textContent:'',style:{}};\n"
        "      }\n"
        "    }\n"
        "    return globalThis.__els[sel];\n"
        "  }\n"
        "};\n"
        "globalThis.window={addEventListener(){},IT:null};\n"
        "globalThis.fetch=()=>Promise.resolve({json:()=>Promise.resolve({})});\n"
    )


def _run_node(transformed, portfolio):
    js = REPO_ROOT / "tests" / "_pf_txns_harness.js"
    tail = (
        "\nglobalThis.__renderPortfolio(" + json.dumps(portfolio, ensure_ascii=False) + ");\n"
        "var el = globalThis.__els['#pfTxns'];\n"
        "console.log(JSON.stringify({html: el.innerHTML}));\n"
    )
    js.write_text(_harness() + transformed + tail, encoding="utf-8")
    try:
        proc = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"node 执行失败：{proc.stderr}"
        return json.loads(proc.stdout.strip().splitlines()[-1])["html"]
    finally:
        js.unlink(missing_ok=True)


def _expose():
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    out = app_js.replace(
        "\n  boot();\n",
        "\n  globalThis.__renderPortfolio = function(d){ DATA = d; renderPortfolio(); };\n")
    assert "__renderPortfolio" in out, "未能注入 renderPortfolio 暴露钩子"
    return out


def _txn(**kw):
    base = {"date": "2026-10-16", "ticker": "ADSK", "action": "SELL", "shares": 43,
            "price": 237.81, "amount": 10225.83, "realized_pnl": 274.77,
            "reason": "Review exit", "time": None, "entry_date": None,
            "entry_time": None, "exit_date": None, "exit_time": None,
            "holding_days": None, "holding_hours": None, "holding_open": None}
    base.update(kw)
    return base


def test_renders_time_columns_and_holding_span():
    html = _run_node(_expose(), {"portfolio": {"transactions": [
        _txn(action="BUY", realized_pnl=0.0, time="21:44",
             entry_date="2026-10-07", entry_time="21:44",
             exit_date="2026-10-16", exit_time="18:26",
             holding_days=9, holding_hours=212, holding_open=False),
        _txn(time="18:26", entry_date="2026-10-07", entry_time="21:44",
             exit_date="2026-10-16", exit_time="18:26",
             holding_days=9, holding_hours=212),
    ]}})
    assert "<th>Holding</th>" in html, html
    # 本笔时刻（Date 列副行）
    assert 'class="pf-time">21:44' in html, html
    assert 'class="pf-time">18:26' in html, html
    # 持有时间：212 小时 = 8 天 20 小时（精确到时刻，非仅日期相减）
    assert "8 天 20 小时" in html, html
    # 买入 → 卖出 时刻轴
    assert "10-07 21:44 → 10-16 18:26" in html, html
    assert "美东时间 ET" in html, html
    assert "undefined" not in html and "NaN" not in html, html


def test_open_buy_shows_holding_in_progress():
    html = _run_node(_expose(), {"portfolio": {"transactions": [
        _txn(ticker="APA", action="BUY", realized_pnl=0.0, time="18:26",
             entry_date="2026-10-19", entry_time="18:26",
             holding_days=1, holding_open=True),
    ]}})
    assert "持有中 · 1 天" in html, html
    assert "自 10-19 18:26" in html, html


def test_legacy_row_without_time_stays_date_only():
    html = _run_node(_expose(), {"portfolio": {"transactions": [
        _txn(date="2026-10-07", action="BUY", realized_pnl=0.0,
             entry_date="2026-10-07", holding_open=True, holding_days=3),
    ]}})
    assert "2026-10-07" in html, html
    assert "部分历史成交未记录时刻" in html, html
    assert 'class="pf-time"' not in html, html
    assert "00:00" not in html, html
    assert "undefined" not in html and "NaN" not in html, html
