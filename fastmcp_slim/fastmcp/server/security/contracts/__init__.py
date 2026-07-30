"""Context Broker for SecureMCP (Phase 2).

Real-time contract negotiation between AI agents and MCP servers.
Provides cryptographic signing, mutual authentication, session management,
and non-repudiation logging.
"""

from fastmcp.server.security.contracts.agent_registry import AgentKeyRegistry
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
    Contract,
    ContractNegotiationRequest,
    ContractNegotiationResponse,
    ContractStatus,
    ContractTerm,
    NegotiationStatus,
    TermType,
)

__all__ = [
    "AgentKeyRegistry",
    "Contract",
    "ContractCryptoHandler",
    "ContractNegotiationRequest",
    "ContractNegotiationResponse",
    "ContractStatus",
    "ContractTerm",
    "ExchangeEventType",
    "ExchangeLog",
    "NegotiationStatus",
    "SignatureInfo",
    "SigningAlgorithm",
    "TermType",
]
