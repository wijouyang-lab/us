# Defensive Treasury ETF Diagnostic

Date: 2026-11-02  
Status: **RETROSPECTIVE / DESCRIPTIVE ONLY — NOT A STRATEGY TEST**

Source: Yahoo Finance history via yfinance 1.7.0, downloaded by research workflow [41403087606](https://github.com/wijouyang-lab/us/actions/runs/41403087606). No API token was used. All return statistics below use provider `Adj Close` as a total-return proxy; this is not a validated accounting feed.

## 1. Long-history comparison

Common start date: 2007-05-30 (BIL availability); end: 2026-10-30. Split/dividend-adjusted close history.

| ETF | Total return | CAGR | Annualized vol | Max drawdown | Sessions |
|---|---:|---:|---:|---:|---:|
| BIL | +31.07% | 1.40% | 0.49% | -0.78% | 4,888 |
| SHV | +34.83% | 1.55% | 0.35% | -0.45% | 4,888 |
| TLT | +73.33% | 2.87% | 15.13% | -48.35% | 4,888 |
| GLD | +449.72% | 9.17% | 18.23% | -45.56% | 4,888 |
| IWM | +332.46% | 7.83% | 24.70% | -58.64% | 4,888 |
| QQQ | +1,608.89% | 15.74% | 22.33% | -53.40% | 4,888 |

SGOV has a shorter history and must not be substituted into the common 2007 comparison:

| ETF | Available period | Total return | CAGR | Annualized vol | Max drawdown |
|---|---|---:|---:|---:|---:|
| SGOV | 2020-06-01 to 2026-10-30 | +20.89% | 3.00% | 0.23% | -0.03% |

These figures illustrate the role of a short-Treasury ETF as a cash-parking sleeve, not an alpha engine. A low realized drawdown over one provider history does not eliminate interest-rate, liquidity, fund-structure, or execution risks.

## 2. Descriptive next-session returns by prior-close SPY regime

Regime is assigned using SPY data available at the previous close: RISK_ON if SPY Close > MA200 and MA200 20-session slope > 0; RISK_OFF if both are below/negative; otherwise TRANSITION. Each row below summarizes the next close-to-close adjusted return after that prior-close label.

| ETF | Regime | Observations | Annualized arithmetic mean | Annualized vol | Positive sessions |
|---|---|---:|---:|---:|---:|
| BIL | RISK_ON | 3,520 | 1.45% | 0.31% | 43.4% |
| BIL | RISK_OFF | 819 | 1.23% | 0.95% | 43.6% |
| BIL | TRANSITION | 548 | 1.32% | 0.38% | 41.8% |
| SHV | RISK_ON | 3,615 | 1.62% | 0.27% | 49.8% |
| SHV | RISK_OFF | 819 | 1.44% | 0.57% | 51.4% |
| SHV | TRANSITION | 548 | 1.78% | 0.38% | 50.9% |
| SGOV | RISK_ON | 1,264 | 3.01% | 0.23% | 66.5% |
| SGOV | RISK_OFF | 195 | 2.62% | 0.24% | 59.5% |
| SGOV | TRANSITION | 154 | 3.06% | 0.24% | 67.5% |
| TLT | RISK_ON | 4,425 | 3.59% | 12.46% | 51.9% |
| TLT | RISK_OFF | 1,006 | 5.18% | 17.85% | 52.0% |
| TLT | TRANSITION | 672 | 9.24% | 18.57% | 53.3% |

These are descriptive conditional averages, not statistical evidence of a tradable regime premium. The regime buckets are non-contiguous, annualized arithmetic means are not portfolio CAGRs, and no transaction costs or portfolio weights are applied. SGOV's RISK_OFF sample is short (195 sessions).

## 3. Research implications

1. **BIL / SHV** are plausible defensive cash-parking candidates for a long-only system: their historical total-return volatility and drawdowns are far below TLT's. Their expected return is low and depends on the short-rate environment.
2. **SGOV** is a newer 0–3 month Treasury candidate with only about 6.4 years of history in this dataset. Its higher CAGR largely reflects the post-2020 rate environment; do not use it to claim a decade-long record.
3. **TLT is not cash.** It may act as a duration hedge in selected disinflationary crises, but its large historical drawdown makes it unsuitable as the default defensive cash sleeve under a 15% portfolio drawdown objective.
4. **GLD is not cash either.** It may be tested as a separate diversifier/strategy sleeve, but its own volatility and drawdown are equity-like in magnitude.
5. This diagnostic does not prove a strategy. A future portfolio test should compare idle cash, BIL, and SHV as the defensive sleeve under the same entry/exit rules, execution price, and costs. Do not optimize the allocation on the reused full history.

## 4. Limitations

- Yahoo Finance is a third-party provider. `Adj Close` is a provider-adjusted total-return proxy, not independently audited fund NAV or total-return index data.
- Only currently existing funds are included; closed or liquidated ETFs are not reconstructed.
- No point-in-time ETF universe, spreads, market impact, tracking error, tax, or broker execution is modeled.
- This is a retrospective diagnostic; it does not change production signals, risk limits, portfolio accounting, or order entry.
