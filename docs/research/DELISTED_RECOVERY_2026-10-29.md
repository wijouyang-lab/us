# Delisted Historical Price Recovery Probe

Date: 2026-10-29 UTC
Research only. No canonical panel write.

## Sample

24 delisted/removed S&P names with removal years from 2002鈥?025, plus a
12-name Wayback CDX check.

## Actual results

| Result | Count |
|---|---:|
| Yahoo chart 404/no data | 22 |
| Yahoo series appears to be ticker reuse | 2 (`ADCT`, `INFO`) |
| Wayback CDX snapshots found | **0/12** |
| Accepted pre-delisting series | **0** |

### Yahoo

- `ADCT`: HTTP 200, 1,414 rows, first 2020-05-18, last 2025-12-31.
  Removal year 2007 鈫?**ticker reuse, rejected**.
- `INFO`: HTTP 200, 307 rows, first 2024-10-10, last 2025-12-31.
  Removal year 2022 鈫?**ticker reuse, rejected**.
- `ALTR`, `BRCM`, `CA`, `TWX`, `ALXN`, `XLNX`, `NUAN`, `CTXS`, `TWTR`,
  `ATVI`, `SIVB`, `FRC`, `PBCT`, `DISCA`, `CERN`, `ABMD`, `WLTW`, `ANSS`,
  `WCOM`, `LEHM`, `BSC`: HTTP 404/no series.

### Wayback legacy Yahoo CSV

CDX queries for 12 delisted tickers:
`ADCT, ALTR, BRCM, CA, TWX, ALXN, XLNX, NUAN, CTXS, TWTR, ATVI, SIVB`.

All returned HTTP 200 with **0 matching snapshots**. The earlier fetch
attempts therefore failed because no archived CSV exists, not because of a
usable partial download.

## Validator

`tools/research/delisted_recovery_validator.py` rejects:

- empty frame;
- missing date;
- series starting after removal (ticker reuse);
- series ending too early;
- series extending after removal;
- missing/invalid OHLC.

Tests: `tests/test_delisted_recovery_validator.py` 鈥?**5 passed**.

A recovered series must also match the historical security identity; numeric
OHLCV alone is insufficient.

## Files

- Results CSV: `docs/research/delisted_recovery_results_2026-10-29.csv`
- Yahoo probe: `docs/research/yahoo_delisted_probe_2026-10-29.json`
- Wayback probe: `docs/research/wayback_cdx_probe_2026-10-29.json`
- validator: `tools/research/delisted_recovery_validator.py`

## Actual new historical records

**0.**

No series was accepted, so no independent delisted dataset was created.

## Stop condition

For the tested free paths:

- Yahoo: no old delisted series; only ticker reuse or 404.
- Wayback legacy Yahoo CSV: no indexed snapshots.

Do not repeat these same probes. Further work must use a different free
official/archival source with a clear data identity and usage basis, or accept
that delisted coverage is unavailable.

## Impact

The current 503-name panel remains survivorship-biased. It cannot be described
as a complete historical universe, and the five-factor results cannot be
called full-PIT or delisted-inclusive.
