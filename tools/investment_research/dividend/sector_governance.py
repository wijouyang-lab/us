"""Industry taxonomy and fixed dividend scoring profiles. No network."""
from __future__ import annotations
import re

CLASSES = {"NON_FINANCIAL","BANK","INSURANCE","REIT","FINANCIAL_OTHER","UNKNOWN_INDUSTRY"}


def normalize_label(label: str | None) -> str:
    if not label: return ""
    s = label.lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def classify(ticker: str, raw_label: str | None, *, sic: int | None = None) -> dict:
    n = normalize_label(raw_label)
    rule = "UNKNOWN"
    cls = "UNKNOWN_INDUSTRY"
    if "reit" in n or "real estate investment trust" in n or sic == 6798:
        cls, rule = "REIT", "REIT/real-estate-investment-trust"
    elif any(x in n for x in ("bank", "regional bank", "commercial bank")):
        cls, rule = "BANK", "bank alias"
    elif "insurance" in n or "insurer" in n or (sic is not None and 6300 <= sic <= 6399):
        cls, rule = "INSURANCE", "insurance alias/SIC 63xx"
    elif any(x in n for x in ("financial", "financial services", "diversified financial")):
        cls, rule = "FINANCIAL_OTHER", "financial alias"
    elif "real estate" in n or "realty" in n:
        cls, rule = "FINANCIAL_OTHER", "real estate but not REIT"
    elif any(x in n for x in ("software","semiconductor","technology","hardware","retail","industrial",
                              "manufacturing","healthcare","health care","pharma","biotech","energy",
                              "utilities","utility","consumer","materials","communication")):
        cls, rule = "NON_FINANCIAL", "non-financial label"
    elif sic is not None and not (6000 <= sic <= 6999):
        cls, rule = "NON_FINANCIAL", f"SIC {sic} outside financial ranges"
    return {"ticker": ticker.upper(), "raw_label": raw_label, "normalized_label": n,
            "sic": sic, "classification": cls, "rule": rule}


PROFILES = {
    "NON_FINANCIAL_DIVIDEND_V1": {
        "profile_id":"NON_FINANCIAL_DIVIDEND_V1", "version":"1.0",
        "components": {"payout":1/3, "fcf_coverage":1/3, "continuity":1/3},
        "signature":"payout|fcf_coverage|continuity", "denominator":3},
}

READY = {"payout","fcf_coverage","continuity"}


def evaluate(metrics: dict, classification: str, *, insurance_subtype: str | None = None) -> dict:
    if classification == "BANK":
        return {"score_profile_id":"BANK_MODEL", "industry_model_status":"BANK_MODEL_NOT_READY",
                "score":None, "score_status":"INDUSTRY_MODEL_NOT_READY",
                "reason":"CET1/regulatory capital evidence required; no proxy from equity/assets"}
    if classification == "INSURANCE":
        return {"score_profile_id":"INSURANCE_MODEL", "industry_model_status":"INSURANCE_MODEL_NOT_READY",
                "score":None, "score_status":"INDUSTRY_MODEL_NOT_READY",
                "insurance_subtype":insurance_subtype or "UNVERIFIED",
                "reason":"no common insurance capital/coverage model; industrial FCF not used"}
    if classification == "REIT":
        return {"score_profile_id":"REIT_MODEL", "industry_model_status":"REIT_FFO_REQUIRED",
                "score":None, "score_status":"INDUSTRY_MODEL_NOT_READY",
                "reit_ffo_status":"DATA_BLOCKED", "reit_affo_status":"DATA_BLOCKED",
                "reit_payout_status":"DATA_BLOCKED",
                "reason":"official FFO/AFFO disclosure required; GAAP net income payout is not a substitute"}
    if classification != "NON_FINANCIAL":
        return {"score_profile_id":"NONE", "industry_model_status":"INDUSTRY_MODEL_NOT_READY",
                "score":None, "score_status":"INDUSTRY_MODEL_NOT_READY",
                "reason":"unknown industry"}
    p = PROFILES["NON_FINANCIAL_DIVIDEND_V1"]
    available = {}
    payout = metrics.get("net_income_payout", {}); fcf = metrics.get("fcf_dividend_coverage", {})
    cont = metrics.get("continuity_status")
    if payout.get("status") == "OK": available["payout"] = payout.get("value")
    if fcf.get("status") == "OK": available["fcf_coverage"] = fcf.get("value")
    if cont == "OK": available["continuity"] = 1.0
    missing = sorted(READY - set(available))
    common = {"score_version":"p46-1.0", "score_profile_id":p["profile_id"],
              "score_component_signature":p["signature"], "score_weights":p["components"],
              "score_denominator":p["denominator"], "available_components":available,
              "missing_components":missing}
    if missing:
        return {**common, "industry_model_status":"NON_FINANCIAL_MODEL_READY",
                "score":None, "score_status":"NOT_READY",
                "reason":"missing required fixed component(s): " + ",".join(missing)}
    # Fixed weights; no renormalization.
    payout_score = max(0.0, 1 - max(0.0, available["payout"] - 0.5)/0.5)
    fcf_score = min(1.0, max(0.0, available["fcf_coverage"]/2.0))
    score = 100*(payout_score*(1/3) + fcf_score*(1/3) + 1.0*(1/3))
    return {**common, "industry_model_status":"NON_FINANCIAL_MODEL_READY",
            "score":round(score,1), "score_status":"SCORE_READY",
            "component_scores":{"payout":payout_score,"fcf_coverage":fcf_score,"continuity":1.0},
            "reason":None}


def comparable(a: dict, b: dict) -> bool:
    keys=("score_version","score_profile_id","score_component_signature","score_weights","score_denominator")
    return all(a.get(k)==b.get(k) for k in keys)
