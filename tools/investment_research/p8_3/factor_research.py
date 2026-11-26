"""P8.3 valid-data alpha research.

Uses only effective-dated S&P membership and raw prices available at the
decision date. Post-hoc P8.2.2 classifications are not used as historical
filters. Forward labels are matched separately and never fed back into signal
eligibility.
"""
from __future__ import annotations
import csv, gzip, json, math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

ROOT = Path(".")
OUT = ROOT / "data/research/p8_3_valid_data_alpha"
OUT.mkdir(parents=True, exist_ok=True)
AS_OF = date(2024, 12, 31)
HORIZONS = (5, 10, 20)


def hac_t(x, lags):
    x = np.asarray([v for v in x if np.isfinite(v)], float); n = len(x)
    if n < 12: return None, None
    mu = x.mean(); e = x - mu; var = float(e @ e / n)
    for lag in range(1, min(lags, n - 1) + 1):
        var += 2 * (1 - lag / (lags + 1)) * float(e[lag:] @ e[:-lag] / n)
    se = math.sqrt(max(var, 0) / n)
    if not se: return None, None
    t = mu / se
    from math import erf, sqrt
    return t, 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))


def factor_defs():
    # name: (window, direction, economic meaning)
    return {
        "MOM_5": (5, 1, "short reversal / momentum"),
        "MOM_20": (20, 1, "one-month momentum"),
        "MOM_60": (60, 1, "quarterly momentum"),
        "MOM_120": (120, 1, "six-month momentum"),
        "MOM_ACCEL_20_120": (120, 1, "short-minus-long momentum acceleration"),
        "MOM_ACCEL_5_20": (20, 1, "very short acceleration"),
        "MOM_VOL_20": (20, 1, "momentum per unit total volatility"),
        "MOM_VOL_60": (60, 1, "quarterly risk-adjusted momentum"),
        "MOM_UPSIDE_20": (20, 1, "momentum divided by upside volatility"),
        "MOM_DOWNSIDE_20": (20, 1, "momentum divided by downside volatility"),
        "MOM_PERSIST_20": (20, 1, "sign persistence of daily returns"),
        "MOM_HIT_60": (60, 1, "fraction of positive days"),
        "VOL_20": (60, -1, "short realized volatility"),
        "VOL_60": (60, -1, "long realized volatility"),
        "VOL_RATIO_5_60": (60, -1, "short/long volatility ratio"),
        "VOL_CHANGE_20": (60, -1, "volatility change"),
        "VOL_OF_VOL_20": (60, -1, "volatility-of-volatility"),
        "DOWNSIDE_VOL_20": (60, -1, "downside semideviation"),
        "UP_DOWN_RATIO_20": (60, 1, "upside/downside volatility"),
        "MAX_DD_60": (60, -1, "rolling drawdown"),
        "PRICE_EFF_20": (20, 1, "net move / path length"),
        "PRICE_EFF_60": (60, 1, "quarterly price efficiency"),
        "RANGE_POS_20": (20, 1, "close position in 20d range"),
        "GAP_5": (5, 1, "average overnight gap"),
        "BREAKOUT_60": (60, 1, "distance from 60d high"),
        "VOLUME_Z_20": (20, 1, "volume surprise"),
        "VOLUME_TREND_20": (60, 1, "short/long volume trend"),
        "PRICE_VOLUME_CORR_20": (20, 1, "return-volume correlation"),
        "UP_VOLUME_RATIO_20": (20, 1, "volume on up days vs down"),
        "VOLUME_PRICE_IMPACT": (20, 1, "price move times volume surprise"),
        "TREND_VOLUME": (60, 1, "trend times volume trend"),
        "REVERSAL_DOWNSIDE_5": (20, 1, "short reversal times downside risk"),
        "EFF_VOLUME": (20, 1, "efficiency times volume surprise"),
    }


def main():
    px = pd.read_csv(ROOT/"data/research/pit_data/finsaber_prices_raw.csv",
                     usecols=["date","symbol","open","high","low","close","adjusted_close","volume"])
    px["date"] = pd.to_datetime(px.date); px["symbol"] = px.symbol.str.upper()
    px = px[(px.date >= "2000-01-03") & (px.date <= "2024-12-31")].copy()
    px["adj_open"] = px.open * px.adjusted_close / px.close
    close = px.pivot_table(index="date", columns="symbol", values="adjusted_close", aggfunc="last").sort_index()
    open_ = px.pivot_table(index="date", columns="symbol", values="adj_open", aggfunc="last").reindex(close.index)
    high = px.pivot_table(index="date", columns="symbol", values="high", aggfunc="last").reindex(close.index)
    low = px.pivot_table(index="date", columns="symbol", values="low", aggfunc="last").reindex(close.index)
    raw_close = px.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").reindex(close.index)
    high = high * (close / raw_close); low = low * (close / raw_close)
    volume = px.pivot_table(index="date", columns="symbol", values="volume", aggfunc="last").reindex(close.index)
    ret = close.pct_change(fill_method=None); jump = ret.abs() > 5.0
    c = close.to_numpy(float); o = open_.to_numpy(float); h = high.to_numpy(float); l = low.to_numpy(float); v = volume.to_numpy(float)
    r = ret.to_numpy(float); j = jump.to_numpy(float)
    cols = list(close.columns); dates = list(close.index.date)
    # valid price/volume at formation; no future information
    base_valid = np.isfinite(c) & (c > 0) & np.isfinite(o) & (o > 0) & np.isfinite(h) & np.isfinite(l) & np.isfinite(v) & (v > 0) & (h >= np.maximum(o,c)) & (l <= np.minimum(o,c))
    # deterministic point-in-time shock filter: any >5x move in the prior 60 sessions
    shock60 = pd.DataFrame(j).rolling(60, min_periods=1).max().to_numpy(bool)
    m = pd.read_csv(ROOT/"data/research/historical_universe/sp500_daily.csv")
    m["date"] = pd.to_datetime(m.date).dt.date; m = m.drop_duplicates("date").sort_values("date")
    member_sets = {row.date: {x.strip().upper() for x in str(row.tickers).split(",") if x.strip()} for row in m.itertuples()}
    # forward labels: next open to open H sessions later; invalid if future shock/missing
    labels = {}
    for H in HORIZONS:
        entry = np.roll(o, -1, axis=0); exitp = np.roll(o, -(H + 1), axis=0)
        lab = exitp / entry - 1
        future_shock = pd.DataFrame(j).rolling(H + 1, min_periods=1).max().shift(-H-1).to_numpy(bool)
        lab[~np.isfinite(lab)] = np.nan
        lab[future_shock] = np.nan
        labels[H] = lab
    # base factors (full panel); computed with past data only
    def roll(a, w, f="mean"):
        return pd.DataFrame(a).rolling(w, min_periods=w).agg(f).to_numpy()
    def rstd(a, w): return pd.DataFrame(a).rolling(w, min_periods=w).std().to_numpy()
    vol20 = rstd(r, 20) * math.sqrt(252); vol60 = rstd(r, 60) * math.sqrt(252)
    up = np.where(r > 0, r, 0.0); down = np.where(r < 0, -r, 0.0)
    upvol = rstd(up, 20) * math.sqrt(252); downvol = rstd(down, 20) * math.sqrt(252)
    mom5 = c / np.roll(c, 5, axis=0) - 1; mom20 = c / np.roll(c, 20, axis=0) - 1
    mom60 = c / np.roll(c, 60, axis=0) - 1; mom120 = c / np.roll(c, 120, axis=0) - 1
    absret = np.abs(r)
    eff20 = np.abs(mom20) / np.maximum(roll(absret, 20, "sum"), 1e-12)
    eff60 = np.abs(mom60) / np.maximum(roll(absret, 60, "sum"), 1e-12)
    high20 = pd.DataFrame(h).rolling(20).max().to_numpy(); low20 = pd.DataFrame(l).rolling(20).min().to_numpy()
    high60 = pd.DataFrame(h).rolling(60).max().to_numpy()
    gap = o / np.roll(c, 1, axis=0) - 1
    volz = (v - roll(v, 20)) / np.maximum(rstd(v, 20), 1e-9)
    voltr = roll(v, 20) / np.maximum(roll(v, 60), 1e-9)
    rvcorr = pd.DataFrame(r).rolling(20).corr(pd.DataFrame(v).pct_change()).to_numpy()
    upv = pd.DataFrame(np.where(r > 0, v, 0)).rolling(20).sum().to_numpy()
    downv = pd.DataFrame(np.where(r < 0, v, 0)).rolling(20).sum().to_numpy()
    dd60 = c / pd.DataFrame(c).rolling(60).max().to_numpy() - 1
    F = {
        "MOM_5": mom5, "MOM_20": mom20, "MOM_60": mom60, "MOM_120": mom120,
        "MOM_ACCEL_20_120": mom20 - mom120, "MOM_ACCEL_5_20": mom5 - mom20,
        "MOM_VOL_20": mom20/np.maximum(vol20,1e-9), "MOM_VOL_60": mom60/np.maximum(vol60,1e-9),
        "MOM_UPSIDE_20": mom20/np.maximum(upvol,1e-9), "MOM_DOWNSIDE_20": mom20/np.maximum(downvol,1e-9),
        "MOM_PERSIST_20": roll(np.sign(r),20), "MOM_HIT_60": roll((r>0).astype(float),60),
        "VOL_20": vol20, "VOL_60": vol60, "VOL_RATIO_5_60": rstd(r,5)/np.maximum(vol60,1e-9),
        "VOL_CHANGE_20": vol20/np.maximum(vol60,1e-9)-1, "VOL_OF_VOL_20": rstd(vol20,20),
        "DOWNSIDE_VOL_20": downvol, "UP_DOWN_RATIO_20": upvol/np.maximum(downvol,1e-9),
        "MAX_DD_60": dd60, "PRICE_EFF_20": eff20, "PRICE_EFF_60": eff60,
        "RANGE_POS_20": (c-low20)/np.maximum(high20-low20,1e-9), "GAP_5": roll(gap,5),
        "BREAKOUT_60": c/np.maximum(high60,1e-9)-1, "VOLUME_Z_20": volz,
        "VOLUME_TREND_20": voltr, "PRICE_VOLUME_CORR_20": rvcorr,
        "UP_VOLUME_RATIO_20": upv/np.maximum(downv,1e-9), "VOLUME_PRICE_IMPACT": mom20*volz,
        "TREND_VOLUME": mom60*voltr, "REVERSAL_DOWNSIDE_5": -mom5*np.maximum(downvol,1e-9),
        "EFF_VOLUME": eff20*volz,
    }
    defs = factor_defs(); assert set(F)==set(defs)
    # create period sample dates (non-overlapping labels) and audit coverage
    sample = {}
    for H in HORIZONS:
        sample[H] = [i for i in range(200, len(dates)-H-2, H) if dates[i] in member_sets]
    label_cov=[]; universe_rows=[]
    for H in HORIZONS:
        for i in sample[H]:
            mem=member_sets[dates[i]]; idx=[ci for ci,t in enumerate(cols) if t in mem]
            valid=idx and [k for k in idx if base_valid[i,k] and not shock60[i,k]]
            mat=[k for k in valid if np.isfinite(labels[H][i,k])]
            label_cov.append({"date":str(dates[i]),"horizon":H,"members":len(mem),"valid":len(valid),"labeled":len(mat),"label_coverage":len(mat)/len(valid) if valid else None})
            universe_rows.append({"date":str(dates[i]),"horizon":H,"members":len(mem),"valid":len(valid),"labeled":len(mat)})
    pd.DataFrame(label_cov).to_csv(OUT/"valid_forward_label_coverage.csv",index=False)
    pd.DataFrame(universe_rows).to_csv(OUT/"valid_research_universe.csv",index=False)
    # IC / quantile per factor-horizon
    ic_rows=[];q_rows=[];cov_rows=[];robust=[];ic_series={}
    for name,f in F.items():
        direction=defs[name][1]; window=defs[name][0]
        for H in HORIZONS:
            ics=[];top=[];bottom=[];spread=[];nums=[]
            for i in sample[H]:
                mem=member_sets[dates[i]]; idx=[k for k,t in enumerate(cols) if t in mem]
                idx=[k for k in idx if base_valid[i,k] and not shock60[i,k] and np.isfinite(f[i,k]) and np.isfinite(labels[H][i,k])]
                if len(idx)<30: continue
                x=f[i,idx]; y=labels[H][i,idx]
                if np.all(x==x[0]) or np.all(y==y[0]): continue
                rx=rankdata(x); ry=rankdata(y); ic=float(np.corrcoef(rx,ry)[0,1])
                if not np.isfinite(ic): continue
                ics.append(ic); nums.append(len(idx))
                order=np.argsort(x); n=len(order); q=max(1,n//5)
                top.append(float(np.mean(y[order[-q:]]))); bottom.append(float(np.mean(y[order[:q]]))); spread.append(top[-1]-bottom[-1])
            if len(ics)<12: cov_rows.append({"factor":name,"horizon":H,"n":len(ics),"status":"INSUFFICIENT"}); continue
            ics=np.array(ics); mean=float(ics.mean()); sd=float(ics.std(ddof=1)); icir=mean/sd*math.sqrt(252/H) if sd else None
            t,p=hac_t(ics, max(1,H//5))
            q10=float(np.mean(np.array(top)-np.array(bottom)))
            # period IC means
            periods={"2000-2007":(date(2000,1,1),date(2007,12,31)),"2008-2015":(date(2008,1,1),date(2015,12,31)),"2016-2024":(date(2016,1,1),date(2024,12,31))}
            per={}
            for pn,(a,b) in periods.items():
                vals=[ic for ic,dt in zip(ics,[dates[i] for i in sample[H]]) if a<=dt<=b] if False else []
            # recompute per-period directly from stored (date,ic)
            # store series
            series=[]
            for i in sample[H]:
                mem=member_sets[dates[i]]; idx=[k for k,t in enumerate(cols) if t in mem]
                idx=[k for k in idx if base_valid[i,k] and not shock60[i,k] and np.isfinite(f[i,k]) and np.isfinite(labels[H][i,k])]
                if len(idx)<30: continue
                x=f[i,idx]; y=labels[H][i,k] if False else labels[H][i,idx]
                if np.all(x==x[0]) or np.all(y==y[0]): continue
                ic=float(np.corrcoef(rankdata(x),rankdata(y))[0,1])
                if np.isfinite(ic): series.append((dates[i],ic))
            ic_series[(name,H)]=series
            for pn,(a,b) in periods.items():
                pv=[v for d,v in series if a<=d<=b]; per[pn]=float(np.mean(pv)) if pv else None
            robust.append({"factor":name,"horizon":H,**per,"sign_stable":len({x>0 for x in per.values() if x is not None})==1})
            ic_rows.append({"factor":name,"horizon":H,"mean_ic":mean,"ic_std":sd,"icir":icir,"n_dates":len(ics),"avg_names":float(np.mean(nums)),"hac_t":t,"p_value":p})
            q_rows.append({"factor":name,"horizon":H,"top_quintile":float(np.mean(top)),"bottom_quintile":float(np.mean(bottom)),"top_minus_bottom":q10,"n_dates":len(top)})
            cov_rows.append({"factor":name,"horizon":H,"n":len(ics),"avg_names":float(np.mean(nums)),"coverage":float(np.mean(nums)/np.mean([len(member_sets[d]) for d in [dates[i] for i in sample[H]]])) if nums else None})
    # IC-series correlation is a redundancy diagnostic, not raw-price factor correlation.
    series_rows=[]
    for (fname,h),vals in ic_series.items():
        for d,v in vals: series_rows.append({"factor":fname,"horizon":h,"date":str(d),"ic":v})
    pd.DataFrame(series_rows).to_csv(OUT/"factor_ic_timeseries.csv",index=False)
    corr_rows=[]
    for h in HORIZONS:
        sub=pd.DataFrame(series_rows); sub=sub[sub.horizon==h]
        if sub.empty: continue
        piv=sub.pivot(index="date",columns="factor",values="ic")
        corr=piv.corr(min_periods=12)
        for a in corr.index:
            for b in corr.columns:
                if a<b and pd.notna(corr.loc[a,b]): corr_rows.append({"factor_a":a,"factor_b":b,"horizon":h,"ic_corr":float(corr.loc[a,b])})
    pd.DataFrame(corr_rows).to_csv(OUT/"factor_correlation.csv",index=False)
    icdf=pd.DataFrame(ic_rows);qdf=pd.DataFrame(q_rows);covdf=pd.DataFrame(cov_rows)
    # BH across all factor-horizon hypotheses
    ps=icdf.dropna(subset=["p_value"]).copy().sort_values("p_value");qvals=[]
    for rank,p in enumerate(ps.p_value,1): qvals.append(min(1.0,float(p)*len(ps)/rank))
    ps["bh_q"]=qvals
    merged=icdf.merge(ps[["factor","horizon","bh_q"]],on=["factor","horizon"],how="left")
    merged.to_csv(OUT/"factor_ic_results.csv",index=False);qdf.to_csv(OUT/"factor_quantile_results.csv",index=False);merged[["factor","horizon","hac_t","p_value","bh_q"]].to_csv(OUT/"factor_hac_results.csv",index=False);merged[["factor","horizon","bh_q"]].to_csv(OUT/"factor_bh_results.csv",index=False);pd.DataFrame(robust).to_csv(OUT/"factor_robustness.csv",index=False);covdf.to_csv(OUT/"factor_coverage.csv",index=False)
    # Candidate only with BH q<=0.10, positive top-bottom, stable sign.
    cand=merged[(merged.bh_q<=0.10)&(merged.mean_ic>0)].copy()
    cand=cand.merge(pd.DataFrame(robust),on=["factor","horizon"],how="left")
    cand=cand[cand.sign_stable==True]
    cand.to_csv(OUT/"strategy_candidates.csv",index=False)
    # panel export: valid observations + labels (sample dates only, compact)
    panel=[]
    for H in HORIZONS:
        for i in sample[H]:
            for t in member_sets[dates[i]]:
                k=cols.index(t) if t in cols else None
                if k is None: continue
                panel.append({"date":str(dates[i]),"ticker":t,"horizon":H,"valid":bool(base_valid[i,k] and not shock60[i,k]),"label":labels[H][i,k] if np.isfinite(labels[H][i,k]) else None})
    pd.DataFrame(panel).to_parquet(OUT/"valid_research_panel.parquet",index=False)
    # factor definitions
    defsjson={k:{"window":v[0],"direction":v[1],"meaning":v[2],"formula_source":"factor_research.py"} for k,v in defs.items()}
    (OUT/"factor_definitions.json").write_text(json.dumps(defsjson,indent=2),encoding="utf-8")
    registry=[]
    for k,v in defs.items():registry.append({"factor":k,"window":v[0],"direction":v[1],"meaning":v[2],"registered":True})
    pd.DataFrame(registry).to_csv(OUT/"candidate_factor_registry.csv",index=False)
    status={"generated_at":datetime.now(timezone.utc).isoformat(),"status":"P8_3_NO_GO" if len(cand)==0 else "P8_3_RESEARCH_CANDIDATE","as_of":"2024-12-31",
            "factors":len(F),"horizons":list(HORIZONS),"ic_rows":len(merged),"candidate_rows":len(cand),"go_count":len(cand),
            "candidates":cand[["factor","horizon","mean_ic","hac_t","bh_q","top_minus_bottom"]].to_dict("records") if len(cand) else [],
            "data_blocked":["Nasdaq-100 membership","Dow 30 membership","historical fundamental PIT","2025-2026 history"],
            "label_policy":"forward labels missing => NaN/CENSORED; never zero; signal eligibility uses formation-time base_valid and prior 60d shock rule",
            "note":"Research only; no P8 shadow. No post-hoc P8.2.2 classification used for historical signals."}
    (OUT/"p8_3_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps({"factors":len(F),"ic_rows":len(merged),"candidates":len(cand),"coverage":covdf.coverage.mean(),"label_coverage":pd.DataFrame(label_cov).label_coverage.mean()},indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
