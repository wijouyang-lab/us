# F Pre-registration: VIX/VXV Backwardation Filter

Frozen before F was run.

Universe: SPY, IEF, TLT, BIL. $50,000, long-only, no leverage.

Signal: `VIXCLS > VXVCLS`.

Allocation:

- backwardation: BIL 100%;
- otherwise: SPY 70%, IEF 15%, TLT 15%;
- missing/invalid pair: BIL 100%.

Monthly at the last SPY session. Both VIX and VXV must come from the same ALFRED
vintage, dated no later than the prior complete SPY session; next session raw
Open execution. No VIX level filter, no other window, no optimizer.

PIT starts when both series have common ALFRED vintages (2014). VXV 2007-2014 is
exploratory only. 5 bps/leg base; 1/3/5/10/20 bps sensitivity.

Evaluation: positive excess after costs, HAC/BH support vs BIL, maximum drawdown
<= 15%, no single-stage dependence, enough trades/exposure, PIT reliability and
reproducible accounting. Any failure = NO-GO; no parameter rescue.
