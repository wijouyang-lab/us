# -*- coding: utf-8 -*-
"""止盈/止损展示三件套（真实 app.js + node harness）：

  1) 已止盈记录板块：只筛 Trailing_Profit_Take / Profit Take，30 天窗口，
     展示 买入价 → 卖出价、收益率、持有时间、原因；
  2) AI 目标持仓卡片：渲染 Stop_Loss（含相对参考价的跌幅）；
  3) 持仓卡片：止损线在入场价上方 → 显示「移动止盈 / 锁定 +%」，
     在下方 → 显示「止损 / 距入场 -%」。
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
        "        globalThis.__els[sel]={innerHTML:'',textContent:'',style:{},hidden:false,"
        "parentNode:{inserted:null,insertBefore:function(n,r){this.inserted=n;}}};\n"
        "      } else {\n"
        "        globalThis.__els[sel]={innerHTML:'',textContent:'',style:{},hidden:false};\n"
        "      }\n"
        "    }\n"
        "    return globalThis.__els[sel];\n"
        "  }\n"
        "};\n"
        "globalThis.window={addEventListener(){},IT:null};\n"
        "globalThis.fetch=()=>Promise.resolve({json:()=>Promise.resolve({})});\n"
    )


def _expose():
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    out = app_js.replace(
        "\n  boot();\n",
        "\n  globalThis.__setData = function(d){ DATA = d; };\n"
        "  globalThis.__run = function(){ renderPortfolio(); renderTarget(); renderProfitTaken(); renderStopped(); };\n")
    assert "__setData" in out, "未能注入 expose 钩子"
    return out


def _run(data):
    js = REPO_ROOT / "tests" / "_profit_harness.js"
    tail = (
        "\nglobalThis.__setData(" + json.dumps(data, ensure_ascii=False) + ");\n"
        "globalThis.__run();\n"
        "var e = globalThis.__els || {};\n"
        "console.log(JSON.stringify({\n"
        "  profitSub: e['#profitSub'] ? e['#profitSub'].textContent : null,\n"
        "  profitBody: e['#profitBody'] ? e['#profitBody'].innerHTML : null,\n"
        "  target: e['#pfTarget'] ? e['#pfTarget'].innerHTML : null,\n"
        "  positions: e['#pfPositions'] ? e['#pfPositions'].innerHTML : null\n"
        "}));\n"
    )
    js.write_text(_harness() + _expose() + tail, encoding="utf-8")
    try:
        proc = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, f"node 执行失败：{proc.stderr}"
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        js.unlink(missing_ok=True)


def test_profit_taken_panel_filters_and_formats():
    data = {"portfolio": {"positions": [], "target": [], "transactions": [
        {"date": "2026-10-16", "time": "18:26", "ticker": "ADSK", "action": "SELL",
         "shares": 43, "price": 237.81, "amount": 10225.83, "realized_pnl": 274.77,
         "reason": "Review exit: Trailing_Profit_Take",
         "entry_price": 231.42, "exit_price": 237.81,
         "entry_date": "2026-10-07", "exit_date": "2026-10-16",
         "holding_days": 9, "holding_hours": 212},
        {"date": "2026-10-05", "ticker": "INTC", "action": "SELL", "shares": 100,
         "price": 23.10, "amount": 2310.0, "realized_pnl": 50.0,
         "reason": "Profit Take", "entry_price": 22.60, "exit_price": 23.10,
         "holding_days": 4},
        {"date": "2026-08-01", "ticker": "OLD", "action": "SELL", "shares": 10,
         "price": 11.0, "amount": 110.0, "realized_pnl": 10.0, "reason": "Profit Take"},
        {"date": "2026-10-15", "ticker": "KR", "action": "SELL", "shares": 168,
         "price": 60.68, "amount": 10194.24, "realized_pnl": 236.88,
         "reason": "Review exit: Stop_Loss_Hit"},
        {"date": "2026-10-07", "ticker": "ADSK", "action": "BUY", "shares": 43,
         "price": 231.42, "amount": 9951.06, "realized_pnl": 0.0, "reason": "Core"},
    ]}}
    r = _run(data)
    sub = r["profitSub"] or ""
    body = r["profitBody"] or ""

    assert "总计: 2 笔" in sub, sub          # OLD 超出 30 天窗口被排除
    assert "合计: +$324.77" in sub, sub     # 274.77 + 50
    assert "ADSK" in body and "INTC" in body, body
    assert "OLD" not in body and "KR" not in body, body   # 止损/超窗不进止盈板块
    assert "$231.42 → $237.81" in body, body
    assert "持有 8 天 20 小时" in body, body
    assert "+2.8%" in body, body
    assert "Trailing_Profit_Take" in body, body
    # 月度汇总：只剩 2026-10 的 2 笔，合计 +$324.77
    assert "2026-10 · 2 笔 · +$324.77" in body, body
    assert "2026-08" not in body, body        # 超窗记录不参与月度汇总


def test_target_card_renders_stop_loss():
    data = {"portfolio": {"positions": [], "transactions": [], "target": [
        {"scan_date": "2026-10-26", "ticker": "AMT", "action": "BUY",
         "target_shares": 66, "ref_price": 188.97,
         "stop_loss": "$177.22", "stop_loss_price": 177.22,
         "ai_reason": "盘前回调"},
    ]}}
    r = _run(data)
    target = r["target"] or ""
    assert "止损" in target, target
    assert "$177.22" in target, target
    assert "-6.2%" in target, target        # 177.22/188.97-1
    assert "AMT" in target and "BUY" in target, target


def test_position_card_marks_trailing_profit_vs_stop_loss():
    base = {"ticker": "ADSK", "shares": 43, "entry_price": 231.42,
            "current_price": 240.0, "market_value": 10320.0,
            "unrealized_pnl": 368.94, "unrealized_pnl_pct": 3.7,
            "weight_pct": 20.0, "holding_days": 9}
    rules = {"exit_rules": {"breakeven_trigger_pct": 5.0}}

    up = _run({"portfolio": dict(rules, target=[], transactions=[],
                                 positions=[dict(base, stop_loss="240.00", stop_loss_price=240.0)])})
    html_up = up["positions"] or ""
    # 止损线已抬到入场价上方 → 止损价与止盈价是同一条移动线
    assert "止损价" in html_up and "止盈价" in html_up, html_up
    assert "止损价</span><b class=\"down\">$240.00（距现价 0.0%）" in html_up, html_up
    assert "止盈价</span><b class=\"up\">$240.00（锁定 +3.7%）" in html_up, html_up
    # 风控距离条：止损/入场/现价三个刻度 + 色带
    assert 'class="prb-track"' in html_up, html_up
    assert 'class="prb-stop"' in html_up and 'class="prb-entry"' in html_up and 'class="prb-cur"' in html_up, html_up
    assert "入场 $231.42（+3.7%）" in html_up, html_up
    assert "现价 $240.00" in html_up, html_up
    # 色带：止损线已抬到入场价上方 → 只有「已锁定盈利」绿段，没有风险红段
    assert 'class="prb-zone up"' in html_up, html_up
    assert 'class="prb-zone down"' not in html_up, html_up

    down = _run({"portfolio": dict(rules, target=[], transactions=[],
                                   positions=[dict(base, stop_loss="220.00", stop_loss_price=220.0)])})
    html_down = down["positions"] or ""
    assert "止损价</span><b class=\"down\">$220.00（距现价 -8.3%）" in html_down, html_down
    # 未激活：不编目标价，显示保本价 + 真实的 +5% 激活阈值（来自 exit_rules）
    assert "止盈价</span><b class=\"flat\">$231.42（保本待激活，浮盈 +5% 后抬保本）" in html_down, html_down
    # 色带：止损→入场为红（风险区），入场→现价为绿（浮盈区）
    assert 'class="prb-zone down"' in html_down, html_down
    assert 'class="prb-zone up"' in html_down, html_down
