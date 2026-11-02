# Phase 3.2.2 Recovery and Execution Audit

Date: 2026-11-02  
Base: `research/phase3-2-1-risk-engine-audit-fix` (PR #426)  
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`

## 1. Audit fixes

| Finding | Fix |
|---|---|
| Sticky cash never recovers | stateful `RecoveryState` with sticky, market, market+breadth designs |
| `risk_cost.py` dropped empty weeks | shared `events_from_signals()` used by main and cost scripts |
| Name cap undone by normalization | hard water-filling cap; no post-cap normalization |
| Missing Open erased held positions | held missing Open raises `MissingExecutionPriceError`; new missing names excluded and counted |
| Annual returns used first/last NAV inside year | prior year-end NAV carried forward |
| Recovery design selection leaks test | train/validation selections only; test reported once |

## 2. Recovery designs

### Sticky
At drawdown ≥12%: 0% new risk forever; high-water mark not reset.

### Market recovery
After CASH_DEFENSE, require two consecutive weekly:
```text
SPY Close > MA200
SPY MA200 20D slope > 0
```
Then re-enter at 25% gross cap; add at most 25pp per qualifying week. If regime fails,
return to cash. HWM is never reset.

### Market + breadth
Same, plus pre-declared breadth:
```text
fraction of available assets with Close > MA200 >= 50%
```

Breadth uses the current universe; it is exploratory and survivorship-biased.

## 3. Design selection

Splits:

```text
train       2018-01-01..2020-12-31
validation  2021-01-01..2023-12-31
test        2024-01-01..2026-10-28
```

Selection rule: highest validation Sharpe, frozen before test reporting.

| Design | Validation Sharpe |
|---|---:|
| Sticky | None (cash, zero variance) |
| Market | **−0.013** |
| Market+breadth | −0.057 |

**Selected: Market recovery.** The test segment was not used for selection.

## 4. Recovery comparison

10 bps, full period:

| Design | CAGR | MaxDD | Sharpe | Transitions | Final mode |
|---|---:|---:|---:|---:|---|
| Sticky | −1.24% | −12.24% | −0.241 | 0 | CASH_DEFENSE |
| **Market** | **−1.30%** | **−14.41%** | **−0.178** | 7 | RECOVERY |
| Market+breadth | −1.23% | −13.09% | −0.192 | 9 | RECOVERY |

All are negative; to the extent recovery helps, it is marginal.

### Split results

| Design | Train CAGR | Validation CAGR | Test CAGR | Test MaxDD |
|---|---:|---:|---:|---:|
| Sticky | −3.61% | 0.00% | 0.00% | 0.00% |
| Market | −2.89% | −0.15% | −0.66% | −11.61% |
| Market+breadth | −2.87% | −0.32% | −0.30% | −4.74% |

The selected market design fails the test period: negative CAGR, though drawdown
is contained.

## 5. Selected market diagnostics (10 bps)

```text
average stock exposure:  37.1%
average cash:            62.9%
average daily holdings:  155.6
max single weight:        7.65%
max cluster weight:      17.6%
cash lockout days:       351
recovery days:           115
transitions:               7
stale holding-days:       116
missing execution events:   0
total cost:               5.61%
turnover:                 28.1x
```

State occupancy:

```text
DEFENSIVE_25       729 days
CASH_DEFENSE       467
DEFENSIVE_75       437
DEFENSIVE_50       395
NORMAL             187
```

Recovery works mechanically, but the strategy does not recover economically.

## 6. Cost sensitivity, selected market design

| Cost | CAGR | MaxDD |
|---:|---:|---:|
| 5 bps | −1.19% | −12.57% |
| 10 bps | −1.30% | −14.41% |
| 20 bps | −1.09% | −14.29% |
| 50 bps | −2.74% | **−22.75%** |

At 50 bps the 15% drawdown objective is breached. Cost results are path-dependent
because recovery/defence changes exposure.

## 7. Original vs corrected four-way

| Scheme | Old CAGR | New CAGR | Old MaxDD | New MaxDD |
|---|---:|---:|---:|---:|
| A SPY buyhold | 12.66% | 12.66% | −34.10% | −34.10% |
| B SPY trend/cash | 12.63% | 8.46% | −34.04% | −18.05% |
| C equal confirmed | 9.51% | 9.31% | −33.09% | −33.12% |
| D sticky | 3.73% | −1.24% | −20.39% | −12.24% |
| D market | — | −1.30% | — | −14.41% |
| D market+breadth | — | −1.23% | — | −13.09% |

The corrected engine confirms that D is not attractive; the old +3.73% result was
an artifact of the accounting/execution defects.

## 8. Tests

New/updated:

- `tests/test_trend_v1_recovery.py`: **9 passed**
  - water-fill caps for 1/2/5/10/50 names;
  - single-name cap;
  - two-week recovery confirmation;
  - immediate risk-off;
  - sticky lockout;
  - breadth requirement;
  - missing held Open raises;
  - annual prior-year-end NAV;
  - shared empty-week event.
- `tests/test_trend_v1_audit_fixes.py`: **12 passed**
- `tests/test_trend_v1_spy_benchmark.py`: **1 passed**
- Existing trend/portfolio: **17 passed**

Total targeted: **39 passed**. Full CI after commit.

## 9. Remaining issues

- No recovery design is economically viable;
- selected market design has negative test CAGR;
- 50 bps breaches the 15% objective;
- current 503-name universe, survivorship bias;
- 4 ETFs only; no ETF PIT membership;
- no delisting/fund-closure returns;
- no dividends, only price returns;
- stale-price policy reports 116 holding-days but no >5-day breach;
- no live slippage/capacity.

## 10. Decision gate

**The trend V1 route does not achieve acceptable net return with reasonable
drawdown risk on untouched test data.** No further threshold tuning should be
done. This is a negative research result, not a deployable strategy.
