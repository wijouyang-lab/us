# 新闻翻译不完整 — 只读诊断报告

生成时间：2026-10-09（基于线上 `news_data.json` @ `2026-10-09T04:42:45Z` + 本地 `/tmp/us/dashboard/fetch_news.py`）
状态：**只读，未改代码、未 push、未碰监控**

---

## 1. max_tokens / 批量大小（代码实测值）

| 项 | 值 | 位置 |
|----|----|------|
| `max_tokens`（单次翻译调用） | **4000** | `fetch_news.py:325` |
| `MARKET_TRANSLATE_TOP`（市场翻译条数） | **10** | `fetch_news.py:62` |
| `TICKER_TRANSLATE_TOP`（每只持仓翻译条数） | **5** | `fetch_news.py:63` |
| 批量逻辑 | **无分批** —— 所有 `missing` 头条在 `translate_headlines()` 里**一次 API 调用**翻译完（:289-332） | `run()` :407-423 |

翻译目标集（`collect_translation_targets`，:202-221）：
- 市场 top 10 + 每只**持仓**（OPEN）top 5，按 headline 去重。
- 当前持仓 4 只（ADSK/ANET/ISRG/KR）→ 理论目标 = 10 + 4×5 = **30 条 / 次调用**。

> 注意：`ticker_news` 实际抓了**整个股票池**（~40 只，1559 条），但翻译范围只限 4 只持仓的 top 5。非持仓 ticker 显示 0 中文是**设计预期**，不是 bug。

---

## 2. 线上 news_data.json 实际翻译覆盖率

| 区块 | 总数 | 有 headline_cn | 说明 |
|------|------|----------------|------|
| market_news | 100 | **10** | top 10 全翻（符合 MARKET_TRANSLATE_TOP=10）✅ |
| ADSK | 23 | **3** | 期望 5（top5 全唯一）→ 缺 2 ❌ |
| ANET | 43 | **5** | 期望 5 ✅ |
| ISRG | 26 | **3** | 期望 5（top5 全唯一）→ 缺 2 ❌ |
| KR | 20 | **5** | 期望 5 ✅ |

**关键验证**：ADSK/ISRG 的 top-5 是 **5 条互不重复的 headline**（已逐条核对 `dup=False`），却只翻了 3 条 → 排除「去重导致少翻」假设，确认是**模型返回里漏了这 2 条**。

**期望 vs 实际**：一次批量请求 30 条，模型实际返回约 **26 条**（ADSK、ISRG 各少 2），差额 = **4 条/次**。

---

## 3. 解析与注入逻辑（为什么漏翻会"静默固化"）

### `_extract_json_array`（:254-286）
- 找第一个 `[`，跟踪括号深度，返回**第一个完整闭合的数组**。
- 若模型输出被硬截断（数组未闭合）→ 返回 `None` → `translate_headlines` 整体返回 `{}` → **全部丢弃**。
- 若模型返回**有效但不完整的前缀数组**（如 `[item1…item26]` 后收尾）→ 返回这 26 条 → **部分被接受**。
- 本次现象属后者（market 全翻证明数组正常闭合，非硬截断）。

### `run()` 的翻译调用（:407-423）
```python
missing = [...换行所有未命中头条...]
translated = translate_fn(missing) or {}      # 单次调用，无逐条重试
for h in missing:
    tr = translated.get(h)
    if isinstance(tr, dict):                    # 只有模型"返回了"的才写缓存+注入
        cache[hash] = {...}
```
- **无完整性校验**：不比对 `translated` 是否覆盖全部 `missing`。
- 模型漏翻的 4 条 → 不在 `translated` → 不写缓存、不注入 → 这些条目**本次无中文**。
- 因未进缓存，下次运行仍在 `missing` 里被重请；但模型**稳定地再次漏同样的 4 条** → 覆盖率固化在 26/30。

### `apply_translations`（:335-350）
- 对列表里**每个条目**按 headline hash 注入；只有命中缓存的才拿到 `headline_cn`/`sentiment`/`rationale`。
- 漏翻条目永远拿不到 → 前端回退英文（符合 R1，不崩，但"看起来没翻完"）。

---

## 4. 根因结论

**不是 max_tokens 截断，也不是去重，而是「模型返回了不完整 JSON 数组 + 代码无完整性校验/重试」，导致少量条目被静默丢弃并固化。**

- `max_tokens=4000` 对 30 条（含 rationale，约 2850 token）**绰绰有余**，不是瓶颈。
- 模型行为：返回 26/30，零散漏掉 ADSK[2][3]、ISRG[1][4]（非简单尾部截断，更像模型"跳过"部分条目）。
- 代码侧使得漏翻**无任何信号**（无 warning、无重试），每次运行稳定复现，覆盖率卡在 ~87%。

> 佐证：market 100 条只翻 10 是**设计**（top 10 展示）；ADSK/ISRG 缺 2 是**真实漏翻**。两者成因不同，不要混淆。

---

## 5. 修复方向（仅列出，未实施）

1. **完整性校验 + 缺口重试（最有效）**
   翻译后计算 `gap = set(missing) - set(translated)`；非空则对 `gap` 再调 `translate_headlines(gap)`，循环至覆盖或最多 N 次（如 2 次）。
2. **提高 max_tokens 安全余量**：4000 → 如 8000，杜绝任何 token 上限截断（即使当前非主因，成本低）。
3. **小批量翻译**：每批 10 条而非 30 条一次；配合逐批完整性校验，单批漏翻影响小、重试便宜。
4. **加 warning 日志**：`len(translated) < len(missing)` 时打印 `⚠️ 翻译缺口 N 条`，让 CI 日志可见（当前零信号）。
5. **提示词强化**：prompt 末尾加「必须返回与输入条数相同的 N 个对象，不得省略任何一条」。

> 优先级建议：①（缺口重试）+ ④（warning）组合，能在不增 API 成本的前提下消除"静默漏翻"；② 作为兜底防 token 截断；③ 可选优化。

---

## 附：本次改动铁律核对
- 未修改 `dashboard/fetch_news.py` 或任何代码；仅读取与拉取线上数据。
- 未 push / rebase；未碰监控 PID 108842；未改 workflow / 未激活 `ENABLE_TARGET_FILE`。
