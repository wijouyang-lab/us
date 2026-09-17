# US Scan / Review structural strategy update — 2026-09-17

## What was accepted

1. Technical signals are now explicit and are used as an entry-quality gate.
2. AI score is no longer trusted as the primary score. Final score = 70% deterministic Quant Score + 30% AI score.
3. Quant Score uses four transparent blocks: Fundamental 35, Event 20, Technical 25, Risk/Liquidity 20.
4. Market regime uses SPY 20D trend, SPY 5D return, VIX, and 20D sector relative strength vs SPY.
5. Liquidity and ATR risk are hard filters where data is available.
6. Stock exits remain dynamic rather than fixed-duration; the first 3 calendar days use a -5% trial stop, then ATR/MA/MACD/KDJ dynamic protection. Profit-lock levels lift the stop instead of forcing an immediate exit.
7. Evolution now gets positive/negative examples and a time-ordered out-of-sample threshold test. Only whitelisted score/gate parameters may be auto-applied when OOS EV is not worse than baseline.
8. Only a small number of recent prompt rules are injected to limit rule accumulation.
9. Scan/Review workflows persist all generated files and no longer rely on a partial git add list.
10. Observation remains a valid Scan recommendation and is included in the recommendation KPI tracking; it is not treated as a real holding.

## What was intentionally changed from the proposal

- Volume is not an unconditional mandatory signal. A rigid volume requirement can eliminate valid setups. The system uses a 2-of-5 technical confirmation rule in normal conditions and raises it to 3-of-5 in stressed/panic regimes; volume is one of the confirmations.
- AI score <65 is not a standalone hard veto. The deterministic Quant Score and market/technical gates are the primary controls, with AI acting as a secondary ranking signal. This avoids turning another noisy black-box score into a hard gate.
- The default stock stop is not widened to -15%. The first-3-day trial stop remains -5%; thereafter the primary protection is 2xATR bounded to 3%-12%. Profit-lock rules tighten protection after meaningful gains.
- Automatic reverse/contrarian trading is not enabled. The historical sample is too heterogeneous to justify an automatic reversal system without a separate, time-ordered test.
