"""Test-only Publisher entry.

Requires a repository and `gh` binary under the system temporary directory, so
it cannot perform real GitHub writes from an arbitrary checkout. Production
`python -m tools.automation.publisher` remains fail-closed.
"""
import shutil
import sys
import tempfile
from pathlib import Path

from tools.automation import publisher


def _under_temp(path: str) -> bool:
    try:
        return Path(path).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    except Exception:
        return False


def main() -> int:
    try:
        repo = sys.argv[sys.argv.index("--repo") + 1]
    except (ValueError, IndexError):
        print("BLOCKED:TEST_REPO_REQUIRED")
        return 3
    gh = shutil.which("gh") or ""
    if not _under_temp(repo) or not gh or not _under_temp(gh):
        print("BLOCKED:TEST_ENTRY_OUTSIDE_TEMP")
        return 3
    return publisher._publish_main()


raise SystemExit(main())
