"""P8.3 valid-data coverage reports and manifest."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

P=Path("data/research/p8_3_valid_data_alpha")


def main():
    panel=pd.read_parquet(P/"valid_research_panel.parquet")
    panel["date"]=pd.to_datetime(panel.date)
    panel["year"]=panel.date.dt.year
    by_year=panel.groupby(["year","horizon"]).agg(valid=("valid","sum"),labeled=("label","count"),rows=("valid","size")).reset_index()
    by_year["valid_coverage"]=by_year.valid/by_year.rows
    by_year["label_coverage"]=by_year.labeled/by_year.valid.replace(0,float("nan"))
    by_year.to_csv(P/"valid_data_coverage_by_year.csv",index=False)
    by_t=panel.groupby("ticker").agg(rows=("valid","size"),valid=("valid","sum"),labeled=("label","count")).reset_index()
    by_t["valid_coverage"]=by_t.valid/by_t.rows
    by_t["label_coverage"]=by_t.labeled/by_t.valid.replace(0,float("nan"))
    by_t.to_csv(P/"valid_data_coverage_by_ticker.csv",index=False)
    pd.DataFrame([{"sector":"UNKNOWN","status":"DATA_BLOCKED","reason":"No reliable historical sector classification on the PIT panel; not fabricated."}]).to_csv(P/"valid_data_coverage_by_sector.csv",index=False)
    manifest={"generated_at":datetime.now(timezone.utc).isoformat(),"as_of":"2024-12-31",
              "panel":"valid_research_panel.parquet","panel_rows":len(panel),
              "factor_count":len(json.loads((P/"factor_definitions.json").read_text(encoding="utf-8"))),
              "horizons":[5,10,20],
              "valid_member_day_coverage":float(panel.valid.mean()),
              "forward_label_coverage":float(panel.label.notna().mean()),
              "raw_input":"data/research/pit_data/finsaber_prices_raw.csv",
              "membership":"data/research/historical_universe/sp500_daily.csv",
              "note":"Historical signals use formation-time base validity and prior 60-session shock rule; post-hoc P8.2.2 classes are not used."}
    (P/"valid_data_research_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2))


if __name__=="__main__":raise SystemExit(main())
