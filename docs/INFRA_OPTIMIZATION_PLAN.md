# 基础设施优化方案书（2026-10-16）

> 状态：方案已出，待逐项批准实施
> 来源：阶段 E 侦察 + 阶段 E2 补查

## 背景

阶段 E 侦察发现 3 项基础设施缺口：
1. 19 个 workflow 零失败通知
2. 0 处 actions/cache
3. 研究类 workflow 未 pin 依赖

补查已确认：
- workflow_run 事件可用（13/19 workflow 有 permissions 段）
- docs/archive/ 非重复（6/6 仅存于 archive）
- Dashboard 中位耗时 1m16s（最近 10 次）

## P0：失败通知（最高优先级）

### 问题
19 个 workflow 零失败通知。昨晚 3h 失败无人知。

### 候选方案

| 方案 | 做法 | 改动面 |
|------|------|--------|
| A（推荐） | 新增 1 个 workflow_run 触发的通知 workflow | 新增 1 文件 |
| B | 在每个 workflow 加 if: failure() 步骤 | 改 19 文件 |
| C | GitHub 内置通知 | 手动配置 |

### 推荐方案 A 实施步骤

1. 新增 .github/workflows/notify-on-failure.yml
2. 触发：on: workflow_run: types: [completed]
3. 判断：github.event.workflow_run.conclusion == 'failure'
4. 动作：创建 issue（最低成本，无需外部依赖）

### 待确认
- 通知渠道：issue / Slack / 邮件？
- 推荐 issue（无需外部依赖，GitHub 内置）

### 风险
低（新增文件，不动现有 19 个 workflow）

## P1：pip 缓存（高收益）

### 问题
0 处 actions/cache。Dashboard 每 15 分钟从零装依赖。

### 推荐
用 actions/setup-python@v5 内置 cache: 'pip'

### 实施步骤
每个 workflow 的 Setup Python 步骤改为：
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
    cache: 'pip'

### 改动面
19 个 workflow（每个改 1-2 行）

### 预期收益（实测修正）

**2026-10-16 试点实测结论**：
- 试点 `research-ic-2y-once.yml`：首次 1m45s（冷缓存）→ 二次 2m5s（缓存命中）
- **缓存命中成功**（日志 `Cache restored successfully`）但**耗时未降反升 20 秒**
- 原因：pip 缓存只省"下载"不省"安装"；本仓依赖栈为纯 wheel、无编译，收益本就有限
- **结论**：P1 在生产类 workflow 收益为负，**不推广**；研究类顺带保留

### 实施状态
- ✅ 试点 1 个（research-ic-2y-once.yml）
- ❌ 不推广到生产类
- ⚠️ 研究类随 P2 一起（见 P2 章节）

### 风险
低（GitHub 官方 action）

## P2：研究类依赖 pin

### 问题
研究类 workflow 裸装（pip install pandas numpy scipy），版本可能漂移。

### 推荐
新增 requirements-research.txt，研究类 workflow 统一引用。

### 实施步骤
1. 新增 requirements-research.txt（含 pandas/numpy/scipy/pandas_ta/yfinance/requests/lxml/html5lib）
2. 研究类 workflow 改为 pip install -r requirements-research.txt

### 改动面
新增 1 文件 + 改 ~10 个 workflow

### 风险
中（版本不兼容会导致研究类 workflow 失败）

## P3：push 重试统一

### 问题
18 个 workflow 含 git push，重试写法不统一。

### 推荐
提取公共 shell 脚本（tools/ci/push_with_retry.sh），所有 workflow 引用。

### 实施步骤
1. 新增 tools/ci/push_with_retry.sh
2. 18 个 workflow 的 push 步骤改为调用该脚本

### 改动面
新增 1 文件 + 改 18 个 workflow

### 风险
中（涉及多次改动，建议最后做）

## P4：cron 审视

### 现状
- dashboard-data.yml：*/15 * * * 1-5（工作日每 15 分钟）
- review.yml：23 22 * * 1-5（工作日 22:23）
- evolve.yml：0 2 1 * *（每月 1 日）
- skill-weekly.yml：0 20 * * 0（周日）

### 推荐
审视 dashboard 频率是否可降至每 30 分钟。

### 改动面
1 个 workflow（改 1 行）

### 风险
低（但影响 dashboard 数据新鲜度）

### 待确认
- Dashboard 每 15 分钟是否有必要？

## 优先级建议

| 优先级 | 项 | 改动面 | 风险 | 收益 |
|--------|-----|--------|------|------|
| P0 | 失败通知 | 新增 1 文件 | 低 | 极高 |
| P1 | pip 缓存 | 改 19 文件 | 低 | 高 |
| P2 | 研究类依赖 pin | 新增 1 + 改 10 | 中 | 中 |
| P3 | push 重试统一 | 新增 1 + 改 18 | 中 | 中 |
| P4 | cron 审视 | 改 1 文件 | 低 | 低 |

## 下一步

请用户确认：
1. P0 通知渠道（推荐 issue）
2. 哪些 P 项现在实施、哪些延后
3. 是否一次性实施 P0+P1（最高性价比组合）

---

## E 系列最终状态（2026-10-16 闭环）

### P0：失败通知 ✅ 已上线
- `notify-on-failure.yml`（workflow_run 触发，创建 ci-failure issue）
- 监控清单 19 项（含 PIT 2Y 快照补全）
- **双向实证**：失败 → issue ✓；成功 → skipped ✓
- 事故期间自动创建 5 issue，1 分钟内可发现

### P1：pip 缓存 ⚠️ 试点验证，收益为负，不推广
- 试点 `research-ic-2y-once.yml`：首次 1m45s → 二次 2m5s
- 缓存命中成功（`Cache restored successfully`）但**耗时未降反升 20 秒**
- 原因：pip 缓存只省"下载"不省"安装"；本仓依赖栈纯 wheel、无编译
- **结论**：生产类不推广；研究类随 P2 顺带保留

### P2：研究类依赖 pin ✅ 已推广到 10 个研究 workflow
- 新增 `tools/research/requirements-research.txt`（234 B，与生产 pin 一致）
- 9 个研究 workflow 改为 `pip install -r tools/research/requirements-research.txt`
- 顺带加 cache + cache-dependency-path（研究类风险低）
- **YAML 0 失败，生产类零改动**

### P3：push 重试统一 ⏸ 未做（低优先级）
- 18 个 workflow 含 git push，写法不统一
- 建议：提取 `tools/ci/push_with_retry.sh`，最后做（改动面最大）

### P4：cron 审视 ⏸ 未做（待用户确认）
- Dashboard 每 15 分钟是否必要？→ 待用户裁决

### 事故记录
- P1 首次实施（`b15e09a4`）缺少 `cache-dependency-path` → 19 workflow 失败
- 生产中断约 4 分钟（Dashboard 3 次失败）
- 已 revert（`84813d4d`）→ 生产恢复 1m22s
- 5 个 ci-failure issue 已关闭
- BOM 缺陷修复（`c1f4591c`）
- **教训**：批量改动前必须先在 1 个非生产 workflow 试点

### 关键 commit 索引
- `ac3b8ec8`：P0 新增 notify-on-failure.yml
- `4227f7df`：P0 修正监控清单
- `6f5b9da5`：P0 补 1 行监控
- `b15e09a4`：P1 首次实施（已 revert）
- `84813d4d`：revert P1
- `e50d6da5`：P1 试点（含 requirements-research.txt）
- `bd53c5c1`：BOM 修复
- `fb9c89d5`：方案书 P1 修正
- `b0f42953`：P2 推广到 9 个研究 workflow

---

## Dashboard 拆分尝试记录（2026-10-16）

### 目标
让 Dashboard 15 分钟 workflow 只抓数据，移出重活。

### 尝试
给 dashboard_export.py 加 `--no-network`（跳过网络抓取，只生成 JSON）。

### 结果
- export 耗时：22s -> 0.0s（-100%）
- **但价格数据完全冻结**：`--no-network` 完全跳过所有行情抓取，不读缓存报价
- docstring 自述：完全跳过行情抓取（只导出 CSV 派生数据）
- 源码：`mode="none"` -> `_init()` 立即返回 -> `yf.download` 不可达

### 已回滚
- `git revert 41eb6c63`
- 生产恢复：export 步骤耗时回到 ~22s

### 教训
**本会话第二次"未验证语义就上线"**：
- 第一次：P1 `cache: 'pip'` 缺少 `cache-dependency-path`
- 第二次：`--no-network` 未确认是否读缓存
- **共同根因**：只验证"改动生效"（日志/耗时），未验证"行为语义"（是否真的做了该做的事）

### 正确的拆分方向（待实施）
- 方案 A：高频 workflow 保留完整 export（带网络）
- 方案 B：拆成"抓取->落盘->生成"三段式
  1. 抓取：高频 workflow 只跑 `fetch_runtimes` + `fetch_market_indicators` + `portfolio_50000 --price-only`，结果落盘
  2. 生成：export 改为读缓存生成 JSON（需要一个真正的 `--read-cache` 模式，而非 `--no-network`）
- **前提**：必须先读 `build_stocks` / `build_market` 的 provider 使用细节，设计好"缓存读取"逻辑

### 关键发现
`dashboard_export.py` 的重量来源是**网络抓取**（22s->0s），而非指标计算。真正的拆分需要"抓取与生成解耦"，而非简单跳过网络。
