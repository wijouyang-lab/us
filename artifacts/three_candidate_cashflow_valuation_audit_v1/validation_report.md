# Validation Report — V2 Period/SBC/Valuation Rebuild

Date: 2026-11-27

## Reconciliation

PHR:

- Revenue: 480.591 + 260.393 − 233.191 = **507.793**
- OCF: 78.814 + 42.250 − 29.685 = **91.379**
- Capex: software 13.225 + PPE 10.632 = **23.857**
- FCF: 91.379 − 23.857 = **67.522**
- SBC total: 68.738 + 26.009 − 34.107 = **60.640**
- SBC expense: 67.452 + 25.429 − 33.455 = **59.426**
- SBC capitalized: 1.286 + 0.580 − 0.652 = **1.214**
- FCF after expense SBC: **8.096**
- FCF after total SBC: **6.882**

OPRX:

- Revenue: 109.429 + 61.963 − 77.190 = **94.202**
- OCF: 18.715 + 12.880 − 11.627 = **19.968**
- Capex: 0.1 + 0.068 − 0.047 = **0.121**
- FCF: **19.847**
- SBC: 6.962 + 5.820 − 5.002 = **7.780**
- Normal SBC (excluding 0.588 accelerated): **7.192**
- FCF after SBC: **12.067**

## Automated tests

```text
pytest -q tests/test_three_audit.py
18 passed
```

Each test checks a formula, period, unit, ownership boundary, SBC distinction, NCI boundary, price date, share count, source traceability, or PAPER gate — not just file existence.

## Limitations

- IMMR parent-only FCF remains undisclosed; no valid Base.
- PHR cash-settled SBC is UNKNOWN.
- OPRX re-contract amount/timing not disclosed; NRR 121%→83%.
- No full 8-quarter PHR series; only FY/H1/prior H1 from the 10-K/10-Qs.
- No PIT; unadjusted prices.
- No PAPER/IBKR/orders.
