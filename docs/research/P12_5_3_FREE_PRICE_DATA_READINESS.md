# P12.5.3 Free Price Data Readiness

## Sources found locally

| Source | Path | Rows / tickers | Range | Fields | Status |
|---|---|---|---:|---|---|
| PIT technical snapshot | `data/_download/snap/research_factor_snapshots_sp500_pit_10y.csv` | 1,047,578 / 502 | 2016-12-12..2026-10-13 | `Price` only | EXPLORATORY |
| FINSABER raw | `_us_audit/pr512/data/research/pit_data/finsaber_prices_raw.csv` | 4,736,109 / 1,017 | 2000-01-03..2024-12-31 | OHLC, adjusted_close, volume | PARTIAL / license-unconfirmed |
| S&P membership | `_us_audit/pr512/data/research/historical_universe/sp500_daily.csv` | daily membership | 1996.. | tickers | available, not fully audited |
| ETFs | `data/research/volume_shock_reversal/{SPY,TLT,GLD,IWM}.csv` | daily | 2006..2026 | OHLC + Adj Close | used |

The PIT snapshot was used for the exploratory run because it was already
validated in P12.5.2. It has no Adjusted Close and no PIT membership proof.

FINSABER has adjusted close and OHLC but its license is not cleared for public
redistribution and its membership/identity audit was not completed this round.
The full FINSABER beta run was started but exceeded the execution budget; it is
not reported as a completed result.

## Universes

```text
STRICT_RESEARCH_UNIVERSE: 0 (no fully verified PIT total-return set)
EXPLORATORY_RESEARCH_UNIVERSE: 481 tickers, 2017-2026
REJECTED_UNIVERSE: not used
```

The exploratory set is not a full-market PIT universe and cannot support a
tradable Alpha claim.
