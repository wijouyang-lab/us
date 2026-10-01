# -*- coding: utf-8 -*-
"""从 GitHub Actions API 读取 scan/review/evolve 最近运行元数据。

输出 JSON（stdout）：
{
  "scan": {
    "latest": {
      "run_id": 123,
      "status": "completed",          # queued | in_progress | completed | ...
      "conclusion": "success",        # success | failure | cancelled | skipped | null(运行中)
      "created_at": "2026-09-30T18:21:10Z",
      "started_at": "2026-09-30T18:21:10Z",   # 来自 GitHub run_started_at
      "updated_at": "2026-09-30T18:35:06Z",   # 结束时间近似（见下）
      "head_sha": "9737418287b7",             # 前 12 位
      "event": "schedule",
      "run_number": 1234,
      "run_attempt": 1,
      "html_url": "https://github.com/.../runs/123"
    },
    "last_success": {
      "run_id": 123,
      "completed_at": "2026-09-30T18:35:06Z",  # = updated_at（API 无 completed_at）
      "head_sha": "9737418287b7"
    },
    "error": null
  },
  "review": {...},
  "evolve": {...}
}

规则：
- latest = 最近一次 run（无论成败/进行中），保留 GitHub 原始 status 与 conclusion；
- last_success = 最近一次 conclusion == "success" 的 run；
- GitHub Actions API 不提供 completed_at，故 last_success.completed_at 使用
  该 run 的 updated_at 作为完成时间近似（见下方注释）；
- 单个 workflow 的 API 失败时，latest / last_success 置 null，并把异常写入 error，
  但绝不让整个脚本崩溃（scan 失败不影响 review/evolve）。

纯只读：不写任何文件、不修改任何数据。
"""
import json
import os
import urllib.request

WORKFLOWS = {
    "scan": "scan.yml",
    "review": "review.yml",
    "evolve": "evolve.yml",
}


def _fetch(token, repo, workflow_file, timeout=30):
    url = (
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/runs"
        f"?per_page=10"
    )
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dashboard-fetch-runtimes",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _short_sha(sha):
    if not sha:
        return None
    return sha[:12]


def _build_latest(r):
    """把 GitHub run 对象映射为 latest 结构，原样保留 status/conclusion。"""
    return {
        "run_id": r.get("id"),
        "status": r.get("status"),
        "conclusion": r.get("conclusion"),
        "created_at": r.get("created_at"),
        "started_at": r.get("run_started_at"),
        "updated_at": r.get("updated_at"),
        "head_sha": _short_sha(r.get("head_sha")),
        "event": r.get("event"),
        "run_number": r.get("run_number"),
        "run_attempt": r.get("run_attempt"),
        "html_url": r.get("html_url"),
    }


def fetch_runtimes(token, repo):
    """返回 {scan:{latest,last_success,error}, review:{...}, evolve:{...}}。"""
    out = {}
    for key, wf in WORKFLOWS.items():
        entry = {"latest": None, "last_success": None, "error": None}
        try:
            data = _fetch(token, repo, wf)
            runs = data.get("workflow_runs") or []
            if runs:
                # GitHub API 默认按 created_at 倒序返回，runs[0] 即最近一次运行
                entry["latest"] = _build_latest(runs[0])
            # 在最近 10 条中找最近一次成功
            for r in runs:
                if r.get("conclusion") == "success":
                    entry["last_success"] = {
                        "run_id": r.get("id"),
                        # GitHub Actions API does not expose completed_at;
                        # updated_at is used as the completion-time approximation.
                        "completed_at": r.get("updated_at") or r.get("created_at"),
                        "head_sha": _short_sha(r.get("head_sha")),
                    }
                    break
        except Exception as e:
            # 记录异常但不崩溃：单个 workflow 失败不影响其他 workflow
            entry["error"] = {"type": type(e).__name__, "message": str(e)}
        out[key] = entry
    return out


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        empty = {"latest": None, "last_success": None, "error": None}
        print(json.dumps({k: empty for k in WORKFLOWS}, ensure_ascii=False))
        return
    print(json.dumps(fetch_runtimes(token, repo), ensure_ascii=False))


if __name__ == "__main__":
    main()
