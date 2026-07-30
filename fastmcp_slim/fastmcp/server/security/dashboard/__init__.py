"""SecureMCP Dashboard (Phase 20).

Server-side data aggregation layer for the security dashboard.
Provides snapshot generation, timeline tracking, component
health monitoring, and a data bridge for frontend visualization.
"""

from fastmcp.server.security.dashboard.data_bridge import DashboardDataBridge
from fastmcp.server.security.dashboard.snapshot import (
    ComponentHealth,
    DashboardSnapshot,
    HealthLevel,
    SecurityDashboard,
    TimelineEntry,
    TimelineType,
)

__all__ = [
    "ComponentHealth",
    "DashboardDataBridge",
    "DashboardSnapshot",
    "HealthLevel",
    "SecurityDashboard",
    "TimelineEntry",
    "TimelineType",
]
