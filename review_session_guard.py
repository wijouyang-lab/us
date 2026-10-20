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
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pending_store import file_lock


MARKER_NAME = "review_session_state.json"
SCHEMA_VERSION = 1
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


def pending_payload_fingerprint(root: str | Path, session_date: str) -> str:
    """Hash normalized event rows, independent of .csv -> .processed rename."""
    root = Path(root)
    day = str(session_date)[:10].replace("-", "")
    patterns = [
        str(root / ("us_stocks_pending_%s.csv" % day)),
        str(root / ("us_stocks_pending_%s.csv.processed" % day)),
    ]
    merged: dict[tuple[str, str, str], dict[str, str]] = {}
    for pattern in patterns:
        for name in sorted(glob.glob(pattern)):
            path = Path(name)
            # Later .processed rows represent the consumed snapshot.
            merged.update(_read_pending_rows(path))
    ordered = [merged[key] for key in sorted(merged)]
    payload = json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha_bytes(payload.encode("utf-8"))


def ledger_fingerprint(root: str | Path) -> dict[str, str]:
    root = Path(root)
    return {name: _sha_file(root / name) for name in LEDGER_FILES}


def build_fingerprint(root: str | Path, session_date: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_date": str(session_date)[:10],
        "pending": pending_payload_fingerprint(root, session_date),
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
            if same_session and same_fingerprint:
                return GuardDecision(True, "同一交易日、输入与账本指纹未变化，已成功处理", digest)
            if same_session:
                return GuardDecision(False, "同一交易日但输入/账本已变化，需要安全重跑", digest)
            return GuardDecision(False, "新的交易日", digest)
        return GuardDecision(False, "无成功标记或上次未完成", digest)

    def mark_success(self, session_date: str, metadata: dict | None = None) -> Path:
        """Write the success marker atomically after all required steps."""
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
