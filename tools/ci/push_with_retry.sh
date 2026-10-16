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
    REBASE_OUT=$(git rebase origin/main 2>&1) || {
        if echo "$REBASE_OUT" | grep -q "CONFLICT"; then
            echo "::error::git rebase 发生冲突，停止推送（不 force）"
            echo "$REBASE_OUT"
            git rebase --abort 2>/dev/null || true
            exit 1
        fi
    }
    if git push origin HEAD:main; then
        echo "[push_with_retry] push ok (attempt $i)"
        exit 0
    fi
    echo "[push_with_retry] attempt $i failed, retrying..."
    git rebase --abort 2>/dev/null || true
    sleep "$SLEEP_SEC"
done

echo "[push_with_retry] push failed after $MAX_RETRIES retries"
exit 1
