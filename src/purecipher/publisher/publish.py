"""Registry preflight and publish helpers for publisher projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from purecipher.publisher.auth import normalize_base_url, resolve_registry_token
from purecipher.publisher.config import load_publisher_config
from purecipher.publisher.package import (
    PublisherPackageResult,
    build_submission_payload,
    package_project,
)


@dataclass(frozen=True)
class PublisherPublishResult:
    """Result of a registry publish attempt."""

    base_url: str
    tool_name: str
    accepted: bool
    status_code: int
    listing_status: str
    listing_url: str
    catalog_url: str
    review_url: str | None
    next_url: str
    preflight: dict[str, Any]
    response_payload: dict[str, Any]
    package: PublisherPackageResult

    def to_dict(self) -> dict[str, Any]:
        """Serialize for CLI JSON output."""

        return {
            "base_url": self.base_url,
            "tool_name": self.tool_name,
            "accepted": self.accepted,
            "status_code": self.status_code,
            "listing_status": self.listing_status,
            "listing_url": self.listing_url,
            "catalog_url": self.catalog_url,
            "review_url": self.review_url,
            "next_url": self.next_url,
            "preflight": self.preflight,
            "response_payload": self.response_payload,
            "package": self.package.to_dict(),
        }


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


def publish_project(
    project_root: str | Path = ".",
    *,
    base_url: str | None = None,
    auth_file: str | Path | None = None,
    token: str | None = None,
    allow_incomplete: bool = False,
    output_dir: str | Path | None = None,
    client: Any | None = None,
) -> PublisherPublishResult:
    """Run registry preflight and publish a project."""

    root = Path(project_root).resolve()
    config = load_publisher_config(root / "purecipher.toml")
    normalized_base_url = normalize_base_url(base_url or config.registry.base_url)
    packaged = package_project(root, output_dir=output_dir)

    if packaged.check.issues and not allow_incomplete:
        issue_summary = " ".join(packaged.check.issues)
        raise ValueError(
            "Publisher project is not ready to publish. "
            f"Run `purecipher-publisher check` first. {issue_summary}"
        )

    submission_payload = build_submission_payload(config)
    preflight_payload = {
        "manifest": submission_payload["manifest"],
        "display_name": submission_payload["display_name"],
        "categories": submission_payload["categories"],
        "metadata": submission_payload["metadata"],
        "requested_level": submission_payload["requested_level"],
    }
    resolved_token = resolve_registry_token(
        base_url=normalized_base_url,
        token=token,
        auth_file=auth_file,
    )
    headers = {"accept": "application/json"}
    if resolved_token:
        headers["authorization"] = f"Bearer {resolved_token}"

    owns_client = client is None
    http_client = client or httpx.Client(
        base_url=normalized_base_url,
        headers=headers,
        timeout=15.0,
    )

    try:
        preflight_response = http_client.post(
            "/registry/preflight",
            json=preflight_payload,
            headers=headers,
        )
        if preflight_response.status_code != 200:
            raise ValueError(_json_error_message(preflight_response))
        preflight = preflight_response.json()
        if not isinstance(preflight, dict):
            raise ValueError("Registry preflight returned an invalid response.")

        if not preflight.get("ready_for_publish") and not allow_incomplete:
            raise ValueError(
                str(
                    preflight.get("summary")
                    or "Registry preflight did not approve publishing."
                )
            )

        submit_response = http_client.post(
            "/registry/submit",
            json=submission_payload,
            headers=headers,
        )
    finally:
        if owns_client:
            http_client.close()

    try:
        response_payload = submit_response.json()
    except Exception as exc:
        raise ValueError(
            f"Registry publish returned an invalid response (status {submit_response.status_code})."
        ) from exc

    if not isinstance(response_payload, dict):
        raise ValueError("Registry publish returned an invalid response.")

    accepted = bool(response_payload.get("accepted"))
    if submit_response.status_code >= 400:
        raise ValueError(_json_error_message(submit_response))

    listing = response_payload.get("listing")
    listing_status = (
        str(listing.get("status") or "unknown")
        if isinstance(listing, dict)
        else "unknown"
    )
    catalog_url = f"{normalized_base_url}/registry"
    listing_url = (
        f"{normalized_base_url}/registry/listings/{config.project.name}"
        if accepted
        else catalog_url
    )
    review_url = (
        f"{normalized_base_url}/registry/review"
        if listing_status == "pending_review"
        else None
    )
    next_url = review_url or listing_url
    return PublisherPublishResult(
        base_url=normalized_base_url,
        tool_name=config.project.name,
        accepted=accepted,
        status_code=submit_response.status_code,
        listing_status=listing_status,
        listing_url=listing_url,
        catalog_url=catalog_url,
        review_url=review_url,
        next_url=next_url,
        preflight=preflight,
        response_payload=response_payload,
        package=packaged,
    )


__all__ = [
    "PublisherPublishResult",
    "publish_project",
]
