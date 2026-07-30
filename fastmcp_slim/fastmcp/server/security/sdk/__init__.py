"""SecureMCP SDK & Integration Layer (Phase 19).

High-level SDK that provides a unified facade over all SecureMCP
components, making it easy for tool developers to integrate
security into their MCP tools.
"""

from fastmcp.server.security.sdk.client import (
    SecureMCPClient,
    SecurityCheckResult,
    ToolSecurityProfile,
)
from fastmcp.server.security.sdk.decorators import (
    SecurityDecorator,
    SecurityDecoratorConfig,
)

__all__ = [
    "SecureMCPClient",
    "SecurityCheckResult",
    "SecurityDecorator",
    "SecurityDecoratorConfig",
    "ToolSecurityProfile",
]
