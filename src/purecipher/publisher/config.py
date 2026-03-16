"""Configuration models and TOML helpers for publisher projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectSection(BaseModel):
    """Core project metadata for a publisher scaffold."""

    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    version: str = "0.1.0"
    description: str
    publisher: str = "your-team"
    template: str = "http"


class PublisherSection(BaseModel):
    """Publisher-owned listing metadata."""

    model_config = ConfigDict(extra="forbid")

    source_url: str = ""
    homepage_url: str = ""
    license: str = "MIT"


class RegistrySection(BaseModel):
    """Registry submission defaults."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://127.0.0.1:8000"
    requested_level: str = "basic"


class RuntimeSection(BaseModel):
    """Runtime metadata used for install and publish artifacts."""

    model_config = ConfigDict(extra="forbid")

    transport: str = "streamable-http"
    endpoint: str = ""
    command: str = "uv"
    args: list[str] = Field(default_factory=list)
    docker_image: str = ""


class MetadataSection(BaseModel):
    """Tags and categories for the listing."""

    model_config = ConfigDict(extra="forbid")

    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class PublisherProjectConfig(BaseModel):
    """Typed representation of ``purecipher.toml``."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectSection
    publisher: PublisherSection
    registry: RegistrySection
    runtime: RuntimeSection
    metadata: MetadataSection

    def to_toml(self) -> str:
        """Render the config back into a predictable TOML layout."""

        lines = [
            "[project]",
            f"name = {json.dumps(self.project.name)}",
            f"display_name = {json.dumps(self.project.display_name)}",
            f"version = {json.dumps(self.project.version)}",
            f"description = {json.dumps(self.project.description)}",
            f"publisher = {json.dumps(self.project.publisher)}",
            f"template = {json.dumps(self.project.template)}",
            "",
            "[publisher]",
            f"source_url = {json.dumps(self.publisher.source_url)}",
            f"homepage_url = {json.dumps(self.publisher.homepage_url)}",
            f"license = {json.dumps(self.publisher.license)}",
            "",
            "[registry]",
            f"base_url = {json.dumps(self.registry.base_url)}",
            f"requested_level = {json.dumps(self.registry.requested_level)}",
            "",
            "[runtime]",
            f"transport = {json.dumps(self.runtime.transport)}",
            f"endpoint = {json.dumps(self.runtime.endpoint)}",
            f"command = {json.dumps(self.runtime.command)}",
            f"args = {json.dumps(self.runtime.args)}",
            f"docker_image = {json.dumps(self.runtime.docker_image)}",
            "",
            "[metadata]",
            f"categories = {json.dumps(self.metadata.categories)}",
            f"tags = {json.dumps(self.metadata.tags)}",
            "",
        ]
        return "\n".join(lines)


def _parse_toml_value(raw_value: str) -> Any:
    value = raw_value.strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _fallback_parse_toml(text: str) -> dict[str, Any]:
    current_section: str | None = None
    payload: dict[str, Any] = {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip()
            payload[current_section] = {}
            continue

        if current_section is None:
            raise ValueError("Invalid PureCipher config: expected a section header.")

        key, separator, value = stripped.partition("=")
        if separator != "=":
            raise ValueError(f"Invalid PureCipher config line: {stripped!r}")

        payload[current_section][key.strip()] = _parse_toml_value(value)

    return payload


def load_publisher_config(config_path: str | Path) -> PublisherProjectConfig:
    """Load ``purecipher.toml`` from disk."""

    path = Path(config_path)
    text = path.read_text()

    try:
        import tomllib
    except ModuleNotFoundError:
        payload = _fallback_parse_toml(text)
    else:
        payload = tomllib.loads(text)

    return PublisherProjectConfig.model_validate(payload)


def write_publisher_config(
    config_path: str | Path,
    config: PublisherProjectConfig,
) -> Path:
    """Write ``purecipher.toml`` to disk."""

    path = Path(config_path)
    path.write_text(config.to_toml())
    return path


__all__ = [
    "MetadataSection",
    "ProjectSection",
    "PublisherProjectConfig",
    "PublisherSection",
    "RegistrySection",
    "RuntimeSection",
    "load_publisher_config",
    "write_publisher_config",
]
