# P10.4: US Historical Data Provider Evaluation (Trial Scope and License Audit)

Date: 2026-11-16
Branch: `research/p10-data-provider-evaluation`
Status: **EVALUATION ONLY — NO PURCHASE, NO SUBSCRIPTION**

---

## 1. Correction summary

The first P10 draft understated Sharadar's tiering and used the wrong currency for
EODHD. This revision separates subscription history tiers and does not treat
"table exists" as PIT coverage.

Key corrections:

- Sharadar Prices starts at **$9/mo for 5 years**, not a full-history product.
- Sharadar Bundle **$29/mo is 5 years**, not full history.
- P9.1 needs 2007-05-30 to 2024-12-31; only the **Full History** tiers can span it.
- EODHD Historian is recorded as **$19.99/mo / $199/yr**, not EUR 19.99.
- EODHD plan includes delisted tickers, splits/dividends and Bulk EOD; S&P 500
  historical constituents remain **UNKNOWN**.
- Norgate Platinum is **$346.50/6 months or $630/year**, with deletion obligations
  on expiry.
- EODHD Historical Constituents is a **$29.99/month add-on**; with Historian the
  total is **≈$49.98/month**. Daily snapshots start only in 2022-11-22; older
  change history is not a daily 2007 PIT series.
- Sharadar public evaluation is paused: **WRITTEN_APPROVAL_REQUIRED**.
- No provider has passed the 95% member-day / 98% ticker gates.

---

## 2. Sharadar official tiers

Official page: https://sharadar.com/subscribe

### Prices

| History tier | Monthly | Annual |
|---|---:|---:|
| 5 Years | $9 | $99 |
| 10 Years | $19 | $199 |
| Full History | $39 | $299 |

Prices includes `stocks`, `funds`, `metrics`, `actions`, and `sp500` tables. It
does **not** include the `fundamentals` table.

### Bundle

| History tier | Monthly | Annual |
|---|---:|---:|
| 5 Years | $29 | $299 |
| 10 Years | $49 | $399 |
| Full History | $69 | $499 |

Bundle includes prices, fundamentals, corporate actions/events and the S&P 500
table.

### What is not proven

- Earliest actual date in the `sp500` table.
- Whether the table is complete point-in-time membership or only a partial list.
- Whether full-history prices cover every delisted ticker needed by P9.1.
- Whether each ticker has the 2007-05-30 to 2024-12-31 range.

The table name is **not** evidence of PIT coverage.

### Public evaluation restriction

Sharadar's Personal Use License section 8 restricts publishing evaluations of the
service/data without prior written approval. The earlier P10 files already contain
public Sharadar sample-evaluation statements; those are not expanded here.

```text
SHARADAR_PUBLIC_EVALUATION: WRITTEN_APPROVAL_REQUIRED
SHARADAR_TEST_KEY_PIT_STATUS: NOT_RUN / NOT_SUFFICIENT
```

A free test-key probe was executed locally. Its row-level results are not
published in this repository. It did not establish a 2007-2024 daily PIT history;
no claim is made that the `sp500` table covers that interval until a licensed
extract is measured.

Pause further public Sharadar evaluation until written permission is obtained.
Do not commit Sharadar raw data.

The current HEAD neutralizes the public sample matrix, but older commits remain
accessible in Git history and may contain prior evaluation text. History was not
rewritten. Therefore the public-evaluation risk is **reduced but not fully
cleared** until written permission is obtained and the historical material is
reviewed.

---

## 3. EODHD correction

Official pages:

- https://eodhd.com/pricing/
- https://eodhd.com/help/plans
- https://eodhd.com/help/personal-use
- https://eodhd.com/help/storage

### Plan

```text
Personal Historian: $19.99/month or $199/year
EOD Historical Data — All World
```

Official plan description includes:

- full end-of-day history;
- delisted tickers;
- splits and dividends;
- Bulk EOD API, splits and dividends.

### Unknown

- S&P 500 historical constituents are **UNKNOWN** in this plan.
- Per-ticker history completeness is not guaranteed by the plan.
- A listed maximum history depth does not guarantee every ticker/date.

### Historical Constituents add-on

```text
$29.99/month add-on
Historian + add-on ≈ $49.98/month
```

Official add-on page notes:

- S&P 500 change history is listed from 1957.
- Daily component snapshots are available only since 2022-11-22.
- Broad S&P index change histories are generally since 2012.
- The page's current offer displays EUR 29.99; the budget record uses the
  requested USD 29.99 and does not claim an FX conversion.

Therefore the change-event history is not the same as daily PIT snapshots. It
cannot be assumed to reconstruct every trading day in 2007-2024.

### License

- Personal, non-professional use only.
- Private research, backtesting and paper trading are allowed.
- Private VPS/cloud server allowed if access to data and app is restricted to
  the licensee; public/shared access is not allowed.
- Raw data may be stored and retained after cancellation.
- No sharing, public display, redistribution or use for others.
- Publishing source code is allowed only without API keys, raw data, caches or
  outputs containing the data.
- Cancellation stops updates; existing downloads remain usable privately.

### Price data is not versioned

EODHD's methodology page states:

- OHLC are raw regular-session prices; `adjusted_close` is split/dividend
  adjusted.
- Historical corrections overwrite existing records; no change timestamps.
- No point-in-time vintage of past downloads is available.
- `adjusted_close` is recalculated across history after new splits/dividends.

Therefore separate PIT dimensions:

```text
historical universe membership:       UNKNOWN in Historian
historical price data:                current version only, not vintage
historical adjusted price vintage:    NOT AVAILABLE
corporate actions:                    available, but not as a full event history
```

Do not describe EODHD as a historical as-known-on-date data source.

---

## 4. Norgate PIT capability

Official pages:

- https://norgatedata.com/data-package-faq.php
- https://norgatedata.com/data-content-tables.php
- https://norgatedata.com/subscribe/eula.php
- https://norgatedata.com/freetrial.php

Platinum:

```text
6 months: $346.50
12 months: $630
Price history: essentially complete US listed/delisted coverage from late 1992
S&P 500 historical constituents: from March 1957
Historical constituents: daily TRUE/FALSE membership
Historical constituents access: Platinum or above
```

Vendor-documented details:

- US listed and delisted coverage is considered essentially complete from late
  1992; earlier coverage is progressively less complete.
- Historical index constituents are daily TRUE/FALSE observations, not month-end
  snapshots.
- The membership series shows the exact effective trading day; an addition
  effective before the open shows 1 on that date; a removal effective before the
  open shows 0 on that date.
- Announcement dates are not provided.
- Historical index constituent access is only at Platinum or Diamond.
- Norgate provides a stable `assetid`, but **does not provide prior tickers or
  prior company names**; price history is moved onto the current symbol.
- Corporate-action details are not provided as event records; they are embedded
  in adjusted price series.

### Critical trial limitation

The official three-week trial gives **Platinum-level access**, including delisted
securities and historical index constituents, but is deliberately limited to
**two years of historical data**. It cannot validate 2007-2024 or the 2007 start.

Therefore:

```text
NORGATE_PIT_CLAIM: VENDOR_DOCUMENTED / SAMPLE_NOT_VERIFIED
NORGATE_TRIAL_CAN_VALIDATE_2007_2024: NO
NORGATE_TRIAL_CAN_VALIDATE_2Y_SAMPLE: YES, if account/trial is manually started
```

License/EULA:

- Personal, non-commercial use only.
- Cloud/processing environments allowed only for the licensee's personal use.
- No redistribution, shared database or public display.
- On subscription expiry: delete Content, exports, extracts and backups.
- Derived Data (backtests, statistics, models) may be retained.

---

## 5. P9.1 interval: 2007-05-30 to 2024-12-31

| Option | Monthly cost | Covers 2007-2024? | Delisted | S&P 500 PIT | Personal cloud research | Keep raw after cancel |
|---|---:|---|---|---|---|---|
| A. EODHD Historian | **$19.99** | Likely full EOD, per-ticker **UNVERIFIED** | YES (plan claim) | **UNKNOWN** | YES (private) | YES |
| B. Sharadar Prices 10Y | **$19** | **NO** (trailing 10 years) | YES | Table present, **UNVERIFIED** | **UNKNOWN** | NO (delete) |
| C. Sharadar Prices Full | **$39** | Prices back to 1997-12; **needs extract** | YES | Table present, **UNVERIFIED** | **UNKNOWN** | NO (delete) |
| D. Sharadar Bundle Full | **$69** | Prices + fundamentals; **needs extract** | YES | Table present, **UNVERIFIED** | **UNKNOWN** | NO (delete) |
| E. Norgate Platinum | **$630/yr ≈ $52.50** | Prices 1992-late; S&P 500 constituents 1957-03; **needs extract** | YES | YES (daily TRUE/FALSE claim) | YES (personal) | NO (delete; trial only 2 years) |

A plus the Historical Constituents add-on is **≈$49.98/month**, still without a
verified daily 2007 PIT series.

### Direct answers

- **Long enough price history:** C, D, E can cover 2007. B cannot. A likely can but
  per-ticker completeness is not guaranteed.
- **S&P 500 historical constituents:** D and E claim it; C has the table but
  earliest date/completeness is UNKNOWN; A alone is UNKNOWN, and A+add-on has
  daily snapshots only since 2022-11-22 plus older change events; B is UNKNOWN.
- **Delisted stocks:** A, C, D, E claim support. Not yet sample-verified.
- **Personal DSH cloud research:** EODHD permits private research; Norgate permits
  personal processing environments; Sharadar's cloud position is UNKNOWN.
- **Retain raw data after cancellation:** EODHD YES; Sharadar NO; Norgate NO.
- **Norgate trial:** three weeks, Platinum level, but only **two years** of
  history; it cannot validate the 2007 start or 2007-2024.
- **95% member-day / 98% ticker:** **not verified for any option.** No PASS.

---

## 6. Minimum feasible plan

### Price-only research

**Sharadar Prices Full History — $39/month ($299/year)**

Why:

- covers 1997-12 onward;
- includes delisted prices and corporate actions;
- includes `sp500` table;
- does not include fundamentals.

But PIT table completeness and the 2007-2024 delisted coverage still need a
download audit.

### Price + fundamentals

**Sharadar Bundle Full History — $69/month ($499/year)**

Only needed if PIT fundamentals/events are required. It is not the first choice
for price-only P9.1 revalidation.

### Cheapest candidate

**EODHD Historian — $19.99/month ($199/year)**

It is the only candidate at the ~$20 line that officially includes delisted
tickers and Bulk EOD. Its S&P 500 historical constituents coverage is UNKNOWN, so
it cannot yet be called a complete P9.1 replacement.

### Full coverage

**Norgate Platinum — $630/year** or **CRSP** institutional. Strongest PIT and
delisted coverage claims, but far above budget.

---

## 7. Free sample evidence

No paid plan or trial was executed.

### EODHD demo key

The official demo key covers AAPL.US, MSFT.US and TSLA.US full history.

| Ticker | Rows | First | Last | Repeat SHA256 |
|---|---:|---|---|---|
| AAPL | 9,283 | 1990-01-02 | 2026-11-10 | MATCH |
| MSFT | 9,283 | 1990-01-02 | 2026-11-10 | MATCH |
| TSLA | 4,118 | 2010-06-29 | 2026-11-10 | MATCH |

AAPL splits returned 5 records (1987-06-16 through 2020-08-31).

This validates basic OHLCV availability and repeatability for three large,
currently listed tickers. It does **not** validate delisted names, 2007-2024
survivorship, S&P 500 PIT membership, or the 98% ticker gate.

### Sharadar official test key

Public evaluation is paused under Sharadar license §8.

```text
SHARADAR_PUBLIC_EVALUATION: WRITTEN_APPROVAL_REQUIRED
SHARADAR_TEST_KEY_PIT_STATUS: NOT_RUN / NOT_SUFFICIENT
```

A local test-key probe was attempted. Row-level dates/counts are not published.
The free key does not establish the 2007-2024 licensed `sp500` history, so it is
not marked PASS.

### EODHD delisted demo probes

The demo key returned HTTP 403 for TWTR, LEHMQ, ENRNQ, WCOMQ and BSC. These
remain `NOT_RUN`; no paid endpoint was used to fake a result.

### Sample matrix

`data/research/p10_sample_validation.csv` has 34 tickers × 3 candidates = 102
rows. Current status:

```text
PARTIAL: 3   (AAPL/MSFT/TSLA EODHD)
NOT_RUN: 99
PASS:     0
```

No unverified metric is marked PASS.

---

## 8. Norgate trial acceptance plan

Do not auto-register. A human must start the official three-week trial.

### What the trial can test

The trial is Platinum-level but limited to two years. It can test:

- AAPL, MSFT, NVDA, BRK.B;
- recent delisted names whose delisting falls inside the trial window;
- rename/split/M&A samples;
- API/updater mechanics;
- daily TRUE/FALSE S&P 500 membership for the **two-year window**;
- effective dates within that window;
- `assetid` continuity;
- repeated download and rebuild consistency.

The old names LEHMQ, ENRNQ, WCOMQ and BSC traded long before the two-year
window. They are **NOT_RUN / OUTSIDE_TRIAL_HISTORY**, not executable trial
samples.

Recent delisting candidates confirmed by SEC Form 25:

| Ticker | Company | Form 25 date | Trial scope |
|---|---|---|---|
| WBA | Walgreens Boots Alliance | 2025-08-28 | CANDIDATE_IN_WINDOW |
| HES | Hess | 2025-07-18 | CANDIDATE_IN_WINDOW |
| ANSS | Ansys | 2025-07-17 | CANDIDATE_IN_WINDOW |
| JNPR | Juniper Networks | 2025-07-02 | CANDIDATE_IN_WINDOW |

Sources: SEC EDGAR submissions for
[WBA](https://data.sec.gov/submissions/CIK0001618921.json),
[HES](https://data.sec.gov/submissions/CIK0000004447.json),
[ANSS](https://data.sec.gov/submissions/CIK0001013462.json),
[JNPR](https://data.sec.gov/submissions/CIK0001043604.json).

These are candidates, not verified trial data. Availability must be checked in
the actual trial before any status changes.

It **cannot** test 2007-05-30 to 2024-12-31 or the full 95%/98% gates.

### Required checks

```text
TRIAL_SCOPE: 2 years only
TRIAL_STARTED: NO
TRIAL_DATA_DOWNLOADED: NO
```

1. Price first/last date for each sample.
2. Delisted history presence and final trading date.
3. Daily TRUE/FALSE membership for each sample/date.
4. Effective-date check around additions/removals.
5. Current-symbol/assetid mapping; prior ticker strings are unavailable.
6. Member-day coverage and ticker coverage, two-year version only.
7. Repeat download and rebuild determinism.
8. Record SHA256 of derived extracts; do not commit raw data.

### Post-trial (requires paid subscription)

Only after purchase can the 2007-2024 window be measured. Then apply the original
unaltered gates:

```text
member-day >= 95%
ticker >= 98%
```

If the trial output is treated as full-history evidence, the test is invalid.

**Recommendation:** the trial is worth starting only to verify API/mechanics and
two-year delisted/PIT behavior. It cannot by itself approve Norgate for P9.1.

---

## 9. License comparison

| Provider | Personal research | Cloud processing | Redistribution | Retain raw after cancel |
|---|---|---|---|---|
| Sharadar | YES (individual) | UNKNOWN | NO | NO, delete raw |
| EODHD | YES (private) | YES — PRIVATE LICENSEE ONLY | NO | YES |
| Norgate | YES (personal) | YES, personal processing | NO | NO, delete raw/backups |
| Alpha Vantage | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| CRSP | Institutional | Institutional | NO | Institutional terms |

No provider permits publishing the raw dataset in this public repository.

---

## 10. Public exposure audit

Checked:

- **GitHub Pages** — source is `main`, not this research branch. No vendor data
  is in the public build.
- **Public Dashboard** — no vendor price/PIT files; P10 files are under
  `data/research`, not served by the dashboard.
- **GitHub Actions artifacts** — P10 adds no artifact. Existing P7/Terminal
  artifacts contain no vendor data.
- **Public CSV/JSON** — only provider metadata, sample status and aggregate
  hashes/counts; no raw vendor OHLCV, PIT membership or fundamentals.
- **Auto-committed scans** — no P10 data is wired into production scanners.

Risk if a subscription data file is later placed in `data/research` and committed:
it would be public. That is prohibited by Sharadar/EODHD/Norgate personal terms.

Required private pipeline if procured:

```text
private DB/object store (not Pages, not public repo, not public artifact)
  -> private analysis environment
  -> only derived, non-reconstructable aggregate outputs may be published
```

If that isolation cannot be guaranteed, a commercial licence is a prerequisite.

---

## 11. Decision

```text
P10_PROVIDER_EVALUATION: COMPLETE
P10_PURCHASE_DECISION: NONE
P10_RECOMMENDED_PRICE_ONLY_TRIAL: Sharadar Prices Full History ($39/mo)
P10_RECOMMENDED_BUNDLE_TRIAL: Sharadar Bundle Full History ($69/mo)
P10_CHEAPEST_UNVERIFIED_OPTION: EODHD Historian ($19.99/mo)
P10_EODHD_WITH_CONSTITUENTS: ≈ $49.98/mo
SHARADAR_PUBLIC_EVALUATION: WRITTEN_APPROVAL_REQUIRED
NORGATE_PIT_CLAIM: VENDOR_DOCUMENTED / SAMPLE_NOT_VERIFIED
NORGATE_TRIAL_CAN_VALIDATE_2007_2024: NO
NORGATE_TRIAL_WORTH_STARTING: LIMITED (2-year mechanics only)
P10_BUDGET_COMPATIBLE_WITH_VERIFIED_PIT: NO
P9_DATA_REPRODUCIBILITY: BLOCKED
P9_RESULTS: unchanged; all 8 NO-GO
```

No purchase, payment details, subscription, or vendor connection was made.

### Next manual approval

1. **Norgate three-week trial:** worth starting only for two-year API,
   delisted-ticker, daily membership, effective-date and repeatability checks.
   It cannot approve the 2007-2024 P9.1 interval.
2. **Sharadar:** do not publish further evaluation until written approval; if
   approved, trial **Prices Full History $39/month** first. Use Bundle Full
   History $69/month only if fundamentals are required.
3. **EODHD:** $19.99/month is the cheapest private-use option with retention, but
   it lacks a validated 2007-2024 daily PIT series.

All post-trial coverage tests must use the original unaltered gates:

```text
member-day >= 95%
ticker >= 98%
interval 2007-05-30 .. 2024-12-31
```

Do not commit raw vendor data; use the private pipeline described above.

---

## 12. Official sources

- Sharadar subscribe/prices: https://sharadar.com/subscribe
- Sharadar prices: https://sharadar.com/prices
- Sharadar bundle: https://sharadar.com/bundle
- Sharadar license: https://sharadar.com/terms
- EODHD pricing: https://eodhd.com/pricing/
- EODHD plans: https://eodhd.com/help/plans
- EODHD methodology: https://eodhd.com/help/methodology
- EODHD AI/cloud tools: https://eodhd.com/help/ai-tools
- EODHD personal use: https://eodhd.com/help/personal-use
- EODHD storage/cancellation: https://eodhd.com/help/storage
- EODHD S&P Global add-on: https://eodhd.com/lp/spglobal
- Norgate packages: https://norgatedata.com/stockmarketpackages.php
- Norgate EULA: https://norgatedata.com/subscribe/eula.php
- SEC EDGAR API: https://www.sec.gov/edgar/sec-api-documentation
- FRED: https://fred.stlouisfed.org/
- GDELT: https://www.gdeltproject.org/
