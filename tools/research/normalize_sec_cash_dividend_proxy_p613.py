"""Normalize SEC cash-dividend facts and compute actual TTM amounts.

Sign rule: positive PaymentsOfDividends* is a payment; negative is a reversal /
adjustment requiring review, not an absolute dividend. Per-share facts never
become total cash.
"""
from __future__ import annotations
from datetime import date
from collections import defaultdict

CASH_TAGS = {"DividendsPaid", "PaymentsOfDividends", "PaymentsOfDividendsCommonStock",
             "PaymentsOfDividendsPreferredStockAndPreferenceStock", "DividendsCommonStockCash",
             "DividendsCash", "Dividends", "DividendsCommonStock", "PaymentsOfOrdinaryDividends"}
PER_SHARE_TAGS = {"CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"}
TAG_PRIORITY = {"PaymentsOfDividendsCommonStock": 0, "PaymentsOfDividends": 1,
                "DividendsPaid": 2, "DividendsCommonStockCash": 3, "DividendsCash": 4,
                "Dividends": 5, "PaymentsOfOrdinaryDividends": 6}
CASH_METRIC = "DividendsPaid"


def parse_date(v):
    try: return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError): return None


def normalize_cash(raw_value, unit, tag):
    try: x = float(raw_value)
    except (TypeError, ValueError): return None, "VALUE_INVALID"
    if tag in PER_SHARE_TAGS or unit == "USD/shares":
        return None, "PER_SHARE_FACT_NOT_TOTAL_CASH"
    if tag not in CASH_TAGS:
        return None, "UNSUPPORTED_CASH_TAG"
    if unit not in ("USD", "CAD", "EUR", "GBP", "JPY", "BRL", "MXN", "AUD",
                    "CNY", "HKD", "INR", "KRW", "ZAR", "SEK", "DKK", "NOK",
                    "CHF", "TWD", "SGD", "PEN", "COP", "CLP", "ARS", "TRY"):
        return None, "UNSUPPORTED_UNIT"
    if x == 0: return 0.0, "ZERO_CASH_FACT"
    if x < 0: return None, "NEGATIVE_SIGN_REQUIRES_REVIEW"
    return x, "CASH_FACT_NORMALIZED"


def period_type(start, end, filed):
    s, e, f = parse_date(start), parse_date(end), parse_date(filed)
    if not e or not f: return "UNKNOWN"
    if not s: return "INSTANT"
    days = (e - s).days
    if 80 <= days <= 110: return "QUARTER"
    if 160 <= days <= 290: return "YTD"
    if 300 <= days <= 400: return "ANNUAL"
    return "OTHER"


def _quarterize(tag_facts):
    """Convert Q and YTD facts to non-overlapping quarter amounts for one series."""
    quarters = []
    for f in tag_facts:
        s, e = parse_date(f.get("period_start")), parse_date(f.get("period_end"))
        if not s or not e: continue
        pt = f.get("_pt") or period_type(f.get("period_start"), f.get("period_end"), f.get("filed"))
        val = f.get("_positive")
        if val is None: continue
        if pt == "QUARTER":
            quarters.append({"start": s, "end": e, "amount": val, "filed": f.get("filed"),
                             "accn": f.get("accn"), "method": "QUARTER_DIRECT"})
        elif pt == "YTD":
            quarters.append({"start": s, "end": e, "amount": val, "filed": f.get("filed"),
                             "accn": f.get("accn"), "method": "YTD_CUMULATIVE"})
    # derive YTD differences only within same start year, ordered by end
    out = []
    by_year = defaultdict(list)
    annuals = []
    for f in tag_facts:
        pt = f.get("_pt") or period_type(f.get("period_start"), f.get("period_end"), f.get("filed"))
        if pt == "ANNUAL" and f.get("_positive") is not None:
            annuals.append(f)
    for q in quarters:
        if q["method"] == "YTD_CUMULATIVE":
            by_year[q["start"].year].append(q)
        else:
            out.append(q)
    for year, qs in by_year.items():
        qs.sort(key=lambda q: q["end"])
        prev = 0.0
        prev_end = None
        for q in qs:
            amt = q["amount"] - prev
            if amt < 0: continue
            qstart = q["start"] if prev_end is None else __import__("datetime").date.fromordinal(prev_end.toordinal() + 1)
            out.append({"start": qstart, "end": q["end"], "amount": amt,
                        "filed": q["filed"], "accn": q["accn"], "method": "YTD_DIFFERENCE"})
            prev = q["amount"]; prev_end = q["end"]
    # Q4 = annual - 9M YTD for the same fiscal end
    for a in annuals:
        ae = parse_date(a.get("period_end")); ast = parse_date(a.get("period_start"))
        if not ae or not ast: continue
        ytd = [q for q in out if q["end"] == ae and q["start"].year == ast.year]
        if ytd and ast.year == ae.year:
            y = max(ytd, key=lambda q: q["amount"])
            amt = float(a.get("raw_value")) - y["amount"]
            if amt >= 0:
                q4start = __import__("datetime").date.fromordinal(y["end"].toordinal() + 1)
                out.append({"start": q4start, "end": ae, "amount": amt,
                            "filed": a.get("filed"), "accn": a.get("accn"), "method": "ANNUAL_LESS_9M_YTD"})
    out.sort(key=lambda q: q["end"])
    # drop overlapping/duplicate quarter periods, keep latest filing
    clean = {}
    for q in out:
        key = (q["start"], q["end"])
        if key not in clean or (q["filed"] or "") >= (clean[key]["filed"] or ""):
            clean[key] = q
    return sorted(clean.values(), key=lambda q: q["end"])


def compute_ttm(facts):
    """facts: list with cik/taxonomy/tag/unit/period_start/period_end/filed/raw_value.

    Chooses one tag priority per CIK/currency; returns *computed* TTM only when
    four contiguous non-overlapping quarters exist.
    """
    out = {}
    by_cik = defaultdict(list)
    for f in facts:
        if f.get("fact_kind") != "TOTAL_CASH": continue
        by_cik[f.get("cik")].append(f)
    for cik, fs in by_cik.items():
        by_series = defaultdict(list)
        for f in fs:
            raw = f.get("raw_value")
            try: raw = float(raw)
            except (TypeError, ValueError): continue
            if raw <= 0: continue
            f = dict(f); f["_positive"] = raw
            by_series[(f.get("taxonomy"), f.get("tag"), f.get("unit"))].append(f)
        best = None
        for (tax, tag, unit), series in sorted(by_series.items(), key=lambda kv: TAG_PRIORITY.get(kv[0][1], 99)):
            qs = derive_quarters(series)
            if len(qs) < 4: continue
            last = qs[-4:]
            ok = True
            for a, b in zip(last, last[1:]):
                if not a["start"] or not b["start"]: ok = False; break
                if (b["start"] - a["end"]).days != 1: ok = False; break
                if not (80 <= (a["end"] - a["start"]).days <= 110): ok = False; break
            if not ok: continue
            total = sum(q["amount"] for q in last)
            best = {"cik": cik, "ttm_cash_dividend": total, "currency": unit,
                    "q1_amount": last[0]["amount"], "q1_start": last[0]["start"].isoformat(), "q1_end": last[0]["end"].isoformat(),
                    "q2_amount": last[1]["amount"], "q2_start": last[1]["start"].isoformat(), "q2_end": last[1]["end"].isoformat(),
                    "q3_amount": last[2]["amount"], "q3_start": last[2]["start"].isoformat(), "q3_end": last[2]["end"].isoformat(),
                    "q4_amount": last[3]["amount"], "q4_start": last[3]["start"].isoformat(), "q4_end": last[3]["end"].isoformat(),
                    "filed_date": max((q["filed"] or "") for q in last),
                    "accession_number": "|".join(str(q["accn"] or "") for q in last),
                    "taxonomy": tax, "tag": tag, "method": "SUM_FOUR_DERIVED_QUARTERS",
                    "verification_status": "TTM_AMOUNT_COMPUTED"}
            break
        if best: out[cik] = best
    return out


def stop_after_status(status):
    return status == 429


def ttm_status(periods):
    """Legacy period-coverage helper retained for tests; not amount computation."""
    ps = sorted((parse_date(a), parse_date(b)) for a, b in periods)
    if len(ps) < 4: return "TTM_UNAVAILABLE"
    last = ps[-4:]
    for (s1,e1),(s2,e2) in zip(last,last[1:]):
        if not s1 or not e1 or not s2 or not e2: return "TTM_UNAVAILABLE"
        if not (80 <= (e1-s1).days <= 110): return "TTM_UNAVAILABLE"
        if (s2-e1).days != 1: return "TTM_UNAVAILABLE"
    return "TTM_AVAILABLE"


def derive_quarters(tag_facts):
    """Derive quarter amounts directly from Q, YTD and annual cash facts."""
    direct, ytd, annual = [], [], []
    for f in tag_facts:
        s, e = parse_date(f.get("period_start")), parse_date(f.get("period_end"))
        if not s or not e: continue
        pt = f.get("period_type") or period_type(f.get("period_start"), f.get("period_end"), f.get("filed_date"))
        val = f.get("_positive")
        if val is None: continue
        rec = {"start": s, "end": e, "amount": val,
               "filed": f.get("filed_date") or f.get("filed"), "accn": f.get("accession_number") or f.get("accn")}
        if pt == "QUARTER": direct.append({**rec, "method": "QUARTER_DIRECT"})
        elif pt == "YTD": ytd.append({**rec, "method": "YTD_CUMULATIVE"})
        elif pt == "ANNUAL": annual.append(rec)
    out = list(direct)
    # YTD differences: Q1=YTD1, Q2=YTD2-YTD1, Q3=YTD3-YTD2
    groups = defaultdict(list)
    for f in ytd: groups[(f["start"], f["start"].year)].append(f)
    for _, qs in groups.items():
        qs.sort(key=lambda x: x["end"])
        prev = 0.0; prev_end = None
        for q in qs:
            amt = q["amount"] - prev
            if amt < 0: prev = q["amount"]; prev_end = q["end"]; continue
            start = q["start"] if prev_end is None else date.fromordinal(prev_end.toordinal() + 1)
            out.append({"start": start, "end": q["end"], "amount": amt, "filed": q["filed"],
                        "accn": q["accn"], "method": "YTD_DIFFERENCE"})
            prev = q["amount"]; prev_end = q["end"]
    # Q4 = annual - 9M YTD (same fiscal end)
    for a in annual:
        same = [q for q in ytd if q["end"] == a["end"]]
        if not same: continue
        y = max(same, key=lambda x: x["amount"])
        amt = a["amount"] - y["amount"]
        if amt < 0: continue
        out.append({"start": date.fromordinal(y["end"].toordinal() + 1), "end": a["end"],
                    "amount": amt, "filed": a["filed"], "accn": a["accn"],
                    "method": "ANNUAL_LESS_9M_YTD"})
    clean = {}
    for q in out:
        key = (q["start"], q["end"])
        if key not in clean or (q["filed"] or "") >= (clean[key]["filed"] or ""):
            clean[key] = q
    return sorted(clean.values(), key=lambda q: q["end"])
