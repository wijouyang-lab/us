# PR #447 Browser Visual Audit

Date: 2026-11-03
Branch: `fix/dashboard-data-provenance-ux`
PR HEAD audited: `3d3c4aff590fc80314339240a361fd2e49d72d80` plus local visual-audit fixes.
Server: `http://127.0.0.1:8765/`
Browser: real Google Chrome via Playwright, headless.

## Environment

```text
Desktop: 1440 x 1000
Mobile:   390 x 844
```

The dashboard was served from the repository working tree; no GitHub Pages
deployment and no merge were performed.

## Screenshots

```text
docs/research/dashboard_visual_audit/desktop_full.png
docs/research/dashboard_visual_audit/mobile_full.png
docs/research/dashboard_visual_audit/desktop_top.png
docs/research/dashboard_visual_audit/mobile_top.png
docs/research/dashboard_visual_audit/desktop_macro.png
docs/research/dashboard_visual_audit/mobile_macro.png
docs/research/dashboard_visual_audit/desktop_portfolio.png
docs/research/dashboard_visual_audit/mobile_portfolio.png
docs/research/dashboard_visual_audit/desktop_data_health.png
docs/research/dashboard_visual_audit/mobile_data_health.png
docs/research/dashboard_visual_audit/desktop_details_open.png
docs/research/dashboard_visual_audit/mobile_details_open.png
docs/research/dashboard_visual_audit/desktop_market_summary.png
docs/research/dashboard_visual_audit/desktop_global_markets.png
```

## Console / network

| Check | Desktop | Mobile |
|---|---|---|
| Console errors | **0** | **0** |
| Page errors | **0** | **0** |
| Failed requests | **0** | **0** |
| Body horizontal overflow | 1440/1440 | 390/390 |

A favicon 404 was found during the first audit and fixed with an inline
`data:` favicon; subsequent runs are clean.

## PASS / FAIL checklist

| Check | Desktop | Mobile |
|---|---|---|
| Scan / Dashboard / quote times separated | PASS | PASS |
| Missing Scan does not use generated time | PASS | PASS |
| Missing Regime shows unavailable | PASS | PASS |
| Quote VIX has source + quote time | PASS | PASS |
| Top VIX duplicated | **PASS (one)** | **PASS (one)** |
| Macro unit `%` / `K` / `pts` | PASS | PASS |
| Macro unverified: no numeric surprise/impact | PASS | PASS |
| Macro period/release reason visible | PASS | PASS |
| Portfolio marked Paper / Simulated | PASS | PASS |
| Target labeled未成交 | PASS | PASS |
| Data Health MISSING/STALE/FALLBACK | PASS | PASS |
| Data Health own timestamps | PASS | PASS |
| Research details default collapsed | PASS | PASS |
| Research details expand/collapse | PASS | PASS |
| Empty Options explicit empty state | PASS | PASS |
| Header/nav wrapping | PASS | PASS |
| Text overlap | PASS | PASS |
| No page-level horizontal scroll | PASS | PASS |
| Portfolio table readable | PASS | **WARN** |

### WARN: mobile portfolio table

The transaction table remains an intentionally horizontally scrollable
`.pf-wrap` inside the card. Page-level width is 390px with no body overflow, and
the first columns remain readable, but full columns (Realized PnL/Holding/Reason)
require horizontal scrolling within the table. This is disclosed as a WARN, not
a page overflow failure.

## Issues found and fixed during audit

1. **Data Health was empty** — `renderDataHealth()` ran immediately after the
   async `boot()` before `DATA` existed. It now runs at the end of boot after
   all data is loaded.
2. **Mobile Fear & Greed gauge shrank** — flex shrink squeezed the ring until
   the score was unreadable. `.mi-fg > svg` now has `flex:0 0 auto`, and
   subindicator chips wrap below the gauge.
3. **Macro cards showed "单位未核验"** for UMich/ISM — indicator cards now fall
   back to the matching forecast unit when their own unit is absent.
4. **Unverified AI macro commentary leaked direction/percentages** — hidden
   unless the matching forecast is verified.
5. **Favicon 404** — added `<link rel="icon" href="data:,">`.
6. **Duplicate VIX label** — removed the separate `Regime VIX —` line; quote VIX
   is the single top VIX and retains source/time. Global Markets excludes VIX.

## Data verification

Current page DOM:

```text
Scan: 扫描时间未知/本次未提供
Regime: 市场状态不可用（来源缺失）
Quote VIX: 21.15 · yahoo_http · 2026-11-03T06:09:46Z
Macro: 9/9 unverified; 差值 —; 影响文案已隐藏
Data Health Macro: FALLBACK (9 unverified)
News: MISSING (no data)
AI: MISSING (pending)
Ledger: FRESH (2026-11-02, simulated)
```

No unverified macro numeric surprise or impact is displayed. No strategy,
factor, risk, ledger or order logic was changed.
