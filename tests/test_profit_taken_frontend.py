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
        "  globalThis.__setMacro = function(m){ MACRO = m; };\n"
        "  globalThis.__run = function(){ renderPortfolio(); renderTarget(); renderProfitTaken(); renderStopped(); renderOversold(); renderMarketIndicators(); renderMacro(); };\n")
    assert "__setData" in out, "未能注入 expose 钩子"
    return out


def _run(data):
    js = REPO_ROOT / "tests" / "_profit_harness.js"
    tail = (
        "\nglobalThis.__setData(" + json.dumps(data, ensure_ascii=False) + ");\n"
        "globalThis.__setMacro((" + json.dumps(data, ensure_ascii=False) + ").macro || null);\n"
        "globalThis.__run();\n"
        "var e = globalThis.__els || {};\n"
        "console.log(JSON.stringify({\n"
        "  profitSub: e['#profitSub'] ? e['#profitSub'].textContent : null,\n"
        "  profitBody: e['#profitBody'] ? e['#profitBody'].innerHTML : null,\n"
        "  target: e['#pfTarget'] ? e['#pfTarget'].innerHTML : null,\n"
        "  positions: e['#pfPositions'] ? e['#pfPositions'].innerHTML : null,\n"
        "  summary: e['#pfSummary'] ? e['#pfSummary'].innerHTML : null,\n"
        "  stopped: e['#stoppedBody'] ? e['#stoppedBody'].innerHTML : null,\n"
        "  oversold: e['#oversoldBody'] ? e['#oversoldBody'].innerHTML : null,\n"
        "  oversoldHidden: e['#oversoldCard'] ? e['#oversoldCard'].hidden : null,\n"
        "  oversoldSub: e['#oversoldSub'] ? e['#oversoldSub'].textContent : null,\n"
        "  market: e['#marketIndicatorsBody'] ? e['#marketIndicatorsBody'].innerHTML : null,\n"
        "  macro: e['#macroBody'] ? e['#macroBody'].innerHTML : null\n"
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
    # 未激活：显示下一档「目标参考价」= 入场 × (1+5%)，并标注是目标参考而非固定出场价
    assert "止盈价</span><b class=\"flat\">$242.99（目标参考 +5% · 抬保本）" in html_down, html_down
    # 色带：止损→入场为红（风险区），入场→现价为绿（浮盈区）
    assert 'class="prb-zone down"' in html_down, html_down
    assert 'class="prb-zone up"' in html_down, html_down


def test_position_card_next_profit_target_tier():
    """浮盈 16.7% 已过 +15% 档 → 止盈价显示下一档 +30% 的目标参考价（锁 8% 回撤）。"""
    rules = {"exit_rules": {"breakeven_trigger_pct": 5.0,
                            "profit_lock_1_pct": 15.0, "profit_lock_1_drawdown_pct": 10.0,
                            "profit_lock_2_pct": 30.0, "profit_lock_2_drawdown_pct": 8.0,
                            "profit_lock_3_pct": 50.0, "profit_lock_3_drawdown_pct": 12.0}}
    pos = {"ticker": "MSFT", "shares": 10, "entry_price": 240.0, "current_price": 280.0,
           "market_value": 2800.0, "unrealized_pnl": 400.0, "unrealized_pnl_pct": 16.67,
           "weight_pct": 10.0, "holding_days": 12,
           "stop_loss": "252.00", "stop_loss_price": 252.0}   # 已抬到入场上方 → 已激活
    r = _run({"portfolio": dict(rules, target=[], transactions=[], positions=[pos])})
    html = r["positions"] or ""
    assert "止盈价</span><b class=\"up\">$252.00（锁定 +5.0%）" in html, html

    # 把止损线放回入场下方（未激活）→ 看下一档目标参考价
    pos2 = dict(pos, stop_loss="230.00", stop_loss_price=230.0)
    r2 = _run({"portfolio": dict(rules, target=[], transactions=[], positions=[pos2])})
    html2 = r2["positions"] or ""
    assert "止盈价</span><b class=\"flat\">$312.00（目标参考 +30% · 锁 8% 回撤）" in html2, html2


def test_month_chips_use_backend_full_ledger():
    """月度汇总优先用后端全量聚合（closed_months），不受 20 条展示截断影响。"""
    data = {"portfolio": {
        "target": [], "positions": [],
        "closed_months": [
            {"month": "2026-10", "profit": {"n": 3, "pnl": 100.0},
             "stop": {"n": 7, "pnl": -50.0}},
            {"month": "2026-09", "profit": {"n": 2, "pnl": 40.0},
             "stop": {"n": 1, "pnl": -10.0}},
        ],
        # 展示窗口只剩 1 条，但月度 chip 应该是全量的 7 笔
        "transactions": [
            {"date": "2026-10-13", "ticker": "KR", "action": "SELL", "shares": 168,
             "price": 60.68, "amount": 10194.24, "realized_pnl": 236.88,
             "reason": "Review exit: Stop_Loss_Hit"},
        ],
    }}
    r = _run(data)
    stopped = r["stopped"] or ""
    assert "2026-10 · 7 笔 · -$50.00" in stopped, stopped
    assert "2026-09 · 1 笔 · -$10.00" in stopped, stopped
    profit = r["profitBody"] or ""
    assert "2026-10 · 3 笔 · +$100.00" in profit, profit
    assert "2026-09 · 2 笔 · +$40.00" in profit, profit


def test_summary_risk_and_snapshot_note():
    """概览：组合最大风险 + 快照落后提示；卡片：单笔最大亏损 + 色带图例。"""
    pos = {"ticker": "ADSK", "shares": 10, "entry_price": 100.0, "current_price": 105.0,
           "market_value": 1050.0, "unrealized_pnl": 50.0, "unrealized_pnl_pct": 5.0,
           "weight_pct": 10.0, "holding_days": 3,
           "stop_loss": "90.00", "stop_loss_price": 90.0}
    data = {"portfolio": {
        "target": [], "transactions": [], "positions": [pos],
        "total_equity": 10000.0, "initial_capital": 10000.0, "cash": 8950.0,
        "stock_value": 1050.0, "total_pnl": 0.0, "return_pct": 0.0,
        "realized_pnl": 0.0, "unrealized_pnl": 50.0, "open_positions": 1,
        "open_pct": 10.5, "start_date": "2026-10-01",
        "asof": "2026-10-22", "snapshot_asof": "2026-10-20", "rolled_txns": 2,
    }}
    r = _run(data)
    summary = r["summary"] or ""
    # (100-90)*10 = $100 → 100 / 10000 = 1.00%
    assert "组合最大风险" in summary, summary
    assert "1.00%（$100.00）" in summary, summary
    assert "2 笔成交发生在权益快照（2026-10-20）之后" in summary, summary

    html = r["positions"] or ""
    assert "最大亏损" in html and "-$100.00" in html, html
    assert "（1.0% 权益）" in html, html
    assert "▲ 盈利区（入场 → 现价/止盈线）" in html, html
    assert "▼ 风险区（止损 → 入场）" in html, html


def test_position_without_stop_warns():
    pos = {"ticker": "XYZ", "shares": 10, "entry_price": 100.0, "current_price": 101.0,
           "market_value": 1010.0, "unrealized_pnl": 10.0, "unrealized_pnl_pct": 1.0,
           "weight_pct": 10.0, "holding_days": 2, "stop_loss": None}
    data = {"portfolio": {"target": [], "transactions": [], "positions": [pos],
                          "total_equity": 10000.0, "open_positions": 1}}
    r = _run(data)
    html = r["positions"] or ""
    assert "无有效止损：盘中止损不会保护这笔持仓" in html, html
    summary = r["summary"] or ""
    assert "无止损持仓" in summary and "1 只" in summary, summary


def test_stopped_row_labels_profit_above_breakeven():
    """止损机制离场但盈利 → 标注「保本以上离场」，避免误读为亏损止损。"""
    data = {"portfolio": {"target": [], "positions": [], "transactions": [
        {"date": "2026-10-14", "ticker": "ISRG", "action": "SELL", "shares": 24,
         "price": 414.81, "amount": 9955.44, "realized_pnl": 233.76,
         "reason": "Review exit: Stop_Loss_Hit", "entry_price": 405.07},
        {"date": "2026-10-13", "ticker": "ANET", "action": "SELL", "shares": 47,
         "price": 204.98, "amount": 9634.06, "realized_pnl": -297.04,
         "reason": "Review exit: Stop_Loss_Hit", "entry_price": 211.30},
    ]}}
    r = _run(data)
    stopped = r["stopped"] or ""
    assert "结果: 保本以上离场" in stopped, stopped
    assert "结果: 亏损离场" in stopped, stopped


# ---------------------------------------------------------------- 超跌观察推荐
def test_oversold_hidden_when_key_missing():
    """oversold 键缺失（文件不存在）→ 整块隐藏。"""
    r = _run({"portfolio": {"target": [], "transactions": [], "positions": []}})
    assert r["oversoldHidden"] is True, r


def test_oversold_empty_state():
    """文件存在但 candidates 为空 → 显示空态 + 备注，不隐藏。"""
    r = _run({"portfolio": {"target": [], "transactions": [], "positions": []},
              "oversold": {"schema": 1, "asof": "2026-10-24", "source": "GPT 研究",
                           "note": "本周暂无候选", "count": 0, "candidates": []}})
    assert r["oversoldHidden"] is False, r
    assert "暂无超跌候选" in (r["oversold"] or ""), r
    assert "本周暂无候选" in (r["oversold"] or ""), r
    assert "GPT 研究" in (r["oversoldSub"] or ""), r
    assert "非生产信号" in (r["oversoldSub"] or ""), r


def test_oversold_renders_candidate_fields():
    cand = {"ticker": "XYZ", "name": "XYZ Inc", "score": 82.5, "tag": "超跌反弹",
            "rsi": 22.4, "bias_pct": -14.2, "drawdown_pct": -28.5,
            "ref_price": 95.2, "stop_loss": 88.5,
            "confirm": "RSI 回升过 30 + 放量阳线",
            "invalid": "跌破前低 $88.50",
            "observe_until": "2026-11-05",
            "reason": "板块未同步下跌，个股跌因一次性事件。"}
    r = _run({"portfolio": {"target": [], "transactions": [], "positions": []},
              "oversold": {"schema": 1, "asof": "2026-10-24", "source": "GPT 研究",
                           "count": 1, "candidates": [cand]}})
    html = r["oversold"] or ""
    assert r["oversoldHidden"] is False, r
    for s in ("XYZ", "XYZ Inc", "超跌反弹", "82.5", "22.4", "-14.2%", "-28.5%",
              "$95.20", "$88.50", "确认", "失效", "观察至 2026-11-05", "一次性事件"):
        assert s in html, (s, html)


def test_oversold_missing_optional_fields_no_placeholder_zero():
    """只有 ticker 的候选也要渲染，缺失字段不能出现 0 / NaN。"""
    r = _run({"portfolio": {"target": [], "transactions": [], "positions": []},
              "oversold": {"candidates": [{"ticker": "abc"}]}})
    html = r["oversold"] or ""
    assert "ABC" in html, html
    assert "NaN" not in html and "undefined" not in html, html
    assert "0.00" not in html, html


# ---------------------------------------------------------------- 市场情绪 AI 解读
_MI = {"fear_greed": {"score": 27.1, "rating": "fear", "subindicators": {}},
       "fedwatch": {"meetings": [], "current_target": "3.75%-4.00%"}, "error": None}


def test_market_ai_commentary_rendered():
    data = {"portfolio": {"target": [], "transactions": [], "positions": []},
            "market_indicators": _MI,
            "market_ai": {"generated_at": "2026-10-27T00:00:00Z", "model": "gpt-x",
                          "summary": "整体情绪偏恐慌，但尚未到极端。",
                          "sections": [{"title": "F&G 结构", "text": "六个子项全部处于恐惧区间。"}]}}
    r = _run(data)
    html = r["market"] or ""
    assert "AI 解读" in html, html
    assert "整体情绪偏恐慌" in html, html
    assert "F&amp;G 结构" in html and "六个子项" in html, html
    assert "外部研究生成" in html, html
    assert "gpt-x" in html, html
    assert "AI 解读 pending" not in html, html


def test_market_ai_pending_when_missing():
    data = {"portfolio": {"target": [], "transactions": [], "positions": []},
            "market_indicators": _MI}
    r = _run(data)
    html = r["market"] or ""
    assert "AI 解读 pending" in html, html
    assert "market_ai_commentary.json" in html, html


def test_detail_review_shows_take_profit_row():
    """个股详情 Review 复盘必须含「止盈价」，且复用 takeProfitInfo（与持仓卡片同口径）。"""
    src = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    assert "mx('止盈价'" in src, "个股详情缺止盈价"
    assert "takeProfitInfo(numLoose(s.stop), num(s.recPrice), num(s.px))" in src, \
        "个股详情未复用 takeProfitInfo"


# ---------------------------------------------------------------- 目标持仓：计划 vs 实际
def test_target_plan_vs_actual_partial():
    target = {"ticker": "AMT", "action": "BUY", "target_shares": 66,
              "ref_price": 188.97, "stop_loss": "$177.22", "stop_loss_price": 177.22,
              "scan_date": "2026-10-26", "ai_reason": "盘前回调",
              "actual_shares": 53, "actual_entry_price": 188.28,
              "actual_entry_date": "2026-10-26", "actual_stop_loss_price": 176.78,
              "shares_delta": 13, "entry_price_diff_pct": -0.37,
              "fill_status": "partial"}
    r = _run({"portfolio": {"target": [target], "transactions": [], "positions": []}})
    html = r["target"] or ""
    assert "部分建仓" in html, html
    assert "实际 53 股" in html, html
    assert "@ $188.28（2026-10-26）" in html, html
    assert "差 +13 股" in html, html
    assert "参考价差 -0.37%" in html, html
    assert "止损 计划 $177.22 / 实际 $176.78" in html, html


def test_target_plan_vs_actual_pending():
    target = {"ticker": "XYZ", "action": "BUY", "target_shares": 10,
              "ref_price": 50.0, "stop_loss_price": 45.0, "scan_date": "2026-10-26",
              "actual_shares": 0, "actual_entry_price": None, "actual_entry_date": None,
              "actual_stop_loss_price": None, "shares_delta": 10,
              "entry_price_diff_pct": None, "fill_status": "pending"}
    r = _run({"portfolio": {"target": [target], "transactions": [], "positions": []}})
    html = r["target"] or ""
    assert "待建仓" in html, html
    assert "实际 0 股" in html, html
    assert "差 +10 股" in html, html


# ---------------------------------------------------------------- 宏观：数据期展示
def _macro(econ):
    return {"generated_at": "2026-10-26T13:02:45Z", "economic": econ, "speakers": []}


def test_macro_monthly_date_is_period_not_day():
    """2026-09-01 是「9 月数据期」，不是 9 月 1 日抓的数据；前端要显示成 2026年9月。"""
    r = _run({"portfolio": {"target": [], "transactions": [], "positions": []},
              "macro": _macro([
                  {"indicator": "CPI", "value": "4.00%", "date": "2026-09-01",
                   "source": "BLS API", "sentiment": "bearish", "rationale": "x"},
                  {"indicator": "核心PCE", "value": "3.00%", "date": "August 2026",
                   "source": "BEA 官方网页", "sentiment": "bearish", "rationale": "x"},
                  {"indicator": "10Y国债", "value": "4.99%", "date": "2026-10-26",
                   "source": "Yahoo Finance", "sentiment": "neutral", "rationale": "x"},
              ])})
    html = r["macro"] or ""
    assert "数据期 2026年9月" in html, html
    assert "2026-09-01" not in html, html          # 不再暴露"9月1日"这种错觉
    assert "数据期 2026年8月" in html, html
    assert "10-26" in html, html
    assert "月度" in html, html
    assert "滞后" not in html, html                # 9 月数据在 10 月底不算滞后


def test_macro_stale_period_flagged():
    r = _run({"portfolio": {"target": [], "transactions": [], "positions": []},
              "macro": _macro([
                  {"indicator": "CPI", "value": "4.00%", "date": "2026-06-01",
                   "source": "BLS API", "sentiment": "bearish", "rationale": "x"},
              ])})
    html = r["macro"] or ""
    assert "数据期 2026年6月" in html, html
    assert "滞后" in html, html
