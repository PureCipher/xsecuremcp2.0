"""Import one prepared business integration as a persistent, uncertified draft."""

import hashlib
import json
import sys
from pathlib import Path

from fastmcp.server.security.gateway.tool_marketplace import (
    PublishStatus,
    ToolMarketplace,
)
from purecipher.registry import _make_security_backend, _parse_manifest


def main():
    root = Path(sys.argv[1]).resolve()
    service = sys.argv[2]
    if service not in {"github", "slack", "jira", "outlook", "onedrive", "apollo"}:
        raise ValueError("Unknown integration")
    payload = json.loads((root / (service + "-submission.json")).read_text())
    manifest = _parse_manifest(payload.pop("manifest"))
    assert (
        manifest.author == "purecipher"
        and manifest.tool_name == "purecipher-" + service
    )
    for filename, digest in payload["metadata"]["bundle_sha256"].items():
        path = (root / filename).resolve()
        if (
            path.parent != root
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Source checksum mismatch")
    backend = _make_security_backend(
        Path("/run/secrets/database_url").read_text().strip()
    )
    if backend is None:
        raise RuntimeError("Persistent database is required")
    marketplace = ToolMarketplace(backend=backend)
    existing = marketplace.get_by_name(manifest.tool_name)
    if existing and (
        existing.author != "purecipher"
        or existing.status != PublishStatus.DRAFT
        or existing.attestation is not None
    ):
        raise RuntimeError(
            "Refusing to overwrite an owned, published or certified listing"
        )
    if (
        existing
        and existing.metadata.get("bundle_sha256")
        == payload["metadata"]["bundle_sha256"]
    ):
        print(manifest.tool_name, "already imported")
        return
    payload["tags"] = set(payload["tags"])
    listing = marketplace.publish(
        manifest.tool_name,
        author="purecipher",
        version=manifest.version,
        manifest=manifest,
        status=PublishStatus.DRAFT,
        **payload,
    )
    saved = ToolMarketplace(backend=backend).get_by_name(manifest.tool_name)
    assert saved and saved.status == PublishStatus.DRAFT and saved.attestation is None
    print(listing.tool_name, saved.status.value, saved.listing_id, "persisted")


if __name__ == "__main__":
    main()
