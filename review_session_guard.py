# -*- coding: utf-8 -*-
"""Trading-session idempotency guard for Review.

The guard stores a small, committed marker (``review_session_state.json``)
after Review *and* the portfolio step have completed successfully.  The next
run of the same session is skipped only when the marker is valid **and** the
input fingerprint is unchanged.  Newly arrived pending rows or edited ledgers
change the fingerprint, so a retry never loses new work.

The marker is deliberately written by the workflow finalizer (after the
portfolio ledger step), not by ``review.py`` itself.  A failure in any required
step therefore leaves no success marker and the next run can safely retry.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pending_store import file_lock


MARKER_NAME = "review_session_state.json"
SCHEMA_VERSION = 2
LEDGER_FILES = (
    "trade_history.csv",
    "review_history.csv",
    "option_strategies.csv",
    "portfolio_50000_positions.csv",
    "portfolio_50000_transactions.csv",
    "portfolio_50000_history.csv",
    "portfolio_50000_meta.json",
)


class ReviewGuardError(RuntimeError):
    """Raised when the idempotency marker cannot be read or written safely."""


@dataclass
class GuardDecision:
    skip: bool
    reason: str
    fingerprint: str


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    try:
        return _sha_bytes(path.read_bytes())
    except OSError as exc:
        raise ReviewGuardError("cannot hash %s: %s" % (path, exc)) from exc


def _read_pending_rows(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    import csv

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = {}
            for row in reader:
                key = (
                    str(row.get("Date") or "").strip()[:10],
                    str(row.get("Ticker") or "").strip().upper(),
                    str(row.get("Tag") or "").strip(),
                )
                if not any(key):
                    continue
                rows[key] = {str(k): str(v or "") for k, v in row.items() if k is not None}
            return rows
    except Exception as exc:
        raise ReviewGuardError("cannot read pending file %s: %s" % (path, exc)) from exc


def _pending_files(root: Path) -> list[Path]:
    """All pending inputs Review may consume, regardless of session date.

    ``review.py`` scans every ``us_stocks_pending_*.csv`` and
    ``*.csv.processed`` file (supplement and recommendation-price lookup), so
    the guard fingerprint must cover the same universe, not just today's file.
    """
    names = set(glob.glob(str(root / "us_stocks_pending_*.csv")))
    names.update(glob.glob(str(root / "us_stocks_pending_*.csv.processed")))
    return sorted(Path(name) for name in names)


def unprocessed_pending_files(root: str | Path) -> list[Path]:
    """Pending .csv files that have not been renamed to .processed yet."""
    root = Path(root)
    return [
        path for path in _pending_files(root)
        if not path.name.endswith(".csv.processed")
        and re.search(r"us_stocks_pending_\d{8}\.csv$", path.name)
    ]


def pending_payload_fingerprint(root: str | Path, session_date: str | None = None) -> str:
    """Hash normalized rows of every pending file; rename-stable.

    The payload is keyed by the date embedded in the filename and contains the
    normalized event rows for that date.  Renaming ``.csv`` to ``.processed``
    does not change the payload.  A new/changed file for any date does.
    """
    root = Path(root)
    by_date: dict[str, dict[tuple[str, str, str], dict[str, str]]] = {}
    for path in _pending_files(root):
        match = re.search(r"us_stocks_pending_(\d{8})\.csv(?:\.processed)?$", path.name)
        if not match:
            continue
        day = match.group(1)
        bucket = by_date.setdefault(day, {})
        # A later .processed snapshot supersedes the same event in .csv;
        # distinct events from .csv are retained.
        bucket.update(_read_pending_rows(path))
    payload = [
        [day, [rows[key] for key in sorted(rows)]]
        for day, rows in sorted(by_date.items())
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha_bytes(raw.encode("utf-8"))


def ledger_fingerprint(root: str | Path) -> dict[str, str]:
    root = Path(root)
    return {name: _sha_file(root / name) for name in LEDGER_FILES}


def build_fingerprint(root: str | Path, session_date: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_date": str(session_date)[:10],
        "pending_scope": "all_dates",
        "pending": pending_payload_fingerprint(root),
        "ledgers": ledger_fingerprint(root),
    }


def fingerprint_digest(fingerprint: dict[str, object]) -> str:
    raw = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha_bytes(raw.encode("utf-8"))


class ReviewSessionGuard:
    def __init__(self, root: str | Path = ".", lock_timeout: float = 120.0):
        self.root = Path(root)
        self.marker_path = self.root / MARKER_NAME
        self.lock_timeout = float(lock_timeout)
        self._lock_cm = None

    def _load_marker(self) -> dict | None:
        if not self.marker_path.exists():
            return None
        try:
            data = json.loads(self.marker_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print("⚠️ [ReviewGuard] 标记文件不可读，按未完成处理：%s" % exc)
            return None
        return data if isinstance(data, dict) else None

    def begin(self, session_date: str) -> GuardDecision:
        """Acquire the session lock and decide whether this run should execute."""
        self._lock_cm = file_lock(self.marker_path, timeout=self.lock_timeout)
        self._lock_cm.__enter__()
        try:
            current = build_fingerprint(self.root, session_date)
            digest = fingerprint_digest(current)
            marker = self._load_marker()
        except Exception:
            self.release()
            raise
        if marker and marker.get("status") == "success":
            same_session = str(marker.get("session_date") or "")[:10] == str(session_date)[:10]
            same_fingerprint = marker.get("fingerprint") == current
            same_schema = marker.get("schema_version") == SCHEMA_VERSION
            if same_session and same_fingerprint and same_schema:
                unprocessed = unprocessed_pending_files(self.root)
                if unprocessed:
                    names = ", ".join(p.name for p in unprocessed[:5])
                    return GuardDecision(
                        False,
                        "同一交易日但仍有未处理 pending 文件：%s" % names,
                        digest,
                    )
                return GuardDecision(True, "同一交易日、输入与账本指纹未变化，且无未处理 pending，已成功处理", digest)
            if same_session:
                return GuardDecision(False, "同一交易日但输入/账本已变化，需要安全重跑", digest)
            return GuardDecision(False, "新的交易日", digest)
        return GuardDecision(False, "无成功标记或上次未完成", digest)

    def mark_success(self, session_date: str, metadata: dict | None = None) -> Path:
        """Write the success marker atomically after all required steps."""
        unprocessed = unprocessed_pending_files(self.root)
        if unprocessed:
            names = ", ".join(p.name for p in unprocessed[:5])
            raise ReviewGuardError(
                "仍有未处理 pending 文件，拒绝写成功标记：%s" % names
            )
        current = build_fingerprint(self.root, session_date)
        marker = {
            "schema_version": SCHEMA_VERSION,
            "session_date": str(session_date)[:10],
            "status": "success",
            "completed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fingerprint": current,
            "metadata": metadata or {},
        }
        if self._lock_cm is not None:
            self._atomic_write_json(self.marker_path, marker)
        else:
            with file_lock(self.marker_path, timeout=self.lock_timeout):
                self._atomic_write_json(self.marker_path, marker)
        return self.marker_path

    def release(self) -> None:
        if self._lock_cm is not None:
            try:
                self._lock_cm.__exit__(None, None, None)
            finally:
                self._lock_cm = None

    def _atomic_write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise


def _default_session_date() -> str:
    from us_market_calendar import review_session_date

    return review_session_date().strftime("%Y-%m-%d")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Review session idempotency guard")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("mark", "check"):
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
        p.add_argument("--session", default=None)
        p.add_argument("--lock-timeout", type=float, default=120.0)
    args = parser.parse_args(argv)

    session = args.session or _default_session_date()
    guard = ReviewSessionGuard(args.root, lock_timeout=args.lock_timeout)
    if args.command == "mark":
        ready = Path(args.root) / ".review_session_ready"
        if not ready.exists():
            print("::error::review.py 未完成业务处理（缺少 .review_session_ready），拒绝写成功标记")
            return 1
        try:
            path = guard.mark_success(
                session,
                {"github_run_id": os.environ.get("GITHUB_RUN_ID", "")},
            )
        except Exception as exc:
            print("::error::无法写入 Review 成功标记：%s" % exc)
            return 1
        print("✅ Review 成功标记已写入 %s（session=%s）" % (path, session))
        return 0

    decision = guard.begin(session)
    print("ReviewGuard: %s" % decision.reason)
    guard.release()
    return 10 if decision.skip else 0


if __name__ == "__main__":
    sys.exit(main())
