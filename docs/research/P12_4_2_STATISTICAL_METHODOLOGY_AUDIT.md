# P12.4.2: Fundamental and 8-K Statistical Methodology Audit

Date: 2026-11-17
Branch: `research/p12-event-fundamental-feasibility`
Status: **DESCRIPTIVE_ONLY; fundamental NO_SIGNAL**

P12.4.1 files are preserved. This audit uses `data/research/p12_4_2/`.

---

## 1. Fixed methodology

1. Reused P12.3.3 `_et_end_of_day()`; no fixed 24-hour copy.
2. Fundamental entry uses US/Eastern trading semantics:
   - filing-date-only -> next trading day;
   - acceptance before 16:00 ET on a session -> same session close;
   - acceptance after 16:00 ET or non-session -> next session.
3. Bootstrap: 500 CIK-cluster resamples, seed `20261117`.
4. Bootstrap p uses finite-sample correction; no p=0 output.
5. Fundamental BH across 45 tests (5 metrics x 3 horizons x all/explore/validate).
6. 8-K BH across 88 item/session/period tests.
7. Overlap: trading-day D20 window intersection, both events marked.
8. 2.02 AFTER_HOURS clean samples split by period.

---

## 2. Sample

```text
fundamental accessions: 2,624
fundamental issuers:     114
US 8-K accessions:      11,612
US 8-K issuers:            133
```

D0/D1/D5/D10/D20 available: 10,945 / 10,944 / 10,941 / 10,930 / 10,869.

---

## 3. Fundamental

Best validation-period cells:

```text
cash_conversion / 10d: IC 0.0496, p 0.0359, BH q 0.7455
op_margin / 5d:        IC 0.0422, p 0.2196, q 0.7455
revenue / 5d:          IC 0.0383, p 0.2794, q 0.7455
```

No fundamental test survives BH.

```text
FUNDAMENTAL_CHANGE: NO_SIGNAL
```

---

## 4. 8-K

After 500-draw bootstrap and BH:

```text
2.02 INTRADAY D5:      +0.609%, p 0.060, q 0.532
2.03 AFTER_HOURS D20:  +1.107%, p 0.016, q 0.084
5.02 AFTER_HOURS D20:  +0.675%, p 0.004, q 0.042
2.02 AFTER_HOURS D20:  +0.711%, p 0.004, q 0.042
```

The apparent D20 signals are overlap-driven:

5.02 AFTER_HOURS:

```text
period      sample       n     issuers  D20 mean   p       q
all         all        1585    123      +0.675%    0.004   0.042
all         no_overlap  167     79      +0.035%    0.898   0.914
all         clean_both  166     79      +0.023%    0.906   0.914
validate    all        1195    121      +0.830%    0.004   0.042
validate    no_overlap  125     68      -0.179%    0.739   0.914
validate    clean_both  124     68      -0.198%    0.707   0.914
```

5.02 is **NO_SIGNAL after overlap control**.

2.02 AFTER_HOURS:

```text
period      sample       n     issuers  D20 mean   p       q
all         all        1493     84      +0.711%    0.004   0.042
all         clean_both  297     46      +0.147%    0.766   0.914
explore     clean_both   77     21      +0.162%    0.882   0.914
validate    clean_both  220     43      +0.142%    0.774   0.914
```

The full-sample 2.02 D20 signal disappears under overlap control. It is not a
validated candidate.

---

## 5. 2.02 AFTER_HOURS detailed clean table

File: `p12_4_2_clean_window_stats.csv`

```text
period      sample       horizon n     issuers  mean      p       q
all         all          5       1501    84     +0.221%   0.064   0.230
all         all          20      1493    84     +0.711%   0.004   0.021
all         no_overlap   5        365    54     +0.299%   0.140   0.300
all         no_overlap   20       361    54     +0.065%   0.894   0.914
all         no_same_day  5       1219    79     +0.253%   0.072   0.230
all         no_same_day  20      1212    79     +0.812%   0.004   0.021
all         clean_both   5        300    46     +0.487%   0.032   0.192
all         clean_both   20       297    46     +0.147%   0.766   0.914
validate    all          5       1150    82     +0.240%   0.060   0.230
validate    all          20      1142    82     +0.637%   0.012   0.057
validate    clean_both   5        223    43     +0.543%   0.044   0.230
validate    clean_both   20       220    43     +0.142%   0.774   0.914
```

No clean 2.02 D20 result survives. The only clean D5 result is exploratory and
does not survive FDR.

---

## 6. Final decision

```text
P12_4_2_STATUS: DESCRIPTIVE_ONLY
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

- `data/research/p12_4_2/p12_4_2_fundamental_panel.csv`
- `data/research/p12_4_2/p12_4_2_fundamental_stats.csv`
- `data/research/p12_4_2/p12_4_2_8k_panel.csv`
- `data/research/p12_4_2/p12_4_2_8k_stats.csv`
- `data/research/p12_4_2/p12_4_2_overlap_sensitivity.csv`
- `data/research/p12_4_2/p12_4_2_clean_window_stats.csv`
- `data/research/p12_4_2/p12_4_2_timezone_entry_tests.csv`
- `data/research/p12_4_2/p12_4_2_run_manifest.json`

---

## 8. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P12_4_2_STATUS: DESCRIPTIVE_ONLY
FUNDAMENTAL_CHANGE: NO_SIGNAL
TRADABLE_ALPHA: NOT_CLAIMED
BOOTSTRAP_REPS: 500
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
P11_PRICE_FACTORS: NO-GO
IBKR_CONNECTED: NO
```

No purchase, VPS, IBKR, paper/shadow, portfolio, merge/main change, or raw data
upload.
