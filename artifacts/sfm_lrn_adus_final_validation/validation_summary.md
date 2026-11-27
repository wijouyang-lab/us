# SFM / LRN / ADUS — Final Validation Summary

Date: 2026-11-27
Base PR #635 HEAD `b5a832ac36113d207c197216a354fbf08b8d4046`.

## Verdict

**NO_ACTION remains.** All three are **WATCH**; no PRIORITY_WATCH.

- SFM: negative comps and lower FCF; base $56.52, bear $29.29.
- LRN: FCF was overstated because **$61.6M software capex** was omitted; corrected FCF $438.7M, base $91.22.
- ADUS: organic +6.9%, but 20x P/E and Medicaid risk; base $133.25.

## Formula audit

`Equity Value = FCF × EV/FCF Multiple − Net Debt`  
`Implied Price = Equity Value / Diluted Shares`

Net Debt = interest-bearing debt − cash at latest balance sheet date. Negative Net Debt = net cash; subtracting a negative adds cash. This is mathematically the same as the original "FCF × multiple + net cash" but the definition is now explicit.

## Corrected scenarios

| Ticker | Scenario | FCF | Multiple | Net Debt | Diluted Shares | Implied Price | Latest | Return |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| SFM | Bear | $220M | 12x | -$104M | 93.666M | $29.29 | $53.32 | -45.1% |
| SFM | Base | $346M | 15x | -$104M | 93.666M | $56.52 | $53.32 | +5.9% |
| SFM | Bull | $420M | 18x | -$104M | 93.666M | $81.82 | $53.32 | +53.4% |
| LRN | Bear | $350M | 7x | -$129M | 44.828M | $57.54 | $79.90 | -28.0% |
| LRN | Base | $440M | 9x | -$129M | 44.828M | $91.22 | $79.90 | +14.2% |
| LRN | Bull | $500M | 11x | -$129M | 44.828M | $125.58 | $79.90 | +57.2% |
| ADUS | Bear | $110M | 13x | -$75M | 18.574M | $81.03 | $122.53 | -33.9% |
| ADUS | Base | $150M | 16x | -$75M | 18.574M | $133.25 | $122.53 | +8.8% |
| ADUS | Bull | $175M | 19x | -$75M | 18.574M | $183.05 | $122.53 | +49.4% |

The original PR #635 used **basic shares** (SFM 92.233M, LRN 42.049M, ADUS 18.633M). The validation uses **diluted weighted-average shares** (SFM 93.666M, LRN 44.828M, ADUS 18.574M). This accounts for small differences; LRN also changed because FCF was corrected.

## Latest price

No 2026-11-27 official close was available at retrieval (US market not closed; Nov 26 holiday). Latest verified close is **2026-11-25**:

| Ticker | Price | Date | Provider |
|---|---:|---|---|
| SFM | $53.32 | 2026-11-25 | yfinance unadjusted close |
| LRN | $79.90 | 2026-11-25 | yfinance unadjusted close |
| ADUS | $122.53 | 2026-11-25 | yfinance unadjusted close |

## Data confidence

| Ticker | FCF confidence | Valuation confidence | Safety margin | Decision |
|---|---|---|---|---|
| SFM | MEDIUM | MEDIUM | NO | WATCH |
| LRN | MEDIUM (after software capex correction) | MEDIUM | NO | WATCH |
| ADUS | MEDIUM | MEDIUM | NO | WATCH |

No company reaches PRIORITY_WATCH.
