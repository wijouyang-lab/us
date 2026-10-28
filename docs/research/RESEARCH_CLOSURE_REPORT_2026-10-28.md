# Research Closure and Data-Readiness Gates

Date: 2026-10-28
Baseline: PR #399 `28060f24d907f0b0b75a323a6314084222a1077a`
Research only. No production changes.

## Frozen conclusion

Within the tested 466-ticker, current-universe, survivorship-biased panel:

- **No reliable alpha.**
- **No deployable strategy.**
- **No qualified paper-trading candidate.**
- 399-formula best positive: 3.1839% net, q=0.06687; still not significant.

This is a conclusion about the tested sample, **not proof that all future
low-frequency strategies are impossible**.

## Reopen gates

| Gate | Owner role | Verification | Current | Status |
|---|---|---|---|---|
| PIT universe + delisted OHLCV | research data owner (human) | PIT coverage + recovery gate | 91.61% member, 84.23% ticker, 0/98 delisted | **fail** |
| Independent adjusted prices/actions | research data owner (human) | independent adjusted source + action audit | 466 raw; SPY provider-only | **fail** |
| Qlib raw period results | strategy research owner (human) | committed per-period JSON + rerun | audit doc only | **fail** |
| Event pre-registered sample | event research owner (human) | `event_experiment_gate.py` | 35 events, 0 entry/+1/+5 | **not_eligible** |
| 10/28 official close | research operations owner (human) | provider close + updater | latest 10/27 | **pending** |
| Second real cross-day capture | research operations owner (human) | workflow + archive verify | 1 run on 10/28 | **pending** |

Machine-readable:

`docs/research/RESEARCH_CLOSURE_DATA_READINESS_2026-10-28.json`

## Important distinctions

- **Data not ready 鈮?strategy proven impossible.**
- **Qlib audit not independently rerun** 鈥?values are taken from the committed
  audit document; raw per-period JSON is missing.
- Event 35/0/0/0 is a sample/gate failure, not an event alpha finding.
- 10/28 close and second cross-day capture are pending; no simulation or replay
  is counted as real data.

## Evidence links

- Final conclusion PR #399: https://github.com/wijouyang-lab/us/pull/399
- Final acceptance audit: `docs/research/FINAL_ACCEPTANCE_AUDIT_2026-10-28.md`
- 466 validation: https://github.com/wijouyang-lab/us/pull/392
- Qlib audit: https://github.com/wijouyang-lab/us/pull/389
- Data coverage: https://github.com/wijouyang-lab/us/pull/390
- Event research: https://github.com/wijouyang-lab/us/pull/397
- First real event run: https://github.com/wijouyang-lab/us/actions/runs/40661139681

## Research stop rule

Do not start another factor/model/parameter search on the same 466 sample.
Reopen only after the data gates above are satisfied and a new hypothesis is
pre-registered.

## Protection

PR #397, #398, #399 and this closure PR remain Draft. No auto-merge. Production
scanner, scoring, stops, ledger, order path, and external triggers unchanged.
