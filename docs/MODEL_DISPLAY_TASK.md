# 任务文档：网页显示"运行时实际模型"

> **状态**：🔴 **待实施**（本文档是完整任务规格，可直接交给新会话执行）
> **创建**：2026-10-13
> **背景 commit**：`3ed5a4bb`（模型统一改为 `claude-fable-5-1`）
> **建议提交信息**：`feat(ai): collect upstream model usage` + `feat(dashboard): show model name in runtime strip`

---

## 一、目标

1. 每次 `scan` / `review` / `evolve` 跑完后，把**实际使用的模型**写入
   `dashboard/data/model_usage.json` —— 数据来自 ClawSocket 响应的 `upstream_model`
   （即中转站**真正返回**的模型），而不是我们**请求**的模型。
2. 网页顶部 runtime 条（`SCAN ✓ / REVIEW ✓ / EVOLVE ✓`）在每个状态标记后追加
   **本次实际用的模型名**。
3. **核心价值：让用户一眼看出中转站是否偷换了模型。**

### 为什么需要它（触发原因）

2026-10-13 的实测已经出现过两类"请求模型 ≠ 实际模型"：

- **scan 正常日志**：`请求引擎: claude-opus-5-5`，随后
  `⚠️ [ClawSocket] claude-opus-5-5 在真实 POST 阶段路由失败；尝试运行时备用模型 claude-fable-5-1`
  → 请求 opus，实际跑的是 fable。
- **同一次运行的 upstream 行**：`[ClawSocket] upstream_model=claude-opus-5-5 requested=claude-opus-5-5`
  → 这次却真的用了 opus。

**即：模型到底是哪个，只存在于 stdout 日志里，网页上看不到。** 而模型质量直接影响
scan 的选股与 review 的复盘质量 —— 用户必须能看见。

---

## 二、改动清单（逐文件 + 代码草稿）

### A. `clawsocket_compat.py`

**A1. 模块顶部新增累积器**（放在 `import` 之后、`class _TextBlock` 之前）：

```python
# --------------------------------------------------------------------------- #
# 运行时模型使用记录（供 dashboard 展示"中转站实际返回了什么模型"）
# 数据来源：ClawSocket 响应体里的 upstream_model / model 字段（见 _post）。
# 由调用方（scan.py / review.py / evolve.py）用 set_context() 标记当前语境，
# 跑完后用 write_model_usage() 落盘到 dashboard/data/model_usage.json。
# --------------------------------------------------------------------------- #
_MODEL_USAGE: dict = {}
_CURRENT_CONTEXT = None


def set_context(context: str) -> None:
    """调用方设置当前 context（'scan' / 'review' / 'evolve'）。"""
    global _CURRENT_CONTEXT
    _CURRENT_CONTEXT = context


def record_model_usage(context: str, model, requested: str, fallback: bool) -> None:
    """记录一次真实的模型使用。`model` = 中转站返回的 upstream model。"""
    _MODEL_USAGE[context] = {
        "model": model,
        "requested": requested,
        "fallback": bool(fallback),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_model_usage() -> dict:
    """返回当前进程内累积的使用记录（供测试/调试）。"""
    return dict(_MODEL_USAGE)


def write_model_usage(data_dir, context: str) -> None:
    """把当前 context 的记录**合并**写入 dashboard/data/model_usage.json。

    合并语义（重要）：文件里可能已有其它 context 的记录（scan 写的文件，
    review 不能覆盖掉）—— 所以先读旧内容，只更新自己那一个 key。
    任何异常都吞掉并打印警告：**记录模型失败绝不能让 scan/review 失败**。
    """
    try:
        path = Path(data_dir) / "dashboard" / "data" / "model_usage.json"
        existing = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
        if not isinstance(existing, dict):
            existing = {}
        existing[context] = _MODEL_USAGE.get(context)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ [model-usage] 写入失败（不影响主流程）：{type(e).__name__}: {e}")
```

**A2. 确认 `clawsocket_compat.py` 顶部的 import**

`datetime` / `timezone` / `json` / `Path` 必须已导入；缺哪个补哪个：
```python
import json
from datetime import datetime, timezone
from pathlib import Path
```

**A3. 在 `_post` 里现有的 `upstream_model` 打印之后追加一行**

现有代码（约 `:250` 附近）：
```python
print(f"[ClawSocket] upstream_model={data.get('model')} requested={...}")
```
紧跟着加：
```python
record_model_usage(
    _CURRENT_CONTEXT or "unknown",
    data.get("model"),
    self.last_model_used,
    self.last_model_fallback,
)
```

> ⚠️ `self.last_model_fallback` / `self.last_model_used` 已存在（见 `__init__`），直接用。

### B. `scan.py` / `review.py` / `evolve.py`

**B1. `main()` 开头**（`argparse` 之后、真正的业务逻辑之前）：
```python
set_context("scan")      # review.py → "review"；evolve.py → "evolve"
```
import 处补：`from clawsocket_compat import ClawSocketClient, set_context, write_model_usage`
（各文件现有 import 行按实际写法调整，通常是 `from clawsocket_compat import ClawSocketClient`。）

**B2. `main()` 结尾**（return 之前、**无论成功失败都要执行**）：
```python
write_model_usage(data_dir, "scan")   # 各自替换 context 名
```
> 建议放在 `finally:` 里，保证异常路径也能落盘 —— 否则最需要看模型的失败场景反而没记录。

### C. `scan.yml` / `review.yml` / `evolve.yml` 的提交步骤

在各 workflow 的提交块（`git add ...` 那一串）里加上：

```bash
if [ -f dashboard/data/model_usage.json ]; then
  git add dashboard/data/model_usage.json
fi
```

### D. `dashboard_export.py`

**D1. 新增读取函数**（放在 `_read_skill_serenity` 之后，沿用同一套哨兵模式）：
```python
# 哨兵：model_usage.json 不存在（从未跑过 / 被清理）时返回，用于「不注入键」
_MODEL_USAGE_MISSING = object()


def _read_model_usage(data_dir: Path):
    """读运行时模型使用记录 → 注入 dashboard_data.json 的 `model_usage`。

    缺文件 → 返回哨兵 → 调用方**不注入键** ⇒ dashboard_data.json 与加此功能前逐字节一致。
    解析失败 → 返回 None（前端隐藏 model 小字，但保留"键存在"这一事实）。
    """
    p = data_dir / "dashboard" / "data" / "model_usage.json"
    if not p.exists():
        return _MODEL_USAGE_MISSING
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"[WARN] 模型使用记录读取失败（{e}），model_usage 输出 null")
        return None
```

**D2. payload 组装处**（紧跟 `skill_serenity` 注入之后）：
```python
# ---- 运行时模型使用记录（缺文件 → 不注入键，保持逐字节一致）----
mu = _read_model_usage(data_dir)
if mu is not _MODEL_USAGE_MISSING:
    payload["model_usage"] = mu
```

### E. `app.js` 的 `renderRuntime()`

在渲染每个 runtime 状态标记（`SCAN ✓` 等）之后追加 model 小字：

```js
/* 运行时模型：让用户看出中转站是否偷换模型。
   无记录 → 不显示；fallback → 加 warn 样式并前置 ⚠️。 */
function runtimeModel(kind) {
  var mu = (DATA && DATA.model_usage) || {};
  var rec = mu[kind];
  if (!rec || !rec.model) return '';
  var m = String(rec.model);
  if (m.indexOf('claude-') === 0) m = m.slice(7);   // claude-fable-5-1 → fable-5-1
  return '<span class="runtime-model' + (rec.fallback ? ' warn' : '') + '" title="请求 ' +
    esc(rec.requested || '?') + ' · 实际 ' + esc(rec.model) + (rec.fallback ? '（运行时降级）' : '') +
    '">' + (rec.fallback ? '⚠️ ' : '') + esc(m) + '</span>';
}
```

调用点：`renderRuntime()` 里拼 `SCAN` / `REVIEW` / `EVOLVE` 三段 HTML 时，各接一个
`runtimeModel('scan' | 'review' | 'evolve')`。

> ⚠️ **实施前先读 `renderRuntime()` 的真实结构** —— 上面是按任务书给的示意，
> 实际拼串方式可能不同（例如走 `[].map().join('')`）。以真实代码为准。

### F. `app.css`

```css
.runtime-model{font-size:11px;color:#888;margin-left:6px;font-weight:500}
.runtime-model.warn{color:#d97706}
```

---

## 三、测试（4 个）

新建 `tests/test_model_usage.py`（或并入既有最贴近的文件）：

1. **`test_model_usage_record_and_write`**
   `set_context("scan")` → `record_model_usage("scan", "claude-fable-5-1", "claude-fable-5-1", False)`
   → `write_model_usage(tmp, "scan")` → 断言 JSON 里有 `scan.model / requested / fallback / updated_at`。

2. **`test_model_usage_merged_across_contexts`**
   先写 `scan`，再写 `review` → 断言文件里**两个 key 都在**、且 `scan` 的内容没被覆盖。
   （这一条是合并语义的核心保护，必须写。）

3. **`test_dashboard_export_injects_model_usage`**
   有文件 → `payload["model_usage"]` 存在且内容正确；
   无文件 → 返回**哨兵**、调用方**不注入键**（关闭时逐字节一致）。

4. **`test_frontend_runtime_shows_model`**
   用 `tests/_sk_harness.js` 同款 node 脚手架：`DATA.model_usage` 有值时渲染出
   `class="runtime-model"` 小字；`fallback:true` 时带 `warn` 与 `⚠️`；
   **无记录时不渲染任何 model 小字**。

**全量测试基线**：当前 **465 passed** → 期望 **≥ 469 passed**。

---

## 四、验证方式

1. 手动触发一次 `scan.yml`（`workflow_dispatch`，`ref=main`），等跑完（约 15 分钟）。
2. 拉 `dashboard/data/model_usage.json` 看结构：
   ```bash
   gh api repos/wijouyang-lab/us/contents/dashboard/data/model_usage.json \
     --jq '.content' | base64 -d | python -m json.tool
   ```
3. 拉线上 `dashboard_data.json`，确认出现 `model_usage` 键。
4. 打开 <https://wijouyang-lab.github.io/us/> 看 runtime 条是否显示 model 名
   （注意 Pages 有 ~75 秒部署延迟）。
5. **关键判读**：`upstream_model` 与 `requested` 不一致 → 中转站换了模型；
   `fallback: true` → 走了兜底链。

---

## 五、铁律

**只改**：
`clawsocket_compat.py` / `scan.py` / `review.py` / `evolve.py` /
`dashboard_export.py` / `app.js` / `app.css` / 3 个 workflow 的提交块 / `tests/`

**不碰**：`portfolio_50000.py` / `quant_*` / 任何数据文件

**流程**：`git fetch` → `git rebase origin/main` → `git push`；**不 amend / 不 force**

**建议拆 2 个 commit**：
```
1. feat(ai): collect upstream model usage across workflows
   - clawsocket_compat.py + scan.py + review.py + evolve.py + workflows + tests
2. feat(dashboard): show model name in runtime strip
   - dashboard_export.py + app.js + app.css + tests
```

---

## 六、已知坑（实施时务必注意）

1. **`record_model_usage` 的调用点必须 `try/except`** —— 记录失败绝不能让 scan/review 失败。
   `write_model_usage` 内部已兜底，但 `_post` 里的调用也要保证不抛。
2. **合并写入，不是覆盖** —— `write_model_usage` 必须读旧文件再改自己那一个 key，
   否则 review 会把 scan 的记录抹掉。
3. **`finally` 落盘** —— 失败路径同样需要记录（那才是最需要看模型的场景）。
4. **`model_usage` 缺文件 → 不注入键**，与 `market_indicators` / `skill_serenity`
   的哨兵机制保持一致，保证功能关闭时 `dashboard_data.json` 逐字节不变。
5. **`upstream_model` 可能为 `None`** —— 前端必须容忍 `model` 为空并不渲染小字。
6. **模型名缩写**：`claude-fable-5-1` 建议显示为 `fable-5-1`（去掉 `claude-` 前缀）以省横向空间，
   `title` 里保留全名。
