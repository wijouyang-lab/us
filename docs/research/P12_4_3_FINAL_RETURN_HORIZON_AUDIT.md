# P12.4.3: Final Fundamental Return-Horizon and Statistical Boundary Audit

Date: 2026-11-17
Branch: `research/p12-event-fundamental-feasibility`
Status: **DESCRIPTIVE_ONLY; fundamental NO_SIGNAL**

P12.4.1 and P12.4.2 outputs are preserved. New results are under
`data/research/p12_4_3/`.

---

## 1. Fixes

### 1.1 Fundamental exit dates

Old code used `j = bisect_right(tdays, UTC_date)` and then `tdays[j+h]` even
when the entry was the same trading day. That added an extra session.

New code:

```text
entry_index = index of entry session (same day or next session)
exit_index  = entry_index + horizon
```

The panel now carries `entry_date`, `exit5_date`, `exit10_date`, `exit20_date`.

Controls:

```text
filing-date-only -> next session
acceptance before 16:00 ET on a session -> same session close
acceptance at/after 16:00 ET or non-session -> next session
```

### 1.2 Period boundaries

Fundamental periods now use US/Eastern disclosure dates and left-closed,
right-open intervals:

```text
all:      [2009-01-01, 2025-01-01)
explore:  [2009-01-01, 2019-01-01)
validate: [2019-01-01, 2025-01-01)
```

### 1.3 8-K D5/D20 counts

D5 and D20 now have independent samples and counts:

```text
n_d5_accessions / n_d5_issuers
n_d20_accessions / n_d20_issuers
```

They are no longer filled from the D5 sample.

---

## 2. Off-by-one impact

Affected fundamental records:

```text
changed 5-day returns:  464 / 2,624
changed 10-day returns: 464 / 2,624
changed 20-day returns: 462 / 2,624
```

Coverage did not change:

```text
5d: 2,623 / 2,624
10d: 2,620 / 2,624
20d: 2,617 / 2,624
```

Mean absolute return change: ~0.23% (5d), ~0.23% (10d), ~0.26% (20d).

Exit-date examples (SPY calendar):

```text
intraday 2024-03-11:
  entry 2024-03-11, exits 03-18 / 03-25 / 04-09
after close 2024-03-11:
  entry 2024-03-12, exits 03-19 / 03-26 / 04-10
filing-only 2024-03-10 (spring DST):
  entry 2024-03-11, exits 03-18 / 03-25 / 04-09
filing-only 2024-11-03 (fall DST):
  entry 2024-11-04, exits 11-11 / 11-18 / 12-03
```

`p12_4_3_timezone_exit_tests.csv`: 5/5 PASS.

---

## 3. Fundamental results after correction

Best validation cells:

```text
revenue_growth / 5d:   IC 0.0491, p 0.188, BH q 0.777
cash_conversion / 10d: IC 0.0477, p 0.056, BH q 0.777
op_margin / 5d:        IC 0.0442, p 0.208, BH q 0.777
```

No metric passes BH FDR.

```text
FUNDAMENTAL_CHANGE: NO_SIGNAL
```

---

## 4. 8-K D5/D20 counts

32 of 88 item/session/period rows have different D5 and D20 sample sizes; the
largest difference is 15 accessions.

Example, 2.02 AFTER_HOURS all:

```text
D5:  1,501 accessions / 84 issuers
D20: 1,493 accessions / 84 issuers
```

---

## 5. 2.02 AFTER_HOURS

500-draw CIK bootstrap, seed 20261117:

```text
period      sample       n     issuers  D20 mean   p       q
all         all        1493    84      +0.711%    0.004   0.021
all         no_overlap  361    54      +0.065%    0.894   0.914
all         clean_both  297    46      +0.147%    0.766   0.914
explore     clean_both   77    21      +0.162%    0.882   0.914
validate    clean_both  220    43      +0.142%    0.774   0.914
```

The D20 result is entirely overlap-driven.

5.02 AFTER_HOURS:

```text
all clean_both:       +0.023%
validate clean_both:  -0.198%
```

`5.02 AFTER_HOURS_D20: NO_SIGNAL_AFTER_OVERLAP_CONTROL`

---

## 6. Final decision

```text
P12_4_3_STATUS: DESCRIPTIVE_ONLY
FUNDAMENTAL_CHANGE: NO_SIGNAL
8K_EVENT_DIFFERENCES: DESCRIPTIVE_ONLY
2.02_AFTER_HOURS_D20: NO_SIGNAL_AFTER_OVERLAP_CONTROL
5.02_AFTER_HOURS_D20: NO_SIGNAL_AFTER_OVERLAP_CONTROL
TRADABLE_ALPHA: NOT_CLAIMED
BOOTSTRAP_REPS: 500
FDR_FAMILY_FUNDAMENTAL: 45
FDR_FAMILY_8K: 88
MARKET_WIDE: DATA_BLOCKED
```

---

## 7. Files

- `p12_4_3_fundamental_panel.csv`
- `p12_4_3_fundamental_stats.csv`
- `p12_4_3_8k_panel.csv`
- `p12_4_3_8k_stats.csv`
- `p12_4_3_overlap_sensitivity.csv`
- `p12_4_3_clean_window_stats.csv`
- `p12_4_3_return_differences.csv`
- `p12_4_3_timezone_exit_tests.csv`
- `p12_4_3_period_boundary_tests.csv`
- `p12_4_3_coverage.json`
- `p12_4_3_run_manifest.json`

---

## 8. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P12_4_3_STATUS: DESCRIPTIVE_ONLY
FUNDAMENTAL_ACCESSIONS: 2624
US_8K_ACCESSIONS: 11612
TRADABLE_ALPHA: NOT_CLAIMED
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
P11_PRICE_FACTORS: NO-GO
IBKR_CONNECTED: NO
```

No purchase, VPS, IBKR, paper/shadow, portfolio, merge/main change, or raw-data
upload.
