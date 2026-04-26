"""Project templates for the PureCipher publisher accelerator."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from purecipher.publisher.config import (
    MetadataSection,
    ProjectSection,
    PublisherProjectConfig,
    PublisherSection,
    RegistrySection,
    RuntimeSection,
)


@dataclass(frozen=True)
class PublisherTemplate:
    """Template metadata for a generated publisher project."""

    template_id: str
    label: str
    description: str
    transport: str
    categories: tuple[str, ...]
    tags: tuple[str, ...]
    permissions: tuple[str, ...]
    data_source: str
    data_destination: str
    data_classification: str
    data_description: str
    resource_pattern: str
    resource_access_type: str
    resource_description: str
    resource_classification: str
    endpoint_template: str
    docker_image_template: str


TEMPLATES: dict[str, PublisherTemplate] = {
    "http": PublisherTemplate(
        template_id="http",
        label="Remote HTTP",
        description="A streamable HTTP server for web-hosted tools.",
        transport="streamable-http",
        categories=("network", "utility"),
        tags=("api", "web"),
        permissions=("network_access",),
        data_source="input.query",
        data_destination="output.answer",
        data_classification="public",
        data_description="A request is sent to the publisher API and returned as a tool response.",
        resource_pattern="https://your-service-domain.tld/*",
        resource_access_type="read",
        resource_description="Calls the publisher API over HTTPS.",
        resource_classification="public",
        endpoint_template="https://mcp.your-service-domain.tld/{tool_name}",
        docker_image_template="ghcr.io/{publisher}/{tool_name}:0.1.0",
    ),
    "stdio": PublisherTemplate(
        template_id="stdio",
        label="Local stdio",
        description="A local process launched directly from an MCP client.",
        transport="stdio",
        categories=("file_system", "utility"),
        tags=("local", "desktop"),
        permissions=("read_resource",),
        data_source="resource.local_path",
        data_destination="output.summary",
        data_classification="internal",
        data_description="Reads local files from an approved path and returns a summary.",
        resource_pattern="file:///workspace/*",
        resource_access_type="read",
        resource_description="Reads files from an approved workspace path.",
        resource_classification="internal",
        endpoint_template="",
        docker_image_template="",
    ),
    "docker": PublisherTemplate(
        template_id="docker",
        label="Dockerized",
        description="A container-ready server with a web endpoint and local image metadata.",
        transport="streamable-http",
        categories=("data_access", "monitoring"),
        tags=("container", "ops"),
        permissions=("network_access",),
        data_source="input.query",
        data_destination="output.report",
        data_classification="confidential",
        data_description="Queries a backend service and returns a structured report.",
        resource_pattern="https://your-service-domain.tld/*",
        resource_access_type="read",
        resource_description="Calls the service API exposed by the publisher.",
        resource_classification="confidential",
        endpoint_template="https://mcp.your-service-domain.tld/{tool_name}",
        docker_image_template="ghcr.io/{publisher}/{tool_name}:0.1.0",
    ),
}


def normalize_project_name(value: str) -> str:
    """Normalize a CLI project name into the MCP naming style."""

    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not normalized:
        raise ValueError("Project name must include at least one letter or number.")
    return normalized


def module_name_for_tool(tool_name: str) -> str:
    """Return a Python-safe module name for a tool."""

    return tool_name.replace("-", "_")


def _display_name_from_tool(tool_name: str) -> str:
    return tool_name.replace("-", " ").title()


def available_templates() -> list[PublisherTemplate]:
    """Return all supported publisher templates."""

    return [TEMPLATES[key] for key in sorted(TEMPLATES)]


def get_template(template_name: str) -> PublisherTemplate:
    """Look up a publisher template by name."""

    try:
        return TEMPLATES[template_name]
    except KeyError as exc:
        valid = ", ".join(sorted(TEMPLATES))
        raise ValueError(
            f"Unknown template {template_name!r}. Expected one of: {valid}."
        ) from exc


def build_project_config(
    *,
    project_name: str,
    template_name: str,
    publisher_name: str = "your-team",
    registry_base_url: str = "http://127.0.0.1:8000",
) -> PublisherProjectConfig:
    """Build the default config for a newly scaffolded project."""

    tool_name = normalize_project_name(project_name)
    template = get_template(template_name)
    endpoint = template.endpoint_template.format(
        publisher=publisher_name,
        tool_name=tool_name,
    )
    docker_image = template.docker_image_template.format(
        publisher=publisher_name,
        tool_name=tool_name,
    )

    return PublisherProjectConfig(
        project=ProjectSection(
            name=tool_name,
            display_name=_display_name_from_tool(tool_name),
            description=f"{_display_name_from_tool(tool_name)} built with the PureCipher publisher accelerator.",
            publisher=publisher_name,
            template=template.template_id,
        ),
        publisher=PublisherSection(
            source_url=f"https://github.com/{publisher_name}/{tool_name}",
            homepage_url=endpoint if endpoint else "",
        ),
        registry=RegistrySection(base_url=registry_base_url),
        runtime=RuntimeSection(
            transport=template.transport,
            endpoint=endpoint,
            command="uv",
            args=["run", "python", "app.py"],
            docker_image=docker_image,
        ),
        metadata=MetadataSection(
            categories=list(template.categories),
            tags=list(template.tags),
        ),
    )


def _build_pyproject(config: PublisherProjectConfig) -> str:
    return f"""[project]
name = {json.dumps(config.project.name)}
version = {json.dumps(config.project.version)}
description = {json.dumps(config.project.description)}
requires-python = ">=3.10"
dependencies = ["fastmcp>=0.0.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
"""


def _build_app_py(config: PublisherProjectConfig) -> str:
    template = get_template(config.project.template)
    module_name = module_name_for_tool(config.project.name)
    tool_function_name = module_name
    transport_line = (
        '    app.run(transport="stdio")'
        if template.transport == "stdio"
        else '    app.run(transport="streamable-http", host="127.0.0.1", port=8000)'
    )

    return f'''from securemcp import SecureMCP

from tools.{module_name} import build_response

app = SecureMCP({config.project.name!r})


@app.tool(name={config.project.name!r})
def {tool_function_name}(query: str) -> str:
    """Sample tool generated by the PureCipher publisher accelerator."""

    return build_response(query)


if __name__ == "__main__":
{transport_line}
'''


def _build_tool_module(config: PublisherProjectConfig) -> str:
    return f'''"""Business logic for {config.project.display_name}."""


def build_response(query: str) -> str:
    """Return a simple placeholder response for local development."""

    return (
        "This is the starter response for {config.project.display_name}. "
        f"Update tools/{module_name_for_tool(config.project.name)}.py to handle: {{query}}"
    )
'''


def _build_test(config: PublisherProjectConfig) -> str:
    module_name = module_name_for_tool(config.project.name)
    return f"""from fastmcp.client import Client

from app import app


async def test_{module_name}_smoke():
    async with Client(app) as client:
        result = await client.call_tool({config.project.name!r}, {{"query": "status"}})

    assert result
"""


def _build_readme(config: PublisherProjectConfig) -> str:
    return f"""# {config.project.display_name}

This project was scaffolded by the PureCipher Publisher Accelerator.

## Local workflow

```bash
uv sync
uv run python app.py
uv run purecipher-publisher check .
```

## Files to edit first

- `purecipher.toml` for publisher metadata and runtime details
- `tools/{module_name_for_tool(config.project.name)}.py` for tool logic
- `app.py` if you want to add more tools or transports
"""


def _build_dockerfile() -> str:
    return """FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md purecipher.toml manifest.json runtime.json app.py ./
COPY tools ./tools

RUN uv sync --no-dev

CMD ["uv", "run", "python", "app.py"]
"""


def render_project_files(config: PublisherProjectConfig) -> dict[Path, str]:
    """Return the file map for a generated publisher project."""

    module_name = module_name_for_tool(config.project.name)
    return {
        Path("pyproject.toml"): _build_pyproject(config),
        Path("app.py"): _build_app_py(config),
        Path("purecipher.toml"): config.to_toml(),
        Path("README.md"): _build_readme(config),
        Path("Dockerfile"): _build_dockerfile(),
        Path("tools/__init__.py"): "",
        Path(f"tools/{module_name}.py"): _build_tool_module(config),
        Path("tests/test_smoke.py"): _build_test(config),
    }


__all__ = [
    "PublisherTemplate",
    "available_templates",
    "build_project_config",
    "get_template",
    "module_name_for_tool",
    "normalize_project_name",
    "render_project_files",
]
