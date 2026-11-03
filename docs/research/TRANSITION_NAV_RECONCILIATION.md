# PR438 Transition NAV Reconciliation

Date: 2026-11-03
PR438 frozen HEAD: `9b6effa6b76d860e583ba5b2edd9d79083997ffd`
PR455 frozen HEAD: `360dd8492a45eeaf08acbc1411fd9df5030e0f4d`

## 1. Result

Two rebuilds were compared to PR438 `w25_c10_all_legs` daily NAV:

| Rebuild | Max abs daily diff | Final NAV | Volatility |
|---|---:|---:|---:|
| PR438 original | — | 1.42978965 | 2.266148% |
| Adjusted-price / sleeve accounting | **0.00000165** | 1.42978968 | 2.266151% |
| Raw Open/Close + cash dividends | 0.03091968 | 1.46070933 | 2.816454% |

The adjusted-price sleeve rebuild reproduces PR438 almost exactly:

- max abs diff **0.00000165** (0.000165 percentage points of NAV)
- mean abs diff **0.00000033**
- final NAV diff **0.00000003**
- vol diff **0.000003 pp**

This confirms the original accounting: 75% BIL reserve, 25% strategy sleeve,
all-legs 10 bps, adjusted Open/Close, fractional units, dividends embedded in
adjusted prices.

## 2. Why the raw/cash rebuild differs

PR438 uses adjusted prices, so dividends are embedded in the price path. The
unified raw-price rebuild instead:

- executes at raw Open;
- marks at raw Close;
- credits ex-date dividends to cash;
- does not reinvest dividends.

That is a different total-return path. It produces final NAV 1.4607 (+2.15% vs
PR438) and realized vol **2.816%** vs **2.266%**, with max daily NAV difference
3.09%.

This is not a missing order or duplicate cost. It is a price-convention
difference: adjusted total-return prices vs raw prices plus cash dividends.

## 3. Consequence for risk matching

The existing 10.5337% passive weight targets PR438's **adjusted** 2.2661% vol.
It does **not** target the raw/cash Transition vol 2.816% under 3 bps and the
unified IBKR fee model.

Therefore:

- the exact 3 bps raw/cash risk-matching weight has **not** been finalized;
- the existing 10.5337% comparison remains a valid comparison against PR438's
  own adjusted NAV, but is not a raw/cash vol match;
- no new weight was chosen from CAGR or MaxDD.

## 4. Status

- PR438 adjusted accounting: **reproduced**.
- Raw/cash unified Transition NAV: **reconstructed but not equal** to PR438 by
  design; this is the source of the 2.06% vs 2.27% discrepancy previously seen
  in the non-sleeve rebuild.
- Exact 3 bps raw/cash risk match: **not completed**; this is the remaining
  blocker.
- Transition decision remains **NO-GO / no incremental strategy value**; no
  parameter, window, fee or risk-target rescue.

## 5. Files

```text
docs/research/transition_risk_match/transition_nav_reconciliation.csv
docs/research/transition_risk_match/reconciliation.json
tools/research/reconcile_transition.py
```
