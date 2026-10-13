# tools/ — 归档工具与一次性资产

> 归档日期：2026-10-13 · 来源：沙箱 `/workspace` 与 `/tmp`，停用前抢救性入库
> 定位：**存档**，不是生产链路的一部分。任何 workflow 都不调用这些脚本。

## ⚠️ 使用前必读

1. **硬编码路径**：绝大多数脚本写死了沙箱路径 `/tmp/us`（仓库根）和 `/workspace`（输出目录）。
   换机器运行前请先全局替换这两处，否则会读不到数据或把结果写到不存在的目录。
   ```bash
   grep -rn "/tmp/us\|/workspace" tools/          # 先看命中
   sed -i 's#/tmp/us#<你的仓库根>#g' <script>      # 再替换
   ```
2. **只读性**：以每个脚本自己的 `README`/头部注释为准（多数为只读，修复类除外）。
3. **修复类脚本有破坏性**：`tools/repair/` 下的 `*_repair.py` 会**改写 CSV 账本**，历史上只运行过一次。
   **不要重跑**，仅作为「当时怎么修的」证据保留。务必先备份 `trade_history.csv` 等账本文件再考虑复现。
4. **不参与 pytest**：文件名已避开 pytest 默认采集模式（`test_*.py` / `*_test.py`）。
   注：`tools/quant/probe_night_session.py` 原名 `night_session_test.py`，为规避 pytest 采集在归档时**已重命名**（内容未改）。

---

## 目录说明

| 子目录 | 内容 | 关联文档 / 任务 |
|--------|------|----------------|
| `repair/` | Stop_Loss 历史修复、event key / orphan 修复、Rec_Price 修复、trade_history 去重清理 | 对应 `#78–#82`、`P0.5_stop_loss_repair_report.md` |
| `backfill/` | OHLCV 历史补采三版（`ohlc` → `ohlc_batch` → `ohlc_stooq`，后者最新） | `docs/OHLCV_BACKFILL_REPORT.md` |
| `quant/` | Quant Phase 1 验证；Yahoo 夜盘数据覆盖实测 | `docs/PHASE1_FIRST_REAL_DATA_REPORT.md`、`docs/YAHOO_NIGHT_SESSION_TEST.md` |
| `experiment/` | 技术因子 OOS 加速实验脚本 + `results/` 摘要结果 | `docs/ACCELERATION_EXPERIMENT.md` |
| `sim/` | 周一演练、意外成功全链路模拟、dashboard 并发冲突模拟 | `docs/SUCCESS_PATH_SIM.md`、`docs/DASHBOARD_DATA_STABILITY_REPORT.md` |

### 关于 `experiment/`

- 同名脚本曾作为 `_temp_experiment/` 提交（该目录计划清理删除），**本目录是它们的永久留存**。
- `results/` 保留了实验**结论性结果**：`report.json`（总览）、`results.json`、`summary.csv`、`correlation.csv`、`validation.csv`。
- 未搬运的大体积中间产物：`history.csv`(222KB)、`snapshot.csv`(376KB)、`backtest.csv`(478KB) —— 属于可再生成的原始数据，体量大而复用低。

---

## 刻意**未**搬运的内容（及原因）

| 类别 | 例子 | 不搬原因 |
|------|------|---------|
| 截图 PNG / HTML | `DASHBOARD_PREVIEW_*.png`、`preview/`、`线上验证_*.png` | 非脚本；UI 快照已过期，且多为已被取代的界面状态 |
| 旧版界面目录 | `/workspace/preview/`、`/workspace/us-review-dashboard-linkage/` | 内含陈旧 `app.js`/`index.html` 副本，与当前仓库版本重复且易误用 |
| `__pycache__/` | `.pyc` | 无价值产物 |
| `test_*.py`（7 个） | `test_backfill_integration.py`、`test_stop_loss_sanity.py` 等 | ⚠️ **pytest 采集风险**：本仓库**无 `pytest.ini`/`testpaths` 配置**，放入 `test_*.py` 会让裸 `pytest` 把你主机当测试收集，缺依赖时直接报错。其中 2 个已在 `tests/`，其余 5 个若要入库请**改名**或补 fixture 后再放 `tests/` |
| 审计 CSV 证据 | `P2_event_key_before.csv`、`P0.5_stop_loss_*.csv` 等 | 一次性审计输出，结论已写入对应文档 |
| `/tmp` 一次性探针 | `analyze_*.py`、`verify_*.py`、`monitor_*.py`、`live_*.py`、`shot*.py`、`exp_import_review*.py`、`cdp_*`、`gen_preview.py` 等 | 一次性调试/截图脚本，无复用价值 |
| `/tmp` 日志与中间 JSON | `*.log`、`cleared.json`(203KB)、`audit_runs.json` | 瞬态产物 |

---

## 后续新增脚本的约定

若日后要往 `tools/` 加脚本，**请确保文件名不以 `test_` 开头、不以 `_test.py` 结尾**，
否则会污染默认的 pytest 采集（本仓库没有 testpaths 配置，这点很容易踩）。
