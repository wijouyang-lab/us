# Value Share-Class and OHLC Reconciliation — P5.3

Date: 2026-11-05
Branch: `research/akshare-us-28-coverage-p52`
PR: #497 (Draft)
Status: **AUDIT / DATA CORRECTION — no production changes**

## 1. Result summary

| Item | Result |
|---|---:|
| Current quotes available | 28/28 |
| History non-empty | 28/28 |
| qfq basic OHLCV quality | 23/28 |
| Value market-cap input ready | **28/28** |
| Share-class records present | 28/28 |
| GARP forward EPS ready | 0/28 |
| SCORE_READY | 0/28 |
| BACKTEST_READY | 0/28 |

The 28/28 Value figure means only:

```text
quote price + SEC shares + market-cap unit/value check passed
```

It does **not** mean Value score or backtest readiness.

## 2. SEC share-class corrections

The P5.2 registry used `f.get("acc")`, but SEC CompanyFacts uses `accn`. It also
selected stale or wrong-class facts for five companies.

Corrected records:

| Ticker | Shares | Basis | As-of | Accession | Form | Filed | SEC source |
|---|---:|---|---|---|---|---|---|
| NKE | 1,485,308,829 | Class A + Class B | 2026-09-28 | `0000320187-26-000193` | 10-Q | 2026-10-02 | `https://www.sec.gov/Archives/edgar/data/320187/000032018726000193/nke-20260831.htm` |
| BRK.B | 2,140,710,161 | Class B equivalent (A x 1500) | 2026-07-29 | `0001193125-26-341032` | 10-Q | 2026-08-10 | `https://www.sec.gov/Archives/edgar/data/1067983/000119312526341032/brka-20260630.htm` |
| NEE | 2,097,306,049 | Common shares | 2026-09-30 | `0000753308-26-000081` | 10-Q | 2026-10-21 | `https://www.sec.gov/Archives/edgar/data/753308/000075330826000081/nee-20260930.htm` |
| DUK | 779,702,193 | Common shares | 2026-07-31 | `0001326160-26-000040` | 10-Q | 2026-08-04 | `https://www.sec.gov/Archives/edgar/data/1326160/000132616026000040/duk-20260630.htm` |
| PLD | 950,513,000 | Common shares | 2026-10-26 | `0001193125-26-436160` | 10-Q | 2026-10-28 | `https://www.sec.gov/Archives/edgar/data/1045609/000119312526436160/pld-20260930.htm` |

All 28 registry records now carry:

```text
source_url
accession
form
filed
as_of
period_end where applicable
shares_basis
```

NKE combines Class A and Class B. BRK.B uses Class A-to-B 1:1500 conversion to
a B-equivalent count; it is not the 941,481 Class A share fact used previously.

## 3. Value market-cap reconciliation

Method:

```text
estimated_market_cap = AkShare latest quote price × SEC shares
ratio = AkShare total market cap / estimated_market_cap
```

Data:

```text
data/research/value_share_class_reconciliation_2026-11-05.json
```

All 28 pass:

```text
VALUE_MARKET_CAP_INPUT_READY = 28/28
SCORE_READY = 0/28
BACKTEST_READY = 0/28
```

Five corrected companies:

| Ticker | Quote | SEC shares | Estimated cap | AkShare cap | Ratio | Shares age |
|---|---:|---:|---:|---:|---:|---:|
| NKE | 40.925 | 1,485,308,829 | 60.786B | 60.786B | 1.0000 | 38 days |
| BRK.B | 573.74 | 2,140,710,161 | 1.2282T | 1.2282T | 1.0000 | 99 days |
| NEE | 88.18 | 2,097,306,049 | 184.940B | 184.940B | 1.0000 | 36 days |
| DUK | 129.45 | 779,702,193 | 100.932B | 100.932B | 1.0000 | 97 days |
| PLD | 128.38 | 950,513,000 | 122.027B | 122.027B | 1.0000 | 10 days |

The market-cap unit is USD under the US-board convention. This is an input
readiness result, not a valuation score.

## 4. OHLC anomalies — targeted raw/qfq probe

Probe:

```text
run: https://github.com/wijouyang-lab/us/actions/runs/41880105908
artifact: 13349520901
scope: NVDA, HD, HON, NEE, JPM only
```

Evidence:

```text
data/research/ohlc_anomaly_probe_2026-11-05.json
```

### NVDA

qfq produced 20 non-positive rows from 2016-01-14 through 2016-02-17, for
example:

```text
2016-01-14  O 0.011  C 0.011  H 0.019  L -0.010
2016-01-15  O -0.018 C -0.028 H -0.009 L -0.040
2016-02-17  O -0.022 C -0.014 H -0.008 L -0.025
```

Raw history has no non-positive rows and passes basic OHLCV checks.

Classification:

```text
QFQ_ADJUSTMENT_OUT_OF_RANGE
```

This is an adjustment/upstream defect, not a real price series. NVDA remains
quality-failed; raw passing alone is not proof that qfq is correct.

### HD

```text
date: 2017-07-24
qfq: O 81.660 C 79.570 H 81.600 L 79.160
raw: O 146.750 C 144.660 H 146.690 L 144.250
```

Open > high in both qfq and raw. This looks like vendor OHLC boundary/rounding
inconsistency, not a split or dividend. Keep quality-failed.

### HON

```text
date: 2017-07-24
qfq: O 99.851 C 100.908 H 101.036 L 99.881
raw: O 136.730 C 137.800 H 137.930 L 136.760
```

Open < low in both qfq and raw. Same upstream boundary inconsistency; keep
quality-failed.

### NEE

```text
date: 2017-07-14
qfq: O 19.711 C 19.851 H 19.976 L 19.773
raw: O 141.070 C 141.630 H 142.130 L 141.320
```

Open < low in both. Same classification; no confirmed corporate action.

### JPM

```text
date: 2017-07-11
qfq: O 55.340 C 54.810 H 55.260 L 54.300
raw: O 93.330 C 92.800 H 93.250 L 92.290
```

Open > high in both. Same classification; no confirmed corporate action.

### Final OHLC status

```text
NVDA: DATA_QUALITY_FAIL (qfq adjustment)
HD:   DATA_QUALITY_FAIL (raw + qfq boundary)
HON:  DATA_QUALITY_FAIL (raw + qfq boundary)
NEE:  DATA_QUALITY_FAIL (raw + qfq boundary)
JPM:  DATA_QUALITY_FAIL (raw + qfq boundary)

Other 23: DATA_QUALITY_PASS (basic qfq checks only)
BACKTEST_READY: 0/28
PIT 95%/98% gates: unchanged
```

No anomaly was reclassified as valid merely because raw data passed.

## 5. GARP and residual blockers

Forward EPS remains `DATA_BLOCKED` for all 28:

```text
GARP forward EPS ready = 0/28
PEG = DATA_BLOCKED
```

Hedge remains blocked due lack of free historical option chains and costs.

## 6. Tests

```text
tests/test_akshare_us_28_coverage.py    7 passed
tests/test_akshare_us_28_value.py       5 passed
```

Test coverage includes:

- NKE Class A + Class B registry record;
- BRK.B Class B-equivalent record;
- `accn`/accession presence;
- stale-share gate;
- market-cap ratio/unit gate;
- qfq/raw OHLC anomaly row capture.

## 7. Boundaries

- No production scan, scoring, trading, stop-loss, ledger or Dashboard changes.
- No full SEC accession scan.
- No paid API.
- No merger/deployment.
- Value `INPUT_READY` is not `SCORE_READY` or `BACKTEST_READY`.
- The five OHLC failures remain failures.
