# 判决后操作清单 SOP（POST_VERDICT_SOP）

> 判决前仅 commit，未 push / 未 rebase / 未跑 scan / 未碰监控 PID 536931 / 未碰 us-market-terminal/。
> 本 SOP 在判决结果出来后执行。**执行前必须逐项复核第四部分的前置检查。**

---

## 第一部分：读取判决

```bash
cat /tmp/scan_1008_monitor.log | tail -30
```

**四选一判定**：

| 判定 | 含义 | 后续动作 |
|---|---|---|
| **OK** | 契约兑现、无告警 | 走分支 A（push） |
| **SYSTEMATIC** | 存在系统性偏差但已定性 | 走分支 A（push，可加说明） |
| **DEEPER** | 需深入调查 | 走分支 B（不 push） |
| **OTHER** | 其他异常 | 走分支 B（不 push） |

**报告四项数字**：
1. T 实际值（Technical_Date 契约观测值）
2. price history 最新日期
3. 相差天数
4. 告警是否触发（`STALE` / `OK`）

---

## 第二部分：分支 A（OK / SYSTEMATIC）push 清单

### 2.1 push 三连（按顺序，不可跳步）

```bash
cd /tmp/us

# 1. 判决后首次 fetch（拉取 origin/main 最新，含 dashboard 累积提交）
git fetch origin

# 2. rebase 到 origin/main（保留本地 commit 线性历史）
git rebase origin/main

# 3. 一次性 push 全部本地 commit
git push origin main
```

> rebase 若冲突：以本仓库真实逻辑为准，绝不覆盖已推送内容；冲突无法当场解决则停下报告。

### 2.2 push 后配置（新闻模块上线，与路径调查结论一致）

```bash
# 1. 配 Secret（GitHub 网页操作，非 CLI）
#    GitHub → Settings → Secrets and variables → Actions → New repository secret
#    Name:  FINNHUB_API_KEY
#    Value: <.env 里的真实 key>
#    注意：配完先自检 —— 网页上 key 不能出现在任何公开日志/commit 里

# 2. 填 news-fetch.yml cron（本地改文件 → commit → push）
#    .github/workflows/news-fetch.yml 第 9 行 cron 改为：'23 */2 * * 1-5'

# 3. 手动 dispatch news-fetch 一次（首次不等 2 小时定时）
#    GitHub → Actions → news-fetch → Run workflow → Run workflow

# 4. 等 dashboard-data 工作流注入 news（news_data.json 生成后自动跑）

# 5. 验证（替换 <pages-url> 为实际 Pages 地址）
curl -s <pages-url>/dashboard/data/dashboard_data.json | python3 -c "import json,sys; d=json.load(sys.stdin); n=d.get('news'); print('news 存在:', n is not None); print('market_news:', len(n.get('market_news',[])) if n else 0)"
```

---

## 第三部分：分支 B（DEEPER / OTHER）

- **全部不 push**（本地 commit 保持未推送状态）。
- 停下，报告判定结果 + 四项数字 + 建议下一步调查方向。
- **等用户指令**，不自作主张 rebase/push。

---

## 第四部分：push 前的最终检查（每次 push 前复核）

| # | 检查项 | 命令 | 期望 |
|---|---|---|---|
| 1 | 工作区干净 | `git status -s` | 空 |
| 2 | 全量测试 | `python3.12 -m pytest tests/ -q` | 217 passed |
| 3 | 历史无真实 key | `git log --all -p \| grep -c "d6g0419r01qqnmbq8rj"` | 0 |
| 4 | .env 未被跟踪 | `git ls-files \| grep "\.env"` | 无输出 |
| 5 | 未碰 us-market-terminal | `git status -s us-market-terminal/` | 空 |
| 6 | 监控仍存活 | `ps -p 108842` | ✅ 已于 10-08 15:18 北京重启，新 PID=108842（脚本 /tmp/monitor_scan_1008.py，日志 /tmp/scan_1008_monitor.log，基线 origin/main=5130514743be） |

---

## 第五部分：监控失效 fallback（若重启后监控再次停止）

**触发条件**：判决时（10-08 13:07 UTC）监控日志无新内容，即 `tail -1 /tmp/scan_1008_monitor.log` 的时间戳 < 10-08 13:00 UTC。

**手动四选一判定（不依赖旧日志，直接读远端）**：

```bash
cd /tmp/us
git fetch origin
git log origin/main --oneline -10          # 找 10-08 的 scan 提交（subject 含 scan/quant）

# 读 10-08 那批 snapshot 的 Technical_Date（取 Scan_Date=2026-10-08 的行）
git show origin/main:quant_factor_snapshot.csv \
  | python3 -c "import csv,sys; rows=[r for r in csv.DictReader(sys.stdin) if r.get('Scan_Date')=='2026-10-08']; print('Scan_Date=2026-10-08 行数:', len(rows)); print('Technical_Date:', sorted({r.get('Technical_Date') for r in rows}))"

# 读 price history 最新日期
git show origin/main:quant_factor_price_history.csv \
  | python3 -c "import csv,sys; d=sorted({r.get('Date') for r in csv.DictReader(sys.stdin) if r.get('Date')}); print('price history 最新:', d[-1] if d else None)"

# 对比 → 四选一
#   Technical_Date = 2026-10-07 → OK
#   Technical_Date = 2026-10-06 → SYSTEMATIC
#   Technical_Date = 2026-10-05 → DEEPER
#   其它                       → OTHER
```

> 判定口径与原监控脚本 `monitor_scan_1008.py` 的 `analyze()` 一致。

---

## 附：本轮已完成的两个 commit（待 push）

| SHA | message | 文件 |
|---|---|---|
| `da6e82b` | feat(quant): extract scan strict-filter to quant_filter module | quant_filter.py, tests/test_quant_filter.py |
| `0856291` | feat(scan): redefine core as positions + strict candidates | scan.py, .github/workflows/evolve.yml, dashboard_export.py |

> 这两个 commit 在分支 A 的 `git push origin main` 中随全部本地 commit 一次性推送；分支 B 则保持未推送。
