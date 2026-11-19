# P17 PIT Fundamental Entry/Exit Research

Date: 2026-11-20
Branch: `research/p17-pit-fundamental-entry-exit`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **DATA_BLOCKED at security identity; no fundamental backtest**

## 1. Executive answer

The local SEC facts are rich enough to calculate quality/growth metrics, but the
historical **ticker → CIK → security identity** layer is not available at
research coverage. Therefore P17 does not run a fundamental entry, fundamental
exit, or full portfolio backtest. Doing so would mix current CIKs into historical
S&P members and fabricate PIT exposure.

```text
P17_IDENTITY = DATA_BLOCKED
P17_SEC_FACTS = AVAILABLE_BUT_IDENTITY_BLOCKED
P17_ENTRY_QUALITY = DATA_BLOCKED
P17_ENTRY_GROWTH = DATA_BLOCKED
P17_ENTRY_VALUE = DATA_BLOCKED
P17_EXIT_FUNDAMENTAL = DATA_BLOCKED
P17_FULL_SYSTEM = NOT_RUN
P17_PRODUCTION_READY = FALSE
```

## 2. PIT identity coverage

Source: P13.1.2 5Y expected membership + local P10 identity crosswalk.

| status | expected member-days | share |
|---|---:|---:|
| IDENTITY_CONFIRMED | 2,516 | **0.397%** |
| IDENTITY_CONFLICT | 399 | 0.063% |
| UNRESOLVED | 631,056 | **99.54%** |

- expected member-days: 633,971
- unique historical tickers: 607
- mapped tickers: **3**
- unique CIKs: 23
- identity conflicts: 1

P10's crosswalk contains only 80 historical names (mostly known conflicts /
delisted review cases); it is not a full S&P identity master. Current
`company_tickers.json` cannot be used as a historical mapping.

## 3. SEC facts availability

Local SEC CompanyFacts panel:

```text
6,391,195 rows
PIT field `pit_available_date`: 0 nulls
PIT range: 2013-03-19 .. 2026-11-05
forms include 10-Q 4,348,709; 10-K 1,535,053; 20-F 233,785; 6-K 104,587;
10-Q/A 37,549; 10-K/A 37,424
```

This is sufficient for a technical facts replay, but not for joining to PIT
members if 99.5% of member-days have no verified identity. Building ROA/ROE/OCF
on this join would be a current-CIK backfill.

## 4. What was not run

- Quality: Gross Profit/Assets, CFO/Assets, accruals.
- Growth: revenue/operating income/CFO/EPS growth.
- Value: EBIT/EV, book-to-market, earnings yield.
- Fundamental deterioration exit.
- Regime + entry + exit portfolio.
- Trade ledger/NAV/cost/OOS.

All are `NOT_RUN` because the identity gate blocks them.

## 5. P16 engine audit

Separate audit (`P16_ENGINE_AUDIT.md`) found:

- IC uses ranked score while portfolio uses raw momentum;
- `pct_change()` default fill usage;
- regime counts reported over full series (main 2020–2024: 979/1,258 RISK_ON);
- regime only blocks entries, no exposure overlay;
- stock adjusted_close vs SPY close benchmark mismatch;
- Sharpe = CAGR/vol, not daily excess-return Sharpe;
- no per-trade ledger / stale-price handling tests.

P16 results are not used as P17 evidence.

## 6. Core questions

1. Historical SEC data usable for reliable PIT selection? **No, not with current identity coverage.**
2. Quality/growth/value incremental info? **Not tested; DATA_BLOCKED.**
3. Do combinations beat single factors? **Not tested.**
4. Does fundamental exit help? **Not tested.**
5. Does exit add only turnover? **Not tested.**
6. Does regime improve full system? **No full system; P16 audit only.**
7. 10 bps OOS advantage? **No result.**
8. What can free data support? **Price-only exploratory research after identity/price audit; not fundamental PIT selection.**

## 7. Required unblock

1. A historical identity master with valid_from/valid_to and CIK evidence for
   the full S&P membership union, including delisted/renamed tickers.
2. A SEC facts replay using filing/accepted timestamps and amendments.
3. Historical shares/debt/cash for EV; otherwise Value remains blocked.
4. A trade-level portfolio engine with next-session execution and stale-price
   rules.

No purchase, no new vendor, no API key was used.

## 8. Files

- `tools/research/p17_multifactor_entry_exit.py`
- `tests/test_p17_multifactor_entry_exit.py`
- `docs/research/P16_ENGINE_AUDIT.md`
- `data/research/p17/p17_security_identity.csv`
- `p17_identity_conflicts.csv`
- `p17_identity_coverage.json`
- `p17_identity_evidence.csv`
- `p17_sec_facts_audit.csv`
- `p16_engine_audit.json`
- `p17_summary.json`
- `p17_manifest.json`

No model call, no API key, no broker, no order.
