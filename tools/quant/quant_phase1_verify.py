#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quant Phase 1 第一次真实生产运行后 —— 只读验证脚本。

【严格 READ ONLY】
  - 不写入 /tmp/us 任何文件
  - 不修改任何代码
  - 不 commit / 不 push
  - 全部内容通过 `git cat-file -p <ref>:<path>` 直接从远端 ref 读取，
    绝不改动本地工作区 / HEAD / 索引

用法：
  python3 /tmp/quant_phase1_verify.py [--ref origin/main]

覆盖 15 项核验：
  1  snapshot 是否生成          2  生产路径是否正确
  3  Scan_Date 是否为本次       4  Ticker 数量是否合理
  5  是否覆盖完整 snapshot_pool  6  Gate_Status 是否存在
  7  8 个 Quant Factor 是否存在  8  Factor 数值异常检查（NaN/inf/量级）
  9  唯一键 Scan_Date|Ticker     10 浮点尾数污染
  11 dashboard-data 是否同步     12 Dashboard Quant 状态是否转换
  13 Dashboard 其它数据未被破坏  14 Scan workflow 是否成功
  15 Scan 成功但 snapshot 未落地 → 定位日志
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import math
import subprocess
import sys
from collections import Counter

REPO = "/tmp/us"

FACTORS = [
    "Momentum_5D_Pct",
    "Momentum_20D_Pct",
    "Momentum_60D_Pct",
    "Realized_Volatility_20D_Pct",
    "Volume_Ratio_20D",
    "ZScore_20D",
    "Beta_60D_SPY",
    "Stock_RS_20D_vs_SPY",
]

# 各因子的合理量级边界（超出即标记为可疑，不视为致命）
BOUNDS = {
    "Momentum_5D_Pct": (-100.0, 300.0),
    "Momentum_20D_Pct": (-100.0, 500.0),
    "Momentum_60D_Pct": (-100.0, 1000.0),
    "Realized_Volatility_20D_Pct": (0.0, 500.0),
    "Volume_Ratio_20D": (0.0, 100.0),
    "ZScore_20D": (-15.0, 15.0),
    "Beta_60D_SPY": (-10.0, 15.0),
    "Stock_RS_20D_vs_SPY": (-200.0, 200.0),
}

SNAPSHOT_PATH = "quant_factor_snapshot.csv"
DASHBOARD_JSON = "dashboard/data/dashboard_data.json"

results: list[tuple[str, str, str]] = []  # (status, check, detail)


def mark(status: str, check: str, detail: str = "") -> None:
    results.append((status, check, detail))
    icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌", "INFO": "ℹ️ "}[status]
    print(f"  [{icon}] {check}" + (f" — {detail}" if detail else ""))


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, timeout=120
    )


def cat_file(ref: str, path: str):
    """从 git ref 读取文件（只读不落盘）。返回 (ok, text_or_error)。"""
    r = git("cat-file", "-p", f"{ref}:{path}")
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()
    return True, r.stdout


def ref_has_file(ref: str, path: str) -> bool:
    r = git("cat-file", "-e", f"{ref}:{path}")
    return r.returncode == 0


def parse_csv(text: str):
    import csv as _csv

    rows = list(_csv.DictReader(io.StringIO(text)))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--baseline", default="a220233995651a7698ce98e1a9643e71b3a474b3",
                    help="Scan 之前的基准 commit（用于对比 Dashboard 其它数据）")
    ap.add_argument("--expect-date", default=None,
                    help="期望的 Scan_Date（默认按当日 UTC 推算）")
    args = ap.parse_args()

    print("=" * 74)
    print("Quant Phase 1 · 第一次真实生产运行验证（READ ONLY）")
    print("=" * 74)
    now_utc = dt.datetime.now(dt.timezone.utc)
    print(f"验证时间(UTC) : {now_utc:%Y-%m-%d %H:%M:%S}")
    print(f"目标 ref      : {args.ref}")

    # 先同步远端（只更新 remote-tracking ref，不动工作区/HEAD）
    r = git("fetch", "origin")
    if r.returncode != 0:
        print(f"[FATAL] git fetch 失败：{r.stderr.strip()}")
        return 2
    head = git("rev-parse", args.ref).stdout.strip()
    print(f"{args.ref:14}: {head[:12]}")
    print(f"本地 HEAD     : {git('rev-parse','HEAD').stdout.strip()[:12]} （不参与校验，仅显示）")
    print()

    expected_date = args.expect_date
    if expected_date is None:
        # Scan cron 13:07 UTC → 美东 09:07 → 美东日期通常与当日 UTC 日期一致
        expected_date = now_utc.strftime("%Y-%m-%d")

    # ---------------------------------------------------------------
    print("── 14. Scan workflow 是否成功完成 ─────────────────────────")
    # 无 GH token，改以"远端是否出现 Scan 产物提交"作为成功证据
    log = git("log", "--format=%H|%ad|%s", "--date=iso", "-n", "12", args.ref).stdout.strip().splitlines()
    scan_commits = [l for l in log if "scan" in l.split("|", 2)[-1].lower()]
    recent = []
    for l in log:
        parts = l.split("|", 2)
        if len(parts) < 3:
            continue
        try:
            ts = dt.datetime.fromisoformat(parts[1]).replace(tzinfo=dt.timezone.utc)
        except Exception:
            continue
        recent.append((parts[0][:8], ts, parts[2]))
    today = now_utc.date()
    todays = [(h, t, s) for h, t, s in recent if t.date() == today]
    print(f"  远端今日({today})提交 {len(todays)} 条：")
    for h, t, s in todays[:10]:
        print(f"    {h} {t:%H:%M}Z  {s}")

    commit_files = git("show", "--stat", "--name-only", "--oneline", args.ref).stdout

    scan_ran_today = any("pending" in s.lower() or "scan" in s.lower() for _, _, s in todays)
    if scan_ran_today:
        mark("PASS", "Scan 今日已在远端产出提交（pending/scan 关键字）")
    else:
        mark("WARN", "未在远端发现今日 Scan 提交产物", "可能尚未运行或未 commit")
    print()

    # ---------------------------------------------------------------
    print("── 1 / 2. snapshot 是否生成 & 生产路径是否正确 ───────────")
    exists = ref_has_file(args.ref, SNAPSHOT_PATH)
    if not exists:
        if not scan_ran_today:
            mark("FAIL", "quant_factor_snapshot.csv 不存在（远端仓库根目录）",
                 "远端今日尚未检测到 Scan 提交 → 属【Scan 尚未运行/尚未产出】，非写入失败")
            print()
            print("=" * 74)
            print("⏳ 结论：Scan 尚未运行或尚未 commit，snapshot 属于「等待中」而非「失败」")
            print("=" * 74)
            return 3
        mark("FAIL", "quant_factor_snapshot.csv 存在于远端仓库根目录", "不存在")
        print()
        print("=" * 74)
        print("❌ 结论：Scan 成功但 Quant Snapshot 未落地（见下方第 15 项定位）")
        print("=" * 74)
        # 15. 定位日志位置
        print()
        print("── 15. Scan 成功但 snapshot 未落地 → 失败定位 ───────────")
        print("  产出责任链（按代码审计结论）：")
        print("    scan.py:3709  build_stock_pool()        → 计算 ext_factors")
        print("    scan.py:3726  snapshot_pool = pool_data  → 取全池引用")
        print("    scan.py:3727  apply_entry_quality_gate() → 原地标 Gate_Status")
        print("    scan.py:3728-3731  try: write_factor_snapshot(...)")
        print("            except Exception as _qf_e: print(f'⚠️ [Quant Factor Lab] 因子快照写入失败"
              "（不影响主流程）：...')")
        print()
        print("  ⚠️ 关键点：该 try/except 只 print warning，不会让 Scan 失败、不会改退出码。")
        print("     因此 GitHub Actions 可能全绿，但 snapshot 缺失。")
        print()
        print("  需在 GitHub Actions run 日志中检索以下行：")
        print("    ① ⚠️ [Quant Factor Lab] 因子快照写入失败   ← 直接证据")
        print("    ② ✅ 技术面完成：N 只                      ← pool 是否非空（N=0 则不进 snapshot）")
        print("    ③ 🛡️ [硬门槛] x/y 只通过                  ← gate 是否执行到")
        print("    ④ ⚠️ 今日扫描无有效标的                    ← scan.py:3711 提前退出，永不写 snapshot")
        print()
        print("  需检查的 early-exit 点（位于 write_factor_snapshot 之前，会跳过落盘）：")
        print("    scan.py:129   环境变量 CLAWSOCKET_* 缺失 → sys.exit(1)")
        print("    scan.py:3711  pool_data 为空 → sys.exit(0)   ← 最高嫌疑")
        print("  注意：scan.py:3733 的 gate 后空池退出在写入之后，不会导致缺失。")
        return 1

    ok, text = cat_file(args.ref, SNAPSHOT_PATH)
    if not ok:
        mark("FAIL", "snapshot 读取失败", text)
        return 1
    rows = parse_csv(text)
    mark("PASS", f"quant_factor_snapshot.csv 已生成（远端根目录，行数 {len(rows)}）",
         "生产路径正确")
    print()

    if not rows:
        mark("FAIL", "snapshot 为空（0 数据行）", "Scan 写了头但无数据")
        return 1

    cols = list(rows[0].keys())

    # ---------------------------------------------------------------
    print("── 3. Scan_Date 是否为本次 Scan 日期 ─────────────────────")
    dates = Counter((r.get("Scan_Date") or "").strip() for r in rows)
    print(f"  Scan_Date 分布：{dict(sorted(dates.items()))}")
    if expected_date in dates:
        mark("PASS", f"Scan_Date 命中本次日期 {expected_date}（{dates[expected_date]} 行）")
    else:
        mark("WARN", f"未发现期望日期 {expected_date}", f"实际 {list(dates)}")
    tech_dates = Counter((r.get("Technical_Date") or "").strip() for r in rows)
    print(f"  Technical_Date 分布：{dict(sorted(tech_dates.items()))}")
    bad_align = sum(1 for r in rows if r.get("Technical_Date", "") > r.get("Scan_Date", ""))
    if bad_align:
        mark("FAIL", f"Technical_Date > Scan_Date 的异常行 {bad_align} 条（look-ahead 风险）")
    else:
        mark("PASS", "Technical_Date <= Scan_Date 全部成立（无未来日期）")
    print()

    # ---------------------------------------------------------------
    print("── 4. Ticker 数量是否合理 ────────────────────────────────")
    tickers = sorted({(r.get("Ticker") or "").strip() for r in rows if r.get("Ticker")})
    n = len(tickers)
    print(f"  Ticker 数 = {n}")
    if 150 <= n <= 300:
        mark("PASS", f"Ticker 数量 {n} 落在合理区间 [150,300]（候选池 Top300）")
    elif 80 <= n < 150:
        mark("WARN", f"Ticker 数量 {n} 偏低", "可能因 len(df)>=40 过滤或行情失败较多")
    elif n == 0:
        mark("FAIL", "Ticker 数为 0")
    else:
        mark("WARN", f"Ticker 数量 {n} 超出预期区间", "需复核候选池")
    empty_tk = sum(1 for r in rows if not (r.get("Ticker") or "").strip())
    if empty_tk:
        mark("WARN", f"空 Ticker 行 {empty_tk} 条")
    print()

    # ---------------------------------------------------------------
    print("── 5. 是否覆盖完整 snapshot_pool ─────────────────────────")
    # 完整池的证据：Gate 存在多状态（含失败项），而非只剩 PASS_PRE_AI
    gate = Counter((r.get("Gate_Status") or "").strip() for r in rows)
    print(f"  Gate_Status 分布：{dict(sorted(gate.items()))}")
    non_pass = sum(v for k, v in gate.items() if k and k != "PASS_PRE_AI")
    if non_pass > 0:
        mark("PASS", f"包含 {non_pass} 条 Gate 未通过项 → 确为「全池」而非仅通过者（无 selection bias）")
    elif "PASS_PRE_AI" in gate:
        mark("WARN", "snapshot 仅含 PASS_PRE_AI", "疑似只写了 gate 通过子集")
    else:
        mark("WARN", "Gate_Status 列无有效取值")
    print()

    # ---------------------------------------------------------------
    print("── 6. Gate_Status 是否存在 ───────────────────────────────")
    if "Gate_Status" in cols:
        filled = sum(1 for r in rows if (r.get("Gate_Status") or "").strip())
        pct = filled / len(rows) * 100
        if pct >= 99.0:
            mark("PASS", f"Gate_Status 填充率 {filled}/{len(rows)} ({pct:.1f}%)")
        else:
            mark("WARN", f"Gate_Status 填充率 {filled}/{len(rows)} ({pct:.1f}%)")
    else:
        mark("FAIL", "snapshot 缺少 Gate_Status 列")
    print()

    # ---------------------------------------------------------------
    print("── 7. 8 个 Quant Factor 列是否存在 ───────────────────────")
    missing = [f for f in FACTORS if f not in cols]
    if missing:
        mark("FAIL", f"缺失因子列 {missing}")
    else:
        mark("PASS", "8 个 Quant Factor 列全部存在")
    print()

    # ---------------------------------------------------------------
    print("── 8. Factor 数值异常检查（NaN / inf / 量级） ────────────")
    stats = {}
    for f in FACTORS:
        if f not in cols:
            continue
        vals, empty, badnum, infs, nans = [], 0, 0, 0, 0
        for r in rows:
            s = (r.get(f) or "").strip()
            if s == "":
                empty += 1
                continue
            low = s.lower()
            if low in ("nan", "inf", "-inf", "infinity", "-infinity"):
                nans += low.startswith("nan")
                infs += not low.startswith("nan")
                badnum += 1
                continue
            try:
                v = float(s)
            except ValueError:
                badnum += 1
                continue
            if math.isnan(v):
                nans += 1
                badnum += 1
                continue
            if math.isinf(v):
                infs += 1
                badnum += 1
                continue
            vals.append(v)
        lo, hi = BOUNDS.get(f, (-1e9, 1e9))
        oor = [v for v in vals if v < lo or v > hi]
        stats[f] = dict(n=len(vals), empty=empty, bad=badnum, inf=infs, nan=nans,
                        oor=len(oor), vmin=min(vals) if vals else None,
                        vmax=max(vals) if vals else None)
        pct_empty = empty / len(rows) * 100
        tag = "PASS"
        notes = []
        if badnum:
            tag = "FAIL"
            notes.append(f"非法值 {badnum}(nan={nans},inf={infs})")
        if oor:
            tag = "WARN" if tag == "PASS" else tag
            notes.append(f"超界 {len(oor)}")
        notes.append(f"有效 {len(vals)}/{len(rows)}, 空 {pct_empty:.1f}%")
        if vals:
            notes.append(f"范围[{min(vals):.4g},{max(vals):.4g}]")
        mark(tag, f"{f}", "; ".join(notes))

    total_bad = sum(s["bad"] for s in stats.values())
    if total_bad == 0:
        mark("PASS", "全部因子无 NaN / inf / 不可解析值")
    else:
        mark("FAIL", f"共 {total_bad} 个非法数值")
    print()

    # ---------------------------------------------------------------
    print("── 9. 唯一键 Scan_Date|Ticker 去重核验 ───────────────────")
    keys = [f"{(r.get('Scan_Date') or '').strip()}|{(r.get('Ticker') or '').strip()}" for r in rows]
    dup = [k for k, c in Counter(keys).items() if c > 1]
    if dup:
        mark("FAIL", f"唯一键重复 {len(dup)} 个", f"示例 {dup[:5]}")
    else:
        mark("PASS", f"Scan_Date|Ticker 唯一键无重复（{len(keys)} 行）")
    print()

    # ---------------------------------------------------------------
    print("── 10. 浮点尾数污染核验 ──────────────────────────────────")
    # build_snapshot_rows 对 8 factors 用 _fmt(v, 4)；Price 用 _fmt(v, 2)
    worst = {}
    for f in FACTORS:
        if f not in cols:
            continue
        m = 0
        for r in rows:
            s = (r.get(f) or "").strip()
            if s and "." in s:
                m = max(m, len(s.split(".")[1]))
        worst[f] = m
    print(f"  各因子最大小数位：{worst}")
    over = {k: v for k, v in worst.items() if v > 4}
    if over:
        mark("WARN", f"存在 >4 位小数的因子列 {over}", "预期 _fmt(v,4)")
    else:
        mark("PASS", "因子精度均 ≤4 位小数（符合 _fmt(v,4) 约定）")
    # Price 字段
    pm = 0
    for r in rows:
        s = (r.get("Price") or "").strip()
        if s and "." in s:
            pm = max(pm, len(s.split(".")[1]))
    if pm > 2:
        mark("WARN", f"Price 小数位 {pm} > 2")
    else:
        mark("PASS", f"Price 小数位 {pm} ≤ 2（符合 _fmt(v,2)）")
    print()

    # ---------------------------------------------------------------
    print("── 11 / 12. Dashboard 是否同步 & Quant 状态是否转换 ───────")
    ok, dj = cat_file(args.ref, DASHBOARD_JSON)
    if not ok:
        mark("WARN", "无法读取远端 dashboard_data.json", dj[:120])
        print()
    else:
        try:
            data = json.loads(dj)
        except Exception as e:
            data = None
            mark("WARN", "dashboard_data.json 解析失败", str(e))
        if data is not None:
            q = data.get("quant")
            if not q:
                mark("FAIL", "dashboard_data.json 缺少 quant 键",
                     "dashboard-data 尚未用新代码重跑")
            else:
                fl = q.get("factor_lab", {})
                rows_seen = fl.get("snapshot_rows")
                st = fl.get("status")
                print(f"  quant.factor_lab.status      = {st}")
                print(f"  quant.factor_lab.snapshot_rows = {rows_seen}")
                print(f"  quant.data_availability      = {q.get('data_availability')}")
                print(f"  quant.status                 = {q.get('status')}")
                if rows_seen and rows_seen > 0:
                    mark("PASS", f"Dashboard 已同步 snapshot（snapshot_rows={rows_seen}）")
                    if st == "DATA_AVAILABLE":
                        mark("PASS", "Dashboard Quant 状态已由 NOT_ENOUGH_DATA 转为 DATA_AVAILABLE")
                    else:
                        mark("WARN", f"Dashboard factor_lab.status 仍为 {st}")
                    # 一致性：dashboard 看到的行数 vs 真实文件行数
                    if rows_seen == len(rows):
                        mark("PASS", f"dashboard snapshot_rows 与文件行数一致（{rows_seen}）")
                    else:
                        mark("WARN", "行数不一致（可能 dashboard 生成早于最新 snapshot）",
                             f"dashboard={rows_seen} vs file={len(rows)}")
                else:
                    mark("WARN", "Dashboard 尚未感知 snapshot（snapshot_rows=0）",
                         "dashboard-data workflow 可能还未在此之后运行")

            # -------------------------------------------------------
            print()
            print("── 13. Dashboard 其它数据是否被 Quant 接入破坏 ──────────")
            base_ok, base_txt = cat_file(args.baseline, DASHBOARD_JSON)
            if not base_ok:
                mark("WARN", "无法读取基准 dashboard_data.json", "跳过对比")
            else:
                base = json.loads(base_txt)

                def cnt(d, path):
                    cur = d
                    for p in path:
                        if not isinstance(cur, dict) or p not in cur:
                            return None
                        cur = cur[p]
                    return len(cur) if isinstance(cur, (list, dict)) else cur

                checks = [
                    ("stocks", ["stocks"]),
                    ("review.records", ["review", "records"]),
                    ("history", ["history"]),
                    ("options", ["options"]),
                    ("runtimes", ["runtimes"]),
                ]
                for label, path in checks:
                    b, c = cnt(base, path), cnt(data, path)
                    if b == c:
                        mark("PASS", f"{label:<16} {c}（与基准一致）")
                    else:
                        mark("WARN", f"{label:<16} 基准={b} 当前={c}", "数量变化需确认")
                bp = data.get("portfolio")
                bpb = base.get("portfolio")
                if (bp is None) != (bpb is None):
                    mark("WARN", "portfolio 存在性发生变化")
                elif bp is not None and bpb is not None:
                    same_keys = set(bp.keys()) == set(bpb.keys())
                    mark("PASS" if same_keys else "WARN",
                         f"portfolio 键集合一致" if same_keys else "portfolio 键集合变化",
                         f"{len(bp or {})} 键")
                else:
                    mark("INFO", "portfolio 两版均为 null")
                # Core / Observation 拆分
                core = sum(1 for s in data.get("stocks", []) if s.get("bucket") == "Core")
                obs = sum(1 for s in data.get("stocks", []) if s.get("bucket") == "Observation")
                bcore = sum(1 for s in base.get("stocks", []) if s.get("bucket") == "Core")
                boss = sum(1 for s in base.get("stocks", []) if s.get("bucket") == "Observation")
                print(f"  Core {bcore} → {core}   Observation {boss} → {obs}")
    print()

    # ---------------------------------------------------------------
    print("=" * 74)
    n_fail = sum(1 for s, _, _ in results if s == "FAIL")
    n_warn = sum(1 for s, _, _ in results if s == "WARN")
    n_pass = sum(1 for s, _, _ in results if s == "PASS")
    print(f"汇总：PASS {n_pass} · WARN {n_warn} · FAIL {n_fail}")
    if n_fail:
        print("结论：❌ 存在致命问题，见上方 FAIL 项")
        return 1
    if n_warn:
        print("结论：⚠️ 基本可用，但有告警需人工复核")
        return 0
    print("结论：✅ Quant Phase 1 第一次真实生产运行全部核验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
