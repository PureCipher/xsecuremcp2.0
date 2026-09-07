import json
from pathlib import Path

import pytest

from scripts.prepare_huggingface import prepare, render_readme


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
    assert 'CMD ["python", "/app/space_app.py"]' in docker
    assert "COPY space_app.py index.html /app/" in docker
    assert (output / "space_app.py").is_file()
    assert "sdk: docker\napp_port: 8000" in (output / "README.md").read_text()
    assert "base_path: /\n" in (output / "README.md").read_text()
    readme = (output / "README.md").read_text()
    assert "{{" not in readme
    assert f"/commit/{commit}" in readme
    assert "| Package version | `1.0.0` |" in readme
    assert (output / ".dockerignore").read_text().startswith("*\n")
    page = (output / "index.html").read_text()
    assert '<main id="readme">' in page
    assert "base_path:" not in page
    assert "{{" not in page
    assert f"/commit/{commit}" in page
    for wheel in dist.glob("*.whl"):
        assert (output / "wheels" / wheel.name).read_bytes() == wheel.read_bytes()


def test_space_rejects_artifacts_from_a_different_commit(tmp_path: Path):
    dist = artifacts(tmp_path, "a" * 40)
    with pytest.raises(ValueError, match="tested fork commit"):
        prepare(Path(__file__).parents[1], dist, tmp_path / "space", "b" * 40)
    assert not (tmp_path / "space").exists()


def test_readme_navigation_tables_and_safe_markup():
    page = render_readme(
        "---\nsdk: docker\n---\n## Usage\n## Usage\n"
        "[Docs](https://example.com)\n\n<script>alert(1)</script>\n\n"
        "[Bad](javascript:alert(1))\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
        "{{TOC_HTML}}{{README_HTML}}",
    )
    assert 'href="#usage"' in page
    assert 'id="usage-1"' in page
    assert 'target="_blank" rel="noopener noreferrer"' in page
    assert '<div class="table-wrap"><table>' in page
    assert "<script>" not in page
    assert 'href="javascript:' not in page
    assert "sdk: docker" not in page


def test_space_readme_preserves_health_endpoint(tmp_path: Path, monkeypatch):
    from starlette.testclient import TestClient

    from scripts.huggingface_app import create_registry

    monkeypatch.setenv("PURECIPHER_SIGNING_SECRET", "readme-test-only")
    page = tmp_path / "index.html"
    page.write_text("<!doctype html><h1>Usage guide</h1>")
    registry = create_registry(page)
    with TestClient(registry.http_app(path="/mcp")) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Usage guide" in response.text
        assert client.head("/").status_code == 200
        health = client.get("/registry/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"


def test_space_requires_readme_file(tmp_path: Path):
    from scripts.huggingface_app import create_registry

    with pytest.raises(FileNotFoundError, match="Missing Space README"):
        create_registry(tmp_path / "missing.html")
