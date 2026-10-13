# scripts/ — 运维脚本（可复用）

> 归档日期：2026-10-13 · 来源：沙箱 `/workspace`，停用前抢救性入库
> **这些脚本不被任何 workflow 调用**，是人工运维时手动执行的工具。

## monday_check.sh（★ 唯一被 runbook 引用）

被 `docs/TUESDAY_CHECKLIST.md` 与 `docs/TONIGHT_CHECKLIST.md` 引用：
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
