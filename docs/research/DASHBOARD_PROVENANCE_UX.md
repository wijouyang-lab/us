# Dashboard Data Provenance / UX Fix

Date: 2026-11-03
Branch: `fix/dashboard-data-provenance-ux`
Status: implementation + targeted tests; Draft PR.

## P0 — time and market-state labels

Before:

- `pending_scan_date=null`, but `renderGmBar()` fell back to
  `DATA.generated_at.slice(0,10)` and still labeled it “Scan 日期 · 真实数据”.
- `regime.market` and `regime.vix` were null, but `regimeTxt()` replaced the
  missing regime with live/frozen quote counts.
- A separate `^VIX` quote existed in `market.assets` and could be mistaken for
  the Regime VIX.

After:

- Scan date is never taken from `generated_at`.
- Missing scan shows `扫描时间未知/本次未提供`.
- Dashboard build time and market quote time are shown separately.
- Missing regime shows `市场状态不可用（来源缺失）`; no Risk-on/Risk-off is inferred.
- Regime VIX and quote VIX are separate lines. The quote line includes source,
  quote time, and the explicit text `行情报价，非 Regime VIX`.
- Session tag shows `扫描时间未知` when absent.

## P1 — macro units and provenance

Before:

- `umich` and `ism` were stored with unit `%`; forecast deltas always used `pp`.
- `macro_forecast.as_of` and `released_at` were null, but values still looked
  official.
- No per-item source status; fallback items were not marked.
- Speech module was titled “重要人物讲话” even though it contains media reports.

After:

- Semantic unit mapping: `%` → percent/pp, `K` → count K, `index point` → points,
  `千桶` → thousand barrels; unknown units render `单位未核验`.
- Unit-specific comparison thresholds: 0.05 for percent, 0.5 for points, 1 for
  counts.
- Forecast rows with missing `released_at` or mismatched period show
  `期间/发布时间未核验` and do not emit a directional surprise.
- Each item now carries `source`, `source_status`, `period`, `released_at`,
  `fetched_at`; unverified items are `unverified`; fallback is explicit.
- Macro section retitled “政策人物与宏观相关报道”; each card is marked
  `媒体报道` unless an official flag is present.

Current snapshot after repair:

```text
umich   unit=index point  source=unverified
ism     unit=index point  source=unverified
adp     unit=K
claims  unit=K
nonfarm unit=K
released_at=null  -> direction hidden
```

## P1 — simulated account disclosure

Before:

- Header said `REAL · dashboard_data.json`; footer said “本页不含任何模拟数据”,
  while the page contained the $50,000 portfolio.
- Target rows with `actual_shares=0` and `fill_status=pending` were under
  “AI 目标持仓”.
- `trade_stats.avg_holding_days` was null even though closed BUY/SELL pairs had
  holding data.

After:

- Header: `真实行情 + 模拟组合`.
- Footer: `真实行情数据 · $50,000 组合为 Paper / Simulated（模拟）`.
- Portfolio heading has `SIMULATED`; summary labels are `Simulated NAV`,
  `Simulated Total PnL`, `Simulated Return %`.
- Disclosure: simulated PnL does not include commission, slippage, spread, or
  dividends.
- Target section is `待执行目标（未成交）`.
- Transaction section is `Recent Paper Ledger Entries`; time is labeled ledger
  record time, price is labeled reference/close reference.
- Stop section renamed `止损线触发离场`.
- `avg_holding_days` now pairs closed SELL rows with prior BUY rows by Unit_ID.
  Current snapshot: **5.3 days** (was null).

## P2 — Data Health

Added `#dataHealthSec` / `#dataHealth` with independent cards:

```text
扫描 Scan
市场行情
技术日线
宏观数据
新闻
AI 文本
模拟账本
```

Each card shows its own timestamp, source, status
(`FRESH / STALE / FALLBACK / MISSING`), threshold, and note. `network_status=ok`
does not override a missing/fallback item.

## Before/after evidence

Current baseline (`5c22b32`):

```text
meta.pending_scan_date = null
meta.notes = ["Market_Regime ... regime.market 输出 null"]
regime.market / regime.vix = null
macro_forecast.as_of = null
macro_forecast.items[].released_at = null
portfolio.trade_stats.avg_holding_days = null
```

Repaired snapshot:

```text
Scan label                = 扫描时间未知/本次未提供
Regime                   = 市场状态不可用（来源缺失）
Quote VIX                = separate 行情 VIX + source + quote time
UMich / ISM              = index point, not %
Macro direction           = 期间/发布时间未核验
Portfolio avg holding     = 5.3
Portfolio labels          = SIMULATED / Paper
```

## Commands and results

```text
python dashboard_export.py
  exit 0; JSON written; trade_stats.avg_holding_days=5.3

python -m pytest tests/test_dashboard_provenance_ux.py
python -m pytest tests/test_trade_stats.py tests/test_trade_stats_frontend.py
python -m pytest tests/test_macro_panel_frontend.py
python -m pytest tests/test_dashboard_snapshot_match.py tests/test_macro_forecast.py
  dashboard-focused suite: 38 passed

python tests/test_dashboard_runtime.py        19/19
python tests/test_dashboard_data_stability.py 34/34
```

A later export rerun hit local yfinance cache/database errors for market symbols;
the committed snapshot is the successful export plus only the intended metadata
and unit corrections. No strategy, weight, stop, ledger-rule, or order-path code
was changed.

## Additional verification fail-closed work

- Export layer now sets `surprise=null` unless the item is verified:
  source status `verified`, `released_at` present, a parseable statistical
  period, matching actual/forecast periods, and matching indicator definitions.
- Each item gets `verification_status` and `verification_reason`.
- The statistical period may legitimately differ from the publication month
  (e.g. September CPI released in October); verification compares the
  actual/forecast **statistical periods**, not release month.
- `最新`/unparseable periods fail closed.
- Frontend only displays a surprise/direction when
  `verification_status=verified`; otherwise it shows the unverified reason and
  no numeric difference.
- Current snapshot: all 9 macro items are unverified, `surprise=null`.

## P2 completion

- Top market summary reduced to 3 keys: S&P 500, VIX, US10Y.
- Those keys are excluded from the lower Global Markets duplicates; the rest of
  the full list remains.
- Decision Inputs and Quant phases are inside collapsed `<details>` research
  sections; Quant summary remains visible.
- Empty Options list already renders an explicit empty state; no fake options.
- Data Health: macro aggregates all items; any FALLBACK/UNVERIFIED item marks the
  whole macro card FALLBACK. News/AI/ledger with missing timestamps are MISSING;
  old timestamps are STALE.

## Not completed / follow-ups

- No browser screenshot was captured; verification is DOM/test-based.
- A later export rerun hit local yfinance cache errors; the committed snapshot is
  the successful export plus intended metadata/unit/verification corrections.
- PR #445 BLS macro data block remains independent and unresolved.
