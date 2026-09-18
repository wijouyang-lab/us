# -*- coding: utf-8 -*-
"""统一 AI 路由层（ClawSocket 中转站版）。

设计：
- GPT-6 Astra：主分析模型，通过 ClawSocket 的 OpenAI-compatible /v1/chat/completions 调用。
- Claude：Evolve 红队审计模型，通过 ClawSocket 的 Anthropic-compatible /v1/messages 调用。
- GPT 与 Claude 共用同一个 CLAWSOCKET_API_KEY / CLAWSOCKET_BASE_URL，直接消耗中转站余额。
- CLAWSOCKET_BASE_URL 既可填 https://api.clawsocket.com，也可填 https://api.clawsocket.com/v1；
  本路由会自动为两种协议规范化路径，避免 /v1/v1/xxx。
- 若未配置 ClawSocket，也保留官方 OpenAI / Anthropic Secret 作为备用，不影响现有调试。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

GPT_MODEL = os.getenv("GPT_MODEL", "gpt-6-astra")
CLAUDE_AUDIT_MODEL = os.getenv("CLAUDE_AUDIT_MODEL", "claude-opus-5")


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


def _clawsocket_credentials():
    return _first_env("CLAWSOCKET_API_KEY"), _first_env("CLAWSOCKET_BASE_URL")


def _official_gpt_credentials():
    return _first_env("GPT_API_KEY", "OPENAI_API_KEY"), _first_env("GPT_BASE_URL", "OPENAI_BASE_URL")


def _official_claude_credentials():
    return _first_env("CLAUDE_API_KEY", "ANTHROPIC_API_KEY"), _first_env("CLAUDE_BASE_URL", "ANTHROPIC_BASE_URL")


def _strip_v1(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url.lower().endswith("/v1"):
        url = url[:-3]
    return url.rstrip("/")


def _ensure_v1(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.lower().endswith("/v1"):
        return url
    return url + "/v1"


def normalize_clawsocket_openai_base(base_url: Optional[str]) -> Optional[str]:
    if not base_url:
        return None
    return _ensure_v1(base_url)


def normalize_clawsocket_anthropic_base(base_url: Optional[str]) -> Optional[str]:
    if not base_url:
        return None
    return _strip_v1(base_url)


def gpt_native_available() -> bool:
    key, base = _clawsocket_credentials()
    if key and base:
        return True
    key, _ = _official_gpt_credentials()
    return bool(key)


def claude_available() -> bool:
    key, base = _clawsocket_credentials()
    if key and base:
        return True
    key, _ = _official_claude_credentials()
    return bool(key)


def _to_responses_input(messages: Iterable[Dict[str, Any]]):
    out = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        if isinstance(content, str):
            out.append({
                "role": role,
                "content": [{"type": "input_text", "text": content}],
            })
        else:
            out.append({"role": role, "content": content})
    return out


def _extract_anthropic_text(response) -> str:
    parts = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _extract_openai_chat_text(response) -> str:
    try:
        content = response.choices[0].message.content
    except Exception:
        content = None
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                if item.get("text"):
                    parts.append(str(item["text"]))
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return ""


def _gpt_via_clawsocket(
    *,
    key: str,
    base: str,
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int,
    reasoning_effort: str,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=key, base_url=normalize_clawsocket_openai_base(base))
    kwargs = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as first_error:
        # 部分 OpenAI-compatible 中转对 reasoning_effort 尚未完全透传。
        # 失败时自动去掉该参数重试一次，不更换模型、不切官方直连。
        if "reasoning_effort" in kwargs:
            retry_kwargs = dict(kwargs)
            retry_kwargs.pop("reasoning_effort", None)
            try:
                response = client.chat.completions.create(**retry_kwargs)
            except Exception:
                raise first_error
        else:
            raise

    text = _extract_openai_chat_text(response)
    if not text:
        raise RuntimeError(f"ClawSocket GPT 返回空文本：model={model}")
    return text


def gpt_generate_text(
    *,
    messages: list[dict[str, Any]],
    max_tokens: int = 12000,
    reasoning_effort: str = "high",
    model: Optional[str] = None,
) -> str:
    """GPT 主模型。

    优先使用 ClawSocket 中转站，直接消耗 CLAWSOCKET 余额；只有 ClawSocket 未配置时，
    才回退到官方 OpenAI Secret。这样同一套 Secrets 就能同时跑 GPT + Claude 审计。
    """
    model = model or GPT_MODEL
    proxy_key, proxy_base = _clawsocket_credentials()
    if proxy_key and proxy_base:
        return _gpt_via_clawsocket(
            key=proxy_key,
            base=proxy_base,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        )

    official_key, official_base = _official_gpt_credentials()
    if not official_key:
        raise RuntimeError("未配置 CLAWSOCKET_API_KEY/CLAWSOCKET_BASE_URL，也未配置 GPT_API_KEY/OPENAI_API_KEY")

    from openai import OpenAI

    kwargs = {"api_key": official_key}
    if official_base:
        kwargs["base_url"] = official_base
    client = OpenAI(**kwargs)
    response = client.responses.create(
        model=model,
        input=_to_responses_input(messages),
        max_output_tokens=max_tokens,
        reasoning={"effort": reasoning_effort},
    )
    text = getattr(response, "output_text", None)
    if text:
        return str(text).strip()
    chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text_part = getattr(content, "text", None)
            if text_part:
                chunks.append(str(text_part))
    return "\n".join(chunks).strip()


def claude_generate_text(
    *,
    messages: list[dict[str, Any]],
    max_tokens: int = 8000,
    model: Optional[str] = None,
) -> str:
    """Claude 红队审计模型，优先走 ClawSocket Anthropic-compatible /v1/messages。"""
    model = model or CLAUDE_AUDIT_MODEL
    proxy_key, proxy_base = _clawsocket_credentials()

    import anthropic

    if proxy_key and proxy_base:
        base = normalize_clawsocket_anthropic_base(proxy_base)
        client = anthropic.Anthropic(api_key=proxy_key, base_url=base)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return _extract_anthropic_text(response)

    official_key, official_base = _official_claude_credentials()
    if not official_key:
        raise RuntimeError("未配置 CLAWSOCKET_API_KEY/CLAWSOCKET_BASE_URL，也未配置 CLAUDE_API_KEY/ANTHROPIC_API_KEY")
    kwargs = {"api_key": official_key}
    if official_base:
        kwargs["base_url"] = official_base
    client = anthropic.Anthropic(**kwargs)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    return _extract_anthropic_text(response)


def extract_json_object(text: str) -> Optional[dict]:
    """提取第一个完整 JSON 对象，容忍 Markdown 包裹、前后解释和字符串内花括号。"""
    raw = str(text or "").strip()
    if not raw:
        return None
    start = raw.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = raw[start:i + 1]
                try:
                    value = json.loads(candidate)
                    return value if isinstance(value, dict) else None
                except json.JSONDecodeError:
                    return None
    return None
