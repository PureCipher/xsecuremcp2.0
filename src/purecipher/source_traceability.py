"""Publisher source declarations and independently collected registry build evidence.

A match is a byte/commit comparison, not certification or upstream verification.
Only the fixed consumer module bundle is inspected; publisher paths are never read.
"""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
BUILD_FILE = ROOT / "_build_identity.json"
REPOSITORY = "https://github.com/PureCipher/xsecuremcp2.0"


def validate_source(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {
        "repository",
        "commit",
        "paths",
        "sha256",
    }:
        raise ValueError(
            "Source evidence must contain repository, commit, paths, and optional sha256"
        )
    repo = value.get("repository", "")
    if not isinstance(repo, str) or len(repo) > 500:
        raise ValueError("Provide a public HTTPS repository URL")
    url = urlsplit(repo)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or any(c.isspace() for c in repo)
    ):
        raise ValueError(
            "Provide a public HTTPS repository URL without credentials, query, or fragment"
        )
    commit = value.get("commit", "")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ValueError("Provide the full 40-character source commit")
    paths = value.get("paths")
    if not isinstance(paths, list) or not 1 <= len(paths) <= 100:
        raise ValueError("Provide 1 to 100 implementation paths")
    for path in paths:
        if (
            not isinstance(path, str)
            or len(path) > 300
            or not re.fullmatch(r"[a-zA-Z0-9_./-]+", path)
            or path.startswith("/")
            or any(p in {"", ".", ".."} for p in path.split("/"))
        ):
            raise ValueError(
                "Implementation paths must be relative paths without traversal"
            )
    if len(set(paths)) != len(paths):
        raise ValueError("Implementation paths must be unique")
    hashes = value.get("sha256", {})
    if not isinstance(hashes, dict) or set(hashes) - set(paths):
        raise ValueError("Artifact hashes must refer to declared implementation paths")
    if any(
        not isinstance(h, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", h)
        for h in hashes.values()
    ):
        raise ValueError("Artifact hashes must be SHA-256 hex digests")
    return {
        "repository": repo.rstrip("/"),
        "commit": commit.lower(),
        "paths": paths,
        "sha256": {p: h.lower() for p, h in hashes.items()},
    }


def runtime_hashes():
    return {
        "src/purecipher/" + p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(ROOT.glob("consumer_*.py"))
        if p.is_file() and not p.is_symlink()
    }


def running_build():
    try:
        data = json.loads(BUILD_FILE.read_text())
        source = validate_source(data)
        if source is None or source["repository"] != REPOSITORY:
            return None
        current = runtime_hashes()
        if (
            not current
            or set(source["paths"]) != set(current)
            or source["sha256"] != current
        ):
            return None
        return source
    except (OSError, ValueError, TypeError):
        return None


def describe(metadata):
    metadata = metadata or {}
    build = running_build()
    result = {
        "status": "not_verified",
        "scope": "Registry consumer runtime source comparison",
        "submitted": None,
        "running": build,
        "reason": "No complete source declaration was submitted.",
        "upstream_status": "not_verified",
    }
    try:
        source = validate_source(metadata.get("source_evidence"))
    except (ValueError, TypeError):
        result["reason"] = "The stored source declaration is incomplete or invalid."
        return result
    result["submitted"] = source
    if not source:
        return result
    if not build:
        result["reason"] = (
            "Running build identity is unavailable or its recorded hashes no longer match the installed files."
        )
    elif source["repository"] != build["repository"]:
        result["reason"] = (
            "This repository is not the registry runtime; its deployment has not been independently verified."
        )
    elif set(source["sha256"]) != set(build["sha256"]) or set(source["paths"]) != set(
        build["paths"]
    ):
        result["reason"] = (
            "Comparison requires hashes for the complete registry consumer runtime bundle."
        )
    elif source["commit"] != build["commit"] or source["sha256"] != build["sha256"]:
        result.update(
            status="mismatch",
            reason="Submitted commit or artifact hashes differ from the running registry build.",
        )
    else:
        result.update(
            status="match",
            reason="Submitted commit and complete consumer bundle hashes match the running registry build. This does not certify behavior or an external upstream.",
        )
    return result


if __name__ == "__main__":
    # Run inside the source checkout during image construction, before deployment.
    import subprocess

    checkout = ROOT.parents[1]
    commit = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        [
            "git",
            "-C",
            str(checkout),
            "status",
            "--porcelain",
            "--",
            "src/purecipher/consumer_*.py",
        ],
        text=True,
    )
    if dirty:
        raise SystemExit("Cannot record build identity with modified consumer sources")
    hashes = runtime_hashes()
    BUILD_FILE.write_text(
        json.dumps(
            validate_source(
                {
                    "repository": REPOSITORY,
                    "commit": commit,
                    "paths": list(hashes),
                    "sha256": hashes,
                }
            ),
            indent=2,
        )
        + "\n"
    )
