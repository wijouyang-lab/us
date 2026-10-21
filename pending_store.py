# -*- coding: utf-8 -*-
"""Safe merge/write layer for ``us_stocks_pending_YYYYMMDD.csv``.

Scan can run more than once on the same New York trading day.  The old writer
opened the day file with mode ``"w"`` and silently replaced the earlier scan's
recommendations.  This module merges by the canonical recommendation key
``(Date, Ticker, Tag)`` and writes atomically under a cross-process lock.

Rules:
  * a key already present in ``*.processed`` is never re-queued;
  * a duplicate key from a newer scan updates only non-empty fields, so an
    empty/broken value never erases a valid earlier field;
  * every conflict is logged; nothing is overwritten silently;
  * the existing CSV header order is preserved and missing new columns are
    appended, keeping old files readable;
  * a failed write leaves the original file untouched.
"""

from __future__ import annotations

import contextlib
import csv
import os
import tempfile
import time
from pathlib import Path
from typing import Iterable, Mapping, Sequence


KEY_FIELDS = ("Date", "Ticker", "Tag")
LOCK_SUFFIX = ".lock"
LOCK_STALE_SECONDS = 300.0


class PendingStoreError(RuntimeError):
    """Raised when a pending file cannot be read or written safely."""


def normalize_key(row: Mapping[str, object]) -> tuple[str, str, str]:
    """Canonical recommendation key; Tag keeps Core/Observation distinct."""
    return (
        str(row.get("Date") or "").strip()[:10],
        str(row.get("Ticker") or "").strip().upper(),
        str(row.get("Tag") or "").strip(),
    )


def _normalize_row(row: Mapping[str, object], fields: Sequence[str]) -> dict[str, str]:
    out = {}
    for field in fields:
        value = row.get(field, "")
        if value is None:
            value = ""
        out[field] = str(value)
    return out


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
        return fields, rows
    except Exception as exc:
        raise PendingStoreError("cannot read %s safely: %s" % (path, exc)) from exc


def _merge_fields(existing: Mapping[str, str], incoming: Mapping[str, str]) -> tuple[dict[str, str], list[str]]:
    """Newer non-empty values win; empty incoming values never erase data."""
    merged = dict(existing)
    changed = []
    for field, value in incoming.items():
        if field not in merged:
            merged[field] = value
            changed.append(field)
            continue
        if str(value or "") == "":
            continue
        if str(merged.get(field, "")) != str(value):
            merged[field] = str(value)
            changed.append(field)
    return merged, changed


def _pid_alive(pid: int) -> bool:
    """Cross-platform liveness check without os.kill(pid, 0) on Windows.

    On Windows ``os.kill(pid, 0)`` is not a no-op: Python maps it to
    TerminateProcess, which would kill the lock owner (or the caller).
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return False
                return code.value == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True


@contextlib.contextmanager
def _file_lock(path: Path, timeout: float = 10.0):
    """Portable O_CREAT|O_EXCL lock with PID-aware stale-lock recovery."""
    lock_path = Path(str(path) + LOCK_SUFFIX)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.1, float(timeout))
    fd = None
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, ("%s %.3f" % (os.getpid(), time.time())).encode("ascii"))
            os.fsync(fd)
            break
        except FileExistsError:
            stale = False
            try:
                raw = lock_path.read_text(encoding="ascii", errors="ignore").split()
                age = time.time() - lock_path.stat().st_mtime
                if raw and raw[0].isdigit():
                    pid = int(raw[0])
                    if not _pid_alive(pid) and age > 2.0:
                        stale = True
                elif age > LOCK_STALE_SECONDS:
                    stale = True
            except OSError:
                pass
            if stale:
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise PendingStoreError("pending file lock timeout: %s" % lock_path)
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _atomic_write(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fields})
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def merge_pending_file(
    path: str | Path,
    new_rows: Iterable[Mapping[str, object]],
    new_fields: Sequence[str],
    processed_path: str | Path | None = None,
    lock_timeout: float = 10.0,
    logger=print,
) -> dict[str, int]:
    """Merge ``new_rows`` into ``path`` atomically; return merge statistics.

    ``processed_path`` is normally ``path + ".processed"``.  Its event keys are
    treated as already consumed and are never written back to pending.
    """
    target = Path(path)
    processed = Path(processed_path) if processed_path else Path(str(target) + ".processed")
    incoming = [dict(row) for row in (new_rows or [])]
    new_fields = [str(f) for f in (new_fields or [])]
    if not new_fields:
        raise PendingStoreError("new_rows were supplied without a header")

    with _file_lock(target, timeout=lock_timeout):
        existing_fields, existing_rows = _read_csv(target)
        processed_fields, processed_rows = _read_csv(processed)

        # Existing header order wins; append only genuinely new columns.
        fields = list(existing_fields)
        for field in new_fields:
            if field not in fields:
                fields.append(field)
        if not fields:
            fields = list(new_fields)

        processed_keys = {
            normalize_key(row) for row in processed_rows if any(str(v or "").strip() for v in row.values())
        }
        processed_keys.discard(("", "", ""))

        merged_rows: list[dict[str, str]] = []
        by_key: dict[tuple[str, str, str], int] = {}
        stats = {"kept": 0, "added": 0, "updated": 0, "duplicates": 0, "processed_skipped": 0, "skipped_event_keys": []}

        for row in existing_rows:
            row = _normalize_row(row, fields)
            key = normalize_key(row)
            if key in processed_keys:
                stats["processed_skipped"] += 1
                logger("[pending] skip already-processed event %s from existing file" % (key,))
                continue
            if key in by_key:
                stats["duplicates"] += 1
                logger("[pending] duplicate existing event %s ignored" % (key,))
                continue
            by_key[key] = len(merged_rows)
            merged_rows.append(row)
            stats["kept"] += 1

        for raw in incoming:
            row = _normalize_row(raw, fields)
            key = normalize_key(row)
            if key in processed_keys:
                stats["processed_skipped"] += 1
                stats["skipped_event_keys"].append(key)
                logger("[pending] skip already-processed event %s from new scan" % (key,))
                continue
            if key in by_key:
                idx = by_key[key]
                merged, changed = _merge_fields(merged_rows[idx], row)
                merged_rows[idx] = merged
                stats["duplicates"] += 1
                if changed:
                    stats["updated"] += 1
                    logger(
                        "[pending] event %s appeared again; updated non-empty fields: %s"
                        % (key, ", ".join(changed))
                    )
                else:
                    logger("[pending] event %s appeared again with no new non-empty fields" % (key,))
                continue
            by_key[key] = len(merged_rows)
            merged_rows.append(row)
            stats["added"] += 1

        _atomic_write(target, fields, merged_rows)
        logger(
            "[pending] merged %s: kept=%d added=%d updated=%d duplicates=%d processed_skipped=%d"
            % (target.name, stats["kept"], stats["added"], stats["updated"],
               stats["duplicates"], stats["processed_skipped"])
        )
        return stats


# Public alias used by review_session_guard (same cross-process lock semantics).
file_lock = _file_lock
