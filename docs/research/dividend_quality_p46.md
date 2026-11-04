# Dividend Quality P4.6 — Sector Governance

Date: 2026-11-04
Branch: `research/dividend-quality-p46-sector-governance`
Stacked target: `research/dividend-quality-p41-hardening`
Status: **governance complete; no invented industry scores**

## 1. Industry classification

Rules are in `sector_governance.py`:

- normalized lowercase labels;
- BANK aliases: bank, regional bank, commercial bank;
- INSURANCE aliases and SIC 63xx;
- REIT requires REIT/real-estate-investment-trust or SIC 6798;
- generic Real Estate is FINANCIAL_OTHER, never automatically REIT;
- Financials is FINANCIAL_OTHER, not BANK;
- unknown/Unmapped stays UNKNOWN_INDUSTRY unless a non-financial SIC proves
  otherwise.

| Classification | Count |
|---|---:|
| NON_FINANCIAL | **21** |
| BANK | **2** |
| INSURANCE | **3** |
| REIT | **2** |
| FINANCIAL_OTHER | 0 |
| UNKNOWN_INDUSTRY | 0 |

Banks: JPM, BAC.  
Insurance: BRK.B, MET, UNH (UNH is SIC 6324 hospital/medical service plans,
classified insurance, not healthcare).  
REITs: PLD, O.  
UNP has SIC 4011 and is NON_FINANCIAL, not unknown.

## 2. Fixed non-financial profile

```text
profile_id = NON_FINANCIAL_DIVIDEND_V1
score_version = p46-1.0
components = payout, fcf_coverage, continuity
weights = 1/3, 1/3, 1/3
denominator = 3
signature = payout|fcf_coverage|continuity
```

Rules:

- all three components are required;
- a missing component sets score `null` and `NOT_READY`;
- weights are never renormalized;
- DPS growth is excluded because split basis is unverified;
- all numeric scores retain `score_profile_id`, `signature`, `weights`,
  `denominator`, available components and missing components.

## 3. Model readiness

| Group | Status | Numeric score |
|---|---|---:|
| Non-financial with all 3 components | `NON_FINANCIAL_MODEL_READY` / `SCORE_READY` | 10 |
| Non-financial missing component | `NON_FINANCIAL_MODEL_READY` / `NOT_READY` | null |
| Bank | `BANK_MODEL_NOT_READY` | null |
| Insurance | `INSURANCE_MODEL_NOT_READY` | null |
| REIT | `REIT_FFO_REQUIRED` / `REIT_MODEL_NOT_READY` | null |

### Banks

- no FCF coverage component;
- no digital score;
- CET1 status `DATA_BLOCKED`;
- `Common Equity / Total Assets` is not CET1 and is not calculated as a proxy;
- no bank ranking.

### Insurance

- no industrial FCF component;
- no digital score;
- Life/Health, P&C and Other are kept distinct where labels allow;
- RBC is not inferred from equity/assets and is not a universal ranking score;
- `INSURANCE_MODEL_NOT_READY`.

### REIT

- `reit_ffo_status = DATA_BLOCKED`;
- `reit_affo_status = DATA_BLOCKED`;
- `reit_payout_status = DATA_BLOCKED`;
- GAAP net income payout is not used as a REIT quality score;
- CFO/FCF is not renamed FFO;
- official Nareit-style FFO/AFFO evidence is required.

## 4. P4.1 → P4.6 score changes

P4.1 numeric scores: 20.  
P4.6 numeric scores: **10**.

The 10 unchanged READY companies:

```text
AAPL, MSFT, NVDA, HD, MCD, NKE, CAT, HON, UNP, CVX
```

They all use the same three-component signature and weights.

Changes:

- GOOGL, CRM: old score, now NOT_READY for missing continuity component;
- NEE, DUK: old score, now NOT_READY for missing required components;
- JPM, BAC: moved to BANK_MODEL_NOT_READY;
- MET, UNH: moved to INSURANCE_MODEL_NOT_READY;
- PLD, O: moved to REIT_FFO_REQUIRED;
- BRK.B: insurance model not ready (old score was already null);
- other non-payers / insufficient-history companies remain NOT_READY.

No formula was relaxed to preserve the old 20.

## 5. 28-company classification

| Ticker | Classification | P4.1 score | P4.6 score | P4.6 status |
|---|---|---:|---:|---|
| AAPL | NON_FINANCIAL | 100.0 | 100.0 | SCORE_READY |
| MSFT | NON_FINANCIAL | 100.0 | 100.0 | SCORE_READY |
| GOOGL | NON_FINANCIAL | 66.1 | — | NOT_READY |
| NVDA | NON_FINANCIAL | 100.0 | 100.0 | SCORE_READY |
| CRM | NON_FINANCIAL | 66.7 | — | NOT_READY |
| ADBE | NON_FINANCIAL | — | — | NOT_READY |
| AMZN | NON_FINANCIAL | — | — | NOT_READY |
| HD | NON_FINANCIAL | 79.9 | 79.9 | SCORE_READY |
| MCD | NON_FINANCIAL | 83.6 | 83.6 | SCORE_READY |
| NKE | NON_FINANCIAL | 63.5 | 63.5 | SCORE_READY |
| CAT | NON_FINANCIAL | 100.0 | 100.0 | SCORE_READY |
| HON | NON_FINANCIAL | 88.4 | 88.4 | SCORE_READY |
| UNP | NON_FINANCIAL | 95.0 | 95.0 | SCORE_READY |
| CVX | NON_FINANCIAL | 55.0 | 55.0 | SCORE_READY |
| NEE | NON_FINANCIAL | 95.2 | — | NOT_READY |
| DUK | NON_FINANCIAL | 37.4 | — | NOT_READY |
| JNJ | NON_FINANCIAL | — | — | NOT_READY |
| PFE | NON_FINANCIAL | — | — | NOT_READY |
| XOM | NON_FINANCIAL | — | — | NOT_READY |
| MRNA | NON_FINANCIAL | — | — | NOT_READY |
| RIVN | NON_FINANCIAL | — | — | NOT_READY |
| JPM | BANK | 100.0 | — | INDUSTRY_MODEL_NOT_READY |
| BAC | BANK | 100.0 | — | INDUSTRY_MODEL_NOT_READY |
| BRK.B | INSURANCE | — | — | INDUSTRY_MODEL_NOT_READY |
| MET | INSURANCE | 84.6 | — | INDUSTRY_MODEL_NOT_READY |
| UNH | INSURANCE | 97.0 | — | INDUSTRY_MODEL_NOT_READY |
| PLD | REIT | 66.7 | — | INDUSTRY_MODEL_NOT_READY |
| O | REIT | 45.2 | — | INDUSTRY_MODEL_NOT_READY |

## 6. Counts

| Status | Count |
|---|---:|
| SCORE_READY | **10** |
| NOT_READY | **11** |
| INDUSTRY_MODEL_NOT_READY | **7** |

## 7. DATA_BLOCKED reasons

- Banks: CET1/regulatory capital evidence absent; no equity/assets proxy.
- Insurance: no common capital/coverage model; no RBC proxy.
- REIT: FFO/AFFO official disclosure absent.
- Non-financial NOT_READY: one or more fixed three components missing.

No missing value is reported as zero.

## 8. Comparison gate

`comparable(a, b)` requires equality of:

```text
score_version
score_profile_id
score_component_signature
score_weights
score_denominator
```

Different profiles or component signatures cannot be ranked.  
No cross-industry unified ranking is produced.

## 9. Data and tests

Only local SEC CompanyFacts cache was used. No network request.

Tests: `tests/test_sector_governance_p46.py`:
- aliases and unknown labels;
- Real Estate vs REIT;
- bank/insurance no FCF;
- REIT FFO requirement;
- fixed weights and no renormalization;
- profile comparison gate;
- 28-company counts.

No production scan/trade code changed. No Yahoo/AKShare/Finnhub.
