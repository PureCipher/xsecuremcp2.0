"""Agent key registry for mutual contract authentication.

Manages cryptographic key material for agents participating in contract
negotiation. Supports both symmetric (HMAC) shared secrets and
asymmetric (RSA/ECDSA) public keys.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from fastmcp.server.security.contracts.crypto import SigningAlgorithm

logger = logging.getLogger(__name__)


class AgentKeyRegistry:
    """Registry of agent cryptographic keys for mutual contract signing.

    Stores the mapping from agent identifiers to their key material and
    preferred signing algorithm.  The broker uses this registry to verify
    agent-provided signatures during the countersign step.

    Example::

        registry = AgentKeyRegistry()
        registry.register_agent_key(
            "agent-abc",
            key_material=b"shared-secret",
            algorithm=SigningAlgorithm.HMAC_SHA256,
        )
        entry = registry.get_agent_key("agent-abc")
        assert entry is not None

    For HMAC-SHA256, ``key_material`` is a ``bytes`` shared secret.
    For RSA-PSS / ECDSA-P256, ``key_material`` is the public key object
    from the ``cryptography`` package.
    """

    def __init__(self) -> None:
        self._keys: dict[str, tuple[Any, SigningAlgorithm]] = {}
        self._lock = threading.Lock()

    def register_agent_key(
        self,
        agent_id: str,
        key_material: Any,
        algorithm: SigningAlgorithm,
    ) -> None:
        """Register or update key material for an agent.

        Args:
            agent_id: Unique agent identifier.
            key_material: Cryptographic key (bytes for HMAC, public key for RSA/ECDSA).
            algorithm: The signing algorithm the agent uses.
        """
        with self._lock:
            self._keys[agent_id] = (key_material, algorithm)
            logger.info(
                "Registered key for agent %s (algorithm=%s)", agent_id, algorithm.value
            )

    def get_agent_key(self, agent_id: str) -> tuple[Any, SigningAlgorithm] | None:
        """Look up key material for an agent.

        Returns:
            Tuple of (key_material, algorithm) or None if not registered.
        """
        return self._keys.get(agent_id)

    def remove_agent_key(self, agent_id: str) -> bool:
        """Remove an agent's key registration.

        Returns:
            True if the agent was found and removed, False otherwise.
        """
        with self._lock:
            if agent_id in self._keys:
                del self._keys[agent_id]
                logger.info("Removed key for agent %s", agent_id)
                return True
            return False

    def has_agent(self, agent_id: str) -> bool:
        """Check whether an agent has registered key material."""
        return agent_id in self._keys

    def list_agents(self) -> list[str]:
        """Return identifiers of all registered agents."""
        return list(self._keys.keys())

    @property
    def agent_count(self) -> int:
        """Number of registered agents."""
        return len(self._keys)
