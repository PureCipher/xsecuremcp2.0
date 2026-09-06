"""Authenticated, read-only Hugging Face Hub metadata; no inference or downloads."""

import os
from urllib.parse import urlsplit

from fastmcp.server.auth.providers.huggingface import HuggingFaceProvider

from .common import ANNOTATIONS, page_size, read_json, resource_id, secured

TOOLS = {"hf_search_models", "hf_get_model", "hf_search_datasets", "hf_get_dataset"}
SCOPES = ["openid", "profile", "read-repos"]
BASE = "https://huggingface.co/api/"


def create_oauth(client_id: str, client_secret: str, base_url: str):
    url = urlsplit(base_url)
    if not client_id or not client_secret:
        raise ValueError("Hugging Face OAuth client credentials are required")
    if (
        url.scheme != "https"
        or not url.netloc
        or url.username
        or url.query
        or url.fragment
    ):
        raise ValueError("An HTTPS callback base URL is required")
    return HuggingFaceProvider(
        client_id=client_id,
        client_secret=client_secret,
        base_url=base_url,
        required_scopes=SCOPES,
        valid_scopes=SCOPES,
        forward_resource=False,
    )


def repo_path(repo: str) -> str:
    parts = repo.split("/")
    if len(parts) not in (1, 2):
        raise ValueError("Expected a repository name or owner/name")
    return "/".join(resource_id(part) for part in parts)


def create_server(auth):
    server = secured("huggingface", auth, TOOLS)

    @server.tool(annotations=ANNOTATIONS)
    async def hf_search_models(search: str, limit: int = 20) -> dict:
        """Search model metadata on Hugging Face Hub."""
        return await read_json(
            BASE, "models", {"search": search, "limit": page_size(limit)}
        )

    @server.tool(annotations=ANNOTATIONS)
    async def hf_get_model(repository: str) -> dict:
        """Read model metadata without downloading or executing model code."""
        return await read_json(BASE, "models/" + repo_path(repository))

    @server.tool(annotations=ANNOTATIONS)
    async def hf_search_datasets(search: str, limit: int = 20) -> dict:
        """Search dataset metadata without downloading dataset contents."""
        return await read_json(
            BASE, "datasets", {"search": search, "limit": page_size(limit)}
        )

    @server.tool(annotations=ANNOTATIONS)
    async def hf_get_dataset(repository: str) -> dict:
        """Read dataset metadata."""
        return await read_json(BASE, "datasets/" + repo_path(repository))

    return server


if __name__ == "__main__":
    create_server(
        create_oauth(
            os.environ.get("PURECIPHER_HF_CLIENT_ID", ""),
            os.environ.get("PURECIPHER_HF_CLIENT_SECRET", ""),
            os.environ.get("PURECIPHER_HF_BASE_URL", ""),
        )
    ).run(transport="http", host="127.0.0.1", port=9118)
