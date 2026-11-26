"""SEC SIC -> normalized industry. SIC is not GICS."""
from __future__ import annotations
from datetime import datetime, timezone

VERSION = "sic-map-1.0"

# Transparent, coarse ranges. This is an industry research tag, not GICS.
RULES = [
    ((7370, 7379), "Software"),
    ((3674, 3674), "Semiconductor"),
    ((3570, 3579), "Technology Hardware"),
    ((3651, 3652), "Consumer Electronics"),
    ((5200, 5999), "Retail"),
    ((2830, 2836), "Healthcare"),
    ((8000, 8099), "Healthcare"),
    ((2900, 2999), "Energy"),
    ((1300, 1399), "Energy"),
    ((4900, 4999), "Utilities"),
    ((6000, 6199), "Banking"),
    ((6300, 6399), "Insurance"),
    ((6798, 6798), "REIT"),
    ((6500, 6599), "Real Estate"),
    ((2000, 3999), "Industrial/Manufacturing"),
]


def classify_sic(sic, description: str | None = None) -> dict:
    try: code = int(sic)
    except (TypeError, ValueError):
        return {"sic": sic, "sic_description": description, "normalized_industry": None,
                "mapping_status": "NO_SIC", "mapping_version": VERSION}
    for (lo, hi), name in RULES:
        if lo <= code <= hi:
            return {"sic": code, "sic_description": description, "normalized_industry": name,
                    "mapping_status": "OK", "mapping_version": VERSION}
    return {"sic": code, "sic_description": description, "normalized_industry": "Unmapped",
            "mapping_status": "UNMAPPED", "mapping_version": VERSION}


def industry_from_submissions(cik: str, submissions: dict, *, manual_sector: str | None = None,
                              manual_reason: str | None = None) -> dict:
    base = classify_sic(submissions.get("sic"), submissions.get("sicDescription"))
    base.update({"ticker": None, "cik": cik, "source": "SEC Submissions",
                 "fetched_at": datetime.now(timezone.utc).isoformat(),
                 "sector_source": "SEC_SIC"})
    if manual_sector:
        base["normalized_industry"] = manual_sector
        base["sector_source"] = "MANUAL_OVERRIDE"
        base["manual_reason"] = manual_reason or "caller supplied"
        base["sic_original"] = base["sic"]
        base["mapping_status"] = "MANUAL"
    return base
