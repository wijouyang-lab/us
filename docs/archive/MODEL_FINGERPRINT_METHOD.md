# ClawSocket 实际模型识别方法（Model Fingerprint）

> 只读静态分析报告，未调用任何 API，未修改 `/tmp/us` 代码。
> 目的：在不真调 API（限流 + 计费）的前提下，确定 ClawSocket 网关**实际**返回的是
> Claude / GPT / Llama 中的哪一个，并给出 3 层检测法的操作与可信度排序。

---

## 0. 先给结论（基于静态代码）

**当前代码无法从日志里知道 ClawSocket 实际给了什么模型。**

- 响应里的 `model` 字段：**客户端从不解析、从不打印**（`_extract_text` 只取文本，`_post` 只 `response.json()` 后交给文本提取）。
- 响应里的 `usage`（`prompt_tokens` / `completion_tokens`）：**全仓库零引用**——连提取都没有，更不打印。
- 唯一保留上游完整 JSON 的地方是 `_Response.raw`（L16），但**没有任何地方打印或检查 `raw`**。
- 日志里出现的 `last_model_used` / `CLAWSOCKET_LIVE_MODEL`（scan.py:218、2939）反映的是**客户端决定发送的**模型 ID（解析后的 `resolved`、variant、或运行时 fallback），**不是上游实际服务的模型**。网关若二次路由，这里看不出来。

> 换句话说：客户端把"我请求了谁"当成了"谁服务了"，但二者在 ClawSocket 网关下可能不一致
> （见 L118-144 运行时 fallback：主模型 POST 失败会退 `claude-fable-5-1` → `gpt-6-astra`）。

---

## 1. 代码里能看到的字段

| 字段 | 来源 | 是否被解析 | 是否被打印/记录 | 含义 |
|---|---|---|---|---|
| 请求侧 `model`（payload） | `clawsocket_compat.py` L287/294/300 | 是（发送） | 否（仅用于发送） | 客户端**想**用的模型 |
| `last_model_used` | L180/338/368/390 | 是 | ✅ print + env | 客户端**决定发送**的模型（≠ 上游实际服务） |
| `CLAWSOCKET_LIVE_MODEL` (env) | L182/335/351 | 是 | ✅ | 启动 `live_probe` 实测成功的模型名（仍是"请求侧"） |
| 响应 `model`（上游回传） | 藏在 `response.json()` 内 | ❌ **未提取** | ❌ | 上游**实际服务**的模型（真值，但被丢弃） |
| 响应 `usage` | 藏在 `response.json()` 内 | ❌ **未提取** | ❌ | token 计数（真值，但被丢弃） |
| `_Response.raw` | L16 | 持有但未用 | ❌ | 上游完整 JSON，**唯一能拿真值的入口** |

**要点**：真值（上游 `model` / `usage`）只在 `raw` 里，而 `raw` 从不暴露。
要拿到真值，唯一办法是**读取 `response.raw`**——目前需要一次性插桩（见 §2 层 1 动态部分）。

---

## 2. 3 层检测法（具体操作）

### 层 1 · 响应体字段核查（response body）
**目标**：直接看上游回传 JSON 里有没有 `model` / `usage`，是否被记录。

- **静态（已做，零成本）**：读 `clawsocket_compat.py` 的解析段（`_post` L271-284、`_extract_text` L256-258、
  三个 `_extract_*_text`）。结论：客户端只取文本，不取 `model`/`usage`，`raw` 持有但不打印。
  → 静态层面**已确认代码不暴露真值**。
- **动态（需一次性调用，本次未做）**：在 `create()` 返回处临时 `print(response.raw.get("model"), response.raw.get("usage"))`，
  发 1 个最小请求（如 `live_probe` 的 "Reply with exactly: OK"），从 `raw` 读出上游真正的 `model` 字符串。
  - 若 `raw["model"]` 存在 → 直接得到真值（如 `"gpt-6-astra"` / `"claude-opus-5-5"`）。
  - 若网关**不回传** `model`（很多代理会剥掉）→ 层 1 动态失败，转层 2/层 3。

### 层 2 · token 计数对照（usage）
**目标**：用固定文本（如 `"Hello world"`）发请求，记录 `usage.prompt_tokens`，通过 tokenizer 差异区分模型家族。

- **前提**：当前代码根本不读 `usage`（见 §1），所以必须先从 `raw` 取出 `usage.prompt_tokens`。
- **操作（设计，本次未执行——遵守"不真调 API"）**：
  1. 插桩读取 `raw["usage"]["prompt_tokens"]`。
  2. 对同一段固定文本（英文短句 + 一段中文 + 一段代码）分别记录 prompt_tokens。
  3. 对照已知 tokenizer 的 token 数：Claude/OpenAI/Llama 对同一文本 token 数不同（中文、emoji、代码差异最明显）。
- **为什么这次跳过**：不确定能否调（沙箱限流 + 计费），按用户要求只做静态分析。

### 层 3 · 行为特征（behavioral fingerprint）
**目标**：设计 5 个可区分 Claude / GPT / Llama 的 prompt（**不执行，仅设计**）。

| # | 测试 prompt（中性、无敏感内容） | 区分逻辑（假设性，非断言） |
|---|---|---|
| 1 | "用中文逐字数出：『人工智能正在改变世界』有几个字，只回答数字。" | 不同模型对 CJK 计数/对齐的稳健度不同；GPT 系曾对精确字符计数更易出错 |
| 2 | "用一句话解释 affect 和 effect 的区别并各给一个例句。" | 措辞风格、例句选择有家族特征；Claude 偏谨慎规整，GPT 偏口语，Llama 偏模板化 |
| 3 | "Which is larger, 9.11 or 9.9? Answer in one word." | 经典浮点/版本号陷阱；部分 GPT 早期版本答错，Claude 多答对，可作辅助信号 |
| 4 | "把『The quick brown fox jumps over the lazy dog』翻译成法语，再翻译成德语。" | 多步翻译的流畅度与回译一致性：闭源大模型 > 多数开源 Llama 衍生 |
| 5 | "写一段 80 字内的科幻微小说，结局必须出人意料。" | 创意风格聚类：Claude 偏文学性、GPT 偏直白、Llama 衍生常偏套路/重复 |

> 行为法**只能做旁证**：网关可对齐输出、prompt 微小改动即翻转结果，且 Llama 经指令微调后风格可接近闭源。
> 绝不能作为唯一判据。

---

## 3. 各层可信度

| 层 | 方法 | 可信度 | 依赖 | 成本 |
|---|---|---|---|---|
| **层 1（动态读 raw.model）** | 直接读上游回传的 `model` 字段 | **高**（真值，若网关回传） | 需 1 次插桩调用 | 1 次 API 调用 |
| **层 1（静态）** | 确认代码不暴露真值 | **高（关于"代码现状"）** | 无 | 0 |
| **层 2（usage）** | tokenizer 差异推断家族 | **中** | 需读 `raw.usage` + 调用 | 1+ 次调用 |
| **层 3（behavior）** | prompt 行为聚类 | **低** | 无（可零成本设计） | 0（设计）/ 多调用（验证） |

**关键约束**：层 1 动态能否成功取决于**网关是否回传 `model`**。若网关剥掉该字段，层 1 动态与层 2 都失效，
只剩层 3（低可信）。这种情况下需改用"请求侧对账"：比对 `last_model_used` 与实际输出风格是否矛盾。

---

## 4. 建议先做哪一层

**优先级：层 1 动态（读 `raw.model`）＞ 层 2 ＞ 层 3。**

1. **首选层 1 动态**：它是唯一可能拿到**权威真值**的路径，成本仅 1 次最小调用。
   - 操作：在 `clawsocket_compat.py` 的 `create()`（L33）或 `_post`（L279）临时加一行
     `print("RAW_MODEL=", raw.get("model"), "RAW_USAGE=", raw.get("usage"))`，
     跑一次 `live_probe`，看 `raw["model"]` 是否为真值。
   - 若能拿到 → 任务结束，可信度最高。
2. **若层 1 动态拿不到 `model`** → 做层 2（`raw.usage` 的 token 数对照），用 tokenizer 差异锁定家族（Claude/OpenAI/Llama）。
3. **层 3 仅作零成本旁证**：现在就能设计（见 §2 层 3），但不能单独下结论。

> 本次因"不真调 API"约束，**只完成了层 1 静态 + 层 3 设计**。层 1 动态、层 2 需在允许调用时执行。

---

## 5. 已知运行时 fallback 链（影响"实际模型"判断）

即使请求写的是 `claude-opus-5-5`，ClawSocket 在真实 POST 路由失败时可能切换：

- 主链（业务函数）：`claude-*` 默认 fallback → `claude-opus-4-6` / `claude-sonnet-4-5-20250929`（L91）；
  `gpt-*` → `gpt-6-astra` / `gpt-5.4` / ...（L91）。
- 运行时兜底（POST 阶段 `model route` 类错误）：`claude-fable-5-1` → `gpt-6-astra`（L137）。

**含义**：`last_model_used` 可能已经是 fallback 后的模型；而网关侧的二次路由仍可能再变。
所以"客户端记录了什么模型" ≠ "用户最终拿到的内容来自哪个模型"，这正是必须读 `raw` 的原因。

---

## 6. 铁律确认

- 本报告为**只读静态分析 + 文档**，未调用 ClawSocket API，未修改 `/tmp/us` 任何文件。
- 未 `push` / `rebase` / `commit`；今日 21:00 scan 与周二 06:23 review 链路未受影响。
- 所有"调用/插桩"步骤均为**设计**，需用户在允许调用时另行执行。
