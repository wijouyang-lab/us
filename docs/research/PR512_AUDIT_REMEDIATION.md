# PR #512 Audit Remediation

Date: 2026-11-10  
Branch: `fix/pr512-audit-remediation`  
Base for review: `research/invest-terminal-v1` at `9b07f588dd5af05017d2d4cba36ae87a23d9460a`  
No merge or deployment.

---

## Final status

```text
WORKFLOW_SECURITY: PASS
PRODUCTION_ISOLATION: FAIL (residual public terminal.html; Dashboard coupling removed)
P9_METRIC_CONSISTENCY: PASS
P9_DATA_REPRODUCIBILITY: BLOCKED
DATA_PROVENANCE: PARTIAL
PAPER_ENGINE_SECURITY: PASS
PR512_READY_FOR_REVIEW: NO
```

The P0 workflow and Dashboard coupling issues are fixed. P9.1 has a generation
program in the PR, but its raw inputs are not in the branch, so full regeneration
remains blocked. A direct public `terminal.html` URL also remains a residual
Pages exposure.

---

## 1. Modified files

```text
.github/workflows/p7-shadow-daily.yml
.github/workflows/dashboard-data.yml
.gitignore
index.html
dashboard/data/invest_terminal_data.json   (untracked/removed from Git)
data/research/p9_1_support_resistance/p9_1_status.json
docs/research/p9_1_support_resistance.md
tests/test_invest_terminal_snapshot_sync.py
tests/test_pr512_remediation.py             (new)
tools/invest_terminal/build_snapshot.py
tools/investment_research/p9_1/strategy.py
tools/investment_research/p9_1/portfolio.py
data/research/pr512_provenance_manifest.csv (new)
```

---

## 2. Workflow security: before/after

### Before

`.github/workflows/p7-shadow-daily.yml`:

- `workflow_dispatch.inputs.branch`;
- `contents: write`;
- checkout `ref: ${{ github.event.inputs.branch }}`;
- `git push origin HEAD:${{ github.event.inputs.branch }}`.

### After

- no branch input;
- `permissions: contents: read`;
- checkout uses the selected ref only;
- no `git push`;
- results uploaded as artifact;
- no path to `main` writes.

Security test:

```text
tests/test_pr512_remediation.py
```

asserts no `contents: write`, no `git push`, no `inputs.branch`, and artifact use.

---

## 3. Production Dashboard isolation: before/after

### Removed

- `dashboard-data.yml` no longer runs `tools.invest_terminal.build_snapshot`.
- `dashboard-data.yml` no longer stages/commits `invest_terminal_data.json`.
- `index.html` no longer contains the Invest Terminal production entry.
- `dashboard/data/invest_terminal_data.json` is no longer tracked and is now
  ignored.

### Preserved

- `terminal.html`, `terminal/`, `tools/invest_terminal/`, `tools/paper_trading/`.
- Local terminal server and PAPER engine.
- `research-invest-terminal.yml` remains a separate read-only integration
  workflow and artifact producer.

### Residual FAIL

`terminal.html` remains in the repository root. If GitHub Pages publishes the
repository root, the page can still be reached by direct URL even without the
Dashboard link. The snapshot is no longer committed, so it will show missing
local paper state, but the page itself is public.

To fully isolate it, move Terminal static assets to a non-Pages deployment path
or publish only an explicitly approved read-only research page. This is not
changed here because it would alter the local Terminal serving path and needs
an explicit publication decision.

---

## 4. P9.1 correction to the prior audit

The previous audit incorrectly said “no P9.1 generation code.” That was wrong.
The branch contains:

```text
tools/investment_research/p9_1/strategy.py
tools/investment_research/p9_1/portfolio.py
```

Correction:

- generation code exists;
- `p9_1_signals.csv.gz` is tracked;
- `p9_1_signals.csv` (uncompressed) is not tracked;
- `portfolio.py` previously required the uncompressed CSV; now it falls back to
  the gzip file;
- `strategy.py` now writes both CSV and CSV.GZ.

### Missing inputs

The code requires:

```text
data/research/pit_data/finsaber_prices_raw.csv
data/research/historical_universe/sp500_daily.csv
```

Neither is present in the branch. Therefore `P9_DATA_REPRODUCIBILITY` remains
**BLOCKED**, not FAIL: the code is present, inputs are missing.

---

## 5. Event-count reconciliation

Actual current definitions:

| Count | Meaning |
|---:|---|
| **204,180** | raw signal rows in `p9_1_signals.csv.gz` (8 experiments) |
| **204,030** | valid event observations after horizon labels, sum of max per experiment |
| **611,790** | experiment-horizon observations: same event counted at 5/10/20 days |

The prior PR/docs number `204,180` was the raw signal count; the table values
were stale. The 611,790 status value was a horizon-sum, not unique events.

Updated `p9_1_status.json` now records:

```text
events: 204180
valid_event_observations: 204030
event_horizon_observations: 611790
event_rows: 24
```

`strategy.py` now derives these fields instead of treating them as one number.

---

## 6. Sharpe reconciliation

Method now documented:

```text
mean(daily NAV returns) / std(daily NAV returns, ddof=1) * sqrt(252)
no separate risk-free subtraction; BIL is the 80% cash leg
```

Recomputed from NAV:

| Strategy | Sharpe |
|---|---:|
| D_C_MACD | 0.2747 |
| E_C_KDJ | 0.6232 |
| F_C_BOTH | 0.5485 |
| H_G_BOTH | 0.5485 |

`docs/research/p9_1_support_resistance.md` previously had 0.23/0.47/0.33; it now
uses the reproducible values.

CAGR and MaxDD remain:

```text
D: 0.826%, -14.60%
E: 1.80%, -8.17%
F/H: 1.245%, -10.10%
```

All 8 strategies remain `NO-GO`; benchmark `20QQQ_80BIL` remains
CAGR 2.085%, Sharpe 1.351, MaxDD -3.79%.

---

## 7. Duplicate hypotheses

- `G_LEVEL_ALL_PATTERNS` duplicates `C_SUPPORT_PATTERN`.
- `H_G_BOTH` duplicates `F_C_BOTH`.

They are retained as historical records but are not independent strategies.
`p9_1_status.json` records `duplicate_experiments`.

---

## 8. Coverage

```text
member-days: 1,095,490
valid:         981,362 = 89.58% < 95%
unknown:       109,132
corrupt:           117
zero/stale:      4,845
unresolved:         34
```

Ticker coverage is about 91.55%, below 98%.

P9.1 remains data-blocked for a market-wide backtest. The NO-GO decision is
unchanged.

---

## 9. Data provenance manifest

Added:

```text
data/research/pr512_provenance_manifest.csv
```

198 data files covered. Fields:

```text
relative_path, bytes, sha256, type, source, acquired_at, as_of,
generated_by, parameters, license, rebuildable
```

Many source/acquired/license fields are `UNKNOWN` because the branch does not
contain that evidence. This is intentionally not invented. Status is therefore
`DATA_PROVENANCE: PARTIAL`, not PASS.

---

## 10. Tests

```text
pytest tests/test_invest_terminal.py
       tests/test_invest_terminal_server.py
       tests/test_invest_terminal_snapshot_sync.py
       tests/test_paper_trading_platform.py
       tests/test_p9_1_support_resistance.py
       tests/test_pr512_remediation.py
```

Result: **53 passed in 6.70s**.

`git diff --check`: clean. `git status`: only intended changes plus the new
manifest/test; no production scanner/ledger changes.

Full CI remains to be run on the pushed branch.

---

## 11. Remaining blockers

1. P9.1 raw price and historical membership inputs are not in the branch.
2. P9.1 cannot be regenerated from the PR alone; `P9_DATA_REPRODUCIBILITY` is
   BLOCKED.
3. Direct `terminal.html` can still be publicly reachable under GitHub Pages.
4. Provenance manifest has UNKNOWN acquisition/source/license fields for many
   files.
5. Full CI not yet observed for this fix branch.

---

## 12. Recommendation

Do not merge PR #512 yet. Review this fix branch, then decide separately whether
Terminal may be a public static page. If not, move it off the Pages root before
any merge.
