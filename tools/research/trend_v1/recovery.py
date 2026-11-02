"""Stateful cash-defence recovery independent of the NAV high-water mark."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecoveryState:
    design: str = "sticky"  # sticky | market | market_breadth
    mode: str = "NORMAL"
    cap: float = 1.0
    qualifying_weeks: int = 0
    transitions: int = 0

    def update(self, drawdown_magnitude: float, spy_ok: bool, breadth_ok: bool = True):
        if self.design == "sticky":
            self.cap = 0.0 if drawdown_magnitude >= 0.12 else 1.0
            self.mode = "CASH_DEFENSE" if self.cap == 0 else "NORMAL"
            return self
        if drawdown_magnitude < 0.12:
            self.mode, self.cap, self.qualifying_weeks = "NORMAL", 1.0, 0
            return self
        regime = bool(spy_ok and (breadth_ok if self.design == "market_breadth" else True))
        if self.mode not in ("CASH_DEFENSE", "RECOVERY"):
            self.mode, self.cap, self.qualifying_weeks = "CASH_DEFENSE", 0.0, 0
        if self.mode == "CASH_DEFENSE":
            self.cap = 0.0
            self.qualifying_weeks = self.qualifying_weeks + 1 if regime else 0
            if self.qualifying_weeks >= 2:
                self.mode, self.cap, self.qualifying_weeks = "RECOVERY", 0.25, 0
                self.transitions += 1
        elif self.mode == "RECOVERY":
            if not regime:
                self.mode, self.cap, self.qualifying_weeks = "CASH_DEFENSE", 0.0, 0
            else:
                self.cap = min(1.0, self.cap + 0.25)
        return self
