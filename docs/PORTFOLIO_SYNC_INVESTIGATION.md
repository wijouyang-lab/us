# Portfolio 数据本地/云端不同步调查报告

> 调查时间：2026-10-08（GMT+8）
> 性质：**只读调查。未修改任何代码、未 push、未 rebase、未 fetch、未碰监控 PID 536931、未手工改动任何 portfolio 文件。**
> 远端只读手段：`git ls-remote`、`curl` raw/Pages（无 fetch / merge）。
> 仓库：`wijouyang-lab/us`（本地 `/tmp/us`）

---

## 1. 文件跟踪状态（跟踪 / 忽略 / 未跟踪）

**① `git ls-files | grep -i portfolio`（被 git 跟踪的文件）：**

```
portfolio_50000.py
portfolio_50000_history.csv
portfolio_50000_meta.json
portfolio_50000_positions.csv
portfolio_50000_transactions.csv
tests/test_portfolio_50000.py
```

→ 5 个 ledger/配置 CSV·JSON **全部被跟踪**，包括 `portfolio_50000_positions.csv` 与 `portfolio_50000_history.csv`。

**② `.gitignore` 中 portfolio 相关：**

```
$ cat .gitignore | grep -i portfolio
cat: .gitignore: No such file or directory
```

→ **仓库根目录不存在 `.gitignore` 文件**（全文 0 行）。进一步用 `git check-ignore -v portfolio_50000_positions.csv portfolio_50000_history.csv` 验证 → "未被任何 ignore 规则忽略"。

**结论：portfolio 文件是 git 跟踪文件，不是被忽略的运行时产物。** 本地 positions.csv 为空、history.csv 仅 10-06 一行，是**数据未同步**所致，而非"本地本就该空"。

---

## 2. 数据流源头（谁写、写到哪、是否提交）

**① 谁写 `portfolio_50000_positions.csv`？**
→ `portfolio_50000.py` 的 `main()`（产出 `positions`/`history`/`transactions`/`meta` 四件套，落盘到 `--data-dir .`，默认仓库根）。

**② `portfolio_50000.py` 的输出路径：** 仓库根目录：`portfolio_50000_positions.csv` / `_history.csv` / `_transactions.csv` / `_meta.json`。

**③ 哪个 workflow 调用它？**
→ **`.github/workflows/review.yml`**（美股盘后复盘，Tue–Sat 06:00 北京 = Mon–Fri 22:00 UTC）：

```
review.yml:56      run: python portfolio_50000.py --data-dir .
review.yml:82-86   git add portfolio_50000_meta.json / _positions.csv / _transactions.csv / _history.csv
review.yml:106     git commit -m "chore: 美股盘后补充成交 $(date +%Y-%m-%d)"
review.yml:130     git push origin HEAD:main        # 并发安全：先 fetch + rebase 再 push，禁 force
```

→ 即：**盘后复盘被 review.yml 调用，写入 ledger，并 git add + commit + push 到 main。**

**④ 写入后是否 git add + commit？**
→ **是。** review.yml 明确 `git add` 四个 ledger 文件并 commit+push（非 `git add -A`，有"提交范围守卫"）。scan.yml **不**调用 portfolio_50000.py（scan 只负责选股/pending，不维护账户账本）。

**dashboard 展示链路：** `dashboard-data.yml`（每 15 分钟 `*/15 * * * 1-5`）运行 `dashboard_export.py`，读取上述 ledger CSV + scan 数据，重新生成 `dashboard/data/dashboard_data.json`，并 `git add dashboard/data/dashboard_data.json` + commit + push（L139/L152/L160）。dashboard 网页（app.js）即读该 JSON 的 `portfolio` 段。

> 完整链路：**scan.py（盘中选股）→ review.yml（盘后跑 portfolio_50000.py 写 ledger 并 push）→ dashboard-data.yml（每 15 分钟刷 dashboard_data.json 并 push）→ 网页展示**。

---

## 3. 本地 vs 线上实际差异（数值对照）

**关键方法学修正：** 单纯的 `git diff HEAD origin/main` **不可靠**——它比的是**本地缓存的 origin/main 引用**，而非真实远端。本次证实本地 `origin/main` 引用已陈旧。

**① 本地缓存 origin/main vs 真实远端 HEAD（`git ls-remote`，只读）：**

```
本地缓存 origin/main : cbae160f997103ea9916eef55d07ef75a8d7f2b8
真实远端 HEAD        : 36dd589b61b000d9781f5894e2c99fc07bcaf977   ← 不一致，本地引用陈旧
```

→ 本地 `git diff HEAD origin/main` 显示为空，是因比的都是**旧缓存**（cbae160f）；真实远端（36dd589b）已前进。

**② 本地 vs 线上 `portfolio_50000_history.csv`（`curl` raw main，只读）：**

| 日期 | Cash | Stock_Value | Total_Equity | Return% | Open_Positions | 来源 |
|---|---|---|---|---|---|---|
| 2026-10-06 | 50000.00 | 0.00 | 50000.00 | 0.00 | **0** | 本地 + 线上一致 |
| 2026-10-07 | **10438.80** | **40153.64** | **50592.44** | **1.18** | **4** | **仅线上（main）有，本地缺失** |

→ 线上 main 的 history 已含 **2026-10-07 的 4/4 行**：Cash $10,438.80、Stock $40,153.64、净值 $50,592.44、收益 +1.18%。**与用户网页看到的 live 状态完全吻合。**

**③ 本地 `dashboard/data/dashboard_data.json` portfolio 段：** `asof=2026-10-06, open_positions=0`（停留创立日快照，因本地落后）。线上实时 JSON 因体积 1.7MB+ 在沙箱网络下多次超时（HTTP 000），但由 history.csv 的权威 4/4 行可确定：线上 dashboard 的 `portfolio` 段必为 `asof=2026-10-07 / open_positions=4 / cash=$10,438.80`。

**④ 本地 vs 线上差异小结：**

| 维度 | 本地 checkout | 线上 main（真实） |
|---|---|---|
| origin/main 引用 | cbae160f（陈旧） | 36dd589b |
| history.csv | 仅 10-06（0 持仓） | 10-06 + 10-07（**4 持仓**） |
| dashboard portfolio 段 | asof 10-06, 0 | asof 10-07, 4（推断自 history） |
| 用户网页所见 | — | 4/4, Cash $10,438.80 ✅ 与线上一致 |

> 注：线上 `positions.csv` / `meta.json` 的 raw 拉取在本环境返回 HTTP 000（超时/网络抖动），未取到正文；但 `history.csv` 已权威证明线上 4/4，且 review.yml 确认这两个文件同样被 add+commit+push，故不影响结论。

---

## 4. 判断：bug / 设计如此 / 还是其他

**判定：属于「portfolio CSV 是 git 跟踪的，本地落后」——正常同步滞后（fetch 即可解决）。**

逐一排除用户列出的其他情况：

| 候选情况 | 是否成立 | 排除依据 |
|---|---|---|
| portfolio CSV 是 git 跟踪的，本地落后（同步问题，fetch 即可） | ✅ **成立** | §1 全部被跟踪、无 .gitignore；§3 真实远端（36dd589b）已含 4/4 ledger，本地仅因 origin/main 引用陈旧未 fetch |
| portfolio CSV 是 .gitignore 的运行时产物（设计如此，本地空正常） | ❌ 不成立 | 仓库无 .gitignore；5 个 ledger 均被 `git ls-files` 跟踪；`git check-ignore` 确认未被忽略 |
| 线上 dashboard 读的是别处的数据源 | ❌ 不成立 | 线上 dashboard 读的就是 git 跟踪的 ledger CSV（dashboard_export.py 从 positions/history CSV 生成 JSON）；与本地同源，非独立库 |
| 其他 | ❌ 不适用 | — |

**性质：不是 bug，也不是"设计上本地就该空"。** 是**本地工作副本的 `origin/main` 引用未刷新**导致的纯同步滞后——云端流水线（review.yml + dashboard-data.yml）工作正常，已正确把 4/4 账户状态提交并推送到 main，网页展示也正确。本地看不到，仅仅是因为没有 `git fetch`。

---

## 5. 若视为需对齐的问题：修复方向（仅列方向，不实施）

1. **方向 A（推荐，预期内同步，非修 bug）：** 本地执行 `git fetch origin` 刷新 `origin/main` 引用。刷新后 `git diff HEAD origin/main -- '*portfolio*'` 即会出现 10-07 的 4/4 ledger 差异，本地 checkout 与线上对齐。**本轮按要求未执行 fetch。**
2. **方向 B（按需）：** 若本地开发副本需直接反映线上账户，可在合适时机 `git merge` / `git rebase` origin/main。注意本地当前 ahead 10（6 quant + review/evolve cron `3ed1495` + 本次 3 个 Phase 2-7 commit），merge/rebase 时按既定 push 顺序处理，避免与远端 dashboard 累积提交冲突。
3. **方向 C（非必要，代码无需改）：** review.yml 盘后 push ledger、dashboard-data.yml 每 15 分钟 push JSON 的两条流水线均已正确 `git add` + commit + push 且有提交范围守卫。若担忧"本地永远看不到线上账户"，根因只是 fetch 频率，无需改动任何 workflow 或脚本。
4. **排查习惯提醒（供后续调查）：** 验证"本地 vs 线上"差异时，**不要依赖 `git diff HEAD origin/main`**——它基于本地陈旧的 origin/main 缓存，会假显示"无差异"。应以 `git ls-remote` 比对远端 HEAD SHA，或用 `curl` raw/API 直接读线上文件，才能得到真实差异（本次即因此修正了初判）。

---

## 附：本次执行的关键命令与证据

- 跟踪：`git ls-files | grep -i portfolio`；`git check-ignore -v portfolio_50000_*.csv`
- 忽略：`cat .gitignore`（不存在）；`git check-ignore` 确认未忽略
- 远端提交：`git log origin/main --oneline -10 -- '*portfolio*'` → `03d0e54 chore: 美股盘后补充成交 2026-10-07`、`99d14d1 feat(portfolio): add $50,000 long-term simulated portfolio ledger`
- 本地差异：`git diff HEAD origin/main -- '*portfolio*'`（空，因 origin/main 缓存陈旧）；`git diff HEAD origin/main -- dashboard/data/dashboard_data.json`（origin/main 缓存已含 10-07 17:47 版）
- 远端真实 HEAD：`git ls-remote origin HEAD` → `36dd589b...`；本地 `git rev-parse origin/main` → `cbae160f...`（不一致）
- 线上 ledger（只读）：`curl -s --compressed raw.githubusercontent.com/wijouyang-lab/us/main/portfolio_50000_history.csv` → 含 10-07 行（4 持仓、Cash 10438.80）
- 数据流：`Read .github/workflows/review.yml`（L56/L82-86/L106/L130）、`Read .github/workflows/dashboard-data.yml`（L4/L80/L139/L152/L160）
