"""Test-only Publisher entry that calls the internal publish function.

It bypasses only the production main() gates; no production module variable or
environment switch is used. Production `python -m tools.automation.publisher`
remains fail-closed.
"""
import sys

from tools.automation import publisher

raise SystemExit(publisher._publish_main())
