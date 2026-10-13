#!/usr/bin/env bash
#
# 周一验证脚本 —— 只读，不改仓库
# ----------------------------------------------------------------------------
# 用途：一键跑完周一 4 个时点（06:23 review / 21:07 scan / 21:30+ Dashboard /
#       22:00 review）的核心检查，输出 ✅ / ❌ / ⚠️ 状态表。
# 用法：bash monday_check.sh
#
# 铁律：
#   - 只读：cd /tmp/us 后只做 git log / git show / git fetch，绝不改写任何文件。
#   - 不静默错误：关键命令的错误（command not found / permission denied）会显式报出，
#     不靠 2>/dev/null 吞掉（仅 grep/python 的内部 stderr 重定向，错误仍会上报）。
#   - 幂等：可任意重复运行，无副作用。
#   - 本脚本不含任何测试断言的"修复"动作，仅供人工核对。
# ----------------------------------------------------------------------------

set -u
# 故意不设 set -e：单项检查失败不应中断整体；错误通过 $? 与 stderr 暴露。

# ── 仓库与预取 ─────────────────────────────
REPO="/tmp/us"
if [ ! -d "$REPO/.git" ]; then
  echo "❌ 仓库目录不存在或不是 git 仓库: $REPO"
  exit 1
fi
cd "$REPO" || { echo "❌ 无法进入 $REPO（permission denied?）"; exit 1; }

# 只做只读网络预取；失败也继续（以本地 origin/main 为准）
git fetch origin --quiet || echo "⚠️ git fetch origin 失败（可能无网络/无权限），以下以本地 origin/main 为准"

# ── 状态打印助手 ───────────────────────────
ok()   { printf '   ✅ %s\n' "$1"; }
bad()  { printf '   ❌ %s\n' "$1"; }
warn() { printf '   ⚠️  %s\n' "$1"; }

# ── 头部 ───────────────────────────────────
echo "════════ 周一验证清单 ════════"
echo "当前时间: $(date '+%Y-%m-%d %H:%M %Z')"
echo "HEAD: $(git rev-parse --short origin/main 2>/dev/null || echo 'N/A')"
echo ""

# ── 1. review 检查（盘后补充成交，应 ≥ 06:23 北京）──
echo "── 1. review 检查（盘后补充成交，应 ≥ 06:23 北京）──"
review_log=$(git log origin/main --since="24 hours ago" --oneline 2>&1)
review_hits=$(printf '%s\n' "$review_log" | grep -i "盘后补充成交" | head -3)
if [ -n "$review_hits" ]; then
  ok "近 24h 发现盘后补充成交提交："
  printf '%s\n' "$review_hits" | sed 's/^/      /'
else
  warn "近 24h 未匹配 '盘后补充成交' 提交（可能未到执行时间，或 commit 文案不同）"
fi
# 补充：positions 表头是否含 Last_Update（补充成交的落地标志）
lu_hdr=$(git show origin/main:portfolio_50000_positions.csv 2>&1 | head -1)
if printf '%s\n' "$lu_hdr" | grep -q "Last_Update"; then
  ok "portfolio_50000_positions.csv 含 Last_Update 字段（补充成交已落地）"
else
  warn "positions 表头未见 Last_Update 字段：$lu_hdr"
fi

# ── 2. scan 检查（persist scan，应 ≥ 21:07 北京）──
echo "── 2. scan 检查（persist scan，应 ≥ 21:07 北京）──"
scan_hits=$(git log origin/main --since="24 hours ago" --oneline 2>&1 | grep -iE "persist scan|scan" | head -3)
if [ -n "$scan_hits" ]; then
  ok "近 24h 发现 scan 相关提交："
  printf '%s\n' "$scan_hits" | sed 's/^/      /'
else
  warn "近 24h 未匹配 scan 提交（可能未到执行时间）"
fi

# ── 3. AI 目标持仓 ──
echo "── 3. AI 目标持仓（portfolio_50000_target.csv）──"
tgt_raw=$(git show origin/main:portfolio_50000_target.csv 2>&1)
if printf '%s\n' "$tgt_raw" | grep -q "fatal: Path"; then
  bad "portfolio_50000_target.csv 不存在于 origin/main（flag 未开或尚未生成）"
else
  tgt_lines=$(printf '%s\n' "$tgt_raw" | grep -c .)
  if [ "$tgt_lines" -ge 2 ]; then
    ok "存在，共 $tgt_lines 行（含表头），预览前 3 行："
    printf '%s\n' "$tgt_raw" | head -3 | sed 's/^/      /'
  else
    warn "文件仅表头或为空（0 条目标）"
  fi
fi

# ── 4. quant-research 检查 ──
echo "── 4. quant-research 检查 ──"
q_csv=$(git show origin/main:quant_factor_backtest.csv 2>&1)
q_log=$(git log origin/main --oneline 2>&1 | grep -i "quant" | head -3)
if ! printf '%s\n' "$q_csv" | grep -q "fatal: Path"; then
  ok "quant_factor_backtest.csv 存在"
elif [ -n "$q_log" ]; then
  warn "quant_factor_backtest.csv 未直接命中，但有 quant 相关提交："
  printf '%s\n' "$q_log" | sed 's/^/      /'
else
  warn "未见 quant 产物或相关提交（可能本周未跑）"
fi

# ── 5. news 检查（market_relevant 分布）──
echo "── 5. news 检查（market_relevant 分布）──"
news_raw=$(git show origin/main:dashboard/data/news_data.json 2>&1)
if printf '%s\n' "$news_raw" | grep -q "fatal: Path"; then
  bad "news_data.json 不存在于 origin/main"
else
  tmpf=$(mktemp)
  printf '%s\n' "$news_raw" > "$tmpf"
  dist=$(python3 - "$tmpf" <<'PY' 2>&1
import sys, json
from collections import Counter
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        d = json.load(f)
except Exception as e:
    print("PARSE_ERR", e); raise SystemExit
# news_data.json: market_news / error 均在顶层（与 dashboard_data.json 的嵌套 news 不同）
err = (d.get("error") if isinstance(d, dict) else None)
items = (d.get("market_news") if isinstance(d, dict) else None) or []
print("news_error: %s" % ("NONE" if not err else err))
print("market_news 条数:", len(items))
c = Counter(str(x.get("market_relevant")) for x in items)
for k, v in sorted(c.items()):
    print("  market_relevant=%s : %d" % (k, v))
PY
)
  rm -f "$tmpf"
  if printf '%s\n' "$dist" | grep -q "PARSE_ERR"; then
    warn "news_data.json 解析失败：$(printf '%s\n' "$dist" | head -1)"
  elif printf '%s\n' "$dist" | grep -q "^news_error: NONE$"; then
    ok "market_relevant 分布统计完成（无 error）："
    printf '%s\n' "$dist" | sed 's/^/      /'
  else
    warn "news_data.json 含 error 字段（最近抓取可能失败），仍统计分布："
    printf '%s\n' "$dist" | sed 's/^/      /'
  fi
fi

# ── 6. 冷却字段（Cooldown_Until 列）──
echo "── 6. 冷却字段（Cooldown_Until 列）──"
hdr=$(git show origin/main:portfolio_50000_positions.csv 2>&1 | head -1)
if printf '%s\n' "$hdr" | grep -q "Cooldown_Until"; then
  ok "positions 表头含 Cooldown_Until 列"
else
  bad "positions 表头未见 Cooldown_Until：$hdr"
fi

# ── 7. 止损记录（Intraday Stop Loss）──
echo "── 7. 止损记录（Intraday Stop Loss）──"
txn_raw=$(git show origin/main:portfolio_50000_transactions.csv 2>&1)
if printf '%s\n' "$txn_raw" | grep -q "fatal: Path"; then
  bad "transactions 文件不存在于 origin/main"
else
  cnt=$(printf '%s\n' "$txn_raw" | grep -c "Intraday Stop Loss")
  if [ "$cnt" -gt 0 ]; then
    ok "发现 $cnt 条 Intraday Stop Loss 记录（盘中止损横幅应显示）"
  else
    warn "未发现 Intraday Stop Loss 记录（若今日未触发机械止损，属正常）"
  fi
fi

# ── 8. 下一周一 21:00（北京）倒计时 ──
echo "── 8. 下一周一 21:00（北京）倒计时 ──"
next_mon=$(python3 - <<'PY' 2>&1
import datetime
bj = datetime.timezone(datetime.timedelta(hours=8))
now = datetime.datetime.now(bj)
days_ahead = (0 - now.weekday()) % 7   # 周一=0
if days_ahead == 0 and (now.hour, now.minute) >= (21, 0):
    days_ahead = 7
target = (now + datetime.timedelta(days=days_ahead)).replace(hour=21, minute=0, second=0, microsecond=0)
delta = target - now
tot = int(delta.total_seconds())
dys, rem = divmod(tot, 86400)
hrs, rem2 = divmod(rem, 3600)
mins, _ = divmod(rem2, 60)
print("目标: %s (北京) | 剩余 %d 天 %d 小时 %d 分" % (target.strftime('%Y-%m-%d %H:%M'), dys, hrs, mins))
PY
)
printf '%s\n' "$next_mon" | sed 's/^/   /'

# ── 9. flag 状态（应全为未设 / 关闭）──
echo "── 9. flag 状态（应全为未设 / 关闭） ──"
# 检查 repo variables 是否被误设
if grep -q "ENABLE_SCAN_BUY_DECISION" .github/workflows/*.yml 2>/dev/null; then
  # 检查是否被硬编码为 "1"
  if grep -q "ENABLE_SCAN_BUY_DECISION: \"1\"" .github/workflows/*.yml 2>/dev/null; then
    echo "❌ ENABLE_SCAN_BUY_DECISION 被硬编码为 1（应为 vars. 引用）"
  else
    echo "✅ ENABLE_SCAN_BUY_DECISION 仅 vars. 引用（周一走旧路径）"
  fi
fi

# 检查 ENABLE_MACRO_PANEL / ENABLE_OPTIONS_WHEEL 未被激活
for flag in ENABLE_MACRO_PANEL ENABLE_OPTIONS_WHEEL; do
  if grep -q "$flag: \"1\"" .github/workflows/*.yml 2>/dev/null; then
    echo "❌ $flag 被激活（周一前不应激活）"
  else
    echo "✅ $flag 未激活"
  fi
done

# ── 10. review 双跑检查（周二专用）──
echo "── 10. review 双跑检查（周二专用）──"
# ① 先看当前是"双开"还是"单开"
REVIEW_HAS_SCHEDULE=$(grep -c "schedule:" .github/workflows/review.yml 2>/dev/null || echo 0)
if [ "$REVIEW_HAS_SCHEDULE" -ge 1 ]; then
  echo "   状态：双开（GitHub schedule + cron-job.org）"
else
  echo "   状态：单开（仅 cron-job.org）"
fi
# ② 数 review 提交
git fetch origin --quiet 2>/dev/null
REVIEW_COMMITS=$(git log origin/main --since="24 hours ago" --oneline 2>/dev/null | grep -c "盘后补充成交" || echo 0)
# ③ 按状态+commit 数给结论
if [ "$REVIEW_HAS_SCHEDULE" -ge 1 ] && [ "$REVIEW_COMMITS" -ge 2 ]; then
  echo "✅ review 双跑成功（$REVIEW_COMMITS 次提交）"
  echo "   → 去 Actions 确认有 $REVIEW_COMMITS 个 run"
elif [ "$REVIEW_HAS_SCHEDULE" -ge 1 ] && [ "$REVIEW_COMMITS" -eq 1 ]; then
  echo "⚠️  review 只跑了 1 次——去 Actions 页面看有几个 run："
  echo "      · 1 个 run → 外部触发未生效"
  echo "      · 2 个 run（1 个被取消）→ concurrency 冲突"
elif [ "$REVIEW_COMMITS" -eq 0 ]; then
  echo "⏳ review 尚未跑（未到时间或失败）"
else
  echo "⚠️  单开状态（外部触发）——$REVIEW_COMMITS 次提交"
fi

echo ""
echo "════════ 完成 ════════"
echo "以上均为只读检查（git log / git show / git fetch），未修改任何文件。可重复运行。"
