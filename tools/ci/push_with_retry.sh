#!/bin/bash
# tools/ci/push_with_retry.sh
#
# 用途：GitHub Actions 中安全推送
# 逻辑：fetch origin main -> [可选 Pending 保护] -> rebase -> push，失败重试 N 次
# 用法：bash tools/ci/push_with_retry.sh [MAX_RETRIES] [SLEEP_SEC] [PROTECT_PENDING]
#   PROTECT_PENDING=1：Review 专用。推送前比较 origin/main 上的
#   us_stocks_pending_*.csv 与本地同名 .csv.processed 的字节内容；
#   若远端 Pending 在本轮 Review 期间被 Scan 更新/新增，则立即安全失败，
#   不执行 rebase/push，避免 rename 被 Git 静默解析为“覆盖远端新行”。
#
# 注意：GH Actions runner IP 不被 GitHub 封锁，无需 curloptResolve

set -e

MAX_RETRIES="${1:-3}"
SLEEP_SEC="${2:-5}"
PROTECT_PENDING="${3:-0}"

echo "[push_with_retry] starting (max=$MAX_RETRIES, sleep=$SLEEP_SEC, protect_pending=$PROTECT_PENDING)"

for i in $(seq 1 "$MAX_RETRIES"); do
    echo "[push_with_retry] attempt $i"
    git fetch origin main || true
    if [ "$PROTECT_PENDING" = "1" ]; then
        while IFS= read -r remote_pending; do
            [ -z "$remote_pending" ] && continue
            local_processed="${remote_pending}.processed"
            if [ ! -f "$local_processed" ]; then
                echo "::error::[pending-guard] remote $remote_pending has no local .processed; refusing push"
                exit 2
            fi
            if ! git show "origin/main:$remote_pending" | cmp -s - "$local_processed"; then
                echo "::error::[pending-guard] remote $remote_pending changed after Review started; refusing push (keep remote Pending for next Review)"
                exit 2
            fi
        done < <(git ls-tree -r --name-only origin/main | grep -E '^us_stocks_pending_[0-9]{8}\.csv$' || true)
    fi
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
