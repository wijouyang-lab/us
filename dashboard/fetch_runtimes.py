# -*- coding: utf-8 -*-
"""从 GitHub Actions API 读取 scan/review/evolve 最近一次成功运行元数据。

输出 JSON（stdout）：
{
  "scan":   {"last_success_at": "2026-09-30T07:00:18Z", "last_success_sha": "abc123...", "run_id": 123},
  "review": {...},
  "evolve": {...}
}

规则：
- 只接受 conclusion == "success" 的 run（失败/取消/跳过不覆盖成功时间）；
- last_success_at = 该成功 run 的 updated_at（完成时间，ISO 8601 UTC）；
- last_success_sha = 该成功 run 实际使用的 head_sha（前 12 位）；
- 无 GITHUB_TOKEN / GITHUB_REPOSITORY 或 API 失败时，对应字段为 null。

纯只读：不写任何文件、不修改任何数据。
"""
import json
import os
import sys
import urllib.request

WORKFLOWS = {
    "scan": "scan.yml",
    "review": "review.yml",
    "evolve": "evolve.yml",
}


def _fetch(token, repo, workflow_file, timeout=30):
    url = (
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/runs"
        f"?status=success&per_page=1"
    )
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dashboard-fetch-runtimes",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_runtimes(token, repo):
    """返回 {scan:{...}, review:{...}, evolve:{...}}，失败字段为 None。"""
    out = {}
    for key, wf in WORKFLOWS.items():
        entry = {"last_success_at": None, "last_success_sha": None, "run_id": None}
        try:
            data = _fetch(token, repo, wf)
            runs = data.get("workflow_runs") or []
            if runs:
                r = runs[0]
                if r.get("conclusion") == "success":
                    entry["last_success_at"] = r.get("updated_at") or r.get("created_at")
                    sha = r.get("head_sha") or ""
                    entry["last_success_sha"] = sha[:12] if sha else None
                    entry["run_id"] = r.get("id")
        except Exception:
            pass
        out[key] = entry
    return out


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print(json.dumps({k: {"last_success_at": None, "last_success_sha": None, "run_id": None}
                          for k in WORKFLOWS}, ensure_ascii=False))
        return
    print(json.dumps(fetch_runtimes(token, repo), ensure_ascii=False))


if __name__ == "__main__":
    main()
