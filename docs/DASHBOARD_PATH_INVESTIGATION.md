# Dashboard 路径错位只读调查报告

> **调查目的**：判决前确认新闻模块上线后，前端能否真正读到新闻数据——即"路径错位"在生产环境是否真实存在。
> **调查性质**：只读 + 线上探测 + 静态代码核查。**未修改任何代码、未 push/rebase/commit、未碰监控 PID 536931。**
> **基准时间**：2026-10-08 13:06 GMT+8（≈ 05:06 UTC）。

---

## 0. TL;DR（核心结论）

**生产环境的路径其实是对齐的，本地验证看到的"错位"是本地 artifacts，不是生产 bug。**

- 用户担忧的"CI 把 export 写到 `us-market-terminal`、前端读根目录 → 新闻空白" **在生产中不会发生**：
  `dashboard-data.yml` 始终显式传 `--out dashboard/data/dashboard_data.json`，export 不会走 legacy 回退分支。
- 本地验证之所以看到错位，是因为当时命令是 bare `python dashboard_export.py`（无 `--out`），
  触发了 `dashboard_export.py:2759-2761` 的**默认-out 回退**：`us-market-terminal/` 目录若存在则写到那里。
  本地磁盘有该目录 → 写 legacy，根目录那份（陈旧、无 news 键）未动。
- 新闻上线真正的两道阻塞是 **`news-fetch.yml` 的 cron 仍为 `TBD`** 与 **`FINNHUB_API_KEY` Secret 未配**，
  这俩不解决，新闻才会恒为 `null`（与路径无关）。

---

## 1. GitHub Pages 部署源

| 项目 | 结论 | 证据 |
|---|---|---|
| Pages 部署动作 | **无独立部署步骤** | 6 个 workflow 中无任何 `deploy-pages` / `github-pages` / `peaceiris` 引用 |
| 部署源推断 | **`main` 分支根目录（`/root`）** | 无 `gh-pages` 分支（`git rev-parse` 报 MISSING）；仅 `main` 单分支 |
| 线上默认前端 | **根 `index.html`**（含 `app.js`） | `https://wijouyang-lab.github.io/us/index.html` → 200；`us-market-terminal/index.html` 仅为子路径可达，非默认 |
| 仓库 | `wijouyang-lab/us`，单分支 `main` | `git remote -v` → `wijouyang-lab/us` |

线上前端数据读取路径（实测）：
```
线上 root app.js:16  →  DATA_URL = 'dashboard/data/dashboard_data.json'
本地新闻版 app.js:4  →  dashboard/data/dashboard_data.json   （完全一致）
```
→ **生产前端读的就是根目录 `dashboard/data/dashboard_data.json`**，与本地新闻版同源。

---

## 2. dashboard-data.yml 的输出路径与提交逻辑

关键行号（`/tmp/us/.github/workflows/dashboard-data.yml`）：

| 行 | 内容 | 含义 |
|---|---|---|
| `84` | `ARGS="--data-dir . --out dashboard/data/dashboard_data.json ..."` | **显式指定输出到根目录 JSON** |
| `92` | `python dashboard_export.py $ARGS` | 跑 export，带 `--out` |
| `139` | `git add dashboard/data/dashboard_data.json dashboard/data/last_run.json dashboard/data/last_run.log` | **只提交根目录 3 个文件** |
| `138`（注释） | "绝不提交已停止维护的旧前端 `us-market-terminal/`" | 明确排除 legacy |
| `148`/`175` | 提交范围守卫：`grep -vE '^dashboard/data/(dashboard_data\.json\|last_run\.json\|last_run\.log)$'` | 任何非允许路径立即 `exit 1` |

**结论**：CI 运行 export 时 `--out` 被显式传入，输出**永远落在根目录** `dashboard/data/dashboard_data.json`；
提交守卫进一步保证不会把 `us-market-terminal/` 任何文件带入 `main`。
生产链路中 `dashboard_export.py` 的 legacy 回退分支（`:2759-2761`）**不会被触发**。

---

## 3. 线上实际可访问的路径（curl 探测）

| URL | HTTP | 内容 |
|---|---|---|
| `<pages>/dashboard/data/dashboard_data.json` | 200 | **生产数据**（含 `runtimes`，40 stocks，`meta.counts` 完整） |
| `<pages>/us-market-terminal/dashboard/data/dashboard_data.json` | 200 | legacy 前端数据（仅 legacy 子路径可读，默认不被访问） |
| `<pages>/index.html` | 200 | 默认前端（当前为**旧版**，无 newsCard） |
| `<pages>/us-market-terminal/index.html` | 200 | legacy 前端（0 newsCard，早已停止维护） |

线上 root `dashboard_data.json` 实测结构（完整解析 1.78MB）：
```
顶层键: generated_at, stocks, market, options, review, history, runtimes, portfolio, quant, meta
  news   键: 不存在（False）        ← 未上线，符合预期
  runtimes 键: 存在（scan/review/evolve）  ← 确为 dashboard-data.yml 产物
  stocks: 40 | meta.counts: core=13, observation=27, market 15/15, kline_ok=40 ...
```

`news_data.json` 线上状态：
```
<pages>/dashboard/data/news_data.json                          → 404（未上线，预期）
raw.githubusercontent.com/.../main/dashboard/data/news_data.json → 404
```
→ 新闻源文件尚未进入仓库，**新闻上线前 news 必然为 null**，与路径无关。

---

## 4. 路径错位对新闻上线的具体影响

### 4.1 生产环境（push 后真实链路）：**无影响**

```
news-fetch.yml ──提交──> dashboard/data/news_data.json (root)
                                    │
dashboard-data.yml ── --out root ──> dashboard/data/dashboard_data.json (root)  ← build_news 读 news_data.json 注入 news
                                    │
根 index.html + app.js (DATA_URL=root JSON)  ──读取──> 根 dashboard_data.json.news  ✓ 渲染
```
三者全部落在**根目录同路径**，前端 `DATA_URL` 与 export `--out` 与 news-fetch 提交路径**三点对齐**。
判定"路径错位导致新闻空白"在生产中**不成立**。

### 4.2 本地验证（bare 运行）：**有错位，但属本地 artifact**

```
python dashboard_export.py  (无 --out)
   └─ dashboard_export.py:2759-2761 默认分支
        └─ us-market-terminal/ 目录存在(on 本地磁盘) → 写到 us-market-terminal/dashboard/data/dashboard_data.json
           根目录 dashboard/data/dashboard_data.json 未更新（陈旧、无 news 键）
   根前端 serve 根 JSON → 显示「暂无新闻」
```
这正是 `NEWS_LOCAL_VERIFICATION.md` 记录的"错位"根因。**CI 不会走此分支**（因 `--out` 显式传入），故不反映生产行为。

### 4.3 真正的上线阻塞（与路径无关，必须解决）

1. **`news-fetch.yml` cron 仍为 `TBD`**（`news-fetch.yml:9` 注释待填，无生效 cron）。
   → workflow 永不调度 → `news_data.json` 永不生成 → `build_news` 返回 `None` → 新闻恒为空白。
2. **GitHub Secrets 未配 `FINNHUB_API_KEY`**（`news-fetch.yml:39` 引用 `secrets.FINNHUB_API_KEY`）。
   → 即使 cron 生效，抓取仍失败。

---

## 5. 修复方向（只列，不实施）

| # | 方向 | 说明 | 优先级 |
|---|---|---|---|
| 1 | **填 `news-fetch.yml` 的 cron** | 如 `23 */2 * * 1-5`（注释已给推荐值），并确认 Secrets 已配 `FINNHUB_API_KEY` | 🔴 上线前提 |
| 2 | **修 export 默认-out 回退（消除本地 footgun）** | `dashboard_export.py:2759-2761`：当无 `--out` 时，应默认写 `data_dir/dashboard/data/dashboard_data.json`（根），删除"若 `us-market-terminal` 存在则写那里"的回退。注释"前端目录=us-market-terminal"已是过时假设（前端早已迁 root） | 🟡 本地陷阱，建议修 |
| 3 | **（可选）清理 `us-market-terminal/` 遗留目录** | 删除该 legacy 前端，从根消除混淆（部署源已确认为 root，删除安全） | 🟢 整洁性 |
| 4 | **验证脚本（上线后）** | push 后等 `news-fetch` 跑一次 → `dashboard-data` 下次运行注入 `news` → `curl <pages>/dashboard/data/dashboard_data.json \| jq '.news'` 应非空 | 🔵 上线验收 |

> 注：方向 2/3 不改变生产行为（CI 已用 `--out` 对齐），仅消除本地预览的"假错位"，避免后续本地验证再次误判。

---

## 6. 与"us-market-terminal 遗留"的关系

`us-market-terminal/` 是**已停止维护的旧前端**，代码本身已将其定性为 deprecated：

- `dashboard_export.py:2742-2747`（注释）：
  > "显式把 JSON 同步写入 `us-market-terminal/dashboard/data/`；**默认关闭——该目录为已停止维护的旧前端**，
  > 继续同步会让 dashboard-data 的同一批数据在多次运行间产生无意义的重提交冲突。"
  > `--mirror` 默认 OFF 即不再同步。
- `dashboard-data.yml:138`（注释 + 提交守卫）：明确"**绝不提交已停止维护的旧前端 `us-market-terminal/`**"，
  提交范围守卫（`148`/`175` 行）硬性拒绝任何该目录文件进入 `main`。
- `git log -- us-market-terminal/`：仅见 `chore(dashboard): refresh market data [skip ci]` 数据刷新提交，
  **无任何前端代码改动**——前端早已迁移到仓库根目录（root `index.html`/`app.js`）。
- 本次新闻 commit `0a76ac6` 只改 root 的 `index.html`/`app.js`/`app.css`，**未触碰 `us-market-terminal`**，符合"新功能只建在受维护的 root 前端"的约定。

**结论**：本次报告的"路径错位"本质是上述 legacy 目录仍驻留磁盘 + export 默认-out 回退逻辑
（其注释假设前端仍在 `us-market-terminal`）共同造成的**遗留症状**，并非新引入的缺陷。
治理层面已在代码注释中将其标记为 deprecated；清理该目录（方向 3）即可彻底消除混淆。

---

## 7. 只读核查证据汇总

| 核查项 | 结果 | 来源 |
|---|---|---|
| Pages 部署源 | `main` 分支根目录 | 无 deploy action + 仅 `main` 分支 + 线上 4 路径均 200 |
| 线上前端 DATA_URL | `dashboard/data/dashboard_data.json`（root） | 线上 root `app.js:16` |
| CI export 输出路径 | `--out dashboard/data/dashboard_data.json`（root） | `dashboard-data.yml:84,139` |
| build_news 读新闻源 | `dashboard/data/news_data.json`（root） | `dashboard_export.py:2715` |
| news-fetch 提交路径 | `dashboard/data/news_data.json`（root） | `news-fetch.yml:46` |
| 线上 news_data.json | 404（未上线） | curl 探测 |
| 线上 root JSON 是否含 news | 否（键不存在，未上线预期） | 完整解析 1.78MB root JSON |
| legacy 目录性质 | deprecated，仅数据刷新、无代码改动 | `dashboard_export.py:2742-2747` + `git log` |

---

## 8. 铁律与 git 状态

- **未 push / 未 rebase / 未 commit**（本地验证副作用已按指令清理：`git checkout us-market-terminal/.../dashboard_data.json` + `rm dashboard/data/news_data.json`，`git status` 为空）。
- **未碰监控 PID 536931**。
- **未修改任何代码**：本报告为只读结论，方向 2/3 仅列不实施。
- 距 10-08 13:07 UTC 判决剩余约 **8 小时**（当前 05:06 UTC）。

---

## 9. 对判决后实施的建议顺序

1. 判决通过 → 按既定顺序 push（含新闻 commit `0a76ac6`）。
2. **先配 Secrets `FINNHUB_API_KEY` + 填 `news-fetch.yml` cron**（方向 1，否则新闻恒空）。
3. 等 `news-fetch` 跑一次生成 `news_data.json` → `dashboard-data` 下次运行注入 `news`。
4. 用 `curl <pages>/dashboard/data/dashboard_data.json | jq '.news'` 验收。
5. （建议但非必须）择机修 export 默认-out 回退 + 清理 legacy 目录，消除本地 footgun。
