"""Tests for Inter-Agent Digital Contracts — mutual signing, agent registry,
exchange log export, verification events, and HTTP endpoints.
"""

from __future__ import annotations

import pytest

from fastmcp.server.security.contracts.agent_registry import AgentKeyRegistry
from fastmcp.server.security.contracts.broker import ContextBroker
from fastmcp.server.security.contracts.crypto import (
    ContractCryptoHandler,
    SignatureInfo,
    SigningAlgorithm,
)
from fastmcp.server.security.contracts.exchange_log import (
    ExchangeEventType,
    ExchangeLog,
)
from fastmcp.server.security.contracts.schema import (
    ContractNegotiationRequest,
    ContractStatus,
    ContractTerm,
    NegotiationStatus,
)

# ── AgentKeyRegistry ─────────────────────────────────────────────


class TestAgentKeyRegistry:
    """Tests for agent key material management."""

    def test_register_and_retrieve_hmac_key(self) -> None:
        registry = AgentKeyRegistry()
        registry.register_agent_key(
            "agent-1", b"shared-secret", SigningAlgorithm.HMAC_SHA256
        )

        entry = registry.get_agent_key("agent-1")
        assert entry is not None
        key_material, algo = entry
        assert key_material == b"shared-secret"
        assert algo == SigningAlgorithm.HMAC_SHA256

    def test_get_nonexistent_agent_returns_none(self) -> None:
        registry = AgentKeyRegistry()
        assert registry.get_agent_key("ghost") is None

    def test_remove_agent_key(self) -> None:
        registry = AgentKeyRegistry()
        registry.register_agent_key("a1", b"k", SigningAlgorithm.HMAC_SHA256)
        assert registry.remove_agent_key("a1") is True
        assert registry.get_agent_key("a1") is None

    def test_remove_nonexistent_returns_false(self) -> None:
        registry = AgentKeyRegistry()
        assert registry.remove_agent_key("ghost") is False

    def test_list_agents(self) -> None:
        registry = AgentKeyRegistry()
        registry.register_agent_key("a1", b"k1", SigningAlgorithm.HMAC_SHA256)
        registry.register_agent_key("a2", b"k2", SigningAlgorithm.HMAC_SHA256)
        agents = registry.list_agents()
        assert set(agents) == {"a1", "a2"}

    def test_has_agent(self) -> None:
        registry = AgentKeyRegistry()
        registry.register_agent_key("a1", b"k", SigningAlgorithm.HMAC_SHA256)
        assert registry.has_agent("a1") is True
        assert registry.has_agent("a2") is False

    def test_agent_count(self) -> None:
        registry = AgentKeyRegistry()
        assert registry.agent_count == 0
        registry.register_agent_key("a1", b"k", SigningAlgorithm.HMAC_SHA256)
        assert registry.agent_count == 1

    def test_update_existing_agent_key(self) -> None:
        registry = AgentKeyRegistry()
        registry.register_agent_key("a1", b"old", SigningAlgorithm.HMAC_SHA256)
        registry.register_agent_key("a1", b"new", SigningAlgorithm.HMAC_SHA256)
        key_material, _ = registry.get_agent_key("a1")  # type: ignore[misc]
        assert key_material == b"new"


# ── Crypto: verify_with_external_key ─────────────────────────────


class TestCryptoExternalKey:
    """Tests for verifying signatures with externally provided keys."""

    def test_verify_with_correct_external_key(self) -> None:
        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        agent_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"agent-secret",
        )
        data = {"contract_id": "c1", "terms": []}
        sig = agent_handler.sign(data, signer_id="agent-1")

        assert (
            server_handler.verify_with_external_key(data, sig, b"agent-secret") is True
        )

    def test_verify_with_wrong_external_key_fails(self) -> None:
        handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        agent_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"correct-key",
        )
        data = {"contract_id": "c1"}
        sig = agent_handler.sign(data, signer_id="agent-1")

        assert handler.verify_with_external_key(data, sig, b"wrong-key") is False

    def test_verify_with_tampered_data_fails(self) -> None:
        handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        agent_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"agent-key",
        )
        data = {"contract_id": "c1"}
        sig = agent_handler.sign(data, signer_id="agent-1")

        tampered = {"contract_id": "c1-tampered"}
        assert handler.verify_with_external_key(tampered, sig, b"agent-key") is False


# ── Mutual Signing Flow ──────────────────────────────────────────


class TestMutualSigningFlow:
    """Tests for the full dual-signature contract flow."""

    @pytest.mark.anyio
    async def test_negotiate_creates_pending_countersign(self) -> None:
        """With agent_registry, contract should be PENDING_COUNTERSIGN after negotiation."""
        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        registry = AgentKeyRegistry()
        registry.register_agent_key(
            "agent-1", b"agent-secret", SigningAlgorithm.HMAC_SHA256
        )

        broker = ContextBroker(
            server_id="srv",
            crypto_handler=server_handler,
            agent_registry=registry,
        )

        request = ContractNegotiationRequest(
            agent_id="agent-1",
            proposed_terms=[ContractTerm(description="Read access")],
        )
        response = await broker.negotiate(request)

        assert response.status == NegotiationStatus.ACCEPTED
        assert response.contract is not None
        assert response.contract.status == ContractStatus.PENDING_COUNTERSIGN
        assert response.contract.is_signed_by("srv")
        assert not response.contract.is_signed_by("agent-1")

    @pytest.mark.anyio
    async def test_agent_signs_and_activates(self) -> None:
        """Agent countersignature moves contract to ACTIVE."""
        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        agent_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"agent-secret",
        )
        registry = AgentKeyRegistry()
        registry.register_agent_key(
            "agent-1", b"agent-secret", SigningAlgorithm.HMAC_SHA256
        )

        broker = ContextBroker(
            server_id="srv",
            crypto_handler=server_handler,
            agent_registry=registry,
        )

        req = ContractNegotiationRequest(
            agent_id="agent-1",
            proposed_terms=[ContractTerm(description="Test")],
        )
        resp = await broker.negotiate(req)
        contract = resp.contract
        assert contract is not None

        # Agent signs
        contract_data = contract.to_dict()
        agent_sig = agent_handler.sign(contract_data, signer_id="agent-1")
        success, error = await broker.agent_sign_contract(
            contract.contract_id, agent_sig
        )

        assert success is True
        assert error == ""

        updated = broker.get_contract(contract.contract_id)
        assert updated is not None
        assert updated.status == ContractStatus.ACTIVE
        assert updated.is_signed_by("srv")
        assert updated.is_signed_by("agent-1")

    @pytest.mark.anyio
    async def test_agent_sign_wrong_key_fails(self) -> None:
        """Agent signing with wrong key is rejected."""
        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        wrong_agent_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"wrong-key",
        )
        registry = AgentKeyRegistry()
        registry.register_agent_key(
            "agent-1", b"correct-key", SigningAlgorithm.HMAC_SHA256
        )

        broker = ContextBroker(
            server_id="srv",
            crypto_handler=server_handler,
            agent_registry=registry,
        )

        req = ContractNegotiationRequest(
            agent_id="agent-1",
            proposed_terms=[ContractTerm(description="Test")],
        )
        resp = await broker.negotiate(req)
        contract = resp.contract
        assert contract is not None

        bad_sig = wrong_agent_handler.sign(contract.to_dict(), signer_id="agent-1")
        success, error = await broker.agent_sign_contract(contract.contract_id, bad_sig)

        assert success is False
        assert "Invalid agent signature" in error
        assert contract.status == ContractStatus.PENDING_COUNTERSIGN

    @pytest.mark.anyio
    async def test_agent_sign_nonexistent_contract_fails(self) -> None:
        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        registry = AgentKeyRegistry()
        broker = ContextBroker(
            server_id="srv",
            crypto_handler=server_handler,
            agent_registry=registry,
        )

        sig = SignatureInfo(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            signer_id="agent-1",
            signature="dGVzdA==",
        )
        success, error = await broker.agent_sign_contract("nonexistent", sig)
        assert success is False
        assert "not found" in error

    @pytest.mark.anyio
    async def test_agent_sign_already_active_fails(self) -> None:
        """Cannot countersign a contract that's already ACTIVE."""
        # No agent_registry = contract goes straight to ACTIVE
        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        registry = AgentKeyRegistry()

        broker = ContextBroker(
            server_id="srv",
            crypto_handler=server_handler,
            agent_registry=registry,
        )

        req = ContractNegotiationRequest(
            agent_id="agent-1",
            proposed_terms=[ContractTerm(description="Test")],
        )
        resp = await broker.negotiate(req)
        contract = resp.contract
        assert contract is not None
        assert contract.status == ContractStatus.PENDING_COUNTERSIGN

        # Register agent and sign to activate
        registry.register_agent_key(
            "agent-1", b"agent-key", SigningAlgorithm.HMAC_SHA256
        )
        agent_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"agent-key",
        )
        agent_sig = agent_handler.sign(contract.to_dict(), signer_id="agent-1")
        success, _ = await broker.agent_sign_contract(contract.contract_id, agent_sig)
        assert success

        # Try to sign again
        success2, error2 = await broker.agent_sign_contract(
            contract.contract_id, agent_sig
        )
        assert success2 is False
        assert "not awaiting countersignature" in error2


# ── Backward Compatibility ────────────────────────────────────────


class TestBackwardCompatibility:
    """Without agent_registry, contracts go straight to ACTIVE."""

    @pytest.mark.anyio
    async def test_no_registry_contract_goes_active(self) -> None:
        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        broker = ContextBroker(
            server_id="srv",
            crypto_handler=server_handler,
            # No agent_registry
        )

        req = ContractNegotiationRequest(
            agent_id="agent-1",
            proposed_terms=[ContractTerm(description="Test")],
        )
        resp = await broker.negotiate(req)

        assert resp.contract is not None
        assert resp.contract.status == ContractStatus.ACTIVE
        assert resp.contract.is_signed_by("srv")

    @pytest.mark.anyio
    async def test_no_crypto_no_signing(self) -> None:
        broker = ContextBroker(server_id="srv")

        req = ContractNegotiationRequest(
            agent_id="agent-1",
            proposed_terms=[ContractTerm(description="Test")],
        )
        resp = await broker.negotiate(req)

        assert resp.contract is not None
        assert resp.contract.status == ContractStatus.ACTIVE
        assert len(resp.contract.signatures) == 0


# ── Exchange Log Export & Summary ─────────────────────────────────


class TestExchangeLogExport:
    """Tests for exchange log export and session summary."""

    def test_entry_to_dict_serialization(self) -> None:
        log = ExchangeLog()
        entry = log.record(
            session_id="s1",
            event_type=ExchangeEventType.SESSION_STARTED,
            actor_id="srv",
            data={"agent_id": "agent-1"},
        )

        d = ExchangeLog.entry_to_dict(entry)
        assert d["session_id"] == "s1"
        assert d["event_type"] == "session_started"
        assert d["actor_id"] == "srv"
        assert d["data"] == {"agent_id": "agent-1"}
        assert "timestamp" in d
        assert "data_hash" in d
        assert "previous_hash" in d

    def test_export_entries_all(self) -> None:
        log = ExchangeLog()
        log.record("s1", ExchangeEventType.SESSION_STARTED, "srv")
        log.record("s2", ExchangeEventType.SESSION_STARTED, "srv")

        entries = log.export_entries()
        assert len(entries) == 2

    def test_export_entries_by_session(self) -> None:
        log = ExchangeLog()
        log.record("s1", ExchangeEventType.SESSION_STARTED, "srv")
        log.record("s2", ExchangeEventType.SESSION_STARTED, "srv")
        log.record("s1", ExchangeEventType.ACCEPTED, "srv")

        entries = log.export_entries(session_id="s1")
        assert len(entries) == 2
        assert all(e["session_id"] == "s1" for e in entries)

    def test_get_session_summary_empty(self) -> None:
        log = ExchangeLog()
        summary = log.get_session_summary("nonexistent")
        assert summary["entry_count"] == 0
        assert summary["chain_verified"] is True

    def test_get_session_summary_with_events(self) -> None:
        log = ExchangeLog()
        log.record("s1", ExchangeEventType.SESSION_STARTED, "srv")
        log.record("s1", ExchangeEventType.PROPOSAL_RECEIVED, "agent")
        log.record("s1", ExchangeEventType.ACCEPTED, "srv")
        log.record("s1", ExchangeEventType.VERIFICATION_PASSED, "srv")

        summary = log.get_session_summary("s1")
        assert summary["entry_count"] == 4
        assert summary["verification_passed"] == 1
        assert summary["verification_failed"] == 0
        assert summary["chain_verified"] is True
        assert "started_at" in summary
        assert "ended_at" in summary

    def test_agent_signed_event_type_exists(self) -> None:
        log = ExchangeLog()
        entry = log.record("s1", ExchangeEventType.AGENT_SIGNED, "agent-1")
        assert entry.event_type == ExchangeEventType.AGENT_SIGNED

        d = ExchangeLog.entry_to_dict(entry)
        assert d["event_type"] == "agent_signed"


# ── Exchange Log in Mutual Signing ────────────────────────────────


class TestExchangeLogMutualSigning:
    """Verify exchange log records all events during mutual signing."""

    @pytest.mark.anyio
    async def test_full_lifecycle_exchange_log(self) -> None:
        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        agent_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"agent-secret",
        )
        registry = AgentKeyRegistry()
        registry.register_agent_key(
            "agent-1", b"agent-secret", SigningAlgorithm.HMAC_SHA256
        )

        broker = ContextBroker(
            server_id="srv",
            crypto_handler=server_handler,
            agent_registry=registry,
        )

        # Negotiate
        req = ContractNegotiationRequest(
            agent_id="agent-1",
            proposed_terms=[ContractTerm(description="Test")],
        )
        resp = await broker.negotiate(req)
        contract = resp.contract
        assert contract is not None

        # Agent signs
        agent_sig = agent_handler.sign(contract.to_dict(), signer_id="agent-1")
        success, _ = await broker.agent_sign_contract(contract.contract_id, agent_sig)
        assert success

        # Verify exchange log
        session_id = contract.session_id
        entries = broker.exchange_log.export_entries(session_id=session_id)
        event_types = [e["event_type"] for e in entries]

        assert "session_started" in event_types
        assert "proposal_received" in event_types
        assert "accepted" in event_types
        assert "contract_signed" in event_types
        assert "agent_signed" in event_types

        # Chain integrity
        assert broker.exchange_log.verify_chain(session_id) is True

        # Session summary
        summary = broker.exchange_log.get_session_summary(session_id)
        assert summary["chain_verified"] is True
        assert summary["entry_count"] == len(entries)

    @pytest.mark.anyio
    async def test_failed_agent_sign_logs_verification_failed(self) -> None:
        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        registry = AgentKeyRegistry()
        registry.register_agent_key(
            "agent-1", b"correct-key", SigningAlgorithm.HMAC_SHA256
        )

        broker = ContextBroker(
            server_id="srv",
            crypto_handler=server_handler,
            agent_registry=registry,
        )

        req = ContractNegotiationRequest(
            agent_id="agent-1",
            proposed_terms=[ContractTerm(description="Test")],
        )
        resp = await broker.negotiate(req)
        contract = resp.contract
        assert contract is not None

        # Sign with wrong key
        wrong_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"wrong-key",
        )
        bad_sig = wrong_handler.sign(contract.to_dict(), signer_id="agent-1")
        success, _ = await broker.agent_sign_contract(contract.contract_id, bad_sig)
        assert success is False

        entries = broker.exchange_log.export_entries(session_id=contract.session_id)
        event_types = [e["event_type"] for e in entries]
        assert "verification_failed" in event_types


# ── HTTP Endpoint Tests ───────────────────────────────────────────


class TestContractHTTPEndpoints:
    """Tests for contract API methods on SecurityAPI."""

    def _make_api(
        self,
        *,
        with_registry: bool = False,
    ) -> tuple:
        """Create a SecurityAPI with a broker."""
        from fastmcp.server.security.http.api import SecurityAPI

        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        registry = AgentKeyRegistry() if with_registry else None
        if registry is not None:
            registry.register_agent_key(
                "agent-1", b"agent-secret", SigningAlgorithm.HMAC_SHA256
            )

        broker = ContextBroker(
            server_id="srv",
            crypto_handler=server_handler,
            agent_registry=registry,
        )

        api = SecurityAPI(broker=broker)
        return api, broker

    @pytest.mark.anyio
    async def test_negotiate_contract_endpoint(self) -> None:
        api, _broker = self._make_api()

        result = await api.negotiate_contract(
            {
                "agent_id": "agent-1",
                "proposed_terms": [
                    {
                        "description": "Read-only access",
                        "constraint": {"read_only": True},
                    },
                ],
            }
        )

        assert result["status"] == "accepted"
        assert "session_id" in result
        assert "contract" in result

    @pytest.mark.anyio
    async def test_negotiate_and_sign_endpoint(self) -> None:
        api, broker = self._make_api(with_registry=True)

        # Negotiate
        result = await api.negotiate_contract(
            {
                "agent_id": "agent-1",
                "proposed_terms": [],
            }
        )
        assert result["status"] == "accepted"
        contract_id = result["contract"]["contract_id"]

        # Contract should be PENDING_COUNTERSIGN
        details = api.get_contract_details(contract_id)
        assert details["contract"]["status"] == "pending_countersign"
        assert details["is_mutually_signed"] is False

        # Agent signs
        agent_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"agent-secret",
        )
        contract = broker.get_contract(contract_id)
        assert contract is not None
        agent_sig = agent_handler.sign(contract.to_dict(), signer_id="agent-1")

        sign_result = await api.agent_sign_contract_endpoint(
            contract_id,
            {
                "algorithm": "hmac-sha256",
                "signer_id": "agent-1",
                "signature": agent_sig.signature,
            },
        )
        assert sign_result["success"] is True

        # Now mutually signed
        details2 = api.get_contract_details(contract_id)
        assert details2["contract"]["status"] == "active"
        assert details2["is_mutually_signed"] is True

    def test_get_contract_not_found(self) -> None:
        api, _broker = self._make_api()
        result = api.get_contract_details("nonexistent")
        assert result["status"] == 404

    @pytest.mark.anyio
    async def test_list_agent_contracts(self) -> None:
        api, _broker = self._make_api()

        await api.negotiate_contract(
            {
                "agent_id": "agent-1",
                "proposed_terms": [],
            }
        )

        result = api.list_agent_contracts("agent-1")
        assert result["count"] == 1
        assert result["agent_id"] == "agent-1"

    @pytest.mark.anyio
    async def test_revoke_contract_endpoint(self) -> None:
        api, _broker = self._make_api()

        neg = await api.negotiate_contract(
            {
                "agent_id": "agent-1",
                "proposed_terms": [],
            }
        )
        contract_id = neg["contract"]["contract_id"]

        result = await api.revoke_contract_endpoint(contract_id, reason="testing")
        assert result["success"] is True

    @pytest.mark.anyio
    async def test_exchange_log_entries_endpoint(self) -> None:
        api, _broker = self._make_api()

        neg = await api.negotiate_contract(
            {
                "agent_id": "agent-1",
                "proposed_terms": [],
            }
        )
        session_id = neg["session_id"]

        result = api.get_exchange_log_entries(session_id=session_id)
        assert result["count"] > 0
        assert all(e["session_id"] == session_id for e in result["entries"])

    @pytest.mark.anyio
    async def test_verify_exchange_chain_endpoint(self) -> None:
        api, _broker = self._make_api()

        neg = await api.negotiate_contract(
            {
                "agent_id": "agent-1",
                "proposed_terms": [],
            }
        )
        session_id = neg["session_id"]

        result = api.verify_exchange_chain(session_id)
        assert result["chain_verified"] is True
        assert result["entry_count"] > 0

    def test_endpoints_return_503_without_broker(self) -> None:
        from fastmcp.server.security.http.api import SecurityAPI

        api = SecurityAPI()  # No broker

        assert api.get_contract_details("x")["status"] == 503
        assert api.list_agent_contracts("x")["status"] == 503
        assert api.get_exchange_log_entries()["status"] == 503
        assert api.verify_exchange_chain("x")["status"] == 503


# ── Full Lifecycle Integration ────────────────────────────────────


class TestFullContractLifecycle:
    """End-to-end: negotiate → counter → accept → mutual sign → verify."""

    @pytest.mark.anyio
    async def test_full_lifecycle_with_counter_proposal(self) -> None:
        server_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"server-secret",
        )
        agent_handler = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=b"agent-secret",
        )
        registry = AgentKeyRegistry()
        registry.register_agent_key(
            "agent-1", b"agent-secret", SigningAlgorithm.HMAC_SHA256
        )

        def evaluator(
            terms: list[ContractTerm],
            ctx: dict,
        ) -> tuple[list[ContractTerm], list[str]]:
            # Reject if more than 1 term
            if len(terms) > 1:
                return terms[:1], ["Too many terms"]
            return terms, []

        broker = ContextBroker(
            server_id="srv",
            crypto_handler=server_handler,
            agent_registry=registry,
            term_evaluator=evaluator,
        )

        # Round 1: agent proposes 2 terms → counter
        req1 = ContractNegotiationRequest(
            agent_id="agent-1",
            proposed_terms=[
                ContractTerm(description="Term A"),
                ContractTerm(description="Term B"),
            ],
        )
        resp1 = await broker.negotiate(req1)
        assert resp1.status == NegotiationStatus.COUNTER
        assert resp1.counter_terms is not None
        assert len(resp1.counter_terms) == 1

        # Round 2: agent agrees to counter
        req2 = ContractNegotiationRequest(
            session_id=resp1.session_id,
            agent_id="agent-1",
            proposed_terms=resp1.counter_terms,
        )
        resp2 = await broker.negotiate(req2)
        assert resp2.status == NegotiationStatus.ACCEPTED
        assert resp2.contract is not None
        assert resp2.contract.status == ContractStatus.PENDING_COUNTERSIGN

        contract = resp2.contract

        # Agent countersigns
        agent_sig = agent_handler.sign(contract.to_dict(), signer_id="agent-1")
        success, _ = await broker.agent_sign_contract(contract.contract_id, agent_sig)
        assert success

        # Verify final state
        updated = broker.get_contract(contract.contract_id)
        assert updated is not None
        assert updated.status == ContractStatus.ACTIVE
        assert updated.is_signed_by("srv")
        assert updated.is_signed_by("agent-1")

        # Verify exchange log integrity
        session_id = contract.session_id
        assert broker.exchange_log.verify_chain(session_id) is True

        summary = broker.exchange_log.get_session_summary(session_id)
        assert summary["chain_verified"] is True
        assert "agent_signed" in summary["events"]
        assert "contract_signed" in summary["events"]
        assert "counter_sent" in summary["events"]
        assert "counter_received" in summary["events"]

        # Verify we can export the audit trail
        entries = broker.exchange_log.export_entries(session_id=session_id)
        assert (
            len(entries) >= 7
        )  # started, proposal, counter_sent, counter_received, accepted, signed, agent_signed

        # Revoke and confirm
        revoked = await broker.revoke_contract(
            contract.contract_id, reason="test complete"
        )
        assert revoked
        assert updated.status == ContractStatus.REVOKED
