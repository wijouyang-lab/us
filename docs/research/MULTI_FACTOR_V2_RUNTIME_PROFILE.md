# V2 Runtime Profile

The first daily engine used per-day pandas `.loc` and repeated DataFrame copies;
it exceeded 10 minutes for 5Y A alone and was abandoned.

The final engine precomputes date x ticker matrices for Price, ATR, MA50 and
A/B/C scores, ranks once, and uses NumPy row arrays in the daily loop. It
completed all 5Y/3Y/1Y strategy runs, 7 exit variants and 3 cost scenarios
within one command execution.

No exact wall-clock timing was recorded; this is a design/profile description,
not a benchmark claim. The completed outputs are the evidence that the run
finished.
