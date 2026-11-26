"""Scenario DCF, deliberately decoupled from SEC and price providers."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict


@dataclass
class DCFInputs:
    base_fcf: float
    discount_rate: float = 0.10
    terminal_growth: float = 0.025
    years: int = 5
    growth: dict = field(default_factory=lambda: {"bear": -0.02, "base": 0.03, "bull": 0.08})
    net_debt: float | None = None
    shares: float | None = None
    source: str = "model_assumption"


def _pv(fcf: float, g: float, r: float, tg: float, years: int) -> float:
    if r <= tg: raise ValueError("discount rate must exceed terminal growth")
    pv = sum(fcf * ((1 + g) ** i) / ((1 + r) ** i) for i in range(1, years + 1))
    tv = fcf * ((1 + g) ** years) * (1 + tg) / (r - tg)
    return pv + tv / ((1 + r) ** years)


def run(inp: DCFInputs) -> dict:
    if inp.base_fcf <= 0:
        return {"status": "NOT_APPLICABLE", "reason": "base FCF <= 0; positive-growth perpetuity DCF not applicable",
                "label": "SCENARIO_ESTIMATE_NOT_INVESTMENT_TARGET"}
    if inp.discount_rate <= inp.terminal_growth:
        return {"status": "INSUFFICIENT_DATA", "reason": "discount rate <= terminal growth",
                "label": "SCENARIO_ESTIMATE_NOT_INVESTMENT_TARGET"}
    scenarios = {}
    for name, g in inp.growth.items():
        ev = _pv(inp.base_fcf, g, inp.discount_rate, inp.terminal_growth, inp.years)
        equity = ev - inp.net_debt if inp.net_debt is not None else None
        per_share = equity / inp.shares if equity is not None and inp.shares and inp.shares > 0 else None
        scenarios[name] = {"growth": g, "enterprise_value": ev, "equity_value": equity,
                           "value_per_share": per_share}
    def table(axis):
        values = []
        if axis == "discount":
            grid = [inp.discount_rate - 0.02, inp.discount_rate - 0.01, inp.discount_rate,
                    inp.discount_rate + 0.01, inp.discount_rate + 0.02]
            for r in grid:
                if r <= inp.terminal_growth: continue
                values.append({"discount_rate": r, "enterprise_value": _pv(inp.base_fcf, inp.growth["base"], r, inp.terminal_growth, inp.years)})
        elif axis == "terminal":
            grid = [inp.terminal_growth - 0.01, inp.terminal_growth - 0.005, inp.terminal_growth,
                    inp.terminal_growth + 0.005, inp.terminal_growth + 0.01]
            for tg in grid:
                if inp.discount_rate <= tg: continue
                values.append({"terminal_growth": tg, "enterprise_value": _pv(inp.base_fcf, inp.growth["base"], inp.discount_rate, tg, inp.years)})
        else:
            for g in [inp.growth["bear"], inp.growth["base"], inp.growth["bull"]]:
                values.append({"growth": g, "enterprise_value": _pv(inp.base_fcf, g, inp.discount_rate, inp.terminal_growth, inp.years)})
        return values
    return {"status": "OK", "label": "SCENARIO_ESTIMATE_NOT_INVESTMENT_TARGET",
            "scenarios": scenarios,
            "assumptions": {"base_fcf": inp.base_fcf, "years": inp.years,
                            "discount_rate": inp.discount_rate, "terminal_growth": inp.terminal_growth,
                            "growth": inp.growth, "net_debt": inp.net_debt, "shares": inp.shares,
                            "source": inp.source},
            "sensitivity": {"discount_rate": table("discount"), "terminal_growth": table("terminal"),
                            "fcf_growth": table("growth")},
            "warning": "Scenario estimate only; not an investment target or BUY/SELL signal."}
