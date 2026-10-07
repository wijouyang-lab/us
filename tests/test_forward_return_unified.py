# -*- coding: utf-8 -*-
"""Forward Return 统一真源回归测试。

验证：
  1) quant_factor_backtest.forward_return_nd 是唯一真源（5D/10D/20D 行为正确）；
  2) quant_shadow 已改为复用该真源（不再有自己的 compute_forward_return）；
  3) 统一前后结果完全一致（用固定 fixture 固化）。
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from quant_factor_backtest import forward_return_nd
import quant_shadow

passed = 0
total = 0


def check(name, cond, detail=""):
    global passed, total
    total += 1
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name}  {detail}")


def make_series(n=30, start="2026-01-01", base=100.0, step=1.0):
    idx = pd.bdate_range(start, periods=n)
    vals = [base + step * i for i in range(n)]
    return pd.Series(vals, index=idx)


# ---- 1-3. 5D / 10D / 20D 正确 ----
def test_horizons():
    s = make_series(n=30, base=100.0, step=1.0)
    # T = 第 1 个交易日（index 0），close_t = 100
    t = s.index[0]
    r5 = forward_return_nd(s, t, 100.0, 5)
    r10 = forward_return_nd(s, t, 100.0, 10)
    r20 = forward_return_nd(s, t, 100.0, 20)
    # close[t+5] = 105, close[t+10] = 110, close[t+20] = 120
    check("1. 5D 正确", r5 is not None and abs(r5 - 0.05) < 1e-6, f"got {r5}")
    check("2. 10D 正确", r10 is not None and abs(r10 - 0.10) < 1e-6, f"got {r10}")
    check("3. 20D 正确", r20 is not None and abs(r20 - 0.20) < 1e-6, f"got {r20}")


# ---- 4. None（close_t 无效 / series 为空）----
def test_none():
    s = make_series(n=30)
    t = s.index[0]
    check("4. close_t=None → None", forward_return_nd(s, t, None, 5) is None)
    check("4b. close_t=0 → None", forward_return_nd(s, t, 0.0, 5) is None)
    check("4c. series=None → None", forward_return_nd(None, t, 100.0, 5) is None)
    check("4d. series 空 → None", forward_return_nd(pd.Series(dtype=float), t, 100.0, 5) is None)


# ---- 5. missing future date ----
def test_missing_future():
    s = make_series(n=5)  # 只有 5 个交易日
    t = s.index[4]  # 最后一个交易日，之后无交易日
    check("5. 未来交易日缺失 → None", forward_return_nd(s, t, 100.0, 1) is None)


# ---- 6. zero return ----
def test_zero_return():
    idx = pd.bdate_range("2026-01-01", periods=10)
    s = pd.Series([100.0] * 10, index=idx)  # 平盘
    t = idx[0]
    r = forward_return_nd(s, t, 100.0, 5)
    check("6. 零收益 → 0.0（非 None）", r == 0.0, f"got {r}")


# ---- 7. negative return ----
def test_negative_return():
    idx = pd.bdate_range("2026-01-01", periods=10)
    s = pd.Series([100.0 - i for i in range(10)], index=idx)  # 下跌
    t = idx[0]
    r = forward_return_nd(s, t, 100.0, 5)
    check("7. 负收益 → 负值", r is not None and r < 0, f"got {r}")


# ---- 8. boundary index ----
def test_boundary():
    s = make_series(n=10)
    t = s.index[0]
    r_ok = forward_return_nd(s, t, 100.0, 9)   # target = 9 = 最后一天，可用
    r_bad = forward_return_nd(s, t, 100.0, 10)  # target = 10 = 越界，None
    check("8. 边界 index（最后一个可用）", r_ok is not None, f"got {r_ok}")
    check("8b. 越界 → None", r_bad is None, f"got {r_bad}")


# ---- 9-10. 统一前后结果一致（固定 fixture 固化，覆盖原 backtest/shadow 行为）----
def test_consistent_with_legacy():
    idx = pd.bdate_range("2026-01-01", periods=40)
    vals = [100.0 + i for i in range(40)]
    vals[10] = 110.0
    vals[11] = 110.0
    vals[20] = 80.0
    s = pd.Series(vals, index=idx)
    # 与统一前 fixture 对比的期望值（旧 forward_return_nd 输出）
    expect = {
        ("2026-01-05", 100.0, 5): 0.07,
        ("2026-01-05", 100.0, 10): 0.12,
        ("2026-01-05", 100.0, 20): 0.22,
    }
    ok = True
    for (td, ct, n), exp in expect.items():
        r = forward_return_nd(s, td, ct, n)
        if r is None or abs(r - exp) > 1e-6:
            ok = False
            print(f"      {td}/{n}: got {r}, expect {exp}")
    check("9. 与旧 backtest 结果一致（5D/10D/20D）", ok)


def test_shadow_uses_unified():
    # shadow 不再有自己的 compute_forward_return，且复用的是同一个 forward_return_nd
    check("10. shadow 无自己的 compute_forward_return",
          not hasattr(quant_shadow, "compute_forward_return"))
    check("10b. shadow 复用 forward_return_nd 真源",
          getattr(quant_shadow, "forward_return_nd") is forward_return_nd)


# ---- 11. deterministic ----
def test_deterministic():
    s = make_series(n=30)
    t = s.index[0]
    outs = {forward_return_nd(s, t, 100.0, n) for n in (5, 10, 20)}
    outs2 = {forward_return_nd(s, t, 100.0, n) for n in (5, 10, 20)}
    check("11. 确定性（重复运行结果一致）", outs == outs2)


# ---- 12. no future leakage（只读 T 之后，不读 T 及之前）----
def test_no_future_leakage():
    # 构造：T 之前的 bar 全是异常值（999），T 日 = 100，T+1..T+6 = 101..106。
    # 验证 forward_return_nd 只读 T 之后的 bar，绝不受 T 之前异常值影响。
    idx = pd.bdate_range("2026-01-01", periods=12)
    base = [999.0] * 5 + [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0]
    s = pd.Series(base, index=idx)
    t = idx[5]  # T = 第 6 个交易日，close = 100
    r = forward_return_nd(s, t, 100.0, 5)  # close[T+5] = 105
    check("12. 无未来泄漏（只读 T 之后 bar）", r is not None and abs(r - 0.05) < 1e-6, f"got {r}")


def main():
    test_horizons()
    test_none()
    test_missing_future()
    test_zero_return()
    test_negative_return()
    test_boundary()
    test_consistent_with_legacy()
    test_shadow_uses_unified()
    test_deterministic()
    test_no_future_leakage()
    print(f"\n结果: 通过 {passed} / {total}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
