# scripts/ — 运维脚本（可复用）

> 归档日期：2026-10-13 · 来源：沙箱 `/workspace`，停用前抢救性入库
> **这些脚本不被任何 workflow 调用**，是人工运维时手动执行的工具。

## monday_check.sh（★ 唯一被 runbook 引用）

被 `docs/archive/TUESDAY_CHECKLIST.md` 与 `docs/archive/TONIGHT_CHECKLIST.md` 引用：
原写法是 `bash /workspace/monday_check.sh`，沙箱停用后该文件不再存在，**改指向本文件**：

```bash
cd /tmp/us            # 或你的仓库根目录
bash scripts/monday_check.sh
```

产出：§1~§9 体检结果（scan run 数、flag 状态、持仓与组合概览等），用于 06:23 review 后的复核。

### ⚠️ 移植到新机器前必改一处

文件第 21 行硬编码了沙箱仓库路径：

```bash
REPO="/tmp/us"        # ← 改成你的本地仓库绝对路径
```

其余部分只读（`git log` / `git show` / `git fetch`），**不改写任何文件**，可直接用。
（本副本为原样保留，未做改动 —— 如需改 REPO 请自行替换。）

---

## 目录约定

| 目录 | 用途 |
|------|------|
| `scripts/` | 运维/体检脚本，**手动执行**，生产链路不依赖 |
| `tools/` | 分析、修复、补采、实验脚本（一次性资产，保留为「怎么做到的」证据） |

⚠️ **两者都不参与 CI，也不参与 pytest**（无 `test_*.py` / `*_test.py` 命名，避免被默认采集）。


## ticker_brief.py —— 单只标的决策简报（只读）

```bash
python scripts/ticker_brief.py AAPL                    # 纯文本（默认）
python scripts/ticker_brief.py AAPL --md               # Markdown
python scripts/ticker_brief.py AAPL --json             # 结构化 JSON
python scripts/ticker_brief.py AAPL --date 2026-10-16  # 指定历史快照日
python scripts/ticker_brief.py --ticker AAPL --json    # --ticker 写法同样支持
```

输出四段：① AI 历史（`ai_snapshot.csv`）② 因子位置 + 当日横截面百分位（`quant_factor_snapshot.csv`）
③ 交易明细（`portfolio_50000_transactions.csv` + 侧车 `portfolio_50000_txn_time.csv` 的精确时刻；
无记录时自动退化为同 Sector 最近 10 笔）④ 宏观结论（恐惧贪婪 / FedWatch / 经济指标 / 美联储讲话）。

特性：**只读、不写文件**；不 import 任何生产模块；缺失项统一 `N/A`，异常不外抛，退出码恒 0。
