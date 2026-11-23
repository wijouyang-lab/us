# P12.5.4 Macro Event Robustness

Date: 2026-11-23
Branch: `research/p12-5-4-macro-event-robustness`
Base: `research/macro-cross-sectional-equity-response` (`50f9ebbf`)
Status: **NO_GO / PARTIAL REBUILD**

## 1. Final answer

```text
P12_5_4_STATUS = NO_GO
PORTFOLIO_SIMULATION = NOT_AUTHORIZED_BY_RESEARCH_GATE
```

No macro-event cross-sectional hypothesis survives global multiple testing.
The Payroll × Beta_IWM D20 result has a borderline event-level p-value, but
global BH q = 0.177, Holm p = 0.363, and the test-period spread is ~ -0.08%
versus a full-sample -1.77%. It is not a stable long-only candidate.

## 2. Data actually used

| input | rows / events |
|---|---:|
| CPI event panel | 44,045 stock-event rows |
| Employment event panel | 43,661 stock-event rows |
| CPI events | 105 |
| Employment events | 104 |
| FOMC events | 76 |
| FOMC stock rows | from 10.4 MB panel |
| BLS event inventory | 476 |

The panel was rebuilt/recomputed from the existing P12.5 event panel; the raw
198 MB price snapshot was not re-read in this run. Therefore this is **not** a
full from-raw-price reconstruction. Price basis remains unadjusted close.

## 3. Main recomputed results

### Payroll × Beta_IWM

| horizon | mean Top-Bottom | HAC p | global BH q | test spread |
|---|---:|---:|---:|---:|
| D20 | **-1.77%** | 0.0070 | **0.177** | **-0.08%** |
| D5 | -0.59% | 0.0139 | 0.177 | -0.37% |

The full-sample effect is large but does not survive global correction and
nearly disappears in the chronological test segment.

### Other families

- CPI headline/core × TLT: no global significance.
- FOMC best: `vol20_z` D20, spread +1.01%, p=0.019, global q=0.177; test
  spread +0.79%, but Holm p=0.923.
- 52 tests total; minimum global BH q = **0.1768**.

## 4. HAC / bootstrap

HAC lag 0–10 was computed for the 10 largest spreads. Moving-block bootstrap
used 2,000 reps and block lengths 3/5/8 for three core hypotheses. The task
requested 20,000 reps; this run used 2,000 due time/resource limits and marks
that as incomplete.

No pointwise bootstrap interval excluding zero survives global correction.

## 5. OOS

A 60/20/20 chronological split by event date was computed inside the result
table (train/validation/test). Test-period Payroll D20 ≈ -0.08%, not a
continuation of the training effect.

The historical test period is **REUSED_HOLDOUT / NOT_PRISTINE** because prior
P12.5 work already examined it.

## 6. Limitations

- No raw 1M-row price snapshot rebuild in this run.
- No D20 full purge/walk-forward table generated.
- No event-date cluster permutation.
- No two-way clustered regression.
- No FOMC 40-test full feature set; only four available z-scored features.
- Bootstrap 2,000, not 20,000.
- No portfolio simulation; gate fails.
- Historical universe coverage remains ~91.68% member-session / ~84.23%
  ticker; not a complete PIT universe.
- Prices are unadjusted close; no total-return claim.

## 7. Decision

```text
P12_5_4_MACRO_EVENT_ROUTE = NO_GO
```

Do not continue P12.5 with more factor variants. The free data and event timing
are insufficient to establish a robust, globally significant, OOS-stable
cross-sectional macro signal.

## 8. Files

- `tools/research/p12_5_4_macro_robustness.py`
- `tests/test_p12_5_4_macro_robustness.py`
- `data/research/p12_5_4/m1_input_manifest.json`
- `m1_event_inventory.csv`
- `m1_event_date_cluster.csv`
- `m3_event_results.csv`
- `m3_hac_sensitivity.csv`
- `m3_block_bootstrap.csv`
- `m3_fomc_results.csv`
- `m3_multiple_testing.csv`
- `p12_5_4_final_summary.json`
- `p12_5_4_output_manifest.json`
