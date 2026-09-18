# -*- coding: utf-8 -*-
"""ClawSocket dual-protocol compatibility client.

Protocol routing:
- GPT models: OpenAI Responses API (/v1/responses) first, then Chat Completions fallback.
- Claude models: Anthropic Messages API (/v1/messages) first, then Chat Completions fallback.

The business code keeps one tiny interface:
    client.messages.create(...)
    client.messages.stream(...)

The client is deliberately defensive because third-party gateways can expose
more than one compatibility surface and may change supported parameters.
"""
import json
import os
import time
from typing import Any

import requests


class _TextBlock:
    def __init__(self, text: str):
        self.text = text


class _Response:
    def __init__(self, text: str, raw: Any = None):
        self.content = [_TextBlock(text)] if text else []
        self.output_text = text or ""
        self.raw = raw


class _StreamContext:
    """Compatibility stream wrapper.

    ClawSocket is called synchronously here. The existing project expects
    stream.text_stream, so we expose one text chunk after a successful request.
    This keeps the call sites unchanged while using the more reliable protocol
    adapters underneath.
    """

    def __init__(self, client, kwargs):
        self.client = client
        self.kwargs = kwargs
        self.text_stream = []

    def __enter__(self):
        response = self.client._request(**self.kwargs)
        text = self.client._extract_text(response)
        self.text_stream = [text] if text else []
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Messages:
    def __init__(self, client):
        self.client = client

    def stream(self, **kwargs):
        return _StreamContext(self.client, kwargs)

    def create(self, **kwargs):
        response = self.client._request(**kwargs)
        return _Response(self.client._extract_text(response), raw=response)


class ClawSocketClient:
    def __init__(self, api_key=None, base_url=None, timeout=300, retries=2):
        self.api_key = api_key or os.environ.get("CLAWSOCKET_API_KEY")
        self.base_url = (base_url or os.environ.get("CLAWSOCKET_BASE_URL") or "https://api.clawsocket.com").strip().rstrip("/")
        self.timeout = int(timeout)
        self.retries = int(retries)
        self.messages = _Messages(self)

    # -------------------------- URL helpers --------------------------
    def _root(self) -> str:
        base = self.base_url.rstrip("/")
        return base[:-3] if base.endswith("/v1") else base

    def _url_v1(self, path: str) -> str:
        return f"{self._root()}/v1/{path.lstrip('/')}"

    # -------------------------- text helpers --------------------------
    @staticmethod
    def _message_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if text is None:
                        text = item.get("input_text")
                    if text is not None:
                        parts.append(str(text))
            return "".join(parts)
        return str(content or "")

    @classmethod
    def _messages_to_anthropic(cls, messages):
        system_parts = []
        out = []
        for msg in messages or []:
            role = str(msg.get("role", "user"))
            content = cls._message_text(msg.get("content", ""))
            if role == "system":
                system_parts.append(content)
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            out.append({"role": role, "content": content})
        return "\n\n".join(x for x in system_parts if x), out

    @classmethod
    def _messages_to_responses(cls, messages):
        """Convert Chat-style messages into Responses input items."""
        out = []
        for msg in messages or []:
            role = str(msg.get("role", "user"))
            text = cls._message_text(msg.get("content", ""))
            if role == "system":
                role = "developer"
            elif role not in {"user", "assistant", "developer"}:
                role = "user"
            out.append({
                "role": role,
                "content": [{"type": "input_text", "text": text}],
            })
        return out

    @staticmethod
    def _extract_responses_text(data: dict) -> str:
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        parts = []
        for item in data.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                    parts.append(str(content.get("text", "")))
        return "".join(parts)

    @staticmethod
    def _extract_chat_text(data: dict) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return ClawSocketClient._message_text(message.get("content", ""))

    @staticmethod
    def _extract_anthropic_text(data: dict) -> str:
        parts = []
        for item in data.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)

    def _extract_text(self, data: dict) -> str:
        if not isinstance(data, dict):
            return ""
        return (
            self._extract_responses_text(data)
            or self._extract_anthropic_text(data)
            or self._extract_chat_text(data)
        ).strip()

    # -------------------------- request helpers --------------------------
    def _headers_openai(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _headers_anthropic(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key,
            "anthropic-version": os.environ.get("CLAWSOCKET_ANTHROPIC_VERSION", "2023-06-01"),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _safe_error_body(response) -> str:
        try:
            return response.text[:1600]
        except Exception:
            return "<无法读取错误正文>"

    def _post(self, url, headers, payload):
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                # Retry transient gateway errors, not deterministic 4xx request errors.
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self.retries:
                    time.sleep(2 ** (attempt - 1))
                    continue
                if not response.ok:
                    raise RuntimeError(f"HTTP {response.status_code}: {self._safe_error_body(response)}")
                return response.json()
            except Exception as exc:
                last_error = exc
                if attempt < self.retries and not str(exc).startswith("HTTP 4"):
                    time.sleep(2 ** (attempt - 1))
                else:
                    break
        raise RuntimeError(str(last_error))

    def _request_responses(self, model, messages, max_tokens, reasoning_effort=None, extra=None):
        payload = {
            "model": model,
            "input": self._messages_to_responses(messages),
        }
        if max_tokens is not None:
            payload["max_output_tokens"] = int(max_tokens)
        # GPT-6 Astra supports reasoning effort; omit it unless explicitly configured.
        effort = reasoning_effort or os.environ.get("GPT_REASONING_EFFORT", "")
        if effort:
            payload["reasoning"] = {"effort": effort}
        for key in ("store", "service_tier", "metadata"):
            if extra and extra.get(key) is not None:
                payload[key] = extra[key]
        return self._post(self._url_v1("responses"), self._headers_openai(), payload)

    def _request_chat(self, model, messages, max_tokens, extra=None):
        payload = {
            "model": model,
            "messages": messages,
        }
        if max_tokens is not None:
            # Prefer current field; many gateways still accept max_tokens, so keep a fallback.
            payload["max_completion_tokens"] = int(max_tokens)
        for key in ("top_p", "seed", "stop", "response_format", "store", "service_tier"):
            if extra and extra.get(key) is not None:
                payload[key] = extra[key]
        return self._post(self._url_v1("chat/completions"), self._headers_openai(), payload)

    def _request_anthropic(self, model, messages, max_tokens, extra=None):
        system, clean_messages = self._messages_to_anthropic(messages)
        payload = {
            "model": model,
            "max_tokens": int(max_tokens or 4096),
            "messages": clean_messages,
        }
        if system:
            payload["system"] = system
        # Use adaptive thinking only when explicitly requested. This avoids
        # consuming excessive output budget on short red-team checks.
        if extra and extra.get("thinking") is not None:
            payload["thinking"] = extra["thinking"]
        if extra and extra.get("effort") is not None:
            payload["output_config"] = {"effort": extra["effort"]}
        return self._post(self._url_v1("messages"), self._headers_anthropic(), payload)

    def _protocol_plan(self, model: str):
        override = str(os.environ.get("CLAWSOCKET_PROTOCOL", "auto")).lower().strip()
        if override in {"responses", "chat", "anthropic"}:
            return [override]
        if str(model).lower().startswith("claude"):
            return ["anthropic", "chat"]
        return ["responses", "chat"]

    def _request(self, model, messages, max_tokens=None, temperature=None, reasoning_effort=None, **kwargs):
        if not self.api_key:
            raise RuntimeError("CLAWSOCKET_API_KEY 未设置")
        model = str(model or "").strip()
        if not model:
            raise RuntimeError("模型名为空：请设置 GPT_MODEL / CLAUDE_AUDIT_MODEL")

        extra = dict(kwargs)
        plan = self._protocol_plan(model)
        errors = []
        for protocol in plan:
            try:
                if protocol == "responses":
                    data = self._request_responses(model, messages, max_tokens, reasoning_effort, extra)
                elif protocol == "anthropic":
                    data = self._request_anthropic(model, messages, max_tokens, extra)
                else:
                    data = self._request_chat(model, messages, max_tokens, extra)

                text = self._extract_text(data)
                if not text:
                    raise RuntimeError(
                        f"{protocol} 请求成功但没有文本内容：{json.dumps(data, ensure_ascii=False)[:1600]}"
                    )
                return data
            except Exception as exc:
                errors.append(f"{protocol}: {exc}")
                # Try the next compatibility surface. This is especially useful
                # when a gateway exposes Responses for GPT and Anthropic Messages for Claude.
                continue

        hint = (
            f"ClawSocket 调用失败（{model}）。尝试协议: {', '.join(plan)}。"
            f"详细错误: {' | '.join(errors)}"
        )
        raise RuntimeError(hint)
