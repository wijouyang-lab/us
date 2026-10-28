# Final Low-Frequency Strategy Research Conclusion

Date: 2026-10-28
Deadline: 2026-11-04
Research only. No production changes.

## 1. Executive conclusion

**No reliable alpha and no deployable strategy were found.**

The strongest fixed-model result (Qlib Ridge, 39.85% annualized, Sharpe 2.78)
did not survive honest walk-forward refitting (13.24%, Sharpe 0.69, t 0.64,
alpha CI includes zero). The broad formula search, 2-year five-factor test,
466-ticker five-factor test, and high-vol/beta test also failed the
predeclared significance/robustness requirements.

Stop generating more factors/models on the current 466-stock,
survivorship-biased panel. Do not promote any result to paper or production.

Machine-readable record:

`docs/research/FINAL_RESEARCH_CONCLUSION_2026-10-28.json`

---

## 2. What was already tested

| Experiment | Data | Status | Main result |
|---|---|---|---|
| 399 formula search | 2y PIT, 502 tickers | failed | 0 positive BH q<0.05 |
| 2y fixed five-factor | 2y PIT | failed | no positive q<0.05 |
| Qlib Ridge fixed | 2y PIT | superseded | 39.85% / Sharpe 2.78, 9 months |
| Qlib Ridge walk-forward | 2y PIT | failed | 13.24% / Sharpe 0.69 / t 0.64 |
| High-vol/ATR beta | 10y current universe | rejected | alpha t ~0.05; beta ~0.75 |
| 466 five-factor | 466 current tickers, 2016鈥?026 | failed | no positive BH q<0.05 |
| Event study | 35 Fed events + SPY | not eligible | 0 entry / 0 +1 / 0 +5 |

### Duplicate-work cleanup

- The 399-formula search and fixed five-factor test are different hypothesis
  families; no need to rerun them as 鈥渘ew鈥?research.
- Qlib fixed-model report is superseded by the walk-forward audit.
- High-vol beta and low-vol factor are separate tests; neither is alpha.
- Event simulation/import tests are not new observations.

---

## 3. Candidate vs benchmark

466-ticker current-universe sample, test 2023鈥?026, 20D monthly Q5/Q1, 5 bps:

| Candidate | Net monthly | Annualized | Sharpe | p | BH q |
|---|---:|---:|---:|---:|---:|
| Vol60 low | -1.73% | -20.4% | -1.06 | 0.044 | 0.128 |
| ATR low | -1.61% | -19.1% | -1.04 | 0.051 | 0.128 |
| Mom12-1 high | +0.72% | +7.4% | 0.44 | 0.334 | 0.334 |
| Mom1 low | -1.00% | -12.2% | -0.89 | 0.099 | 0.164 |
| MA50 high | +0.58% | +6.3% | 0.46 | 0.328 | 0.334 |

Benchmark (equal-weight eligible universe, same dates):

| Metric | Value |
|---|---:|
| Annualized | **14.31%** |
| Sharpe | **0.86** |
| Max drawdown | -21.60% |

No positive candidate beats the benchmark with statistical support. The
benchmark itself is survivorship-biased.

---

## 4. Costs, OOS, robustness

### Costs

- Base: 5 bps one-way, applied to name turnover.
- Sensitivity: 10/20 bps.
- Mean turnover varies ~22%鈥?8% by factor.
- Costs are not the main driver; absence of stable alpha is.

### Time split

- 466 test: train 鈮?022, test 2023鈥?026.
- Qlib: fixed 9 test months; walk-forward expanding window with 21-session
  purge/embargo.
- No test-period parameter selection.

### Stability

- Qlib test halves differ materially (27.9% vs 50.2% annualized fixed).
- Walk-forward drawdown worsens to ~-12%.
- 466 factors are not consistently positive across train and test.
- High-vol result is market beta, not alpha.

### Multiple testing

- 399 formulas: BH/BY correction; none positive significant.
- 466: BH across exactly five predeclared factors; none positive q<0.05.
- No post-hoc factor reversal counted as a new candidate.

### Data quality / survivorship

- 466 current tickers, 2,532 sessions, 1,179,912 rows.
- Current-universe only; delisted names absent.
- PIT coverage 91.61% and ticker coverage 84.23% remain below the full-history
  gate.
- Raw OHLCV, no adjusted close for the 466 panel.
- Therefore results are **not** full PIT and **not** deployable.

---

## 5. Event research status

- 35 real Fed events; 35 publication-forward candidates.
- 0 entry, 0 +1, 0 +5 results; all pending entry bars.
- Strict PIT event sample: 0.
- Formal experiment gate: `not_eligible` (35<200, coverage<365d, no complete
  horizons).
- No event alpha test run.
- Event work continues in parallel; it is not a blocker for the conclusion
  above.

Current event artifacts:

- PR #397: https://github.com/wijouyang-lab/us/pull/397
- Archive branch: https://github.com/wijouyang-lab/us/tree/research/event-archive
- First real run: https://github.com/wijouyang-lab/us/actions/runs/40661139681
- Pre-registration: `docs/research/EVENT_EXPERIMENT_PREREGISTRATION_2026-10-28.md`

### 10/28 close and second cross-day run

At the time of this research run, the provider still only had 2026-10-27.
10/28 official close and the second real UTC-day capture are pending; no data
was fabricated. They do not change the no-alpha conclusion from the existing
466 sample.

---

## 6. Decision

| Decision | Result |
|---|---|
| Reliable alpha found? | **No** |
| Deployable strategy? | **No** |
| Paper-trading candidate? | **No** |
| Continue unlimited factor search? | **No** |
| Production changes? | **None** |

## 7. What would justify reopening

Only if all of these happen:

1. Full PIT/delisted price coverage meets the predeclared gate.
2. A candidate is pre-registered before testing.
3. Positive OOS result survives costs, benchmark adjustment, and multiple
   testing.
4. Independent adjusted-close/corporate-action validation.
5. Paper trading and explicit human review.

Until then, the research conclusion is **no reliable alpha**, not a pending
invitation to keep testing the same sample.
