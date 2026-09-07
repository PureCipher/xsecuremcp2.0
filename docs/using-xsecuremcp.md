# Using xSecureMCP: from a tool call to an enforced policy

This guide demonstrates three observable behaviors: a permitted tool returns a result, a forbidden tool is blocked, and a completed permitted call carries an execution receipt. It runs locally and does not require the hosted registry.

## 1. Install the fork

Create a Python virtual environment and install the matching packages:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade -r https://github.com/PureCipher/xsecuremcp2.0/releases/download/build-latest/requirements.txt
```

On Windows, use `.venv\Scripts\Activate.ps1` to activate the environment in PowerShell.

## 2. Define the server and its policy

Save this as `server.py`. The policy permits listing tools and calling `add`; other operations are denied. `reset_demo` is deliberately registered so you can check that a callable tool can still be rejected by policy.

```python
from fastmcp.server.security.policy.provider import PolicyDecision, PolicyResult
from securemcp import SecureMCP, SecurityConfig
from securemcp.config import PolicyConfig, ProvenanceConfig


class CalculatorPolicy:
    async def evaluate(self, context):
        allowed = context.action == "list_tools" or (
            context.action == "call_tool" and context.resource_id == "add"
        )
        return PolicyResult(
            decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
            reason="This server permits only calculator addition.",
            policy_id=await self.get_policy_id(),
        )

    async def get_policy_id(self):
        return "calculator-allowlist"

    async def get_policy_version(self):
        return "1.0.0"


server = SecureMCP(
    "governed-calculator",
    security=SecurityConfig(
        policy=PolicyConfig(providers=[CalculatorPolicy()], fail_closed=True),
        provenance=ProvenanceConfig(),
    ),
)


@server.tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@server.tool
def reset_demo() -> str:
    """A harmless demonstration operation that policy must block."""
    return "This tool body should not run under CalculatorPolicy."


if __name__ == "__main__":
    server.run(transport="http", host="127.0.0.1", port=8000)
```

Start it with `python server.py`. The endpoint is `http://127.0.0.1:8000/mcp`.

The policy is an explicit allowlist, so future tools are not automatically permitted. `fail_closed=True` makes policy evaluation failures deny access. This example does not identify users, request human approval, or configure consent: add those controls according to your application’s requirements.

## 3. Call it and verify the behavior

In a second terminal, activate the same virtual environment. Save this as `client.py`, then run `python client.py`:

```python
import asyncio

from fastmcp import Client
from mcp.shared.exceptions import MCPError
from securemcp.receipts import RECEIPT_META_KEY, verify_execution_receipt


async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
        print("Result:", result.data)
        receipt = result.meta[RECEIPT_META_KEY]
        verification = verify_execution_receipt(receipt)
        print("Receipt integrity:", verification["valid"])

        try:
            await client.call_tool("reset_demo", {})
        except MCPError:
            print("reset_demo: request rejected; check the server policy log")
        else:
            raise RuntimeError("Expected reset_demo to be denied")


asyncio.run(main())
```

Expected output, alongside any framework logs:

```text
Result: 5
Receipt integrity: True
reset_demo: request rejected; check the server policy log
```

In this build, a middleware denial reaches the client as an `MCPError`, which may have the generic message `Internal server error`. Confirm the specific cause in the server log: this example logs `Policy DENY` for `calculator-allowlist` and `reset_demo`. Do not classify every MCP error as a policy denial.

The policy evaluates the requested action before permitting it. The receipt describes the permitted execution observed by provenance. A call rejected before provenance runs may not have an execution receipt; use the policy audit trail to review the denial.

`valid=True` checks the receipt’s internal integrity. To compare against an independently trusted ledger root, use `verify_execution_receipt(receipt, trusted_root=expected_root)`. Obtain that root through your own trusted channel; taking it from the same untrusted receipt does not add trust. See [Execution Receipts](execution-receipts.md) for the exact coverage and limitations.

## 4. Adapt an existing FastMCP server

Install the fork’s complete package bundle in an isolated environment first. Existing `FastMCP` tools, resources, prompts, and clients remain the starting point. You can use `SecureMCP` as the server class, or attach controls to an existing instance with the public helper:

```python
from fastmcp import FastMCP
from securemcp import attach_security
from securemcp.config import ProvenanceConfig, SecurityConfig

server = FastMCP("existing-server")
attach_security(server, SecurityConfig(provenance=ProvenanceConfig()))
```

Attach your selected configuration once, before serving requests. Add policy providers, consent graphs, and contract settings as needed. Re-run your own application’s tests; inheriting FastMCP APIs does not guarantee every upstream extension or version combination will behave identically.

Standard MCP clients can consume ordinary results. Receipt-aware clients must explicitly inspect the `securemcp/execution-receipt` metadata and verify it. Listing a remote server in PureCipher Registry does not attach this middleware to that remote server.

## 5. Decide which additional controls you need

| Requirement | Configure | What you must supply |
| --- | --- | --- |
| Limit which operations a caller can perform | `PolicyConfig` | Policy providers and authoritative identity/context for any caller-dependent decisions. The demo above uses only operation names. |
| Enforce consent for data use | `ConsentConfig` | The consent graph, resource ownership, and the grants or approvals applicable to the request. |
| Constrain exchanges by contract | `ContractConfig` | Contract terms and the applicable identity/key and exchange configuration. |
| Preserve execution evidence | `ProvenanceConfig` | A ledger and retention/persistence choices appropriate to your environment. |
| Observe behavior and respond to changes | `ReflexiveConfig`, `AlertConfig` | Monitoring and escalation settings, event handling, and operational response procedures. |
| Review what enters a shared catalog | Registry certification and moderation settings | Publisher information, validation requirements, reviewer access, and publication policy. |

The [configuration definitions](../fastmcp_slim/fastmcp/server/security/config.py), [security overview](servers/security/overview.mdx), and [settings guide](servers/security/settings.mdx) describe the integration points. Configure and test each control against both permitted and rejected requests. An empty/default component configuration is not a complete organization-specific policy.

MCP already specifies transport authorization and consent principles. Continue to configure authentication, credentials, transport security, and data permissions for your deployment. The allowlist example does not replace those requirements. Likewise, monitoring is limited to what the system observes; it is not a guarantee against prompt injection or every malicious tool behavior.

## 6. Publish and operate a registry

A server and a catalog serve different purposes: the server executes MCP tools; the registry stores and governs their listings. The publisher CLI helps prepare the information used in a listing.

1. Run `purecipher-publisher init my-server --template http` to create a project.
2. Edit `my-server/purecipher.toml`, replace placeholder publisher and endpoint values, and implement/test its tools.
3. Run `purecipher-publisher check my-server`, then `purecipher-publisher package my-server`.
4. Configure the destination registry and authentication using the [publisher guide](servers/security/purecipher-publisher.mdx), then submit with `purecipher-publisher publish my-server`.
5. When running your own registry, configure its signing key, authentication, PostgreSQL persistence, and moderation requirements. Connect the [xregistry console](https://github.com/PureCipher/xregistry) to that backend.

The [hosted Hugging Face Space](https://huggingface.co/spaces/purecipher/xsecuremcp) runs the registry backend. Its App tab displays the usage guide, with a separate link to service health; it does not deploy the calculator in this guide or execute every server listed in a catalog. Review the [registry guide](servers/security/purecipher-registry.mdx) before using a shared deployment.
