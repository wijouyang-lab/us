# Phase 2.7.2 Research Accounting Audit

Date: 2026-10-30
Research only. Original reports preserved. Label remains
`EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`.

## 1. Shared accounting module

Added `tools/research/portfolio_accounting.py`:

```text
long_net       = long_gross - long_cost
short_net      = -underlying_gross - short_cost
long_short_net = long_net + short_net
1x spread      = long_short_net
2x capital     = long_short_net / 2   (100% long + 100% short)
CAGR           = equity^(1 / elapsed_years) - 1
Sharpe         = mean(period) / std(period) 脳 sqrt(periods_per_year)
max drawdown   = equity / running_peak - 1
```

Cost units:

- initial buy = 1 side;
- replacement = buy + sell = 2 脳 turnover;
- zero turnover = zero cost.

Tests: `tests/test_portfolio_accounting.py`, **12 passed**.

## 2. Audit table

| Module | Original accounting | Correct? | Fixed? | Impact |
|---|---|---|---|---|
| Phase 2.3 technical / walk-forward | long-only; CAGR = `(prod)^(12/n)`, Sharpe = CAGR/vol | **No** | not yet | Sharpe/CAGR invalid; maximum drawdown still valid |
| Phase 2.5 IC/Q1鈥換5 | Q1鈥換5 **gross** future-return means; no cost/Sharpe | Yes for gross | no change needed | must not be read as net long-short |
| Phase 2.7 non-overlap portfolios | long Q5, **long Q1**, then Q5鈭扱1; cost on Q1 added back | **No** | corrected in #416 | original Q5鈭扱1 net and Sharpe overstated |
| Phase 2.7.1 audit | short leg, independent cost, 1x/2x capital | Yes | audit basis | corrected ATR 2x 10 bps = 10.26% |
| `factor_quantile_backtest.py` | long-short gross spread; Sharpe on gross; no costs | Partly | not corrected | label as gross; not net |
| `event_factor_backtest.py` | subtracts fixed `4 脳 cost_bps` per trade, not actual turnover | **No** | not corrected | cost may be wrong |
| `multi_strategy_comparison.py` | long-only net, mean/std Sharpe, turnover cost | Yes | 鈥?| safe for long-only, not long-short |
| `low_frequency_atr_*` | turnover-based cost, long-only | Partly | 鈥?| cost may be one-sided only; recheck |

## 3. Phase 2.3: invalid metrics

`technical_strategy_backtest.stats` and `walkforward_validation.metrics`:

```python
ann = prod(1+r) ** (12/n) - 1
sharpe = ann / vol
```

Problems:

1. periods are 20-session cohorts, not months; `12/n` is the wrong
   annualization;
2. CAGR should use actual elapsed calendar time;
3. Sharpe must use mean/std of period returns, not CAGR/vol;
4. 2026 partial year must not be treated as a full year.

Maximum drawdown uses a compounded equity curve, so that part is sound.

**Conclusion: Phase 2.3 Sharpe and CAGR values are not confirmed. Phase 2.3
must be rerun with the shared accounting module before its performance numbers
are used.** Its qualitative conclusion (no stable cross-window excess) may
survive, but the exact numbers do not.

## 4. Phase 2.5: gross only

The Phase 2.5 Q5鈭扱1 is:

```text
mean(Q5 forward return) 鈭?mean(Q1 forward return)
```

It is a **gross cross-sectional spread**, not a tradeable long-short portfolio:

- no cost;
- no capital denominator;
- no borrow/financing;
- no compounding;
- no Sharpe/CAGR;
- daily 60D labels overlap.

The report should keep it as gross factor evidence. It must not be relabeled as
net or as a deployable long-short return.

## 5. Phase 2.7: original vs audit

Original ATR 10 bps:

```text
Q5 CAGR                 27.26%
Q1 leg                  +6.13% (this was long Q1, not short)
Q5鈭扱1 CAGR 1x           20.04%
Q5鈭扱1 Sharpe            0.66
```

Audit ATR 10 bps:

```text
Q5 CAGR                 26.76%
Q1 short net            鈭?.50%
Q5鈭扱1 1x CAGR           18.95%
Q5鈭扱1 2x capital CAGR   10.26%
Q5鈭扱1 Sharpe            0.358
```

At 50 bps:

| Factor | Original 1x Q5鈭扱1 | Audit 1x | Audit 2x |
|---|---:|---:|---:|
| ATR | 20.32% | 16.30% | 9.02% |
| Realized Vol | 14.55% | 9.51% | 5.54% |
| Beta | 13.33% | 9.55% | 5.97% |

Original values are invalid for net-return comparison.

## 6. Effects / invalidated conclusions

Invalidated:

- Phase 2.3 all Sharpe/CAGR figures;
- Phase 2.7 original Q5鈭扱1 net CAGR, cost sensitivity, Sharpe;
- any claim that increasing costs increases Q5鈭扱1;
- any direct comparison of 1x spread CAGR to 100%-long CAGR.

Still usable:

- Phase 2.3 maximum drawdowns and qualitative instability;
- Phase 2.5 gross IC/Rank IC and gross Q1鈥換5;
- Phase 2.7 gross Q5/Q1 and factor correlations;
- Phase 2.7.1 corrected 1x/2x results;
- Phase 2.4 factor coverage;
- Phase 2.6 coverage audit, with no PIT date.

## 7. Other modules

Need follow-up fixes, not silently accepted:

- `event_factor_backtest.py` fixed 4脳 cost is not turnover-based;
- `factor_quantile_backtest.py` gross long-short Sharpe lacks costs and capital
  denominator;
- `low_frequency_atr_*` should verify whether cost is one side or two;
- modules reporting Q5鈭扱1 must explicitly say gross vs net and 1x vs 2x.

## 8. Safe-to-use list before fixes

Safe:

- factor engine coverage and formulas;
- Phase 2.5 IC/Rank IC, with `WEAK_EXPLORATORY`/gross labels;
- Phase 2.6 membership coverage, no PIT;
- Phase 2.7.1 corrected audit;
- Phase 2.3 drawdown/qualitative signs, but not CAGR/Sharpe.

Not safe:

- Phase 2.3 CAGR/Sharpe;
- Phase 2.7 original net spread;
- event-factor fixed-cost net returns;
- any Q5鈭扱1 figure without gross/net and 1x/2x labels.

## 9. Remaining real costs

Even corrected long-short results omit:

- borrow fees;
- locate/availability;
- financing;
- short dividends;
- market impact;
- hard-to-borrow constraints.

## 10. Conclusion

The repository did **not** have one consistent accounting convention. The shared
module now defines one. Phase 2.3 must be recomputed before use; Phase 2.7
original numbers are superseded by #416; Phase 2.5 must stay gross-only.

No new strategy optimization should start until the affected reports are
regenerated.
