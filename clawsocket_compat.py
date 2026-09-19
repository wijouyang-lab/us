# -*- coding: utf-8 -*-
"""ClawSocket compatibility client with model discovery and safe fallback."""
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

    def live_probe(self, requested: str, timeout: int = 25) -> Dict[str, Any]:
        """Perform one tiny real POST so /v1/models catalog != POST routing mismatch is detected early."""
        requested = self._clean_model_id(requested)
        info = self.describe_model(requested)
        variants = self._model_variants(requested)
        # Prefer bare catalog ID, then provider-qualified identity.
        errors = []
        old_timeout = self.timeout
        self.timeout = min(int(timeout), old_timeout)
        try:
            for candidate in variants:
                for protocol in self._protocol_plan(candidate):
                    try:
                        probe_messages = [{"role": "user", "content": "Reply with exactly: OK"}]
                        data = self._request_one(candidate, protocol, probe_messages, 16, None, {})
                        text = self._extract_text(data)
                        if text:
                            self.last_model_used = candidate
                            self.last_protocol = protocol
                            os.environ["CLAWSOCKET_LIVE_MODEL"] = candidate
                            os.environ["CLAWSOCKET_LIVE_PROTOCOL"] = protocol
                            print(f"✅ [ClawSocket实测] model={candidate} protocol={protocol} 可用")
                            return {"ok": True, "model": candidate, "protocol": protocol, "text": text, "errors": errors, "catalog": info}
                    except Exception as exc:
                        errors.append(f"{candidate}/{protocol}: {exc}")
        finally:
            self.timeout = old_timeout
        print("⚠️ [ClawSocket实测] 请求模型没有可用的真实 POST 路由")
        for err in errors[:6]:
            print(f"   - {err}")
        return {"ok": False, "model": "", "protocol": "", "text": "", "errors": errors, "catalog": info}

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
        headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json","Accept":"application/json"}
        if model:
            headers["x-openclaw-model"] = str(model)
        return headers
    def _headers_anthropic(self): return {"Authorization":f"Bearer {self.api_key}","x-api-key":self.api_key,"anthropic-version":os.environ.get("CLAWSOCKET_ANTHROPIC_VERSION","2023-06-01"),"Content-Type":"application/json","Accept":"application/json"}
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
        if str(model).lower().startswith("claude") or str(model).lower().startswith("anthropic/"): return ["anthropic","chat"]
        return ["chat","responses"]

    def _model_variants(self, model: str) -> List[str]:
        """Return model-id variants used by common proxy/provider routers."""
        m = self._clean_model_id(model)
        out = [m]
        low = m.lower()
        # ClawSocket/OpenClaw-style provider-qualified identity.
        if low.startswith("gpt-"):
            out.append("openai/" + m)
        elif low.startswith("claude-"):
            out.append("anthropic/" + m)
        return list(dict.fromkeys(out))

    def _request_one(self, model, protocol, messages, max_tokens, reasoning_effort, kwargs):
        if protocol == "responses":
            return self._request_responses(model, messages, max_tokens, reasoning_effort, kwargs)
        if protocol == "anthropic":
            return self._request_anthropic(model, messages, max_tokens, kwargs)
        return self._request_chat(model, messages, max_tokens, kwargs)

    def _request(self, model, messages, max_tokens=None, temperature=None, reasoning_effort=None, **kwargs):
        if not self.api_key:
            raise RuntimeError("CLAWSOCKET_API_KEY 未设置")
        requested = self._clean_model_id(model)
        if not requested:
            raise RuntimeError("模型名为空：请设置 GPT_MODEL / CLAUDE_AUDIT_MODEL")
        live_model = self._clean_model_id(os.environ.get("CLAWSOCKET_LIVE_MODEL", ""))
        live_protocol = str(os.environ.get("CLAWSOCKET_LIVE_PROTOCOL", "")).lower().strip()
        resolved = live_model or self._resolve_model(requested)
        self.last_model_used = resolved
        all_errors = []

        # 已经在启动阶段做过真实 POST 验证时，优先复用验证成功的路由，避免每个业务函数重复打失败请求。
        if live_model and live_protocol:
            try:
                data = self._request_one(resolved, live_protocol, messages, max_tokens, reasoning_effort, kwargs)
                text = self._extract_text(data)
                if text:
                    self.last_protocol = live_protocol
                    return data
            except Exception as exc:
                all_errors.append(f"live/{resolved}/{live_protocol}: {exc}")
                os.environ.pop("CLAWSOCKET_LIVE_MODEL", None)
                os.environ.pop("CLAWSOCKET_LIVE_PROTOCOL", None)

        # 先用目录返回的原始 ID；如果网关把 provider/model 作为路由键，
        # 再尝试 openai/<id> / anthropic/<id>。/v1/models 的裸 ID 仍然优先。
        model_variants = self._model_variants(resolved)
        plan = self._protocol_plan(resolved)
        for candidate_model in model_variants:
            for protocol in plan:
                try:
                    data = self._request_one(candidate_model, protocol, messages, max_tokens, reasoning_effort, kwargs)
                    text = self._extract_text(data)
                    if not text:
                        raise RuntimeError(
                            f"{protocol} 请求成功但没有文本内容：{json.dumps(data, ensure_ascii=False)[:1600]}"
                        )
                    self.last_protocol = protocol
                    self.last_model_used = candidate_model
                    if candidate_model != resolved:
                        print(f"🔁 [ClawSocket] provider-qualified model 成功：{candidate_model}")
                    return data
                except Exception as exc:
                    all_errors.append(f"{candidate_model}/{protocol}: {exc}")

        # GPT 模型如果真实 POST 阶段失败，尝试明确的 Claude Fable 运行时备用。
        route_error_seen = any(self._looks_like_model_route_error(RuntimeError(err)) for err in all_errors)
        if route_error_seen:
            for fallback in self._runtime_fallback_candidates(resolved):
                fallback_plan = self._protocol_plan(fallback)
                print(f"⚠️ [ClawSocket] {resolved} 在真实 POST 阶段路由失败；尝试运行时备用模型 {fallback}")
                for protocol in fallback_plan:
                    try:
                        data = self._request_one(fallback, protocol, messages, max_tokens, reasoning_effort, kwargs)
                        text = self._extract_text(data)
                        if not text:
                            raise RuntimeError(
                                f"{protocol} 请求成功但没有文本内容：{json.dumps(data, ensure_ascii=False)[:1600]}"
                            )
                        self.last_model_fallback = True
                        self.last_model_used = fallback
                        self.last_protocol = protocol
                        print(f"✅ [ClawSocket] 运行时备用模型成功：{fallback} ({protocol})")
                        return data
                    except Exception as exc:
                        all_errors.append(f"{fallback}/{protocol}: {exc}")

        available = self.available_models
        availability_note = (
            f"；/v1/models可见模型前40={available[:40]}"
            if available else
            "；/v1/models未返回可用模型列表（接口可能关闭或当前Key无法读取）"
        )
        raise RuntimeError(
            f"ClawSocket调用失败（requested={requested}, used={self.last_model_used or resolved}）。"
            f"详细错误: {' | '.join(all_errors)}{availability_note}"
        )
