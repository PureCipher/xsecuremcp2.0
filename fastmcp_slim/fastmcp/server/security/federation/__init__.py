"""SecureMCP Federation & Revocation (Phase 16).

Cross-registry trust sharing, certificate revocation lists (CRLs),
and emergency revocation propagation.
"""

from fastmcp.server.security.federation.crl import (
    CRLEntry,
    CertificateRevocationList,
    RevocationReason,
)
from fastmcp.server.security.federation.federation import (
    BroadcastDelivery,
    BroadcastResult,
    BroadcastTransport,
    FederatedQuery,
    FederatedTrustResult,
    FederationPeer,
    PeerStatus,
    TrustFederation,
)

__all__ = [
    "BroadcastDelivery",
    "BroadcastResult",
    "BroadcastTransport",
    "CRLEntry",
    "CertificateRevocationList",
    "FederatedQuery",
    "FederatedTrustResult",
    "FederationPeer",
    "PeerStatus",
    "RevocationReason",
    "TrustFederation",
]
