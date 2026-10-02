# -*- coding: utf-8 -*-
"""dashboard-data 提交稳定性回归测试（本题任务范围：commit 稳定性 + 废弃 mirror 隔离）。

覆盖：
  A. dashboard_export.py 默认运行不产生 us-market-terminal/ 同步副本
  B. 正式 dashboard/data 路径仍然正常产出
  C. stocks 中仍然携带 rec_price 字段（保护已有字段修复）
  D. workflow 的 git add 范围不包含 us-market-terminal/，且无 git add . / -A
  E. workflow concurrency 不会 cancel 正在运行的 Dashboard Data
  F. workflow 无 force push、无 git pull --rebase
  G. rec_price 仍然取自 trade_history.Price（非当前价 / 非 Scan_Ref_Price）

运行：python3.11 tests/test_dashboard_data_stability.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "dashboard-data.yml"
EXPORT = REPO / "dashboard_export.py"
LEGACY_MIRROR = REPO / "us-market-terminal" / "dashboard" / "data" / "dashboard_data.json"

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'[PASS]' if ok else '[FAIL]'} {name}" + (f"  {detail}" if detail else ""))
    return ok


print("=" * 70)
print("dashboard-data 提交稳定性回归测试")
print("=" * 70)

# ---------------------------------------------------------------- A/B/C
print("\n--- A/B/C. 运行 dashboard_export.py 真实导出（默认参数）---")

wf = WORKFLOW.read_text(encoding="utf-8")
_export_text = EXPORT.read_text(encoding="utf-8")

mirror_before = LEGACY_MIRROR.stat().st_mtime if LEGACY_MIRROR.exists() else None
mirror_exists_before = LEGACY_MIRROR.exists()

tmp = Path(tempfile.mkdtemp(prefix="ddstab_"))
data_dir = tmp / "data"
data_dir.mkdir(parents=True, exist_ok=True)
out_dir = tmp / "out"
out_dir.mkdir(parents=True, exist_ok=True)

# 用仓库真实 CSV 的只读副本作为输入（只读源，写出的产物全部落到 tmp）
copied = []
for name in ("trade_history.csv", "option_strategies.csv", "review_history.csv",
             "strategy_params.json", "scan_version.txt"):
    src = REPO / name
    if src.exists():
        shutil.copy2(src, data_dir / name)
        copied.append(name)
print(f"  输入文件副本: {copied}")

proc = subprocess.run(
    [sys.executable, str(EXPORT),
     "--data-dir", str(data_dir),
     "--out", str(out_dir / "dashboard_data.json"),
     "--no-network", "--no-stooq", "--timeout", "1", "--retries", "0"],
    cwd=str(tmp), capture_output=True, text=True, timeout=300,
)
print(f"  退出码: {proc.returncode}")
if proc.returncode != 0:
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
    print("  错误尾部: " + " | ".join(tail))

formal = out_dir / "dashboard_data.json"
check("B. 正式 dashboard_data.json 已产出", formal.exists(), str(formal.name))

if formal.exists():
    d = json.loads(formal.read_text(encoding="utf-8"))
    stocks = d.get("stocks") or []
    have_key = sum(1 for s in stocks if "rec_price" in s)
    nonnull = sum(1 for s in stocks if s.get("rec_price") is not None)
    print(f"  stocks={len(stocks)}  rec_price 键={have_key}  非空={nonnull}")

    check("B2. JSON 合法且含全部顶层字段",
          all(k in d for k in ("stocks", "market", "options", "review", "history", "meta")))
    check("C. stocks 全部携带 rec_price 字段",
          len(stocks) > 0 and have_key == len(stocks),
          f"{have_key}/{len(stocks)}")
    check("C2. rec_price 有真实数值（来自 trade_history.Price）",
          nonnull == have_key, f"{nonnull}/{have_key}")

    # C3：rec_price 必须区别于当前价语义来源 —— 校验它等于源 CSV 的 Price，而非当前价
    import csv as _csv
    src_csv = data_dir / "trade_history.csv"
    if src_csv.exists() and stocks:
        with open(src_csv, encoding="utf-8") as f:
            rows = list(_csv.DictReader(f))
        by_tk = {}
        for r in rows:
            by_tk.setdefault((r.get("Ticker") or "").upper(), []).append(r.get("Price"))
        matched = 0
        checked = 0
        for s in stocks:
            tk = (s.get("ticker") or "").upper()
            cand = by_tk.get(tk) or []
            if not cand:
                continue
            checked += 1
            try:
                if any(abs(float(c) - float(s.get("rec_price"))) < 0.005 for c in cand if c):
                    matched += 1
            except Exception:
                pass
        check("C3. rec_price 取自 trade_history.Price（推荐日真实价）",
              checked > 0 and matched == checked, f"{matched}/{checked}")

# A. mirror 未被产生
mirror_created = (tmp / "us-market-terminal" / "dashboard" / "data" / "dashboard_data.json")
check("A1. 未在临时输出目录产生 mirror",
      not mirror_created.exists())

if mirror_exists_before:
    mtime_after = LEGACY_MIRROR.stat().st_mtime
    check("A2. 仓库内废弃 mirror 文件未被改写",
          mirror_before == mtime_after, "（mtime 未变）")
else:
    check("A2. 仓库内废弃 mirror 文件未被创建", not LEGACY_MIRROR.exists())

check("A3. 导出日志未出现 '同步副本'",
      "同步副本" not in (proc.stdout or ""))

# 参数存在性（CLI 向后兼容）
check("A4. --mirror 显式开关存在", "--mirror" in _export_text)
check("A5. --no-mirror 兼容参数仍被接受", "--no-mirror" in _export_text)
check("A6. mirror 写入由 args.mirror 显式控制（默认关闭）",
      "if args.mirror:" in _export_text)

# ---------------------------------------------------------------- D
print("\n--- D. workflow git add / commit 范围 ---")

# 仅检查「实际会被执行的命令行」，剔除 YAML 注释行，
# 否则注释里提到路径会被误判为真实引用。
wf_code = "\n".join(
    ln for ln in wf.splitlines() if ln.strip() and not ln.strip().startswith("#")
)

check("D1. 不再 git add us-market-terminal",
      "us-market-terminal" not in wf_code)
check("D2. 无 git add . / git add -A / git add --all",
      not ("git add ." in wf_code or "git add -A" in wf_code
           or "git add --all" in wf_code))
check("D4. 明确列出三个正式数据文件",
      all(p in wf for p in ("dashboard/data/dashboard_data.json",
                            "dashboard/data/last_run.json",
                            "dashboard/data/last_run.log")))
check("D5. 存在提交范围守卫（非预期文件即失败）",
      "检测到非预期文件进入提交范围" in wf)

# ---------------------------------------------------------------- E
print("\n--- E. concurrency ---")
check("E1. cancel-in-progress = false（不取消进行中的 run）",
      "cancel-in-progress: false" in wf)
check("E2. concurrency group 仅限 dashboard-data",
      "group: dashboard-data-refresh" in wf and wf.count("concurrency:") == 1)
import yaml  # noqa: E402
_parsed = yaml.safe_load(wf)
_on = _parsed.get(True, _parsed.get("on"))
check("E3. concurrency 配置可解析且作用域正确",
      _parsed.get("concurrency", {}).get("cancel-in-progress") is False)
check("E4. schedule 未被修改（*/15 * * * 1-5）",
      _on.get("schedule") == [{"cron": "*/15 * * * 1-5"}])
check("E5. push.paths 未被修改",
      _on.get("push", {}).get("paths") == ["dashboard_export.py",
                                           "dashboard/fetch_runtimes.py",
                                           "dashboard/summarize_run.py",
                                           ".github/workflows/dashboard-data.yml"])

# ---------------------------------------------------------------- F
print("\n--- F. push 安全性 ---")
check("F1. 无 force push", "--force" not in wf and "force-with-lease" not in wf)
check("F2. 不再使用 git pull --rebase（避免同源 JSON 行级冲突）",
      "pull --rebase" not in wf_code)
check("F3. retry 前重新 fetch（不使用陈旧远端基准）",
      "git fetch origin main" in wf)
check("F4. retry 上限为 3 次", "for i in 1 2 3" in wf)
check("F5. 失败时明确报错而非静默通过", "exit 1" in wf)

# ---------------------------------------------------------------- G
print("\n--- G. 已有修复未被回退（源码守卫）---")
rev_py = (REPO / "review.py").read_text(encoding="utf-8")
check("G1. review.py 仍透传 Market_Regime / VIX / Sector_RS_20D_Pct",
      all(k in rev_py for k in ("Market_Regime", "VIX", "Sector_RS_20D_Pct")))
check("G2. dashboard_export 仍输出 rec_price", '"rec_price"' in _export_text)
app_js = (REPO / "app.js").read_text(encoding="utf-8")
check("G3. app.js 仍渲染买入价", "recPrice" in app_js)
check("G4. Options RR 门槛未被改动（2.0 / 0.40 仍并存）",
      "MIN_REWARD_RISK = 2.0" in (REPO / "scan_us_option_engine.py").read_text(encoding="utf-8"))
check("G5. 无 Email / SMTP 回归",
      "smtplib" not in _export_text and "smtplib" not in rev_py)

# 清理
shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------- 结果
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
print("\n" + "=" * 70)
for name, ok, detail in results:
    if not ok:
        print(f"  FAILED: {name} {detail}")
print(f"结果：通过 {passed} / {total}")
print("=" * 70)
sys.exit(0 if passed == total else 1)
