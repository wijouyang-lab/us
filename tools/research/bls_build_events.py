import json
from pathlib import Path

import pandas as pd

out = Path("data/research/macro_cross_sectional")
p = pd.read_csv(out / "alfred_initial_values.csv")
p["ref"] = pd.PeriodIndex(p.reference_period, freq="M")
p["yoy_prior_ref"] = (p.ref - 12).astype(str)
# Same-vintage year-ago value captured by the recovery step.
p["yoy"] = p.initial_value / p.prior_year_value_same_vintage - 1
p["mom"] = p.initial_value / p.prior_value_same_vintage - 1
p["change"] = p.initial_value - p.prior_value_same_vintage

events = []
manifest = json.loads((out / "bls_source_manifest.json").read_text())
for fam, group in (("cpi", p[p.series.isin(["cpi_headline_sa", "cpi_core_sa"])]),
                   ("employment", p[p.series.isin(["payrolls_sa", "unemployment_sa", "earnings_sa"])])):
    for d, g in group.groupby("release_date"):
        latest = g.sort_values("ref").iloc[-1]
        row = {"event_id": f"{fam}_{d}", "event_type": fam,
               "reference_period": latest.reference_period,
               "release_date": d, "embargo_time_local": "", "timezone": "America/New_York",
               "timestamp_precision": "date_only", "timestamp_confidence": "none",
               "scheduled_release_time": "", "actual_publication_time": "",
               "collector_first_seen_at": "", "source_url": "https://alfred.stlouisfed.org/",
               "source_filename": "ALFRED vintage download", "source_sha256": "",
               "release_number": "", "initial_headline_value": "", "initial_core_value": "",
               "initial_payroll_change": "", "initial_unemployment_rate": "",
               "initial_earnings_mom": "", "initial_earnings_yoy": "",
               "prior_value_as_reported": "", "prior_value_before_release": "",
               "revision_status": "INITIAL_VINTAGE_ONLY", "reissue_or_errata_status": "",
               "data_quality_status": "ALFRED_VINTAGE_DATE_ONLY"}
        if fam == "cpi":
            h = g[g.series == "cpi_headline_sa"]
            c = g[g.series == "cpi_core_sa"]
            if len(h):
                hr = h.sort_values("ref").iloc[-1]
                row["initial_headline_value"] = round(float(hr.mom) * 100, 3)
                row["headline_yoy"] = round(float(hr.yoy) * 100, 3) if pd.notna(hr.yoy) else ""
                row["source_sha256"] = manifest["series"]["CPIAUCSL"]["zip_sha256"]
            if len(c):
                cr = c.sort_values("ref").iloc[-1]
                row["initial_core_value"] = round(float(cr.mom) * 100, 3)
                row["core_yoy"] = round(float(cr.yoy) * 100, 3) if pd.notna(cr.yoy) else ""
        else:
            pay = g[g.series == "payrolls_sa"]
            une = g[g.series == "unemployment_sa"]
            earn = g[g.series == "earnings_sa"]
            if len(pay):
                pr = pay.sort_values("ref").iloc[-1]
                row["initial_payroll_change"] = round(float(pr.change), 1)
                row["source_sha256"] = manifest["series"]["PAYEMS"]["zip_sha256"]
            if len(une):
                row["initial_unemployment_rate"] = float(une.sort_values("ref").iloc[-1].initial_value)
            if len(earn):
                er = earn.sort_values("ref").iloc[-1]
                row["initial_earnings_mom"] = round(float(er.mom) * 100, 3)
                row["initial_earnings_yoy"] = round(float(er.yoy) * 100, 3) if pd.notna(er.yoy) else ""
        events.append(row)
ev = pd.DataFrame(events).sort_values(["release_date", "event_type"])
ev = ev[ev.release_date >= "2007-01-01"]
ev.to_csv(out / "bls_macro_events.csv", index=False)
manifest.update({"events": len(ev), "cpi_events": int((ev.event_type == "cpi").sum()),
                 "employment_events": int((ev.event_type == "employment").sum()),
                 "exact_embargo_time_events": 0,
                 "initial_cpi_coverage": float(ev[ev.event_type == "cpi"].initial_headline_value.notna().mean()),
                 "initial_payroll_coverage": float(ev[ev.event_type == "employment"].initial_payroll_change.notna().mean())})
(out / "bls_source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(ev.groupby("event_type").size().to_dict(), len(ev))
print(ev[ev.event_type == "cpi"].tail(3).to_string(index=False))
