"""Risk sizing, correlation groups and drawdown defence for Trend V1."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskConfig:
    target_vol: float = 0.10
    max_weight: float = 0.10
    max_group_weight: float = 0.20
    corr_threshold: float = 0.70
    lookback: int = 60


def defense_cap(drawdown: float) -> float:
    if drawdown >= 0.15:
        return 0.0
    if drawdown >= 0.12:
        return 0.0
    if drawdown >= 0.10:
        return 0.25
    if drawdown >= 0.08:
        return 0.50
    if drawdown >= 0.05:
        return 0.75
    return 1.0


def defense_state(drawdown: float) -> str:
    if drawdown >= 0.15:
        return "HARD_RISK_BREACH"
    if drawdown >= 0.12:
        return "CASH_DEFENSE"
    if drawdown >= 0.10:
        return "DEFENSIVE_25"
    if drawdown >= 0.08:
        return "DEFENSIVE_50"
    if drawdown >= 0.05:
        return "DEFENSIVE_75"
    return "NORMAL"


def _clusters(corr: np.ndarray, tickers: list[str], threshold: float) -> dict[str, int]:
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform
    n = len(tickers)
    if n < 2:
        return {tickers[0]: 0} if tickers else {}
    dist = np.clip(1.0 - np.nan_to_num(corr, nan=0.0), 0.0, 2.0)
    np.fill_diagonal(dist, 0.0)
    z = linkage(squareform(dist, checks=False), method="average")
    labels = fcluster(z, t=max(1e-9, 1.0 - threshold), criterion="distance")
    return {t: int(labels[i]) for i, t in enumerate(tickers)}
    return out


def allocate(candidates: pd.DataFrame, closes: pd.DataFrame, signal_date, drawdown_magnitude: float,
             cfg: RiskConfig = RiskConfig()) -> tuple[dict[str, float], dict]:
    """candidates: ticker, Score. drawdown_magnitude is a positive loss fraction."""
    if candidates.empty:
        return {}, {"reason": "NO_CONFIRMED", "expected_vol": 0.0, "clusters": 0,
                    "gross": 0.0, "defense": defense_state(drawdown_magnitude)}
    px = closes[closes.index <= pd.Timestamp(signal_date)].tail(cfg.lookback + 1)
    rets = px.pct_change().dropna(how="all")
    tickers = [t for t in candidates.ticker if t in rets.columns and rets[t].notna().sum() >= cfg.lookback - 5]
    if not tickers:
        return {}, {"reason": "INSUFFICIENT_VOL", "expected_vol": 0.0, "clusters": 0,
                    "gross": 0.0, "defense": defense_state(drawdown_magnitude)}
    r = rets[tickers].dropna(axis=1, how="any")
    tickers = list(r.columns)
    vol = r.std(ddof=1) * np.sqrt(252)
    vol = vol.replace(0, np.nan).dropna()
    tickers = [t for t in tickers if t in vol.index]
    if not tickers:
        return {}, {"reason": "ZERO_VOL", "expected_vol": 0.0, "clusters": 0,
                    "gross": 0.0, "defense": defense_state(drawdown_magnitude)}
    # Ranking is a transparent weight multiplier: the best-scored asset gets
    # 1.0x inverse-vol and the worst gets 0.5x. No fixed holding-count cap.
    score = candidates.set_index("ticker").Score.reindex(tickers).astype(float)
    rank_pct = score.rank(pct=True).fillna(0.0)
    raw = (1 / vol[tickers]) * (0.5 + 0.5 * rank_pct)
    w = raw / raw.sum()
    w = w.clip(upper=cfg.max_weight)
    w = w / w.sum()
    corr = r[tickers].corr().to_numpy()
    groups = _clusters(corr, tickers, cfg.corr_threshold)
    for _ in range(3):
        for gid in set(groups.values()):
            members = [t for t in tickers if groups[t] == gid]
            gs = float(w[members].sum())
            if gs > cfg.max_group_weight:
                w[members] *= cfg.max_group_weight / gs
    cov = r[tickers].cov().to_numpy() * 252
    exp_vol = float(np.sqrt(max(w.to_numpy() @ cov @ w.to_numpy(), 0.0)))
    scale = min(1.0, cfg.target_vol / exp_vol) if exp_vol > 0 else 0.0
    w = w * scale * defense_cap(drawdown_magnitude)
    w = w.clip(upper=cfg.max_weight)
    gross = float(w.sum())
    max_group = max((float(w[[t for t in tickers if groups[t] == gid]].sum()) for gid in set(groups.values())), default=0.0)
    return {t: float(w[t]) for t in tickers if w[t] > 1e-9}, {
        "reason": "OK", "expected_vol": exp_vol, "clusters": len(set(groups.values())),
        "gross": gross, "max_group_weight": max_group, "defense": defense_state(drawdown_magnitude)}
