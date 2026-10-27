# 供应链研究优先级 · 联网核验契约

`dashboard/data/serenity_verified.json` 由 `scripts/serenity_verify.py` 生成。
它**只补证据，不改** `skill_serenity.json` 的 `priority_rank`。

## 数据源

- SEC EDGAR：`company_tickers.json` → `submissions/CIK##########.json`，取最近 3 份 8-K/10-Q/10-K；
- yfinance `Ticker.calendar`：下次财报日；
- `dashboard_data.json` 的 `news.ticker_news`：最近 3 条新闻。

## Schema

```json
{"schema":1,"generated_at":"...","source":"SEC EDGAR + yfinance + news_data",
 "mode":"online_verification","count":10,
 "items":[{"ticker":"EOG","earnings_date":"2026-11-05",
           "filings":[{"form":"8-K","date":"2026-10-08","url":"https://www.sec.gov/..."}],
           "news":[{"title":"...","url":"..."}],
           "missing":["客户集中度"],"status":"verified"}]}
```

- 找不到写进 `missing`，不补结论；
- `status`: `verified`（三项至少一项命中） / `not_found`；
- 不调用 AI、不构成买入建议。
