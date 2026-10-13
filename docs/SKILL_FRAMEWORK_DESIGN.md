# Skill 通用框架设计（一次做好，未来加 skill 只写一个文件）

> 设计阶段文档，未实施、未改代码、未提交。
> 定位：**在 serenity 单个 skill 之上，抽一层通用框架**——未来任何新 skill 只需实现 `SkillBase` 并落一个文件即可自动接入。
> 落地时间：**12-06 后**（建议先于单个 skill 落地，框架比单点更值得先做）。

---

## 1. 目标

- 一次做好框架，**未来加任何 skill 只需写一个文件**（实现 `SkillBase`）。
- 主流程（scan / review）**零改动接入**：只调 `runner.run_all(context)`。
- 失败隔离、超时隔离、格式隔离全部在框架层统一处理。

---

## 2. 核心组件

| 文件 | 职责 |
|---|---|
| `skills/base.py` | 抽象基类（接口定义） |
| `skills/registry.py` | 自动发现 `skills/*.py` 并注册（排除 `base` / `__init__` / `README`） |
| `skills/runner.py` | 按 flag 过滤 + 按 schedule 执行 + 失败/超时隔离 + 汇总 |
| `skills/__init__.py` | 公开 API：`load_skills()` / `run_all(context)` |

---

## 3. 接口规范

每个 skill **必须**实现：

```python
# skills/<my_skill>.py
from skills.base import SkillBase


class MySkill(SkillBase):
    name = "my_skill"
    flag = "ENABLE_SKILL_MY_SKILL"
    schedule = "daily"          # daily / weekly / on_demand

    def run(self, context):
        # context 包含：positions / candidates / market_data
        # 返回：{"summary": str, "details": [...], "cost_tokens": int}
        ...
```

`context` 统一结构（由主流程构造一次，所有 skill 共享）：
```python
context = {
    "positions":   [...],        # 当前持仓
    "candidates":  [...],        # 候选池
    "market_data": {...},        # F&G / FedWatch / 宏观等（若已启用）
    "asof_et": "...",            # 美东时点
}
```

---

## 4. 执行流程

```
主流程（scan / review）
   ↓ 构造 context
   ↓ runner.run_all(context)
   ↓ 对每个已注册 skill：
        if flag 关闭            → 跳过
        if schedule 不匹配本周/今日 → 跳过（用 outputs json 的 updated_at 周次判断）
        else                    → 调 run(context)
   ↓ 汇总结果 → 写 dashboard/data/skills_output.json
   ↓ 前端渲染（按 name 分区块，未启用则隐藏）
```

`skills_output.json` 结构：
```json
{
  "updated_at": "2026-12-08T18:23:00-05:00",
  "skills": {
    "serenity": { "summary": "...", "details": [...], "cost_tokens": 2680 },
    "sentiment_analysis": { "summary": "...", "details": [...], "cost_tokens": 1200 }
  },
  "skipped": ["earnings_deep_dive"]   // 因 flag 关 / schedule 不匹配而跳过
}
```

---

## 5. 失败隔离

| 情形 | 框架处理 |
|---|---|
| 单个 skill **抛异常** | `try/except` 包裹，`runner` 记录 `error` 并继续下一个 skill；主流程不受影响 |
| 单个 skill **超时** | `concurrent.futures` / `signal` 设超时（如 60s），超时 → 跳过并记 `timeout` |
| skill **输出格式错** | 校验返回结构（必须含 `summary`/`details`/`cost_tokens`），不合格 → 忽略该 skill |

> 原则：**任何 skill 的成败都不应阻断 scan / review 的主 AI 决策链路**（与 `SERENITY_SKILL_DESIGN.md` §1 一致）。

---

## 6. 未来可加的 skill（举例）

| Skill | 用途 | 频率 |
|---|---|---|
| `serenity` | 产业链 + 机构视角分析 | 每周 |
| `earnings_deep_dive` | 财报深挖（业绩会要点 / 指引变化） | 按需（财报季） |
| `sentiment_analysis` | 情绪面分析（新闻/社媒情绪聚合） | 每天 |
| `macro_event` | 宏观事件日历 + 影响解读 | 每天 |

每个新 skill = **1 个文件 + 1 个 flag**，无需改框架、无需改主流程。

---

## 7. 实施时机

- **12-06 后**：建议**先于**单个 serenity skill 落地——框架到位后，serenity 只是框架的第一个具体实现。
- 与 23h 改造同批激活，避免在当前 scan/review 运行期引入改动。
- 灰度：先 `ENABLE_SKILL_SERENITY=1`；后续 skill 各自独立 flag 灰度。

---

## 8. 与 serenity 设计的关系

| 文档 | 范围 |
|---|---|
| `SERENITY_SKILL_DESIGN.md` | 单个 skill（serenity）的实现 + 替换/删除流程 |
| 本文 `SKILL_FRAMEWORK_DESIGN.md` | 通用框架（registry / runner / 失败隔离），serenity 是首个接入者 |

> 落地顺序建议：**先框架（本文）后单点（serenity）**；serenity 的 `skills/` 目录、接口、`renderSerenity` 直接复用本文约定，互不冲突。

---

## 9. 铁律确认

- 本文为**设计文档**，未修改 `/tmp/us` 任何文件；未 `push` / `rebase` / `commit`。
- 今日 21:00 scan 与周二 06:23 review 链路未被触及。
- 框架与所有 skill 均 flag 门控，关闭时对主流程零影响；任一 skill 失败不影响主链路。
