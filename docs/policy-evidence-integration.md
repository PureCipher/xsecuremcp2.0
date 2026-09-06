# Trusted policy evidence integration

The ten catalog packs have versioned evaluators, but deploying or staging a pack does not activate it or supply trusted facts. Standard server configuration now accepts `PolicyEvidenceResolvers` through `PolicyConfig.evidence_resolvers`.

```python
from fastmcp.server.security.config import (
    PolicyConfig, PolicyEvidenceResolvers, SecurityConfig,
)

security = SecurityConfig(
    policy=PolicyConfig(
        providers=[configured_change_policy],
        evidence_resolvers=PolicyEvidenceResolvers(
            change_evidence_resolver=resolve_from_authoritative_system,
        ),
    ),
)
```

The provider and resolver in this example are application-owned objects. Use this security config with the standard SecureMCP bootstrap. Supply asynchronous callbacks for FERPA, Zero Trust, PCI, CCPA, SOC 2, GDPR, HIPAA, published-tool or change evidence as required by the installed providers. Callbacks receive the authenticated policy context. They must verify facts and exact request binding against authoritative records, never promote client metadata into trusted evidence.

Callbacks are deployment code, not callable names loaded from policy JSON. Only policy configuration is persisted; callbacks must be configured again when each process starts. Missing evidence or resolver errors deny requests requiring that evidence. The client-aware middleware upgrade retains callback references.

This iteration enables the standard middleware path. It does not provision external authorities or automatically configure production resolvers. Direct calls to `PolicyEngine.evaluate`, including registry simulation, do not invoke middleware resolvers. Those paths and consumer execution routes still need separate evidence-integration review; simulation without evidence must not be presented as a successful runtime readiness check.
