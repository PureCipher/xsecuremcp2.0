"""Tests for Iter 14.21 — JSON-on-disk policy bundle loader."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest


def _write_bundle(tmp_dir: Path, name: str, payload: dict) -> Path:
    """Helper: write ``name.json`` with ``payload`` and return the path."""
    path = tmp_dir / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_payload(bundle_id: str = "custom-bundle") -> dict:
    """Helper: return the minimum-viable bundle JSON payload."""
    return {
        "bundle_id": bundle_id,
        "title": "Custom Bundle",
        "summary": "A short summary",
        "description": "A longer description",
        "risk_posture": "balanced",
        "recommended_environments": ["staging"],
        "tags": ["custom"],
        "providers": [
            {
                "type": "rate_limit",
                "policy_id": "rl-1",
                "max_requests": 100,
                "window_seconds": 60,
            }
        ],
    }


class TestLoadBundlesFromDisk:
    def test_valid_json_loads(self, tmp_path: Path) -> None:
        from fastmcp.server.security.policy.workbench import (
            load_bundles_from_disk,
        )

        _write_bundle(tmp_path, "ok", _valid_payload("custom-ok"))
        bundles = load_bundles_from_disk(tmp_path)
        assert len(bundles) == 1
        assert bundles[0].bundle_id == "custom-ok"
        assert bundles[0].title == "Custom Bundle"
        assert bundles[0].providers[0]["type"] == "rate_limit"

    def test_unset_path_returns_empty(self) -> None:
        from fastmcp.server.security.policy.workbench import (
            load_bundles_from_disk,
        )

        assert load_bundles_from_disk(None) == ()
        assert load_bundles_from_disk("") == ()

    def test_nonexistent_path_returns_empty(self, tmp_path: Path) -> None:
        from fastmcp.server.security.policy.workbench import (
            load_bundles_from_disk,
        )

        assert load_bundles_from_disk(tmp_path / "does-not-exist") == ()

    def test_non_json_file_ignored(self, tmp_path: Path) -> None:
        from fastmcp.server.security.policy.workbench import (
            load_bundles_from_disk,
        )

        (tmp_path / "notes.txt").write_text("not a bundle")
        (tmp_path / "data.yaml").write_text("also: not")
        _write_bundle(tmp_path, "real", _valid_payload("real-one"))
        bundles = load_bundles_from_disk(tmp_path)
        assert [b.bundle_id for b in bundles] == ["real-one"]

    def test_invalid_json_skipped_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        from fastmcp.server.security.policy.workbench import (
            load_bundles_from_disk,
        )

        (tmp_path / "broken.json").write_text("{not valid json")
        _write_bundle(tmp_path, "ok", _valid_payload("ok-one"))
        with caplog.at_level(logging.WARNING):
            bundles = load_bundles_from_disk(tmp_path)
        assert len(bundles) == 1
        assert any("invalid JSON" in rec.getMessage() for rec in caplog.records)

    def test_missing_required_field_skipped(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        from fastmcp.server.security.policy.workbench import (
            load_bundles_from_disk,
        )

        # Missing 'bundle_id'.
        bad = _valid_payload("x")
        del bad["bundle_id"]
        _write_bundle(tmp_path, "bad", bad)
        _write_bundle(tmp_path, "good", _valid_payload("good-one"))
        with caplog.at_level(logging.WARNING):
            bundles = load_bundles_from_disk(tmp_path)
        assert [b.bundle_id for b in bundles] == ["good-one"]
        assert any(
            "bundle_id" in rec.getMessage() for rec in caplog.records
        )

    def test_providers_must_be_non_empty_list(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        from fastmcp.server.security.policy.workbench import (
            load_bundles_from_disk,
        )

        # Empty providers — meaningless bundle.
        bad = _valid_payload("empty-providers")
        bad["providers"] = []
        _write_bundle(tmp_path, "empty", bad)
        with caplog.at_level(logging.WARNING):
            bundles = load_bundles_from_disk(tmp_path)
        assert bundles == ()

    def test_providers_entries_must_be_objects(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        from fastmcp.server.security.policy.workbench import (
            load_bundles_from_disk,
        )

        bad = _valid_payload("bad-entry")
        bad["providers"] = ["just a string"]
        _write_bundle(tmp_path, "bad", bad)
        with caplog.at_level(logging.WARNING):
            bundles = load_bundles_from_disk(tmp_path)
        assert bundles == ()

    def test_duplicate_bundle_id_drops_later_files(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        from fastmcp.server.security.policy.workbench import (
            load_bundles_from_disk,
        )

        # Two files with the same bundle_id; sorted by name, "a.json"
        # comes first and wins.
        _write_bundle(
            tmp_path, "a", _valid_payload("dup-id")
        )
        _write_bundle(
            tmp_path, "b", _valid_payload("dup-id")
        )
        with caplog.at_level(logging.WARNING):
            bundles = load_bundles_from_disk(tmp_path)
        assert [b.bundle_id for b in bundles] == ["dup-id"]
        # Hint about which file was dropped.
        assert any("Duplicate bundle_id" in rec.getMessage() for rec in caplog.records)

    def test_optional_fields_default_when_missing(self, tmp_path: Path) -> None:
        from fastmcp.server.security.policy.workbench import (
            load_bundles_from_disk,
        )

        # Minimum-viable bundle: just the four required fields.
        minimal = {
            "bundle_id": "minimal",
            "title": "Minimal Bundle",
            "summary": "Short.",
            "providers": [{"type": "rate_limit"}],
        }
        _write_bundle(tmp_path, "minimal", minimal)
        bundles = load_bundles_from_disk(tmp_path)
        assert len(bundles) == 1
        b = bundles[0]
        # description falls back to summary; risk defaults; lists empty.
        assert b.description == "Short."
        assert b.risk_posture == "balanced"
        assert b.recommended_environments == ()
        assert b.tags == ()


class TestEffectiveBundles:
    def test_disk_extras_appear_in_listing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from fastmcp.server.security.policy import workbench

        _write_bundle(
            tmp_path,
            "site-pack",
            _valid_payload("site-custom-pack"),
        )
        monkeypatch.setenv("PURECIPHER_POLICY_BUNDLES_DIR", str(tmp_path))

        listed = workbench.list_policy_bundles()
        ids = [b["bundle_id"] for b in listed]
        # Disk bundle is appended, not replacing built-ins.
        assert "site-custom-pack" in ids
        assert "gdpr-data-protection" in ids  # still there

    def test_get_policy_bundle_finds_disk_entry(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from fastmcp.server.security.policy import workbench

        payload = _valid_payload("findme")
        _write_bundle(tmp_path, "x", payload)
        monkeypatch.setenv("PURECIPHER_POLICY_BUNDLES_DIR", str(tmp_path))

        out = workbench.get_policy_bundle("findme")
        assert out is not None
        assert out["title"] == "Custom Bundle"
        assert out["provider_count"] == 1

    def test_disk_cannot_shadow_builtin_bundle_id(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An operator with a typo can't accidentally shadow GDPR /
        HIPAA / SOC 2 etc. with a misconfigured local file."""
        from fastmcp.server.security.policy import workbench

        # Try to override the GDPR built-in.
        sneaky = _valid_payload("gdpr-data-protection")
        sneaky["title"] = "FAKE GDPR — should be ignored"
        _write_bundle(tmp_path, "fake-gdpr", sneaky)
        monkeypatch.setenv("PURECIPHER_POLICY_BUNDLES_DIR", str(tmp_path))

        with caplog.at_level(logging.WARNING):
            listed = workbench.list_policy_bundles()
        # The real GDPR bundle is still the one returned.
        gdpr = next(
            b for b in listed if b["bundle_id"] == "gdpr-data-protection"
        )
        assert gdpr["title"] == "GDPR Data Protection"
        # And the operator gets a warning.
        assert any(
            "collides with a built-in" in rec.getMessage()
            for rec in caplog.records
        )

    def test_unset_env_var_falls_back_to_builtins_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastmcp.server.security.policy import workbench

        monkeypatch.delenv("PURECIPHER_POLICY_BUNDLES_DIR", raising=False)
        listed = workbench.list_policy_bundles()
        # All built-in bundle IDs are present, no extras.
        ids = {b["bundle_id"] for b in listed}
        assert "gdpr-data-protection" in ids
        assert "hipaa-health-data" in ids
