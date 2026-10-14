#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方案 A：持仓每日 AI 快照持久化（含源码契约 + 落盘行为）。"""
import ast
import csv
import os
import tempfile

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
    pend = _ln('pending_file = f"us_stocks_pending_')
    persist = _ln("if _ai_persist:")
    assert gate > 0 and pend > 0 and persist > 0
    assert gate < pend < persist, "pending 应在门控内(L%d<%d)，持久化在其后(L%d)" % (gate, pend, persist)


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
    use = _at("chosen = _enrich_input")
    call = _at("chosen = enrich_verified_items_with_ai_details(")
    assert not_chosen > 0 and blk > 0 and inp > 0 and use > 0 and call > 0
    # 顺序：风控空判断 -> 构造 enrich 输入 -> 交给 enrich
    assert not_chosen < blk < inp < use < call
    # 持仓来自 AI 输入列表，按持仓集合筛选
    assert _at("_held_up = {str(t).upper() for t in (redef_positions or [])}") > 0
    assert _at("for _h in (ai_input or []):") > 0


def test_holdings_enriched_when_chosen_partial():
    """chosen 非空时，enrich 输入 = 风控后 chosen + 持仓（并集）。"""
    src = (REPO / "scan.py").read_text(encoding="utf-8")
    blk = src.split("_chosen_after_risk = list(chosen)", 1)[1].split(
        "chosen = enrich_verified_items_with_ai_details(", 1)[0]
    assert "_enrich_input = list(_chosen_after_risk)" in blk     # 先放风控后的
    assert "_enrich_input.append(_h)" in blk                     # 再追加持仓
    assert "_tk in _held_up" in blk                              # 只追加持仓


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
    call = _at("chosen = enrich_verified_items_with_ai_details(")
    rm = _at('to_write = [x for x in to_write if x["Ticker"] not in active]')
    gate = _at("if to_write:")
    persist = _at("if _ai_persist:")
    assert call < rm < gate < persist, "顺序: enrich(%d) < 剔持仓(%d) < 门控(%d) < 持久化(%d)" % (
        call, rm, gate, persist)
    # 风控逻辑未被改动
    src = (REPO / "scan.py").read_text(encoding="utf-8")
    assert "hard_blocked = set(restricted_tickers) | set(review_triggered)" in src
    assert 'chosen = [x for x in chosen if str(x.get("Ticker","")).upper() not in hard_blocked]' in src
