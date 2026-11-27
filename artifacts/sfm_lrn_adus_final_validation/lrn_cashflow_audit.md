# LRN Cash-Flow Audit

Date: 2026-11-27

## Finding

The PR #635 LRN TTM FCF of **$504.5M** used capex of only **$0.285M**, which is the
`PaymentsToAcquirePropertyPlantAndEquipment` tag only. It omitted capitalized
software payments.

LRN's cash-flow statement separately reports:

| Item | FY2026 | Q1 FY2027 | Q1 FY2026 |
|---|---:|---:|---:|
| PP&E capex | $0.587M | $0.004M | $0.306M |
| Capitalized software (`PaymentsForSoftware`) | **$61.591M** | $17.911M | $13.713M |

TTM capex:

```text
PP&E:       0.587 + 0.004 - 0.306 = 0.285M
Software:  61.591 + 17.911 - 13.713 = 65.789M
Total:                                66.074M
```

TTM OCF = **$504.807M**.  
Corrected TTM FCF = **$438.733M**, not $504.5M.

## Cash-flow quality

- OCF TTM is real but seasonal. Q1 FY2027 OCF was **-$124.8M**; Q1 FY2026 was **-$195.8M**. The first fiscal quarter is cash-negative, and later quarters release working capital.
- Prepayments/deferred revenue/accounts payable timing affects OCF; the 10-Q does not disclose a clean single-quarter waterfall in XBRL. We do not treat Q1 OCF as annualized.
- Stock-based compensation: FY2026 `ShareBasedCompensation` = **$40.3M**, about 9% of OCF. It is non-cash but dilutive; FCF is not adjusted for SBC.
- Finance leases: principal payments are financing cash flows, not capex; no finance-lease capex is added. The company's capex definition is PP&E + capitalized software.

## Confidence

`FCF_CONFIDENCE_MEDIUM`: both PP&E and software are now included; no other capex
tag was found. It is not HIGH because the XBRL cash-flow taxonomy does not expose
a single "total capex" line and working-capital timing remains opaque.

## Impact on valuation

| Metric | Before | After |
|---|---:|---:|
| TTM FCF | $504.5M | **$438.7M** |
| EV/FCF | 6.40 | **7.36** |
| P/E | 10.05 | 10.05 (unchanged; earnings unaffected) |
| FCF yield | 15.0% | **13.1%** |
| Base scenario price | $110.09 | **$91.22** |

LRN remains WATCH; the low multiple is less extreme after the correction.
