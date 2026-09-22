# US V23 Data / Risk Fix

1. America/New_York timezone instead of fixed UTC-4.
2. Scan exits outside 04:00-09:29 ET; no fake premarket N/A snapshot.
3. Premarket status explicitly distinguishes not started / active / ended.
4. Raw regular-session close is used for technical/price display; adjusted close is not shown as yesterday close.
5. Review STOP_TRIGGERED is read from stopped rows, not only Active rows.
6. Tag is no longer trusted for stop-loss warning; Status/Review_Risk_Status are used.
7. Final Scan recheck blocks yesterday exited/restricted tickers before pending and Option generation.
8. Scan workflow scheduled at 09:30 UTC; Review workflow at 22:30 UTC. Manual dispatch outside the premarket window is safely blocked by scan.py.
