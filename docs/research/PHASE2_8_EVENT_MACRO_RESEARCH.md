# Phase 2.8 Event and Macro Factor Research

Date: 2026-10-30
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`
No production changes. No `VALIDATED_ALPHA`.

## 1. Data audit answers

1. **Which SEC events are obtainable?**
   Submissions metadata for 10-Q, 10-K, 8-K, including forms and items.
2. **Real public time saved?**
   `acceptanceDateTime` is saved, but it is not proof of first public
   visibility. No historical first-seen record exists.
3. **Historical earnings and release times?**
   Filing-level dates/times are available; exact first-public time is not
   verified.
4. **Historical macro first-release values?**
   No ALFRED vintage access in this environment; current FRED series are not
   first-release PIT.
5. **Verifiable historical news timestamps?**
   No free historical archive with reproducible first-public timestamps.
6. **Stable free sources?**
   SEC submissions/companyfacts and the local S&P membership/CIK table;
   FRED current series; official RSS (current only).
7. **Severe coverage gaps?**
   Historical delisted issuers, exact first-public time, analyst expectations,
   macro vintages, historical news archive.

## 2. SEC event sample

Actual sample from `data.sec.gov/submissions`:

| Ticker | CIK | Events |
|---|---|---:|
| AAPL | 0000320193 | 30 |
| MSFT | 0000789019 | 30 |
| NVDA | 0001045810 | 30 |
| TSLA | 0001318605 | 30 |
| AMZN | 0001018724 | 30 |

Total: **150 events**, 5 tickers.

| Event type | Count |
|---|---:|
| Earnings indicator (10-Q/10-K/8-K 2.02) | 92 |
| 8-K events | 107 |
| Management change (8-K 5.02) | 23 |

All events:

```text
source_confidence = official_sec_submissions
timestamp_confidence = official_acceptance_time_not_first_public
pit_eligible = false
```

`acceptanceDateTime` is not first-public-availability proof; no event is
admitted to formal PIT.

## 3. Event factor engine

`tools/research/event_data.py`
`tools/research/event_factor_engine.py`

Implemented:

- canonical event fields;
- UTC normalized `published_at`;
- event dedupe by accession ID;
- next-trading-session alignment (after close/weekend);
- `Earnings_Release_Indicator`;
- `SEC_8K_Event_Count` (trailing 20 calendar days);
- `Management_Change_Indicator`;
- explicit `UNAVAILABLE_DATA` for missing fundamentals/macro.

Unavailable in the actual sample:

| Factor | Available / 150 |
|---|---:|
| Revenue_Growth | 0 |
| EPS_Growth | 0 |
| Gross_Margin_Change | 0 |
| Operating_Margin_Change | 0 |
| FCF_Change | 0 |
| Macro_Rate_Change | 0 |
| CPI_Surprise | 0 |
| Payroll_Surprise | 0 |
| VIX_Regime | 0 |

No values were fabricated. Analyst expectations were unavailable, so no
Revenue/EPS surprise is calculated.

## 4. Event sample returns (descriptive)

Using `forward_return.py`, entry at next-session open:

| Horizon | Matured | Mean | Median | Positive |
|---:|---:|---:|---:|---:|
| 1D | 144 | 鈭?.22% | 鈭?.49% | 38.4% |
| 5D | 144 | +0.23% | 鈭?.54% | 43.1% |
| 10D | 144 | +0.47% | 鈭?.59% | 47.9% |
| 20D | 142 | +1.68% | +1.50% | 59.9% |
| 60D | 135 | +6.34% | +2.94% | 63.0% |

This is a 5-ticker, 150-event descriptive sample. It is not an event alpha
estimate, not PIT, and not a strategy.

## 5. Macro / news feasibility

| Source | Status |
|---|---|
| FRED current series | accessible in principle; no ALFRED vintage key in environment |
| ALFRED vintage | requires API key; not used |
| BLS CPI/employment releases | release pages accessible; no complete machine-readable history |
| FOMC statements/minutes | official pages, exact release time partly available |
| Historical news archive | no free reproducible archive |
| CEO/CFO speeches | no complete historical timestamp archive |
| VIX | free current/history via market data, but not loaded into this event panel |

Consequences:

- `CPI_Surprise`, `Payroll_Surprise`: unavailable (no expectations/vintage).
- `Macro_Rate_Change`: unavailable as first-release PIT series.
- `VIX_Regime`: not computed in this sample.
- No news sentiment or speech factor is generated.

## 6. Incremental validation

Not performed:

- only 5 tickers and 150 events;
- no macro vintage;
- no news timestamps;
- no event-and-technical merged panel with sufficient sample;
- daily cross-sectional IC would be dominated by 5 names.

No claim of incremental information beyond technical factors.

## 7. Tests

`tests/test_event_data.py`: 5 passed
`tests/test_event_factor_engine.py`: 4 passed

Coverage:

- after-close 鈫?next session;
- weekend 鈫?next session;
- naive timestamp rejected;
- duplicate event dedupe;
- event PIT false;
- earnings/8-K count;
- management change;
- unavailable fundamentals remain null.

Full CI after commit.

## 8. Survivorship / PIT

- current 503-name price universe, survivorship-biased;
- local S&P membership source is third-party (MIT-licensed, CIK-aware), not
  official S&P DJI;
- 713 historical tickers absent from price panel;
- no delisting returns;
- Phase 2.6 has **0** PIT dates.

## 9. Conclusion

- Event data foundation exists for SEC metadata and event timestamps.
- Real SEC event sample was computed.
- Exact first-public time is still unverified.
- Fundamental/macro/news factors remain unavailable and are explicitly null.
- No incremental event/macro alpha is demonstrated.
- No event strategy is admitted.

## 10. Artifacts

- `tools/research/event_data.py`
- `tools/research/event_factor_engine.py`
- `tools/research/event_sample_study.py`
- `tests/test_event_data.py`
- `tests/test_event_factor_engine.py`
- `docs/research/sec_event_sample_2026-10-30.json`
- `docs/research/sec_event_factors_2026-10-30.csv`
- `docs/research/sec_event_study_sample_2026-10-30.json`
