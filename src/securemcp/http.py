"""SecureMCP HTTP facade."""

from fastmcp.server.security.http import (
    SecurityAPI,
    SecurityAuthorizer,
    SecurityCapability,
    mount_security_routes,
)

__all__ = [
    "SecurityAPI",
    "SecurityAuthorizer",
    "SecurityCapability",
    "mount_security_routes",
]
