# Validation Report — Corrected Timing

## Engineering fix

- Month-end signal at `t` -> position at `t+1`.
- Cost charged on actual position change at `t+1`.
- Equity curve uses corrected net returns.
- Standard Sharpe: mean monthly excess ×12 / (std × sqrt12); rf=0 disclosed.
- SPY 8/10/12 windows all use the same next-month execution.

## Tests added

`tests/test_spy_timing.py` calls the real timing functions on synthetic series:

1. signal cannot affect same-month return;
2. exit starts next month;
3. entry starts next month;
4. cost charged on switch month;
5. equity equals cumprod net returns;
6. Sharpe uses mean, not CAGR;
7. no cost when no switch.

## Results

- SPY_TREND full CAGR 8.23%, MaxDD -23.43%, Sharpe 0.78.
- OOS 9.40%, MaxDD -23.43%.
- 20 bps full 8.05%.
- 8m full 10.32%, DD -23.43%; 12m full 8.74%, DD -16.89%.
- No window meets 15% DD.

## Data limits

- 987 static symbols; delisted not verified -> survivorship.
- No PIT fundamentals; Route C unavailable.
- No taxes/slippage; monthly close.
- Zero risk-free simplification.
- No PAPER-50000, no orders.
