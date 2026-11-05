# US Market-Wide Quote Coverage — P6.2

Date: 2026-11-05
Branch: `research/us-market-quotes-p62`
Base: `research/us-market-universe-p61` (PR #498 still open)
Status: **AUDIT ONLY — current quotes, no history/fundamentals/backtest**

## 1. Result

| Metric | Result |
|---|---:|
| Target denominator (Common + ADR) | **5,502** |
| Common | 5,187 |
| ADR | 315 |
| Batch spot records | **13,895** |
| QUOTE_MATCHED | **5,488** |
| QUOTE_NOT_FOUND | **0** |
| AMBIGUOUS_MATCH | **4** |
| INVALID_QUOTE | **10** |
| SOURCE_ERROR | **0** |
| **quote_coverage** | **99.7455%** |

```text
quote_coverage = 5,488 / 5,502 = 0.997455
```

AkShare version: **1.20.28**
Source: `ak.stock_us_spot_em()`
Snapshot: `2026-11-05T08:16:00Z`
Delay: **15 minutes** (not real-time)
Only one batch request was made; no per-symbol quote loop.

## 2. Category coverage

| Security type | Total | Matched | Coverage |
|---|---:|---:|---:|
| Common | 5,187 | 5,175 | **99.7687%** |
| ADR | 315 | 313 | **99.3651%** |

ADR coverage is slightly lower; two ADR invalid quotes remain.

## 3. Exchange coverage

| Exchange | Total | Matched | Coverage |
|---|---:|---:|---:|
| NASDAQ | 3,397 | 3,385 | 99.6467% |
| NYSE | 1,861 | 1,859 | 99.8925% |
| NYSE American | 237 | 237 | 100% |
| NYSE Arca | 1 | 1 | 100% |
| Cboe BZX | 1 | 1 | 100% |
| OTHER:F | 5 | 5 | 100% |

NASDAQ and ADR have the lowest coverage, but both remain above 99.3%.

## 4. Field coverage

Among the 5,502 target securities:

| Field | Available | Coverage |
|---|---:|---:|
| Price | 5,488 | **99.7455%** |
| Market cap | 5,437 | **98.8186%** |
| PE | 5,211 | **94.7110%** |

PE or market-cap absence does **not** invalidate a usable positive price; fields are reported separately.

## 5. Failures (16 rows)

### Ambiguous (4)

| Ticker | Type | Exchange | Candidates |
|---|---|---|---|
| BID | COMMON | NASDAQ | `105.BID`, `106.BID` |
| LUNG | COMMON | NASDAQ | `105.LUNG`, `105.LUNG_` |
| PC | COMMON | NASDAQ | `105.PC`, `106.PC` |
| DCOM | COMMON | NYSE | `106.DCOM`, `106.DCOM_` |

These are retained as ambiguous; no arbitrary candidate was selected.

### Invalid quote (12)

Target invalid (10):

```text
EFTY, HCHL, LAWR, MAGH, MCTA, OST, SVA, TJGC, UCFI, OPAY
```

UNCLASSIFIED invalid (2, not in denominator):

```text
GJO, JBK
```

The failures CSV also includes these unclassified rows with `cohort=UNCLASSIFIED`.

## 6. 28-company regression

```text
sample_28_matched = 28/28
```

All previously audited 28 companies still map to a quote.

## 7. UNCLASSIFIED cohort

Processed separately, not in the 5,502 denominator:

```text
UNCLASSIFIED total: 113
matched: 111
not found: 0
ambiguous: 0
invalid quote: 2 (GJO, JBK)
```

## 8. Tick matching

- Ticker class separators are preserved:
  - `AGMH` and `AGM_H` are different securities;
  - `BRK.B`, `BRK-B`, `BRK_B` are equivalent class notation.
- `GOOG` / `GOOGL`, `FOX` / `FOXA`, `NWS` / `NWSA`, `BRK.A` / `BRK.B` remain distinct.
- Exact normalized ticker matching is used first; ambiguous same-key matches can use company-name evidence, otherwise they remain `AMBIGUOUS_MATCH`.
- No unresolved ticker was silently deleted.

## 9. Data source assessment

AkShare `stock_us_spot_em()` returned 13,895 records in one batch and covered
**99.7455%** of the confirmed Common+ADR universe.

It is sufficient as the **primary current-quote source** for this universe,
subject to:

- 15-minute delay;
- 4 ambiguity cases needing a secondary lookup;
- 10 target invalid quotes;
- field gaps for market cap/PE;
- no per-symbol fallback attempted here (batch audit only).

It is not a real-time or execution-grade feed.

## 10. Files

```text
tools/research/audit_us_market_quotes_p62.py
tests/test_us_market_quotes_p62.py
data/universe/us_market_quote_coverage_p62.json
data/universe/us_market_quote_mapping_p62.csv
data/universe/us_market_quote_failures_p62.csv
.github/workflows/research-us-market-quotes-p62.yml
```

Live run:

```text
https://github.com/wijouyang-lab/us/actions/runs/41993795459
artifact: 13400172203
```

## 11. Conclusion

1. **5,502 家中实际匹配 5,488 家。**
2. **全市场当前报价覆盖率 99.7455%。**
3. 覆盖最低的是 ADR（313/315），NASDAQ 也略低于 NYSE；但仍超过 99.3%。
4. **AkShare 足够作为主要免费当前行情源**，但不能当作实时/执行级数据；需要处理 4 个歧义和 10 个目标无效报价。
5. 失败股票已逐条列出，未删除、未强行合并。
6. 下一阶段可以开始 SEC 基本面批量采集，但应独立建立 PIT/披露时间门禁，不能把当前报价当作历史或评分输入。
