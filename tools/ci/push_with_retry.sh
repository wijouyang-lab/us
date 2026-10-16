#!/bin/bash
# tools/ci/push_with_retry.sh
#
# 用途：GitHub Actions 中安全推送
# 逻辑：fetch origin main -> rebase -> push，失败重试 N 次
# 用法：bash tools/ci/push_with_retry.sh [MAX_RETRIES] [SLEEP_SEC]
#
# 注意：GH Actions runner IP 不被 GitHub 封锁，无需 curloptResolve

set -e

MAX_RETRIES="${1:-3}"
SLEEP_SEC="${2:-5}"

echo "[push_with_retry] starting (max=$MAX_RETRIES, sleep=$SLEEP_SEC)"

for i in $(seq 1 "$MAX_RETRIES"); do
    echo "[push_with_retry] attempt $i"
    git fetch origin main || true
    if git rebase origin/main; then
        if git push origin HEAD:main; then
            echo "[push_with_retry] push ok (attempt $i)"
            exit 0
        fi
    else
        echo "[push_with_retry] rebase conflict on attempt $i, aborting and retrying..."
        git rebase --abort 2>/dev/null || true
    fi
    echo "[push_with_retry] attempt $i failed, retrying..."
    git rebase --abort 2>/dev/null || true
    sleep "$SLEEP_SEC"
done

echo "[push_with_retry] push failed after $MAX_RETRIES retries"
exit 1
