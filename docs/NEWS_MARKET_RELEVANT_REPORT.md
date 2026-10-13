# 市场相关度过滤 实施报告

> 时间：2026-10-10 00:47 (GMT+8)｜范围：仅 `dashboard/fetch_news.py` + `app.js` + 测试
> 铁律：未碰 review.py / review.yml / scan.py / portfolio_50000.py / dashboard_export.py / 任何 workflow

## 1. 改动 diff

### 1.1 后端 `dashboard/fetch_news.py`（commit `3aff4c7`）
- **Prompt 增强**：`_build_translation_prompt` 新增第 4 条要求 + JSON 格式加 `"market_relevant": true`
  - 直接影响（利率/CPI/财报/板块）→ true；间接影响（地缘推高油价、航空成本）→ true；纯司法个案/花边/无业务影响人事 → false；拿不准 → true（保守）。
- **归一化**：新增 `_norm_market_relevant(v)` —— 已是 bool 原样返回；字符串 `"false"/"no"/"0"`（忽略大小写/空白）→ False；其余（含 None/缺字段/True/`"yes"`）→ **True（保守不误删）**。
- **缓存完整性**：`_cache_complete` 增加 `and ("market_relevant" in tr)` → 旧缓存（无该键）判为不完整，触发一次重译补全（约 ~30 条，多花 ~30s，仅一次）。
- **落盘**：`translate_headlines` 输出、`apply_translations` 注入、`run()` 缓存写入三处均带上 `market_relevant`。
- schema_version 保持 `news.v1`（纯追加列、向后兼容，与 OHLCV 决策一致）。

### 1.2 前端 `app.js`（commit `b3e35a4`）
- 新增纯函数 `isMarketRelevant(x)`：`return !x || x.market_relevant !== false;`（false → 隐藏；缺失/true/其它/越界 → 显示）。
- `renderNews` 市场流：`(news.market_news || []).filter(isMarketRelevant)`；空 → 显示「暂无相关市场新闻」（不崩）。
- 持仓联动：每只 ticker 的 `list` 同样 `filter(isMarketRelevant)`；空 → 沿用「暂无」。
- 向后兼容：旧 `news_data.json`（无该字段）→ `undefined !== false` → 全部显示。

## 2. 新测试 + 全量测试

| 类别 | 测试 | 结果 |
|---|---|---|
| 后端单测 | `_norm_market_relevant`（10 例：bool/字符串否定/缺失/非否定） | ✅ |
| 后端 | AI 返回 `market_relevant=false` → 解析为 False | ✅ |
| 后端 | AI 缺 `market_relevant` → 归一化为 True | ✅ |
| 后端 | 旧缓存（无该键）→ `_cache_complete` 判不完整 → 重译补全 | ✅ |
| 后端 | 新缓存（含该键）→ 视为完整 → 不重译 + 命中原值 | ✅ |
| 后端 | 端到端：market_relevant 落到 news_data.json | ✅ |
| 前端 | node harness 验证真实 `app.js` 的 `isMarketRelevant`（false 隐藏 / 缺失·true·null 显示） | ✅ |

- 现有测试修正：因 `_cache_complete` 新增键要求，给 `test_cache_entry_with_rationale_empty_string_is_complete` 的预置缓存补 `market_relevant` 键（否则会误判不完整）。
- **全量结果：291 passed（基线 284 + 6 后端新测试 + 1 前端新测试），7 个 Deprecation 警告（非本次引入），零失败。**

## 3. 明早 review 安全性重申

- `git diff --name-only`（两个 commit）仅含：`dashboard/fetch_news.py` / `app.js` / `tests/test_fetch_news.py` / `tests/test_news_frontend_filter.py`。
- **未触碰 review.py / review.yml**（硬证据通过 grep 确认），未碰 scan.py / portfolio_50000.py / dashboard_export.py / 任何 workflow。
- 明早 06:23 review 走 `python portfolio_50000.py --data-dir .`，完全不读新闻数据与前端，**不受影响**。

## 4. commit SHA + push

| # | SHA | message | 文件 |
|---|---|---|---|
| 1 | `3aff4c7` | feat(news): add market_relevant field to AI translation | `dashboard/fetch_news.py` + `tests/test_fetch_news.py` |
| 2 | `b3e35a4` | feat(dashboard): filter non-market-relevant news items | `app.js` + `tests/test_news_frontend_filter.py` |

- push：`4525263..b3e35a4` → origin/main（已变基合入上游新增的 `4525263`，rebase 干净无冲突），工作树 clean。

## 5. 下周一预期

- **news-fetch 首次用新 prompt**：AI 对每个标题返回 `market_relevant`；翻译缓存因缺该键会触发一次性重译（~30 条，多 ~30s，仅此一轮）。
- `news_data.json` 每条带 `market_relevant`；前端 `renderNews` 过滤掉 `=== false` 的条目（如「两名男子否认替伊朗监视使馆」AI 标 false → 前端不再显示），缺失字段的旧数据仍全部显示（保守）。
- 过滤后空集 → 显示「暂无相关市场新闻」/「暂无」，不崩。
- 残余：无市场风险项需跟进；本次为纯前端+后端字段增强，爆炸半径为零。
