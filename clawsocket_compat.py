# -*- coding: utf-8 -*-
"""ClawSocket unified model client.

Uses the OpenAI-compatible Chat Completions endpoint for both GPT and Claude
models so the project does not depend on Anthropic SDK parameter compatibility.
"""
import json
import os
import time
import requests


class _TextBlock:
    def __init__(self, text):
        self.text = text


class _Response:
    def __init__(self, text, raw=None):
        self.content = [_TextBlock(text)] if text else []
        self.raw = raw


class _StreamContext:
    def __init__(self, client, kwargs):
        self.client = client
        self.kwargs = kwargs
        self.text_stream = []
        self._text = ""

    def __enter__(self):
        self._text = self.client._complete(**self.kwargs)
        self.text_stream = [self._text] if self._text else []
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Messages:
    def __init__(self, client):
        self.client = client

    def stream(self, **kwargs):
        return _StreamContext(self.client, kwargs)

    def create(self, **kwargs):
        text = self.client._complete(**kwargs)
        return _Response(text)


class ClawSocketClient:
    def __init__(self, api_key=None, base_url=None, timeout=300, retries=3):
        self.api_key = api_key or os.environ.get("CLAWSOCKET_API_KEY")
        self.base_url = (base_url or os.environ.get("CLAWSOCKET_BASE_URL") or "https://api.clawsocket.com").strip().rstrip("/")
        self.timeout = int(timeout)
        self.retries = int(retries)
        self.messages = _Messages(self)

    def _endpoint(self):
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            return base + "/chat/completions"
        return base + "/v1/chat/completions"

    @staticmethod
    def _extract_text(data):
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                    parts.append(str(item.get("text", "")))
            return "".join(parts)
        return str(content or "")

    def _complete(self, model, messages, max_tokens=None, temperature=None, **kwargs):
        if not self.api_key:
            raise RuntimeError("CLAWSOCKET_API_KEY 未设置")

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)

        # 不向 GPT-6 Astra / Claude 传 temperature，避免中转站或上游 SDK
        # 对 reasoning/modern models 报 unexpected keyword/unsupported field。
        # 其它 kwargs 只保留 OpenAI-compatible 安全字段。
        for key in ("top_p", "seed", "stop", "response_format"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                r = requests.post(
                    self._endpoint(),
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                if r.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    time.sleep(2 ** (attempt - 1))
                    continue
                if not r.ok:
                    body = r.text[:1200]
                    raise RuntimeError(f"ClawSocket HTTP {r.status_code}: {body}")
                data = r.json()
                text = self._extract_text(data).strip()
                if not text:
                    raise RuntimeError(f"ClawSocket 返回成功但没有文本内容: {json.dumps(data, ensure_ascii=False)[:1200]}")
                return text
            except Exception as e:
                last_error = e
                if attempt < self.retries:
                    time.sleep(2 ** (attempt - 1))
                else:
                    break
        raise RuntimeError(f"ClawSocket 调用失败（{model}）：{last_error}")
