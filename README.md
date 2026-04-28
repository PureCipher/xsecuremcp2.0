# SecureMCP

SecureMCP is a trust-native framework for building MCP servers on top of FastMCP.

This repository now contains three layers:

- `SecureMCP`: the secure server framework
- `PureCipher Registry`: a trusted registry for MCP tools and servers
- `PureCipher Publisher`: publisher tooling for scaffolding, checking, packaging, and publishing SecureMCP projects

## What SecureMCP adds

SecureMCP keeps the FastMCP server developer experience, but adds enforceable security controls around tool execution and distribution:

- explicit security manifests
- runtime policy enforcement
- consent and contract checks
- provenance and audit trails
- certification and attestation
- trust and moderation hooks

In plain terms: FastMCP exposes capability, and SecureMCP governs capability.

## Are we using FastMCP fully?

Mostly on the server side, yes.

`SecureMCP` subclasses `FastMCP`, so the normal FastMCP server surface remains available:

- tools
- resources
- prompts
- middleware
- transports
- auth integration
- server composition patterns

What is not yet fully re-expressed through SecureMCP branding is the broader FastMCP product surface:

- FastMCP client APIs are still FastMCP-first, not SecureMCP-first
- FastMCP app/UI concepts are not wrapped as SecureMCP features
- package metadata and some repo-level naming still reflect FastMCP
- the public README had still been mostly upstream FastMCP copy until this rewrite

So the right answer is:

- SecureMCP already inherits most of FastMCP's server capabilities
- SecureMCP does not yet present every FastMCP capability as a first-class SecureMCP product surface

## Quickstart

```python
from securemcp import SecureMCP
from securemcp.config import PolicyConfig, RegistryConfig, SecurityConfig

server = SecureMCP(
    "weather-lookup",
    security=SecurityConfig(
        policy=PolicyConfig(),
        registry=RegistryConfig(),
    ),
    mount_security_api=True,
)


@server.tool
def current_weather(city: str) -> str:
    return f"Sunny in {city}"


if __name__ == "__main__":
    server.run()
```

Because `SecureMCP` extends `FastMCP`, the normal FastMCP patterns for tools, resources, prompts, and transports still apply.

## PureCipher Registry

This repo also includes a working product layer called PureCipher: a trusted registry for MCP tools and servers.

Current PureCipher capabilities include:

- catalog and listing pages
- publisher pages
- moderation and review queue
- JWT auth and role-based access
- install recipes
- SQLite-backed persistence
- Docker launch flow

Launch it locally:

```bash
PURECIPHER_SIGNING_SECRET=development-secret uv run purecipher-registry
```

By default, the backend now serves the registry API only at:

- `http://127.0.0.1:8000/registry`

The legacy server-rendered UI is disabled by default. Use the Next.js console in `registry-ui/`, or opt back into the old backend UI with:

```bash
PURECIPHER_SIGNING_SECRET=development-secret uv run purecipher-registry --enable-legacy-ui
```

## PureCipher Publisher

This repo also includes publisher tooling for SecureMCP projects.

Current publisher commands:

- `purecipher-publisher templates`
- `purecipher-publisher init`
- `purecipher-publisher check`
- `purecipher-publisher login`
- `purecipher-publisher package`
- `purecipher-publisher publish`

Example flow:

```bash
uv run purecipher-publisher init weather-lookup --template http
cd weather-lookup
uv run purecipher-publisher check
uv run purecipher-publisher package
uv run purecipher-publisher publish
```

## Installation

Today, this repository still builds under the `fastmcp` distribution name in [pyproject.toml](pyproject.toml), while shipping three packages from the same source tree:

- `fastmcp`
- `securemcp`
- `purecipher`

For local development, use:

```bash
uv sync
```

If you want the repo installed in editable mode:

```bash
uv pip install -e .
```

The repo now exposes both `fastmcp` and `securemcp` console entrypoints.

- Use `fastmcp` for upstream FastMCP examples and workflows.
- Use `securemcp` for SecureMCP-specific examples and workflows.
- FastMCP behavior stays upstream-compatible; SecureMCP is the sibling secure layer.

## Repository shape

- [src/fastmcp](src/fastmcp): upstream FastMCP base
- [src/securemcp](src/securemcp): SecureMCP facade
- [src/purecipher](src/purecipher): registry and publisher product layer
- [docs/servers/security](docs/servers/security): SecureMCP and PureCipher docs

## Development

Required verification workflow:

```bash
uv sync
uv run pytest -n auto
uv run prek run --all-files
```

## Current positioning

The clean way to think about this repo now is:

- FastMCP is the engine
- SecureMCP is the secure server layer
- PureCipher is the trusted registry and publisher product layer

That is already enough to describe this codebase as more than a FastMCP fork. It is becoming a SecureMCP platform with a real product surface for both publishers and users.
