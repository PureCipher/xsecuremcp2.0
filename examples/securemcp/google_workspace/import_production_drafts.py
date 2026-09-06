"""Operator-only draft import; never certifies or publishes Google integrations.

Run with the production runtime, a mounted database secret and uploaded package.
Uses the marketplace persistence API; restart the registry afterwards to reload.
"""

import hashlib
import json
import sys
from pathlib import Path

from fastmcp.server.security.gateway.tool_marketplace import (
    PublishStatus,
    ToolMarketplace,
)
from purecipher.registry import _make_security_backend, _parse_manifest


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    database = Path("/run/secrets/database_url").read_text().strip()
    backend = _make_security_backend(database)
    if backend is None:
        raise RuntimeError("A persistent production backend is required")
    marketplace = ToolMarketplace(backend=backend)
    for service in ("gmail", "docs", "tasks", "calendar"):
        payload = json.loads((root / f"{service}-submission.json").read_text())
        manifest = _parse_manifest(payload.pop("manifest"))
        metadata = payload["metadata"]
        digest = hashlib.sha256(
            (root / metadata["source_file"]).read_bytes()
        ).hexdigest()
        if digest != metadata["source_sha256"]:
            raise RuntimeError("Uploaded source checksum mismatch")
        existing = marketplace.get_by_name(manifest.tool_name)
        if existing is not None:
            if (
                existing.author not in {"PureCipher", "purecipher"}
                or existing.status != PublishStatus.DRAFT
            ):
                raise RuntimeError(
                    "Refusing to overwrite a non-draft or another publisher"
                )
            if (
                existing.metadata.get("source_sha256") == digest
                and existing.author == "purecipher"
            ):
                print(manifest.tool_name, "already imported", existing.status.value)
                continue
        payload["tags"] = set(payload["tags"])
        listing = marketplace.publish(
            manifest.tool_name,
            manifest=manifest,
            version=manifest.version,
            author="purecipher",
            status=PublishStatus.DRAFT,
            **payload,
        )
        assert listing.attestation is None
        print(listing.tool_name, listing.status.value, listing.listing_id)
    # Read back via a new store instance to verify persistence, not just memory.
    reloaded = ToolMarketplace(backend=backend)
    for service in ("gmail", "docs", "tasks", "calendar"):
        listing = reloaded.get_by_name(f"purecipher-google-{service}")
        assert listing is not None and listing.status == PublishStatus.DRAFT
    print("Verified four persistent drafts; no certification or public publication.")


if __name__ == "__main__":
    main()
