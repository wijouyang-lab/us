# Quant Dashboard 第一阶段：只读架构审计 + 最小实施方案

> 本阶段严格只读：未修改任何代码、未 commit、未 push。已同步远端到最新 main（`fa99093`）。

---

## 一、现有 Dashboard 架构（审计结果）

### 前端（index.html / app.js / app.css）

现有 section 顺序：

| # | Section | id | 数据来源 |
|---|---|---|---|
| 1 | Runtime 状态条 | runtimeStrip | runtimes（scan/review/evolve） |
| 2 | 宏观资产 | gmBar | market |
| 3 | $50,000 Portfolio | portfolioSec | portfolio |
| 4 | Core 持仓 | coreList | stocks（Core） |
| 5 | Observation 观察池 | obsList | stocks（Observation） |
| 6 | Global Markets | globalWrap | market.assets |
| 7 | Review 复盘 | reviewTiles | review + history |
| 8 | Options 策略 | optHomeList | options |
| 9 | History 跟踪趋势 | histList | history |

`app.js` 主渲染入口 `renderDashboard(data)`，子函数：`renderHeader / renderRuntime / renderGmBar / renderPools / renderGlobal / renderReview / renderOptions / renderHistory / renderPortfolio` + `drawPortfolioCurve / drawAllSparks` 等绘图。

### 数据 schema（dashboard_data.json 顶层 9 键）

```
generated_at, stocks[34], market, options[0], review,
history[46], runtimes{scan,review,evolve}, portfolio, meta
```

由 `dashboard_export.py` 的 payload 组装（line 2808）。**关键特性**：`dashboard_export.py` 是**零第三方依赖**（纯标准库 csv/json/os/urllib/pathlib），`build_portfolio()` 已示范"只读消费 CSV、不写回"的模式。

---

## 二、Quant Phase 1-7 当前可展示数据/状态（审计结果）

### 数据文件现状（全部不存在）

`quant_factor_snapshot.csv` / `price_history` / `backtest` / `validation` / `correlation` / `registry` / `clusters` / `score_v2_candidates` / `shadow_snapshot` / `production_*.json` **全部不存在**（snapshot 尚未产生 —— 今天 13:07 UTC 的 Scan 未到）。

### 各 Phase 可展示信息（静态 + 动态）

| Phase | 静态可展示信息 | 当前动态状态 |
|---|---|---|
| 1 Factor Library | 8 个扩展因子（Momentum 5/20/60D、RV_20D、Volume_Ratio_20D、ZScore_20D、Beta_60D_SPY、Stock_RS_20D） | `snapshot: NOT_ENOUGH_DATA` |
| 2 Backtest | HORIZONS=(5,10,20)、24 个因子（19 RAW + Quant_Score + 4 score） | `NOT_ENOUGH_DATA` |
| 2B Price History | 未复权收盘价持久化（auto_adjust=False） | `NOT_ENOUGH_DATA` |
| 3 Validation | 24 factor × 3 horizon = 72 行；状态枚举 8 种 | 72 行全 `NOT_ENOUGH_DATA` |
| 4 Score 2.0 | 3 个候选模型（A_CONSERVATIVE / B_BALANCED / C_MOMENTUM） | `enabled=false`、`NOT_ENOUGH_DATA` |
| 5 Walk-Forward | 4 模型（3 候选 + 1 基准 CURRENT_EXISTING_QUANT_SCORE） | `NOT_ENOUGH_DATA` |
| 6 Shadow | `SHADOW_ENABLE=false` | `SHADOW_DISABLED` |
| 7 Production | `QUANT_SCORE_V2_ENABLED=false`、production_model=V1 | `V1_ACTIVE / V2_DISABLED / production_gate=NOT_READY` |

状态枚举（已实现，可直接复用）：`NOT_ENOUGH_DATA / EXPLORATORY / WEAK_EVIDENCE / PROMISING / INCONCLUSIVE / REGIME_DEPENDENT / POTENTIALLY_REDUNDANT / PASS / FAIL / NOT_READY / BLOCKED / SHADOW_DISABLED / RESEARCH / CANDIDATE / PRODUCTION_ACTIVE / ROLLED_BACK` 等。

---

## 三、最小实现方案

### 核心原则

1. **最小侵入**：新增 Quant 独立 section，不破坏现有 9 个 section。
2. **零假数据**：所有 Quant 数据文件不存在 → 明确输出 `NOT_ENOUGH_DATA / DISABLED / NOT_READY`，绝不生成伪造的胜率/收益/权重。
3. **保持 dashboard_export.py 零依赖**：`build_quant()` 用**纯标准库**读数据文件存在性 + 静态状态，**不 import quant 模块**（避免引入 pandas 依赖、避免重耦合）。

### 数据层（dashboard_export.py）

新增 `build_quant(data_dir)` 函数（约 +80 行，纯标准库），产出 `payload["quant"]`：

```json
{
  "pipeline_status": "RESEARCH",           // 恒 RESEARCH（研究态）
  "v2_enabled": false,                      // 硬编码，对应 quant_score_v2.QUANT_SCORE_V2_ENABLED
  "production_model": "CURRENT_EXISTING_QUANT_SCORE",
  "phases": {
    "phase1_factor_library": {
      "status": "OK",
      "factors": 8,
      "snapshot_status": "NOT_ENOUGH_DATA",
      "snapshot_rows": 0
    },
    "phase2_backtest":   {"status": "NOT_ENOUGH_DATA", "horizons": [5,10,20], "factors": 24},
    "phase2b_price_history": {"status": "NOT_ENOUGH_DATA"},
    "phase3_validation": {"status": "NOT_ENOUGH_DATA", "factor_x_horizon": 72},
    "phase4_score_v2":   {"status": "NOT_ENOUGH_DATA", "enabled": false,
                          "models": ["MODEL_A_CONSERVATIVE","MODEL_B_BALANCED","MODEL_C_MOMENTUM"]},
    "phase5_walk_forward":{"status": "NOT_ENOUGH_DATA",
                          "models": ["MODEL_A","MODEL_B","MODEL_C","CURRENT_EXISTING_QUANT_SCORE"]},
    "phase6_shadow":     {"status": "SHADOW_DISABLED", "enable": false},
    "phase7_production": {"active_model": "CURRENT_EXISTING_QUANT_SCORE",
                          "v2_enabled": false,
                          "production_gate": "NOT_READY",
                          "state": "V1_ACTIVE"}
  }
}
```

状态判定规则（确定性，写入代码注释）：
- `snapshot.csv` 存在且非空 → 各 Phase 读真实数据；否则 `NOT_ENOUGH_DATA`。
- `QUANT_SCORE_V2_ENABLED` / `SHADOW_ENABLE` 恒 `false`（当前设计，硬编码 + 注释指向 quant_score_v2.py / quant_shadow.py）。
- `production_gate` 恒 `NOT_READY`（因 research/walk-forward/shadow 三 gate 均 NOT_ENOUGH_DATA，且无 Human Approval）。

### 前端（index.html + app.js + app.css）

1. `index.html`：在 Portfolio section 之后新增 `<section class="card sec" id="quantSec">`，含标题 "Quant Research / Factor Lab" + 状态概览容器 `#quantSummary` + Phase 列表容器 `#quantPhases`。
2. `app.js`：新增 `renderQuant()`（约 +80 行），在 `renderDashboard()` 里调用（`renderPortfolio()` 之后）。渲染：
   - 顶部 pipeline 状态卡片（RESEARCH / V2 DISABLED / V1 ACTIVE）
   - Phase 1-7 列表，每项显示 status 徽章（`NOT_ENOUGH_DATA` 灰 / `DISABLED` 灰 / `OK` 绿 / `PROMISING` 黄）
   - 无数据时不显示任何数字（胜率/收益/权重均不渲染，只显示状态文本）
3. `app.css`：复用现有 `.card .sec` + 少量状态徽章样式（约 +15 行）。

### payload 接线

`dashboard_export.py` 的 payload 组装处新增 `"quant": build_quant(data_dir)`。

---

## 四、预计文件改动

| 文件 | 改动 | 性质 |
|---|---|---|
| `dashboard_export.py` | +80（build_quant + payload 接线） | 修改（纯新增，不 import quant 模块） |
| `index.html` | +15（Quant section） | 修改 |
| `app.js` | +80（renderQuant） | 修改 |
| `app.css` | +15（状态徽章样式） | 修改 |
| `tests/test_quant_dashboard.py` | 新增（约 15 项：空数据状态、无假数据、payload schema、renderQuant 结构） | 新增 |

**不改**：scan.py / review.py / portfolio / quant_factor_*.py / quant_score_v2 / quant_walk_forward / quant_shadow / quant_production / 所有 workflow / requirements。

---

## 五、风险点

| 风险 | 等级 | 说明 |
|---|---|---|
| 硬编码状态常量与 quant 模块漂移 | P3 | `QUANT_SCORE_V2_ENABLED` 等若未来改变，需同步 build_quant。用注释锚定源文件位置缓解 |
| 数据文件未来产生后的状态衔接 | 设计预留 | build_quant 的判定规则已按"存在性→读真实数据"设计，数据来了自然从 NOT_ENOUGH_DATA 演进 |
| 破坏 dashboard_export 零依赖 | 无 | build_quant 用纯标准库，不 import quant 模块 |

## 六、验证计划

1. 新增 `test_quant_dashboard.py`：空数据 → 全 NOT_ENOUGH_DATA/DISABLED/NOT_READY；无任何伪造数字字段。
2. 全量 pytest（152 + 新增）。
3. dashboard_export 实跑（空数据）→ dashboard_data.json 新增 `quant` 键且状态正确。
4. 前端 renderQuant 不崩溃（结构验证）。

---

## 七、待确认（3 个问题）

1. **Quant section 位置**：放在 Portfolio 之后（第 4 位）还是放在最末尾（History 之后）？默认建议 **Portfolio 之后**（凸显 $50K 账户与 Quant 研究的关系）。
2. **状态徽章配色**：沿用 A 股"红涨绿跌"惯例？Quant 状态徽章建议中性色（灰=NOT_ENOUGH_DATA、蓝=OK、黄=PROMISING、绿=PRODUCTION_ACTIVE），不涉及涨跌红绿。确认后实施。
3. **是否接受"硬编码静态状态 + 数据文件存在性判定"**（不 import quant 模块）？这是保持 dashboard_export 零依赖、最小侵入的关键决策。若你希望"直接 import quant 模块生成状态"，我会调整方案（代价是 dashboard_export 引入 pandas 依赖）。

---

确认后进入第二阶段实施。本阶段未 commit、未 push。
