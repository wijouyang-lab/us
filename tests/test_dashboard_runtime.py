# -*- coding: utf-8 -*-
"""Dashboard 运行状态改造回归测试（离线，纯函数）。

覆盖（对应 runtime 架构升级 latest + last_success）：
  1. success → latest.status=completed, conclusion=success；last_success 正确
  2. running → latest.status=in_progress, conclusion=None；last_success 为更早 success
  3. queued → latest.status=queued, conclusion=None
  4. failed → latest 保留 failed；last_success 为更早 success（不覆盖）
  5. cancelled → latest 保留 cancelled；last_success 为更早 success
  6. skipped → latest 保留 skipped
  7. 全失败无 success → last_success=null
  8. 空 runs → latest=null, last_success=null
  9. API 异常 → error 记录 type/message，latest/last_success=null，不崩溃
  10. SHA 截断为前 12 位
  11. scan/review/evolve 独立字段
  12. completed_at 使用 updated_at（GitHub API 无 completed_at）
"""
import importlib.util
import os

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FR_PATH = os.path.join(REPO, "dashboard", "fetch_runtimes.py")

_spec = importlib.util.spec_from_file_location("fetch_runtimes", FR_PATH)
fr_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fr_mod)

results = []
def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


def run_with(mock_responses):
    orig = fr_mod._fetch
    fr_mod._fetch = mock_responses
    try:
        return fr_mod.fetch_runtimes("tok", "o/r")
    finally:
        fr_mod._fetch = orig


def run_obj(rid, status, conclusion, updated, sha="abc1234567890", event="schedule", n=100):
    return {"id": rid, "status": status, "conclusion": conclusion,
            "created_at": "2026-10-01T18:00:00Z", "run_started_at": "2026-10-01T18:01:00Z",
            "updated_at": updated, "head_sha": sha, "event": event,
            "run_number": n, "run_attempt": 1, "html_url": f"https://x/{rid}"}


def one_wf(runs):
    def f(token, repo, workflow_file, timeout=30):
        return {"workflow_runs": runs}
    return f


print("== 1. success ==")
out = run_with(one_wf([run_obj(1, "completed", "success", "2026-10-01T18:20:00Z")]))
s = out["scan"]
check("1a. latest.status=completed", s["latest"]["status"] == "completed")
check("1b. latest.conclusion=success", s["latest"]["conclusion"] == "success")
check("1c. last_success.run_id=1", s["last_success"]["run_id"] == 1)

print("== 2/3. running / queued ==")
out = run_with(one_wf([run_obj(10, "in_progress", None, "2026-10-01T18:20:00Z"),
                       run_obj(9, "completed", "success", "2026-10-01T17:00:00Z")]))
check("2a. running: latest.status=in_progress", out["scan"]["latest"]["status"] == "in_progress")
check("2b. running: latest.conclusion=None", out["scan"]["latest"]["conclusion"] is None)
check("2c. running: last_success 为更早 success(run 9)", out["scan"]["last_success"]["run_id"] == 9)

out = run_with(one_wf([run_obj(11, "queued", None, "2026-10-01T18:00:00Z"),
                       run_obj(9, "completed", "success", "2026-10-01T17:00:00Z")]))
check("3. queued: latest.status=queued, conclusion=None",
      out["scan"]["latest"]["status"] == "queued" and out["scan"]["latest"]["conclusion"] is None)

print("== 4/5/6. failed / cancelled / skipped 不被过滤 ==")
out = run_with(one_wf([run_obj(1, "completed", "failure", "2026-10-01T18:20:00Z"),
                       run_obj(2, "completed", "success", "2026-10-01T17:00:00Z")]))
check("4a. failed: latest.conclusion=failure", out["scan"]["latest"]["conclusion"] == "failure")
check("4b. failed: last_success=更早 success(run 2)", out["scan"]["last_success"]["run_id"] == 2)

out = run_with(one_wf([run_obj(1, "completed", "cancelled", "2026-10-01T18:20:00Z"),
                       run_obj(2, "completed", "success", "2026-10-01T17:00:00Z")]))
check("5. cancelled: latest.conclusion=cancelled, last_success=run 2",
      out["scan"]["latest"]["conclusion"] == "cancelled" and out["scan"]["last_success"]["run_id"] == 2)

out = run_with(one_wf([run_obj(1, "completed", "skipped", "2026-10-01T18:20:00Z")]))
check("6. skipped: latest.conclusion=skipped", out["scan"]["latest"]["conclusion"] == "skipped")

print("== 7/8. 全失败 / 空 ==")
out = run_with(one_wf([run_obj(1, "completed", "failure", "18:20"),
                       run_obj(2, "completed", "failure", "17:00")]))
check("7. 全失败: last_success=null", out["scan"]["last_success"] is None)
out = run_with(one_wf([]))
check("8. 空 runs: latest=null, last_success=null",
      out["scan"]["latest"] is None and out["scan"]["last_success"] is None)

print("== 9. API 异常记录 ==")
def boom(token, repo, workflow_file, timeout=30):
    raise RuntimeError("HTTP 403 rate limit")
out = run_with(boom)
check("9a. 异常记录 type", out["scan"]["error"]["type"] == "RuntimeError")
check("9b. 异常记录 message", "HTTP 403" in out["scan"]["error"]["message"])
check("9c. latest/last_success 为 null 不崩溃",
      out["scan"]["latest"] is None and out["scan"]["last_success"] is None
      and out["review"]["latest"] is None and out["evolve"]["latest"] is None)

print("== 10/11/12. SHA / 独立字段 / completed_at ==")
long_sha = "19021f6adbd6f75db96e718644eaf7295650a0ec"
out = run_with(one_wf([run_obj(9, "completed", "success", "2026-09-30T07:26:16Z", sha=long_sha)]))
check("10. SHA 截断 12 位", out["scan"]["latest"]["head_sha"] == "19021f6adbd6")
check("11. scan/review/evolve 独立", set(out.keys()) == {"scan", "review", "evolve"})
check("12. completed_at == updated_at（API 无 completed_at）",
      out["scan"]["last_success"]["completed_at"] == "2026-09-30T07:26:16Z")

failed = [n for n, c in results if not c]
print(f"\n结果：通过 {len(results)-len(failed)} / {len(results)}")
if failed:
    print("失败：", failed)
    raise SystemExit(1)
print("全部通过 ✅")
