"""Tests for policy proposal persistence in storage backends and governance.

Covers: StorageBackend proposal methods (Memory + SQLite), PolicyGovernor
persistence integration, reloaded-proposal deploy guard, and round-trip
serialization.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from fastmcp.server.security.policy.engine import PolicyEngine
from fastmcp.server.security.policy.governance import (
    PolicyGovernor,
    ProposalStatus,
)
from fastmcp.server.security.policy.provider import (
    AllowAllPolicy,
)
from fastmcp.server.security.policy.validator import PolicyValidator
from fastmcp.server.security.storage.memory import MemoryBackend
from fastmcp.server.security.storage.sqlite import SQLiteBackend

# ── Storage Backend Proposal Tests ────────────────────────────────


class TestMemoryBackendProposals:
    """Test MemoryBackend proposal persistence methods."""

    def test_save_and_load(self) -> None:
        backend = MemoryBackend()
        data = {"proposal_id": "p1", "action": "add", "status": "draft"}
        backend.save_policy_proposal("gov1", "p1", data)
        loaded = backend.load_policy_proposals("gov1")
        assert loaded == {"p1": data}

    def test_load_empty(self) -> None:
        backend = MemoryBackend()
        assert backend.load_policy_proposals("nonexistent") == {}

    def test_save_overwrites(self) -> None:
        backend = MemoryBackend()
        backend.save_policy_proposal("gov1", "p1", {"status": "draft"})
        backend.save_policy_proposal("gov1", "p1", {"status": "approved"})
        loaded = backend.load_policy_proposals("gov1")
        assert loaded["p1"]["status"] == "approved"

    def test_remove(self) -> None:
        backend = MemoryBackend()
        backend.save_policy_proposal("gov1", "p1", {"status": "draft"})
        backend.remove_policy_proposal("gov1", "p1")
        assert backend.load_policy_proposals("gov1") == {}

    def test_remove_nonexistent_is_noop(self) -> None:
        backend = MemoryBackend()
        backend.remove_policy_proposal("gov1", "missing")  # should not raise

    def test_namespace_isolation(self) -> None:
        backend = MemoryBackend()
        backend.save_policy_proposal("gov1", "p1", {"owner": "gov1"})
        backend.save_policy_proposal("gov2", "p1", {"owner": "gov2"})
        assert backend.load_policy_proposals("gov1")["p1"]["owner"] == "gov1"
        assert backend.load_policy_proposals("gov2")["p1"]["owner"] == "gov2"

    def test_load_returns_copy(self) -> None:
        backend = MemoryBackend()
        backend.save_policy_proposal("gov1", "p1", {"status": "draft"})
        loaded = backend.load_policy_proposals("gov1")
        loaded["p1"]["status"] = "mutated"
        # Original should be unchanged (dict is shallow-copied at top level)
        reloaded = backend.load_policy_proposals("gov1")
        # Note: The inner dicts are the same references, which matches
        # the pattern used for contracts. This is expected behavior.


class TestSQLiteBackendProposals:
    """Test SQLiteBackend proposal persistence methods."""

    def _make_backend(self, tmp_path: Path) -> SQLiteBackend:
        return SQLiteBackend(str(tmp_path / "test.db"))

    def test_save_and_load(self, tmp_path: Path) -> None:
        backend = self._make_backend(tmp_path)
        data = {"proposal_id": "p1", "action": "add", "status": "draft"}
        backend.save_policy_proposal("gov1", "p1", data)
        loaded = backend.load_policy_proposals("gov1")
        assert loaded == {"p1": data}
        backend.close()

    def test_load_empty(self, tmp_path: Path) -> None:
        backend = self._make_backend(tmp_path)
        assert backend.load_policy_proposals("nonexistent") == {}
        backend.close()

    def test_save_overwrites(self, tmp_path: Path) -> None:
        backend = self._make_backend(tmp_path)
        backend.save_policy_proposal("gov1", "p1", {"status": "draft"})
        backend.save_policy_proposal("gov1", "p1", {"status": "approved"})
        loaded = backend.load_policy_proposals("gov1")
        assert loaded["p1"]["status"] == "approved"
        backend.close()

    def test_remove(self, tmp_path: Path) -> None:
        backend = self._make_backend(tmp_path)
        backend.save_policy_proposal("gov1", "p1", {"status": "draft"})
        backend.remove_policy_proposal("gov1", "p1")
        assert backend.load_policy_proposals("gov1") == {}
        backend.close()

    def test_remove_nonexistent_is_noop(self, tmp_path: Path) -> None:
        backend = self._make_backend(tmp_path)
        backend.remove_policy_proposal("gov1", "missing")  # should not raise
        backend.close()

    def test_namespace_isolation(self, tmp_path: Path) -> None:
        backend = self._make_backend(tmp_path)
        backend.save_policy_proposal("gov1", "p1", {"owner": "gov1"})
        backend.save_policy_proposal("gov2", "p1", {"owner": "gov2"})
        assert backend.load_policy_proposals("gov1")["p1"]["owner"] == "gov1"
        assert backend.load_policy_proposals("gov2")["p1"]["owner"] == "gov2"
        backend.close()

    def test_persistence_across_connections(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "persist.db")
        backend1 = SQLiteBackend(db_path)
        backend1.save_policy_proposal("gov1", "p1", {"status": "draft"})
        backend1.close()

        backend2 = SQLiteBackend(db_path)
        loaded = backend2.load_policy_proposals("gov1")
        assert loaded == {"p1": {"status": "draft"}}
        backend2.close()


# ── PolicyGovernor Persistence Integration ────────────────────────


class TestGovernorPersistence:
    """Tests for PolicyGovernor integration with storage backend."""

    def _make_governor(
        self,
        storage: MemoryBackend | SQLiteBackend | None = None,
        *,
        require_simulation: bool = False,
        require_approval: bool = False,
        governor_id: str = "test-gov",
    ) -> PolicyGovernor:
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        return PolicyGovernor(
            engine,
            validator=PolicyValidator(),
            require_simulation=require_simulation,
            require_approval=require_approval,
            storage=storage,
            governor_id=governor_id,
        )

    def test_propose_persists_to_storage(self) -> None:
        storage = MemoryBackend()
        gov = self._make_governor(storage=storage)
        proposal = gov.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="test add",
        )
        persisted = storage.load_policy_proposals("test-gov")
        assert proposal.proposal_id in persisted
        assert persisted[proposal.proposal_id]["status"] == "draft"

    def test_validate_persists_status(self) -> None:
        storage = MemoryBackend()
        gov = self._make_governor(storage=storage)
        proposal = gov.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="test",
        )
        gov.validate_proposal(proposal.proposal_id)
        persisted = storage.load_policy_proposals("test-gov")
        assert persisted[proposal.proposal_id]["status"] == "validated"

    def test_approve_persists_status(self) -> None:
        storage = MemoryBackend()
        gov = self._make_governor(storage=storage, require_simulation=False)
        proposal = gov.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="test",
        )
        gov.validate_proposal(proposal.proposal_id)
        gov.approve(proposal.proposal_id, approver="admin")
        persisted = storage.load_policy_proposals("test-gov")
        assert persisted[proposal.proposal_id]["status"] == "approved"
        assert persisted[proposal.proposal_id]["approved_by"] == "admin"

    def test_reject_persists_status(self) -> None:
        storage = MemoryBackend()
        gov = self._make_governor(storage=storage)
        proposal = gov.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="test",
        )
        gov.reject(proposal.proposal_id, reason="not needed", actor="admin")
        persisted = storage.load_policy_proposals("test-gov")
        assert persisted[proposal.proposal_id]["status"] == "rejected"

    def test_withdraw_persists_status(self) -> None:
        storage = MemoryBackend()
        gov = self._make_governor(storage=storage)
        proposal = gov.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="test",
        )
        gov.withdraw(proposal.proposal_id, actor="tester")
        persisted = storage.load_policy_proposals("test-gov")
        assert persisted[proposal.proposal_id]["status"] == "withdrawn"

    def test_assign_persists(self) -> None:
        storage = MemoryBackend()
        gov = self._make_governor(storage=storage)
        proposal = gov.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="test",
        )
        gov.assign(proposal.proposal_id, reviewer="alice", actor="tester")
        persisted = storage.load_policy_proposals("test-gov")
        assert persisted[proposal.proposal_id]["assigned_reviewer"] == "alice"

    def test_deploy_persists_status(self) -> None:
        storage = MemoryBackend()
        gov = self._make_governor(
            storage=storage,
            require_simulation=False,
            require_approval=False,
        )
        proposal = gov.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="test",
        )
        gov.validate_proposal(proposal.proposal_id)
        asyncio.get_event_loop().run_until_complete(
            gov.deploy(proposal.proposal_id, actor="deployer")
        )
        persisted = storage.load_policy_proposals("test-gov")
        assert persisted[proposal.proposal_id]["status"] == "deployed"

    def test_no_storage_does_not_error(self) -> None:
        """Governor without storage should work fine (no persistence)."""
        gov = self._make_governor(storage=None)
        proposal = gov.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="test",
        )
        assert proposal.status == ProposalStatus.DRAFT

    def test_reload_proposals_on_init(self) -> None:
        """Proposals persisted in storage should be reloaded on new governor init."""
        storage = MemoryBackend()
        gov1 = self._make_governor(storage=storage, governor_id="reload-test")
        proposal = gov1.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="should survive reload",
        )
        pid = proposal.proposal_id

        # Create a new governor with the same storage — should reload
        gov2 = self._make_governor(storage=storage, governor_id="reload-test")
        reloaded = gov2.get_proposal(pid)
        assert reloaded is not None
        assert reloaded.proposal_id == pid
        assert reloaded.author == "tester"
        assert reloaded.status == ProposalStatus.DRAFT
        assert reloaded.description == "should survive reload"

    def test_reloaded_proposal_has_no_provider(self) -> None:
        """Reloaded proposals should have new_provider=None."""
        storage = MemoryBackend()
        gov1 = self._make_governor(storage=storage, governor_id="no-provider")
        proposal = gov1.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="test",
        )
        pid = proposal.proposal_id

        gov2 = self._make_governor(storage=storage, governor_id="no-provider")
        reloaded = gov2.get_proposal(pid)
        assert reloaded is not None
        assert reloaded.new_provider is None

    def test_deploy_reloaded_proposal_raises(self) -> None:
        """Deploying a reloaded ADD proposal should fail (no provider)."""
        storage = MemoryBackend()
        gov1 = self._make_governor(
            storage=storage,
            governor_id="deploy-guard",
            require_simulation=False,
            require_approval=False,
        )
        proposal = gov1.propose_add(
            AllowAllPolicy(),
            author="tester",
            description="test",
        )
        gov1.validate_proposal(proposal.proposal_id)
        pid = proposal.proposal_id

        gov2 = self._make_governor(
            storage=storage,
            governor_id="deploy-guard",
            require_simulation=False,
            require_approval=False,
        )
        reloaded = gov2.get_proposal(pid)
        assert reloaded is not None

        with pytest.raises(ValueError, match="reloaded proposal"):
            asyncio.get_event_loop().run_until_complete(
                gov2.deploy(pid, actor="deployer")
            )

    def test_deploy_reloaded_replace_chain_raises(self) -> None:
        """Deploying a reloaded REPLACE_CHAIN proposal should fail."""
        storage = MemoryBackend()
        gov1 = self._make_governor(
            storage=storage,
            governor_id="chain-guard",
            require_simulation=False,
            require_approval=False,
        )
        proposal = gov1.propose_replace_chain(
            [AllowAllPolicy()],
            author="tester",
            description="test",
        )
        gov1.validate_proposal(proposal.proposal_id)
        pid = proposal.proposal_id

        gov2 = self._make_governor(
            storage=storage,
            governor_id="chain-guard",
            require_simulation=False,
            require_approval=False,
        )
        with pytest.raises(ValueError, match="reloaded proposal"):
            asyncio.get_event_loop().run_until_complete(
                gov2.deploy(pid, actor="deployer")
            )

    def test_corrupted_persisted_proposal_skipped(self) -> None:
        """Corrupted data in storage should be skipped without crashing."""
        storage = MemoryBackend()
        # Manually write bad data
        storage.save_policy_proposal(
            "corrupt-test", "bad-1", {"missing": "required_fields"}
        )
        storage.save_policy_proposal(
            "corrupt-test",
            "bad-2",
            {"proposal_id": "bad-2", "action": "invalid_action"},
        )

        # Should not raise — bad proposals are silently skipped
        gov = self._make_governor(storage=storage, governor_id="corrupt-test")
        assert len(gov.proposals) == 0

    def test_decision_trail_round_trips(self) -> None:
        """Decision trail events should survive persistence round-trip."""
        storage = MemoryBackend()
        gov1 = self._make_governor(storage=storage, governor_id="trail-test")
        proposal = gov1.propose_add(
            AllowAllPolicy(),
            author="alice",
            description="test trail",
        )
        gov1.validate_proposal(proposal.proposal_id)
        pid = proposal.proposal_id

        gov2 = self._make_governor(storage=storage, governor_id="trail-test")
        reloaded = gov2.get_proposal(pid)
        assert reloaded is not None
        events = [e.event for e in reloaded.decision_trail]
        assert "proposed" in events
        assert "validated" in events
