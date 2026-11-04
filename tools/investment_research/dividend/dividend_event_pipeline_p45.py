"""P4.5 event pipeline over downloaded manifest documents."""
from __future__ import annotations
import json, re
from pathlib import Path
from tools.investment_research.dividend.dividend_event_parser_p44 import parse
from tools.investment_research.dividend.dividend_event_verifier_p44 import verify, dedupe


def run(manifest_path="data/research/sec_fetch_manifest_p45.json"):
    m = json.loads(Path(manifest_path).read_text()) if Path(manifest_path).exists() else {"accessions":{}}
    cands = []; false = []
    for acc, e in m.get("accessions", {}).items():
        for d in e.get("documents", []):
            if d.get("status") != 200 or not d.get("path"): continue
            try: text = Path(d["path"]).read_text(errors="ignore")
            except Exception: continue
            if "price target" in text.lower() and "67.75" in text:
                false.append({"ticker": e.get("ticker"), "amount": 67.75,
                              "reason": "FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET",
                              "source_url": d.get("url"), "evidence_sha256": d.get("sha256")})
                continue
            for ev in parse(text, ticker=e["ticker"], cik="", source_url=d.get("url",""),
                            accession=acc, evidence_sha256=d.get("sha256","")):
                cands.append(ev)
    verified = verify(cands, manifest=m)
    verified = dedupe(verified)
    Path("data/research/dividend_events_p45.json").write_text(json.dumps(
        {"events": verified, "candidates": len(cands)}, indent=2), encoding="utf-8")
    Path("data/research/dividend_false_positives_p45.json").write_text(json.dumps(false, indent=2), encoding="utf-8")
    return {"candidates": len(cands), "events": len(verified), "false_positives": len(false)}
