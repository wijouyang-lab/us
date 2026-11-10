"""Two-stage WATCH -> CONFIRMED state machine with exit/re-entry reset."""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class TrendState:
    state: str = "FLAT"
    watch_streak: int = 0
    low_ma50_streak: int = 0

    def copy(self):
        return TrendState(self.state, self.watch_streak, self.low_ma50_streak)


def _f(v):
    return None if v is None else float(v)


def evaluate_row(row, prior: TrendState) -> tuple[TrendState, dict]:
    required = ("Close", "MA50", "MA200", "MA200_Slope20", "Mom20", "Rel20")
    if any(row.get(k) is None or row.get(k) != row.get(k) for k in required):
        return TrendState(), {"state": "FLAT", "watch": False, "confirmed": False,
                             "exit_signal": prior.state == "CONFIRMED", "reason": "MISSING_DATA"}
    close, ma50, ma200 = float(row["Close"]), float(row["MA50"]), float(row["MA200"])
    watch = close > ma50 and float(row["Mom20"]) > 0 and float(row["Rel20"]) > 0
    confirm_ok = close > ma200 and ma50 > ma200 and float(row["MA200_Slope20"]) > 0
    low = close < ma50
    low_streak = (prior.low_ma50_streak + 1) if low else 0
    st = prior.copy()
    exit_signal = False
    if prior.state == "CONFIRMED":
        hard = close < ma200
        soft = low_streak >= 2 and float(row["Mom20"]) < 0
        if hard or soft:
            st = TrendState()
            exit_signal = True
            reason = "HARD_EXIT_MA200" if hard else "SOFT_EXIT_2W_MA50"
        else:
            st.low_ma50_streak = low_streak
            reason = "HOLD_CONFIRMED"
    elif watch:
        st.watch_streak = prior.watch_streak + 1
        st.low_ma50_streak = low_streak
        if st.watch_streak >= 2 and confirm_ok:
            st.state = "CONFIRMED"
            reason = "CONFIRMED"
        else:
            st.state = "WATCH"
            reason = "WATCH"
    else:
        st = TrendState()
        reason = "NOT_WATCH"
    return st, {"state": st.state, "watch": bool(watch), "confirmed": st.state == "CONFIRMED",
                "exit_signal": exit_signal, "reason": reason, "watch_streak": st.watch_streak}
