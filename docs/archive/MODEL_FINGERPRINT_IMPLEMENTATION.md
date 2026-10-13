# ClawSocket 实际模型识别 — 改动实施方案

> **状态：方案已就绪，代码改动待 21:00 scan 跑完后（明天上午）执行。**
> 本文档为"改动方案 + 实施脚本"，当前**不修改任何文件**，不 `push`/`rebase`/`commit`。
> 铁律：今天 21:00 scan 要跑，`clawsocket_compat.py` 被 scan 调用，**现在不能改**。

---

## 0. 只读确认结论（已核实，基于当前 HEAD）

| 检查项 | 结果 |
|---|---|
| 响应解析点 | `_post`（L271-284）是唯一真实 POST 出口；`_extract_text` 只取文本 |
| `model` 字段是否被读 | **零**（全仓 grep 无 `response['model']` / `raw['model']`） |
| `usage` 字段是否被读 | **零**（全仓无 `prompt_tokens` / `completion_tokens` / `.usage` 读取） |
| `raw` 是否暴露给上层 | `create()` 持有但**从不打印**；`stream()`（scan/review 实际用的路径）**不传 raw** |
| 上层能否拿到 model/usage | **不能**；唯一相关引用是 `scan.py:218` 读 `probe.last_model_used`（请求侧 ID，非上游） |

**推论**：真值（上游 `model` / `usage`）只在 `_post` 拿到的 `response.json()` 里，且当前被丢弃。
最佳注入点是 `_post`——它是 `stream` 与 `create` 共同的 POST chokepoint，在此 `print` 一次即可在 CI 日志看到，且不受"stream 不传 raw"影响。

---

## 1. 改动点（逻辑）

在读到上游响应 JSON 后，立即打印一行结构化日志：

```python
# 精确位置：_post 内，拿到 response.json() 之后
_upstream_model = _resp_json.get("model", "unknown")
_usage = _resp_json.get("usage") or {}
print(f"[ClawSocket] upstream_model={_upstream_model} "
      f"prompt_tokens={_usage.get('prompt_tokens', '?')} "
      f"completion_tokens={_usage.get('completion_tokens', '?')} "
      f"requested={self.last_model_used} "
      f"fallback={self.last_model_fallback}")
```

关键字段含义：
- `upstream_model` → 上游**真实服务**的模型（硬证据，若网关回传）。
- `usage.prompt_tokens` → tokenizer 指纹（家族判别辅助）。
- `requested` → 客户端**请求**的模型（`self.last_model_used`，已含 fallback 解析结果）。
- `fallback` → 本次是否发生运行时降级（`self.last_model_fallback`）。

> 注：用户草稿里的 `resolved_model` / `last_model_fallback` 变量名在 `_post` 作用域不存在；
> 改用等价属性 `self.last_model_used`（L338 已被赋为 `resolved`）与 `self.last_model_fallback`（L389）。

---

## 2. 改动位置（精确行号 + diff 草稿）

**文件**：`clawsocket_compat.py`
**函数**：`_post`（定义于 L271）
**插入点**：L278（`if not response.ok: raise ...`）与 L279（`return response.json()`）之间。

### 改前（L271-284 原文）
```python
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
```

### 改后（仅改 try 块末两行）
```python
    def _post(self, url, headers, payload):
        last_error=None
        for attempt in range(1,self.retries+1):
            try:
                response=requests.post(url,headers=headers,json=payload,timeout=self.timeout)
                if response.status_code in {429,500,502,503,504} and attempt<self.retries:
                    time.sleep(2**(attempt-1)); continue
                if not response.ok: raise RuntimeError(f"HTTP {response.status_code}: {self._safe_error_body(response)}")
                _resp_json = response.json()
                _upstream_model = _resp_json.get("model", "unknown")
                _usage = _resp_json.get("usage") or {}
                print(f"[ClawSocket] upstream_model={_upstream_model} "
                      f"prompt_tokens={_usage.get('prompt_tokens', '?')} "
                      f"completion_tokens={_usage.get('completion_tokens', '?')} "
                      f"requested={self.last_model_used} "
                      f"fallback={self.last_model_fallback}")
                return _resp_json
            except Exception as exc:
                last_error=exc
                if attempt<self.retries and not str(exc).startswith("HTTP 4"): time.sleep(2**(attempt-1))
                else: break
        raise RuntimeError(str(last_error))
```

> **注意（噪声）**：`_post` 在一次逻辑请求内可能被重试/多协议探测/ fallback 多次调用，故同一请求可能打印多行。
> 可接受（CI 日志本就要 grep）；若要降噪，可在 print 前加 `if attempt == 1 and not self.last_model_fallback:` 之类闸门，本次先用简单版。

---

## 3. 测试方案（本地 mock，不调真实 API）

新增 `tests/test_model_fingerprint_log.py`，用 `monkeypatch` 替换 `requests.post`，`capsys` 捕获 stdout：

```python
import types, pytest
from clawsocket_compat import ClawSocketClient

def _fake_resp(json_body, ok=True, status=200):
    r = types.SimpleNamespace()
    r.ok = ok; r.status_code = status
    r.json = lambda: json_body
    r.text = ""
    return r

def test_logs_upstream_model_and_usage(monkeypatch, capsys):
    def fake_post(*a, **k):
        return _fake_resp({"model": "claude-opus-5-5",
                           "usage": {"prompt_tokens": 12, "completion_tokens": 34},
                           "content": [{"type": "text", "text": "hi"}]})
    monkeypatch.setattr("clawsocket_compat.requests.post", fake_post)
    c = ClawSocketClient(api_key="x"); c.last_model_used = "claude-opus-5-5"; c.last_model_fallback = False
    c._post("http://x", {}, {"model": "claude-opus-5-5", "messages": []})
    out = capsys.readouterr().out
    assert "[ClawSocket] upstream_model=claude-opus-5-5" in out
    assert "prompt_tokens=12" in out and "completion_tokens=34" in out
    assert "requested=claude-opus-5-5" in out and "fallback=False" in out

def test_missing_model_prints_unknown_no_crash(monkeypatch, capsys):
    def fake_post(*a, **k):
        return _fake_resp({"content": [{"type": "text", "text": "hi"}]})  # 无 model / 无 usage
    monkeypatch.setattr("clawsocket_compat.requests.post", fake_post)
    c = ClawSocketClient(api_key="x"); c.last_model_used = "claude-opus-5-5"; c.last_model_fallback = True
    c._post("http://x", {}, {"model": "claude-opus-5-5", "messages": []})  # 不应抛异常
    out = capsys.readouterr().out
    assert "upstream_model=unknown" in out
    assert "prompt_tokens=?" in out and "fallback=True" in out

def test_print_called_exactly_on_success(monkeypatch, capsys):
    def fake_post(*a, **k):
        return _fake_resp({"model": "gpt-6-astra", "content": [{"type": "text", "text": "ok"}]})
    monkeypatch.setattr("clawsocket_compat.requests.post", fake_post)
    c = ClawSocketClient(api_key="x"); c.last_model_used = "claude-opus-5-5"; c.last_model_fallback = True
    c._post("http://x", {}, {"model": "claude-opus-5-5", "messages": []})
    # 断言 stdout 至少出现一次 [ClawSocket] 前缀（验证 print 被触发）
    assert capsys.readouterr().out.count("[ClawSocket]") >= 1
```

- **用例 1**：`raw` 含 `model`+`usage` → 正确打印全部字段。
- **用例 2**：`raw` 不含 `model`/`usage` → 打印 `unknown` / `?`，**不崩**。
- **用例 3**：`capsys` 断言 `[ClawSocket]` 前缀出现 ≥1 次（print 被触发）。
- 全量回归：`pytest`（确保 5 用例叠加后整体仍 ≥ 既有通过数）。

---

## 4. 验证方式（明天改动 + push 后）

等下次 scan / review 真实跑：
1. 打开 GitHub Actions 对应 run 日志。
2. `grep "[ClawSocket] upstream_model="`。
3. 记录实际值。

| 日志显示 | 判断 |
|---|---|
| `upstream_model=claude-opus-5-5` | 真 opus，未降级 |
| `upstream_model=claude-fable-5-1` | 发生降级（主模型被拒） |
| `upstream_model=其他（如 gpt-6-astra）` | 中转站/网关偷换或 fallback 生效 |
| `upstream_model=unknown` | 上游不返回 `model` 字段 → 转 **token 计数法**（§1 的 `prompt_tokens` 仍可作辅助；若连 `usage` 都没有，则用 `MODEL_FINGERPRINT_METHOD.md` §2 层 3 行为法） |

> 因 scan/review 走 `stream`，日志会出现在多协议探测/fallback 路径上，grep 取**首次出现**或**非 unknown 的那条**即可。

---

## 5. 回滚方式

- 改动仅为 `_post` 内几行 `print` + 变量。
- 回滚：`git revert <sha>`（单行逻辑，干净）；或手动删这 5 行 `print`。
- 无副作用：不改动请求体、不改动路由、不影响 `raw`/返回值结构。

---

## 6. 实施时机

| 时间 | 动作 | 约束 |
|---|---|---|
| **今天 21:00 前** | 只做只读 + 本方案文档 | ❌ 不动 `clawsocket_compat.py`（scan 依赖它） |
| **明天上午（21:00 scan 跑完后）** | 应用 §2 diff + 加 §3 测试 + 全量 pytest + `commit` + `push` | 不激活新 flag（本改动无 flag，纯日志） |
| **周二 06:23 review 跑时** | 去 Actions 日志 grep `[ClawSocket] upstream_model=` | 即可见真值 |

---

## 7. 铁律确认

- 本文件为**方案 + 脚本**，当前**未修改** `/tmp/us` 任何文件；未 `push`/`rebase`/`commit`。
- 今日 21:00 scan 与周二 06:23 review 链路**未被触及**（改动推迟到明早）。
- 所有"调用/插桩/测试"均为**方案**，待明早执行。
