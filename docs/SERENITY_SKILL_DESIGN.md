# Serenity-Skill 独立模块设计（可替换 / 可删除）

> 设计阶段文档，未实施、未改代码、未提交。
> 核心约束（用户要求）：**独立文件，方便换其他 skill 或删除**——必须做到"删文件 + 删 flag = 完全移除，且不影响主流程"。
> 落地时间：**12-06 后**（因需碰 `scan.py` / `review.py`）。

---

## 1. 核心设计原则

| 要求 | 落地设计 |
|---|---|
| **独立文件** | 每个 skill 一个 `.py` 文件，统一放 `skills/` 目录 |
| **可替换** | 约定统一接口（`SkillBase`），换 skill = 换一个文件 |
| **可删除** | 删文件 + 删 flag = 完全移除，前端板块自动消失 |
| **不影响主链路** | 任何 skill 抛异常 / 超时 / 输出格式错 → 主流程继续，仅跳过该 skill |

---

## 2. 目录结构

```
skills/
├── __init__.py           # 统一加载入口（暴露 load_skills / run_skill）
├── base.py               # 抽象基类（接口定义，零实现）
├── serenity.py           # serenity-skill 实现（首个具体 skill）
└── README.md             # 怎么加 / 换 / 删一个 skill
```

---

## 3. 统一接口（关键）

```python
# skills/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict


class SkillBase(ABC):
    # —— 元数据（子类用类属性覆盖）——
    name: str = ""                 # "serenity"
    flag: str = ""                 # "ENABLE_SKILL_SERENITY"
    schedule: str = ""             # "weekly" / "daily" / "on_demand"

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """输入 context（持仓/候选/市场数据），返回分析结果。

        返回约定：
            {
                "summary": str,            # 一句话结论
                "details": [               # 每只持仓一段叙事
                    {"ticker": "AAPL", "narrative": "...", "tokens": 520},
                    ...
                ],
                "cost_tokens": int,        # 本次 AI 实际消耗
            }
        任何异常都应在调用方被吞掉，绝不向上抛。
        """
        raise NotImplementedError
```

---

## 4. serenity.py 实现

### 4.1 输入
- `$50k` 组合的 **4 只持仓**（来自 positions / portfolio 状态）
- 当前市场数据（可选：价格、行业、近期新闻摘要）

### 4.2 分析框架（serenity = 产业链 + 机构视角）
对每只持仓，按"产业链位置 + 机构行为/筹码结构"两个维度生成叙事：
- **产业链**：上游/中游/下游、供需瓶颈、涨价/降价传导。
- **机构视角**：谁在买/卖、筹码集中度、估值与预期的背离。

### 4.3 输出
- 每只持仓一段叙事分析，**~500 token/只**。
- **AI 调用：一次批量**（4 只一起喂给 AI，而非 4 次）——降低调用次数与冷启动开销。

### 4.4 成本
| 项 | 估算 |
|---|---|
| 单次 token | ~2000–3000 token（4 只批量） |
| 频率 | 每周 1 次 |
| 月成本 | ~¥0.5–1 / 月（远低于其它 AI 决策） |

---

## 5. 触发方式（推荐 B）

| 选项 | 实现 | 复杂度 | 评价 |
|---|---|---|---|
| **A. 独立 workflow** | 新 `skill-weekly.yml`，每周日定时跑 | 中 | 隔离好，但多一条 workflow 维护 |
| **B. 挂到 review 后面** ✅ | review 加 flag 判断"本周是否已跑"，首次 review 时跑 | 低 | 复用现有 review 触发，零新增 workflow |

**推荐 B**：每周只在第一次 review 时跑 serenity（review 本身周二~周五盘后运行，自然落在周内）。用 `dashboard/data/skill_serenity.json` 的 `updated_at` 周次判断"本周是否已跑"，避免重复。

```python
# review.py 尾部（flag 门控，示意）
if os.environ.get("ENABLE_SKILL_SERENITY") == "1" and _skill_not_run_this_week("serenity"):
    from skills import load_skill
    skill = load_skill("serenity")
    result = skill.run(context)
    _write_json_safe("dashboard/data/skill_serenity.json", result)
```

---

## 6. 输出展示

- 写 `dashboard/data/skill_serenity.json`：
  ```json
  {
    "updated_at": "2026-12-08T18:23:00-05:00",
    "summary": "本周持仓情绪偏谨慎……",
    "details": [
      {"ticker": "AAPL", "narrative": "……", "tokens": 510},
      {"ticker": "MSFT", "narrative": "……", "tokens": 498}
    ],
    "cost_tokens": 2680
  }
  ```
- 前端**独立区块**（或并入现有 AI 分析区）：`renderSerenity(data)`。
- skill 关闭时：该区块**隐藏**（前端判断 `data` 为空或 flag 关）。

---

## 7. 替换 / 删除流程

### 换 skill（例如换成 `other_skill`）
```
1. 新建 skills/other_skill.py（实现 SkillBase 接口）
2. 改 flag 名（ENABLE_SKILL_OTHER_SKILL）
3. 删 skills/serenity.py（或保留作为参考）
4. 前端自动显示新 skill 输出（渲染入参由 payload 决定，无需改渲染逻辑）
```

### 删除 skill（彻底移除 serenity）
```
1. 删 skills/serenity.py
2. 删 flag（ENABLE_SKILL_SERENITY，连同 workflow/review 中的引用）
3. 前端板块消失（无数据 → 隐藏）
4. 主流程完全不受影响（review 中该 flag 判断分支整体失效）
```

---

## 8. 改动半径

| 类型 | 文件 | 改动 |
|---|---|---|
| **新增** | `skills/` 目录（3–4 文件：`__init__.py` / `base.py` / `serenity.py` / `README.md`） | 框架 + 首个实现 |
| **修改** | `review.py`（或 `scan.py`） | 加 flag 判断 + 调 skill（本周是否已跑） |
| **修改** | `dashboard_export.py` | 注入 `skill_serenity` 到 payload |
| **修改** | `app.js` | 新增 `renderSerenity(data)` |
| **新增** | `tests/test_skills.py` | ① 接口契约测试；② 异常隔离测试；③ flag 关=跳过 |

> 因需碰 `review.py` / `scan.py`，实施排期在 **12-06 后**（与 23h 改造同批，避免干扰当前 scan/review 运行）。

---

## 9. 实施时机

- **12-06 后**：必须先完成 23h 改造（scan/review 稳定），再引入 skill 框架，避免双线风险叠加。
- 灰度：先 `ENABLE_SKILL_SERENITY=1`，观察 AI 叙事质量与成本 1–2 周，再长期保留。

---

## 10. 铁律确认

- 本文为**设计文档**，未修改 `/tmp/us` 任何文件；未 `push` / `rebase` / `commit`。
- 今日 21:00 scan 与周二 06:23 review 链路未被触及。
- skill 框架与具体实现均 flag 门控，关闭时对主流程零影响。
