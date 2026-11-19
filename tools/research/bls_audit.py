import json
from pathlib import Path

import pandas as pd

out = Path("data/research/macro_cross_sectional")
new = pd.read_csv(out / "bls_macro_events.csv")
old = pd.read_csv("data/research/macro_event_response/events.csv")
old = old[old.event_type.isin(["cpi", "empsit"])]
old["family"] = old.event_type.map({"cpi": "cpi", "empsit": "employment"})
new["year"] = new.release_date.str[:4]
old["year"] = old.publication_date.str[:4]
old_keys = set(zip(old.family, old.publication_date))
new_keys = set(zip(new.event_type, new.release_date))
matched = sorted(old_keys & new_keys)
missing = sorted(old_keys - new_keys)
newly = sorted(new_keys - old_keys)
dups = new[new.duplicated(["event_type", "release_date"], keep=False)]
date_mismatch = []
ref_mismatch = []
for fam in ("cpi", "employment"):
    for y in sorted(new[new.event_type == fam].year.unique()):
        refs = new[(new.event_type == fam) & (new.year == y)].reference_period
        if len(refs) == 0 or len(set(refs)) != len(refs):
            ref_mismatch.append(f"{fam}:{y}:duplicate_reference_period")
audit = {
    "status": "PARTIAL",
    "bls_live": {"cpi": 403, "empsit": 403},
    "source": "ALFRED vintage download; BLS live HTML/PDF blocked",
    "cpi": {"events": int((new.event_type == "cpi").sum()), "years": sorted(new[new.event_type == "cpi"].year.unique().tolist()),
            "exact_embargo_time": 0, "initial_headline_mom": int(new[new.event_type == "cpi"].initial_headline_value.notna().sum()),
            "initial_core_mom": int(new[new.event_type == "cpi"].initial_core_value.notna().sum())},
    "employment": {"events": int((new.event_type == "employment").sum()), "years": sorted(new[new.event_type == "employment"].year.unique().tolist()),
                   "exact_embargo_time": 0, "initial_payroll_change": int(new[new.event_type == "employment"].initial_payroll_change.notna().sum()),
                   "initial_unemployment": int(new[new.event_type == "employment"].initial_unemployment_rate.notna().sum()),
                   "initial_earnings_mom": int(new[new.event_type == "employment"].initial_earnings_mom.notna().sum())},
    "coverage": {
        "cpi_years": int(new[new.event_type == "cpi"].year.nunique()),
        "employment_years": int(new[new.event_type == "employment"].year.nunique()),
        "cpi_exact_time_rate": 0.0, "employment_exact_time_rate": 0.0,
        "cpi_initial_rate": float(new[new.event_type == "cpi"].initial_headline_value.notna().mean()),
        "employment_payroll_initial_rate": float(new[new.event_type == "employment"].initial_payroll_change.notna().mean()),
        "cpi_per_year": new[new.event_type == "cpi"].groupby("year").size().to_dict(),
        "employment_per_year": new[new.event_type == "employment"].groupby("year").size().to_dict(),
    },
    "special_2025_2026": {
        "cpi_2025_10_missing": bool("cpi_2025-10" not in set(new.event_id)),
        "employment_2025_10_missing": bool("employment_2025-10" not in set(new.event_id)),
        "employment_2025_09_released": "2025-11-20",
        "cpi_2025_09_released": "2025-10-24",
        "note": "ALFRED vintage dates show delayed/missing releases; no synthetic fill.",
    },
    "reconciliation": {
        "old_cpi": int((old.family == "cpi").sum()), "new_cpi": int((new.event_type == "cpi").sum()),
        "old_employment": int((old.family == "employment").sum()), "new_employment": int((new.event_type == "employment").sum()),
        "matched_old_events": len(matched), "missing_from_new": missing,
        "newly_recovered_events": len(newly), "duplicate_events": int(len(dups)),
        "date_mismatches": date_mismatch, "reference_period_mismatches": ref_mismatch,
    },
    "market_consensus": {"status": "DATA_BLOCKED", "reason": "No free auditable pre-release consensus snapshots."},
}
(out / "bls_event_coverage_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
(out / "alfred_vintage_audit.json").write_text(json.dumps({
    "series": json.loads((out / "bls_source_manifest.json").read_text())["series"],
    "initial_selection": "first non-null vintage per observation; prior month/year same vintage",
    "timestamp_policy": "vintage date only; no embargo inference"}, indent=2), encoding="utf-8")
print(json.dumps(audit, indent=2))
