#!/usr/bin/env python3
"""Contact User-Agent validation without storing or logging PII."""
from __future__ import annotations

import os
import re
from typing import Mapping

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PLACEHOLDER_DOMAINS = {"example.com", "example.org", "example.net", "test.com", "localhost"}
_PLACEHOLDER_LOCAL = {"test", "user", "your", "name", "contact", "noreply", "no-reply"}


def validate_user_agent(value: str | None, *, require_email: bool = False) -> str:
    if value is None:
        raise ValueError("User-Agent is not configured")
    agent = value.strip()
    if not agent or len(agent) > 256 or any(c in agent for c in "\r\n\t"):
        raise ValueError("User-Agent must be a single non-empty header value")
    if _has_placeholder_email(agent):
        raise ValueError("User-Agent contains a placeholder contact")
    if require_email and not has_contact_email(agent):
        raise ValueError("User-Agent must contain a real contact email")
    return agent


def _has_placeholder_email(agent: str) -> bool:
    for token in re.findall(r"[^\s<>()]+@[^\s<>()]+", agent):
        email = token.strip(".,;:")
        if not _EMAIL.match(email):
            continue
        local, domain = email.rsplit("@", 1)
        if domain.lower() in _PLACEHOLDER_DOMAINS or local.lower() in _PLACEHOLDER_LOCAL:
            return True
    return False


def has_contact_email(agent: str | None) -> bool:
    if not agent:
        return False
    for token in re.findall(r"[^\s<>()]+@[^\s<>()]+", agent):
        email = token.strip(".,;:")
        if not _EMAIL.match(email):
            continue
        local, domain = email.rsplit("@", 1)
        if domain.lower() in _PLACEHOLDER_DOMAINS or local.lower() in _PLACEHOLDER_LOCAL:
            continue
        return True
    return False


def load_user_agent(env: Mapping[str, str], names: tuple[str, ...], *,
                    require_email: bool = False) -> str | None:
    for name in names:
        value = env.get(name)
        if value:
            return validate_user_agent(value, require_email=require_email)
    return None


def redact_user_agent(agent: str | None) -> str | None:
    if not agent:
        return None
    for token in re.findall(r"[^\s<>()]+@[^\s<>()]+", agent):
        email = token.strip(".,;:")
        if _EMAIL.match(email):
            local, domain = email.rsplit("@", 1)
            return agent.replace(email, f"{local[:1]}***@{domain}")
    return agent
