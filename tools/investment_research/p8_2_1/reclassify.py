"""P8.2.1 revised anomaly classification (no zero-volume == corruption)."""
from __future__ import annotations
import csv, json
from collections import Counter
from pathlib import Path

P82=Path("data/research/p8_2"); OUT=Path("data/research/p8_2_1"); OUT.mkdir(parents=True,exist_ok=True)


def main():
    rows=[]
    with (P82/"ticker_anomaly_audit.csv").open(encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            t=r["ticker"]; vol=float(r["volume"] or 0); prev_vol=None
            # previous volume is not in the row; zero current volume is enough to flag stale, not corruption
            if t in ("CBE","ACS"):
                cls="VERIFIED_CORRUPT"; evidence="alternating adjusted price basis / symbol identity transition"
            elif t=="GME":
                cls="VERIFIED_REAL_RETURN"; evidence="GME 2021 short squeeze; true market move"
            elif vol==0:
                cls="ZERO_VOLUME_OR_STALE"; evidence="zero current volume; stale/suspended session, not proven price corruption"
            else:
                cls="UNRESOLVED"; evidence="large adjusted move without verified split/identity source"
            rows.append({**r,"classification":cls,"evidence":evidence})
    with (OUT/"ticker_anomaly_audit.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    counts=dict(Counter(r["classification"] for r in rows))
    summary={"generated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
             "rows":len(rows),"tickers":len({r["ticker"] for r in rows}),"counts":counts,
             "policy":"zero volume is ZERO_VOLUME_OR_STALE, not automatically corrupt; only CBE/ACS have verified corruption evidence in this pass.",
             "special":{t:[r for r in rows if r["ticker"]==t][:3] for t in ("CBE","ACS","GME")}}
    (OUT/"anomaly_classification.json").write_text(json.dumps(summary,indent=2,default=str),encoding="utf-8")
    print(json.dumps({"counts":counts,"rows":len(rows)},indent=2))


if __name__=="__main__":raise SystemExit(main())
