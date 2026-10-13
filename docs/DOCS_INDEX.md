# docs/ 索引：130 篇遗留设计/调查文档

> 生成日期：2026-10-13（周二 11:55）
> 说明：本索引把 `docs/` 下 130 篇历史工具文档按**主题**重组（而非文件名），每篇给一行摘要（< 30 字）与状态标签。
>
> **状态标签说明**
> - `已实施` —— 对应改动已落进代码/配置，或该调查的问题已被修复
> - `设计中` —— 只有方案/评估/决策草案，代码未落地或 flag 关闭未启用
> - `已废弃` —— 被同主题的后续文档覆盖（多版 Final/Stage 报告），或文档自述「不实施」
> - 带 `?` —— 依文档标题/类型 + 仓库现状推断，**未逐篇正文核验**，需人工确认
>
> **冲突标记**：同一主题存在多份互相覆盖的文档时用 `⚠️` 标注，详见第 15 节。
>
> ⚠️ 本文档为**只读整理**，未改动任何代码。

---

## 1. 组合账本 / $50k Portfolio Ledger（16 篇）

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| PORTFOLIO_50000_AUDIT_PLAN.md | 50k 账本只读审计与最小改造方案 | 已实施 |
| PORTFOLIO_50000_IMPLEMENTATION_REPORT.md | 50k 长期组合账本落地实施报告 | 已实施 |
| PORTFOLIO_UNIT_DESIGN.md | Unit 制持仓单位设计调查 | 已实施 |
| archive/PORTFOLIO_WEEKEND_GUARD_DESIGN.md | 周末休市不交易守卫设计 | 设计中? |
| PORTFOLIO_PRICE_SOURCE_INVESTIGATION.md | 持仓价格数据来源只读调查 | 已实施 |
| PORTFOLIO_REFRESH_HISTORY_INVESTIGATION.md | 组合价格刷新历史跟随调查 | 已实施 |
| archive/PORTFOLIO_SYNC_INVESTIGATION.md | 组合本地/云端不同步调查 | 已废弃? |
| PORTFOLIO_ENTRY_PRICE_INVESTIGATION.md | 买入价时点只读调查 | 已实施 |
| PORTFOLIO_OPTIONS_INVESTIGATION.md | 50k 持仓是否涉期权调查 | 已实施 |
| archive/PORTFOLIO_PREOPEN_RECOMMENDATION_INVESTIGATION.md | 盘前推荐机制可行性调查 | 设计中? |
| POSITION_CARD_DATA_INVESTIGATION.md | 持仓卡片渲染数据可行性 | 已实施 |
| POSITION_CARD_UPDATE_MECHANISM.md | 持仓卡片内容更新机制分析 | 已实施 |
| POSITION_CEILING_EVAL.md | 80% 股票天花板评估（自述不实施） | 设计中 |
| archive/BUY_PRICE_DESIGN.md | 买入价时点设计 | 设计中 |
| BUY_DECISION_OWNER.md | 买入决策归属（scan vs 账本）调查 | 设计中 |
| archive/STOPPED_PANEL_REPORT.md | 已止损记录前端面板实施 | 已实施 |
| SUCCESS_PATH_SIM.md | 周末「意外成功」全链路模拟 | 已实施 |

## 2. 止损 / 风控 / 数据契约（9 篇）

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| P0.5_stop_loss_repair_report.md | Stop_Loss 历史数据确定性修复 | 已实施 |
| INTRADAY_STOP_LOSS_DESIGN.md | 盘中机械止损设计 | 已实施 |
| INTRADAY_STOP_LOSS_IMPLEMENTATION_REPORT.md | 盘中机械止损落地实施 | 已实施 |
| ANET_STOPLOSS_TRIPLE.md | ANET 三个止损价溯源（只读） | 已实施 |
| archive/ANET_STOP_PROPAGATION.md | ANET 止损写回与账本消费溯源 | 已实施 |
| archive/PRE_WEEKEND_CHECK.md | 周末 5 处改动交叉风险体检 | 已废弃? |
| archive/WEEKEND_COMBO_CHECK.md | 周末组合体检第二轮静态分析 | 已废弃? |
| TECHNICAL_DATE_INVESTIGATION.md | Technical_Date 滞后问题调查 | 已实施 |
| CONTRACT_WARNING_REPORT.md | Technical_Date 契约告警实施 | 已实施 |

> 📌 ANET 两篇的问题已于 **本日（10-13）修复**：`rec_id_of` 键归一化 + ANET 状态重置，见 `HANDOVER.md`。

## 3. 调度 / 触发 / 部署（15 篇）⚠️ 多版本冲突重灾区

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| TRIGGER_ARCHITECTURE.md | 触发架构总文档（当前准绳） | 已实施 |
| archive/EXTERNAL_TRIGGER_VERIFY.md | 外部触发（cron-job.org）验证手册 | 已实施 |
| SCHEDULE_ADJUSTMENT_REPORT.md | review/evolve 离开整点调整 | 已实施 |
| SCAN_SCHEDULE_STAGE6C_REPORT.md | Stage 6C 第三次 schedule 验证 | 已实施 |
| archive/REVIEW_DOUBLE_RUN_READINESS.md | review 双跑就绪度只读检查 | 已实施 |
| archive/SCHEDULE_AUDIT_REPORT.md | Scan/Review/Evolve 调度审计 | 已废弃 |
| SCHEDULE_TRIGGER_INVESTIGATION.md | 调度是否真的触发调查 | 已废弃 |
| SCAN_SCHEDULE_INVESTIGATION.md | Scan schedule 调查 | 已废弃 |
| archive/SCAN_SCHEDULE_OBSERVATION.md | Stage 6B scan 调度观察 | 已废弃 |
| archive/DEPLOYMENT_AND_SCHEDULE_FINAL.md | 部署与调度「最终」报告 | 已废弃 |
| archive/FINAL_DEPLOYMENT_AND_SCHEDULE_AUDIT.md | 「最终」部署调度审计（二次） | 已废弃 |
| archive/DEPLOYMENT_STATUS_FINAL.md | 部署状态「最终」报告 | 已废弃 |
| archive/PHASE1_VERDICT_PLAYBOOK.md | 10-08 契约观测判决预案 | 已废弃 |
| archive/POST_VERDICT_SOP.md | 判决后操作清单 SOP | 设计中? |
| RUNTIME_TRIGGER_FIX_REPORT.md | Runtime 采集器触发修复 | 已实施 |

## 4. Quant Research（27 篇）⚠️ 审计/交付多版并存

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| archive/QUANT_RESEARCH_FACTOR_LAB_AUDIT.md | Factor Lab 第一阶段只读审计 | 已废弃? |
| QUANT_PHASE1_DATA_SOURCE_AUDIT.md | Quant Phase 1 数据源只读审计 | 已实施 |
| QUANT_PHASE2_7_ARCHITECTURE_AUDIT.md | Phase 2–7 架构只读审计 | 已实施 |
| QUANT_DASHBOARD_PHASE1_PLAN.md | Quant 面板第一阶段方案 | 已实施 |
| QUANT_PHASE1_DELIVERY_REPORT.md | Factor Library + 日频快照交付 | 已实施 |
| QUANT_PHASE2_DELIVERY_REPORT.md | 因子回测框架交付 | 已实施 |
| QUANT_PHASE2B_DELIVERY_REPORT.md | 持久化价格历史层交付 | 已实施 |
| QUANT_PHASE3_DELIVERY_REPORT.md | 因子验证引擎交付 | 已实施 |
| QUANT_PHASE4_DELIVERY_REPORT.md | Quant Score 2.0 交付 | 已实施 |
| QUANT_PHASE5_DELIVERY_REPORT.md | Walk-Forward/OOS 验证交付 | 已实施 |
| QUANT_PHASE6_DELIVERY_REPORT.md | Shadow Mode 框架交付 | 已实施 |
| QUANT_PHASE7_DELIVERY_REPORT.md | 生产集成与治理交付 | 已实施 |
| PHASE1_FIRST_REAL_DATA_REPORT.md | Phase 1 首份真实生产数据验证 | 已实施 |
| PHASE2_7_LOCAL_BUILD_REPORT.md | Phase 2–7 本地搭建报告 | 已实施 |
| archive/PHASE2_MAIN_REPORT.md | Phase 2 补 main() + 4 类测试 | 已实施 |
| archive/PHASE3_7_R1_REPORT.md | Phase 3–7 R1 全面修复 | 已实施 |
| archive/PHASE4_8_TEST_REPORT.md | Phase 3–7 补测报告 | 已实施 |
| archive/PRE_RUN_ROBUSTNESS_CHECK.md | Phase 2–7 健壮性预检 | 已废弃? |
| archive/DAILY_SNAPSHOT_SUFFICIENCY.md | 日频快照字段充足性调查 | 已废弃? |
| ALPHA101_FACTOR_RESEARCH.md | Alpha101 因子引入调研 | 设计中 |
| ACCELERATION_EXPERIMENT.md | 技术因子 OOS 加速实验 | 设计中 |
| REVIEW_SIMPLIFY_QUANT_RESEARCH_REPORT.md | review 精简 + quant 链式化 | 已实施 |
| SCHEMA_VERSION_REPORT.md | schema_version 实施报告 | 已实施 |
| SCHEMA_VERSION_CONSUMERS.md | schema_version 消费方预调查 | 已废弃 |
| FORWARD_RETURN_UNIFICATION_REPORT.md | Forward Return 实现统一交付 | 已实施 |
| TRADE_HISTORY_QUALITY_FIX_REPORT.md | Trade History 数据质量修复 | 已实施 |
| OHLCV_BACKFILL_REPORT.md | OHLCV 历史补采实施 | 已实施 |

## 5. 期权 Options（6 篇）⚠️ 4 份「验收报告」同主题并存

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| OPTIONS_WHEEL_DESIGN.md | 期权 Wheel（CSP→CC）设计 | 设计中 |
| archive/OPTIONS_RISK_AUDIT.md | 期权策略风险逻辑只读审计 | 已废弃 |
| OPTIONS_RISK_IMPLEMENTATION_REPORT.md | 期权风险/盈亏比改造实施 | 已实施 |
| archive/OPTIONS_RR_DEPLOYMENT_REPORT.md | RR 改造部署与生产验收 | 已废弃 |
| archive/OPTIONS_RR_PRODUCTION_VERIFICATION.md | RR 改造生产验收（只读） | 已废弃 |
| OPTIONS_RR_FINAL_ACCEPTANCE.md | RR 修复「最终」生产验收（准绳） | 已实施 |

## 6. 新闻 News（7 篇）

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| archive/NEWS_MODULE_DRAFT.md | 新闻板块需求草案 | 已废弃 |
| archive/NEWS_MODULE_DECISIONS.md | 新闻板块推进决策清单 | 已废弃 |
| NEWS_MODULE_IMPLEMENTATION.md | 新闻板块实施（Finnhub 免费档） | 已实施 |
| archive/NEWS_LOCAL_VERIFICATION.md | 新闻模块本地验证报告 | 已废弃? |
| NEWS_CN_GAP_INVESTIGATION.md | news_cn 覆盖缺口根因调查 | 已实施 |
| NEWS_TRANSLATION_INCOMPLETE_DIAGNOSIS.md | 新闻翻译不完整诊断 | 已实施 |
| NEWS_MARKET_RELEVANT_REPORT.md | 市场相关度过滤实施 | 已实施 |

> 📌 补充（文档外）：本日已追加**前端过滤 neutral 情感新闻**（`app.js` `isNewsVisible`），`docs/` 尚无对应文档。

## 7. Dashboard / Runtime（7 篇）

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| archive/DASHBOARD_PATH_INVESTIGATION.md | Dashboard 路径错位只读调查 | 已实施 |
| DASHBOARD_DATA_STABILITY_REPORT.md | 并发提交稳定性 + Mirror 隔离 | 已实施 |
| archive/DASHBOARD_DATA_CONCURRENCY_FIX_REPORT.md | 并发删除 Bug 修复报告 | 已废弃 |
| RUNTIME_IMPLEMENTATION_REPORT.md | Runtime metadata 实施 | 已实施 |
| archive/RUNTIME_DEPLOYMENT_REPORT.md | Runtime 架构升级部署验收 | 已实施 |
| archive/RUNTIME_VALIDATION_REPORT.md | Runtime 数据与字段验证 | 已废弃 |
| RUNTIME_ACCEPTANCE_REPORT.md | Runtime 最终验收（准绳） | 已实施 |

## 8. 宏观 Macro / 市场指标（4 篇）

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| MACRO_DATAFLOW_INVESTIGATION.md | 宏观数据在 scan 链中的流向 | 已实施 |
| MACRO_GOLD_SILVER_STATUS.md | 黄金/白银宏观数据状态调查 | 已实施 |
| MACRO_PANEL_ACTIVATION.md | 宏观板块 flag 激活清单 | 已实施（flag 已 ON） |
| MARKET_INDICATORS_PANEL_DESIGN.md | F&G + FedWatch 面板设计 | 设计中（flag 值未知） |

## 9. 模型 / AI 中转 ClawSocket（5 篇）⚠️ 与当前临时改动冲突

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| CLAWSOCKET_API_INVESTIGATION.md | ClawSocket 接口只读调查 | 已实施 |
| archive/MODEL_SWITCH_INVESTIGATION.md | gpt-6-astra→opus5.5 切换调查 | 已废弃 |
| MODEL_FINGERPRINT_METHOD.md | 实际模型识别方法 | 设计中 |
| archive/MODEL_FINGERPRINT_IMPLEMENTATION.md | 模型指纹实施方案 | 设计中 |
| archive/TOKEN_CONSUMPTION_ESTIMATE.md | 每日 AI Token 消耗静态估算 | 已实施 |

## 10. Scan（6 篇）

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| SCAN_AI_INPUT_FIX_REPORT.md | AI 输入字段缺失 KeyError 修复 | 已实施 |
| archive/SCAN_DATASOURCE_INVESTIGATION.md | 数据源与时间敏感性调查 | 已废弃? |
| archive/SCAN_FAILURE_DIAGNOSIS.md | 美股盘中扫描失败诊断 | 已废弃? |
| archive/SCAN_IDEMPOTENCY_INVESTIGATION.md | Scan 重复运行幂等性调查 | 已废弃? |
| SCAN_ROLE_REDEFINITION_DESIGN.md | Scan 角色重定义设计 | 设计中 |
| SCAN_REDEFINITION_IMPLEMENTATION.md | Scan 角色重定义（选 B）实现 | 已实施 |

## 11. Review 字段（3 篇）

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| archive/REVIEW_FIELD_AUDIT_REPORT.md | Price/Market_Regime 字段审计 | 已废弃 |
| REVIEW_FIELD_MAPPING_FIX_REPORT.md | Review 字段映射修复（准绳） | 已实施 |
| ECON_CALENDAR_L2.md | 事件日历 L2 调研（自述不实施） | 设计中 |

## 12. 23 小时交易 / 美股时段（4 篇）⚠️ 最大草稿，未落地

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| 23H_IMPLEMENTATION_DIFFS.md | 23 小时交易改造 Diff 级草稿 | 设计中 |
| archive/23H_TRADING_IMPACT.md | 23 小时 + 买入价影响面只读调查 | 设计中 |
| archive/US_SESSION_DESIGN.md | `_us_session.py` 设计文档 | 设计中 |
| YAHOO_NIGHT_SESSION_TEST.md | Yahoo 夜盘数据覆盖实测 | 设计中 |

> 📌 已核验：`_us_session.py` **在仓库中不存在** → 23H 尚未落地，仅为草稿。

## 13. Python 运行时 / 依赖 / 测试基建（5 篇）⚠️ PEP701 未解决

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| PEP701_TECHDEBT_REPORT.md | PEP 701（f-string 反斜杠）技术债确认 | 设计中（未修复） |
| PYTHON_RUNTIME_CONSISTENCY_AUDIT.md | Python 运行时版本一致性审计 | 已实施 |
| archive/PYTHON_DEPENDENCY_REPRODUCIBILITY_AUDIT.md | 依赖版本可重复性只读审计 | 已废弃 |
| PYTHON_DEPENDENCY_PINNING_REPORT.md | 生产依赖可重复性最小实施 | 已实施 |
| PYTEST_STANDARDIZATION_REPORT.md | pytest Runner 标准化交付 | 已实施 |

> 📌 已核验（10-13）：`scan.py:2690` 仍含 3.11 不兼容的 f-string 反斜杠 → **全量测试必须用 python3.12**，用 3.11 会在收集阶段报 SyntaxError。

## 14. 总览审计 / 运维计划（13 篇）⚠️ 「Final」互相覆盖

| 文档 | 摘要（<30字） | 状态 |
|------|--------------|------|
| archive/AUDIT_REPORT.md | 早期项目总审计报告 | 已废弃 |
| archive/ARCHITECTURE_AUDIT_REPORT.md | 架构只读审计 | 已废弃 |
| archive/FULL_PROJECT_AUDIT_REPORT.md | 全项目实跑 + 深度审计 | 已废弃 |
| archive/FULL_REPO_REEXECUTION_REPORT.md | 全仓库重跑 + 错误验证 | 已废弃 |
| archive/FINAL_PRODUCTION_BASELINE.md | 生产基线快照 | 已废弃 |
| FINAL_PRODUCTION_STABILITY_AUDIT.md | 最终生产稳定性总审计（准绳） | 已实施 |
| archive/P0_review_data_integrity_audit.md | P0 Review 数据完整性审查 | 已废弃 |
| WEEKEND_IMPLEMENTATION_PLAN.md | 周末实施计划（总纲） | 已废弃? |
| WEEKEND_CHANGELOG.md | 周末变更记录含回滚矩阵 | 已实施 |
| MONDAY_VERIFICATION_PLAN.md | 周一验证计划（周末改动验收） | 已废弃? |
| TONIGHT_CHECKLIST.md | 周一 10-12 当晚验证清单 | 已废弃（日期过期） |
| TUESDAY_CHECKLIST.md | 周二验证清单（含收尾清理） | 已实施（进行中） |
| INTRADAY_SPARKLINE_DESIGN.md | 盘中 sparkline 设计（方案 B） | 设计中 |
| SERENITY_SKILL_DESIGN.md | Serenity-Skill 独立模块设计 | 设计中 |
| SKILL_FRAMEWORK_DESIGN.md | Skill 通用框架设计 | 设计中 |

---

## 15. 冲突文档清单（同一主题多版本）

| 主题 | 冲突文档 | 建议以哪篇为准 |
|------|---------|--------------|
| 部署/调度 | 同主题 6 篇「Final/Stage」报告互盖 | `TRIGGER_ARCHITECTURE.md` |
| 总览审计 | AUDIT / ARCHITECTURE / FULL ×2 / FINAL ×2 | `FINAL_PRODUCTION_STABILITY_AUDIT.md` |
| 期权验收 | RR 部署 / 生产 / 最终验收 3 份并存 | `OPTIONS_RR_FINAL_ACCEPTANCE.md` |
| Runtime | Validation / Acceptance / Deployment | `RUNTIME_ACCEPTANCE_REPORT.md` |
| 新闻 | Draft / Decisions / Local Verification | `NEWS_MODULE_IMPLEMENTATION.md` |
| Quant 审计 | Factor Lab Audit vs Phase1/2-7 Audit | `QUANT_PHASE2_7_ARCHITECTURE_AUDIT.md` |
| Review 字段 | Field Audit vs Field Mapping Fix | `REVIEW_FIELD_MAPPING_FIX_REPORT.md` |
| 周末体检 | PRE_WEEKEND_CHECK vs WEEKEND_COMBO_CHECK | `archive/WEEKEND_COMBO_CHECK.md` |

### ⚠️ 与代码实际状态冲突的文档（注意！）

| 文档主张 | 代码实际情况（10-13 实测） |
|---------|------------------------|
| 扫描「每晚 21:00 自动跑」 | `scan.yml` **只有 `workflow_dispatch`，无 cron** → 依赖外部触发（cron-job.org），GitHub 侧不会自动排程 |
| `_us_session.py` 设计存在 | 仓库中**无此文件**，23H 未落地 |
| 盘中 sparkline 已规划 | `app.js` 中**无 `renderIntradaySpark`**，未实现 |
| PEP701 技术债待修 | 仍存在：`python3.11` 无法解析 `scan.py` |

---

*索引覆盖 130 篇；状态为基于文档类型 + 仓库现状的推断，带 `?` 者请人工复核后再据以行动。*
