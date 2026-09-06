# Policy code map

The production release `90107548b` contains the evaluators below. In each file, `evaluate()` implements the allow/deny decision; evidence dataclasses define trusted inputs. The source is Python, while catalog JSON configures those evaluators.

| Pack | Production source | Local source |
|---|---|---|
| FERPA | [GitHub](https://github.com/PureCipher/xsecuremcp2.0/blob/90107548b/fastmcp_slim/fastmcp/server/security/policy/policies/ferpa_request.py) | [ferpa_request.py](/Users/purecipher/code/xsecuremcp2.0/fastmcp_slim/fastmcp/server/security/policy/policies/ferpa_request.py) |
| GDPR | [GitHub](https://github.com/PureCipher/xsecuremcp2.0/blob/90107548b/fastmcp_slim/fastmcp/server/security/policy/policies/gdpr_request.py) | [gdpr_request.py](/Users/purecipher/code/xsecuremcp2.0/fastmcp_slim/fastmcp/server/security/policy/policies/gdpr_request.py) |
| HIPAA | [GitHub](https://github.com/PureCipher/xsecuremcp2.0/blob/90107548b/fastmcp_slim/fastmcp/server/security/policy/policies/hipaa_request.py) | [hipaa_request.py](/Users/purecipher/code/xsecuremcp2.0/fastmcp_slim/fastmcp/server/security/policy/policies/hipaa_request.py) |
| PCI DSS | [GitHub](https://github.com/PureCipher/xsecuremcp2.0/blob/90107548b/fastmcp_slim/fastmcp/server/security/policy/policies/pci_request.py) | [pci_request.py](/Users/purecipher/code/xsecuremcp2.0/fastmcp_slim/fastmcp/server/security/policy/policies/pci_request.py) |
| CCPA/CPRA | [GitHub](https://github.com/PureCipher/xsecuremcp2.0/blob/90107548b/fastmcp_slim/fastmcp/server/security/policy/policies/ccpa_request.py) | [ccpa_request.py](/Users/purecipher/code/xsecuremcp2.0/fastmcp_slim/fastmcp/server/security/policy/policies/ccpa_request.py) |
| SOC 2 | [GitHub](https://github.com/PureCipher/xsecuremcp2.0/blob/90107548b/fastmcp_slim/fastmcp/server/security/policy/policies/soc2_request.py) | [soc2_request.py](/Users/purecipher/code/xsecuremcp2.0/fastmcp_slim/fastmcp/server/security/policy/policies/soc2_request.py) |
| Zero Trust | [GitHub](https://github.com/PureCipher/xsecuremcp2.0/blob/90107548b/fastmcp_slim/fastmcp/server/security/policy/policies/zero_trust.py) | [zero_trust.py](/Users/purecipher/code/xsecuremcp2.0/fastmcp_slim/fastmcp/server/security/policy/policies/zero_trust.py) |
| Published Tools Only | [GitHub](https://github.com/PureCipher/xsecuremcp2.0/blob/90107548b/fastmcp_slim/fastmcp/server/security/policy/policies/published_tools.py) | [published_tools.py](/Users/purecipher/code/xsecuremcp2.0/fastmcp_slim/fastmcp/server/security/policy/policies/published_tools.py) |

In the console: Policy Kernel → Policy packs → View details → Show raw provider config. This shows the staged provider configuration, not Python source or proof of runtime enforcement. Current policy shows the installed chain.

Catalog definitions are in `fastmcp_slim/fastmcp/server/security/policy/workbench.py`. Builder/validation wiring is in `declarative.py`, and configuration persistence is in `serialization.py` in the same directory. Trusted runtime callbacks are in `fastmcp_slim/fastmcp/server/security/middleware/policy_enforcement.py`.

The local Balanced Registry Guardrails v2 update reuses `zero_trust.py`; it does not need a duplicate evaluator. Its JSON differs from the production catalog until released.

Evidence adapters must consult authoritative systems and enforce their attested scope. Selecting a provider and viewing its configuration does not prove that an adapter is configured or that a pack is active.
