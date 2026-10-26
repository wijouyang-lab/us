from __future__ import annotations

import json
from pathlib import Path

from tools.research.record_sec_capture_failure import write_failure_record


def test_sec_failure_record_is_diagnostic_and_not_pit_eligible(tmp_path: Path) -> None:
    log = tmp_path / "capture.log"
    output = tmp_path / "nested" / "failure.json"
    log.write_text("request failed: SEC master index HTTP 403\n", encoding="utf-8")

    payload = write_failure_record(str(log), str(output), "2026-10-01", "2026-10-26", 2)

    assert payload["failure_code"] == "http_403"
    assert payload["historical_pit_eligible"] is False
    assert payload["source_retrieval_succeeded"] is False
    assert "not be interpreted as proof" in " ".join(payload["limitations"])
    assert json.loads(output.read_text(encoding="utf-8")) == payload
