# Three-Route Rules and Data Verdict

## Data audit

- **Daily source:** 987 U.S. symbols, 2007-01-03 to 2024-12-31, 3,479,190 rows; adjusted close and raw OHLCV.
- **Monthly panel:** 166,320 rows; 987 symbols; 710 names at 2024-12 month-end.
- **Delisted stocks:** NOT VERIFIED. The symbol set is static; this is a likely **survivorship bias**.
- **Ticker/name changes:** NOT VERIFIED.
- **Splits/dividends:** `adjusted_close` available; raw close used only for the $5 price filter.
- **PIT fundamentals:** **NO.** Quality and industry are current static classifications, so quality/industry variants are **exploratory and look-ahead biased**.
- **Benchmarks:** SPY/QQQ monthly 2007-2024.
- **Budget:** no paid data purchased; all from existing repository/cache.

### Data grades

- **A — rigorous historical backtest:** price-only monthly momentum/trend with adjusted prices; still subject to survivorship because the universe is static.
- **B — current selection / limited history:** quality and industry filters, current classifications.
- **C — not usable for conclusions:** PIT financial-improvement strategy (Route C); no historical filing-date fundamentals.

## Route A — Momentum + quality

Signal at month-end `t`:

- 12-1 return: `adj[t-1]/adj[t-12] - 1`
- 52-week high position: `adj[t]/max(adj[t-12:t])`
- 6-month return
- liquidity: raw close × volume ≥ $10M
- price ≥ $5
- 20 names; max 5% each; max 4 per industry
- variants: MOM, MOM+QUAL, MOM+IND, MOM+QUAL+IND
- monthly rebalance; next-month close-to-close return

## Route B — Industry first

Rank industries by median 6-month return; keep top 3; within those rank by 52-week high position and 6-month return; 20 names; same caps.

## Route C — Fundamental improvement + price confirmation

**NOT HISTORICALLY EVALUABLE.** No PIT filing-date fundamentals are in the repo. Current `quality_pct` cannot be backfilled. No results are reported; no synthetic estimates were created.

## Unified backtest

- $50,000; monthly; next-month close; 5/10/20 bps one-way costs.
- Train 2008-2016; validation 2017-2019; OOS 2020-2024.
- Max 5% per name, max 4 per industry; 20 names.
- Benchmarks: SPY, QQQ, SPY 10-month trend, simple 12-1 momentum (A_MOM).
- 15% max drawdown target.

## Bias warning

All stock strategies use a static 987-symbol universe. This is not a historical complete universe and cannot support a claim of validated alpha. Results are exploratory.
