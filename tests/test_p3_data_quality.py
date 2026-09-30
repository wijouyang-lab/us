# -*- coding: utf-8 -*-
"""P3 数据质量回归测试（离线，纯函数）。

固化 P3 深度审计的确定性规则：
  - orphan lineage 分类：DETERMINISTIC_REPAIR / MULTIPLE_POSSIBLE_LINEAGE /
    NO_LINEAGE / ALREADY_CORRECT_EMPTY；
  - Rec_Price collision 分类：EARLY_BACKFILL_CORRECTION / FLOAT_PRECISION_NOISE / SOURCE_MISMATCH；
  - 只有 DETERMINISTIC_REPAIR 才允许修复，其余 KEEP（不猜）；
  - 修复不得触碰 trade_history / PnL / milestone / Stop_Loss / Exit。

这是对 P3 审计结论的规则性验证，不读取 production CSV。
"""

# ---------------------------------------------------------------------------
# 纯函数：P3 分类规则（与 P3 审计脚本一致的确定性逻辑）
# ---------------------------------------------------------------------------

def classify_orphan(tag, trade_history_statuses):
    """返回 (classification, action, reason)。"""
    if tag == "Trap_Warning":
        return ("ALREADY_CORRECT_EMPTY", "KEEP",
                "Trap_Warning=诱多对照组，review.py 不追踪，空 Status 符合数据模型")
    if len(set(trade_history_statuses)) > 1:
        return ("MULTIPLE_POSSIBLE_LINEAGE", "KEEP",
                f"trade_history 多个 Status {trade_history_statuses}，无法唯一确定")
    if not trade_history_statuses:
        return ("NO_LINEAGE", "KEEP", "无 trade_history lineage")
    return ("MULTIPLE_POSSIBLE_LINEAGE", "KEEP",
            f"trade_history Status={trade_history_statuses}，英文无法唯一映射中文（一对多）")


def classify_collision(rec_price_values, trade_history_price):
    """返回 (classification, action)。"""
    uniq = list(dict.fromkeys([round(float(v), 6) for v in rec_price_values]))
    if len(uniq) == 1:
        return ("FLOAT_PRECISION_NOISE", "KEEP")
    last = round(float(rec_price_values[-1]), 6)
    th = round(float(trade_history_price), 6) if trade_history_price else None
    if th is not None and abs(last - th) < 1e-4:
        return ("EARLY_BACKFILL_CORRECTION", "REVIEW")  # 触及交易基准，先只报告
    return ("SOURCE_MISMATCH", "REVIEW")


def apply_p3_repair(records, classify_fn):
    """只对 DETERMINISTIC_REPAIR 的字段执行修复；其余保持原样。"""
    out = []
    for r in records:
        new = dict(r)
        cls, action, _ = classify_fn(r["tag"], r["trade_statuses"])
        if cls == "DETERMINISTIC_REPAIR" and action == "REPAIR":
            new["status"] = r["repair_status"]
            new["rec_count"] = r["repair_rec_count"]
        out.append(new)
    return out


results = []
def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


print("== orphan lineage 分类 ==")
# 1. deterministic lineage（仅当存在唯一可映射时才出现——本规则下 Trap_Warning 是 empty-valid 而非 repair）
#    构造一个真正的 DETERMINISTIC_REPAIR 场景：同 key 有唯一非空快照（P2 已处理的那种）
def classify_orphan_p2(has_nonempty_snapshot, snapshot_status):
    """P2 已确认的确定性场景：同 key 存在唯一非空快照。"""
    if has_nonempty_snapshot and snapshot_status:
        return ("DETERMINISTIC_REPAIR", "REPAIR", snapshot_status)
    return ("NO_LINEAGE", "KEEP", "无同 key 非空快照")

check("1a. 同key唯一非空快照 -> DETERMINISTIC_REPAIR",
      classify_orphan_p2(True, "持仓中")[0] == "DETERMINISTIC_REPAIR")
check("1b. 无同key非空快照 -> NO_LINEAGE",
      classify_orphan_p2(False, None)[0] == "NO_LINEAGE")

# 2. ambiguous lineage -> 不修
c = classify_orphan("Observation", ["Observation_Closed", "Dropped"])
check("2. ambiguous(多Status) -> MULTIPLE_POSSIBLE_LINEAGE 不修",
      c[0] == "MULTIPLE_POSSIBLE_LINEAGE" and c[1] == "KEEP")

# 3. no lineage -> 不修
c = classify_orphan("Observation", [])
check("3. no lineage -> NO_LINEAGE 不修", c[0] == "NO_LINEAGE" and c[1] == "KEEP")

# 4. empty-but-valid -> 不修
c = classify_orphan("Trap_Warning", ["Dropped"])
check("4. Trap_Warning empty-valid -> ALREADY_CORRECT_EMPTY 不修",
      c[0] == "ALREADY_CORRECT_EMPTY" and c[1] == "KEEP")

print("== Rec_Price collision 分类 ==")
# 5. collision detection
check("5a. 浮点噪声(round后1值) -> FLOAT_PRECISION_NOISE",
      classify_collision(["196.43499755859375", "196.43499755859372"], "196.4349975585937")[0]
      == "FLOAT_PRECISION_NOISE")
check("5b. 真实漂移 -> EARLY_BACKFILL_CORRECTION",
      classify_collision(["20.18000030517578", "19.0"], "19.0")[0] == "EARLY_BACKFILL_CORRECTION")

# 6. Rec_Price evidence validation：后期值 == trade_history Price 才是 backfill correction
check("6. 后期==trade_history Price -> 证据成立(REVIEW 而非自动修复)",
      classify_collision(["20.18", "19.0"], "19.0")[1] == "REVIEW")
check("6b. 后期!=trade_history Price -> SOURCE_MISMATCH",
      classify_collision(["20.18", "19.0"], "19.5")[0] == "SOURCE_MISMATCH")

print("== 数据不变性 ==")
# fixture 记录：repair 只改 status/rec_count
recs = [
    {"ticker": "X", "tag": "Observation", "trade_statuses": ["Observation_Closed"],
     "status": "", "rec_count": "", "repair_status": "观察推荐", "repair_rec_count": "1",
     "rec_price": "20.0", "pnl_5d": "1.0", "stop_loss": "18", "exit_price": ""},
]
# 非 DETERMINISTIC 场景（MULTIPLE）→ 不修
after = apply_p3_repair(recs, lambda tag, ts: ("MULTIPLE_POSSIBLE_LINEAGE", "KEEP", ""))
b, a = recs[0], after[0]
check("7/8/9. 非deterministic不触碰任何字段", b == a)

# 构造 DETERMINISTIC 场景 → 只改 status/rec_count，其余字段不变
def cls_det(tag, ts):
    return ("DETERMINISTIC_REPAIR", "REPAIR", "")
recs2 = [dict(recs[0])]
after2 = apply_p3_repair(recs2, cls_det)
b2, a2 = recs2[0], after2[0]
check("7. repair 仅改 status/rec_count", a2["status"] == "观察推荐" and a2["rec_count"] == "1")
check("8. 不改 PnL", a2["pnl_5d"] == b2["pnl_5d"])
check("9. 不改 milestone 基准字段", a2["rec_price"] == b2["rec_price"] and a2["stop_loss"] == b2["stop_loss"])

# 10. deterministic（相同输入 -> 相同输出）
out1 = apply_p3_repair([dict(recs[0])], cls_det)
out2 = apply_p3_repair([dict(recs[0])], cls_det)
check("10. deterministic", out1 == out2)

# 11. idempotent（第二次运行 0 变化）
out3 = apply_p3_repair(out1, cls_det)
check("11. idempotent", out1 == out3)

# 12. non-target records 0 change（只有 X 是 DETERMINISTIC_REPAIR，Y 是非目标）
def cls_only_x(tag, ts):
    if tag == "Observation":
        return ("DETERMINISTIC_REPAIR", "REPAIR", "")
    return ("MULTIPLE_POSSIBLE_LINEAGE", "KEEP", "")

mixed = [dict(recs[0]), {"ticker": "Y", "tag": "Core_Dragon", "trade_statuses": ["Active"],
                          "status": "持仓中", "rec_count": "2", "repair_status": "", "repair_rec_count": "",
                          "rec_price": "30.0", "pnl_5d": "", "stop_loss": "28", "exit_price": ""}]
out_mixed = apply_p3_repair(mixed, cls_only_x)
check("12. 非目标记录 0 变化", out_mixed[1] == mixed[1])

# 汇总
failed = [n for n, c in results if not c]
print(f"\n结果：通过 {len(results)-len(failed)} / {len(results)}")
if failed:
    print("失败：", failed)
    raise SystemExit(1)
print("全部通过 ✅")
