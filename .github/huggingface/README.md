---
title: xSecureMCP by PureCipher
emoji: 🛡️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 8000
base_path: /
pinned: false
license: apache-2.0
short_description: Security and governance for MCP registries
---

# xSecureMCP

**Security and governance for MCP servers and tool registries.**

xSecureMCP is PureCipher’s platform for building MCP servers, applying execution policies, recording evidence, and publishing tools through a governed registry. It builds on FastMCP and includes the SecureMCP Python server layer, PureCipher Registry, and PureCipher Publisher CLI.

[GitHub project](https://github.com/PureCipher/xsecuremcp2.0) · [Python downloads](https://github.com/PureCipher/xsecuremcp2.0/releases/tag/build-latest) · [Registry console](https://github.com/PureCipher/xregistry) · [Documentation](https://github.com/PureCipher/xsecuremcp2.0/tree/main/docs/servers/security)

## What changes beyond MCP, and why

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

## How to use the project

1. **Try the backend:** use the health request below to inspect this Space. It is the registry service, not a general-purpose agent or the calculator example.
2. **Build a server:** install the matching fork packages, define your tools, and configure `SecurityConfig` for the controls your application needs.
3. **Connect a client:** point an MCP client at your server’s endpoint. The [server-and-client quickstart](https://github.com/PureCipher/xsecuremcp2.0#build-an-mcp-server) demonstrates a tool call and receipt verification.
4. **Check enforcement:** follow the [worked usage guide](https://github.com/PureCipher/xsecuremcp2.0/blob/main/docs/using-xsecuremcp.md) to allow one operation, deny another, and understand the resulting evidence.
5. **Share and operate:** use PureCipher Publisher to submit projects to your chosen registry, and the separate xregistry console to manage it. Configure authentication, moderation, and persistent storage for your deployment.

## What this Space runs

This Space hosts the **PureCipher Registry backend API** in a Docker container. It supports tool listings, publisher information, certification checks, moderation, and configurable access control.

The App tab displays this guide. Use the health-status link to inspect the running backend. The web console is maintained and deployed separately in [xregistry](https://github.com/PureCipher/xregistry); the backend’s legacy UI is disabled by default.

| Endpoint | Purpose |
| --- | --- |
| [`/registry/health`](https://purecipher-xsecuremcp.hf.space/registry/health) | Service status, authentication status, and registry counts. |
| [`/mcp`](https://purecipher-xsecuremcp.hf.space/mcp) | Streamable HTTP endpoint for MCP clients. |

Check the running service:

```bash
curl https://purecipher-xsecuremcp.hf.space/registry/health
```

A running service or a registry listing does not by itself establish that a tool is safe or that its execution has been observed.

## Use the Python packages

In a Python virtual environment, install the four matching fork distributions from the latest tested GitHub build:

```bash
python -m pip install --upgrade -r https://github.com/PureCipher/xsecuremcp2.0/releases/download/build-latest/requirements.txt
```

The distributions retain the names `fastmcp`, `fastmcp-slim`, `fastmcp-remote`, and `fastmcp-tasks` for compatibility. They include the `securemcp` and `purecipher` modules. Python 3.10 or later is required; builds are validated on Python 3.12.

See the [GitHub quickstart](https://github.com/PureCipher/xsecuremcp2.0#build-an-mcp-server) to build a server, or the [publisher guide](https://github.com/PureCipher/xsecuremcp2.0/blob/main/docs/servers/security/purecipher-publisher.mdx) to package and submit a project. The [GitHub Release](https://github.com/PureCipher/xsecuremcp2.0/releases/tag/build-latest) also provides a ZIP bundle, checksums, and source distributions.

## Configure your own deployment

Set configuration in **Space Settings → Variables and secrets**. Keep credentials in secrets.

| Setting | Purpose |
| --- | --- |
| `PURECIPHER_SIGNING_SECRET` | Required signing key for the registry. |
| `DATABASE_URL` | PostgreSQL connection string for persistent state. Without it, registry data is ephemeral and can be lost on restart. |
| `PURECIPHER_ENABLE_AUTH` | Enable registry authentication with `true`, together with the user and JWT configuration in the registry guide. |
| `PURECIPHER_REQUIRE_MODERATION` | Require review before accepted submissions become public by setting `true`. |

Authentication is disabled unless configured; a signing secret alone does not enable it. Check the live health response for the current authentication status. See the [registry guide](https://github.com/PureCipher/xsecuremcp2.0/blob/main/docs/servers/security/purecipher-registry.mdx) for deployment and access-control settings.

The container runs as user 1000 and listens on port 8000. It installs the tested Python wheels uploaded to this Space rather than rebuilding the packages from the older source files retained in the repository.

## Build provenance

| Field | Value |
| --- | --- |
| GitHub source | [`{{BUILD_COMMIT_SHORT}}`](https://github.com/PureCipher/xsecuremcp2.0/commit/{{BUILD_COMMIT}}) |
| Package version | `{{PACKAGE_VERSION}}` |
| Build metadata | [`build.json`](https://huggingface.co/spaces/purecipher/xsecuremcp/blob/main/build.json) |

Pushes to the GitHub repository’s `main` branch trigger tests, static checks, clean wheel installation checks, and Docker health checks before publication. Successful builds update this Space and replace its current wheel files. Hub history is retained.

FastMCP release updates are reviewed and merged manually. The publishing workflow does not write to the upstream FastMCP repository.

## License and attribution

Maintained by PureCipher. Built on [FastMCP](https://github.com/PrefectHQ/fastmcp) and distributed under the [Apache 2.0 license](https://github.com/PureCipher/xsecuremcp2.0/blob/main/LICENSE).
