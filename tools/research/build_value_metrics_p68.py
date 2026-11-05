"""Build Value V1 issuer market-cap and metric readiness (P6.8).

The audit module contains the shared parser and status rules; this entry point is
the stable batch builder used by the workflow.
"""
from tools.research.audit_value_market_cap_p68 import main

if __name__ == "__main__":
    raise SystemExit(main())
