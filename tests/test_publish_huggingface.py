import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.publish_huggingface import is_local_only, publish


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("README.md", False),
        ("docs/community/README.md", False),
        ("docs/guide.mdx", False),
        ("docs/guide.md", True),
        ("CLAUDE.md", True),
        ("README_OPENAPI.md", True),
        (".cursor/rules/core.mdc", True),
        ("docs/.cursor/README.md", True),
        ("src/cursor.py", False),
    ],
)
def test_local_only_selection(path: str, expected: bool):
    assert is_local_only(path) is expected


def test_publish_preserves_remote_readmes_and_excludes_local_files(tmp_path: Path):
    commit = "a" * 40
    (tmp_path / "build.json").write_text(
        json.dumps({"commit": commit, "repository": "PureCipher/xsecuremcp2.0"})
    )
    (tmp_path / "README.md").write_text("Public guide")
    (tmp_path / "notes.md").write_text("Private notes")
    api = Mock()
    api.list_repo_files.return_value = [
        "README.md",
        "docs/community/README.md",
        "docs/.cursor/rules/core.mdc",
        "docs/notes.md",
        "Dockerfile",
        "docs/guide.mdx",
    ]
    publish(api, tmp_path, commit)
    args = api.upload_folder.call_args.kwargs
    assert args["delete_patterns"] == [
        "wheels/*.whl",
        "docs/.cursor/rules/core.mdc",
        "docs/notes.md",
    ]
    assert args["ignore_patterns"] == ["notes.md"]
    assert args["repo_id"] == "purecipher/xsecuremcp"
    with pytest.raises(ValueError, match="tested fork commit"):
        publish(api, tmp_path, "b" * 40)
    assert api.upload_folder.call_count == 1
