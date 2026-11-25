# V2 Independent Ledger Audit

Date: 2026-11-25
PR: #626
Branch: `research/multi-factor-strategy-competition-v1`

## 1. Price execution audit

The engine was changed to separate:

- `raw_close`: actual daily close, used for buy/sell execution;
- `mark_close`: `ffill(limit=5)`, used only for valuation;
- no fill price is taken from `mark_close`.

A pending exit is retried on the next day with a real close. Open positions at
the end are recorded as `OPEN_AT_END`.

On the 2021-10-14..2026-10-13 5Y sample the results were **identical** to the
prior version, meaning there were no execution-date missing prices that changed
a trade. The engine still enforces the rule; this is a data property, not a
claim that no stale marks exist.

## 2. Independent reconstruction

A separate script (not the engine's NAV function) rebuilt daily cash and
market value from the trade ledger:

```text
ledger rows:        400
open rows:           10
final independent: 79,703.36528823897
final engine:      79,703.36528823894
max abs NAV diff:  2.91e-11
mean abs NAV diff: 6.67e-12
```

The engine NAV and independent NAV agree within floating-point tolerance
(< 1e-6 USD).

## 3. Ledger checks

- Buy fee and sell fee are based on actual notional.
- `NetPnL = GrossPnL - BuyFee - SellFee` for closed trades.
- `OPEN_AT_END` records a mark, no fake sell fee, and no fake close date.
- Cash changes match buy/sell notional and fees.

The 400-row ledger is for A 5Y only in this audit file; B/C ledgers remain in
the run cache and are not claimed as independently reconciled here.

## 4. Results unchanged

| Metric | Value |
|---|---:|
| A 5Y CAGR | 9.83% |
| A 5Y MaxDD | -14.15% |
| A 5Y Sharpe (rf=0) | 0.777 |
| A trades 5Y | 400 |

The stale-price fix did not change returns because execution dates had real
closes. This is not evidence that the strategy is validated.

## 5. Remaining limitations

- Only Close data; no OHLC intraday stop or gap fill model.
- Prices are unadjusted; no dividends/splits total-return adjustment.
- 502-name partial universe, no delisting returns.
- No strict walk-forward/OOS.
- Behavior tests still limited; current tests are mostly artifact checks plus
  this independent ledger check, not 12 synthetic execution tests.

Status remains **PROMISING_BUT_UNPROVEN**; no PAPER authorization.
