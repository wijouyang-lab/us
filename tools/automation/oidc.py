"""GitHub Actions OIDC verification. Production trusts only GitHub endpoints."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISSUER = "https://token.actions.githubusercontent.com"
JWKS_URL = "https://token.actions.githubusercontent.com/.well-known/jwks"


def verify_token(token: str, jwks: dict, expected: dict | None = None) -> dict:
    proc = subprocess.run(
        ["node", str(ROOT / "tools/automation/oidc_verify.mjs")],
        input=json.dumps({"token": token, "jwks": jwks, "expected": expected or {}}),
        text=True, capture_output=True, timeout=30,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": "OIDC_VERIFIER_FAILED"}
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"ok": False, "error": "OIDC_VERIFIER_INVALID"}


def _fetch_actions_token() -> str:
    url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not url or not bearer:
        return ""
    import urllib.parse
    import urllib.request
    separator = "&" if "?" in url else "?"
    req = urllib.request.Request(
        url + separator + urllib.parse.urlencode({"audience": "dsh-publisher"}),
        headers={"Authorization": f"Bearer {bearer}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8")).get("value", "")


def _fetch_jwks() -> dict:
    import urllib.request
    with urllib.request.urlopen(JWKS_URL, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def oidc_context() -> dict:
    # Production only: no token/JWKS override environment variables.
    try:
        token = _fetch_actions_token()
    except Exception:
        return {"ok": False, "error": "OIDC_CONTEXT_UNVERIFIED"}
    if not token:
        return {"ok": False, "error": "OIDC_CONTEXT_UNVERIFIED"}
    try:
        jwks = _fetch_jwks()
    except Exception:
        return {"ok": False, "error": "OIDC_CONTEXT_UNVERIFIED"}
    result = verify_token(token, jwks, {"run_id": os.environ.get("GITHUB_RUN_ID", "")})
    return result
