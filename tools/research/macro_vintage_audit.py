#!/usr/bin/env python3
"""Macro vintage availability audit; no key is printed or fabricated."""
from __future__ import annotations

import os
import json
from pathlib import Path

SERIES = {
    "FEDFUNDS": "Federal Funds Rate",
    "DGS2": "2Y Treasury",
    "DGS10": "10Y Treasury",
    "CPIAUCSL": "CPI",
    "CPILFESL": "Core CPI",
    "PCEPI": "PCE",
    "PCEPILFE": "Core PCE",
    "UNRATE": "Unemployment",
    "PAYEMS": "Nonfarm Payrolls",
    "ICSA": "Initial Claims",
}


def audit_environment():
    return {"fred_api_key_present": bool(os.environ.get("FRED_API_KEY")),
            "alfred_api_key_present": bool(os.environ.get("ALFRED_API_KEY")),
            "key_value_printed": False}


def summarize(vintage_records):
    total = len(vintage_records)
    verified = sum(1 for r in vintage_records if r.vintage_verified)
    first_available = sum(1 for r in vintage_records if r.first_release_value is not None)
    return {"records": total, "vintage_verified": verified,
            "first_release_available": first_available,
            "pit_eligible": sum(1 for r in vintage_records if r.pit_eligible),
            "vintage_ratio": verified / total if total else 0.0}


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    out = {"series": SERIES, **audit_environment(),
           "status": "UNAVAILABLE_WITHOUT_KEY_OR_VINTAGE",
           "note": "free current FRED CSV is not a historical vintage; ALFRED requires a key"}
    Path(a.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
