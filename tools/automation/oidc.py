"""GitHub Actions OIDC verification via the local Node runtime."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def verify_token(token: str, jwks: dict) -> dict:
    proc = subprocess.run(
        ["node", str(ROOT / "tools/automation/oidc_verify.mjs")],
        input=json.dumps({"token": token, "jwks": jwks}),
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
    with urllib.request.urlopen("https://token.actions.githubusercontent.com/.well-known/jwks", timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def oidc_context() -> dict:
    token = os.environ.get("DSH_OIDC_TOKEN", "") or _fetch_actions_token()
    if not token:
        return {"ok": False, "error": "OIDC_CONTEXT_UNVERIFIED"}
    try:
        jwks_path = os.environ.get("DSH_OIDC_JWKS_FILE", "")
        if jwks_path and Path(jwks_path).is_file():
            jwks = json.loads(Path(jwks_path).read_text(encoding="utf-8"))
        else:
            jwks = _fetch_jwks()
    except Exception:
        return {"ok": False, "error": "OIDC_CONTEXT_UNVERIFIED"}
    return verify_token(token, jwks)
