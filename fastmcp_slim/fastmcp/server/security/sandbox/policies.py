"""Sandbox execution policies.

Define what operations are allowed or blocked during tool execution
based on security manifests and runtime configuration.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResourcePolicy:
    """Policy for resource access control.

    Attributes:
        allowed_patterns: Glob patterns for allowed resources.
        blocked_patterns: Glob patterns for blocked resources.
        max_resources: Maximum number of resources accessible.
        read_only: Whether only read access is allowed.
    """

    allowed_patterns: list[str] = field(default_factory=list)
    blocked_patterns: list[str] = field(default_factory=list)
    max_resources: int = 100
    read_only: bool = False

    def is_allowed(self, resource_uri: str) -> bool:
        """Check if a resource URI is allowed by this policy."""
        # Check blocked first (deny takes priority)
        for pattern in self.blocked_patterns:
            if fnmatch.fnmatch(resource_uri, pattern):
                return False

        # If allowed patterns specified, must match at least one
        if self.allowed_patterns:
            return any(
                fnmatch.fnmatch(resource_uri, pattern)
                for pattern in self.allowed_patterns
            )

        # No patterns specified = allow all (not blocked)
        return True


@dataclass
class TimeoutPolicy:
    """Policy for execution time limits.

    Attributes:
        max_execution_seconds: Maximum allowed execution time.
        warn_at_percent: Emit a warning at this percentage of the limit.
    """

    max_execution_seconds: float = 30.0
    warn_at_percent: float = 80.0

    @property
    def warn_at_seconds(self) -> float:
        """Seconds at which to emit a warning."""
        return self.max_execution_seconds * (self.warn_at_percent / 100.0)


@dataclass
class ExecutionPolicy:
    """Combined execution policy for a sandboxed tool.

    Attributes:
        allow_network: Whether network access is permitted.
        allow_file_read: Whether file system reads are permitted.
        allow_file_write: Whether file system writes are permitted.
        allow_subprocess: Whether subprocess execution is permitted.
        allow_env_read: Whether environment variable reads are permitted.
        allow_cross_origin: Whether cross-origin requests are permitted.
        resource_policy: Resource access rules.
        timeout_policy: Execution time limits.
        require_consent: Whether user consent is required.
        metadata: Additional policy data.
    """

    allow_network: bool = False
    allow_file_read: bool = False
    allow_file_write: bool = False
    allow_subprocess: bool = False
    allow_env_read: bool = False
    allow_cross_origin: bool = False
    resource_policy: ResourcePolicy = field(default_factory=ResourcePolicy)
    timeout_policy: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    require_consent: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "allow_network": self.allow_network,
            "allow_file_read": self.allow_file_read,
            "allow_file_write": self.allow_file_write,
            "allow_subprocess": self.allow_subprocess,
            "allow_env_read": self.allow_env_read,
            "allow_cross_origin": self.allow_cross_origin,
            "max_execution_seconds": self.timeout_policy.max_execution_seconds,
            "require_consent": self.require_consent,
        }
