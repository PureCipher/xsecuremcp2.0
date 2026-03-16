"""Artifact packaging for publisher projects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastmcp.server.security.gateway.tool_marketplace import ToolCategory, ToolListing
from purecipher.install import build_install_recipes
from purecipher.publisher.check import (
    PublisherCheckResult,
    build_manifest_payload,
    build_runtime_payload,
    check_project,
)
from purecipher.publisher.config import PublisherProjectConfig, load_publisher_config


@dataclass(frozen=True)
class PublisherPackageResult:
    """Summary of packaged artifacts for a publisher project."""

    project_root: Path
    output_dir: Path
    submission_payload_path: Path
    install_recipes_path: Path
    manifest_path: Path
    runtime_path: Path
    summary_json_path: Path
    summary_markdown_path: Path
    check: PublisherCheckResult

    def to_dict(self) -> dict[str, Any]:
        """Serialize for CLI JSON output."""

        return {
            "project_root": str(self.project_root),
            "output_dir": str(self.output_dir),
            "submission_payload_path": str(self.submission_payload_path),
            "install_recipes_path": str(self.install_recipes_path),
            "manifest_path": str(self.manifest_path),
            "runtime_path": str(self.runtime_path),
            "summary_json_path": str(self.summary_json_path),
            "summary_markdown_path": str(self.summary_markdown_path),
            "check": self.check.to_dict(),
        }


def _coerce_tool_categories(values: list[str]) -> set[ToolCategory]:
    categories: set[ToolCategory] = set()
    for value in values:
        try:
            categories.add(ToolCategory(value))
        except ValueError:
            categories.add(ToolCategory.OTHER)
    return categories


def build_submission_payload(config: PublisherProjectConfig) -> dict[str, Any]:
    """Build the registry submission payload from config."""

    return {
        "manifest": build_manifest_payload(config),
        "display_name": config.project.display_name,
        "description": config.project.description,
        "categories": list(config.metadata.categories),
        "homepage_url": config.publisher.homepage_url,
        "source_url": config.publisher.source_url,
        "tool_license": config.publisher.license,
        "tags": list(config.metadata.tags),
        "metadata": build_runtime_payload(config),
        "requested_level": config.registry.requested_level,
    }


def _render_package_listing(config: PublisherProjectConfig) -> ToolListing:
    return ToolListing(
        tool_name=config.project.name,
        display_name=config.project.display_name,
        description=config.project.description,
        version=config.project.version,
        author=config.project.publisher,
        categories=_coerce_tool_categories(list(config.metadata.categories)),
        homepage_url=config.publisher.homepage_url,
        source_url=config.publisher.source_url,
        license=config.publisher.license,
        tags=set(config.metadata.tags),
        metadata=build_runtime_payload(config),
    )


def package_project(
    project_root: str | Path = ".",
    *,
    output_dir: str | Path | None = None,
) -> PublisherPackageResult:
    """Generate package-ready publisher artifacts."""

    root = Path(project_root).resolve()
    config = load_publisher_config(root / "purecipher.toml")
    check = check_project(root)

    package_root = (
        Path(output_dir).resolve()
        if output_dir is not None
        else root / "dist" / "purecipher" / config.project.name
    )
    package_root.mkdir(parents=True, exist_ok=True)

    submission_payload = build_submission_payload(config)
    listing = _render_package_listing(config)
    recipes = [
        recipe.to_dict()
        for recipe in build_install_recipes(
            listing,
            registry_prefix="/registry",
            registry_base_url=config.registry.base_url,
        )
    ]

    submission_path = package_root / "submission.json"
    install_path = package_root / "install-recipes.json"
    manifest_path = package_root / "manifest.json"
    runtime_path = package_root / "runtime.json"
    summary_json_path = package_root / "package-summary.json"
    summary_markdown_path = package_root / "package-summary.md"

    submission_path.write_text(json.dumps(submission_payload, indent=2) + "\n")
    install_path.write_text(
        json.dumps(
            {
                "tool_name": config.project.name,
                "display_name": config.project.display_name,
                "recipes": recipes,
            },
            indent=2,
        )
        + "\n"
    )
    manifest_path.write_text(
        json.dumps(build_manifest_payload(config), indent=2) + "\n"
    )
    runtime_path.write_text(json.dumps(build_runtime_payload(config), indent=2) + "\n")
    summary_payload = {
        "tool_name": config.project.name,
        "display_name": config.project.display_name,
        "ready_to_publish": check.ready_to_publish,
        "issues": list(check.issues),
        "output_dir": str(package_root),
        "files": {
            "submission": str(submission_path),
            "install_recipes": str(install_path),
            "manifest": str(manifest_path),
            "runtime": str(runtime_path),
        },
        "install_recipe_titles": [recipe["title"] for recipe in recipes],
    }
    summary_json_path.write_text(json.dumps(summary_payload, indent=2) + "\n")
    summary_markdown_path.write_text(
        "\n".join(
            [
                f"# {config.project.display_name} package summary",
                "",
                f"- Ready to publish: {'yes' if check.ready_to_publish else 'no'}",
                f"- Output directory: `{package_root}`",
                f"- Submission payload: `{submission_path.name}`",
                f"- Install recipes: `{install_path.name}`",
                f"- Manifest: `{manifest_path.name}`",
                f"- Runtime metadata: `{runtime_path.name}`",
                "",
                "## Install recipe titles",
                *[f"- {recipe['title']}" for recipe in recipes],
            ]
        )
        + "\n"
    )

    return PublisherPackageResult(
        project_root=root,
        output_dir=package_root,
        submission_payload_path=submission_path,
        install_recipes_path=install_path,
        manifest_path=manifest_path,
        runtime_path=runtime_path,
        summary_json_path=summary_json_path,
        summary_markdown_path=summary_markdown_path,
        check=check,
    )


__all__ = [
    "PublisherPackageResult",
    "build_submission_payload",
    "package_project",
]
