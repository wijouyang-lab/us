# P11.2 Factor Definitions

All factors use adjusted close except volume; signal at close t, next adjusted
open entry, exit adjusted close t+h. Cross-sectional 1/99% winsorization is
applied before IC/quintile calculations.

| Factor | Definition | Data | Sign |
|---|---|---|---|
| mom5 | close/close.shift(5)-1 | adjusted close | higher = stronger |
| mom10 | close/close.shift(10)-1 | adjusted close | higher |
| mom20 | close/close.shift(20)-1 | adjusted close | higher |
| mom60 | close/close.shift(60)-1 | adjusted close | higher |
| mom120 | close/close.shift(120)-1 | adjusted close | higher |
| rs20 | mom20 - SPY 20d return | adjusted close | higher |
| rs60 | mom60 - SPY 60d | adjusted close | higher |
| rs120 | mom120 - SPY 120d | adjusted close | higher |
| slope20 | (close-close.shift(20))/(20*close.shift(20)) | adjusted close | higher |
| slope60 | same /60 | adjusted close | higher |
| slope120 | same /120 | adjusted close | higher |
| vol_anom20 | volume / 20d average volume -1 | raw volume | higher |
| volume_price_corr20 | corr(daily return, daily volume %change), 20d | raw volume | higher |
| vol20 | 20d std of daily returns * sqrt(252) | adjusted close | higher |
| vol60 | 60d std * sqrt(252) | adjusted close | higher |
| vol_change | vol20 - vol60 | adjusted close | higher |
| risk_adj_mom20 | mom20 / vol20 | adjusted close | higher |
| dd20 | close / 20d high -1 | adjusted close | higher (less negative) |
| dd60 | close / 60d high -1 | adjusted close | higher |
| dd120 | close / 120d high -1 | adjusted close | higher |

Risk adjustment numerator/denominator use same trailing window.

## Labels

```text
forward_h(t) = adjusted_close(t+h) / adjusted_open(t+1) - 1
excess_h(t)  = forward_h(t) - SPY close(t+h)/close(t+1) + 1
```

SPY uses close-to-close because no open series is stored; this is a documented
benchmark proxy.

## Data limitations

- Volume is raw; splits can create artificial jumps. Volume factors are
  `DATA_LIMITED`, not production-grade.
- Only S&P 500 names with local prices; no full delisted/OTC universe.
- 80 zero-member tickers and 62 unresolved identities remain.
- P6 fundamentals are current-only, not used here.
- No news/earnings/analyst data.
