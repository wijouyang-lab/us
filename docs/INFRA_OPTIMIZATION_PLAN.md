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

### 预期收益
每次省 30-50 秒 → Dashboard 每日省 48-80 分钟 runner

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
