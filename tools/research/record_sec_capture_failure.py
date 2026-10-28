"""Persist a bounded, non-PIT-eligible SEC capture failure record."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def write_failure_record(
    log_path: str, error_path: str, start_date: str, end_date: str, exit_code: int
) -> dict[str, object]:
    log_file = Path(log_path)
    log = log_file.read_text(encoding="utf-8", errors="replace")
    payload: dict[str, object] = {
        "source": "sec_edgar_master_index",
        "status": "failed",
        "failure_code": "http_403" if "HTTP 403" in log else "capture_failed",
        "failure_log": log_file.name,
        "failure_excerpt": log[-4000:],
        "attempted_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "exit_code": exit_code,
        "source_retrieval_succeeded": False,
        "historical_pit_eligible": False,
        "research_only": True,
        "limitations": [
            "No filing rows were captured by this attempt.",
            "A retrieval failure must not be interpreted as proof that no filings occurred.",
            "Do not infer publication timestamps or historical first-seen times from this failure record.",
        ],
    }
    output = Path(error_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_path")
    parser.add_argument("error_path")
    parser.add_argument("start_date")
    parser.add_argument("end_date")
    parser.add_argument("exit_code", type=int)
    args = parser.parse_args()
    write_failure_record(args.log_path, args.error_path, args.start_date, args.end_date, args.exit_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
