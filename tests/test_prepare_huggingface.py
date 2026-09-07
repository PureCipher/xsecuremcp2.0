import json
from pathlib import Path

import pytest

from scripts.prepare_huggingface import prepare


def artifacts(tmp_path: Path, commit: str) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "build.json").write_text(
        json.dumps(
            {
                "repository": "PureCipher/xsecuremcp2.0",
                "commit": commit,
                "version": "1.0.0",
            }
        )
    )
    (dist / "constraints.txt").write_text("mcp==1.0.0\n")
    for name in ["fastmcp", "fastmcp_slim", "fastmcp_remote", "fastmcp_tasks"]:
        (dist / f"{name}-1.0.0-py3-none-any.whl").write_bytes(b"tested wheel")
    return dist


def test_space_installs_tested_wheels_as_non_root(tmp_path: Path):
    commit = "a" * 40
    dist = artifacts(tmp_path, commit)
    output = tmp_path / "space"
    prepare(Path(__file__).parents[1], dist, output, commit)
    docker = (output / "Dockerfile").read_text()
    assert "COPY wheels /tmp/wheels" in docker
    assert "COPY --from=build" not in docker
    assert "uv build" not in docker
    assert "USER 1000" in docker
    assert '"--port", "8000"' in docker
    assert "sdk: docker\napp_port: 8000" in (output / "README.md").read_text()
    assert (output / ".dockerignore").read_text().startswith("*\n")
    for wheel in dist.glob("*.whl"):
        assert (output / "wheels" / wheel.name).read_bytes() == wheel.read_bytes()


def test_space_rejects_artifacts_from_a_different_commit(tmp_path: Path):
    dist = artifacts(tmp_path, "a" * 40)
    with pytest.raises(ValueError, match="tested fork commit"):
        prepare(Path(__file__).parents[1], dist, tmp_path / "space", "b" * 40)
    assert not (tmp_path / "space").exists()
