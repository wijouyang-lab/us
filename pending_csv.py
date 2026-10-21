# -*- coding: utf-8 -*-
"""Strict CSV reader for ``us_stocks_pending_*.csv``.

Pandas' ``on_bad_lines="skip"`` can silently drop or shift rows when a pending
file is malformed.  Pending files are later renamed to ``.processed``, so a
silent row loss becomes a permanent lost recommendation.  This module uses the
stdlib CSV parser with ``strict=True`` plus an explicit field-count check.
"""

from __future__ import annotations

import csv
from pathlib import Path


class PendingCsvError(ValueError):
    """Raised when a pending CSV cannot be parsed without losing rows."""


def read_pending_csv(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a pending CSV strictly.

    Returns ``(header, rows)`` where each row is a dict of string values.
    Raises ``PendingCsvError`` for empty files, missing/duplicate headers,
    unclosed quotes, or any row whose field count differs from the header.
    A header-only file is valid and returns ``(header, [])``.
    """
    target = Path(path)
    if not target.exists():
        raise PendingCsvError("file does not exist: %s" % target)
    if target.stat().st_size == 0:
        raise PendingCsvError("empty file (0 bytes): %s" % target)

    try:
        with target.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            try:
                header = next(reader)
            except StopIteration:
                raise PendingCsvError("empty file (no header): %s" % target)
            if not header or not any(str(cell).strip() for cell in header):
                raise PendingCsvError("missing/blank header: %s" % target)
            if len(set(header)) != len(header):
                raise PendingCsvError("duplicate header columns: %s" % target)

            rows: list[dict[str, str]] = []
            for line_no, row in enumerate(reader, start=2):
                if not row:
                    # A physical blank line is not a data row; pandas skips it too.
                    continue
                if len(row) != len(header):
                    raise PendingCsvError(
                        "%s line %d: expected %d fields, got %d"
                        % (target, line_no, len(header), len(row))
                    )
                rows.append({header[i]: row[i] for i in range(len(header))})
            return header, rows
    except PendingCsvError:
        raise
    except csv.Error as exc:
        raise PendingCsvError("malformed CSV %s: %s" % (target, exc)) from exc
    except UnicodeDecodeError as exc:
        raise PendingCsvError("cannot decode CSV %s as UTF-8: %s" % (target, exc)) from exc
    except OSError as exc:
        raise PendingCsvError("cannot read CSV %s: %s" % (target, exc)) from exc
