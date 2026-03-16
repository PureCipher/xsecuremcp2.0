"""Local auth storage and login helpers for publisher workflows."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from platformdirs import user_config_dir


@dataclass(frozen=True)
class PublisherLoginResult:
    """Result of a successful registry login."""

    base_url: str
    token: str
    session: dict[str, Any]
    auth_file: Path


def normalize_base_url(base_url: str) -> str:
    """Normalize a registry base URL for storage and HTTP usage."""

    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("Registry base URL is required.")
    return normalized


def default_auth_file(auth_file: str | Path | None = None) -> Path:
    """Return the default auth storage path."""

    if auth_file is not None:
        return Path(auth_file).expanduser().resolve()

    configured = os.getenv("PURECIPHER_PUBLISHER_AUTH_FILE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    config_dir = Path(user_config_dir("purecipher", appauthor=False))
    return config_dir / "publisher-auth.json"


def load_auth_tokens(auth_file: str | Path | None = None) -> dict[str, Any]:
    """Load saved registry tokens from disk."""

    path = default_auth_file(auth_file)
    if not path.exists():
        return {"registries": {}}
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        return {"registries": {}}
    registries = payload.get("registries")
    if not isinstance(registries, dict):
        return {"registries": {}}
    return {"registries": registries}


def save_auth_tokens(
    payload: dict[str, Any],
    auth_file: str | Path | None = None,
) -> Path:
    """Persist registry tokens to disk."""

    path = default_auth_file(auth_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def store_registry_token(
    *,
    base_url: str,
    token: str,
    session: dict[str, Any],
    auth_file: str | Path | None = None,
) -> Path:
    """Store a registry token keyed by normalized base URL."""

    normalized = normalize_base_url(base_url)
    payload = load_auth_tokens(auth_file)
    payload["registries"][normalized] = {
        "token": token,
        "session": session,
    }
    return save_auth_tokens(payload, auth_file)


def get_registry_token(
    *,
    base_url: str,
    auth_file: str | Path | None = None,
) -> str | None:
    """Return a stored registry token, if present."""

    normalized = normalize_base_url(base_url)
    payload = load_auth_tokens(auth_file)
    entry = payload["registries"].get(normalized)
    if not isinstance(entry, dict):
        return None
    token = entry.get("token")
    return str(token) if isinstance(token, str) and token.strip() else None


def resolve_registry_token(
    *,
    base_url: str,
    token: str | None = None,
    auth_file: str | Path | None = None,
) -> str | None:
    """Resolve a registry token from explicit input, env, or local storage."""

    if token is not None and token.strip():
        return token.strip()

    env_token = os.getenv("PURECIPHER_PUBLISHER_TOKEN", "").strip()
    if env_token:
        return env_token

    return get_registry_token(base_url=base_url, auth_file=auth_file)


def _json_error_message(response: Any) -> str:
    try:
        payload = response.json()
    except Exception:
        return f"Registry request failed with status {response.status_code}."

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, str) and error.strip():
            return error
    return f"Registry request failed with status {response.status_code}."


def login_to_registry(
    *,
    base_url: str,
    username: str,
    password: str,
    auth_file: str | Path | None = None,
    client: Any | None = None,
) -> PublisherLoginResult:
    """Authenticate with PureCipher Registry and store the issued token."""

    normalized = normalize_base_url(base_url)
    owns_client = client is None
    http_client = client or httpx.Client(
        base_url=normalized,
        headers={"accept": "application/json"},
        timeout=15.0,
    )

    try:
        response = http_client.post(
            "/registry/login",
            json={"username": username, "password": password},
        )
    finally:
        if owns_client:
            http_client.close()

    if response.status_code != 200:
        raise ValueError(_json_error_message(response))

    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Registry login returned an invalid response.")

    token = payload.get("token")
    session = payload.get("session")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Registry login response did not include a token.")
    if not isinstance(session, dict):
        raise ValueError("Registry login response did not include a session.")

    path = store_registry_token(
        base_url=normalized,
        token=token,
        session=session,
        auth_file=auth_file,
    )
    return PublisherLoginResult(
        base_url=normalized,
        token=token,
        session=session,
        auth_file=path,
    )


__all__ = [
    "PublisherLoginResult",
    "default_auth_file",
    "get_registry_token",
    "load_auth_tokens",
    "login_to_registry",
    "normalize_base_url",
    "resolve_registry_token",
    "save_auth_tokens",
    "store_registry_token",
]
