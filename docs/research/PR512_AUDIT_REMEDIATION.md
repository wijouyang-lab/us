# PR #512 Audit Remediation

Date: 2026-11-10  
Branch: `fix/pr512-audit-remediation`  
Base for review: `research/invest-terminal-v1` at `9b07f588dd5af05017d2d4cba36ae87a23d9460a`  
No merge or deployment.

---

## Final status

```text
WORKFLOW_SECURITY: PASS
PRODUCTION_ISOLATION: PASS
PAGES_JEKYLL_BUILD: PASS
PAGES_TERMINAL_EXPOSURE: PASS
PAGES_SNAPSHOT_EXPOSURE: PASS
PUBLIC_ARTIFACT_AUDIT: PASS
LOCAL_PAPER_DB_EXCLUDED: PASS
SNAPSHOT_REDACTION: PASS
P9_METRIC_CONSISTENCY: PASS
P9_BH_FAMILY_CONSISTENCY: PASS
P9_DATA_REPRODUCIBILITY: BLOCKED
MARKET_WIDE_DATA_GATE: BLOCKED
SP500_LOCAL_SOURCE_MATCH: PASS
UPSTREAM_BYTES_RETRIEVAL_AVAILABLE: YES
DATASET_LICENSE_SCOPE_VERIFIED: NO
THIRD_PARTY_DATA_RIGHTS_VERIFIED: NO
REDISTRIBUTION_ALLOWED: UNKNOWN
LEGAL_INDEPENDENT_REBUILD_AVAILABLE: UNKNOWN
SP500_DATA_LICENSE: UNKNOWN
FINSABER_SOURCE: UNKNOWN
FINSABER_LICENSE: UNKNOWN
DATA_PROVENANCE: PARTIAL
PAPER_ENGINE_SECURITY: PASS
PR512_READY_FOR_REVIEW: NO
```

The P0 workflow and Dashboard coupling issues are fixed. Terminal was moved to
`_local_terminal/`; Jekyll built successfully on a GitHub hosted runner and the
published output contains no Terminal or snapshot. P9.1 raw inputs remain
missing from Git, so independent PR regeneration remains blocked.

---

## 1. Modified files

```text
.github/workflows/p7-shadow-daily.yml
.github/workflows/dashboard-data.yml
.github/workflows/research-invest-terminal.yml
.gitignore
index.html
dashboard/data/invest_terminal_data.json   (removed from Git)
_local_terminal/terminal.html              (moved)
_local_terminal/terminal.css               (moved)
_local_terminal/terminal.js                (moved)
data/research/p9_1_support_resistance/event_results.csv
data/research/p9_1_support_resistance/event_hac.csv
data/research/p9_1_support_resistance/event_bh.csv
data/research/p9_1_support_resistance/p9_1_status.json
docs/research/p9_1_support_resistance.md
tests/conftest.py
tests/test_invest_terminal.py
tests/test_invest_terminal_server.py
tests/test_invest_terminal_snapshot_sync.py
tests/test_p9_1_support_resistance.py
tests/test_pr512_remediation.py             (new)
tools/invest_terminal/build_snapshot.py
tools/invest_terminal/server.py
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

- Terminal moved to `_local_terminal/` (`terminal.html`, `terminal.css`,
  `terminal.js`).
- `tools/invest_terminal/`, `tools/paper_trading/`.
- Local loopback server and PAPER engine.
- `research-invest-terminal.yml` remains a separate read-only integration
  workflow and artifact producer.

### Pages exposure

GitHub Pages settings (API):

```text
enabled: true
build_type: legacy
source: main / (root)
html_url: https://wijouyang-lab.github.io/us/
```

There is no `.nojekyll` and no `_config.yml` include. Jekyll excludes
underscore-prefixed directories by default, so `_local_terminal/` is not copied
to the Pages output. The Dashboard no longer links to it.

Actual Jekyll build verification on GitHub hosted runner:

```text
workflow: Pages Build Audit (no deploy)
run:      42834839864
result:   success
PAGES_TERMINAL_EXPOSURE=PASS
PAGES_SNAPSHOT_EXPOSURE=PASS
```

The workflow uses `actions/jekyll-build-pages@v1`, source `./`, destination
`./_site`, and has no deploy step or `pages: write` / `id-token: write`.
Assertions confirmed:

- `_site/terminal.html` absent;
- `_site/terminal/` absent;
- `_site/_local_terminal/` absent;
- `_site/dashboard/data/invest_terminal_data.json` absent;
- no `terminal.css` / `terminal.js` / snapshot anywhere in `_site`;
- `_site/index.html` contains neither Terminal href nor `investTerminalLink`.

Do not switch Pages to an Actions deployment without an explicit publication
decision.

### Public Actions artifacts

P7 artifact now contains only `data/universe/p7/`; it no longer builds or uploads
`invest_terminal_data.json`.

Terminal workflow artifact now contains only `_local_terminal/` assets. It no
longer uploads the snapshot.

```text
PUBLIC_ARTIFACT_AUDIT: PASS
LOCAL_PAPER_DB_EXCLUDED: PASS
SNAPSHOT_REDACTION: PASS
```

Tests assert no `paper.sqlite`, WAL, SHM, confirmation token, CSRF or session
secret is in the snapshot/artifact paths. A clean CI no-DB snapshot reports
`LOCAL_PAPER_DB_NOT_PRESENT` and `paper_db_exists=false`.

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

Neither is present in the branch. They were found in the local DSH workspace:

```text
finsaber_prices_raw.csv 265,180,873 bytes
sha256 f67e3972dceefbbdf6c17b84b30957a7b83518401955fff8ae0bc4ae206fa83f
sp500_daily.csv          5,533,628 bytes
sha256 646b2e47284abfb675abebacd4a4035ba22a79ea1ccdeccce7fbe5f0e27bab3a
```

They were used for one local full rerun, but are **not committed** due size and
unverified redistribution rights. The rerun reproduced:

```text
raw_signal_rows: 204180
valid_5d_experiment_observations: 204030
event_horizon_observations: 611790
all 8 portfolios NO-GO
```

`P9_DATA_REPRODUCIBILITY` remains **BLOCKED for the PR** because these inputs
are not in Git and an independent checkout cannot recreate the run.

### Source findings

`sp500_daily.csv`:

Fixed upstream commit:

```text
a2430f2af0c79ddf0748e91de11bdeb1616ab5a7
```

Upstream file:

```text
size:   5,530,907 bytes
sha256: 36326709d46d6cd25834de5df457b16f5f96fad3a06b9beac28f7b88aa0b0d54
blob:   656b033be9418db272f1903f4f8e79a2a8664e6a
```

Local file:

```text
size:   5,533,628 bytes
sha256: 646b2e47284abfb675abebacd4a4035ba22a79ea1ccdeccce7fbe5f0e27bab3a
git hash-object: 656b033be9418db272f1903f4f8e79a2a8664e6a
```

Comparison:

```text
size delta:          2,721 bytes
CRLF count local:    2,721
CRLF count upstream: 0
LF count both:       2,721
CRLF->LF normalized bytes equal: TRUE
git blob hash equal: TRUE
```

The local file is the upstream CSV converted to CRLF; field content is
unchanged. The conversion is consistent with `fetch_sp500_history.py`
(`pandas.read_csv` -> `to_csv` on Windows).

Source status:

```text
SP500_LOCAL_SOURCE_MATCH: PASS
UPSTREAM_BYTES_RETRIEVAL_AVAILABLE: YES
REPOSITORY_LICENSE_METADATA: MIT
DATASET_LICENSE_SCOPE_VERIFIED: NO
THIRD_PARTY_DATA_RIGHTS_VERIFIED: NO
REDISTRIBUTION_ALLOWED: UNKNOWN
LEGAL_INDEPENDENT_REBUILD_AVAILABLE: UNKNOWN
```

The README states the original list came from the *Trading Evolved* book download
and later updates came from Wikipedia. The repository MIT license does not by
itself establish redistribution rights for those third-party inputs. Therefore
the file is not committed and the data license remains UNKNOWN.

`finsaber_prices_raw.csv`:

```text
LOCAL_FILE_FOUND: yes
SOURCE_VERIFIED: no
provider: inferred only from filename; no download script/URL/log found
downloaded_at: UNKNOWN
LICENSE_VERIFIED: no
REDISTRIBUTION_ALLOWED: unknown
INDEPENDENT_REBUILD_AVAILABLE: no
```

The price file is not committed; its provider/license cannot be proven from the
workspace. Do not replace it with another free source to force P9 to pass.

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
raw_signal_rows: 204180
valid_5d_experiment_observations: 204030
experiment_horizon_observations: 611790
event_rows: 24
bh_family_unique: 18
duplicate_alias_cells: 6
```

`204,030` is the sum of each experiment's widest valid count; it includes the
duplicate G=C and H=F aliases. It is not a global unique ticker/date count.
`611,790` is the sum of the 24 horizon cells.

`strategy.py` now derives these fields instead of treating them as one number.

BH correction: only A–F are canonical (6 experiments × 3 horizons = 18
hypotheses). G and H copy C and F q-values respectively for both ordinary and
non-overlap BH. Raw p-values and NAV are unchanged.

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

Counts:

```text
source known:        85 / 198
source UNKNOWN:     113 / 198
acquired_at UNKNOWN:198 / 198
license UNKNOWN:    198 / 198
rebuildable UNKNOWN:198 / 198
```

Many source/acquired/license fields are `UNKNOWN` because the branch does not
contain that evidence. This is intentionally not invented. Status is therefore
`DATA_PROVENANCE: PARTIAL`, not PASS.

---

## 10. Tests

Two focused commands with different scopes were used:

```text
# 6 files, including test_invest_terminal.py
pytest tests/test_invest_terminal.py
       tests/test_invest_terminal_server.py
       tests/test_invest_terminal_snapshot_sync.py
       tests/test_paper_trading_platform.py
       tests/test_p9_1_support_resistance.py
       tests/test_pr512_remediation.py
# 60 passed in 6.19s
```

```text
# 5 files, excluding test_invest_terminal.py
pytest tests/test_p9_1_support_resistance.py
       tests/test_pr512_remediation.py
       tests/test_invest_terminal_server.py
       tests/test_invest_terminal_snapshot_sync.py
       tests/test_paper_trading_platform.py
# 43 passed in 5.78s
```

The earlier `59 passed` was the six-file scope before the final status test was
added; it is superseded by `60 passed`.

Final Full CI on the pushed fix branch:

```text
1524 passed, 1 skipped
https://github.com/wijouyang-lab/us/actions/runs/42849147909
```

Final Pages build audit, exact HEAD
`0ba23a5296ad90fb3913cd59e94763cccae96fc0`:

```text
success
https://github.com/wijouyang-lab/us/actions/runs/42849158668
PAGES_TERMINAL_EXPOSURE=PASS
PAGES_SNAPSHOT_EXPOSURE=PASS
no-deploy Jekyll build
```

Historical verification (superseded, retained for audit):

```text
Full CI: 1524 passed, 1 skipped
https://github.com/wijouyang-lab/us/actions/runs/42845885053

Pages: success
https://github.com/wijouyang-lab/us/actions/runs/42845897184
HEAD: 7e4d6c8b85a2826d3e9c4a92126504d89684ddb4
```

`git diff --check`: clean. `git status`: only intended changes plus the new
manifest/test; no production scanner/ledger changes.

---

## 11. Remaining blockers

1. Finsaber price data source and license are UNKNOWN; the file is not in Git.
2. SP500 file-level origin matches a fixed upstream commit after CRLF
   normalization, but third-party dataset redistribution rights remain UNKNOWN.
3. Historical coverage is below the research gates:
   - member-day 89.58% < 95%;
   - ticker 91.55% < 98%.
4. P9.1 cannot be independently regenerated from the PR alone;
   `P9_DATA_REPRODUCIBILITY` and `MARKET_WIDE_DATA_GATE` are BLOCKED.
5. Provenance manifest has UNKNOWN acquisition/source/license fields for many
   files.

---

## 12. Recommendation

Do not merge PR #512 or #554 yet.

Terminal is a local `127.0.0.1` service. The hosted Jekyll build contains no
Terminal page, CSS, JS or snapshot. The local PAPER engine remains available and
is not connected to a broker or real trading.

P9.1 still has multiple independent blockers: Finsaber source/license are
UNKNOWN; SP500 third-party redistribution rights are UNKNOWN; member-day and
ticker coverage are below the 95%/98% gates; and neither raw input is committed.
Keep `P9_DATA_REPRODUCIBILITY` and `MARKET_WIDE_DATA_GATE` BLOCKED until these
are resolved by evidence, not by substituting a new provider.

All eight P9.1 portfolios remain NO-GO; no NAV, return or p-value was changed.
