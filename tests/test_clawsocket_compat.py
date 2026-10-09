"""clawsocket_compat.py 单元测试（全部 mock，绝不调用真实 ClawSocket API）。

背景（bug 修复回归测试）：
  _request() 在「所有 model×protocol 尝试都失败」的分支里调用了
  _looks_like_model_route_error() 与 _runtime_fallback_candidates()，但这两个方法
  此前从未定义。因为 any() 对空 all_errors 短路，只要主模型一直可用就永不暴露；
  一旦主模型路由失败（例如换模型时），会抛 AttributeError 而不是优雅降级。

覆盖：
  1. _looks_like_model_route_error：只认模型路由类错误，不认 429/5xx/超时
  2. _runtime_fallback_candidates：返回 claude-fable-5-1，排除 requested 自身，支持 env 覆盖
  3. 主模型路由失败 + 备用可用 → 优雅降级成功（不是 AttributeError）
  4. 主模型路由失败 + 备用也失败 → 抛 RuntimeError（不是 AttributeError）
"""
import os

import pytest

import clawsocket_compat as cs


def _client():
    """构造一个不触网的 client（_models_loaded=True 避免 /v1/models 请求）。"""
    c = cs.ClawSocketClient(api_key="dummy", base_url="https://example.test")
    c._models_loaded = True
    c._available_models = []
    return c


# ------------------------------------------------------------------ 1. 路由错误判定
def test_route_error_detection():
    c = _client()
    assert c._looks_like_model_route_error(RuntimeError("HTTP 400: Request is missing a model"))
    assert c._looks_like_model_route_error(RuntimeError("unknown model: gpt-6-astra"))
    assert c._looks_like_model_route_error(RuntimeError("model not found"))
    # 非模型路由类：限流 / 网关 5xx / 超时 / 空 —— 不应误判
    assert not c._looks_like_model_route_error(RuntimeError("HTTP 429 rate limited"))
    assert not c._looks_like_model_route_error(RuntimeError("HTTP 502 bad gateway"))
    assert not c._looks_like_model_route_error(RuntimeError("timeout"))
    assert not c._looks_like_model_route_error(None)
    assert not c._looks_like_model_route_error(RuntimeError(""))


# ------------------------------------------------------------------ 2. 备用候选
def test_runtime_fallback_candidates_default():
    c = _client()
    assert c._runtime_fallback_candidates("gpt-6-astra") == ["claude-fable-5-1"]
    # requested 自身不参与自兜底
    assert c._runtime_fallback_candidates("claude-fable-5-1") == []


def test_runtime_fallback_candidates_env_override(monkeypatch):
    monkeypatch.setenv("CLAUDE_RUNTIME_FALLBACK_MODEL", "claude-opus-5")
    c = _client()
    got = c._runtime_fallback_candidates("gpt-6-astra")
    assert got[0] == "claude-opus-5"


# ------------------------------------------------------------------ 3. 优雅降级成功
def test_route_error_degrades_to_runtime_fallback(monkeypatch):
    """主模型全部路由失败，但运行时备用可用 → 应成功返回并标记 fallback（绝不是 AttributeError）。"""
    c = _client()
    monkeypatch.delenv("CLAWSOCKET_LIVE_MODEL", raising=False)
    monkeypatch.delenv("CLAWSOCKET_LIVE_PROTOCOL", raising=False)

    tried = []

    def fake_request_one(model, protocol, messages, max_tokens, reasoning_effort, kwargs):
        tried.append((model, protocol))
        if model == "claude-fable-5-1":
            return {"content": [{"type": "text", "text": "OK"}]}
        raise RuntimeError("HTTP 400: Request is missing a model")

    monkeypatch.setattr(c, "_request_one", fake_request_one)

    data = c._request("gpt-6-astra", [{"role": "user", "content": "hi"}], max_tokens=16)

    assert isinstance(data, dict)
    assert c._extract_text(data) == "OK"
    assert c.last_model_fallback is True
    assert c.last_model_used == "claude-fable-5-1"
    # 确实尝试过主模型的两个变体，再退到备用
    assert any(m == "gpt-6-astra" for m, _ in tried)
    assert any(m == "claude-fable-5-1" for m, _ in tried)


# ------------------------------------------------------------------ 4. 全失败也不是 AttributeError
def test_route_error_all_fail_raises_runtime_error(monkeypatch):
    """主模型与备用都失败 → 抛 RuntimeError（设计中的终态错误），绝不是 AttributeError。"""
    c = _client()
    monkeypatch.delenv("CLAWSOCKET_LIVE_MODEL", raising=False)
    monkeypatch.delenv("CLAWSOCKET_LIVE_PROTOCOL", raising=False)

    tried = []

    def fake_request_one(model, protocol, messages, max_tokens, reasoning_effort, kwargs):
        tried.append((model, protocol))
        raise RuntimeError("HTTP 400: Request is missing a model")

    monkeypatch.setattr(c, "_request_one", fake_request_one)

    with pytest.raises(RuntimeError) as ei:
        c._request("gpt-6-astra", [{"role": "user", "content": "hi"}], max_tokens=16)

    msg = str(ei.value)
    # 核心回归点：修复前这里是 AttributeError
    assert "AttributeError" not in msg
    assert "has no attribute" not in msg
    assert "ClawSocket调用失败" in msg
    # 备用模型确实被尝试过（证明走到了降级分支）
    assert any(m == "claude-fable-5-1" for m, _ in tried)


# ------------------------------------------------------------------ 5. 非路由错误不触发跨模型降级
def test_non_route_error_does_not_use_runtime_fallback(monkeypatch):
    """429 限流属于网关抖动，不是模型路由问题 → 不应尝试 claude 备用。"""
    c = _client()
    monkeypatch.delenv("CLAWSOCKET_LIVE_MODEL", raising=False)
    monkeypatch.delenv("CLAWSOCKET_LIVE_PROTOCOL", raising=False)

    tried = []

    def fake_request_one(model, protocol, messages, max_tokens, reasoning_effort, kwargs):
        tried.append((model, protocol))
        raise RuntimeError("HTTP 429 rate limited")

    monkeypatch.setattr(c, "_request_one", fake_request_one)

    with pytest.raises(RuntimeError):
        c._request("gpt-6-astra", [{"role": "user", "content": "hi"}], max_tokens=16)

    assert not any(m == "claude-fable-5-1" for m, _ in tried)
