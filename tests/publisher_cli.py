"""Test-only Publisher CLI entry that bypasses OIDC/lock gates.

Production `python -m tools.automation.publisher` always requires OIDC and the
unimplemented lock. Tests use this harness to exercise publishing behavior.
"""
import sys

from tools.automation import publisher

publisher._TEST_HARNESS = True
raise SystemExit(publisher.main())
