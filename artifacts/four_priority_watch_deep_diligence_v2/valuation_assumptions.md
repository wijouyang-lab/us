# Valuation Assumptions and Formulas

Date: 2026-11-27. Prices 2026-11-25. All USD.

## Formula

```text
Equity Value = Normalized FCF × EV/FCF Multiple − Net Debt
Implied Price = Equity Value / Diluted Shares
```

`Net Debt` is total interest-bearing debt minus cash. All four have net cash, so
subtracting a negative adds cash.

## RELY

- Normalized FCF: $200M bear / $240M base / $300M bull (after treating SBC as a
  real economic cost; reported FCF $394.5M before SBC).
- Multiple: 10x / 14x / 18x.
- Net debt: -$669.1M.
- Diluted shares: 214.013M.
- Current: $21.68.

Base: `240×14 + 669.1 = $4,029.1M`, /214.013 = **$18.83**.

## FIVE

- Normalized FCF: $350M / $470M / $550M, removing the ~$169.5M pre-tax tariff
  refund effect.
- Multiple: 12x / 18x / 22x.
- Net debt: -$561.1M.
- Diluted shares: 55.054M.
- Current: $218.09.

Base: `470×18 + 561.1 = $9,021.1M`, /55.054 = **$163.86**.

## USLM

- Normalized FCF: $70M / $99M / $120M (mid-cycle; current TTM FCF $98.7M).
- Multiple: 12x / 18x / 22x.
- Net debt: -$439.2M.
- Diluted shares: 28.688M.
- Current: $104.68.

Base: `99×18 + 439.2 = $2,221.2M`, /28.688 = **$77.43**.

## FIZZ

- Normalized FCF: $130M / $162M / $185M.
- Multiple: 12x / 17x / 20x.
- Net debt: -$107.1M.
- Diluted shares: 93.615M.
- Current: $37.25.

Base: `162×17 + 107.1 = $2,861.1M`, /93.615 = **$30.56**.

## Caveats

- Multiples are research assumptions, not market-observed targets.
- SBC is treated as a cost in RELY; reported FCF excludes it.
- FIVE's normalized FCF removes a one-time tariff refund; this is an estimate, not
  a company-defined adjusted metric.
- USLM is cyclical; "normalized" FCF is not a mid-cycle audited number.
- No DCF, no probability weighting, no target price.
