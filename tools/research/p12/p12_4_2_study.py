"""P12.4.1 PIT fundamental-change and 8-K event study."""
from __future__ import annotations

import bisect
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from tools.research.p12.pit_query import _et_end_of_day

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data/research"
OUT = DATA / "p12_4_2"
OUT.mkdir(parents=True, exist_ok=True)

FACT = DATA / "p12_3/p12_3_accession_fact_panel.csv"
EVENT = DATA / "p12_3_1/p12_3_1_event_window_returns.csv"
PRICE = ROOT.parent / "pr512/data/research/pit_data/finsaber_prices_raw.csv"
SPY = ROOT.parent / "pr512/data/research/p9_1_support_resistance/spy.csv"
METRICS = ["Revenue", "OperatingIncome", "NetIncome", "TotalAssets", "TotalDebt", "Cash", "OperatingCashFlow", "SharesOutstanding"]
EXPLORE = ("2009-01-01", "2018-12-31")
VALID = ("2019-01-01", "2024-12-31")


def _known(row):
    if pd.notna(row["acceptance_datetime"]) and str(row["acceptance_datetime"]):
        return pd.to_datetime(row["acceptance_datetime"], utc=True)
    return _et_end_of_day(str(row["filing_date"])[:10])


def _duration(row):
    if pd.isna(row["period_start"]) or pd.isna(row["period_end"]):
        return None
    return (pd.Timestamp(row["period_end"]) - pd.Timestamp(row["period_start"])).days


def _pick_current(sub):
    sub = sub.copy()
    sub["dur"] = sub.apply(_duration, axis=1)
    if sub["dur"].notna().any():
        sub = sub[sub.dur.notna() & (sub.dur.between(55, 115) | sub.dur.between(300, 400))]
        if sub.empty:
            return None
        return sub.sort_values(["dur", "period_end"]).iloc[-1]
    return sub.sort_values("period_end").iloc[-1]


def main():
    f = pd.read_csv(FACT, dtype={"cik": str})
    f["cik"] = f.cik.str.zfill(10)
    f["known_at"] = f.apply(_known, axis=1)
    f["dur"] = f.apply(_duration, axis=1)
    prices = pd.read_csv(PRICE, usecols=["date", "symbol", "adjusted_close"], parse_dates=["date"])
    prices["symbol"] = prices.symbol.str.upper().str.replace(".", "-", regex=False)
    prices = prices[prices.adjusted_close > 0]
    close = {s: g.set_index("date").adjusted_close.sort_index() for s, g in prices.groupby("symbol")}
    spy = pd.read_csv(SPY, parse_dates=["Date"]).set_index("Date").close.sort_index()
    tdays = sorted(set(spy.index.date.astype(str)))
    spy.index = spy.index.date

    # Fundamental disclosures: one initial 10-K/10-Q accession.
    filings = f[f.form.isin(["10-K", "10-Q"])].drop_duplicates("accession")[["cik", "ticker", "group", "accession", "form", "filing_date", "acceptance_datetime", "known_at"]]
    rows = []
    for _, ev in filings.iterrows():
        g = f[(f.cik == ev.cik) & (f.known_at <= ev.known_at)]
        sub = g[g.accession == ev.accession]
        if sub.empty:
            continue
        period_end = sub.period_end.max()
        vals = {}
        for m in METRICS:
            s = sub[sub.metric == m]
            if s.empty:
                continue
            p = _pick_current(s)
            if p is None or pd.isna(p.value):
                continue
            vals[m] = p
        if not {"Revenue", "OperatingIncome", "NetIncome", "OperatingCashFlow"}.issubset(vals):
            continue
        # Prior-year comparable: exact period end, same tag/unit, visible at filing.
        prior = {}
        for m, p in vals.items():
            target = pd.Timestamp(p.period_end) - pd.DateOffset(years=1)
            cand = g[(g.metric == m) & (g.tag == p.tag) & (g.unit == p.unit) & (g.period_end == str(target.date()))]
            if p.dur is not None and pd.notna(p.dur):
                cand = cand[cand.dur.notna() & (abs(cand.dur - p.dur) <= 20)]
            if not cand.empty:
                prior[m] = cand.sort_values("known_at").iloc[-1]
        def rv(m):
            return float(vals[m].value) if m in vals else np.nan
        def pv(m):
            return float(prior[m].value) if m in prior else np.nan
        growth = rv("Revenue") / pv("Revenue") - 1 if pv("Revenue") > 0 else np.nan
        mcur = rv("OperatingIncome") / rv("Revenue") if rv("Revenue") > 0 else np.nan
        mpri = pv("OperatingIncome") / pv("Revenue") if pv("Revenue") > 0 else np.nan
        cc = rv("OperatingCashFlow") / rv("NetIncome") if rv("NetIncome") > 0 else np.nan
        lev = (rv("TotalDebt") - rv("Cash")) / rv("TotalAssets") if rv("TotalAssets") > 0 else np.nan
        lev0 = (pv("TotalDebt") - pv("Cash")) / pv("TotalAssets") if pv("TotalAssets") > 0 else np.nan
        sh = rv("SharesOutstanding") / pv("SharesOutstanding") - 1 if pv("SharesOutstanding") > 0 else np.nan
        # Entry: first trading day strictly after known_at's date.
        # US/Eastern trading-date semantics; same-day close only if it is
        # strictly after the known disclosure time and that day is a session.
        et = pd.Timestamp(ev.known_at).tz_convert("America/New_York")
        d = str(et.date())
        j = bisect.bisect_right(tdays, d)
        if d in tdays and et.hour < 16:
            entry = d
        else:
            if j >= len(tdays):
                continue
            entry = tdays[j]
        ser = close.get(ev.ticker)
        if ser is None or entry not in ser.index:
            continue
        rets = {}
        for h in (5, 10, 20):
            if j + h < len(tdays):
                ex = tdays[j + h]
                rets[h] = float(ser.loc[ex] / ser.loc[entry] - 1) if ex in ser.index else np.nan
                spy_ex = float(spy.loc[pd.Timestamp(str(ex)).date()] / spy.loc[pd.Timestamp(str(entry)).date()] - 1) if pd.Timestamp(str(ex)).date() in spy.index and pd.Timestamp(str(entry)).date() in spy.index else np.nan
                rets[f"ex{h}"] = rets[h] - spy_ex if np.isfinite(rets[h]) and np.isfinite(spy_ex) else np.nan
        rows.append({
            "cik": ev.cik, "ticker": ev.ticker, "group": ev.group, "form": ev.form,
            "accession": ev.accession, "known_at": ev.known_at, "entry_date": entry, "period_end": period_end,
            "revenue_growth": growth, "op_margin_change": mcur - mpri,
            "cash_conversion": cc, "net_leverage": lev, "leverage_change": lev - lev0,
            "shares_change": sh,
            **{f"ret{h}": rets.get(h, np.nan) for h in (5, 10, 20)},
            **{f"ex{h}": rets.get(f"ex{h}", np.nan) for h in (5, 10, 20)},
        })
    fund = pd.DataFrame(rows)
    if not fund.empty:
        fund["known_at"] = pd.to_datetime(fund.known_at, utc=True)
    fund.to_csv(OUT / "p12_4_2_fundamental_panel.csv", index=False)

    # 8-K accession-level dedup and D10/D20 extension.
    e = pd.read_csv(EVENT)
    e = e[e.event_type == "8-K"].copy()
    e["entry_date"] = e["reaction_date"]
    for h in (10, 20):
        e[f"d{h}_return"] = np.nan
    for i, r in e.iterrows():
        ser = close.get(r["price_symbol"])
        if ser is None or r["reaction_date"] not in ser.index:
            continue
        k = tdays.index(r["reaction_date"])
        for h in (10, 20):
            if k + h < len(tdays) and tdays[k + h] in ser.index:
                e.at[i, f"d{h}_return"] = float(ser.loc[tdays[k + h]] / ser.loc[r["reaction_date"]] - 1)
    e["items"] = e["items"].fillna("")
    e["has_901"] = e["items"].str.contains("9.01")
    e["item_list"] = e["items"].str.split(",")
    # same-day 10-K/10-Q flag
    fdays = set(zip(f.cik, f.filing_date.astype(str)))
    e["same_day_filing"] = [1 if (str(r.cik).zfill(10), str(r.filing_date)) in fdays else 0 for _, r in e.iterrows()]
    # overlap: another 8-K for same issuer within 20 calendar days
    e["overlap_20d"] = 0
    # Trading-day D20 window intersection, not calendar days.
    def session_index(d):
        if d not in tdays:
            return None
        return tdays.index(d)
    e["reaction_index"] = e.reaction_date.map(session_index)
    for cik, g in e.groupby("cik"):
        idxs = [(i, int(r.reaction_index), int(r.reaction_index) + 20) for i, r in g.iterrows() if pd.notna(r.reaction_index)]
        for i, a, b in idxs:
            if any(j != i and c <= b and a <= d for j, c, d in idxs):
                e.loc[i, "overlap_20d"] = 1
    e.to_csv(OUT / "p12_4_2_8k_panel.csv", index=False)

    # Fundamental stats: rank IC pooled, top-bottom terciles, period split.
    fstats = []
    for m in ["revenue_growth", "op_margin_change", "cash_conversion", "leverage_change", "shares_change"]:
        for h in (5, 10, 20):
            for label, (a, b) in {"all": ("2009-01-01", "2024-12-31"), "explore": EXPLORE, "validate": VALID}.items():
                x = fund[(fund.known_at >= a) & (fund.known_at <= b)][["cik", m, f"ret{h}"]].dropna()
                if len(x) < 3:
                    continue
                ic = x[m].corr(x[f"ret{h}"], method="spearman") if x[m].nunique() > 1 else np.nan
                if x[m].nunique() >= 3:
                    x["q"] = pd.qcut(x[m].rank(method="first"), 3, labels=False)
                    spread = x[x.q == 2][f"ret{h}"].mean() - x[x.q == 0][f"ret{h}"].mean()
                else:
                    spread = np.nan
                fstats.append({"metric": m, "horizon": h, "period": label, "n_events": len(x), "n_issuers": x.cik.nunique(), "rank_ic": ic, "top_minus_bottom": spread, "mean_ret": x[f"ret{h}"].mean(), "median_ret": x[f"ret{h}"].median(), "positive_rate": (x[f"ret{h}"] > 0).mean()})
    pd.DataFrame(fstats).to_csv(OUT / "p12_4_2_fundamental_stats.csv", index=False)

    # 8-K stats by item and session; multi-label, accession-level.
    e["period"] = np.where(e.filing_date <= "2018-12-31", "explore", np.where(e.filing_date >= "2019-01-01", "validate", "other"))
    estats = []
    for item in ("1.01", "2.01", "2.02", "2.03", "5.02", "5.07", "7.01", "8.01"):
        for sess in ("PREMARKET", "INTRADAY", "AFTER_HOURS", "NON_TRADING"):
            for period in ("all", "explore", "validate"):
                x = e[e["items"].str.contains(rf"(?<![\d.]){re.escape(item)}(?![\d.])", regex=True) & (e.event_session == sess)]
                if period != "all":
                    x = x[x.period == period]
                x = x[["cik", "d0_return", "d1_return", "d5_return", "d10_return", "d20_return", "same_day_filing", "overlap_20d"]].dropna(subset=["d5_return"])
                if len(x) < 1:
                    continue
                estats.append({"item": item, "session": sess, "period": period, "n_accessions": len(x), "n_issuers": x.cik.nunique(), "d0_mean": x.d0_return.mean(), "d5_mean": x.d5_return.mean(), "d5_median": x.d5_return.median(), "d20_mean": x.d20_return.mean() if x.d20_return.notna().any() else np.nan, "d5_positive": (x.d5_return > 0).mean(), "same_day_filing_rate": x.same_day_filing.mean(), "overlap_rate": x.overlap_20d.mean()})
    pd.DataFrame(estats).to_csv(OUT / "p12_4_2_8k_stats.csv", index=False)

    coverage = {
        "fundamental_accessions": int(fund.accession.nunique()), "fundamental_rows": len(fund),
        "8k_accessions": len(e), "8k_issuers": int(e.cik.nunique()),
        "d0_available": int(e.d0_return.notna().sum()), "d1_available": int(e.d1_return.notna().sum()),
        "d5_available": int(e.d5_return.notna().sum()), "d10_available": int(e.d10_return.notna().sum()),
        "d20_available": int(e.d20_return.notna().sum()),
        "fundamental_5_available": int(fund.ret5.notna().sum()), "fundamental_20_available": int(fund.ret20.notna().sum()),
    }
    (OUT / "p12_4_2_coverage.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    print(coverage)


if __name__ == "__main__":
    main()
