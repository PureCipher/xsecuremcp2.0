"""Prepare a pip-installable bundle for the fork's rolling GitHub Release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

PACKAGES = {"fastmcp", "fastmcp-slim", "fastmcp-remote", "fastmcp-tasks"}
REPOSITORY = "PureCipher/xsecuremcp2.0"
RELEASE_TAG = "build-latest"


def prepare_release(dist: Path, commit: str) -> str:
    wheels = sorted(dist.glob("*.whl"))
    versions: set[str] = set()
    names: set[str] = set()
    for wheel in wheels:
        with ZipFile(wheel) as archive:
            metadata_files = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_files) != 1:
                raise ValueError(f"Invalid wheel metadata: {wheel.name}")
            metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
        names.add(str(metadata["Name"]).replace("_", "-").lower())
        versions.add(str(metadata["Version"]))
    if names != PACKAGES or len(wheels) != len(PACKAGES) or len(versions) != 1:
        raise ValueError("Build exactly four workspace wheels with matching versions")
    if not (dist / "constraints.txt").is_file():
        raise ValueError(
            "Export locked runtime constraints before preparing the release"
        )
    version = versions.pop()
    base_url = f"https://github.com/{REPOSITORY}/releases/download/{RELEASE_TAG}"
    requirements = [f"-c {base_url}/constraints.txt"]
    for wheel in wheels:
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        requirements.append(f"{base_url}/{quote(wheel.name)}#sha256={digest}")
    (dist / "requirements.txt").write_text("\n".join(requirements) + "\n")
    (dist / "build.json").write_text(
        json.dumps(
            {"repository": REPOSITORY, "commit": commit, "version": version}, indent=2
        )
        + "\n"
    )
    with ZipFile(dist / "xsecuremcp2.0-python.zip", "w", ZIP_DEFLATED) as archive:
        for path in [*wheels, dist / "constraints.txt", dist / "build.json"]:
            archive.write(path, path.name)
        archive.writestr(
            "INSTALL.txt",
            "Extract this archive into an empty directory, then run:\n"
            "python -m pip install --constraint constraints.txt ./*.whl\n"
            "\nThe four matching wheels contain the PureCipher fork, not PyPI FastMCP.\n",
        )
    payloads = sorted(
        p for p in dist.iterdir() if p.is_file() and p.name != "SHA256SUMS"
    )
    (dist / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
            for p in payloads
        )
    )
    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    built_version = prepare_release(args.dist, args.commit)
    print(built_version)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a") as stream:
            stream.write(f"version={built_version}\n")
