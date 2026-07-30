"""Provenance Ledger for SecureMCP (Phase 3).

Tamper-evident audit trails with hash-chain integrity and Merkle tree
verification for all MCP operations. Supports pluggable ledger schemes
for varying trust and performance needs:

- ``LocalMerkleLedger``: In-process Merkle tree (fast, single-node trust).
- ``BlockchainAnchoredLedger``: Local Merkle + periodic external chain commits.
"""

from fastmcp.server.security.provenance.export import (
    VerificationBundle,
    export_chain_dump,
    verify_bundle,
    verify_chain_dump,
)
from fastmcp.server.security.provenance.ledger import ProvenanceLedger
from fastmcp.server.security.provenance.merkle import MerkleProof, MerkleTree
from fastmcp.server.security.provenance.records import (
    ProvenanceAction,
    ProvenanceRecord,
    hash_data,
)
from fastmcp.server.security.provenance.schemes import (
    AnchorBackend,
    BlockchainAnchoredLedger,
    ChainAnchor,
    InMemoryAnchorBackend,
    LedgerScheme,
    LedgerSchemeType,
    LocalMerkleLedger,
)

__all__ = [
    "AnchorBackend",
    "BlockchainAnchoredLedger",
    "ChainAnchor",
    "InMemoryAnchorBackend",
    "LedgerScheme",
    "LedgerSchemeType",
    "LocalMerkleLedger",
    "MerkleProof",
    "MerkleTree",
    "ProvenanceAction",
    "ProvenanceLedger",
    "ProvenanceRecord",
    "VerificationBundle",
    "export_chain_dump",
    "hash_data",
    "verify_bundle",
    "verify_chain_dump",
]
