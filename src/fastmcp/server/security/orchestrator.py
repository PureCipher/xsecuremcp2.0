"""Security Orchestrator for SecureMCP (Phase 10).

Centralizes the bootstrap of all security layers from a SecurityConfig.
The orchestrator creates component instances, injects the shared event bus,
wires middleware, and exposes a SecurityContext for programmatic access.

Before this, each layer was wired inline in ``server.py`` — ~120 lines of
boilerplate that duplicated knowledge about component construction.  The
orchestrator replaces that with a single call::

    ctx = SecurityOrchestrator.bootstrap(security_config, server_name="my-server")
    middleware = ctx.middleware
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from fastmcp.server.security.alerts.bus import SecurityEventBus
from fastmcp.server.security.config import SecurityConfig
from fastmcp.server.security.consent.graph import ConsentGraph
from fastmcp.server.security.contracts.broker import ContextBroker
from fastmcp.server.security.gateway.audit import AuditAPI
from fastmcp.server.security.gateway.marketplace import Marketplace
from fastmcp.server.security.policy.engine import PolicyEngine
from fastmcp.server.security.provenance.ledger import ProvenanceLedger
from fastmcp.server.security.reflexive.analyzer import BehavioralAnalyzer, EscalationEngine

logger = logging.getLogger(__name__)


@dataclass
class SecurityContext:
    """Holds all instantiated security components after orchestration.

    Every field is optional — only layers that were configured in the
    ``SecurityConfig`` will be populated.  This gives callers a single
    typed handle to reach any layer.

    Example::

        ctx = SecurityOrchestrator.bootstrap(config)
        if ctx.policy_engine:
            result = await ctx.policy_engine.evaluate(evaluation_ctx)

    Attributes:
        config: The original SecurityConfig used for bootstrapping.
        event_bus: Shared event bus (from AlertConfig or auto-created).
        policy_engine: Policy kernel engine.
        broker: Context broker for contract negotiation.
        provenance_ledger: Provenance ledger for audit trails.
        behavioral_analyzer: Behavioral drift detector.
        escalation_engine: Escalation rule engine.
        consent_graph: Consent graph for access-rights.
        audit_api: Unified audit query API.
        marketplace: Server marketplace registry.
        middleware: Ordered list of security middleware instances.
        gateway_tools: Dict of MCP tool callables from the gateway layer.
    """

    config: SecurityConfig
    event_bus: SecurityEventBus | None = None
    policy_engine: PolicyEngine | None = None
    broker: ContextBroker | None = None
    provenance_ledger: ProvenanceLedger | None = None
    behavioral_analyzer: BehavioralAnalyzer | None = None
    escalation_engine: EscalationEngine | None = None
    consent_graph: ConsentGraph | None = None
    audit_api: AuditAPI | None = None
    marketplace: Marketplace | None = None
    middleware: list[Any] = field(default_factory=list)
    gateway_tools: dict[str, Any] = field(default_factory=dict)


class SecurityOrchestrator:
    """Bootstraps all security layers from a SecurityConfig.

    This is a stateless factory — call :meth:`bootstrap` to produce a
    :class:`SecurityContext` with all layers wired up.

    The orchestrator handles:

    * Component instantiation via each layer config's ``get_*()`` factory.
    * Event bus injection into every component that supports it.
    * Middleware construction in the correct order (policy → contracts →
      provenance → reflexive → consent).
    * Gateway wiring (AuditAPI + Marketplace + MCP tools).

    Example::

        config = SecurityConfig(
            policy=PolicyConfig(providers=[MyPolicy()]),
            alerts=AlertConfig(),
        )
        ctx = SecurityOrchestrator.bootstrap(config, server_name="my-server")

        # All middleware ready:
        for mw in ctx.middleware:
            server.add_middleware(mw)
    """

    @staticmethod
    def bootstrap(
        config: SecurityConfig,
        *,
        server_name: str = "securemcp-server",
        bypass_stdio: bool = True,
    ) -> SecurityContext:
        """Create all security components from the given config.

        Args:
            config: Master security configuration.
            server_name: Server identity for the context broker.
            bypass_stdio: Whether middleware should skip STDIO transport.

        Returns:
            A fully-wired SecurityContext.
        """
        ctx = SecurityContext(config=config)

        # --- Event Bus ---
        event_bus: SecurityEventBus | None = None
        if config.is_alerts_enabled():
            assert config.alerts is not None
            event_bus = config.alerts.get_event_bus()
            ctx.event_bus = event_bus
            logger.debug("Alert system enabled with event bus %s", id(event_bus))

        propagate = (
            config.alerts is not None
            and config.alerts.propagate_to_components
            and event_bus is not None
        )
        bus_for_components = event_bus if propagate else None

        # --- Policy Kernel ---
        if config.is_policy_enabled():
            assert config.policy is not None
            engine = config.policy.get_engine()
            if bus_for_components is not None:
                engine._event_bus = bus_for_components
            ctx.policy_engine = engine

            from fastmcp.server.security.middleware.policy_enforcement import (
                PolicyEnforcementMiddleware,
            )

            ctx.middleware.append(
                PolicyEnforcementMiddleware(
                    policy_engine=engine,
                    bypass_stdio=bypass_stdio,
                )
            )
            logger.debug("Policy kernel enabled")

        # --- Context Broker (Contracts) ---
        if config.is_contracts_enabled():
            assert config.contracts is not None
            broker = config.contracts.get_broker(server_id=server_name)
            ctx.broker = broker

            from fastmcp.server.security.middleware.contract_validation import (
                ContractValidationMiddleware,
            )

            ctx.middleware.append(
                ContractValidationMiddleware(
                    broker=broker,
                    bypass_stdio=bypass_stdio,
                    require_for_list=config.contracts.require_for_list,
                )
            )
            logger.debug("Context broker enabled")

        # --- Provenance Ledger ---
        if config.is_provenance_enabled():
            assert config.provenance is not None
            ledger = config.provenance.get_ledger()
            if bus_for_components is not None:
                ledger._event_bus = bus_for_components
            ctx.provenance_ledger = ledger

            from fastmcp.server.security.middleware.provenance_recording import (
                ProvenanceRecordingMiddleware,
            )

            ctx.middleware.append(
                ProvenanceRecordingMiddleware(
                    ledger=ledger,
                    bypass_stdio=bypass_stdio,
                    record_list_operations=config.provenance.record_list_operations,
                )
            )
            logger.debug("Provenance ledger enabled")

        # --- Reflexive Core ---
        if config.is_reflexive_enabled():
            assert config.reflexive is not None
            analyzer = config.reflexive.get_analyzer()
            escalation_engine = config.reflexive.get_escalation_engine()
            if bus_for_components is not None:
                analyzer._event_bus = bus_for_components
                escalation_engine._event_bus = bus_for_components
            ctx.behavioral_analyzer = analyzer
            ctx.escalation_engine = escalation_engine

            from fastmcp.server.security.middleware.reflexive import (
                ReflexiveMiddleware,
            )

            ctx.middleware.append(
                ReflexiveMiddleware(
                    analyzer=analyzer,
                    escalation_engine=escalation_engine,
                    bypass_stdio=bypass_stdio,
                )
            )
            logger.debug("Reflexive core enabled")

        # --- Consent Graph ---
        if config.is_consent_enabled():
            assert config.consent is not None
            graph = config.consent.get_graph()
            if bus_for_components is not None:
                graph._event_bus = bus_for_components
            ctx.consent_graph = graph

            from fastmcp.server.security.middleware.consent_enforcement import (
                ConsentEnforcementMiddleware,
            )

            ctx.middleware.append(
                ConsentEnforcementMiddleware(
                    graph=graph,
                    resource_owner=config.consent.resource_owner,
                    bypass_stdio=bypass_stdio,
                    require_for_list=config.consent.require_for_list,
                )
            )
            logger.debug("Consent graph enabled")

        # --- API Gateway ---
        if config.is_gateway_enabled():
            assert config.gateway is not None
            marketplace = config.gateway.get_marketplace()
            if bus_for_components is not None:
                marketplace._event_bus = bus_for_components
            ctx.marketplace = marketplace

            audit_api = config.gateway.audit_api or AuditAPI(
                provenance_ledger=ctx.provenance_ledger,
                behavioral_analyzer=ctx.behavioral_analyzer,
                consent_graph=ctx.consent_graph,
                policy_engine=ctx.policy_engine,
            )
            ctx.audit_api = audit_api

            if config.gateway.register_tools:
                from fastmcp.server.security.gateway.tools import (
                    create_audit_tools,
                    create_marketplace_tools,
                )

                ctx.gateway_tools = {
                    **create_audit_tools(audit_api),
                    **create_marketplace_tools(marketplace),
                }
            logger.debug("API gateway enabled")

        return ctx
