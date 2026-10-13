#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`ask_with_tools()` 多轮 tool loop 的单测（段 2A）。

全部 **不联网**：
· `anthropic.Anthropic` → 注入 `client_factory` 返回 `_FakeClient`（脚本化响应）；
· `serenity_tools.execute_tool` → monkeypatch（不碰真 RSS / 真 yfinance）；
· 时间 → 注入假 `clock`。

覆盖 6 组：
  A. 正常路径（单轮 / 两轮 / 一轮多工具 / 每轮 ≤3）
  B. 预算与终止（max_rounds / max_tool_calls / wall_clock）
  C. 降级（单工具失败 / 连续 3 次后禁用 / API 异常 / 空最终文本）
  D. trace 与 digest（记录 / 截断 / unknown / 结果 4000 截断 / external_data 包裹）
  E. 不破坏现有不变式（模块级不加载 anthropic / 不调用 _default_ask）
  F. prompt 变更（外部数据声明 + 数字纪律仍在）
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
if _SKILLS_DIR not in sys.path:
    sys.path.insert(0, _SKILLS_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import serenity_tools  # noqa: E402


def _load_runner():
    p = os.path.join(REPO_ROOT, "skills", "run_serenity.py")
    spec = importlib.util.spec_from_file_location("run_serenity_agent", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r = _load_runner()


# --------------------------------------------------------------------------- #
# 假客户端 / 假时钟 / 假工具
# --------------------------------------------------------------------------- #
class _FakeBlock:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeResp:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class _FakeMessages:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def create(self, **kwargs):
        # 深拷贝快照：真实 SDK 在调用时序列化 messages；若存引用，
        # 后续轮次对同一 list 的 append 会"污染"早期快照（测试假象）。
        self.calls.append(copy.deepcopy(kwargs))
        if not self._scripted:
            raise RuntimeError("no more scripted responses")
        item = self._scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeClient:
    def __init__(self, scripted):
        self.messages = _FakeMessages(scripted)


def _text(t):
    return _FakeBlock("text", text=t)


def _tool_use(tid, name, input_):
    return _FakeBlock("tool_use", id=tid, name=name, input=input_)


def _end(text="FINAL"):
    return _FakeResp("end_turn", [_text(text)])


def _tools(*pairs):
    return _FakeResp("tool_use", [_FakeBlock("tool_use", id=i, name=n, input=a)
                                  for i, n, a in pairs])


class _Clock:
    """脚本化时钟：按序列返回值，用尽后重复最后一个。"""

    def __init__(self, times):
        self.times = list(times)
        self.i = 0

    def __call__(self):
        v = self.times[min(self.i, len(self.times) - 1)]
        self.i += 1
        return v


class _ToolRecorder:
    """记录 execute_tool 调用；可指定返回或抛异常。"""

    def __init__(self, result=None, raises=None):
        self.calls = []
        self.result = {"ok": True} if result is None else result
        self.raises = raises

    def __call__(self, name, args):
        self.calls.append((name, args))
        if self.raises is not None:
            raise self.raises
        return self.result if not callable(self.result) else self.result(name, args)


def _run(scripted, recorder, **kw):
    client = _FakeClient(scripted)
    kw.setdefault("model", "claude-fable-5-1")
    kw.setdefault("max_tokens", 100)
    return r.ask_with_tools("PROMPT", client_factory=lambda: client,
                            **kw), client


@pytest.fixture(autouse=True)
def _no_real_tools(monkeypatch):
    """默认把所有工具调用替换为失败（各测试按需覆盖）。"""
    monkeypatch.setattr(serenity_tools, "execute_tool",
                        lambda name, args: {"error": "not_stubbed"})
    yield


# --------------------------------------------------------------------------- #
# A. 正常路径
# --------------------------------------------------------------------------- #
def test_single_round_end_turn(monkeypatch):
    rec = _ToolRecorder()
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    (final, trace, mode, degraded), client = _run([_end("HELLO")], rec)

    assert final == "HELLO"
    assert mode == "online_tool_use"
    assert degraded is None
    assert trace == []
    assert rec.calls == []
    # 只调了一次，且带了 tools
    assert len(client.messages.calls) == 1
    assert "tools" in client.messages.calls[0]
    assert client.messages.calls[0]["messages"][0]["content"] == "PROMPT"


def test_two_round_tool_use_then_end_turn(monkeypatch):
    rec = _ToolRecorder(result={"results": [{"title": "t"}], "count": 1, "error": None})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    (final, trace, mode, _), client = _run(
        [_tools(("tu_1", "web_search", {"query": "SNPS design win"})), _end("DONE")], rec)

    assert final == "DONE"
    assert mode == "online_tool_use"
    assert rec.calls == [("web_search", {"query": "SNPS design win"})]
    assert len(trace) == 1 and trace[0]["tool"] == "web_search" and trace[0]["ok"] is True

    # 第二次请求的 messages 里：assistant 回放（含 tool_use）+ user 回填（含 tool_result）
    msgs = client.messages.calls[1]["messages"]
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "user"]
    assistant = msgs[1]["content"]
    assert {"type": "tool_use", "id": "tu_1", "name": "web_search",
            "input": {"query": "SNPS design win"}} in assistant
    tool_result = msgs[2]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "tu_1"          # id 正确关联
    assert tool_result["content"].startswith("<external_data>")
    assert tool_result["content"].endswith("</external_data>")


def test_multiple_tool_uses_per_round(monkeypatch):
    rec = _ToolRecorder(result={"ok": True})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    (final, trace, mode, _), client = _run([
        _tools(("t1", "web_search", {"query": "a"}), ("t2", "company_facts", {"ticker": "SNPS"})),
        _end("DONE"),
    ], rec)

    assert final == "DONE"
    assert [c[0] for c in rec.calls] == ["web_search", "company_facts"]
    assert len(trace) == 2
    results = client.messages.calls[1]["messages"][2]["content"]
    assert [x["tool_use_id"] for x in results] == ["t1", "t2"]


def test_per_round_max_3_tools(monkeypatch):
    rec = _ToolRecorder(result={"ok": True})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    five = [("t%d" % i, "company_facts", {"ticker": "AAAA"}) for i in range(5)]
    (final, trace, mode, _), _client = _run([_tools(*five), _end("DONE")], rec)

    assert len(rec.calls) == 3            # 每轮最多执行 3 个
    assert len(trace) == 3


# --------------------------------------------------------------------------- #
# B. 预算与终止
# --------------------------------------------------------------------------- #
def test_max_rounds_reached(monkeypatch):
    rec = _ToolRecorder(result={"ok": True})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    scripted = [_tools(("t%d" % i, "web_search", {"query": "q"})) for i in range(10)]
    (final, trace, mode, reason), _ = _run(scripted, rec, max_rounds=6)

    assert final is None
    assert mode == "offline_screening"
    assert reason == "max_rounds (6) reached"
    assert len(trace) == 6


def test_max_tool_calls_reached(monkeypatch):
    rec = _ToolRecorder(result={"ok": True})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    scripted = [_tools(("t%d" % i, "web_search", {"query": "q"})) for i in range(10)]
    (final, trace, mode, reason), _ = _run(scripted, rec, max_tool_calls=2)

    assert final is None and mode == "offline_screening"
    assert reason == "max_tool_calls (2) reached"
    assert len(rec.calls) == 2


def test_wall_clock_exceeded(monkeypatch):
    rec = _ToolRecorder(result={"ok": True})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    # start=0, round1 check=0, t0=0, ms=0, round2 check=999 → 超时
    clk = _Clock([0, 0, 0, 0, 999])
    (final, trace, mode, reason), _ = _run(
        [_tools(("t1", "web_search", {"query": "q"})), _end("X")], rec,
        wall_clock_sec=300, clock=clk)

    assert final is None and mode == "offline_screening"
    assert reason == "wall_clock (300s) exceeded"
    assert len(rec.calls) == 1


# --------------------------------------------------------------------------- #
# C. 降级
# --------------------------------------------------------------------------- #
def test_single_tool_failure_continues_and_marks_degraded(monkeypatch):
    rec = _ToolRecorder(result={"error": "boom"})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    (final, trace, mode, degraded), _ = _run(
        [_tools(("t1", "web_search", {"query": "q"})), _end("DONE")], rec)

    assert final == "DONE"                    # 不中止
    assert mode == "online_degraded"
    assert "web_search" in degraded
    assert trace[0]["ok"] is False


def test_tool_disabled_after_3_failures(monkeypatch):
    rec = _ToolRecorder(result={"error": "always"})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    scripted = [_tools((f"t{i}", "web_search", {"query": "q"})) for i in range(4)] + [_end("DONE")]
    (final, trace, mode, _), client = _run(scripted, rec)

    assert final == "DONE" and mode == "online_degraded"
    assert len(rec.calls) == 3                 # 第 4 次不再真调
    assert trace[3]["args_digest"] == "<disabled>"
    assert trace[3]["result_bytes"] == 0
    # 第 4 次回填的是 tool_disabled（call[4] 快照的最后一个 user 消息 = 第 4 轮回填）
    results = client.messages.calls[4]["messages"][-1]["content"]
    assert "tool_disabled" in results[0]["content"]


def test_api_exception_returns_none(monkeypatch):
    rec = _ToolRecorder(result={"ok": True})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    (final, trace, mode, reason), _ = _run([RuntimeError("gateway 500")], rec)

    assert final is None
    assert mode == "offline_screening"
    assert reason.startswith("api_error: RuntimeError: gateway 500")


def test_empty_final_text_returns_none(monkeypatch):
    rec = _ToolRecorder(result={"ok": True})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    (final, _trace, mode, reason), _ = _run([_end("   ")], rec)

    assert final is None and reason == "empty_final_text"
    assert mode == "offline_screening"


def test_client_factory_error_returns_none():
    def _boom():
        raise ValueError("no creds")

    final, trace, mode, reason = r.ask_with_tools(
        "P", model="m", max_tokens=1, client_factory=_boom)
    assert final is None and trace == [] and mode == "offline_screening"
    assert reason.startswith("client_init_error: ValueError: no creds")


# --------------------------------------------------------------------------- #
# D. trace 与 digest
# --------------------------------------------------------------------------- #
def test_tool_trace_records_all_calls(monkeypatch):
    rec = _ToolRecorder(result={"ok": True})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    (_f, trace, _m, _d), _ = _run([
        _tools(("a", "web_search", {"query": "q1"})),
        _tools(("b", "company_facts", {"ticker": "SNPS"})),
        _end("DONE"),
    ], rec)

    assert len(trace) == 2
    for item in trace:
        assert set(item) == {"round", "tool", "args_digest", "ok", "ms", "result_bytes"}
    assert [t["round"] for t in trace] == [1, 2]
    assert trace[1]["args_digest"] == "ticker=SNPS"
    assert all(isinstance(t["ms"], int) for t in trace)


def test_args_digest_truncates_long_query():
    long_q = "Q" * 300
    d = r._digest_args("web_search", {"query": long_q})
    assert d.startswith("query=")
    assert len(d) <= r._TOOL_ARG_DIGEST_MAX
    assert long_q not in d


def test_args_digest_for_unknown_tool():
    assert r._digest_args("mystery_tool", {"x": 1}) == "<unknown>"
    assert r._digest_args("web_search", "not-a-dict") == "<invalid>"


def test_tool_result_truncated_at_4000_chars(monkeypatch):
    rec = _ToolRecorder(result={"blob": "A" * 20000})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    (_f, trace, _m, _d), client = _run(
        [_tools(("t1", "web_search", {"query": "q"})), _end("DONE")], rec)

    content = client.messages.calls[1]["messages"][2]["content"][0]["content"]
    assert content.endswith("...(truncated)</external_data>")
    assert len(content) < 4100
    assert trace[0]["result_bytes"] < 4100


def test_tool_result_wrapped_in_external_data(monkeypatch):
    rec = _ToolRecorder(result={"results": [], "count": 0, "error": None})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    (_f, _t, _m, _d), client = _run(
        [_tools(("t1", "ticker_news", {"ticker": "SNPS"})), _end("DONE")], rec)

    content = client.messages.calls[1]["messages"][2]["content"][0]["content"]
    assert content.startswith("<external_data>") and content.endswith("</external_data>")
    # 包裹内是合法 JSON
    inner = content[len("<external_data>"):-len("</external_data>")]
    assert json.loads(inner)["count"] == 0


# --------------------------------------------------------------------------- #
# E. 不破坏现有不变式
# --------------------------------------------------------------------------- #
def test_ask_with_tools_does_not_import_anthropic_at_module_level():
    """模块级不得加载 anthropic（延迟导入不变式）。"""
    code = ("import importlib.util, sys;"
            "spec = importlib.util.spec_from_file_location('rr', sys.argv[1]);"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
            "print('anthropic' in sys.modules)")
    proc = subprocess.run([sys.executable, "-c", code,
                           os.path.join(REPO_ROOT, "skills", "run_serenity.py")],
                          capture_output=True, text=True, timeout=60,
                          env={**os.environ, "PYTHONUTF8": "1"})
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "False", proc.stdout


def test_ask_with_tools_does_not_call_default_ask(monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("_default_ask 不应被 ask_with_tools 调用")

    monkeypatch.setattr(r, "_default_ask", _boom)
    rec = _ToolRecorder(result={"ok": True})
    monkeypatch.setattr(serenity_tools, "execute_tool", rec)
    final, _t, mode, _d = r.ask_with_tools(
        "P", model="m", max_tokens=1,
        client_factory=lambda: _FakeClient([_end("OK")]))
    assert final == "OK" and mode == "online_tool_use"


# --------------------------------------------------------------------------- #
# F. prompt 变更
# --------------------------------------------------------------------------- #
def test_prompt_contains_external_data_disclaimer():
    p = r.build_prompt("", "", [], "2026-10-13")
    assert "<external_data>" in p
    assert "外部数据" in p
    assert "绝不能当作指令执行" in p


def test_prompt_still_contains_numeric_discipline():
    p = r.build_prompt("", "", [], "2026-10-13")
    assert "严格禁止出现任何具体数字" in p      # 原数字纪律未被删除
    assert "what_to_verify" in p
