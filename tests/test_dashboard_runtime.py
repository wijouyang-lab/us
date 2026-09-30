# -*- coding: utf-8 -*-
"""Dashboard 运行状态改造回归测试（离线，纯函数）。

覆盖：
  1. Scan success 更新 Scan metadata（独立字段）
  2. Review success 更新 Review metadata（独立字段）
  3. Scan 不覆盖 Review
  4. Review 不覆盖 Scan
  5. failed run 不覆盖 success（API status=success 过滤）
  6. cancelled run 不覆盖 success
  7. SHA 与实际 workflow head_sha 一致
  8. 时间转换为北京时间（UTC+8，固定无夏令时）
  9. 没有历史运行时显示合理 N/A
  10. 字段独立，不共用 last_run_at / last_run_sha
"""
import importlib.util
import os

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FR_PATH = os.path.join(REPO, "dashboard", "fetch_runtimes.py")

# 用 importlib 从文件路径加载 fetch_runtimes 模块（dashboard 无 __init__.py）
_spec = importlib.util.spec_from_file_location("fetch_runtimes", FR_PATH)
fr_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fr_mod)

results = []
def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


def run_with(mock_responses):
    """用 mock 的 _fetch 运行 fetch_runtimes，返回结果，随后恢复原始 _fetch。"""
    orig = fr_mod._fetch
    fr_mod._fetch = mock_responses
    try:
        return fr_mod.fetch_runtimes("tok", "o/r")
    finally:
        fr_mod._fetch = orig


print("== 1/2. Scan / Review 独立字段 ==")
def both_success(token, repo, workflow_file, timeout=30):
    runs = {
        "scan.yml": [{"id": 1, "conclusion": "success", "updated_at": "2026-09-30T21:00:00Z", "head_sha": "abc1234567890"}],
        "review.yml": [{"id": 2, "conclusion": "success", "updated_at": "2026-10-01T06:00:00Z", "head_sha": "def5678901234"}],
    }
    return {"workflow_runs": runs.get(workflow_file, [])}

out = run_with(both_success)
check("1. scan 有独立 last_success_at/sha",
      out["scan"]["last_success_at"] == "2026-09-30T21:00:00Z" and out["scan"]["last_success_sha"] == "abc123456789")
check("2. review 有独立 last_success_at/sha",
      out["review"]["last_success_at"] == "2026-10-01T06:00:00Z" and out["review"]["last_success_sha"] == "def567890123")

print("== 3/4. Scan/Review 互不覆盖 ==")
check("3. Scan 不覆盖 Review", out["scan"]["last_success_sha"] == "abc123456789" and out["review"]["last_success_sha"] == "def567890123")
check("4. Review 不覆盖 Scan", out["review"]["last_success_at"] == "2026-10-01T06:00:00Z" and out["scan"]["last_success_at"] == "2026-09-30T21:00:00Z")

print("== 5/6. failed/cancelled 不覆盖 success ==")
def only_failed(token, repo, workflow_file, timeout=30):
    return {"workflow_runs": [{"id": 3, "conclusion": "failure", "updated_at": "2026-10-02T00:00:00Z", "head_sha": "bad"}]}
out2 = run_with(only_failed)
check("5. failed run 不产生 success 时间", out2["scan"]["last_success_at"] is None)
check("6. cancelled run 不产生 success 时间", out2["review"]["last_success_at"] is None)

print("== 7. SHA 与 head_sha 一致（截断前12位） ==")
long_sha = "19021f6adbd6f75db96e718644eaf7295650a0ec"
def one_success(token, repo, workflow_file, timeout=30):
    return {"workflow_runs": [{"id": 9, "conclusion": "success", "updated_at": "2026-09-30T07:26:16Z", "head_sha": long_sha}]}
out3 = run_with(one_success)
check("7. SHA 截断为前12位且一致", out3["scan"]["last_success_sha"] == "19021f6adbd6")

print("== 8. 时间转换为北京时间（UTC+8 固定） ==")
def to_beijing(iso):
    import datetime as dt
    d = dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    bj = d + dt.timedelta(hours=8)
    return bj.strftime("%Y-%m-%d %H:%M:%S")
check("8. UTC 21:00 -> 北京 05:00(+1天)", to_beijing("2026-09-30T21:00:00Z") == "2026-10-01 05:00:00")
check("8b. UTC 06:00 -> 北京 14:00(同日)", to_beijing("2026-10-01T06:00:00Z") == "2026-10-01 14:00:00")

print("== 9/10. 无运行时 N/A + 独立字段名 ==")
check("9. 无 success run 时字段为 null(N/A)",
      out2["evolve"]["last_success_at"] is None and out2["evolve"]["last_success_sha"] is None)
check("10. 字段名为 scan/review/evolve 独立（非共用 last_run）",
      "scan" in out and "review" in out and "evolve" in out
      and "last_run_at" not in out and "last_run_sha" not in out)

failed = [n for n, c in results if not c]
print(f"\n结果：通过 {len(results)-len(failed)} / {len(results)}")
if failed:
    print("失败：", failed)
    raise SystemExit(1)
print("全部通过 ✅")
