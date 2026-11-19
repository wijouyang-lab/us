"""Redact execution credentials from public read models.

Only the authenticated local API may return a confirmation token. Public
snapshots and the read-only account API never contain tokens or auth secrets.
"""
from __future__ import annotations
import re

SECRET_KEY = re.compile(r"(confirm.*token|confirmation.*token|csrf|api[_-]?key|secret|password|authorization)", re.I)


def redact(value):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if SECRET_KEY.search(str(k)):
                continue
            out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def public_order(order: dict) -> dict:
    keep = ("order_id", "client_order_id", "status", "ticker", "side", "shares",
            "reference_price", "price_asof", "price_source", "price_type", "strategy",
            "slippage_bps", "created_at", "filled_at", "fill")
    return redact({k: order.get(k) for k in keep if k in order})
