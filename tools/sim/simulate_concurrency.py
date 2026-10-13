# -*- coding: utf-8 -*-
"""在完全隔离的临时 git 仓库中模拟 dashboard-data 并发提交场景。

验证：两次运行修改同一正式数据文件时，
  旧逻辑 `git pull --rebase` 必然冲突导致数据丢失；
  新逻辑 `git fetch + git reset --soft + 重新提交` 可无冲突完成。

不在真实仓库上做任何写入。
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cwd, *args, check=False):
    r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{args} failed\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}")
    return r


def main():
    tmp = Path(tempfile.mkdtemp(prefix="sim_"))
    print(f"隔离沙箱: {tmp}")
    try:
        origin = tmp / "origin.git"
        run(tmp, "git", "init", "-q", "-b", "main", "--bare", str(origin), check=True)

        def clone(name):
            d = tmp / name
            run(tmp, "git", "clone", "-q", str(origin), name, check=True)
            run(d, "git", "config", "user.email", "bot@example.com", check=True)
            run(d, "git", "config", "user.name", "bot", check=True)
            run(d, "git", "checkout", "-q", "-b", "main", check=True)
            return d

        c1 = clone("c1")
        data = c1 / "dashboard" / "data"
        data.mkdir(parents=True, exist_ok=True)
        (data / "dashboard_data.json").write_text('{"v":"BASE"}', encoding="utf-8")
        (data / "last_run.json").write_text("{}", encoding="utf-8")
        (data / "last_run.log").write_text("log", encoding="utf-8")
        run(c1, "git", "add", "-A", check=True)
        run(c1, "git", "commit", "-qm", "base", check=True)
        run(c1, "git", "push", "-q", "origin", "main", check=True)
        print("初始提交完成")

        # run A（先到）
        (c1 / "dashboard" / "data" / "dashboard_data.json").write_text('{"v":"RUN_A"}', encoding="utf-8")
        run(c1, "git", "add", "dashboard/data/dashboard_data.json", check=True)
        run(c1, "git", "commit", "-qm", "refresh run A", check=True)
        run(c1, "git", "push", "-q", "origin", "main", check=True)
        print("run A 已推送")

        # run B（旧基准）
        c2 = tmp / "c2"
        run(c2, "git", "config", "user.email", "bot@example.com", check=True)
        run(c2, "git", "config", "user.name", "bot", check=True)
        (c2 / "dashboard" / "data" / "dashboard_data.json").write_text('{"v":"RUN_B"}', encoding="utf-8")
        run(c2, "git", "add", "dashboard/data/dashboard_data.json", check=True)
        run(c2, "git", "commit", "-qm", "refresh run B", check=True)
        print("run B 本地提交完成（远端已领先）")

        print("\n=====[旧逻辑] git pull --rebase origin main=====")
        r_old = run(c2, "git", "pull", "--rebase", "origin", "main")
        for ln in ((r_old.stdout or "") + (r_old.stderr or "")).splitlines():
            if any(k in ln.upper() for k in ("CONFLICT", "ERROR", "COULD NOT APPLY")):
                print("  " + ln.strip())
        print(f"  退出码: {r_old.returncode}")
        run(c2, "git", "rebase", "--abort")
        print("  已 abort，模拟旧逻辑失败路径")

        print("\n=====[新逻辑] fetch + reset --soft + 重新提交=====")
        run(c2, "git", "fetch", "origin", "main", check=True)
        run(c2, "git", "reset", "--soft", "FETCH_HEAD", check=True)
        rq = run(c2, "git", "diff", "--cached", "--quiet")
        if rq.returncode == 0:
            print("  远端数据与本轮一致，无需重复提交")
        else:
            run(c2, "git", "commit", "-qm", "refresh run B (rebased)", check=True)
            print("  已基于最新 main 重建提交")
        r_new = run(c2, "git", "push", "origin", "main")
        print(f"  push 退出码: {r_new.returncode} -> {'✅ 成功，无冲突' if r_new.returncode == 0 else '❌ 失败'}")

        print("\n" + "=" * 60)
        ok = (r_old.returncode != 0) and (r_new.returncode == 0)
        print(f"  旧逻辑结果: {'❌ 失败（与 #951 一致）' if r_old.returncode != 0 else '成功'}")
        print(f"  新逻辑结果: {'✅ 成功，无冲突' if r_new.returncode == 0 else '❌ 失败'}")
        print(f"  结论: {'✅ 修复有效' if ok else '❌ 需复核'}")
        print("=" * 60)
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
