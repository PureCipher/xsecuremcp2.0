"""Local artifact generation and readiness checks for publisher projects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from purecipher.publisher.config import PublisherProjectConfig, load_publisher_config
from purecipher.publisher.templates import get_template


@dataclass(frozen=True)
class PublisherCheckResult:
    """Summary of a local publisher project check."""

    project_root: Path
    config_path: Path
    manifest_path: Path
    runtime_path: Path
    template: str
    transport: str
    ready_to_publish: bool
    manifest_updated: bool
    runtime_updated: bool
    issues: list[str]
    next_steps: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result for CLI JSON output."""

        return {
            "project_root": str(self.project_root),
            "config_path": str(self.config_path),
            "manifest_path": str(self.manifest_path),
            "runtime_path": str(self.runtime_path),
            "template": self.template,
            "transport": self.transport,
            "ready_to_publish": self.ready_to_publish,
            "manifest_updated": self.manifest_updated,
            "runtime_updated": self.runtime_updated,
            "issues": list(self.issues),
            "next_steps": list(self.next_steps),
        }


def _render_artifact_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2) + "\n"


def build_manifest_payload(config: PublisherProjectConfig) -> dict[str, Any]:
    """Generate a starter ``manifest.json`` payload from project config."""

    template = get_template(config.project.template)
    return {
        "tool_name": config.project.name,
        "version": config.project.version,
        "author": config.project.publisher,
        "description": config.project.description,
        "permissions": list(template.permissions),
        "data_flows": [
            {
                "source": template.data_source,
                "destination": template.data_destination,
                "classification": template.data_classification,
                "description": template.data_description,
            }
        ],
        "resource_access": [
            {
                "resource_pattern": template.resource_pattern,
                "access_type": template.resource_access_type,
                "description": template.resource_description,
                "classification": template.resource_classification,
            }
        ],
        "tags": list(config.metadata.tags),
    }


def build_runtime_payload(config: PublisherProjectConfig) -> dict[str, Any]:
    """Generate a starter ``runtime.json`` payload from project config."""

    payload: dict[str, Any] = {
        "transport": config.runtime.transport,
        "command": config.runtime.command,
        "args": list(config.runtime.args),
    }
    if config.runtime.endpoint:
        payload["endpoint"] = config.runtime.endpoint
    if config.runtime.docker_image:
        payload["docker_image"] = config.runtime.docker_image
    return payload


def _sync_json_artifact(
    path: Path,
    payload: dict[str, Any],
    *,
    overwrite: bool,
) -> bool:
    rendered = _render_artifact_payload(payload)
    previous = path.read_text() if path.exists() else None
    if previous is not None and not overwrite:
        return False
    path.write_text(rendered)
    return previous != rendered


def sync_project_artifacts(
    project_root: str | Path,
    config: PublisherProjectConfig,
    *,
    overwrite: bool = True,
) -> tuple[bool, bool]:
    """Write ``manifest.json`` and ``runtime.json`` from config."""

    root = Path(project_root)
    manifest_updated = _sync_json_artifact(
        root / "manifest.json",
        build_manifest_payload(config),
        overwrite=overwrite,
    )
    runtime_updated = _sync_json_artifact(
        root / "runtime.json",
        build_runtime_payload(config),
        overwrite=overwrite,
    )
    return manifest_updated, runtime_updated


def _build_artifact_issues(
    *,
    project_root: Path,
    config: PublisherProjectConfig,
) -> list[str]:
    issues: list[str] = []
    generated = {
        "manifest.json": _render_artifact_payload(build_manifest_payload(config)),
        "runtime.json": _render_artifact_payload(build_runtime_payload(config)),
    }

    for filename, rendered in generated.items():
        path = project_root / filename
        if not path.exists():
            issues.append(
                f"Missing generated artifact: {filename}. Run "
                "`purecipher-publisher check --refresh-artifacts` to restore it."
            )
            continue
        if path.read_text() != rendered:
            issues.append(
                f"{filename} no longer matches purecipher.toml. Update "
                "purecipher.toml or rerun `purecipher-publisher check "
                "--refresh-artifacts`."
            )

    return issues


def _looks_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(
        marker in lowered for marker in ("your-team", "example", "todo", "change-me")
    )


def _build_issues(
    *,
    project_root: Path,
    config: PublisherProjectConfig,
) -> list[str]:
    issues: list[str] = []

    for required in ("app.py", "purecipher.toml", "README.md"):
        if not (project_root / required).exists():
            issues.append(f"Missing required file: {required}.")

    if _looks_placeholder(config.project.publisher):
        issues.append("Replace the placeholder publisher name in purecipher.toml.")
    if _looks_placeholder(config.publisher.source_url):
        issues.append("Add a real source URL for the project.")
    if config.publisher.homepage_url and _looks_placeholder(
        config.publisher.homepage_url
    ):
        issues.append("Replace the example homepage URL with a real public page.")
    if config.runtime.transport != "stdio" and _looks_placeholder(
        config.runtime.endpoint
    ):
        issues.append("Replace the example endpoint with the real MCP endpoint.")
    if config.runtime.docker_image and _looks_placeholder(config.runtime.docker_image):
        issues.append(
            "Replace the example Docker image with the image you plan to publish."
        )

    return issues


def _build_next_steps(
    *,
    config: PublisherProjectConfig,
    issues: list[str],
) -> list[str]:
    steps = [
        "Edit purecipher.toml with your real publisher metadata.",
        "Update the generated tool implementation in tools/ and app.py.",
        "Run `purecipher-publisher check --refresh-artifacts` after metadata edits.",
    ]
    if any("manifest.json" in issue or "runtime.json" in issue for issue in issues):
        steps.append(
            "Refresh the generated JSON snapshots once purecipher.toml is correct."
        )
    if not issues:
        steps.append(
            f"Next publisher phase: package and publish {config.project.display_name} to {config.registry.base_url}."
        )
    return steps


def check_project(
    project_root: str | Path = ".",
    *,
    refresh_artifacts: bool = False,
) -> PublisherCheckResult:
    """Load a project, sync artifacts, and return a readiness summary."""

    root = Path(project_root).resolve()
    config_path = root / "purecipher.toml"
    config = load_publisher_config(config_path)
    manifest_updated, runtime_updated = sync_project_artifacts(
        root,
        config,
        overwrite=refresh_artifacts,
    )
    issues = _build_issues(project_root=root, config=config)
    issues.extend(_build_artifact_issues(project_root=root, config=config))

    return PublisherCheckResult(
        project_root=root,
        config_path=config_path,
        manifest_path=root / "manifest.json",
        runtime_path=root / "runtime.json",
        template=config.project.template,
        transport=config.runtime.transport,
        ready_to_publish=not issues,
        manifest_updated=manifest_updated,
        runtime_updated=runtime_updated,
        issues=issues,
        next_steps=_build_next_steps(config=config, issues=issues),
    )


__all__ = [
    "PublisherCheckResult",
    "build_manifest_payload",
    "build_runtime_payload",
    "check_project",
    "sync_project_artifacts",
]
