"""Apply operator-reviewed names/categories to PureCipher's preparation drafts."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastmcp.server.security.gateway.tool_marketplace import (
    PublishStatus,
    ToolCategory,
    ToolMarketplace,
)
from purecipher.registry import _make_security_backend


def main():
    root = Path(sys.argv[1]).resolve()
    categories = json.loads((root / "listing-categories.json").read_text())
    backend = _make_security_backend(
        Path("/run/secrets/database_url").read_text().strip()
    )
    if backend is None:
        raise RuntimeError("Persistent storage is required")
    marketplace = ToolMarketplace(backend=backend)
    changes = []
    # Validate the entire set before making any changes.
    for service, assigned in categories.items():
        listing = marketplace.get_by_name("purecipher-" + service)
        if (
            not listing
            or listing.author != "purecipher"
            or listing.status != PublishStatus.DRAFT
            or listing.attestation is not None
        ):
            raise ValueError("Expected an owned uncertified draft: " + service)
        path = root / (service + "-submission.json")
        if service.startswith("google-"):
            path = (
                root.parent
                / "google_workspace"
                / (service.removeprefix("google-") + "-submission.json")
            )
        payload = json.loads(path.read_text())
        name = payload["display_name"]
        selected = {ToolCategory(value) for value in assigned}
        metadata = {
            **listing.metadata,
            **{
                key: payload["metadata"][key]
                for key in ("configuration", "server_type")
            },
        }
        if (
            listing.display_name != name
            or listing.categories != selected
            or listing.metadata != metadata
        ):
            changes.append((listing, name, selected, metadata))
    for listing, name, selected, metadata in changes:
        listing.display_name, listing.categories = name, selected
        listing.metadata = metadata
        listing.updated_at = datetime.now(timezone.utc)
        marketplace._persist_listing(listing)
    saved = ToolMarketplace(backend=backend)
    for service, assigned in categories.items():
        listing = saved.get_by_name("purecipher-" + service)
        assert listing and listing.status == PublishStatus.DRAFT
        assert {category.value for category in listing.categories} == set(assigned)
        assert not listing.display_name.startswith("PureCipher ")
    print(
        f"Verified {len(categories)} persistent categorized drafts; updated {len(changes)} presentations; IDs unchanged"
    )


if __name__ == "__main__":
    main()
