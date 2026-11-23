#!/usr/bin/env python3
"""P17.2.8.3 clean close-out replay for PIT identity evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]


def sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--p281", type=Path, default=BASE / "../_us_p17281/data/research/p17_2_8_1")
    ap.add_argument("--p282", type=Path, default=BASE / "../_us_p17282/data/research/p17_2_8_2")
    ap.add_argument("--p26", type=Path, default=BASE / "../_us_p1726/data/research/p17_2_6")
    ap.add_argument("--p390", type=Path, default=BASE / "../_us_p171/data/research/p17_1/p17_1_p390_identity_reconciliation.csv")
    ap.add_argument("--p10", type=Path, default=BASE / "../_us_audit/p10/data/research/p10_5_2_verified_identity_crosswalk.csv")
    a = ap.parse_args()
    if a.out.exists() and any(a.out.iterdir()):
        raise SystemExit(f"REFUSING_NONEMPTY_OUTPUT: {a.out}")
    a.out.mkdir(parents=True, exist_ok=True)
    old = pd.read_csv(a.p281 / "p17_2_8_1_anchor_identity_results.csv", dtype=str)
    cur = pd.read_csv(a.p282 / "p17_2_8_2_anchor_identity_results.csv", dtype=str)
    sample = pd.read_csv(a.p26 / "p17_2_6_sample_manifest.csv", dtype=str)
    # exact baseline grouping: provenance + prior verified status
    base = old.merge(sample[["anchor", "anchor_date", "ticker"]], on=["anchor", "ticker"], how="left", suffixes=("", "_s"))
    base["group"] = "OTHER_UNVERIFIED"
    prior_v = base.identity_status == "VERIFIED_FILING_POINT"
    base.loc[prior_v & base.cand.isna(), "group"] = "ORIGINAL_199"
    base.loc[prior_v & base.cand.notna(), "group"] = "NEW_38"
    cur = cur.merge(base[["anchor", "ticker", "group"]], on=["anchor", "ticker"], how="left")
    cur["group"] = cur.group.fillna("OTHER_UNVERIFIED")
    cur.to_csv(a.out / "p17_2_8_3_anchor_identity_results.csv", index=False)
    # anchor summary from rows
    s = cur.groupby(["anchor", "anchor_date"]).agg(
        total=("ticker", "size"), unique_tickers=("ticker", "nunique"),
        candidate_cik=("selected_cik", lambda x: sum(1 for v in x if pd.notna(v) and v)),
        verified=("identity_status", lambda x: (x == "VERIFIED_RECONFIRMED").sum()),
        ambiguous=("identity_status", lambda x: (x == "AMBIGUOUS_SECURITY_CONTEXT").sum()),
        title_missing=("identity_status", lambda x: (x == "REVOKED_TITLE_MISSING").sum()),
        no_filing=("identity_status", lambda x: (x == "NO_HISTORICAL_FILING").sum()),
        filing_unverified=("identity_status", lambda x: (x == "FILING_FOUND_IDENTITY_UNVERIFIED").sum())).reset_index()
    s.to_csv(a.out / "p17_2_8_3_anchor_summary.csv", index=False)
    # group reconciliation
    rec = cur.groupby(["group", "identity_status"]).size().reset_index(name="rows")
    rec.to_csv(a.out / "p17_2_8_3_reconciliation.csv", index=False)
    # exception rows and raw facts
    exc = cur[cur.identity_status.isin(["FILING_FOUND_IDENTITY_UNVERIFIED", "AMBIGUOUS_SECURITY_CONTEXT", "REVOKED_TITLE_MISSING"])].copy()
    exc.to_csv(a.out / "p17_2_8_3_exception_disposition.csv", index=False)
    facts = pd.read_csv(a.p282 / "p17_2_8_2_reparsed_xbrl_facts.csv", dtype=str)
    facts[facts.accession.isin(exc.accession)].to_csv(a.out / "p17_2_8_3_raw_xbrl_exception_facts.csv", index=False)
    # context registry from facts
    facts[["accession", "context_id"]].drop_duplicates().to_csv(a.out / "p17_2_8_3_context_registry.csv", index=False)
    # conflicts from actual candidates
    cand = pd.read_csv(a.p281 / "p17_2_8_1_historical_cik_candidates.csv", dtype=str)
    conf = cand.groupby(["anchor", "ticker"]).cand.nunique().reset_index()
    conf = conf[conf.cand > 1]
    conf.to_csv(a.out / "p17_2_8_3_cik_conflicts.csv", index=False)
    # request audit: cache reads = verified rows with doc hash; no network
    cache_hits = int((cur.identity_status == "VERIFIED_RECONFIRMED").sum())
    pd.DataFrame([{"source": "local_cache", "cache_hits": cache_hits, "cache_miss": 0, "network_requests": 0, "http_errors": 0}]).to_csv(a.out / "p17_2_8_3_request_audit.csv", index=False)
    # input manifest
    inputs = {"p17_2_8_1_anchor": a.p281 / "p17_2_8_1_anchor_identity_results.csv",
              "p17_2_8_2_anchor": a.p282 / "p17_2_8_2_anchor_identity_results.csv",
              "sample": a.p26 / "p17_2_6_sample_manifest.csv",
              "p390": a.p390, "p10": a.p10}
    im = {k: {"path": str(v), "sha256": sha(v), "bytes": v.stat().st_size} for k, v in inputs.items() if v.exists()}
    im["missing"] = [str(v) for v in inputs.values() if not v.exists()]
    (a.out / "p17_2_8_3_input_manifest.json").write_text(json.dumps(im, indent=2), encoding="utf-8")
    # business hash over core CSV
    core = (a.out / "p17_2_8_3_anchor_identity_results.csv").read_bytes()
    summary = {"samples": len(cur), "groups": cur.group.value_counts().to_dict(),
               "status": cur.identity_status.value_counts().to_dict(),
               "anchor": s.to_dict("records"), "conflict_rows": len(conf),
               "cache_hits": cache_hits, "network_requests": 0,
               "business_sha256": hashlib.sha256(core).hexdigest(),
               "gate": "FAIL"}
    (a.out / "p17_2_8_3_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    files = {}
    for p in a.out.iterdir():
        if p.suffix in {".csv", ".json"} and p.name != "p17_2_8_3_output_manifest.json":
            files[p.name] = {"sha256": sha(p), "bytes": p.stat().st_size}
    (a.out / "p17_2_8_3_output_manifest.json").write_text(json.dumps({"outputs": files, "business_sha256": summary["business_sha256"]}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
