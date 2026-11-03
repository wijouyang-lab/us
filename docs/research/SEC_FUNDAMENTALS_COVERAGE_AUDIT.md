# SEC Fundamentals Coverage Audit — P2

Date: 2026-11-04
Sample: 9 companies, not full-market coverage.

## 1. Identity and download

| Ticker | CIK | CompanyFacts |
|---|---|---:|
| AAPL | 0000320193 | 25,598 facts |
| MSFT | 0000789019 | 33,058 |
| GOOGL | 0001652044 | 21,498 |
| AMZN | 0001018724 | 30,289 |
| NVDA | 0001045810 | 27,281 |
| BRK.B | 0001067983 | 18,233 |
| JPM | 0000019617 | 54,330 |
| PLD | 0001045609 | 23,446 |
| RIVN | 0001874178 | 6,554 |

- ticker→CIK mapping: **9/9**
- CompanyFacts download: **9/9**
- Source: SEC `company_tickers.json` + `data.sec.gov` CompanyFacts.
- Cache: `data/sec/cache/companyfacts_<cik>.json` with URL, fetched_at, SHA-256.

## 2. Current metric coverage

| Ticker | CIK | Revenue $B | Net income $B | FCF $B | Equity $B | Total debt $B | Gross margin | ROE | Rev growth | 3y Rev CAGR | PEG |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| AAPL | 0000320193 | 458.39 | 124.90 | 146.27 | 112.09 | 78.11 | 48.5% | 111.4% | 15.1% | 7.7% | DATA_BLOCKED |
| MSFT | 0000789019 | 334.11 | 134.61 | 65.98 | 470.51 | 35.48 | 68.1% | 28.6% | 17.8% | 16.1% | DATA_BLOCKED |
| GOOGL | 0001652044 | 459.62 | 236.22 | 63.12 | 677.55 | 126.12 | — | 34.9% | 15.1% | 12.5% | DATA_BLOCKED |
| AMZN | 0001018724 | 764.24 | 134.77 | -61.40 | 613.60 | 173.50 | 0.6% | 22.0% | 12.4% | 11.7% | DATA_BLOCKED |
| NVDA | 0001045810 | 281.58 | 176.34 | 92.41 | 228.98 | 33.37 | 74.2% | 77.0% | 65.5% | 100.0% | DATA_BLOCKED |
| BRK.B | 0001067983 | 382.97 | 78.94 | 23.23 | 747.91 | — | — | 10.6% | -1.0% | 6.0% | DATA_BLOCKED |
| JPM | 0000019617 | 94.81 | 67.03 | — | 374.60 | 342.36 | — | 17.9% | 2.8% | 12.3% | DATA_BLOCKED |
| PLD | 0001045609 | 8.95 | 2.91 | — | 53.50 | — | — | 5.4% | 7.2% | 13.7% | DATA_BLOCKED |
| RIVN | 0001874178 | 6.75 | -3.33 | -4.93 | 5.90 | 4.45 | 7.4% | -56.5% | 8.4% | 48.1% | DATA_BLOCKED |

Missing values are `—` / explicit status, never zero.

## 3. Per-metric coverage

| Field | OK / 9 |
|---|---:|
| Revenue | 9 |
| Net income | 9 |
| Free cash flow | 7 |
| Stockholders' equity | 9 |
| Total debt | 7 |
| Gross margin | 5 |
| Operating margin | 8 |
| Net margin | 9 |
| ROE | 9 |
| FCF conversion | 7 |
| Debt/equity | 6 |
| Net debt/EBITDA | 4 |
| ROIC | **0** (tax/invested-capital not implemented) |
| Interest coverage | **0** (interest expense not implemented) |
| Revenue growth | 9 |
| EPS growth | 8 |
| FCF growth | 7 |
| 3y revenue CAGR | 9 |
| 5y revenue CAGR | 8 |
| Operating leverage | 8 |
| PEG | **0** (forward estimates unlicensed) |
| PE / PB / EV / yields | **0** (no authorized price) |

## 4. Data gaps by company type

- **JPM (bank)**: FCF and gross profit are not comparable; net debt/EBITDA is
  `NOT_APPLICABLE`. Revenue/net income/ROE remain available.
- **PLD (REIT)**: FCF/capex and debt tags are incomplete in CompanyFacts;
  net-debt/EBITDA not computed.
- **BRK.B**: total debt and gross profit are missing; `-` shown, not zero.
- **RIVN (loss-making)**: net income/FCF negative; PE is `NOT_APPLICABLE`;
  growth from a small base can be large and is not a profitability claim.
- **GOOGL**: gross profit tag absent in the mapped set; gross margin `—`.

## 4b. Request configuration

SEC_USER_AGENT is required and must contain a real contact. This local smoke
run used the placeholder contact
esearch contact@example.com; production must
replace it. No email was inferred from Git history. Requests use 0.25s minimum
interval, timeout, retry/backoff, cache and SHA-256.

## 5. XBRL and units

- Accepted units: USD, USD/shares, shares.
- EPS uses `USD/shares`; it is never mixed with USD totals.
- Instant facts used for balance-sheet items; duration facts for flows.
- TTM uses four distinct 70–100 day quarters when available; otherwise the
  latest annual period, explicitly labelled `FY`.
- 6-month/9-month YTD values are not treated as single quarters.
- Amended filings remain separate facts; as-of selection uses the latest
  `filed` date available at that as-of date.
- Custom/unmapped tags are not guessed or merged into standard concepts.

## 6. PIT quality distribution

For OK metrics in the sample:

| Quality | Count |
|---|---:|
| `ACCEPTANCE_ESTIMATE` | 189 |
| `FILED_DATE_ONLY` | 24 |
| `OBSERVED_FIRST_SEEN` | 0 |
| `UNKNOWN` | 0 |

- `available_at` uses the SEC acceptance timestamp when present, else filing date.
- `first_seen_at` is null because this is a historical backfill, not an observed
  forward capture. It is **not** labelled `OBSERVED_FIRST_SEEN`.
- `FILED_DATE_ONLY` facts are only suitable for conservative daily as-of work,
  not intraday historical simulation.
- The full CompanyFacts JSON downloaded today cannot reconstruct what was visible
  intraday in the past.

## 7. What this establishes

Established:

- real SEC identity mapping;
- real CompanyFacts ingestion and caching;
- traceable facts with accession/form/filed/unit;
- as-of gating by filing date;
- Value flow metrics, Quality profitability/leverage metrics, and historical
  GARP growth metrics;
- explicit `DATA_BLOCKED`, `NOT_APPLICABLE`, `INSUFFICIENT_DATA` states.

Not established:

- licensed market prices, so PE/PB/EV/FCF yield/Margin of Safety are blocked;
- ROIC and interest coverage;
- forward EPS/PEG;
- full-market coverage;
- exact historical first-public-visibility timestamps;
- long-horizon historical PIT backtest.

## 8. Files

```text
docs/research/sec_fundamentals_snapshot.json
docs/research/sec_sample_facts.json
docs/research/SEC_FUNDAMENTALS_COVERAGE_AUDIT.md
tools/investment_research/sec/client.py
tools/investment_research/sec/normalize.py
tools/investment_research/sec/service.py
tools/investment_research/metrics.py
tools/investment_research/ingest_sample.py
tests/test_sec_client.py
tests/test_sec_fundamentals.py
```
