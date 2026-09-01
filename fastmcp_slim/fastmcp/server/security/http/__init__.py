"""SecureMCP HTTP API — REST endpoints for dashboards, marketplace, and auditing.

Provides JSON endpoints that power the React dashboard and marketplace UIs,
plus REST APIs for compliance reports, audit queries, and trust lookups.
"""

from fastmcp.server.security.http.api import SecurityAPI, mount_security_routes
from fastmcp.server.security.http.authorization import (
    SecurityAuthorizer,
    SecurityCapability,
)

__all__ = [
    "SecurityAPI",
    "SecurityAuthorizer",
    "SecurityCapability",
    "mount_security_routes",
]
