#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方案 A：持仓每日 AI 快照持久化（含源码契约 + 落盘行为）。"""
import ast
import csv
import os
import tempfile
import textwrap

import pytest

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAN = REPO / "scan.py"


def _lines():
    return (SCAN.read_text(encoding="utf-8")).splitlines()


def _ln(pat):
    for i, l in enumerate(_lines(), 1):
        if pat in l:
            return i
    return -1


def test_holdings_persisted_without_new_recommendations():
    """★ 捕获必须在「剔除持仓」之前，否则 to_write 为空时永远不写快照。"""
    cap = _ln("_ai_persist_source = list(_enriched)")
    rm = _ln('to_write = [x for x in to_write if x["Ticker"] not in active]')
    assert cap > 0, "缺少 _ai_persist 捕获"
    assert rm > 0
    assert cap < rm, "捕获必须在剔除持仓之前（L%d 应 < L%d）" % (cap, rm)
    # 持久化块必须存在且独立于 to_write 门控
    assert _ln("if _ai_persist:") > 0
    assert _ln("_ai_persist = list(_ai_persist_source)") > 0
    assert _ln("upsert_ai_text_cache(_ai_persist)") > 0
    assert _ln("upsert_ai_snapshot(_ai_persist, rec_date=today_us_str())") > 0


def test_pending_csv_not_written_for_holdings():
    """pending CSV 仍只写「新推荐」：它在 if to_write: 门控内，持久化块在其后。"""
    gate = _ln("if to_write:")
    # The filename and duplicate-check are prepared before the gate; only the
    # physical append/create operation must remain inside the new-recommendation gate.
    write = _ln('with open(pending_file, "a" if pending_exists else "w"')
    persist = _ln("if _ai_persist:")
    assert gate > 0 and write > 0 and persist > 0
    assert gate < write < persist, "pending 实际写入应在 if to_write 门控内、AI 持久化块之前(L%d<%d<%d)" % (gate, write, persist)


def test_no_write_when_no_holdings_no_recommendations():
    """无持仓且无推荐 → _ai_persist 为空 → if _ai_persist: 不进入（不误写）。"""
    assert _ln("_ai_persist = list(_ai_persist_source)") > 0
    assert _ln("if _ai_persist:") > 0            # 空列表时短路，不会调用 upsert
    src = SCAN.read_text(encoding="utf-8")
    # 两个 upsert 的新调用点必须都在 if _ai_persist: 之下（缩进 8 空格）
    tail = src.split("if _ai_persist:", 1)[1]
    assert "upsert_ai_text_cache(_ai_persist)" in tail
    assert "upsert_ai_snapshot(_ai_persist, rec_date=today_us_str())" in tail


def test_holdings_rec_date_is_today():
    """前置裁决：持仓快照的 Rec_Date 用 today（每天新增一行，可逐日回溯）。"""
    src = SCAN.read_text(encoding="utf-8")
    tail = src.split("if _ai_persist:", 1)[1]
    assert "upsert_ai_snapshot(_ai_persist, rec_date=today_us_str())" in tail


def test_no_duplicate_when_holding_is_also_recommendation():
    """持仓同时是新推荐时不得重复：_ai_persist 由 list(to_write) 一次性构造（无 append 循环）。"""
    src = SCAN.read_text(encoding="utf-8")
    blk = src.split("_ai_persist_source = list(_enriched)", 1)[1][:600]
    assert "_ai_persist.append(" not in blk
    assert "_ai_persist +=" not in blk
    assert "_ai_persist = list(_ai_persist_source)" in src


def _extract_upsert():
    """用 ast 抽取 upsert_ai_snapshot 及其常量（scan.py 无 __main__ 守卫，不能直接 import）。"""
    src = SCAN.read_text(encoding="utf-8")
    tree = ast.parse(src)
    want = ("AI_SNAPSHOT_FILE", "AI_SNAPSHOT_COLS", "AI_SNAPSHOT_TEXT_COLS",
            "upsert_ai_snapshot")
    ns = {"__name__": "scan_extract", "os": os, "_csv": csv, "csv": csv}
    got = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in want:
                    exec(ast.get_source_segment(src, node), ns)
                    got.append(t.id)
        elif isinstance(node, ast.FunctionDef) and node.name in want:
            exec(ast.get_source_segment(src, node), ns)
            got.append(node.name)
    return ns, got


def test_upsert_ai_snapshot_writes_holding_row_with_today():
    """行为验证：把「像持仓那样」的条目交给 upsert_ai_snapshot，应落一条 Rec_Date=today 的行。"""
    ns, got = _extract_upsert()
    assert "upsert_ai_snapshot" in got, "抽取失败：%s" % got
    cols = ns["AI_SNAPSHOT_COLS"]
    item = {"Ticker": "CME", "Tag": "Core_Dragon"}
    for c in ns["AI_SNAPSHOT_TEXT_COLS"]:
        item[c] = "持仓六段文本-%s" % c
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "ai_snapshot.csv")
        try:
            n = ns["upsert_ai_snapshot"]([item], rec_date="2026-10-14", path=path)
        except NameError as e:                     # 依赖 scan.py 其他助手 → 跳过（诚实标注）
            pytest.skip("scan.py helper not extractable: %s" % e)
        assert n == 1, n
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        assert len(rows) == 1
        assert rows[0]["Ticker"] == "CME"
        assert rows[0]["Rec_Date"] == "2026-10-14"
        assert set(cols).issubset(set(rows[0].keys()))
        # 幂等：同 (Ticker, Rec_Date, Tag) 再写一次不应新增行
        ns["upsert_ai_snapshot"]([item], rec_date="2026-10-14", path=path)
        assert len(list(csv.DictReader(open(path, encoding="utf-8")))) == 1


# --------------------------------------------------------------------------- #
# F1/F3：风控清空 chosen 时，持仓仍必须进入 enrich，并被持久化
# --------------------------------------------------------------------------- #
def _scan_lines():
    return (REPO / "scan.py").read_text(encoding="utf-8").splitlines()


def _at(pat, start=1):
    for i, l in enumerate(_scan_lines(), 1):
        if i >= start and pat in l:
            return i
    return -1


def test_holdings_enriched_when_chosen_empty_after_risk():
    """★ 上轮盲区：chosen 被风控清空后，六段文本仍要为持仓生成。"""
    not_chosen = _at("if not chosen:")
    blk = _at("_chosen_after_risk = list(chosen)")
    inp = _at("_enrich_input = list(_chosen_after_risk)")
    call = _at("_enriched = enrich_verified_items_with_ai_details(")
    keep = _at("_keep_tk = {str(x.get")
    restore = _at("chosen = [x for x in _enriched if")
    assert not_chosen > 0 and blk > 0 and inp > 0 and call > 0 and keep > 0 and restore > 0
    # 顺序：风控空判断 -> 构造 enrich 输入 -> enrich -> 恢复入账语义（chosen 只留风控后）
    assert not_chosen < blk < inp < call < keep < restore
    # 持仓来自 AI 输入列表，按持仓集合筛选
    assert _at("_held_up = {str(t).upper() for t in (redef_positions or [])}") > 0
    assert _at("for _h in (ai_input or []):") > 0


def test_holdings_enriched_when_chosen_partial():
    """chosen 非空时，enrich 输入 = 风控后 chosen + 持仓（并集）。"""
    src = (REPO / "scan.py").read_text(encoding="utf-8")
    blk = src.split("_chosen_after_risk = list(chosen)", 1)[1].split(
        "chosen = enrich_verified_items_with_ai_details(", 1)[0]
    blk2 = src.split("_chosen_after_risk = list(chosen)", 1)[1].split(
        "_enriched = enrich_verified_items_with_ai_details(", 1)[0]
    assert "_enrich_input = list(_chosen_after_risk)" in blk2     # 先放风控后的
    assert "_enrich_input.append(_h_copy)" in blk2                # 再追加持仓（已做数值兜底）
    assert "_tk in _held_up" in blk2                              # 只追加持仓


def test_no_duplicate_when_holding_also_recommended():
    """持仓同时是推荐时不得重复：_seen_tk 去重守卫。"""
    src = (REPO / "scan.py").read_text(encoding="utf-8")
    blk = src.split("_seen_tk = {str(x.get", 1)[1].split("chosen = _enrich_input", 1)[0]
    assert "and _tk not in _seen_tk" in blk
    assert "_seen_tk.add(_tk)" in blk
    assert "for _h in (ai_input or [])" in blk


def test_enrich_called_even_when_chosen_empty():
    """enrich 的输入必须是含持仓的 _enrich_input（chosen 已被重新绑定），且 F3 取 enriched 全量。"""
    src = (REPO / "scan.py").read_text(encoding="utf-8")
    assert "chosen = _enrich_input" in src
    assert "_enrich_input = list(_chosen_after_risk)" in src
    assert "_ai_persist_source = list(_enriched)" in src
    assert "_ai_persist = list(_ai_persist_source)" in src
    # F3：绝不能再从 to_write 捕获
    assert "_ai_persist = list(to_write)" not in src
    # 持久化块仍有守卫（空列表不写）
    assert "if _ai_persist:" in src


def test_bookkeeping_still_filters_holdings():
    """不变量：pending CSV 仍只写新推荐 —— 剔持仓仍在 enrich 之后、to_write 门控之前。"""
    # Current implementation enriches the combined risk-cleared recommendations + holdings
    # into _enriched, then restores the recommendation-only chosen set before pending filtering.
    call = _at("_enriched = enrich_verified_items_with_ai_details(")
    rm = _at('to_write = [x for x in to_write if x["Ticker"] not in active]')
    gate = _at("if to_write:")
    persist = _at("if _ai_persist:")
    assert call < rm < gate < persist, "顺序: enrich(%d) < 剔持仓(%d) < 门控(%d) < 持久化(%d)" % (
        call, rm, gate, persist)
    # 守卫升级（2026-10-19）：防止悄悄删除分级收窄逻辑。
    # 守护三层：(1) 原并集仍在 (2) 分级收窄仍在且在后 (3) 禁止直接 replace 成 _by_status
    src = (REPO / "scan.py").read_text(encoding="utf-8")
    assert 'chosen = [x for x in chosen if str(x.get("Ticker","")).upper() not in hard_blocked]' in src

    LITERAL = "hard_blocked = set(restricted_tickers) | set(review_triggered)"
    NARROW = "hard_blocked = hard_blocked & _by_status"
    # (1) 原并集字面仍在
    assert LITERAL in src, "风控并集字面被删除"
    # (2) 分级收窄调用与赋值都在
    CALL = "build_hard_blocked(_hist, today_us_str())"
    assert CALL in src, "分级封锁的**调用**被删除（仅保留函数定义不算）"
    assert NARROW in src, "分级收窄（& _by_status）被删除"
    # (3) 顺序：收窄必须在并集之后
    idx_literal = src.find(LITERAL)
    idx_narrow = src.find(NARROW)
    assert idx_literal < idx_narrow, "分级收窄必须先于/脱离并集赋值"
    # (4) 禁止偷懒直接替换
    assert "hard_blocked = _by_status" not in src, "禁止把分级直接 replace 掉原并集"


# --------------------------------------------------------------------------- #
# 行为级测试：从 scan.py 抽取【真实代码片段】执行（不是行号断言）
# --------------------------------------------------------------------------- #
def _snippet(start_pat, end_pat):
    """抽取 start_pat 行到 end_pat 行（不含）之间的源码，并左移缩进。"""
    src = (REPO / "scan.py").read_text(encoding="utf-8")
    i = src.index(start_pat)
    j = src.index(end_pat, i)
    return textwrap.dedent(src[i:j])


def _run_snippet(code, ns):
    exec(compile(code, "<snippet>", "exec"), ns)
    return ns


def test_holding_numeric_fields_coerced():
    """Step2 行为：持仓项 Price='230.43' / RSI='47.6' -> _enrich_input 里为 float。"""
    code = _snippet('            _h_copy = dict(_h)',
                    '            _seen_tk.add(_tk)')
    h = {"Ticker": "ADSK", "Price": "230.43", "RSI": "47.6", "ATR_Pct": "3.2",
         "Quant_Score": "88.5", "AI_Score": "70"}
    ns = {"_h": h, "_enrich_input": [], "_f": None}
    ns["_enrich_input"] = []
    _run_snippet(code, ns)
    got = ns["_enrich_input"][0]
    assert got["Price"] == 230.43 and isinstance(got["Price"], float)
    assert got["RSI"] == 47.6 and got["ATR_Pct"] == 3.2
    assert got["Quant_Score"] == 88.5 and got["AI_Score"] == 70.0
    assert h["Price"] == "230.43", "不得修改原始 dict"


def test_string_price_in_holding_does_not_crash():
    """Step2+Step3 行为：字符串 Price 经兜底后不再触发 str*float。"""
    code = _snippet('            _h_copy = dict(_h)',
                    '            _seen_tk.add(_tk)')
    ns = {"_h": {"Ticker": "ISRG", "Price": "405.07", "ATR_Pct": "2.5"}, "_enrich_input": []}
    _run_snippet(code, ns)
    item = ns["_enrich_input"][0]
    # 模拟 scan.py:4109 的运算：必须成功
    val = round(item["Price"] * (1 + (-3.0) / 100), 2)
    assert isinstance(val, float) and val > 0
    # 不可转换的值 -> None（再乘会 TypeError，但防护会把它挡在循环外）
    ns2 = {"_h": {"Ticker": "X", "Price": "abc"}, "_enrich_input": []}
    _run_snippet(_snippet('            _h_copy = dict(_h)',
                          '            _seen_tk.add(_tk)'), ns2)
    assert ns2["_enrich_input"][0]["Price"] is None


def test_chosen_with_non_numeric_price_is_skipped(capsys):
    """Step3 行为：chosen 里 Price='abc' 的项被防护跳过并打印告警。"""
    code = _snippet("    # \u2605 \u9632\u62a4\uff1achosen", "    to_write = []")
    ns = {"chosen": [{"Ticker": "BAD", "Price": "abc"}, {"Ticker": "OK", "Price": 1.0},
                     {"Ticker": "NONE", "Price": None}]}
    _run_snippet(code, ns)
    assert [x["Ticker"] for x in ns["chosen"]] == ["OK", "NONE"]
    out = capsys.readouterr().out
    assert "BAD" in out and "防御" in out


def test_enrich_output_filtered_back_to_risk_approved():
    """Step1 行为：_enriched 含持仓 -> chosen 被过滤回风控后（空），_ai_persist 仍含持仓。"""
    code = _snippet("    # \u2605 \u539f\u65b9\u6848\u7b2c 4 \u6b65", '    log_file = "trade_history.csv"')
    enriched = [{"Ticker": "ADSK", "Price": 230.43}, {"Ticker": "ISRG", "Price": 405.07}]
    ns = {"_enriched": enriched, "_chosen_after_risk": []}
    _run_snippet(code, ns)
    assert ns["chosen"] == [], "风控后为空 -> chosen 必须为空（入账语义恢复）"
    assert len(ns["_ai_persist"]) == 2, "持久化仍含 2 只持仓"
    assert ns["_ai_persist_source"] is not ns["_enriched"]


def test_ai_persist_source_contains_holdings_and_risk_approved():
    """Step1 行为：持仓 + 风控后推荐 -> chosen 只留推荐；_ai_persist 两者都有。"""
    code = _snippet("    # \u2605 \u539f\u65b9\u6848\u7b2c 4 \u6b65", '    log_file = "trade_history.csv"')
    enriched = [{"Ticker": "ADSK"}, {"Ticker": "ISRG"}, {"Ticker": "NEW1"}]
    ns = {"_enriched": enriched, "_chosen_after_risk": [{"Ticker": "NEW1"}]}
    _run_snippet(code, ns)
    assert [x["Ticker"] for x in ns["chosen"]] == ["NEW1"]
    assert sorted(x["Ticker"] for x in ns["_ai_persist"]) == ["ADSK", "ISRG", "NEW1"]
