import copy
import json

import pytest

from purecipher import source_traceability as source
from purecipher.release_candidates import decide
from tests.server.security.test_purecipher_registry import _manifest
from tests.server.security.test_release_candidates import setup


def evidence():
    hashes = source.runtime_hashes()
    return dict(
        repository=source.REPOSITORY, commit="a" * 40, paths=list(hashes), sha256=hashes
    )


def test_missing_build_and_declarations(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "BUILD_FILE", tmp_path / "build.json")
    assert source.describe({})["status"] == "not_verified"
    assert source.describe({"source_evidence": evidence()})["status"] == "not_verified"
    # Publisher metadata can never impersonate operator build identity.
    assert (
        source.describe({"running": evidence(), "source_evidence": evidence()})[
            "running"
        ]
        is None
    )


def test_comparison_and_tampered_running_files(tmp_path, monkeypatch):
    path = tmp_path / "build.json"
    monkeypatch.setattr(source, "BUILD_FILE", path)
    data = evidence()
    path.write_text(json.dumps(data))
    assert source.describe({"source_evidence": data})["status"] == "match"
    changed = copy.deepcopy(data)
    changed["commit"] = "b" * 40
    assert source.describe({"source_evidence": changed})["status"] == "mismatch"
    changed = copy.deepcopy(data)
    changed["sha256"][changed["paths"][0]] = "0" * 64
    assert source.describe({"source_evidence": changed})["status"] == "mismatch"
    changed["sha256"] = {}
    assert source.describe({"source_evidence": changed})["status"] == "not_verified"
    changed = copy.deepcopy(data)
    changed["repository"] = "https://github.com/another/project"
    assert source.describe({"source_evidence": changed})["status"] == "not_verified"
    monkeypatch.setattr(source, "runtime_hashes", lambda: {})
    assert source.describe({"source_evidence": data})["running"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("repository", "https://user:secret@github.com/repo"),
        ("repository", "https://github.com/repo?token=secret"),
        ("commit", "main"),
        ("paths", ["../../etc/passwd"]),
        ("paths", ["/etc/passwd"]),
        ("sha256", {"unknown": "a" * 64}),
        ("sha256", {"src/purecipher/consumer_runtime.py": "bad"}),
    ],
)
def test_invalid_evidence(field, value):
    data = evidence()
    data[field] = value
    with pytest.raises(ValueError):
        source.validate_source(data)


def test_snapshot_preserves_evidence_and_rejects_tampering():
    registry, key = setup()
    data = evidence()
    result = registry.submit_tool(
        _manifest(author="alice", version="1.1.0"),
        metadata={"source_evidence": data},
        changelog="Records exact source",
    )
    record = registry._marketplace().get(key).release_records[0]
    assert record["snapshot"]["metadata"]["source_evidence"] == data
    assert not registry.get_verified_tool("weather-lookup")["source_deployment"][
        "submitted"
    ]
    decide(
        registry, key, result.release_candidate["id"], "approve", "reviewer", "Checked"
    )
    assert (
        registry.get_verified_tool("weather-lookup")["source_deployment"]["submitted"]
        == data
    )
    assert record["snapshot_digest"]
    next_result = registry.submit_tool(
        _manifest(author="alice", version="1.2.0"),
        metadata={"source_evidence": data},
        changelog="Next release",
    )
    registry._marketplace().get(key).release_records[-1]["snapshot"]["metadata"][
        "source_evidence"
    ]["commit"] = "b" * 40
    with pytest.raises(ValueError, match="integrity"):
        decide(
            registry,
            key,
            next_result.release_candidate["id"],
            "approve",
            "reviewer",
            "Checked",
        )
