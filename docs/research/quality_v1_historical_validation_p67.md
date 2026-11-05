# Quality V1 Historical PIT Validation — P6.7

Date: 2026-11-05
Branch: `research/quality-v1-history-p67`
Status: **HISTORICAL PIT GATE FAILED — limited exploratory history only**

## 1. Gate result

| Gate | Required | Actual | Pass |
|---|---:|---:|---|
| Member-session coverage | 95% | **79.58%** | No |
| Ticker coverage | 98% | **69.77%** | No |
| `BACKTEST_READY` | — | **False** | — |
| `VALIDATION_READY` | — | **False** | — |

```text
member_sessions:                 22,483
member_sessions_with_price:      17,892
unique historical members:          718
unique members with price:          501
```

The existing 10-year price panel covers only current S&P 500 survivors. It does
not contain the full delisted-member price history required by the strict PIT
gate, so a full quintile/Q5-Q1/IC backtest was **not run**.

## 2. Historical financial feasibility

| Metric | Count |
|---|---:|
| Current P6.6 candidates | 3,342 |
| Candidates with any annual fact | 3,170 |
| With >=2 annual NetIncome observations | 3,130 |
| With >=2 Assets/Equity instant observations | 3,156 |
| With all four Quality V1 metrics in at least one quarter | **2,536** |
| Configured quarter dates | 43 |
| Scored quarters | **37** (2017-09-30 to 2026-09-30) |
| Scored issuer observations | **58,396** |
| Unique scored issuers | **2,536** |

The first scored quarter is 2017-09-30; 2016 and early 2017 do not have enough
complete peer groups.

## 3. Historical score reconstruction

- Formula: exactly P6.6 fixed weights.
- Annual data visible by `pit_available_date` only.
- Latest complete annual report visible at each quarter end.
- Current/prior fiscal-year assets and equity must match a 300–430 day period.
- Q2/Q3 YTD is not treated as annual.
- US GAAP and IFRS separate.
- Current SIC is a **non-PIT industry proxy**.
- Peer group requires at least 30 issuers.
- Winsorization at 1%/99% within the historical peer group.

The reconstructed panel contains 58,396 observations but is **current-survivor
biased**, not a complete historical S&P 500 PIT universe.

## 4. Stability

| Metric | Value |
|---|---:|
| Scored quarters | 37 |
| Median score, 2024 | 50.61 |
| Median score, 2025 | 51.07 |
| Median score, 2026 | 51.24 |
| Average adjacent-quarter rank persistence | **0.946** |
| First-year to last-year Spearman | **0.334** |

Annual median scores are stable near 50–51. Adjacent-quarter rank persistence is
high, but long-horizon persistence falls to 0.334, indicating meaningful rank
turnover over multiple years.

No winsorization or weight-sensitivity result is claimed. Those sensitivity
tests were not completed because the strict PIT gate failed.

## 5. Forward-return tests

```text
status: BLOCKED_BY_HISTORICAL_PIT_GATE
quintile returns: NOT RUN
Q5-Q1: NOT RUN
IC / Rank IC: NOT RUN
HAC: NOT RUN
multiple testing: NOT RUN
```

The code supports Newey–West HAC and Benjamini–Hochberg correction, but no
forward-return conclusion is possible without the missing delisted price
history. The existing current-survivor price panel cannot support a clean
S&P 500 PIT return test and cannot be called full-market.

## 6. Survivorship and data limitations

1. Price panel has 503 tickers, all current S&P 500 survivors.
2. 718 unique historical members; 217 have no matching price coverage.
3. Current SIC is used as a historical industry proxy.
4. P6.3 PIT is next-weekday after `filed`, without exchange holiday adjustment
   or exact acceptanceDateTime.
5. No delisted-member total-return series is complete.
6. No OTC or full-market historical prices.
7. Historical panel is current-universe-based, not an unbiased historical
   universe.

## 7. Deliverables

```text
tools/research/rebuild_quality_pit_history_p67.py
tools/research/audit_quality_stability_p67.py
tools/research/evaluate_quality_forward_returns_p67.py
tests/test_quality_history_p67.py
data/research/quality_pit_coverage_p67.json
data/research/quality_historical_stability_p67.json
data/research/quality_forward_return_tests_p67.json
docs/research/quality_v1_historical_validation_p67.md
.github/workflows/research-quality-v1-validation-p67.yml
```

The 58,396-row historical score panel is uploaded as a GitHub Actions artifact,
not committed to Git.

## 8. Conclusion

Quality V1 can be reconstructed for **37 quarters / 2,536 issuers**, but the
strict PIT price gate fails badly:

```text
79.58% member-session coverage
69.77% ticker coverage
```

Therefore:

- No `BACKTEST_READY` or `VALIDATION_READY` status is claimed.
- No Q5-Q1, IC, HAC, or multiple-testing result is claimed.
- No conclusion about predictive ability is possible from this run.
- The 0.334 long-horizon rank persistence is exploratory and survivorship-biased.
- Quality V1 should remain a research hypothesis; do not optimize against
  returns until delisted PIT prices and membership are complete.
