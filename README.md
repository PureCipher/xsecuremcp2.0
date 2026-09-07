# xSecureMCP

**Security and governance for MCP servers and tool registries.**

xSecureMCP is PureCipher’s platform for building MCP servers, applying execution policies, recording evidence, and publishing tools through a governed registry. It builds on [FastMCP](https://github.com/PrefectHQ/fastmcp) and keeps its Python APIs for tools, resources, prompts, clients, and transports.

[Python downloads](https://github.com/PureCipher/xsecuremcp2.0/releases/tag/build-latest) · [Hugging Face backend](https://huggingface.co/spaces/purecipher/xsecuremcp) · [Registry console](https://github.com/PureCipher/xregistry) · [Security documentation](docs/servers/security/overview.mdx)

## What’s included

| Component | Purpose |
| --- | --- |
| **SecureMCP** | A Python server layer that connects FastMCP to configurable policy, consent, contracts, provenance, and certification controls. |
| **PureCipher Registry** | A backend for tool listings, publisher information, certification checks, moderation, and access control. |
| **PureCipher Publisher** | CLI tools to scaffold, validate, package, and submit MCP projects to a registry. |
| **xregistry** | The companion web console, maintained in the separate [xregistry repository](https://github.com/PureCipher/xregistry). |

Security controls are configured explicitly for each deployment. Subclassing `FastMCP` or listing a tool in a registry does not by itself establish that a tool is safe or that every control has been applied.

## How xSecureMCP extends MCP

**MCP is the protocol; FastMCP is a Python framework; xSecureMCP adds configurable security and governance components on top.** xSecureMCP does not define a replacement wire protocol. MCP clients still discover and call tools using MCP messages.

MCP already describes [authorization for HTTP transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization), user consent, and [security responsibilities for implementers](https://modelcontextprotocol.io/specification/2025-11-25). FastMCP already provides server/client APIs, middleware, and authentication integration. The additions below are implementation features in this fork, not claims that MCP or FastMCP lack security.

| Area | xSecureMCP adds | Why it matters |
| --- | --- | --- |
| **Execution policy** | Configurable policy providers that evaluate operations and can deny execution, with fail-closed handling when configured. | Being authenticated does not mean a caller should be allowed to perform every operation. For example, an assistant may read a record while being forbidden to reset it. |
| **Consent and contracts** | Consent graphs and contract checks that applications can connect to their identity, approval, and resource rules. | Access can depend on who owns the data, what was approved, and the permitted scope of use—not just whether a request is well formed. |
| **Provenance and execution receipts** | Ledger records and portable receipts with outcome claims, input/output digests, and integrity proofs. | Operators and clients can inspect evidence about an observed execution when debugging or reviewing an incident. |
| **Publication and certification** | Publisher manifests, validation, certification checks, registry listings, and optional moderation. | Teams need a review process for what enters their tool catalog, with publisher and trust information alongside connection details. |
| **Monitoring and response** | Configurable behavioral analysis, security events, and escalation components. | A tool that passed an initial review can still need investigation when observed behavior changes. |
| **Operational governance** | Policy audit trails, registry roles, and governance views in the companion console. | Administrators need to review access decisions and manage the tool lifecycle across a team. |

These features only cover the execution paths and evidence sources connected to them. A catalog listing does not instrument a remote server. Tool annotations are not enforcement, a receipt is not a guarantee of truthful output, and enabling a policy module does not automatically establish regulatory compliance or process isolation.

For example, consider an assistant working with customer records: MCP carries the tool call; authentication establishes the caller; a configured policy decides whether that caller may read or change the record; consent and contract checks evaluate applicable permissions; provenance records the execution that reaches it. Each control answers a different question. Their coverage and ordering depend on the server configuration.

## Choose how to use it

| Your goal | Start here |
| --- | --- |
| Build or adapt an MCP server | Install the fork, define your tools, then enable the controls you need through `SecurityConfig`. Follow the [worked usage guide](docs/using-xsecuremcp.md). |
| Call a server from an application or agent | Connect an MCP client to that server’s endpoint. Receipt-aware clients can additionally inspect the xSecureMCP result metadata. |
| Publish a tool for others to discover | Scaffold and edit a publisher project, validate it, configure its registry destination, and submit it with the publisher CLI. |
| Operate a shared tool catalog | Run PureCipher Registry with authentication and PostgreSQL, then connect the separate xregistry console. |
| Inspect the hosted backend | Open the Hugging Face Space’s health response. The Space is a registry backend; it does not host the calculator example below. |

## Install the latest tested build

Python **3.10 or later** is required. The build workflow validates packages on Python **3.12**.

Create and activate a virtual environment, then install the matching fork packages from the rolling GitHub Release:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade -r https://github.com/PureCipher/xsecuremcp2.0/releases/download/build-latest/requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell.

The bundle contains four distributions: `fastmcp`, `fastmcp-slim`, `fastmcp-remote`, and `fastmcp-tasks`. These names are retained for compatibility; the fork also provides the `securemcp` and `purecipher` Python modules and command-line tools. Installing `fastmcp` directly from PyPI selects the upstream distribution.

The [rolling release](https://github.com/PureCipher/xsecuremcp2.0/releases/tag/build-latest) also provides a ZIP bundle, source distributions, dependency constraints, checksums, and build metadata. It is a development build from this repository’s `main` branch. See [builds and installation](.github/WORKFLOWS.md) for details.

## Build an MCP server

Save this as `server.py`. It creates an HTTP MCP server with provenance enabled:

```python
from securemcp import SecureMCP, SecurityConfig
from securemcp.config import ProvenanceConfig

server = SecureMCP(
    "calculator",
    security=SecurityConfig(provenance=ProvenanceConfig()),
)


@server.tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


if __name__ == "__main__":
    server.run(transport="http", host="127.0.0.1", port=8000)
```

Run `python server.py`, then connect an MCP client to `http://127.0.0.1:8000/mcp`. This example enables provenance; choose the additional policy, identity, consent, and contract settings needed for your application in the [security configuration guide](docs/servers/security/settings.mdx).

### Call the server

With `server.py` running, save the following as `client.py` and run `python client.py` in the same virtual environment:

```python
import asyncio

from fastmcp import Client
from securemcp.receipts import RECEIPT_META_KEY, verify_execution_receipt


async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
        print(result.data)  # 5
        receipt = result.meta[RECEIPT_META_KEY]
        print(verify_execution_receipt(receipt)["valid"])  # True


asyncio.run(main())
```

The normal tool result remains available to MCP clients. Receipt verification is an explicit client action; clients that do not inspect the metadata do not automatically verify it. The example checks internal integrity. For independently anchored verification, supply a ledger root obtained through a trusted channel.

Continue with the [worked usage guide](docs/using-xsecuremcp.md) to add an execution policy and confirm that a disallowed tool is blocked. That guide also covers adopting the fork in an existing FastMCP server and operating a registry.

### Execution receipts

With provenance enabled, completed tool calls can carry an execution receipt containing outcome claims, input/output digests, and a ledger inclusion proof. Clients can inspect and verify these receipts through the public `securemcp` API.

Receipt verification checks integrity and consistency. Authenticating an issuer or establishing the truth of a reported outcome requires an appropriate trust relationship; a self-consistent receipt alone does not establish either. See [Execution Receipts](docs/execution-receipts.md) for usage, coverage, and verification boundaries.

## Run the registry backend

The registry serves an API. Use [xregistry](https://github.com/PureCipher/xregistry) for the web console; the backend’s legacy UI is disabled by default.

For a local evaluation, generate a signing secret and start the backend:

```bash
export PURECIPHER_SIGNING_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
purecipher-registry --host 127.0.0.1 --port 8001
```

Check it from another terminal:

```bash
curl http://127.0.0.1:8001/registry/health
```

Connect the console by setting its `REGISTRY_BACKEND_URL` to `http://127.0.0.1:8001`.

### Docker

The latest tested Linux AMD64 image is available from GitHub Container Registry:

```bash
docker pull ghcr.io/purecipher/xsecuremcp2.0:latest
docker run --rm -p 127.0.0.1:8001:8000 \
  -e PURECIPHER_SIGNING_SECRET \
  ghcr.io/purecipher/xsecuremcp2.0:latest
```

Use the signing-secret environment variable from the local example above. If the image requires authentication, sign in to `ghcr.io` with credentials that can read the package.

### Deployment settings

| Setting | Behavior |
| --- | --- |
| `PURECIPHER_SIGNING_SECRET` | Required registry signing key. Supply it through your deployment’s secret store. |
| `DATABASE_URL` | PostgreSQL connection string for persistent registry state. Without it, state is ephemeral. |
| `PURECIPHER_ENABLE_AUTH` | Set to `true` to enable registry authentication; configure users and JWT settings as described in the registry guide. |
| `PURECIPHER_REQUIRE_MODERATION` | Set to `true` to place accepted submissions into review before publication. |

A signing secret does not enable user authentication. Review [registry configuration](docs/servers/security/purecipher-registry.mdx) before operating a shared deployment.

### Hugging Face

The [PureCipher xSecureMCP Space](https://huggingface.co/spaces/purecipher/xsecuremcp) runs the registry backend and opens its [health endpoint](https://purecipher-xsecuremcp.hf.space/registry/health). Its Docker container installs the same wheels tested by GitHub Actions. The web console is deployed separately.

## Package and publish a project

Start with the publisher CLI:

```bash
purecipher-publisher templates
purecipher-publisher init weather-lookup --template http
cd weather-lookup
purecipher-publisher check
purecipher-publisher package
```

Use `purecipher-publisher login --help` and `purecipher-publisher publish --help` to configure authentication and submit to your registry. The [publisher guide](docs/servers/security/purecipher-publisher.mdx) covers templates, manifests, packaging, and submission.

## Builds and upstream updates

Every push to `PureCipher/xsecuremcp2.0:main` runs tests and static checks, builds the Python packages and Docker images, and checks clean installations and registry health before publication. Successful builds replace the rolling GitHub Release assets and Docker `latest`, then update the Hugging Face Space.

A separate daily workflow reports new stable FastMCP releases for manual review. Upstream release-tag imports and merges remain manual. Neither workflow pushes changes to `PrefectHQ/fastmcp`.

See [workflow configuration and retention](.github/WORKFLOWS.md) for permissions, notification setup, and publication behavior.

## Develop from source

```bash
git clone https://github.com/PureCipher/xsecuremcp2.0.git
cd xsecuremcp2.0
uv sync
uv run pytest -n auto
uv run prek run --all-files
```

| Location | Contents |
| --- | --- |
| [`src/securemcp`](src/securemcp) | SecureMCP server API, configuration, and receipt helpers. |
| [`src/purecipher`](src/purecipher) | Registry backend and publisher tooling. |
| [`fastmcp_slim/fastmcp`](fastmcp_slim/fastmcp) | FastMCP core and security implementation. |
| [`fastmcp_remote`](fastmcp_remote), [`fastmcp_tasks`](fastmcp_tasks) | Remote and task support packages. |
| [`tests`](tests) | Framework, registry, security, and packaging tests. |

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes.

## License and attribution

Licensed under [Apache 2.0](LICENSE). xSecureMCP is maintained by PureCipher and builds on the work of [FastMCP](https://github.com/PrefectHQ/fastmcp) and its contributors.
