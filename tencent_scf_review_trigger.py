# -*- coding: utf-8 -*-
"""
腾讯云函数（SCF）：定时触发 GitHub Actions 美股盘后 Review
=========================================================

职责边界（严格遵守）：
  本函数 **只负责定时触发**，不复制 / 不重新实现 review.py 的任何逻辑，
  不做复盘计算、不算 5D/10D/20D/Final、不调用 AI、不读写任何业务数据。
  真正的复盘由 GitHub Actions 的 review.yml 执行（python review.py）。

链路：
  腾讯云定时触发器(Cron) -> 本云函数 -> GitHub API workflow_dispatch
  -> review.yml -> python review.py -> review_history.csv / trade_history.csv
  -> git push -> dashboard-data.yml -> dashboard_data.json -> Dashboard

------------------------------------------------------------------
环境变量（在腾讯云函数「环境变量 / 密钥配置」里设置，切勿写进代码）
------------------------------------------------------------------
  GITHUB_TOKEN   (必填)  GitHub Personal Access Token，需具备触发 workflow 的权限
                         （与现有 Scan 调度函数 US-Share-Scan 使用同一个 Token 即可）
  GITHUB_REPO    (可选)  默认 "wijouyang-lab/us"
  GITHUB_WORKFLOW(可选)  默认 "review.yml"
  GITHUB_REF     (可选)  默认 "main"

------------------------------------------------------------------
腾讯云定时触发器 Cron（7 字段：秒 分 时 日 月 星期 年，时区为北京时间 UTC+8）
------------------------------------------------------------------
  ⚠️ 本文件只含函数代码；Cron 需在腾讯云控制台的「触发管理」里单独配置，
     代码里不会、也不应该出现 Cron 触发器的实际配置。

  ⚠️ 时区差异：腾讯云 Cron 是 7 字段且按北京时间(UTC+8)；
     GitHub Actions 的 cron 是 5 字段且按 UTC，两者定义不同，不要照搬。

  与 Scan 分离（不重叠触发）：
     - Scan Timer（用户已确认）：0 0 21 * * 1-5 *   = 工作日 21:00 北京 = 美东 09:00 盘前
     - Review 必须在「美国交易日收盘之后」的盘后时间运行。

  建议 Review 触发时间（仅建议，未经腾讯云控制台验证，需用户最终确认）：
     - 0 0 6 * * 1-5 *
       = 工作日 06:00 北京时间
       = 美东夏令时(EDT, UTC-4) 18:00（收盘 16:00 后 2 小时）
       = 美东冬令时(EST, UTC-5) 17:00（收盘 16:00 后 1 小时）
     - 选择 06:00 而非 04:00/05:00 的原因：美股夏令时/冬令时切换（北京不切换），
       06:00 在北京时间下两季都能落在收盘后至少 1 小时，避免收盘价尚未结算。
     - 若需更贴近收盘，夏令时可用 0 0 5 * * 1-5 *（北京 05:00 = EDT 17:00 盘后 1 小时），
       但冬令时需手动切到 0 0 6 * * 1-5 *。

------------------------------------------------------------------
腾讯云函数信息（建议，需用户在控制台创建后确认）
------------------------------------------------------------------
  建议函数名：US-Share-Review（与现有 US-Share-Scan 并列）
  命名空间：default     地域：rid=1
  入口函数：main_handler（SCF Python 标准入口）

安全约定：
  - 绝不把 Token 写进代码 / 仓库 / README / dashboard / 前端 JS
  - 本文件里不会出现任何真实 Token
"""

import json
import os
import urllib.error
import urllib.request

REPO = os.environ.get("GITHUB_REPO", "wijouyang-lab/us")
WORKFLOW = os.environ.get("GITHUB_WORKFLOW", "review.yml")
REF = os.environ.get("GITHUB_REF", "main")

DISPATCH_URL = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches"
TIMEOUT = 20


def main_handler(event, context):
    """腾讯云函数入口。event/context 由 SCF 传入，本函数不使用其业务内容。"""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        return {"success": False, "status": None,
                "error": "环境变量 GITHUB_TOKEN 未配置（请在腾讯云函数环境变量/密钥中设置）"}

    payload = json.dumps({"ref": REF}).encode("utf-8")
    req = urllib.request.Request(
        DISPATCH_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "tencent-scf-review-trigger",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
        # GitHub workflow_dispatch 成功返回 204 No Content
        if 200 <= status < 300:
            return {"success": True, "workflow": WORKFLOW, "repo": REPO, "status": status}
        return {"success": False, "status": status, "error": f"GitHub API 返回非 2xx：{status}"}

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        return {"success": False, "status": e.code, "error": f"HTTP {e.code} {e.reason} {body}".strip()}

    except Exception as e:
        return {"success": False, "status": None, "error": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    # 本地自测入口（部署到腾讯云后由定时触发器调用 main_handler）
    print(json.dumps(main_handler({}, None), ensure_ascii=False, indent=2))
