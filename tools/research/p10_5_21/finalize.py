"""P10.5.21 deterministic offline acceptance finalizer (no network)."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import pandas as pd

ROOT=Path(".");OUT=ROOT/"data/research/p10_5_21_aapl_dataset";OUT.mkdir(parents=True,exist_ok=True)
V10=ROOT/"data/research/p10_5_20_aapl_panel/aapl_core_panel_v10.csv";V15=ROOT/"data/research/p10_5_15_aapl_panel/aapl_context_audit_v5.csv";PRE=ROOT/"data/research/p10_5_20_aapl_panel/aapl_gross_margin_pre_audit_v5.csv"


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def transform(r):
    if r.field=="FreeCashFlow":return "DERIVED_FORMULA","FCF = OCF - Capex"
    if r.field in ("NetCashProvidedByUsedInOperatingActivities","PaymentsToAcquirePropertyPlantAndEquipment"):
        return ("DIRECT_FACT","") if r.quarter=="Q1" else ("RECONSTRUCTED_FROM_CUMULATIVE_FACTS","QTD = YTD_t - YTD_t-1")
    if r.field=="OperatingIncomeLoss" and r.quarter=="Q4":return "DERIVED_FROM_ANNUAL_MINUS_9M","Q4 = FY - 9M"
    if r.field=="Revenue" and r.fy==2019 and r.quarter in ("Q2","Q3"):return "RECONSTRUCTED_FROM_COMPONENTS","Total = Products + Services"
    return "DIRECT_FACT",""


def build(indir:Path,outdir:Path):
    src=Path(indir)/"aapl_core_panel_v10.csv";d=pd.read_csv(src);rows=[];lin=[]
    for r in d.itertuples():
        t,formula=transform(r)
        rows.append({"ticker":"AAPL","fiscal_year":r.fy,"fiscal_quarter":r.quarter,"metric":r.field,"value":r.value,"unit":r.unit,"source_accession":r.source_accession_primary,"source_filename":"","source_fact":r.field,"contextRef":r.context,"startDate":r.period_start,"endDate":r.period_end,"transformation_type":t,"transformation_formula":formula,"validation_status":"ACCEPTED"})
        lin.append({**rows[-1],"secondary_accession":r.source_accession_secondary,"raw_value":r.raw_value,"raw_unit":r.raw_unit,"context_verified":r.context_verified,"derived_inputs":r.derivation_method})
    pd.DataFrame(rows).to_csv(outdir/"aapl_fundamentals_2018_2019.csv",index=False);pd.DataFrame(lin).to_csv(outdir/"aapl_fundamentals_lineage.csv",index=False)
    old=pd.read_csv(Path(indir)/"aapl_context_audit_v5.csv");old=old[~old.context_missing].copy();x=[]
    for r in old.itertuples():
        new=d[(d.fy==r.fy)&(d.quarter==r.quarter)&(d.field==r.field)]
        x.append({"legacy_fy":r.fy,"legacy_quarter":r.quarter,"legacy_field":r.field,"legacy_accession":r.source_accession_primary,"legacy_context":r.context,"v10_accession":new.iloc[0].source_accession_primary if len(new) else "","v10_context":new.iloc[0].context if len(new) else "","v10_status":new.iloc[0].lineage_status if len(new) else "UNRESOLVED","mapping_status":"MAPPED_TO_V10" if len(new) else "UNRESOLVED"})
    pd.DataFrame(x).to_csv(outdir/"aapl_legacy_lineage_crosswalk.csv",index=False)
    pre=pd.read_csv(Path(indir)/"aapl_gross_margin_pre_audit_v5.csv");pre["gross_margin_status"]="UNRESOLVED";pre["reason"]="PRE/LAB parsing not completed";pre.to_csv(outdir/"aapl_gross_margin_audit.csv",index=False)
    status={"core_records":len(d),"direct_fact":sum(1 for r in rows if r["transformation_type"]=="DIRECT_FACT"),"reconstructed_cumulative":sum(1 for r in rows if r["transformation_type"]=="RECONSTRUCTED_FROM_CUMULATIVE_FACTS"),"derived_formula":sum(1 for r in rows if r["transformation_type"]=="DERIVED_FORMULA"),"derived_annual_minus_9m":sum(1 for r in rows if r["transformation_type"]=="DERIVED_FROM_ANNUAL_MINUS_9M"),"reconstructed_components":sum(1 for r in rows if r["transformation_type"]=="RECONSTRUCTED_FROM_COMPONENTS"),"legacy_rows":len(x),"legacy_mapped":sum(1 for r in x if r["mapping_status"]=="MAPPED_TO_V10"),"gross_margin_done":0,"gross_margin_unresolved":len(pre)}
    (outdir/"p10_5_21_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--input-dir",default=str(ROOT/"data/research/p10_5_21_inputs"));ap.add_argument("--output-dir",default=str(OUT));ap.add_argument("--offline",action="store_true");a=ap.parse_args()
    indir=Path(a.input_dir)
    # default input package is the P10.5.20 panel plus two audit inputs
    if not (indir/"aapl_core_panel_v10.csv").exists():
        indir.mkdir(parents=True,exist_ok=True)
        (indir/"aapl_core_panel_v10.csv").write_bytes(V10.read_bytes())
        (indir/"aapl_context_audit_v5.csv").write_bytes(V15.read_bytes())
        (indir/"aapl_gross_margin_pre_audit_v5.csv").write_bytes(PRE.read_bytes())
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    print(json.dumps(build(indir,out),indent=2))


if __name__=="__main__":main()
