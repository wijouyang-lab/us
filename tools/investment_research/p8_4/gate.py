"""P8.4 unified BH gate and status."""
from __future__ import annotations
import csv,json,math
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

O=Path("data/research/p8_4_market_neutral_alpha")


def main():
    ic=pd.read_csv(O/"factor_ic_results.csv"); fm=pd.read_csv(O/"factor_fama_macbeth.csv"); reg=pd.read_csv(O/"factor_regime_results.csv"); rob=pd.read_csv(O/"factor_robustness.csv")
    tests=[]
    for r in ic.itertuples():tests.append({"test":f"{r.factor}|H{r.horizon}","kind":"UNCONDITIONAL","factor":r.factor,"horizon":r.horizon,"ic":r.mean_ic,"t":r.hac_t,"p":r.p_value,"mean_fm":None})
    for r in reg.itertuples():tests.append({"test":f"{r.factor}|{r.condition}|{r.regime}|H{r.horizon}","kind":"REGIME","factor":r.factor,"horizon":r.horizon,"ic":r.mean_ic,"t":r.hac_t,"p":r.p_value,"mean_fm":None})
    for r in fm.itertuples():tests.append({"test":f"{r.factor}|FM|H{r.horizon}","kind":"FAMA_MACBETH","factor":r.factor,"horizon":r.horizon,"ic":r.mean_fm_coef,"t":r.fm_t,"p":r.p_value,"mean_fm":r.mean_fm_coef})
    tests.sort(key=lambda x:(x["p"] is None, x["p"] or 1)); qs=[]
    for rank,t in enumerate(tests,1):qs.append((t,min(1.0,(t["p"] or 1)*len(tests)/rank)))
    for t,q in qs:t["bh_q"]=q
    pd.DataFrame(tests).to_csv(O/"factor_bh_results.csv",index=False)
    pd.DataFrame([{"test":t["test"],"kind":t["kind"],"factor":t["factor"],"horizon":t["horizon"],"ic":t["ic"],"hac_t":t["t"],"p_value":t["p"],"bh_q_all":t["bh_q"]} for t in tests]).to_csv(O/"factor_hac_results.csv",index=False)
    # Regime q merged
    fm=fm.copy();fm["bh_q_all"]=[next((t["bh_q"] for t in tests if t["kind"]=="FAMA_MACBETH" and t["factor"]==r.factor and t["horizon"]==r.horizon),None) for r in fm.itertuples()];fm.to_csv(O/"factor_fama_macbeth.csv",index=False)
    reg=reg.copy();qmap={t["test"]:t["bh_q"] for t in tests if t["kind"]=="REGIME"}
    reg["bh_q_all"]=[qmap.get(f"{r.factor}|{r.condition}|{r.regime}|H{r.horizon}") for r in reg.itertuples()]
    reg.to_csv(O/"factor_regime_results.csv",index=False)
    # Candidates: positive IC, t>=1.64, q<=0.10, sign stable.
    robmap={(r.factor,int(r.horizon)):bool(r.sign_stable) for r in rob.itertuples()}
    cand=[]
    for r in ic.itertuples():
        q=next((t["bh_q"] for t in tests if t["kind"]=="UNCONDITIONAL" and t["factor"]==r.factor and t["horizon"]==r.horizon),None)
        if r.mean_ic>0 and (r.hac_t or 0)>=1.64 and q is not None and q<=0.10 and robmap.get((r.factor,int(r.horizon))):
            cand.append({"factor":r.factor,"horizon":r.horizon,"mean_ic":r.mean_ic,"hac_t":r.hac_t,"bh_q":q})
    pd.DataFrame(cand).to_csv(O/"strategy_candidates.csv",index=False)
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P8_4_NO_GO" if not cand else "P8_4_RESEARCH_CANDIDATE",
            "as_of":"2024-12-31","factors":len(ic.factor.unique()),"unconditional_tests":len(ic),"regime_tests":len(reg),"bh_family":len(tests),
            "go_count":len(cand),"candidates":cand,"data_blocked":["NDX/DJI history","historical fundamental PIT","event/macro PIT","2025-2026 panel"],
            "limits":["2000-2024 has been observed before; results are not pristine independent confirmation","No P8 shadow","No short/leverage/options"],"no_shadow":True}
    (O/"p8_4_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps({"status":status["status"],"bh_family":len(tests),"go":len(cand),"top":[{k:t[k] for k in ("test","ic","t","p","bh_q")} for t in tests[:8]]},indent=2))


if __name__=="__main__":raise SystemExit(main())
