# Three Candidates — Cash Flow and Valuation Audit

Date: 2026-11-27. Prices 2026-11-25, unadjusted. **Research only; no PAPER/IBKR/orders.**

## Decisions

| Ticker | Decision | Price | Reported P/E | Reported EV/FCF | Normalized FCF | SBC-Adj EV/FCF | Base | Base vs price |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| IMMR | **INSUFFICIENT_DATA** | $6.55 | 9.4 | 1.86 | N/A | N/A | NOT_ESTIMABLE | — |
| PHR | **WATCH** | $12.09 | 71.8 | 8.38 | $13.2M | ~51x | $4.37 | -63.8% |
| OPRX | **WATCH** | $7.31 | 27.6 | 6.50 | $12.9M | ~10x | $8.66 | +18.5% |

**PAPER_CANDIDATE: 0.**

## IMMR — EV/FCF 1.86 is invalid

- FY2026 consolidated revenue $1.730B: **parent/licensing $15.924M + BNED $1.714770B**.
- BNED is a consolidated VIE; **NCI ~67.4%**.
- Consolidated OCF $59.1M, capex $16.2M, but parent-only FCF is not disclosed.
- The TTM FCF $61.1M includes BNED's working capital/cash flows; it cannot be attributed to IMMR common shareholders without a segment cash-flow allocation.
- EV/FCF 1.86 and Base $25.17 are **revoked**. There is no defensible parent-level FCF.
- Decision: **INSUFFICIENT_DATA**, not a buy/priority.

## PHR — FCF is mostly SBC

- FY2026 revenue $495.0M, net income $10.4M, OCF $78.8M, capex $24.4M, FCF $54.4M.
- SBC **$67.5M**, or **84% of reported TTM FCF $80.7M**.
- SBC-adjusted FCF ≈ **$13.2M**. EV ≈ $676.9M → **~51x SBC-adjusted EV/FCF**, not 8.4x.
- Capitalized software was $13.3M; already in capex, not added again.
- Decision: **WATCH**; the apparent cheap FCF is an accounting/SBC artifact and does not provide safety.

## OPRX — customer loss changed the thesis

- TTM revenue $94.2M, net income $5.0M, OCF **$19.889M**, FCF $19.9M.
- SBC $7.0M → normalized FCF **$12.9M**; EV ~$129.2M → ~10x, not 6.5x.
- Top five customers ~47% of revenue; one customer ~10% of FY2025 revenue generated **no current-period revenue**. It has been re-contracted, but the timing/amount is not fully disclosed.
- Microcap ($138M), customer concentration, and revenue quality require a discount.
- Decision: **WATCH**; no 25% safety margin.

## Direct answers

1. **IMMR EV/FCF 1.86 is wrong/uncomparable.** Consolidated BNED + NCI; parent-only FCF is unavailable.
2. **PHR after SBC is not attractive.** SBC-adjusted EV/FCF ~51x; FCF is largely SBC.
3. **OPRX customer loss has damaged the original thesis.** One 10% customer contributed zero current-period revenue; top-five ~47%.
4. **No company has ≥25% verified safety margin.** OPRX base is +22% only on a microcap/12x normalized FCF assumption; PHR is below price; IMMR N/A.
5. **Most worth watching: PHR** on business quality, but not at this price; OPRX is cheaper but customer-riskier.
6. **0 PAPER_CANDIDATE.**

## Data limitations

- IMMR segment cash flows are not disclosed; no reliable parent FCF.
- PHR 8-quarter SBC/capitalized-software series was not fully extracted; annual SBC used.
- OPRX customer re-contracting amount/timing is not fully disclosed.
- Prices unadjusted; no PIT; no forward estimates.
- No full 10-K line-by-line review of all notes.

## Files

`artifacts/three_candidate_cashflow_valuation_audit_v1/` with entity, quarterly, FCF reconciliation, SBC, customer concentration, normalized FCF, scenarios, comparison, risk, catalysts, sources, decisions, validation.
