# -*- coding: utf-8 -*-
"""`ENABLE_STOP_LOSS_SYNC` 门控的移动止损同步测试。

背景（见 docs/STOPLOSS_ROOT_CAUSE.md）：账本 `portfolio_50000_positions.csv` 的
`Stop_Loss` 唯一写入点是建仓（`portfolio_50000.py:555`），持仓期间永不更新；
而 review 的移动止损落在 `trade_history.csv`。结果卡片显示的是冻结的初始止损，
与 review 的移动止损不一致（可能放宽止损线）。

本功能（方案 C）在 `mark_to_market()` 里把 trade_history 的移动止损同步进账本行，
**由 `ENABLE_STOP_LOSS_SYNC` 门控，默认关闭**；关闭时行为与加此功能前逐字节一致。

覆盖：
  1. flag 未设 → `Stop_Loss` 不变，且整行字段与"完全不传 recs"逐字段一致（硬证据）
  2. flag 开 + recs 有移动止损 → `Stop_Loss` 被同步
  3. flag 开 + recs 该字段缺失 / RecID 未命中 / 值非法 → 不崩，原值保留（fail-closed）
  4. flag 开 + 内部异常 → 打印警告，主流程继续（返回值仍正确）
  5. `run(price_only=True)` 端到端：flag 关不改 CSV；flag 开把移动止损写进 CSV
"""
import csv

import pytest
from decimal import Decimal

import portfolio_50000 as pf

RID = pf.rec_id_of("ANET", "2026-10-07", "Core_Dragon")
OLD_STOP = "197.69"
NEW_STOP = "210.24"
TODAY = "2026-10-13"


def _pos(**over):
    p = {
        "Ticker": "ANET",
        "Status": "OPEN",
        "Shares": "10",
        "Entry_Price": "211.30",
        "Current_Price": "216.00",
        "Stop_Loss": OLD_STOP,
        "Recommendation_ID": RID,
    }
    p.update(over)
    return p


def _prices():
    return {"ANET": {"current": Decimal("216.00")}}


def _recs(stop=NEW_STOP):
    return {RID: {"Recommendation_ID": RID, "Ticker": "ANET", "Stop_Loss": stop}}


class _BoomDict(dict):
    """非空 dict，但 .get() 抛异常 —— 用来触发同步逻辑的内部异常分支。"""

    def __init__(self):
        super().__init__({"x": 1})

    def get(self, *a, **k):          # noqa: D102
        raise RuntimeError("boom")


# --------------------------------------------------------------------------- #
# 1) flag 关：Stop_Loss 不变，且整行与"不传 recs"逐字段一致
# --------------------------------------------------------------------------- #
def test_flag_unset_stop_loss_unchanged(monkeypatch):
    monkeypatch.delenv("ENABLE_STOP_LOSS_SYNC", raising=False)
    pos = _pos()
    pf.mark_to_market([pos], _prices(), TODAY, _recs())
    assert pos["Stop_Loss"] == OLD_STOP, "flag 未设时绝不允许改动 Stop_Loss"


def test_flag_off_fields_identical_to_no_recs(monkeypatch):
    """硬证据：flag 关 + 传了 recs 的结果，必须与「完全不传 recs」逐字段一致。"""
    monkeypatch.delenv("ENABLE_STOP_LOSS_SYNC", raising=False)

    with_recs = _pos()
    without_recs = _pos()
    r1 = pf.mark_to_market([with_recs], _prices(), TODAY, _recs())
    r2 = pf.mark_to_market([without_recs], _prices(), TODAY, None)

    assert with_recs == without_recs, f"flag 关时两种调用产生了不同结果：{with_recs} vs {without_recs}"
    assert r1 == r2
    assert with_recs["Stop_Loss"] == OLD_STOP


@pytest.mark.parametrize("val", ["0", "true", "yes", "", "2", "TRUE"])
def test_only_exactly_1_enables(monkeypatch, val):
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", val)
    pos = _pos()
    pf.mark_to_market([pos], _prices(), TODAY, _recs())
    assert pos["Stop_Loss"] == OLD_STOP, f"只有 '1' 才应开启，val={val!r} 不应生效"


# --------------------------------------------------------------------------- #
# 2) flag 开：同步成功
# --------------------------------------------------------------------------- #
def test_flag_on_syncs_moving_stop(monkeypatch):
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    pos = _pos()
    pf.mark_to_market([pos], _prices(), TODAY, _recs())
    assert pos["Stop_Loss"] == NEW_STOP


def test_flag_on_recs_none_is_noop(monkeypatch):
    """flag 开但没传 recs（例如调用方未加载）→ 也不能崩，原值保留。"""
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    pos = _pos()
    pf.mark_to_market([pos], _prices(), TODAY, None)
    assert pos["Stop_Loss"] == OLD_STOP


def test_flag_on_same_value_no_rewrite(monkeypatch, capsys):
    """新旧值相同 → 不写、不打日志（避免无意义的 CSV 变更）。"""
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    pos = _pos(Stop_Loss=NEW_STOP)
    pf.mark_to_market([pos], _prices(), TODAY, _recs())
    assert pos["Stop_Loss"] == NEW_STOP
    assert "[stop-sync]" not in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# 2b) "$" 前缀归一化 —— 这是本功能能否真正生效的关键
#     实测：positions.csv 的 4 只持仓全是 "$214.76"/"$197.69"/…，
#     而 dec("$197.69") is None → _run_intraday_stop 会 continue 跳过 → 机械止损失效。
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw,expected", [
    ("$210.24", "210.24"),
    ("210.24", "210.24"),
    (" $210.24 ", "210.24"),
    ("$1,234.56", "1234.56"),
])
def test_flag_on_dollar_prefix_normalized(monkeypatch, raw, expected):
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    pos = _pos()
    pf.mark_to_market([pos], _prices(), TODAY, _recs(stop=raw))
    assert pos["Stop_Loss"] == expected


def test_synced_value_is_parseable_by_dec(monkeypatch):
    """核心目的：同步后的值必须能被 `dec()` 解析。

    否则 `_run_intraday_stop` 仍会在 `if stop is None: continue` 处跳过该持仓，
    等于这次修复白做。
    """
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    pos = _pos(Stop_Loss="$197.69")                       # 历史货币格式仍应可解析
    assert pf.dec(pos["Stop_Loss"]) == Decimal("197.69")  # 解析旧仓位值，不应跳过止损
    pf.mark_to_market([pos], _prices(), TODAY, _recs(stop="$210.24"))
    assert pos["Stop_Loss"] == "210.24"
    assert pf.dec(pos["Stop_Loss"]) == Decimal("210.24")  # 同步后可用


# --------------------------------------------------------------------------- #
# 3) flag 开：各类缺失 / 非法 → 不崩，原值保留
# --------------------------------------------------------------------------- #
def test_flag_on_missing_field_keeps_original(monkeypatch):
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    pos = _pos()
    recs = {RID: {"Recommendation_ID": RID, "Ticker": "ANET"}}      # 无 Stop_Loss 键
    pf.mark_to_market([pos], _prices(), TODAY, recs)
    assert pos["Stop_Loss"] == OLD_STOP


def test_flag_on_rec_id_not_found_keeps_original(monkeypatch):
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    pos = _pos()
    pf.mark_to_market([pos], _prices(), TODAY, {"别的ID": {"Stop_Loss": NEW_STOP}})
    assert pos["Stop_Loss"] == OLD_STOP


def test_flag_on_missing_rec_id_keeps_original(monkeypatch):
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    pos = _pos(Recommendation_ID="")
    pf.mark_to_market([pos], _prices(), TODAY, _recs())
    assert pos["Stop_Loss"] == OLD_STOP


@pytest.mark.parametrize("bad", ["", "  ", "N/A", "观望", "0", "-5", "nan", "inf", "abc", "$", "$$", "-$5"])
def test_flag_on_invalid_stop_keeps_original(monkeypatch, bad):
    """fail-closed：空 / 非数字 / 非正 / 非有限 一律不写。"""
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    pos = _pos()
    pf.mark_to_market([pos], _prices(), TODAY, _recs(stop=bad))
    assert pos["Stop_Loss"] == OLD_STOP, f"非法值 {bad!r} 不应被写入"


# --------------------------------------------------------------------------- #
# 4) flag 开：内部异常 → 警告 + 主流程继续
# --------------------------------------------------------------------------- #
def test_flag_on_exception_warns_and_continues(monkeypatch, capsys):
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    pos = _pos()
    sv, upl = pf.mark_to_market([pos], _prices(), TODAY, _BoomDict())

    out = capsys.readouterr().out
    assert "[stop-sync]" in out and "同步失败" in out, f"应打印同步失败警告，实际输出：{out!r}"
    assert pos["Stop_Loss"] == OLD_STOP, "异常时原值必须保留"
    # 主流程（盯市）必须照常完成
    assert sv == pf.money(Decimal("2160.00"))
    assert upl == pf.money(Decimal("47.00"))
    assert pos["Current_Price"] == "216.00"
    assert pos["Last_Update"] == TODAY


# --------------------------------------------------------------------------- #
# 5) 端到端：run(price_only=True) —— 每 15 分钟由 dashboard-data.yml 驱动的那条路径
# --------------------------------------------------------------------------- #
def _setup_repo(tmp_path):
    """写最小 positions.csv + trade_history.csv，返回 data_dir。"""
    pos = _pos()
    for k in ("Ticker", "Status", "Shares", "Entry_Price", "Current_Price",
              "Stop_Loss", "Recommendation_ID"):
        pass
    row = {c: "" for c in pf.POSITION_COLUMNS}
    row.update(pos)
    with open(tmp_path / pf.POSITIONS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=pf.POSITION_COLUMNS)
        w.writeheader()
        w.writerow(row)

    th_cols = ["Date", "Ticker", "Tag", "Price", "Status", "Exit_Date", "Exit_Price", "Stop_Loss"]
    with open(tmp_path / "trade_history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=th_cols)
        w.writeheader()
        w.writerow({"Date": "2026-10-07", "Ticker": "ANET", "Tag": "Core_Dragon",
                    "Price": "211.30", "Status": "Active", "Exit_Date": "",
                    "Exit_Price": "", "Stop_Loss": NEW_STOP})
    return tmp_path


def _read_stop(data_dir):
    rows = pf.read_csv_rows(data_dir / pf.POSITIONS_FILE)
    return rows[0].get("Stop_Loss")


def test_price_only_flag_off_csv_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("ENABLE_STOP_LOSS_SYNC", raising=False)
    _setup_repo(tmp_path)
    pf.run(tmp_path, offline=True, price_only=True)
    assert _read_stop(tmp_path) == OLD_STOP, "flag 关时 CSV 的 Stop_Loss 必须原样不动"


def test_price_only_flag_on_syncs_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_STOP_LOSS_SYNC", "1")
    _setup_repo(tmp_path)
    pf.run(tmp_path, offline=True, price_only=True)
    assert _read_stop(tmp_path) == NEW_STOP, "flag 开时应把 trade_history 的移动止损写进 CSV"
