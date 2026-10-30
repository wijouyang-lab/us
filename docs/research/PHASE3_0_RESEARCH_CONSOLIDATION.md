# Phase 3.0 Research Consolidation

Date: 2026-10-30
Research only. No production changes.

## 1. Scope

Audited Phase 2.1鈥?.9 code, PR states, data limitations and corrections.

- 2.1, 2.2, 2.4 merged.
- 2.3, 2.5鈥?.9 remain Draft PRs except merged 2.4.
- No Phase 2.5鈥?.9 result is on `main` yet; they are research branches.

## 2. Evidence summary

| Area | Status | Evidence |
|---|---|---|
| Price data | structural audit passed | Level 1 |
| Forward labels | full labels generated; 20D immaturity explained | Level 1 |
| Technical walk-forward | overlapping cohorts; metrics invalid | Level 1 / not usable |
| Factor engine | 20 factors, 1.239M rows, no future leak | Level 1 |
| Factor IC | 60D ATR/RV/Beta/MA FDR-significant only | Level 2, not tradeable |
| Historical universe | third-party partial, 713 tickers missing prices | Level 1, no PIT |
| Volatility portfolios | original invalid; corrected audit | Level 1 |
| Non-overlap portfolio | 105 periods, 0 overlap, costs; all fail at 50 bps | Level 3 design, no pass |
| SEC events | 150 events, 5 tickers, first-public unverified | Level 1, not PIT |
| Macro vintage | no key/vintage, 0 PIT observations | Level 0/1 |

## 3. What is reliable

- factor-engine formulas and coverage;
- forward-return maturity/status logic;
- Phase 2.5 daily IC/Rank IC and FDR for 60D volatility factors;
- corrected accounting identities in Phase 2.7.1;
- non-overlap 20D capital model and cost sensitivity;
- data gap counts (713 missing tickers, 501/503 CIK mapping).

## 4. What is invalid / superseded

- Phase 2.3 original CAGR/Sharpe and overlapping-cohort portfolio;
- Phase 2.7 original short accounting and net spread;
- Phase 2.5 Q5鈭扱1 as a net strategy return;
- any event/macro PIT claim.

## 5. What cannot be concluded

- no event alpha;
- no macro alpha;
- no fundamental quality/value alpha;
- no stable multi-strategy portfolio alpha;
- no historical PIT result.

## 6. Roadmap

1. Obtain official/verifiable historical membership and delisting returns.
2. Obtain SEC first-public evidence.
3. Obtain FRED/ALFRED vintage and release timestamps.
4. Obtain historical analyst expectations.
5. Only then rerun factor/event tests under strict PIT.

## 7. Current PIT status

```text
PIT validated events: 0
PIT validated macro observations: 0
PIT validated historical universe dates: 0
Deployment eligible strategies: 0
```

## 8. Artifacts

- `docs/research/RESEARCH_STATUS_MASTER.md`
- `data/research/research_status.json`
- `tools/research/research_status_audit.py`
- `tests/test_research_status_audit.py`
