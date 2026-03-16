"""CLI for the PureCipher publisher accelerator."""

from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path
from typing import Any

from purecipher.publisher.auth import login_to_registry
from purecipher.publisher.check import check_project, sync_project_artifacts
from purecipher.publisher.config import load_publisher_config, write_publisher_config
from purecipher.publisher.package import package_project
from purecipher.publisher.publish import publish_project
from purecipher.publisher.templates import (
    available_templates,
    build_project_config,
    get_template,
    render_project_files,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the publisher CLI parser."""

    parser = argparse.ArgumentParser(
        prog="purecipher-publisher",
        description="Scaffold and validate SecureMCP projects for PureCipher publishers.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    templates_parser = subparsers.add_parser(
        "templates",
        help="List the built-in project templates.",
    )
    templates_parser.set_defaults(handler=_handle_templates)

    init_parser = subparsers.add_parser(
        "init",
        help="Create a new SecureMCP publisher project.",
    )
    init_parser.add_argument("name", help="Project and tool name.")
    init_parser.add_argument(
        "--template",
        default="http",
        choices=[template.template_id for template in available_templates()],
        help="Starter project shape.",
    )
    init_parser.add_argument(
        "--path",
        default=None,
        help="Output directory. Defaults to a folder matching the project name.",
    )
    init_parser.add_argument(
        "--publisher",
        default="your-team",
        help="Publisher slug written into the starter config.",
    )
    init_parser.add_argument(
        "--registry-url",
        default="http://127.0.0.1:8000",
        help="Default PureCipher Registry base URL.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Allow initialization in an existing empty directory.",
    )
    init_parser.set_defaults(handler=_handle_init)

    check_parser = subparsers.add_parser(
        "check",
        help="Sync generated artifacts and report local publish readiness.",
    )
    check_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project directory. Defaults to the current directory.",
    )
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the check result as JSON.",
    )
    check_parser.set_defaults(handler=_handle_check)

    package_parser = subparsers.add_parser(
        "package",
        help="Write publish-ready artifacts into a dist directory.",
    )
    package_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project directory. Defaults to the current directory.",
    )
    package_parser.add_argument(
        "--output-dir",
        default=None,
        help="Override the package output directory.",
    )
    package_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the package result as JSON.",
    )
    package_parser.set_defaults(handler=_handle_package)

    login_parser = subparsers.add_parser(
        "login",
        help="Authenticate against PureCipher Registry and store a token locally.",
    )
    login_parser.add_argument(
        "--registry-url",
        default=None,
        help="Registry base URL. Defaults to the value in purecipher.toml when available.",
    )
    login_parser.add_argument(
        "--project-path",
        default=".",
        help="Project directory used to discover purecipher.toml when --registry-url is omitted.",
    )
    login_parser.add_argument("--username", required=True)
    login_parser.add_argument(
        "--password",
        default=None,
        help="Password for the registry account. If omitted, the CLI prompts for it.",
    )
    login_parser.add_argument(
        "--auth-file",
        default=None,
        help="Override the local auth storage path.",
    )
    login_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the login result as JSON.",
    )
    login_parser.set_defaults(handler=_handle_login)

    publish_parser = subparsers.add_parser(
        "publish",
        help="Run preflight and submit the project to PureCipher Registry.",
    )
    publish_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project directory. Defaults to the current directory.",
    )
    publish_parser.add_argument(
        "--registry-url",
        default=None,
        help="Registry base URL. Defaults to the value in purecipher.toml.",
    )
    publish_parser.add_argument(
        "--auth-file",
        default=None,
        help="Override the local auth storage path.",
    )
    publish_parser.add_argument(
        "--token",
        default=None,
        help="Registry bearer token. Overrides the stored token and PURECIPHER_PUBLISHER_TOKEN.",
    )
    publish_parser.add_argument(
        "--output-dir",
        default=None,
        help="Override the package output directory used during publish.",
    )
    publish_parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Allow publish even if the local check still reports placeholder metadata.",
    )
    publish_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the publish result as JSON.",
    )
    publish_parser.set_defaults(handler=_handle_publish)

    return parser


def _write_project_files(project_root: Path, file_map: dict[Path, str]) -> None:
    for relative_path, content in file_map.items():
        destination = project_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)


def init_project(
    *,
    project_name: str,
    template_name: str,
    project_root: str | Path | None = None,
    publisher_name: str = "your-team",
    registry_base_url: str = "http://127.0.0.1:8000",
    force: bool = False,
) -> Path:
    """Create a new publisher project on disk."""

    config = build_project_config(
        project_name=project_name,
        template_name=template_name,
        publisher_name=publisher_name,
        registry_base_url=registry_base_url,
    )
    destination = Path(project_root or config.project.name).resolve()

    if destination.exists():
        existing = list(destination.iterdir())
        if existing:
            raise ValueError(
                f"Refusing to initialize in non-empty directory: {destination}"
            )
        if not force and existing == []:
            raise ValueError(
                f"Directory already exists: {destination}. Pass --force to initialize it anyway."
            )
    else:
        destination.mkdir(parents=True, exist_ok=True)

    file_map = render_project_files(config)
    _write_project_files(destination, file_map)
    write_publisher_config(destination / "purecipher.toml", config)
    sync_project_artifacts(destination, config)
    return destination


def _render_check_text(result: Any) -> str:
    updated_files = []
    if result.manifest_updated:
        updated_files.append("manifest.json")
    if result.runtime_updated:
        updated_files.append("runtime.json")
    updated_line = ", ".join(updated_files) if updated_files else "none"

    lines = [
        "PureCipher publisher check",
        f"Project: {result.project_root.name}",
        f"Template: {result.template}",
        f"Transport: {result.transport}",
        f"Ready to publish: {'yes' if result.ready_to_publish else 'no'}",
        f"Updated artifacts: {updated_line}",
    ]
    if result.issues:
        lines.append("Needs attention:")
        lines.extend(f"- {issue}" for issue in result.issues)
    else:
        lines.append("Needs attention: none")

    lines.append("Next steps:")
    lines.extend(f"- {step}" for step in result.next_steps)
    return "\n".join(lines)


def _resolve_registry_url(
    *,
    registry_url: str | None,
    project_path: str | Path,
) -> str:
    if registry_url:
        return registry_url
    config = load_publisher_config(Path(project_path).resolve() / "purecipher.toml")
    return config.registry.base_url


def _handle_templates(args: argparse.Namespace) -> int:
    for template in available_templates():
        print(f"{template.template_id}: {template.label} - {template.description}")
    return 0


def _handle_init(args: argparse.Namespace) -> int:
    template = get_template(args.template)
    destination = init_project(
        project_name=args.name,
        template_name=template.template_id,
        project_root=args.path,
        publisher_name=args.publisher,
        registry_base_url=args.registry_url,
        force=args.force,
    )
    config = load_publisher_config(destination / "purecipher.toml")

    print(f"Created publisher project at {destination}")
    print(f"Template: {template.label}")
    print(f"Project: {config.project.display_name}")
    print("Next steps:")
    print(f"- cd {destination}")
    print("- Edit purecipher.toml with your real publisher metadata.")
    print(
        "- Run `purecipher-publisher check` to refresh manifest.json and runtime.json."
    )
    return 0


def _handle_check(args: argparse.Namespace) -> int:
    result = check_project(args.path)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(_render_check_text(result))
    return 0


def _handle_package(args: argparse.Namespace) -> int:
    result = package_project(args.path, output_dir=args.output_dir)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    print(f"Packaged project into {result.output_dir}")
    print(f"- submission payload: {result.submission_payload_path}")
    print(f"- install recipes: {result.install_recipes_path}")
    print(f"- manifest: {result.manifest_path}")
    print(f"- runtime: {result.runtime_path}")
    print(f"- summary json: {result.summary_json_path}")
    print(f"- summary markdown: {result.summary_markdown_path}")
    print(f"- ready to publish: {'yes' if result.check.ready_to_publish else 'no'}")
    return 0


def _handle_login(args: argparse.Namespace) -> int:
    registry_url = _resolve_registry_url(
        registry_url=args.registry_url,
        project_path=args.project_path,
    )
    password = args.password
    if password is None:
        password = getpass.getpass("Registry password: ")

    result = login_to_registry(
        base_url=registry_url,
        username=args.username,
        password=password,
        auth_file=args.auth_file,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "base_url": result.base_url,
                    "session": result.session,
                    "auth_file": str(result.auth_file),
                },
                indent=2,
            )
        )
        return 0

    print(f"Signed in to {result.base_url}")
    print(f"- role: {result.session.get('role', 'unknown')}")
    print(f"- token stored at: {result.auth_file}")
    return 0


def _handle_publish(args: argparse.Namespace) -> int:
    registry_url = _resolve_registry_url(
        registry_url=args.registry_url,
        project_path=args.path,
    )
    result = publish_project(
        args.path,
        base_url=registry_url,
        auth_file=args.auth_file,
        token=args.token,
        allow_incomplete=args.allow_incomplete,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    status = "accepted" if result.accepted else "not accepted"
    print(f"Publish {status} by {result.base_url}")
    print(f"- tool: {result.tool_name}")
    print(f"- status code: {result.status_code}")
    print(f"- listing status: {result.listing_status}")
    print(f"- listing: {result.listing_url}")
    print(f"- next step url: {result.next_url}")
    if result.review_url is not None:
        print("- moderation: listing is waiting for review")
    print(f"- preflight: {result.preflight.get('summary', 'no summary returned')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the publisher CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    handler = args.handler
    return handler(args)


__all__ = [
    "build_parser",
    "init_project",
    "main",
]
