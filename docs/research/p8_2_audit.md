# P8.2 Data Quality, PIT Coverage, Costs and Walk-forward

Date: 2026-11-08
Status: **P8_2_FORMAL_METHOD_NO_GO · RESEARCH_ONLY**

P8 and P8.1 artifacts are preserved. This is a new, separate P8.2 result set.

## 1. 109-ticker anomaly audit

- Tickers checked: 109
- Anomaly rows: 3,041
- Tickers with at least one recorded anomaly: 109

Classification:

```text
VERIFIED_CORRUPT             2,466
VERIFIED_CORPORATE_ACTION        0
VERIFIED_REAL_RETURN             2  (GME)
UNRESOLVED                     573
```

Every row has ticker, anomaly date, previous date, raw open/close, adjusted
close, volume, classification, evidence and source.

No corporate action was classified without evidence; the 573 unresolved rows
remain unresolved rather than being called corruption.

Special review:

- **CBE**: incompatible adjusted price bases; a 0.1535 price becomes 18.8856
  the next month; classified VERIFIED_CORRUPT.
- **ACS**: alternates between ~$0.14 and ~$25; zero-volume/stale sessions;
  classified VERIFIED_CORRUPT.
- **GME**: the 2021 squeeze is real; classified VERIFIED_REAL_RETURN.

Formal method C isolates only the anomalous ticker-dates/holding intervals. It
does **not** delete the ticker's entire history before the anomaly. Method B
(full-history exclusion of 109) remains only a diagnostic comparison.

Files:

```text
data/research/p8_2/ticker_anomaly_audit.csv
data/research/p8_2/ticker_anomaly_summary.json
```

## 2. PIT coverage with full denominator

Denominator: **all effective-dated S&P 500 member-days**, 2000-01-03..2024-12-31.

```text
member-days:          1,095,490
valid OHLCV:            986,358   (90.04%)
verified after audit:   986,198   (90.02%)
quarantined:                160
unknown:                109,132   (9.96%)
```

The denominator is not reduced by deleting bad tickers.

Outputs:

```text
pit_coverage_summary.json
pit_coverage_by_year.csv
pit_coverage_by_ticker.csv
```

This replaces the conditional 92.45% figure, which used only available names.

## 3. Three data methods

| Method | Definition |
|---|---|
| A_RAW | no anomaly handling; contamination control |
| B_EXCLUDE_ALL | P8.1 diagnostic: remove all 109 tickers |
| C_PER_DATE | formal: isolate anomalous ticker-dates/intervals only |

### Corrected results (10 bps per side, new cost definition)

| Strategy | A CAGR | B CAGR | C CAGR | C OOS CAGR | C HAC active t | C max DD |
|---|---:|---:|---:|---:|---:|---:|
| Momentum20 | 52.5% | 4.1% | 7.7% | 5.4% | -0.41 | -67.9% |
| Momentum60 | 43.2% | 7.6% | 5.7% | 7.7% | -2.09 | -59.4% |
| Momentum120 | 52.8% | 8.9% | 11.4% | 11.4% | 0.22 | -63.6% |
| Trend MA200 | 51.5% | 8.1% | 10.4% | 8.0% | -0.10 | -61.0% |
| Low Vol60 | 12.0% | 10.2% | 9.5% | 11.4% | -1.06 | -34.7% |
| Reversal5 | 41.1% | 6.4% | 14.6% | 8.6% | 1.34 | -76.0% |

Method C is the formal result. All C HAC active t-values are below 1.64 and
all BH q values are >0.10. **No GO.**

Methods A/B are diagnostic; B's coverage must not be presented as formal C
coverage.

## 4. Cost correction

Old:

```text
turn = |hold XOR prev| / n
cost = 10bps * turn * 2
```

`turn` already includes both additions and removals, so multiplying by 2
double-counted the two sides.

New:

```text
turn = |hold XOR prev| / n          # total two-sided traded fraction
cost = 10bps * turn
initial build: turn = 1.0 -> one 10bps cost
```

Examples of the correction:

- Momentum20: old 37.0 bps/month vs new 18.5 bps/month.
- Momentum120: old 18.1 bps vs new 9.1 bps.
- Low Vol60: old 14.5 bps vs new 7.25 bps.

ETF cost changed from unconditional 20 bps/month to 10 bps × L1 weight change.
Average ETF cost is now about 3.45–4.58 bps/month. Full details in
`cost_model_audit.json`.

## 5. Walk-forward with corrected costs

60-month train / 1-month purge / 12-month test; strategy selection only on
training Sharpe; 10 bps charged once when the selected strategy changes.

```text
windows: 19
switches: 6
selected CAGR: 8.92%
selected Sharpe: 0.540
selected max drawdown: -63.67%
HAC active vs EW: -0.391
p-value: 0.695
```

The selected HAC is against equal weight, not zero. Gate: **NO-GO** (drawdown
and no active significance). Fixed strategy test results are in
`walk_forward_results.json`; the tail months not included in a complete test
window are recorded.

## 6. BH consistency

Primary family: 8 strategies (6 PIT + 2 ETF).
All primary q values are > 0.10.

If A/B/C methods are treated as independent hypotheses, the 18-hypothesis
sensitivity family is also reported; no correction improves any result to GO.

P8.1's old q values are preserved in `bh_consistency.json`; the difference from
P8.2 is documented, not silently overwritten.

## 7. Final status

```text
GO:            0
NO-GO:         8 primary strategies
DATA BLOCKED:  Nasdaq-100 interval, Dow 30 interval,
               historical fundamental PIT, 2025-2026 historical panel
```

No `RESEARCH_SHADOW_P8` is launched. P7 `RESEARCH_SHADOW_P7` remains independent.

## 8. Current facts

- S&P 500 PIT is the only valid historical universe.
- Nasdaq-100 / Dow 30 interval files are still absent.
- Historical fundamental PIT remains blocked; current P7.1 Value is not a
  historical backtest.
- No PAPER-50000, IBKR, shorting, leverage or options.

## 9. Files

```text
data/research/p8_2/ticker_anomaly_audit.csv
data/research/p8_2/ticker_anomaly_summary.json
data/research/p8_2/pit_coverage_summary.json
data/research/p8_2/pit_coverage_by_year.csv
data/research/p8_2/method_comparison.json
data/research/p8_2/monthly_A_RAW.csv
data/research/p8_2/monthly_B_EXCLUDE_ALL.csv
data/research/p8_2/monthly_C_PER_DATE.csv
data/research/p8_2/cost_model_audit.json
data/research/p8_2/walk_forward_results.json
data/research/p8_2/bh_consistency.json
data/research/p8_2/strategy_gate_results_p82.csv
data/research/p8_2/p8_2_status.json
```
