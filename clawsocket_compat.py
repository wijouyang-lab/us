# -*- coding: utf-8 -*-
"""ClawSocket compatibility client with model discovery and safe fallback.

2026-09-18 fix: OpenAI-compatible POST requests also send x-openclaw-model
so gateways that route the backend model from headers do not lose the model
field even when an intermediate proxy rewrites the request body.
"""

CLAWSOCKET_COMPAT_VERSION = "2026.09.18-post-model-route-v15.1"
import json
import os
import time
from typing import Any, Dict, List
import requests

class _TextBlock:
    def __init__(self, text: str): self.text = text

class _Response:
    def __init__(self, text: str, raw: Any = None):
        self.content = [_TextBlock(text)] if text else []
        self.output_text = text or ""
        self.raw = raw

class _StreamContext:
    def __init__(self, client, kwargs):
        self.client = client; self.kwargs = kwargs; self.text_stream = []
    def __enter__(self):
        response = self.client._request(**self.kwargs)
        text = self.client._extract_text(response)
        self.text_stream = [text] if text else []
        return self
    def __exit__(self, exc_type, exc, tb): return False

class _Messages:
    def __init__(self, client): self.client = client
    def stream(self, **kwargs): return _StreamContext(self.client, kwargs)
    def create(self, **kwargs):
        response = self.client._request(**kwargs)
        return _Response(self.client._extract_text(response), raw=response)

class ClawSocketClient:
    def __init__(self, api_key=None, base_url=None, timeout=300, retries=2):
        self.api_key = api_key or os.environ.get("CLAWSOCKET_API_KEY")
        self.base_url = (base_url or os.environ.get("CLAWSOCKET_BASE_URL") or "https://api.clawsocket.com").strip().rstrip("/")
        self.timeout = int(timeout); self.retries = int(retries); self.messages = _Messages(self)
        self._models_loaded = False; self._available_models: List[str] = []
        self.last_requested_model = ""; self.last_model_used = ""; self.last_protocol = ""; self.last_model_fallback = False

    def _root(self) -> str:
        base = self.base_url.rstrip("/")
        for suffix in ("/v1/chat/completions", "/v1/responses", "/v1/messages", "/v1"):
            if base.lower().endswith(suffix): return base[:-len(suffix)]
        return base
    def _url_v1(self, path: str) -> str: return f"{self._root()}/v1/{path.lstrip('/') }"

    @staticmethod
    def _clean_model_id(model: str) -> str:
        m = str(model or "").strip()
        for prefix in ("ClawSocketapi-openai/", "ClawSocketapi-claude/", "ClawSocketapi-gemini/", "openai/", "anthropic/"):
            if m.startswith(prefix): return m[len(prefix):]
        return m

    @property
    def available_models(self) -> List[str]:
        if not self._models_loaded: self._load_models()
        return list(self._available_models)

    def _load_models(self) -> List[str]:
        if self._models_loaded: return list(self._available_models)
        self._models_loaded = True
        if not self.api_key: return []
        try:
            response = requests.get(self._url_v1("models"), headers=self._headers_openai(), timeout=min(self.timeout, 30))
            if not response.ok: return []
            data = response.json()
            rows = data.get("data") if isinstance(data, dict) else None
            if not isinstance(rows, list): rows = data.get("models") if isinstance(data, dict) else None
            ids = []
            for row in rows or []:
                if isinstance(row, str): ids.append(row)
                elif isinstance(row, dict):
                    mid = row.get("id") or row.get("name")
                    if mid: ids.append(str(mid))
            self._available_models = sorted(set(ids))
        except Exception:
            self._available_models = []
        return list(self._available_models)

    def describe_model(self, requested: str) -> Dict[str, Any]:
        requested = self._clean_model_id(requested); available = self.available_models
        lower_map = {m.lower(): m for m in available}; ci_match = lower_map.get(requested.lower())
        return {"requested": requested, "exact_available": requested in available or bool(ci_match), "matched": requested if requested in available else ci_match, "available_count": len(available), "available_preview": available[:40]}

    def _fallback_candidates(self, requested: str) -> List[str]:
        env_key = "CLAUDE_FALLBACK_MODEL" if requested.lower().startswith("claude") else "GPT_FALLBACK_MODEL"
        configured = self._clean_model_id(os.environ.get(env_key, ""))
        defaults = ["claude-opus-4-6", "claude-sonnet-4-5-20250929"] if requested.lower().startswith("claude") else ["gpt-6-astra", "gpt-5.4", "gpt-5.3-codex", "gpt-5.2"]
        return list(dict.fromkeys(([configured] if configured else []) + defaults))

    def _resolve_model(self, requested: str) -> str:
        requested = self._clean_model_id(requested); self.last_requested_model = requested; self.last_model_fallback = False
        available = self.available_models
        if not available: return requested
        lower_map = {m.lower(): m for m in available}
        if requested in available: return requested
        if requested.lower() in lower_map: return lower_map[requested.lower()]
        auto = str(os.environ.get("CLAWSOCKET_AUTO_FALLBACK", "1")).lower().strip()
        if auto not in {"1", "true", "yes", "on"}: return requested
        for candidate in self._fallback_candidates(requested):
            match = candidate if candidate in available else lower_map.get(candidate.lower())
            if match:
                self.last_model_fallback = True
                print(f"⚠️ [ClawSocket] 请求模型 {requested} 未出现在 /v1/models；自动切换到可用模型 {match}")
                return match
        return requested

    def preflight(self, requested: str) -> Dict[str, Any]:
        info = self.describe_model(requested)
        print(f"🔎 [ClawSocket预检] requested={info['requested']} available={info['available_count']} exact={info['exact_available']}")
        if info["available_preview"]: print("   可用模型(前40): " + ", ".join(info["available_preview"]))
        if not info["exact_available"]:
            resolved = self._resolve_model(requested)
            if resolved != info["requested"]: print(f"   ✅ 本次业务将使用: {resolved}")
            else: print("   ⚠️ 未发现可验证的匹配模型，将继续尝试并保留原始模型名。")
        return info

    @staticmethod
    def _message_text(content: Any) -> str:
        if isinstance(content, str): return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str): parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if text is None: text = item.get("input_text")
                    if text is not None: parts.append(str(text))
            return "".join(parts)
        return str(content or "")

    @classmethod
    def _messages_to_anthropic(cls, messages):
        system_parts=[]; out=[]
        for msg in messages or []:
            role=str(msg.get("role","user")); content=cls._message_text(msg.get("content",""))
            if role=="system": system_parts.append(content); continue
            if role not in {"user","assistant"}: role="user"
            out.append({"role":role,"content":content})
        return "\n\n".join(x for x in system_parts if x), out

    @classmethod
    def _messages_to_responses(cls, messages):
        out=[]
        for msg in messages or []:
            role=str(msg.get("role","user")); text=cls._message_text(msg.get("content",""))
            if role=="system": role="developer"
            elif role not in {"user","assistant","developer"}: role="user"
            out.append({"role":role,"content":[{"type":"input_text","text":text}]})
        return out

    @staticmethod
    def _extract_responses_text(data: dict) -> str:
        if isinstance(data.get("output_text"), str): return data["output_text"]
        parts=[]
        for item in data.get("output") or []:
            if not isinstance(item,dict): continue
            for content in item.get("content") or []:
                if isinstance(content,dict) and content.get("type") in {"output_text","text"}: parts.append(str(content.get("text","")))
        return "".join(parts)
    @staticmethod
    def _extract_chat_text(data: dict) -> str:
        choices=data.get("choices") or []
        if not choices: return ""
        message=choices[0].get("message") or {}; return ClawSocketClient._message_text(message.get("content",""))
    @staticmethod
    def _extract_anthropic_text(data: dict) -> str:
        return "".join(str(item.get("text","")) for item in (data.get("content") or []) if isinstance(item,dict) and item.get("type")=="text")
    def _extract_text(self, data: dict) -> str:
        if not isinstance(data,dict): return ""
        return (self._extract_responses_text(data) or self._extract_anthropic_text(data) or self._extract_chat_text(data)).strip()

    def _headers_openai(self, model=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if model:
            # OpenClaw-compatible gateways may use this header to select the
            # provider/model behind the selected agent. Keep JSON `model` too.
            headers["x-openclaw-model"] = str(model)
        if str(os.environ.get("CLAWSOCKET_DEBUG", "0")).lower() in {"1", "true", "yes", "on"}:
            print(f"🔧 [ClawSocket POST] model={model or '<none>'} x-openclaw-model={model or '<none>'}")
        return headers
    def _headers_anthropic(self): return {"Authorization":f"Bearer {self.api_key}","x-api-key":self.api_key,"anthropic-version":os.environ.get("CLAWSOCKET_ANTHROPIC_VERSION","2023-06-01"),"Content-Type":"application/json","Accept":"application/json"}

    @staticmethod
    def _looks_like_model_route_error(error: Exception) -> bool:
        text = str(error or "").lower()
        markers = (
            "request is missing a model",
            "missing a model",
            "model is required",
            "model parameter is required",
            "model not found",
            "unknown model",
            "invalid model",
        )
        return any(marker in text for marker in markers)

    def _runtime_fallback_candidates(self, requested: str) -> List[str]:
        """
        /v1/models 能看到某模型，不代表真实 POST 路由一定已经可用。
        当网关在 POST 阶段返回 model 路由错误时，从实际公布的模型中选择运行时备用模型。
        """
        if requested.lower().startswith("claude"):
            return []
        if str(os.environ.get("CLAWSOCKET_RUNTIME_FALLBACK", "1")).lower().strip() not in {"1", "true", "yes", "on"}:
            return []

        preferred = []
        configured = self._clean_model_id(os.environ.get("GPT_RUNTIME_FALLBACK_MODEL", ""))
        if configured:
            preferred.append(configured)
        # 这些只是优先级，不代表一定存在；最终仍以 /v1/models 为准。
        preferred.extend([
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
            "gpt-5.5",
            "gpt-5.4",
            "gpt-5",
            "gpt-4o-mini",
        ])
        available = self.available_models
        lower_map = {str(m).lower(): str(m) for m in available}
        out = []
        for candidate in preferred:
            match = candidate if candidate in available else lower_map.get(candidate.lower())
            if match and match.lower() != requested.lower() and match not in out:
                out.append(match)
        return out
    @staticmethod
    def _safe_error_body(response):
        try: return response.text[:1800]
        except Exception: return "<无法读取错误正文>"

    def _post(self, url, headers, payload):
        last_error=None
        for attempt in range(1,self.retries+1):
            try:
                response=requests.post(url,headers=headers,json=payload,timeout=self.timeout)
                if response.status_code in {429,500,502,503,504} and attempt<self.retries:
                    time.sleep(2**(attempt-1)); continue
                if not response.ok: raise RuntimeError(f"HTTP {response.status_code}: {self._safe_error_body(response)}")
                return response.json()
            except Exception as exc:
                last_error=exc
                if attempt<self.retries and not str(exc).startswith("HTTP 4"): time.sleep(2**(attempt-1))
                else: break
        raise RuntimeError(str(last_error))

    def _request_responses(self, model, messages, max_tokens, reasoning_effort=None, extra=None):
        payload={"model":model,"input":self._messages_to_responses(messages)}
        if max_tokens is not None: payload["max_output_tokens"]=int(max_tokens)
        effort=reasoning_effort or os.environ.get("GPT_REASONING_EFFORT","")
        if effort: payload["reasoning"]={"effort":effort}
        return self._post(self._url_v1("responses"),self._headers_openai(model),payload)

    def _request_chat(self, model, messages, max_tokens, extra=None):
        payload={"model":model,"messages":messages}
        if max_tokens is not None: payload["max_tokens"]=int(max_tokens)
        return self._post(self._url_v1("chat/completions"),self._headers_openai(model),payload)

    def _request_anthropic(self, model, messages, max_tokens, extra=None):
        system,clean_messages=self._messages_to_anthropic(messages)
        payload={"model":model,"max_tokens":int(max_tokens or 4096),"messages":clean_messages}
        if system: payload["system"]=system
        return self._post(self._url_v1("messages"),self._headers_anthropic(),payload)

    def _protocol_plan(self, model: str):
        override=str(os.environ.get("CLAWSOCKET_PROTOCOL","auto")).lower().strip()
        if override in {"responses","chat","anthropic"}: return [override]
        if str(model).lower().startswith("claude"): return ["anthropic","chat"]
        # ClawSocket 的公开 OpenAI-compatible 接入以 /v1/chat/completions 为通用入口；
        # Responses 保留为第二协议备用。
        return ["chat","responses"]

    def _request(self, model, messages, max_tokens=None, temperature=None, reasoning_effort=None, **kwargs):
        if not self.api_key: raise RuntimeError("CLAWSOCKET_API_KEY 未设置")
        requested=self._clean_model_id(model)
        if not requested: raise RuntimeError("模型名为空：请设置 GPT_MODEL / CLAUDE_AUDIT_MODEL")
        resolved=self._resolve_model(requested)
        self.last_model_used=resolved
        all_errors=[]

        # 第一轮：严格尝试用户要求的模型。
        plan=self._protocol_plan(resolved)
        for protocol in plan:
            try:
                if protocol=="responses": data=self._request_responses(resolved,messages,max_tokens,reasoning_effort,kwargs)
                elif protocol=="anthropic": data=self._request_anthropic(resolved,messages,max_tokens,kwargs)
                else: data=self._request_chat(resolved,messages,max_tokens,kwargs)
                text=self._extract_text(data)
                if not text: raise RuntimeError(f"{protocol} 请求成功但没有文本内容：{json.dumps(data,ensure_ascii=False)[:1600]}")
                self.last_protocol=protocol; return data
            except Exception as exc:
                all_errors.append(f"{resolved}/{protocol}: {exc}")

        # 第二轮：如果目录可见模型在真实 POST 路由中被判定为“缺 model/模型不可用”，
        # 把它视为网关目录与实际路由不同步，从实际公布模型中自动选运行时备用模型。
        route_error_seen = any(self._looks_like_model_route_error(RuntimeError(err)) for err in all_errors)
        if route_error_seen:
            for fallback in self._runtime_fallback_candidates(resolved):
                fallback_plan=self._protocol_plan(fallback)
                print(f"⚠️ [ClawSocket] {resolved} 在真实 POST 阶段路由失败；尝试运行时备用模型 {fallback}")
                for protocol in fallback_plan:
                    try:
                        if protocol=="responses": data=self._request_responses(fallback,messages,max_tokens,reasoning_effort,kwargs)
                        elif protocol=="anthropic": data=self._request_anthropic(fallback,messages,max_tokens,kwargs)
                        else: data=self._request_chat(fallback,messages,max_tokens,kwargs)
                        text=self._extract_text(data)
                        if not text: raise RuntimeError(f"{protocol} 请求成功但没有文本内容：{json.dumps(data,ensure_ascii=False)[:1600]}")
                        self.last_model_fallback=True
                        self.last_model_used=fallback
                        self.last_protocol=protocol
                        print(f"✅ [ClawSocket] 运行时备用模型成功：{fallback} ({protocol})")
                        return data
                    except Exception as exc:
                        all_errors.append(f"{fallback}/{protocol}: {exc}")

        available=self.available_models
        availability_note=(f"；/v1/models可见模型前40={available[:40]}" if available else "；/v1/models未返回可用模型列表（接口可能关闭或当前Key无法读取）")
        raise RuntimeError(f"ClawSocket调用失败（requested={requested}, used={self.last_model_used or resolved}）。详细错误: {' | '.join(all_errors)}{availability_note}")
