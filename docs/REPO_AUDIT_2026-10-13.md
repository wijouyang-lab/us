# 仓库复查报告 · wijouyang-lab/us

> **复查日期**：2026-10-13
> **基线 commit**：`4ce239e9`（`docs: mark 模型展示 as implemented in HANDOVER §2.3`），`main == origin/main`
> **复查范围**：`git ls-files` 全部 **358** 个被跟踪文件（本地 clone；本机未挂 GitHub MCP，未读远程，结论等价）
> **复查性质**：**只读**。复查结束时 `git status --porcelain` 为空、`HEAD` 未变。除本文件外未新增 / 修改 / 删除任何文件。

---

## 使用说明（先读这一段）

1. **本文档是只读复查产物，不代表任何问题已被修复。** 写入时所有条目均处于「已确认存在」状态。
2. **修复时必须逐项核对，不可批量套用。** 同类问题在本仓库成因各不相同 —— 例如 `|| true` 全仓库共 6 处，其中 3 处是有意为之并附注释说明原因，批量替换会制造新故障。
3. **本文档所有行号基于 commit `4ce239e9`。** 后续任何 commit 都可能使行号漂移；定位时先 `git log -1 --format=%h` 确认基线，必要时用**内容**而非行号检索。
4. 证据栏中的 `/tmp/us`、`/workspace`、`/mnt/data/...` 均为**历史沙箱路径**，不是本机路径，请勿直接复制执行。
5. §5 记录了**两处已被实测推翻的误报**以及本次复查**未能覆盖的范围**。引用本文档结论前请一并阅读。

---

## §0 分布统计

### 按顶层目录

| 目录 | 文件数 | | 目录 | 文件数 |
|---|---|---|---|---|
| `docs/` | 134 | | `.github/` | 9 |
| `tests/` | 50 | | `us-market-terminal/` | 4 |
| `tools/` | 24 | | `_temp_experiment/` | 4 |
| `skills/` | 13 | | `scripts/` | 2 |
| `dashboard/` | 11 | | **根目录散落** | **107** |

### 按扩展名

| 扩展名 | 数量 | | 扩展名 | 数量 |
|---|---|---|---|---|
| `.md` | 185 | | `.html` | 4 |
| `.py` | 102 | | `.txt` | 3 |
| `.json` | 16 | | `.patch` | 2 |
| `.csv` | 15 | | `.js` / `.css` | 2 / 2 |
| `.csv.processed` | 12 | | `.log` / `.sh` / `.cjs` | 1 / 1 / 1 |
| `.yml` | 9 | | `(none)` / `.example` / `.gitignore` | 1 / 1 / 1 |

### 结构性结论

358 个文件里 **172 个（48%）是 Markdown 或根目录散落的文档/数据**。仓库根目录同时扮演「源码 + 生产数据 + 文档 + 沙箱存档」四种角色 —— 这是本仓库最大的"多余"来源，也是 §1 绝大多数条目的共同根因。

---

## §1 【多余】清单

### 1.1 存档目录（自述"存档 / 不参与生产"却仍在 main）

| 路径 | 类别 | 证据 | 建议动作 |
|---|---|---|---|
| `tools/`（24 文件） | 存档目录 | `tools/README.md:4`：「定位：**存档**，不是生产链路的一部分。任何 workflow 都不调用这些脚本。」 | 归档：移出 main 或接受噪音 |
| `tools/ledger_repairs_READONLY_ARCHIVE/`（5 文件） | 一次性账本修复脚本 | `tools/README.md:15-17`：「会**改写 CSV 账本**，历史上只运行过一次…**不要重跑**」；`git log` → `70b69132 chore(tools): isolate ledger repair scripts into READONLY_ARCHIVE`；`git grep` 在 `tests/`、`.github/` 中 **0 命中** | 归档（严禁重跑，保留为证据） |
| `scripts/`（2 文件） | 一次性验证脚本 | 由 `1d39f827 chore(archive): preserve sandbox scripts and tools before shutdown` 入库；`scripts/monday_check.sh:5` 自述为「周一 4 个时点」的一次性清单 | 归档 |
| `tools/experiment/results/`（5 文件） | 实验结论产物 | `tools/README.md:36`（标为「结论性结果」，`results.json` 1030 行） | 归档 |

> 注：`scripts/monday_check.sh` 本身**没有**硬编码路径 —— 它在 `:21` 用 `REPO="$(cd "$(dirname "$0")/.." && pwd)"` 自解析。只有 `scripts/README.md:23` 的示例值写着 `REPO="/tmp/us"`（并注明"改成你的本地仓库绝对路径"）。

### 1.2 临时实验遗留

| 路径 | 类别 | 证据 | 建议动作 |
|---|---|---|---|
| `_temp_experiment/`（4 文件） | 临时实验 | 由 `2db31d46 ci(temp): acceleration experiment on CI` 引入；**`tools/README.md:35` 自己写着**：「同名脚本曾作为 `_temp_experiment/` 提交（**该目录计划清理删除**）」；与 `tools/experiment/` 同名 4 脚本近似重复（逐文件 diff 仅 5–12 行，差异仅在输出目录与 `sys.path`） | **删除**（`tools/experiment/` 已是永久留存） |
| `.github/workflows/_temp-acceleration.yml` | 临时 workflow | 文件名 `_temp`；`2db31d46` 引入；`on:` 仅 `push`（paths 只有它自己）+ `workflow_dispatch` → **除手动外永不触发**。其引用的 `_temp_experiment/*.py` **确实存在**（见 §5.1 误报纠正） | 删除 |
| `.github/workflows/_temp-test-datasources.yml` | 临时探测 workflow | `16cb02e8 ci(temp): test F&G + FedWatch data sources`；触发条件同上；`15b015b6` 又补了一刀修 masking | 删除 |

### 1.3 旧版入口 / 重定向残留

| 路径 | 类别 | 证据 | 建议动作 |
|---|---|---|---|
| `us-market-terminal/index.html` | 重定向残留 | `:7` 注释「旧前端入口已废弃」、`:8` `<meta http-equiv="refresh" content="0; url=../">`、`:9` `window.location.replace('../')` | 删除整个目录 |
| `us-market-terminal/assets/app.js`、`assets/app.css` | 旧版前端 dead code | 比根版本少 **1161 行 / 249 行**；`app.js:16` 读相对路径 `dashboard/data/dashboard_data.json` → 指向自身目录下的旧副本；`dashboard-data.yml:166` 注释明写「已停止维护的旧前端」 | 删除 |
| `us-market-terminal/dashboard/data/dashboard_data.json` | 陈旧数据镜像（1.3 MB） | 与根版 diff = **37940 增 / 73912 删**；唯一读者 `index.html` 已跳转 | 删除 |

### 1.4 历史数据堆积 / 产物入库

| 路径 | 类别 | 证据 | 建议动作 |
|---|---|---|---|
| `us_stocks_pending_*.csv.processed` ×12（2026-09-17 → 10-08） | 历史堆积 | `review.yml:103-104` `git add us_stocks_pending_*.csv.processed`；`review.py:558-570` **只读 30 天内**的（`if name.endswith(".processed") and day < cutoff: continue`）；由 `review.py:588-589,688-689` 的 `os.rename` 生产。而 `git grep "os.remove\|unlink\|shutil.move" -- review.py scan.py dashboard_export.py` = **0 命中** → 超 30 天后永久失效但仍留在 git（当前最老 26 天，**尚未过期**，故非"垃圾"而是"无回收机制"） | 加保留/清理策略（P2） |
| `report.html`、`review_report.html`（57.7 KB） | 生成产物入库且永久陈旧 | `review.py:3806-3808` 每次运行重写两者；**任何 workflow 都不 `git add`**（仅 `review.yml:77` 作 artifact 上传）；最后提交分别 `f8ada23e (2026-08-05)`、`78a2f62a (2026-07-20)` → 仓库里那份已陈旧约 2 个月，且每次运行后被 stash 丢弃 | 取消跟踪 / 加 `.gitignore` |
| `scan_version.txt` | 运行时改写但从不提交 → 永久陈旧 | `scan.py:234-255` 每次运行重写；`scan.yml` 提交清单 `:83-132` **不含它**，`:143-152` 反把它列入"未纳入本次提交"并 `git stash` 丢弃；值冻结在 `22c2c009…,2026-08-04` | 见 §2.2（它被消费，属错误清单） |
| `dashboard/data/last_run.log`（4.6 KB） | 日志文件入库 | `dashboard-data.yml:120` 生成 + `:167` 明确 `git add`；内容含 `/home/runner/work/us/us`（`:4`、`:67`） | 有意提交，P2 |
| `quant_research_status.json` | CI 产物入库 | `quant-research.yml:65` 提交它；`:3` `"workdir": "/home/runner/work/us/us"` | 保留但去掉绝对路径（P2） |

### 1.5 docs 版本重叠

| 路径 | 类别 | 证据 | 建议动作 |
|---|---|---|---|
| 根目录 38 篇 `.md` | 版本重叠，**且完全不被索引覆盖** | 三套互不相干的编号并存：`FINAL_CHANGES.md:1`「US 最终修复版 **v6**」／`AI_ARCHITECTURE_V10.md` 与 `V10_CHANGELOG.md` **同一天（2026-09-18）都叫 V10 但主题不同**／`AI_ARCHITECTURE_V10` → `AI_ARCHITECTURE_V11_CLAWSOCKET` → `AI_ROUTING_V12` 同一天三次迭代；另有 `REVIEW_V29/V30/V31/V32/V34`、`SCAN_V37`、`TECHNICAL_DATE_FIX_V39`；`NAMEERROR_FIX.md` 与 `REVIEW_NAMEERROR_FIX.md` 同题两份 | 归档到 `docs/archive/`，只留最新 |
| `docs/` 内 39 篇被自家索引标为「已废弃」 | 版本重叠（自证） | `docs/DOCS_INDEX.md` 中 39 行状态=已废弃：`:65-72` 调度 6 篇互盖、`:210-214` 总览审计 5 篇互盖、`:115-117` 期权 3 份验收并存，`:228-239` 甚至专列「冲突文档清单」 | 按索引裁决归档 |
| `docs/` 另有大量"一次性 / 设计稿 / 未实施"文档 | 过期文档 | 逐篇读取头部取得证据，例如：`SCHEDULE_AUDIT_REPORT.md:14`、`SCAN_SCHEDULE_OBSERVATION.md:2`、`DEPLOYMENT_STATUS_FINAL.md:1`、`OPTIONS_RR_DEPLOYMENT_REPORT.md:1`、`RUNTIME_VALIDATION_REPORT.md:4`、`TONIGHT_CHECKLIST.md:3`、`NEWS_MODULE_DRAFT.md:4`、`PHASE4_8_TEST_REPORT.md:5`、`ACCELERATION_EXPERIMENT.md:3,12`、`SUCCESS_PATH_SIM.md:4`、`STOPPED_PANEL_REPORT.md:80`（引用仓库外 `/workspace/*.png`）等 | 统一归档 |
| `scan_ai_csv_fields.patch`、`scan_core_sync_fix.patch` | 一次性补丁，**内容已在代码里** | 实测：`scan_core_sync_fix.patch` 的「【封闭候选集】…」hunk 现存于 **`scan.py:2843`**（逐字一致）；`AI_industry_logic` → `scan.py:3618,3690`；`safe_vals` 加 `\r` → `scan.py:4115`；`parse_ai_score` → `scan.py:2984` | 删除 |

### 1.6 根目录死代码（均为"全仓库 0 引用"）

| 路径 | 类别 | 证据 | 建议动作 |
|---|---|---|---|
| `ai_router.py` | dead code | `git grep -nE "(import\|from) +ai_router" -- '*.py'` = **0 命中**，workflow 0 命中（仅文档提及）；`docs/FINAL_PRODUCTION_STABILITY_AUDIT.md:53,138`、`docs/ARCHITECTURE_AUDIT_REPORT.md:232` 已确认；它还 `import openai`（未安装，见 `docs/PYTHON_DEPENDENCY_REPRODUCIBILITY_AUDIT.md:48`） | 删除 |
| `tencent_scf_review_trigger.py` | 废弃的腾讯云 SCF 触发脚本 | 仓库内 0 引用；`docs/AUDIT_REPORT.md:35,118,230`「已废弃但未删除」；⚠️ `docs/FINAL_PRODUCTION_BASELINE.md:63` 指出**云侧定时器需人工确认停用** | 删除（先确认云函数下线）【待确认】 |
| `patch_v34.py`、`review_kpi_simplify_v25.py`、`review_kpi_tracking_fix.py` | 一次性补丁脚本 | 全仓库无 import/调用（仅 `docs/ARCHITECTURE_AUDIT_REPORT.md:305`、`README.md:3` 提及）；与 `README.md` 同源于 `be5026d4 (2026-09-16) Add files via upload` | 删除 |
| `clawsocket_probe.py` | 诊断脚本 | 0 引用（`scan.py:212-231` 自带 `_ai_preflight`） | 归档 / 删除 |
| `option_wheel.py:11` | 零调用点孤岛（生产侧） | 代码自述：「当前（2026-10-10）**没有任何调用点**（未接入 scan.py / review.py / dashboard_export.py）」；全仓库唯一 import 是 `tests/test_option_wheel.py:22` | 待确认（疑为设计预留）→ 移入 `tools/` 或删除 |

### 1.7 未消费配置

| 路径 | 类别 | 证据 | 建议动作 |
|---|---|---|---|
| `EMAIL_ACCOUNT` / `EMAIL_PASSWORD` / `TARGET_EMAILS`（9 处 env 声明） | 未消费密钥 | `scan.yml:40-42`、`review.yml:46-48`、`evolve.yml:51-53`；`git grep "EMAIL_ACCOUNT\|EMAIL_PASSWORD\|TARGET_EMAILS\|SMTP" -- scan.py review.py evolve.py portfolio_50000.py` = **0 命中** | 删除 env 声明 |
| `evolve.yml:47` `TUSHARE_TOKEN` | 未消费密钥 | `git grep -i tushare -- '*.py'` = **0 命中**（仅此一处 yml 声明） | 删除 |
| `requirements-dashboard.txt` | 遗留配置 | 内容仅 `yfinance>=0.2.40`（不锁上限，与 `requirements-production.txt` 的「>=已验证版本,<下个 major」策略矛盾）；`git grep -n requirements-dashboard -- '.github/*'` = **0 命中**（仅 4 篇 docs 提及）；`docs/FINAL_PRODUCTION_STABILITY_AUDIT.md:130` 已自标「已无 workflow 引用，遗留」 | 删除 |

---

## §2 【错误】清单

### 2.1 P0 — 影响正确性

| 路径 | 类别 | 证据 | 建议动作 |
|---|---|---|---|
| **`.github/workflows/evolve.yml:54`** | **`\|\| true` 掩盖关键错误（且文档谎称已修）** | 代码：`run: python evolve.py \|\| true`。`git log -S '\|\| true' -- .github/workflows/evolve.yml` **只命中 `39c5af5c (2026-06-04) Create evolve.yml`** → 自创建起就存在、**从未被移除**。但 `V10_CHANGELOG.md:22` 写「`evolve.yml` no longer hides failures with `\|\| true`」，`CLAWSOCKET_V13_CHANGELOG.md:31` 写「Evolve 不再使用 `\|\| true` 吞掉失败」→ **两处文档宣称的修复根本没有发生** | 去掉 `\|\| true`；同时改正两处 changelog |
| **`.github/workflows/quant-research.yml:26`** | **依赖缺失 → Phase 3 在 CI 必失败，但 workflow 恒绿并把 FAILED 状态提交进 main** | 代码：`pip install pandas numpy`（**无 scipy**）。反证在仓库里：`quant_research_status.json`（由 CI 于 `2026-10-13T09:16` 生成并提交）写着 `"overall_status": "FAILED"`、phase 3 `"status":"ERROR"`、`"reason":"异常: ModuleNotFoundError: No module named 'scipy'"`、phase 4/5/6 `NOT_ENOUGH_DATA`。而 `requirements-production.txt:20` 有 `scipy>=1.14,<2`，`:10` 注释明说「quant 相关性计算需要」。`quant_research_runner.py:191-193` 只在 `--strict` 时 `exit_code=1`，但 `quant-research.yml:40` **没传 `--strict`** → job 永远绿；`:65` 又把这个 FAILED 文件加进提交。文档侧自证：`docs/PYTHON_DEPENDENCY_PINNING_REPORT.md:97` 声称「**四个 workflow 统一引用** `requirements-production.txt`」，实测 7 个引用、**漏了这一个**，而同文 `:38/:75` 恰好记录过同类 scipy 事故 | 装 scipy（或直接 `-r requirements-production.txt`）+ 加 `--strict` |
| **`docs/HANDOVER.md:86`、`:132`** | **文档与代码不符，且照做会立刻制造配置不一致** | 文档把「回滚 review.yml:51 model → `claude-opus-5-5`」列为待办 P0/P1。实际 `review.yml:51` = `claude-fable-5-1`，且四个 workflow 已统一（`scan.yml:45`／`review.yml:51`／`evolve.yml:50`／`news-fetch.yml:41`），由 `3ed5a4bb feat(ai): switch default model to claude-fable-5-1 across all workflows` 有意统一；照 HANDOVER 执行会直接破坏该统一 | 删除该待办 |

### 2.2 P1 — 影响可维护性

| 路径 | 类别 | 证据 | 建议动作 |
|---|---|---|---|
| `dashboard_export.py:3046-3053` | 错误默认值（本地陷阱） | `:3051-3053` `frontend_out = SCRIPT_DIR/"us-market-terminal"/…`；`out_path = frontend_out if (SCRIPT_DIR/"us-market-terminal").is_dir() else …` → 裸跑写到**已废弃目录**；`:3024` help 文案仍在宣传该默认值；`:3049-3050` 注释说"默认直接写到前端目录"，与前端真实读取路径（`app.js:16` = `dashboard/data/dashboard_data.json`）矛盾。生产因 `dashboard-data.yml:112` 显式传 `--out` 而规避；`docs/DASHBOARD_DATA_STABILITY_REPORT.md:201` 已把它列为未修的 P2 | 默认值改为 `data_dir/dashboard/data/` |
| `clawsocket_compat.py:156` **vs** `:202` | **模型名不一致（同一文件两套兜底表）** | `:156` `defaults = ["claude-opus-4-6","claude-sonnet-4-5-20250929"] …`（静态兜底，由 `:220` 在 `_resolve_model` 内**真实调用**）；`:202` `defaults = ["claude-fable-5-1","gpt-6-astra"]`（运行时兜底）。`claude-opus-4-6` / `claude-sonnet-4-5-20250929` 在全仓库其它任何配置里都不出现 | 统一为当前模型表 |
| `clawsocket_probe.py:4` | 默认模型与全局不一致 | `requested = os.environ.get("GPT_MODEL") or "gpt-6-astra"`；其它全部入口默认 `claude-fable-5-1`（`scan.py:63`、`review.py:51`、`evolve.py:18`、`dashboard/fetch_news.py:62`、`ai_router.py:20-21`） | 统一，或直接删除该脚本 |
| `README.md`（全 13 行） | 文档与代码严重不符 | `:1`「# US Review KPI 修复」、`:3`「运行方式：在美股仓库根目录执行 `python review_kpi_tracking_fix.py`」—— **仓库 README 描述的是一个一次性补丁脚本**。README 与该脚本同源于 `be5026d4 (2026-09-16) Add files via upload`；真实入口是 `scan.py` / `review.py` / `evolve.py`（见 `scan.yml:49` 等） | 重写 README；删掉那个脚本 |
| `scan_version.txt`（被消费的陈旧值） | 配置/数据失真 | `scan.py:234-255` 每次 scan 重写它；`scan.yml:143-152` 把它 stash 丢弃 → 值永久冻结在 `22c2c009…,2026-08-04`；而 `dashboard_export.py:3359` **读它**并写进 `dashboard/data/dashboard_data.json:89561` 的 `scan_version` → **前端展示的扫描版本号永远是错的** | 修 workflow（提交它）或删字段 |
| `CLAWSOCKET_V13_CHANGELOG.md:30`、`CLAWSOCKET_V16_CHANGELOG.md:17` | 文档与代码不符 | 两处称「扫描时提交 `scan_version.txt`」／「scan workflow commits `scan_version.txt` as well as pending files」；实际 `scan.yml` 提交清单 `:83-132` 不含它，`:143-152` 明确把它排除并 stash | 修文档（或修 workflow） |
| **`docs/HANDOVER.md:320`、`:321`、`:322`** | **三条自检指令全部与现状相反** | `:320` `git ls-files \| grep _temp               # 应为空（清理后）` → 实际输出 **6 条**（`_temp_experiment/` ×4 + 2 个 `_temp-*.yml`）；`:321` `grep -n "CLAWSOCKET_LIVE_MODEL" .github/workflows/review.yml   # 应为 claude-opus-5-5` → 实际 `claude-fable-5-1`；`:322` `grep -n "upstream_model" clawsocket_compat.py   # 应无输出（debug 日志已删）` → 实际 **`clawsocket_compat.py:345` 有输出**，且是有意保留（`:346-347` 注释说明"记录中转站实际返回的模型…供 dashboard 展示"）。**照此自检会把正常状态误判为"没清理干净"进而误删/误改** | 修正三条指令 |
| `docs/DOCS_INDEX.md:215` | 文档治理锚点失真 | 它把 `FINAL_PRODUCTION_STABILITY_AUDIT.md` 定为「准绳」，而该文至少 6 处与代码冲突（见下一行） | 撤「准绳」或先修该文 |
| `docs/FINAL_PRODUCTION_STABILITY_AUDIT.md`（6 处） | 文档与代码不符 | 逐条实测：`:38` 称 scan 有 `schedule 7 13 * * 1-5` → 实际 `scan.yml:3-4` **无 cron**；`:40`/`:31` 称 evolve「周六 `0 2 * * 6`」→ 实际 `evolve.yml:7` `0 2 1 * *`；`:39`/`:41` 称 concurrency group 为 `us-stock-review`/`dashboard-data-refresh` → 实际两者均为 `us-stock-portfolio-ledger`（`review.yml:12`、`dashboard-data.yml:43`）；`:47` 「9 包」→ 实际 **11** 包；`:60` 守卫「三文件」→ 实际 `dashboard-data.yml:179/209` 是 **6 条路径**；`:127,139,169` 「9 个 tracked `.pyc`」→ 实际 **0**（`git ls-files \| grep .pyc` 空） | 修或删 |
| `docs/FINAL_PRODUCTION_STABILITY_AUDIT.md:169` | 文档与代码不符（另一处） | 「Quant 3-7 无 workflow 入口」→ `.github/workflows/quant-research.yml` 存在（103 行）且由 `scan.yml:200-202` 触发 | 修 |
| `docs/PYTHON_DEPENDENCY_PINNING_REPORT.md:97`、`docs/FINAL_PRODUCTION_STABILITY_AUDIT.md:47` | 计数错 | 称 `requirements-production.txt` 为「**9 包**」→ 实际 **11** 包（已加 `fear-greed>=0.1.2`、`cme-fedwatch>=0.2.1`） | 改 |
| **测试基线 4 个互相矛盾的数字** | 文档互相矛盾 | 实 grep：**152**（`PYTEST_STANDARDIZATION_REPORT.md:7,39,66`、`FINAL_PRODUCTION_STABILITY_AUDIT.md:18,112,151`、`PYTHON_DEPENDENCY_PINNING_REPORT.md:70`、`PYTHON_RUNTIME_CONSISTENCY_AUDIT.md:69`）／**271/271**（`DASHBOARD_DATA_STABILITY_REPORT.md:214`）／**465**（`HANDOVER.md:53,229,318`、`MODEL_DISPLAY_TASK.md:235`）；静态 `def test_` 计数 = **426**。叠加"无 CI 执行"（见下行）→ **任何"全量测试通过"的文档结论都不可作判据** | 建立单一基线并接入 CI |
| `.github/workflows/` 整体 | 测试无人执行 | `git grep pytest -- .github/` = **0 命中**；9 个 workflow 无一跑测试。而 `docs/HANDOVER.md:53,229,318` 把「465 passed」当作基线，`tools/README.md:48` 还自述本仓库没有 pytest 配置 → 基线**没有任何强制机制** | 加 CI test workflow（`python3.12` + `PYTHONUTF8=1`，见 `HANDOVER.md:120`） |
| `docs/STOPLOSS_ROOT_CAUSE.md:182` | **结论已被推翻（资金风险类）** | 文档写「ANET 现价 ~216 远高于 197.69 → 路径 B 事实上永远不会触发（惰性/失效）」；而 `docs/HANDOVER.md:176-179` 实测根因是 **`dec()` 不剥 `$`** → `dec("$197.69") is None` → `_run_intraday_stop` 直接 `continue`：**与价格无关，任何价格都不会触发**。该文是 3 篇未进 `DOCS_INDEX` 的文档之一 | 标注作废，避免误导止损处置 |
| `docs/MONDAY_VERIFICATION_PLAN.md:3`、`docs/WEEKEND_CHANGELOG.md:3` | 文档字段错误 | 两处都写「仓库：`us-market-terminal`」→ 真实仓库 `wijouyang-lab/us`（`git remote -v`）。`us-market-terminal` 只是目录名 | 修或归档 |
| `docs/EXTERNAL_TRIGGER_VERIFY.md:3`、`docs/DASHBOARD_PATH_INVESTIGATION.md` 通篇 | 过期文档 + 行号漂移 | `EXTERNAL_TRIGGER_VERIFY.md:3` 称「尚未删除 schedule」→ `scan.yml:3-4` 已无 cron；`DASHBOARD_PATH_INVESTIGATION.md` 把默认-out 回退记为 `dashboard_export.py:2759-2761`（实际 `:3051-3053`）、`:112` 称「`news-fetch.yml` cron 仍为 TBD」（实际 `news-fetch.yml:6-9` 已改为 `workflow_call`） | 归档 |
| `docs/FINAL_PRODUCTION_BASELINE.md:63` | 过期文档 | 「3 个 workflow 均保留 `workflow_dispatch`」→ `.github/workflows/` 实为 **9** 个 | 归档 |
| `docs/HANDOVER.md:120`、`docs/DOCS_INDEX.md:204` | 行号错 | 「`scan.py:2690` 含 f-string 反斜杠」→ 实际在 **`scan.py:2689`**（`:2690` 是 `仅输出：{{"decision"…}}`） | 改行号 |
| `docs/DOCS_INDEX.md:18`、`:206` | 计数错 | `:18` 标题「组合账本（**16 篇**）」实际 **17** 行；`:206` 标题「总览审计（**13 篇**）」实际 **15** 行（总数 130 仍正确） | 改计数 |
| `docs/HANDOVER.md:89,146,148,149` 等 | 行号漂移 | 如称 `_run_intraday_stop` 取值点在 `portfolio_50000.py:687`，实际 `stop = dec(p.get("Stop_Loss"))` 在 `:740`；`update_trade_history_trailing_stop` 记为 `:1426-1448`/调用 `:1878-1882`，实际 `:1427`/`:1447`/`:1883` | 逐条改（引用前先核） |
| `patch_v34.py:4`（另 `:264`、`:270`） | 硬编码绝对路径 | `review = Path('/mnt/data/v34/review.py')` —— 路径来自已消失的沙箱 | 删除（本就在死代码清单） |

### 2.3 P2 — 清理项

| 路径 | 类别 | 证据 | 建议动作 |
|---|---|---|---|
| `.github/workflows/_temp-test-datasources.yml:30` | 掩盖失败 | cme-fedwatch 步骤以 `" \|\| echo "FW_FAILED"` 结尾；同文件 `:16-22` 的 F&G 步骤已在 `15b015b6 fix(ci): … stop masking failure` 中去掉掩盖，此步仍吞 | 删除该 `_temp` workflow |
| `dashboard-data.yml:127` | `\|\| true` 掩盖 | `python dashboard/summarize_run.py … \|\| true` → 摘要产出失败静默 | 改为显式告警 |
| `review.yml:114` | `\|\| true` 掩盖 | `git rm -f us_stocks_pending_*.csv 2>/dev/null \|\| true` → 删除失败静默，下一轮可能重复入账 | 加显式判断 |
| `review.py:3807-3810` | 静默吞异常 | `Path(path).write_text(...)` 包在 `except Exception` 里只打印警告（配合 §1.4 的陈旧 HTML） | 至少上升为 warning |
| `tests/test_dashboard_data_stability.py:114-118` | try/except 吞异常 | `try: … abs(float(c)-float(s.get("rec_price")))<0.005 … except Exception: pass` → 非法价格被静默跳过，`:119-120` 的 C3 断言覆盖面可能被高估 | 在 except 中记录解析失败数 |
| `tests/test_quant_production.py:76,85,95,175,196`、`tests/test_quant_shadow.py:257`、`tests/test_quant_walk_forward.py:68,69,240` | `/tmp` 硬编码（可移植性） | 如 `walk_forward_gate("/tmp/nonexistent.json")`、`run_walk_forward(…, results_path="/tmp/r1.csv", summary_path="/tmp/s1.json")`；Windows 上 `/tmp/x` 落到当前盘根，通常不可写 | 改 `tmp_path` fixture（**是否真会写文件未实跑验证**）【待确认】 |
| `scan.yml:18,24` vs `dashboard-data.yml:65,68` | action 版本不一致 | `scan.yml` 用 `actions/checkout@v3` + `setup-python@v4`；`review.yml:30` 用 `setup-python@v4`；其余新 workflow 用 `@v4`/`@v5` | 统一到 v4/v5 |
| `evolve.yml:59-60,66,68` vs 其它 | git 流程不一致 | `git config --global` + `git add -A`（`:66`）+ 裸 `git push`（`:68`，无 fetch/rebase 重试），而 `dashboard-data.yml:165`、`review.yml:87`、`quant-research.yml:48` 都明令「绝不 `git add -A`」并带重试环 | 统一为局部 config + 白名单 add + 重试 |
| `skills/run_serenity.py:53` | 模型名不一致【待确认】 | `DEFAULT_MODEL = "claude-opus-5-5"`，`:385` 在无 `--model`/`SERENITY_MODEL` 时生效；`skill-weekly.yml:45-50` 未设该变量 → 该链路实际跑 opus-5-5，与全局 fable-5-1 不同 | 确认是否有意 |
| `tests/` 子进程依赖 | 未声明的 Node 依赖 | `tests/test_model_usage.py:165`、`test_market_indicators.py:282`、`test_fetch_news.py:357` 等 `subprocess.run(["node", …])`；仓库**无 `package.json`/`engines`**（`git ls-files` 仅 `.js`/`.cjs`） | 声明依赖或改为离线 fixture |
| `tests/conftest.py:16-27` | 测试可收集性问题 | 10 个"脚本式"测试被 `collect_ignore` 排除，改由 `test_script_runner.py` 用 subprocess 跑（`conftest.py:2-10` 自述「import 时触发 SystemExit 会导致 INTERNALERROR」） | 逐步改造为函数式（P2） |

---

## §3 优先级排序

### P0（影响正确性，必须修）

1. `evolve.yml:54` `|| true` 吞掉 Evolve 全部失败 —— 且两处 changelog 谎称已修（`V10_CHANGELOG.md:22`、`CLAWSOCKET_V13_CHANGELOG.md:31`）。
2. `quant-research.yml:26` 缺 scipy → Phase 3-6 在 CI 全废、job 恒绿、FAILED 状态还被提交进 main（`quant_research_status.json`；`quant_research_runner.py:191-193`；文档侧 `PYTHON_DEPENDENCY_PINNING_REPORT.md:97` 的"已统一"声明是假的）。
3. `docs/HANDOVER.md:86,132` 的"回滚模型"待办 —— 文档与代码相反，照做即破坏 `3ed5a4bb` 的全局统一。

### P1（影响可维护性，尽快修）

4. `docs/HANDOVER.md:320-322` 三条自检指令全部与现状相反（会误导后续会话做错误的"清理"与"回滚"）。
5. `docs/DOCS_INDEX.md:215` 把已失真的 `FINAL_PRODUCTION_STABILITY_AUDIT.md` 定为「准绳」—— 文档治理锚点自身坏了。
6. `dashboard_export.py:3046-3053` 默认输出仍指向废弃前端目录。
7. `scan_version.txt` 被消费却永久陈旧 → 前端版本号长期错误。
8. `clawsocket_compat.py:156` vs `:202` 两套兜底模型表 + `clawsocket_probe.py:4` 默认值不一致。
9. `README.md` 描述一个一次性补丁脚本。
10. 无 CI 测试任务，且测试基线 4 值互相矛盾（152 / 271 / 465 / 静态 426）。
11. 文档与代码不符的其余硬伤：`scan_version` 提交声明、错误仓库名 ×2、`FINAL_PRODUCTION_STABILITY_AUDIT.md` 6 处、`STOPLOSS_ROOT_CAUSE.md:182` 被推翻的止损根因。

### P2（清理项，有空再动）

12. 删除 `_temp_experiment/` + 2 个 `_temp-*.yml`（含 `tools/README.md:35` 自述"计划清理"）。
13. 删除 `us-market-terminal/` 整目录（4 文件，含 1.3 MB 陈旧镜像）。
14. 根目录 38 篇版本重叠 `.md` 归档 + `docs/` 约 40 篇已废弃文档归档。
15. 12 个 `.csv.processed` 加保留策略；`report.html` / `review_report.html` 移出 git。
16. 删除死代码（`ai_router.py`、`patch_v34.py`、`review_kpi_*.py`、`clawsocket_probe.py`、`option_wheel.py` 待确认）+ `.patch` ×2 + `requirements-dashboard.txt`。
17. 删除 10 处未消费 secrets 声明（`EMAIL_*` ×9、`TUSHARE_TOKEN`）。
18. `_temp-test-datasources.yml:30`、`dashboard-data.yml:127`、`review.yml:114` 的 `|| true`；action 版本与 git 流程统一；tests 内 `/tmp` 与 `except: pass`。

---

## §4 已核对干净的项

- **无 workflow 引用不存在的文件**：逐个核对 9 个 workflow 的 `run:` / `uses:` 目标 —— `scan.py`、`review.py`、`evolve.py`、`portfolio_50000.py`、`quant_factor_price.py`、`quant_research_runner.py`、`dashboard_export.py`、`dashboard/fetch_news.py`、`dashboard/fetch_runtimes.py`、`dashboard/fetch_market_indicators.py`、`dashboard/summarize_run.py`、`skills/run_serenity.py`、`_temp_experiment/*.py`、`.github/workflows/news-fetch.yml`、`quant-research.yml` **全部存在**；`quant-research.yml:51-65` 与 `scan.yml:83-132` 的 add 清单全部有 `-f` / `ls` 守卫。
- **`portfolio_50000_target.csv` 与 `dashboard/data/runtimes.json` 的"缺失"属预期**：前者由 scan 在 `ENABLE_TARGET_FILE=1` 时产出（`portfolio_target.py:198`），后者由 `dashboard-data.yml:84` 在**使用前**生成（`:119` 消费），且都不在提交清单里 —— **不是悬空引用**。
- **`|| true` 全仓库只有 6 处**（见 §2），其中 `scan.yml:152,173,177`、`review.yml:156,160`、`skill-weekly.yml:74` 属**有意为之**且注释解释了原因（rebase abort / stash），不算缺陷。
- **10 个脚本式测试全部会正确失败**：`tests/conftest.py:16-27` 列出的 10 个 SCRIPT_TESTS，尾部一律以非 0 退出（2 个 `sys.exit(0 if passed == total else 1)`，8 个 `raise SystemExit(1)`），`test_script_runner.py:28` 的 `assert r.returncode == 0` 判定有效。
- **无 skip / xfail**：`git grep "pytest.mark.skip\|xfail" -- tests/` = 0。
- **无字节级重复文件**：对全部 358 个文件做 `git hash-object` 两两比对，**0 组重复**（`_temp_experiment` 与 `tools/experiment` 是近似重复而非复制）。
- **文档引用的 commit 全部真实存在**：`3edd7bb4`、`cf52915f`、`0b55de72`、`27d004e6`、`89eedaa`、`be5026d4`、`1d39f827`、`78a38493`、`3ed5a4bb` —— `git cat-file -t` 全为 `commit`。
- **`tracked .pyc` = 0**（`FINAL_PRODUCTION_STABILITY_AUDIT.md:169` 的说法已过期；`e6456aba (2026-10-09) chore: untrack __pycache__ bytecode` 已清理）。
- **`docs/` 内没有文档声称 `|| true` 已被移除**（`grep "\|\| true" -- docs/` = 0 命中）；说谎的两篇在**仓库根**（`V10_CHANGELOG.md`、`CLAWSOCKET_V13_CHANGELOG.md`）。
- **`.gitignore` 覆盖了真正的密钥**：`.env` / `.env.local` / `__pycache__` / `news_translation_cache.json`；`.env.example:1-4` 只含占位 key，且有实际用途（`dashboard/fetch_news.py` 用 `FINNHUB_API_KEY`）。
- **生产入口的第三方 import 与 `requirements-production.txt` 完全对齐**：逐文件扫描 workflow 会调用的 25 个脚本，`anthropic` / `cme_fedwatch` / `fear_greed` / `numpy` / `pandas` / `pandas_ta` / `requests` / `yfinance` 全部在 requirements 中（**唯一缺口就是 §2.1 的 scipy**）。
- **根目录 ledger/状态类 CSV/JSON 均为"有意入库的运行数据"**，各有真实写者+读者：`portfolio_50000_{meta.json,positions,transactions,history}.csv`（`portfolio_50000.py:52-55`）、`trade_history.csv`、`review_history.csv`、`option_strategies.csv`、`quant_factor_{snapshot,backtest,summary,price_history}.csv`、`quant_production_state.json`、`ai_snapshot.csv`/`ai_text_cache.csv`（`dashboard_export.py:101,105,796,831` 只读）、`macro_data.json`、`strategy_evolution.json`/`evolved_rules.json`（`evolve.py:21-22` 写、`scan.py:2475-2477` 读）。
- **`dashboard/data/last_run.log` 是有意提交**（`dashboard-data.yml:120` 生成 + `:167` 明确 add）。
- **`docs/DOCS_INDEX.md:245` 的核验正确**：「`scan.yml` 只有 `workflow_dispatch`，无 cron」与 `scan.yml:3-4` 一致；`:246,192`「`_us_session.py` 不存在」、`:247`「`app.js` 无 `renderIntradaySpark`」亦经复核为真。
- **活模块导入链完好**：`scan_us_option_engine`(`scan.py:45`)、`quant_filter`(`scan.py:55`)、`portfolio_target`(`scan.py:3856`)、`trade_history_quality`(`review.py:35`)、quant 7 模块、`clawsocket_compat`。
- **`us-market-terminal/` 未被任何文档声称已删除**，且 `dashboard_export.py:3034-3039,3416` 与 `dashboard-data.yml:165-170` 的"已隔离、不写入、不提交"描述与代码一致（问题只在于 §2.2 的**默认值**仍然指向它）。

---

## §5 待确认 / 覆盖说明

### 5.1 已剔除的误报（重要）

复查过程中有两处**推断被实测推翻**，已从清单中剔除，记录于此以免后人重复踩坑：

| 曾被提出的结论 | 实测 | 结论 |
|---|---|---|
| 「`_temp_experiment/` 目录**已不存在** → `.github/workflows/_temp-acceleration.yml:22-31` 是悬空引用，一旦触发必失败」 | `git ls-files "_temp_experiment/*"` = **4 个文件**；`Get-ChildItem _temp_experiment -File` 实列 4 个实体（3332 / 3237 / 1710 / 6132 字节）；其中 2 个被直接读取过 | ❌ **误报**。该 workflow 的引用**有效**；它仍属 §1.2 的"临时实验遗留"，但理由**不是**悬空引用 |
| 「`tests/test_review_dashboard_fields.py:219-226` 与 `tests/test_options_reward_risk.py:335-342` 失败仍退 0（无 `else` 分支、无 `sys.exit(1)`），`test_script_runner.py` 只判 `returncode == 0` → 失败会被判 PASS」 | 两个文件**都有** `else: … sys.exit(1)`；进一步把 10 个 SCRIPT_TESTS 的尾部全部查了一遍，**全部会非 0 退出** | ❌ **误报**。此点为 §4 的 CLEAN 项 |

### 5.2 待确认清单

| 项 | 为什么无法确认 |
|---|---|
| `465 passed` 基线真伪、以及是否存在"断言旧行为"的更深层不一致 | **本次未执行任何测试**：运行 pytest 会在仓库内产生 `__pycache__` / `.pytest_cache`，违反只读约束；一次 `pytest --collect-only` 尝试因环境（Python 版本 / 缺 pandas）挂起后被终止。现有最强静态证据：`def test_` 计数 426、10 个 subprocess 脚本、实测全部正确退码 |
| `tencent_scf_review_trigger.py` 是否仍在腾讯云侧运行 | 仓库内 0 引用可证，云侧无法从仓库验证；`docs/FINAL_PRODUCTION_BASELINE.md:63` 亦提示需人工确认 |
| 仓库 Settings 里 vars 的实际取值（`ENABLE_SCAN_BUY_DECISION`、`ENABLE_MACRO_PANEL`、`ENABLE_MARKET_INDICATORS`、`ENABLE_SKILL_SERENITY`、`ENABLE_TARGET_FILE` 等） | 无法从仓库读取；`docs/DOCS_INDEX.md:152` 同样标了「flag 值未知」 |
| `option_wheel.py` 是否属设计预留 | 代码自述"没有任何调用点"，但存在 `tests/test_option_wheel.py`，无法判断是预留还是废弃 |
| `skills/run_serenity.py:53` 用 `claude-opus-5-5` 是否有意 | 与全局 `claude-fable-5-1` 不一致，但该链路独立，疑似有意为之 |
| `tests/test_quant_walk_forward.py:69` 的 `/tmp/r1.csv` 是否真的写入 | 输入路径不存在时应提前返回；未实跑，无法确认 |
| 各 docs 中引用的行号是否**全部**正确 | 只抽样核对了与结论强相关的行号（如 `scan.py:2689`、`portfolio_50000.py:740`、`clawsocket_compat.py:345`），未做全量行号校验 |

### 5.3 覆盖度

- **已覆盖**：全部 358 个被跟踪文件；9 个 workflow 逐行读完；`dashboard_export.py`、`scan.py`、`review.py`、`evolve.py`、`clawsocket_compat.py` 等关键源码的相关区段实读；`docs/` 134 篇逐篇读取头部并按主题分组，其中约 63 篇读取正文抽样；`tests/` 50 个文件的收集/退码/硬编码路径全量 grep；根目录全部非 `.md` 文件核对了写者与读者。
- **未覆盖**：
  - 未执行任何测试（见 5.2 第一条）。
  - 未做"每个 `.py` 文件完整通读"级别的代码审计 —— 复查聚焦「多余」与「错误配置」两类，未做逻辑正确性审计。
  - 未读远程仓库（本机未挂 GitHub MCP）；本地 `HEAD == origin/main`，结论等价，但**不含** GitHub 侧设置（Actions secrets/vars、Pages 配置、分支保护）。
- **复查方法**：`git ls-files` 全量清单 → 按目录/扩展名统计 → 对 7 个重点目录逐项审查 → 用 `git log -S` / `-G` 追溯配置变更历史 → 对每条结论做「代码 ↔ 文档 ↔ commit」三方交叉验证。所有结论均带行号、原文引用或 commit SHA。
