"""Canonical actor identity resolution for SecureMCP middleware."""

from __future__ import annotations

import hashlib

from fastmcp.server.auth.auth import AccessToken


def principal_id_from_access_token(token: AccessToken | None) -> str | None:
    """Return a stable, non-secret identity for a verified access token.

    Verified issuer/subject claims are preferred because they survive token
    rotation. Opaque tokens fall back to a digest of the complete token; using
    the whole value avoids the collisions caused by redacted token prefixes.
    """
    if token is None:
        return None

    claims = token.claims or {}
    issuer = str(claims.get("iss") or "")
    subject = str(token.subject or claims.get("sub") or "")
    if subject:
        identity = f"subject\0{issuer}\0{subject}"
    else:
        identity = f"token\0{token.token}"

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"principal:{digest}"


__all__ = ["principal_id_from_access_token"]
