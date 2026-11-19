import json
from pathlib import Path

import pandas as pd

out = Path("data/research/macro_cross_sectional")
new = pd.read_csv(out / "bls_macro_events.csv")
old = pd.read_csv("data/research/macro_event_response/events.csv")
old = old[old.event_type.isin(["cpi", "empsit"])]
new_cpi = new[new.event_type == "cpi"]
new_emp = new[new.event_type == "employment"]
old_cpi = old[old.event_type == "cpi"]
old_emp = old[old.event_type == "empsit"]
audit = {
    "status": "PARTIAL",
    "bls_live": {"cpi": 403, "empsit": 403},
    "source": "ALFRED vintage download; BLS live HTML/PDF blocked",
    "cpi": {
        "events": len(new_cpi), "years": sorted(new_cpi.release_date.str[:4].unique().tolist()),
        "exact_embargo_time": int(new_cpi.embargo_time_local.notna().sum()),
        "initial_headline_mom": int(new_cpi.initial_headline_value.notna().sum()),
        "initial_core_mom": int(new_cpi.initial_core_value.notna().sum()),
        "missing_years": [],
    },
    "employment": {
        "events": len(new_emp), "years": sorted(new_emp.release_date.str[:4].unique().tolist()),
        "exact_embargo_time": int(new_emp.embargo_time_local.notna().sum()),
        "initial_payroll_change": int(new_emp.initial_payroll_change.notna().sum()),
        "initial_unemployment": int(new_emp.initial_unemployment_rate.notna().sum()),
        "initial_earnings_mom": int(new_emp.initial_earnings_mom.notna().sum()),
        "missing_years": [],
    },
    "coverage": {
        "cpi_years": int(new_cpi.release_date.str[:4].nunique()),
        "employment_years": int(new_emp.release_date.str[:4].nunique()),
        "cpi_exact_time_rate": 0.0,
        "employment_exact_time_rate": 0.0,
        "cpi_initial_rate": float(new_cpi.initial_headline_value.notna().mean()),
        "employment_payroll_initial_rate": float(new_emp.initial_payroll_change.notna().mean()),
    },
    "special_2025_2026": {
        "cpi_2025_10_missing": True,
        "employment_2025_10_missing": True,
        "employment_2025_09_released": "2025-11-20",
        "cpi_2025_09_released": "2025-10-24",
        "note": "ALFRED vintage dates show delayed releases; no synthetic fill.",
    },
    "reconciliation": {
        "old_cpi": len(old_cpi), "new_cpi": len(new_cpi),
        "old_employment": len(old_emp), "new_employment": len(new_emp),
        "added_cpi": len(new_cpi) - len(old_cpi),
        "added_employment": len(new_emp) - len(old_emp),
        "old_date_range": [str(old.publication_date.min()), str(old.publication_date.max())],
        "new_date_range": [str(new.release_date.min()), str(new.release_date.max())],
    },
    "market_consensus": {
        "status": "DATA_BLOCKED",
        "reason": "No free, auditable pre-release historical consensus snapshot with timestamps.",
    },
}
(out / "bls_event_coverage_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
(out / "alfred_vintage_audit.json").write_text(json.dumps({
    "series": json.loads((out / "bls_source_manifest.json").read_text())["series"],
    "initial_selection": "first non-null vintage per observation",
    "timestamp_policy": "vintage date only; no embargo inference",
}, indent=2), encoding="utf-8")
print(json.dumps(audit, indent=2))
