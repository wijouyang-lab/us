# P10.6 Preflight Report — Fundamental Selection V1

Date: 2026-11-10

## Final conclusion

```text
Value   DATA_BLOCKED
Quality DATA_BLOCKED
GARP    DATA_BLOCKED

READY_FOR_BACKTEST: NO
P10_6_AUTHORIZED:   NO
```

No model is ready for a credible historical backtest. This is a data/PIT
readiness conclusion, not a claim that any model has or lacks alpha.

## 1. Why each model is blocked

| Model | Candidates | Metrics | As-of snapshots | Main blocker |
|---|---:|---:|---:|---|
| Value | 5,453 | 4 | 1 | one 2026-11-05 cross-section; market cap tied to snapshot price |
| Quality | 5,549 | 4 | 1 | one cross-section; filed/accn exist but no historical panel |
| GARP | 5,453 | 6 | 0 | no `data_as_of`; latest-period only |

All three use `PIT_ACCEPTANCE_PROXY`, not verified first-public time.
The current rankings are a current cross-section and cannot be replayed at
historical selection dates.

## 2. Universe

```text
member-days:        1,095,490
verified:             986,198
unknown:              109,132
coverage:                90.02%
required:                95.00%
```

Status: `DATA_BLOCKED`.

Previously identified 98 missing tickers remain unresolved. The historical
S&P 500 member-day universe is not complete enough to avoid survivorship bias.

## 3. Prices / returns

```text
price coverage:         90.02%
delisting returns:      not verified
dividend total return:  not verified
unknown member-days:    109,132
```

Status: `DATA_BLOCKED`.

No usable post-selection return can be computed for all historical members.
Deleting missing names would create survivorship bias, so it is not allowed.

## 4. What is needed to unblock

1. Historical as-of fundamental snapshots for each selection date, keyed to
   accession and acceptance proxy.
2. Historical market cap/price at the same date; no current snapshot backfill.
3. Member-day coverage >= 95% and ticker coverage >= 98%.
4. Verified delisting returns, splits and dividend treatment.
5. A backtest panel that does not delete unresolved names silently.

## 5. What not to do

- Do not backtest current Value/Quality/GARP rankings on history.
- Do not use AAPL's accepted 2018–2019 sample as market-wide data.
- Do not shrink the universe to hide survivorship bias.
- Do not call this `NO_ALPHA`; no qualified OOS backtest was run.

## 6. Safety

```text
P10.6:          NOT AUTHORIZED
Shadow:         NOT STARTED
PAPER-50000:    UNTOUCHED
IBKR:           NOT CONNECTED
Merge:          NOT AUTHORIZED
```
