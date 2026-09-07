"""Publish tested Space artifacts while removing local-only repository files."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


def is_local_only(path: str) -> bool:
    parts = PurePosixPath(path)
    return ".cursor" in parts.parts or (
        parts.suffix == ".md" and parts.name != "README.md"
    )


def publish(api: Any, folder: Path, commit: str) -> Any:
    build = json.loads((folder / "build.json").read_text())
    if (
        not re.fullmatch(r"[a-f0-9]{40}", commit)
        or build["commit"] != commit
        or build["repository"] != "PureCipher/xsecuremcp2.0"
        or not (folder / "README.md").is_file()
    ):
        raise ValueError("Space artifacts must match the tested fork commit")
    repository = "purecipher/xsecuremcp"
    remote_files = api.list_repo_files(repository, repo_type="space")
    deletions = sorted(path for path in remote_files if is_local_only(path))
    ignored = [
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*")
        if path.is_file() and is_local_only(path.relative_to(folder).as_posix())
    ]
    # One commit replaces the wheels and removes stale local-only files.
    # Every README.md is retained, including READMEs outside the upload folder.
    return api.upload_folder(
        repo_id=repository,
        repo_type="space",
        folder_path=str(folder),
        delete_patterns=["wheels/*.whl", *deletions],
        ignore_patterns=ignored,
        commit_message=f"Deploy tested PureCipher build {commit}",
    )


if __name__ == "__main__":
    import os

    from huggingface_hub import HfApi

    publish(HfApi(), Path("hf-space"), os.environ["GITHUB_SHA"])
