# Dividend Quality P4.1 Hardening

Date: 2026-11-04
Branch: `research/dividend-quality-p41-hardening`
Stacked target: `research/dividend-quality-p4`

## 1. What changed

P4.1 is a calculation audit, not a feature expansion.

- dividend payout and FCF coverage now require the **same fiscal period**
  (start, end, period type, unit, and non-conflicting fiscal metadata);
- cash dividends, net income, CFO and CapEx are aligned to the latest **common
  fiscal year**, not merely the latest available date;
- each annual series selects one SEC concept; aliases are not spliced;
- continuity requires 5 consecutive fiscal years; insufficient history is
  `INSUFFICIENT_HISTORY`, not `False`;
- consecutive growth resets on a decline or a missing year; total positive years
  is a separate field;
- scores list their components, weights, denominator and version;
- missing components are excluded, never zero-filled;
- banks/insurers/REITs use an industry-specific component set and are not
  cross-ranked against non-financial companies;
- DPS CAGR is blocked unless split-basis evidence is `VERIFIED`.

## 2. Period matching

Statuses after the fix:

| Metric | OK | INSUFFICIENT | PERIOD_MISMATCH | OTHER |
|---|---:|---:|---:|---:|
| Net income payout | 18 | 8 | 2 | 0 |
| FCF dividend coverage | 13 | 0 | 1 | 14 DATA_BLOCKED |

Examples:

- MSFT: annual cash dividends and FY net income now align to the same
  `2025-07-01..2026-06-30` period.
- FY dividends against a different end date are rejected.
- Different concepts such as `PaymentsOfDividends` and
  `PaymentsOfDividendsCommonStock` are not combined in one annual series.

## 3. Continuity and growth

For 22 dividend payers:

| Field | Result |
|---|---:|
| Continuity OK (5 consecutive years) | **19** |
| INSUFFICIENT_HISTORY | **3** |
| Consecutive growth >= 5 years | **17** |
| Total possible annual DPS cuts (>5%) | **10** |
| Split basis VERIFIED | **0** |
| Split basis UNVERIFIED | **22** |

`dividend_cuts` remains descriptive (`POSSIBLE_REDUCTION`), not a formal event.

## 4. Score changes

Old P4 score status:

- 20 companies had a numeric score.

New P4.1 score status:

- **10 SCORE_READY**
- **18 NOT_READY**

Old -> new:

| Ticker | Old | New | Status | Components |
|---|---:|---:|---|---|
| AAPL | 89.1 | 100.0 | SCORE_READY | payout, fcf, continuity |
| MSFT | 100.0 | 100.0 | SCORE_READY | payout, fcf, continuity |
| GOOGL | 66.1 | — | NOT_READY | payout, fcf |
| NVDA | 100.0 | 100.0 | SCORE_READY | payout, fcf, continuity |
| CRM | 66.7 | — | NOT_READY | payout, fcf |
| HD | 88.5 | 79.9 | SCORE_READY | payout, fcf, continuity |
| MCD | 87.7 | 83.6 | SCORE_READY | payout, fcf, continuity |
| NKE | 72.0 | 63.5 | SCORE_READY | payout, fcf, continuity |
| CAT | 92.1 | 100.0 | SCORE_READY | payout, fcf, continuity |
| HON | 71.3 | 88.4 | SCORE_READY | payout, fcf, continuity |
| UNP | 96.9 | 95.0 | SCORE_READY | payout, fcf, continuity |
| CVX | 58.7 | 55.0 | SCORE_READY | payout, fcf, continuity |
| NEE | 95.2 | — | NOT_READY | payout, continuity |
| DUK | 37.4 | — | NOT_READY | continuity |
| UNH | 97.0 | — | NOT_READY | payout, continuity |
| JPM | 100.0 | — | NOT_READY | payout, continuity |
| BAC | 100.0 | — | NOT_READY | continuity |
| MET | 84.6 | — | NOT_READY | payout, continuity |
| PLD | 66.7 | — | NOT_READY | payout, continuity |
| O | 45.2 | — | NOT_READY | payout, continuity |
| JNJ/PFE/XOM | — | — | NOT_READY | insufficient |
| ADBE/AMZN/BRK.B/MRNA/RIVN | — | — | NOT_READY | non-payer |

Changes are caused by stricter periods, missing components and the split-basis
gate. No formula was relaxed to preserve old high scores.

## 5. Industry comparability

| Group | Count |
|---|---:|
| NON_FINANCIAL | 16 payers |
| INDUSTRY_SPECIFIC (bank/insurer/REIT) | 6 payers |

Banks/insurers/REITs do not get an industrial FCF coverage component.
No cross-group rank is produced.

## 6. Split-basis audit

`split_audit.py` requires:

- ticker;
- ratio;
- announcement date;
- effective date;
- official source URL;
- evidence SHA-256;
- verified status.

Current evidence registry is empty, so all payer DPS histories are:

```text
DPS_SPLIT_BASIS_UNVERIFIED
```

Consequences:

- multi-year DPS CAGR is not used in the score;
- no split ratio is inferred from price or from DPS changes;
- no historical DPS is auto-adjusted.

This is intentionally conservative. A future 8-K/IR evidence pass must populate
the registry before DPS CAGR can be scored.

## 7. Files

```text
tools/investment_research/dividend/
  dividend_quality.py          # strict periods, continuity, score v2
  split_audit.py               # split evidence / blocked CAGR
  dividend_quality_report_p41.py

tests/test_dividend_hardening.py
data/research/dividend_quality_p41.json
```

## 8. Tests

- period mismatch and insufficient history;
- missing fiscal year not continuous;
- consecutive growth resets;
- missing components not zero;
- bank excludes FCF component;
- unverified split blocks CAGR;
- actual 28-company old/new report.

## 9. Remaining

- Split evidence registry is empty.
- No formal DECLARED/EX_DATE event population.
- XOM still identity/history blocked.
- Banks/REITs need dedicated score models before any industry ranking.
- No price/yield calculations.

## 10. Test count

18 passed across P4/P4.1 dividend tests.
