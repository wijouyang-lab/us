# Historical Membership vs Current Price Panel

Date: 2026-10-28
Research only. No production changes.

## Scope

This audit standardizes two public membership datasets and matches their
reconstructed intervals to the existing 10-year price panel. It does not
recover prices, fill gaps, or claim that a membership dataset is an OHLCV
source.

Outputs:

```text
docs/research/membership_coverage_2026-10-28/
  coiltrade_membership_intervals.csv
  coiltrade_ticker_coverage.csv
  coiltrade_annual_coverage.csv
  shardul_membership_intervals.csv
  shardul_ticker_coverage.csv
  shardul_annual_coverage.csv
```

Script:

```bash
python tools/research/standardize_membership_coverage.py \
  --coiltrade datasets/coiltrade/data/membership.json \
  --shardul-dir datasets/shardul/src/sp500_ticker_history \
  --price-panel research_price_history_sp500_10y.csv \
  --identity-csv docs/research/missing_tickers_identity_2026-10-28.csv \
  --outdir docs/research/membership_coverage_2026-10-28
```

Tests: `tests/test_standardize_membership_coverage.py` (2 passed).

## Method

- Normalize each source separately to:
  `ticker, company_id, membership_start, membership_end, source, source_event_date`.
- Coiltrade: reconstruct the earliest set by reversing the dated change log
  from the current snapshot, then replay changes forward.
- Shardul: start from the first annual `tickers_on_Jan_1` snapshot and replay
  the dated `difference`/`union` changes.
- Do not merge the two sources.
- Price panel: existing 10-year OHLCV, 503 tickers; only its dates are used as
  the trading calendar.
- Expected member-days are counted only inside rebuilt intervals and the price
  panel calendar. Missing prices remain missing.

### Important limitation

These are **community/derived membership records**, not an official daily PIT
membership database. Dated changes let us reconstruct intervals where the
source log is complete, but this audit does not independently prove that every
historical change date is correct. Do not label the output as an authoritative
daily PIT membership set.

## Coiltrade annual coverage

| Year | Members | Member-days expected | Observed | Coverage | Members with any price | Members missing all price |
|---:|---:|---:|---:|---:|---:|---:|
| 2016 | 528 | 38,184 | 25,713 | 67.34% | 353 | 175 |
| 2017 | 551 | 131,401 | 91,399 | 69.56% | 373 | 179 |
| 2018 | 547 | 131,547 | 94,426 | 71.78% | 383 | 164 |
| 2019 | 546 | 132,072 | 97,948 | 74.16% | 401 | 147 |
| 2020 | 540 | 132,541 | 102,600 | 77.41% | 410 | 130 |
| 2021 | 543 | 132,068 | 104,806 | 79.36% | 420 | 123 |
| 2022 | 541 | 131,228 | 106,857 | 81.43% | 434 | 107 |
| 2023 | 538 | 130,518 | 110,187 | 84.42% | 449 | 90 |
| 2024 | 538 | 131,564 | 114,612 | 87.12% | 464 | 74 |
| 2025 | 540 | 130,480 | 117,330 | 89.92% | 480 | 62 |
| 2026* | 532 | 64,096 | 59,476 | 92.79% | 490 | 42 |

`*` 2026 is capped at the dataset鈥檚 last dated change (2026-06-30), not the
price panel鈥檚 October end.

## Shardul annual coverage

| Year | Members | Member-days expected | Observed | Coverage | Members with any price | Members missing all price |
|---:|---:|---:|---:|---:|---:|---:|
| 2016 | 510 | 36,942 | 24,325 | 65.85% | 334 | 176 |
| 2017 | 533 | 127,023 | 86,593 | 68.17% | 354 | 180 |
| 2018 | 529 | 126,941 | 89,569 | 70.56% | 365 | 164 |
| 2019 | 534 | 127,288 | 93,491 | 73.45% | 387 | 149 |
| 2020 | 525 | 127,788 | 99,487 | 77.85% | 399 | 126 |
| 2021 | 526 | 127,282 | 102,034 | 80.16% | 409 | 117 |
| 2022 | 528 | 126,465 | 104,814 | 82.88% | 428 | 100 |
| 2023 | 522 | 125,770 | 108,788 | 86.50% | 445 | 78 |
| 2024 | 523 | 126,780 | 113,881 | 89.83% | 462 | 61 |
| 2025 | 524 | 125,773 | 116,860 | 92.91% | 479 | 46 |
| 2026* | 526 | 96,101 | 93,112 | 96.89% | 501 | 25 |

## Ticker status

| Dataset | Complete price coverage | Partial | No price | Reconstructed tickers |
|---|---:|---:|---:|---:|
| coiltrade | 491 | 6 | 219 | 709 |
| shardul | 503 | 5 | 229 | 729 |

`Complete` means every day in the rebuilt interval had a price row in the
existing panel. It does not mean the membership date itself is official.

## New historical members

At the full-history level, the earlier audit found:

- coiltrade: **381** membership tickers outside the 503-name price panel
- shardul: **491** membership tickers outside the 503-name price panel

Inside the 2016鈥?026 price-panel window:

| Dataset | New tickers in window | With any price | Zero price |
|---|---:|---:|---:|
| coiltrade | 218 | **0** | **218** |
| shardul | 228 | **0** | **228** |

The larger 381/491 counts include pre-2016 names that cannot be matched to the
10-year panel. **Membership expansion does not add any OHLCV coverage.**

## Failed-ticker overlap

- coiltrade membership covers 90 of the 98 failed tickers inside the rebuilt
  2016鈥?026 intervals; all-history overlap is 91/98.
- shardul covers 93 of 98 inside the window; all-history overlap is 94/98.
- Coverage in this table is membership/identity coverage only. The failed
  tickers still have no validated historical OHLCV.

## Decision

Membership coverage is better than the current price panel, but price coverage
is unchanged. The data-research gate remains blocked:

- member-day coverage below 95% in every year except the incomplete 2026 tail;
- many historical names have zero price rows;
- no independent OHLCV source;
- no corporate-action validation.

Do not treat this membership dataset as a price source or as proof of a
survivorship-free backtest.
