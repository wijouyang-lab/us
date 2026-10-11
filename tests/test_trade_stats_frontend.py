"""前端"交易观测"板块测试（node 验证真实 app.js 的 renderTradeStats，磁盘 app.js 不变）。

复用 macro / stopped 的 node harness 思路：内存注入 document.querySelector 捕获钩子，
用真实 app.js 代码断言渲染语义，不改动磁盘上的 app.js。

覆盖边界：
  1) trade_stats 缺失 / null → 隐藏整块，不崩
  2) 无交易（全 0）→ 显「暂无交易记录」
  3) 平仓样本 < 10 → 胜率显「样本不足」
  4) 完整统计（closed≥10）→ 频率 / 胜率 % (wins/closed) / 平均盈亏 / 平均持仓 / 累计盈亏
  5) 累计盈亏正负格式化（+$）/ 负值
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
    js = REPO_ROOT / "tests" / "_trade_harness.js"
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
        "  globalThis.__renderTradeStats = renderTradeStats;\n")
    assert "__renderTradeStats" in out, "未能注入 renderTradeStats 暴露钩子"
    return out


def _tail(ts_json):
    return (
        "\nglobalThis.__setData({portfolio:{trade_stats:" + ts_json + "}});\n"
        "globalThis.__renderTradeStats();\n"
        "var els = globalThis.__els || {};\n"
        "console.log(JSON.stringify({\n"
        "  sub: els['#tradeSub'] ? els['#tradeSub'].textContent : null,\n"
        "  body: els['#tradeBody'] ? els['#tradeBody'].innerHTML : null\n"
        "}));\n"
    )


def test_trade_stats_missing_hidden():
    """trade_stats 缺失 / null → 隐藏整块，body 为空，不崩。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)
    r = _run_node(exposed, _tail("null"))
    assert (r["body"] or "") == "", r


def test_trade_stats_no_transactions():
    """无交易（全 0）→ 显「暂无交易记录」。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)
    ts = {"total_buys": 0, "total_sells": 0, "buys_last_7d": 0, "buys_last_30d": 0,
          "sells_last_7d": 0, "sells_last_30d": 0, "avg_holding_days": None,
          "win_rate": None, "wins": 0, "closed_count": 0, "avg_win_pct": None,
          "avg_loss_pct": None, "total_realized_pnl": 0.0}
    r = _run_node(exposed, _tail(json.dumps(ts)))
    body = r["body"] or ""
    assert "暂无交易记录" in body, body


def test_trade_stats_sample_small():
    """平仓样本 < 10 → 胜率显「样本不足」（不显示数字）。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)
    ts = {"total_buys": 8, "total_sells": 5, "buys_last_7d": 2, "buys_last_30d": 6,
          "sells_last_7d": 1, "sells_last_30d": 2, "avg_holding_days": 8.0,
          "win_rate": 60.0, "wins": 3, "closed_count": 5, "avg_win_pct": 4.2,
          "avg_loss_pct": -3.1, "total_realized_pnl": 1240.0}
    r = _run_node(exposed, _tail(json.dumps(ts)))
    body = r["body"] or ""
    assert "样本不足" in body, body
    assert "%" not in body or "样本不足" in body


def test_trade_stats_full_render():
    """完整统计（closed≥10）→ 频率 / 胜率% (wins/closed) / 平均盈亏 / 平均持仓 / 累计盈亏。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)
    ts = {"total_buys": 34, "total_sells": 21, "buys_last_7d": 2, "buys_last_30d": 8,
          "sells_last_7d": 1, "sells_last_30d": 3, "avg_holding_days": 8.5,
          "win_rate": 61.9, "wins": 13, "closed_count": 21, "avg_win_pct": 4.2,
          "avg_loss_pct": -3.1, "total_realized_pnl": 1240.0}
    r = _run_node(exposed, _tail(json.dumps(ts)))
    body = r["body"] or ""
    # 频率
    assert "买 2 · 卖 1" in body, body
    assert "买 8 · 卖 3" in body, body
    assert "买 34 · 卖 21" in body, body
    # 胜率
    assert "62%" in body, body
    assert "(13/21)" in body, body
    # 平均盈/亏
    assert "平均盈利" in body and "+4.2%" in body, body
    assert "平均亏损" in body and "-3.1%" in body, body
    # 平均持仓
    assert "平均持仓" in body and "8.5 天" in body, body
    # 累计盈亏
    assert "累计盈亏" in body and "+$1,240" in body, body


def test_trade_stats_realized_negative():
    """累计盈亏为负 → 显「-$」前缀。"""
    app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    exposed = _expose(app_js)
    ts = {"total_buys": 34, "total_sells": 21, "buys_last_7d": 2, "buys_last_30d": 8,
          "sells_last_7d": 1, "sells_last_30d": 3, "avg_holding_days": 8.5,
          "win_rate": 61.9, "wins": 13, "closed_count": 21, "avg_win_pct": 4.2,
          "avg_loss_pct": -3.1, "total_realized_pnl": -860.0}
    r = _run_node(exposed, _tail(json.dumps(ts)))
    body = r["body"] or ""
    assert "-$860" in body, body
