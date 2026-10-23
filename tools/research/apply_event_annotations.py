"""Apply genuinely reviewed CSV annotations to a new derived archive.

The source event archive is never overwritten. Pending rows are ignored; reviewed
labels require explicit provenance and a timezone-aware review timestamp.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any


def _aware(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(timezone.utc)


def _score(value: Any, field: str, lower: float, upper: float) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric or blank") from exc
    if not math.isfinite(number) or number < lower or number > upper:
        raise ValueError(f"{field} must be finite and in [{lower}, {upper}]")
    return number


def apply_annotations(
    archive: list[dict[str, Any]],
    annotation_rows: list[dict[str, Any]],
    *,
    as_of: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cutoff = _aware(as_of, "as_of")
    by_version: dict[str, dict[str, Any]] = {}
    for event in archive:
        version = str(event.get("event_version_id") or "")
        if not version:
            raise ValueError("every archive event must have event_version_id")
        if version in by_version:
            raise ValueError(f"duplicate event_version_id in archive: {version}")
        by_version[version] = dict(event)

    applied: dict[str, dict[str, Any]] = {}
    ignored_pending = 0
    reviewed_count = 0
    validated_count = 0
    for index, row in enumerate(annotation_rows):
        version = str(row.get("event_version_id") or "").strip()
        if not version:
            raise ValueError(f"annotation row {index} is missing event_version_id")
        if version not in by_version:
            raise ValueError(f"annotation references unknown event_version_id: {version}")
        status = str(row.get("label_review_status") or "pending").strip().lower()
        if status == "pending":
            ignored_pending += 1
            continue
        if status not in {"reviewed", "validated"}:
            raise ValueError(f"annotation row {index} has invalid review status: {status}")
        if version in applied:
            raise ValueError(f"duplicate annotation for event_version_id: {version}")
        event = by_version[version]
        if event.get("label_review_status") in {"reviewed", "validated"}:
            raise ValueError(f"archive event already has reviewed labels: {version}")
        direction = _score(row.get("direction_score"), "direction_score", -1.0, 1.0)
        impact = _score(row.get("impact_score"), "impact_score", 0.0, 1.0)
        rationale = str(row.get("label_rationale") or "").strip()
        labeler = str(row.get("labeler_id") or "").strip()
        reviewer = str(row.get("reviewer_id") or "").strip()
        schema_version = str(row.get("label_schema_version") or "").strip()
        if not rationale or not labeler or not reviewer or not schema_version:
            raise ValueError(f"reviewed annotation {version} requires rationale, labeler, reviewer and schema version")
        if "@" in labeler or "@" in reviewer:
            raise ValueError("labeler_id and reviewer_id must be non-secret identifiers, not email addresses")
        reviewed_at = _aware(row.get("label_reviewed_at_utc"), "label_reviewed_at_utc")
        first_seen = _aware(event.get("first_seen_at_utc"), "first_seen_at_utc")
        if reviewed_at < first_seen:
            raise ValueError(f"review timestamp precedes event first-seen time: {version}")
        if reviewed_at > cutoff:
            raise ValueError(f"review timestamp is after the import cutoff: {version}")
        if status == "validated" and labeler == reviewer:
            raise ValueError(f"validated annotation {version} requires a distinct reviewer")
        applied[version] = {
            "direction_score": direction,
            "impact_score": impact,
            "label_review_status": status,
            "label_reviewed_at_utc": reviewed_at.isoformat().replace("+00:00", "Z"),
            "label_rationale": rationale,
            "labeler_id": labeler,
            "reviewer_id": reviewer,
            "label_schema_version": schema_version,
        }
        reviewed_count += 1
        validated_count += int(status == "validated")

    output = []
    for event in archive:
        row = dict(event)
        version = str(row.get("event_version_id") or "")
        if version in applied:
            row.update(applied[version])
        output.append(row)
    canonical = json.dumps(output, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    report = {
        "status": "annotations_applied" if reviewed_count else "no_reviewed_annotations",
        "as_of_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "archive_rows": len(archive),
        "annotation_rows_received": len(annotation_rows),
        "reviewed_annotations_applied": reviewed_count,
        "validated_annotations_applied": validated_count,
        "pending_rows_ignored": ignored_pending,
        "unreviewed_archive_rows": len(output) - reviewed_count,
        "labels_generated_by_tool": False,
        "source_archive_overwritten": False,
        "output_archive_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
        "research_only": True,
        "limitations": [
            "This tool imports human-entered annotations only; it never generates or infers scores.",
            "The source archive remains unchanged; the output is a separate derived archive.",
            "A successful import does not establish predictive value or empirical alpha.",
        ],
    }
    return output, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--annotations-csv", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", required=True, help="New derived archive JSON path")
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    outputs = [Path(args.output), Path(args.report)]
    if any(path.exists() for path in outputs):
        parser.error("refusing to overwrite existing derived archive or report")
    try:
        archive = json.loads(Path(args.archive).read_text(encoding="utf-8"))
        if not isinstance(archive, list):
            raise ValueError("archive must be a JSON array")
        with Path(args.annotations_csv).open("r", newline="", encoding="utf-8-sig") as handle:
            annotations = list(csv.DictReader(handle))
        merged, report = apply_annotations(archive, annotations, as_of=args.as_of)
        outputs[0].parent.mkdir(parents=True, exist_ok=True)
        outputs[1].parent.mkdir(parents=True, exist_ok=True)
        outputs[0].write_text(json.dumps(merged, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        outputs[1].write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Applied {report['reviewed_annotations_applied']} reviewed annotations; source archive unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
