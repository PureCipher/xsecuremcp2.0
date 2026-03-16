"""SecureMCP CLI facade."""

from __future__ import annotations

import importlib.metadata
import inspect
import platform
from collections.abc import Awaitable, Callable
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from functools import update_wrapper
from pathlib import Path
from typing import Annotated, Any, ParamSpec, TypeVar, cast
from unittest.mock import patch

import cyclopts
import mcp.types
import pyperclip
from cyclopts import Parameter
from rich.console import Console
from rich.table import Table

import securemcp
from fastmcp.cli import cli as fastmcp_cli_module
from fastmcp.cli import client as fastmcp_client_module
from fastmcp.cli import generate as fastmcp_generate_module
from fastmcp.cli.auth import auth_app as fastmcp_auth_app
from fastmcp.cli.cli import apps as fastmcp_apps_command
from fastmcp.cli.cli import inspect as inspect_command
from fastmcp.cli.cli import inspector as fastmcp_inspector_command
from fastmcp.cli.cli import project_app as fastmcp_project_app
from fastmcp.cli.cli import run as run_command
from fastmcp.cli.client import _build_stdio_from_command
from fastmcp.cli.client import call_command as fastmcp_call_command
from fastmcp.cli.client import discover_command as fastmcp_discover_command
from fastmcp.cli.client import list_command as fastmcp_list_command
from fastmcp.cli.discovery import resolve_name
from fastmcp.cli.generate import generate_cli_command as fastmcp_generate_cli_command
from fastmcp.cli.install import claude_code as fastmcp_claude_code_install
from fastmcp.cli.install import claude_desktop as fastmcp_claude_desktop_install
from fastmcp.cli.install import cursor as fastmcp_cursor_install
from fastmcp.cli.install import gemini_cli as fastmcp_gemini_install
from fastmcp.cli.install import goose as fastmcp_goose_install
from fastmcp.cli.install import mcp_json as fastmcp_mcp_json_install
from fastmcp.cli.install import stdio as fastmcp_stdio_install
from fastmcp.cli.install.claude_code import (
    claude_code_command as fastmcp_claude_code_command,
)
from fastmcp.cli.install.claude_desktop import (
    claude_desktop_command as fastmcp_claude_desktop_command,
)
from fastmcp.cli.install.cursor import cursor_command as fastmcp_cursor_command
from fastmcp.cli.install.gemini_cli import (
    gemini_cli_command as fastmcp_gemini_cli_command,
)
from fastmcp.cli.install.goose import goose_command as fastmcp_goose_command
from fastmcp.cli.install.mcp_json import mcp_json_command as fastmcp_mcp_json_command
from fastmcp.cli.install.stdio import stdio_command as fastmcp_stdio_command
from fastmcp.cli.tasks import tasks_app as fastmcp_tasks_app
from fastmcp.client.transports.base import ClientTransport
from fastmcp.client.transports.stdio import StdioTransport
from fastmcp.utilities.mcp_server_config.v1.environments.uv import UVEnvironment

console = Console()
SECURE_CLI_NAME = "securemcp"
_SECURE_TOP_LEVEL_COMMANDS = {
    "auth",
    "call",
    "dev",
    "discover",
    "generate-cli",
    "inspect",
    "install",
    "list",
    "project",
    "run",
    "tasks",
    "version",
}
_ORIGINAL_GENERATE_CLI_SCRIPT = fastmcp_generate_module.generate_cli_script
_ORIGINAL_GENERATE_SKILL_CONTENT = fastmcp_generate_module.generate_skill_content
_ORIGINAL_CLI_SUBPROCESS_RUN = fastmcp_cli_module.subprocess.run
_ORIGINAL_RUN_WITH_RELOAD = fastmcp_cli_module.run_module.run_with_reload
P = ParamSpec("P")
R = TypeVar("R")


def _clone_subapp(subapp: cyclopts.App) -> cyclopts.App:
    """Create a SecureMCP-local copy of a FastMCP sub-app."""
    return deepcopy(subapp)


def _wrap_command_examples(text: str | None) -> str | None:
    """Adjust SecureMCP-facing docstrings/examples while keeping FastMCP intact."""
    if text is None:
        return None
    return (
        text.replace("fastmcp generate-cli", "securemcp generate-cli")
        .replace("fastmcp install", "securemcp install")
        .replace("fastmcp inspect", "securemcp inspect")
        .replace("fastmcp list", "securemcp list")
        .replace("fastmcp call", "securemcp call")
        .replace("fastmcp discover", "securemcp discover")
        .replace("fastmcp run", "securemcp run")
        .replace("fastmcp dev", "securemcp dev")
    )


def _rewrite_secure_cli_tokens(command: list[str]) -> list[str]:
    """Rewrite spawned CLI invocations from FastMCP to SecureMCP.

    This intentionally leaves package/dependency references like
    ``--with fastmcp`` unchanged, and only rewrites executable entrypoints.
    """
    rewritten = list(command)
    for index, token in enumerate(rewritten):
        if (
            token == "fastmcp"
            and index + 1 < len(rewritten)
            and rewritten[index + 1] in _SECURE_TOP_LEVEL_COMMANDS
        ) or (token == "fastmcp.cli" and index > 0 and rewritten[index - 1] == "-m"):
            rewritten[index] = SECURE_CLI_NAME
    return rewritten


class SecureCLIUVEnvironment(UVEnvironment):
    """UV environment wrapper that preserves FastMCP deps but runs SecureMCP."""

    def build_command(self, command: list[str]) -> list[str]:
        secure_command = command
        if command and command[0] == "fastmcp":
            secure_command = [SECURE_CLI_NAME, *command[1:]]
        return super().build_command(secure_command)


def _secure_resolve_json_spec(path: Path) -> str | dict[str, object]:
    """SecureMCP variant of FastMCP's JSON spec resolution."""
    if not path.exists():
        fastmcp_client_module.console.print(
            f"[bold red]Error:[/bold red] File not found: [cyan]{path}[/cyan]"
        )
        raise SystemExit(1)

    try:
        data = fastmcp_client_module.json.loads(path.read_text())
    except fastmcp_client_module.json.JSONDecodeError as exc:
        fastmcp_client_module.console.print(
            f"[bold red]Error:[/bold red] Invalid JSON in {path}: {exc}"
        )
        raise SystemExit(1) from exc

    if isinstance(data, dict) and "mcpServers" in data:
        return data

    fastmcp_client_module.console.print(
        f"[bold red]Error:[/bold red] [cyan]{path}[/cyan] is a FastMCP server config, not an MCPConfig.\n"
        f"Start the server first, then query it:\n\n"
        f"  securemcp run {path}\n"
        f"  securemcp list http://localhost:8000/mcp\n"
    )
    raise SystemExit(1)


def _secure_resolve_server_spec(
    server_spec: str | None,
    *,
    command: str | None = None,
    transport: str | None = None,
) -> str | dict[str, object] | ClientTransport:
    """SecureMCP variant of FastMCP's server-spec resolution."""
    if command is not None and server_spec is not None:
        fastmcp_client_module.console.print(
            "[bold red]Error:[/bold red] Cannot use both a server spec and --command"
        )
        raise SystemExit(1)

    if command is not None:
        return _build_stdio_from_command(command)

    if server_spec is None:
        fastmcp_client_module.console.print(
            "[bold red]Error:[/bold red] Provide a server spec or use --command"
        )
        raise SystemExit(1)

    spec = server_spec

    if spec.startswith(("http://", "https://")):
        if transport == "sse" and not spec.rstrip("/").endswith("/sse"):
            spec = spec.rstrip("/") + "/sse"
        return spec

    path = Path(spec)
    is_file = path.is_file() or (
        not path.is_dir() and spec.endswith((".py", ".js", ".json"))
    )

    if is_file:
        if spec.endswith(".json"):
            return _secure_resolve_json_spec(path)
        if spec.endswith(".py"):
            return StdioTransport(
                command=SECURE_CLI_NAME,
                args=["run", str(path.resolve()), "--no-banner"],
            )
        return spec

    try:
        return resolve_name(spec)
    except ValueError as exc:
        fastmcp_client_module.console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1) from exc


def _secure_generate_cli_script(
    server_name: str,
    server_spec: str,
    transport_code: str,
    extra_imports: set[str],
    tools: list[mcp.types.Tool],
) -> str:
    script = _ORIGINAL_GENERATE_CLI_SCRIPT(
        server_name,
        server_spec,
        transport_code,
        extra_imports,
        tools,
    )
    return script.replace(
        "Generated by: fastmcp generate-cli",
        "Generated by: securemcp generate-cli",
    )


def _secure_generate_skill_content(
    server_name: str,
    cli_filename: str,
    tools: list[mcp.types.Tool],
) -> str:
    return _ORIGINAL_GENERATE_SKILL_CONTENT(server_name, cli_filename, tools)


def _secure_build_uvx_command(
    server_spec: str,
    *,
    python_version: str | None = None,
    with_packages: list[str] | None = None,
) -> list[str]:
    """SecureMCP-specific Goose command builder."""
    args: list[str] = ["uvx"]

    if python_version:
        args.extend(["--python", python_version])

    for pkg in sorted(set(with_packages or [])):
        if pkg != "fastmcp":
            args.extend(["--with", pkg])

    args.extend(["--from", "fastmcp", SECURE_CLI_NAME, "run", server_spec])
    return args


def _secure_subprocess_run(*args: Any, **kwargs: Any) -> Any:
    """Proxy subprocess.run while rewriting spawned CLI entrypoints."""
    if (
        args
        and isinstance(args[0], list)
        and all(isinstance(token, str) for token in args[0])
    ):
        rewritten = _rewrite_secure_cli_tokens(cast(list[str], args[0]))
        args = (rewritten, *args[1:])
    return _ORIGINAL_CLI_SUBPROCESS_RUN(*args, **kwargs)


async def _secure_run_with_reload(
    command: list[str],
    reload_dirs: list[Path] | None = None,
    is_stdio: bool = False,
) -> None:
    """Proxy FastMCP's reload runner while rewriting the command it restarts."""
    rewritten = _rewrite_secure_cli_tokens(command)
    await _ORIGINAL_RUN_WITH_RELOAD(
        rewritten,
        reload_dirs=reload_dirs,
        is_stdio=is_stdio,
    )


async def _secure_start_user_server(
    server_spec: str,
    mcp_port: int,
    *,
    reload: bool = True,
):
    """SecureMCP variant of FastMCP's app-preview server launcher."""
    import asyncio
    import os
    import sys

    cmd = [
        sys.executable,
        "-m",
        SECURE_CLI_NAME,
        "run",
        server_spec,
        "--transport",
        "http",
        "--port",
        str(mcp_port),
        "--no-banner",
    ]
    if reload:
        cmd.append("--reload")
    else:
        cmd.append("--no-reload")

    env = {**os.environ, "FASTMCP_LOG_LEVEL": "WARNING"}
    return await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        start_new_session=sys.platform != "win32",
    )


@contextmanager
def _secure_cli_patches(
    *,
    patch_client: bool = False,
    patch_generate: bool = False,
    patch_install: bool = False,
    patch_runtime: bool = False,
    patch_dev_apps: bool = False,
):
    """Apply SecureMCP-only runtime patches around reused FastMCP commands."""
    with ExitStack() as stack:
        if patch_client or patch_generate:
            stack.enter_context(
                patch.object(
                    fastmcp_client_module,
                    "resolve_server_spec",
                    _secure_resolve_server_spec,
                )
            )
        if patch_generate:
            stack.enter_context(
                patch.object(
                    fastmcp_generate_module,
                    "resolve_server_spec",
                    _secure_resolve_server_spec,
                )
            )
            stack.enter_context(
                patch.object(
                    fastmcp_generate_module,
                    "generate_cli_script",
                    _secure_generate_cli_script,
                )
            )
            stack.enter_context(
                patch.object(
                    fastmcp_generate_module,
                    "generate_skill_content",
                    _secure_generate_skill_content,
                )
            )
        if patch_install:
            install_modules = [
                fastmcp_stdio_install,
                fastmcp_mcp_json_install,
                fastmcp_claude_code_install,
                fastmcp_claude_desktop_install,
                fastmcp_cursor_install,
                fastmcp_gemini_install,
            ]
            for module in install_modules:
                stack.enter_context(
                    patch.object(module, "UVEnvironment", SecureCLIUVEnvironment)
                )
            stack.enter_context(
                patch.object(
                    fastmcp_goose_install,
                    "_build_uvx_command",
                    _secure_build_uvx_command,
                )
            )
        if patch_runtime:
            stack.enter_context(
                patch.object(
                    fastmcp_cli_module.subprocess,
                    "run",
                    _secure_subprocess_run,
                )
            )
            stack.enter_context(
                patch.object(
                    fastmcp_cli_module.run_module,
                    "run_with_reload",
                    _secure_run_with_reload,
                )
            )
        if patch_dev_apps:
            from fastmcp.cli import apps_dev as fastmcp_apps_dev_module

            stack.enter_context(
                patch.object(
                    fastmcp_apps_dev_module,
                    "_start_user_server",
                    _secure_start_user_server,
                )
            )
        yield


def _wrap_async_command(
    func: Callable[P, Awaitable[R]],
    *,
    patch_client: bool = False,
    patch_generate: bool = False,
    patch_install: bool = False,
    patch_runtime: bool = False,
    patch_dev_apps: bool = False,
) -> Callable[P, Awaitable[R]]:
    """Wrap a FastMCP async command for SecureMCP without changing its signature."""

    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        with _secure_cli_patches(
            patch_client=patch_client,
            patch_generate=patch_generate,
            patch_install=patch_install,
            patch_runtime=patch_runtime,
            patch_dev_apps=patch_dev_apps,
        ):
            return await func(*args, **kwargs)

    update_wrapper(cast(Callable[..., Any], wrapper), func)
    wrapper_any = cast(Any, wrapper)
    wrapper_any.__signature__ = inspect.signature(func)
    wrapper_any.__doc__ = _wrap_command_examples(getattr(func, "__doc__", None))
    return wrapper


app = cyclopts.App(
    name="securemcp",
    help="SecureMCP - Secure MCP servers built on FastMCP.",
    version=securemcp.__version__,
    default_parameter=Parameter(negative=()),
)

# Reuse the existing command implementations, but keep FastMCP's sub-apps
# untouched so `fastmcp` retains upstream behavior and branding.
dev_app = cyclopts.App(
    name="dev",
    help="Development tools for SecureMCP servers",
)
project_app = _clone_subapp(fastmcp_project_app)
tasks_app = _clone_subapp(fastmcp_tasks_app)
auth_app = _clone_subapp(fastmcp_auth_app)
install_app = cyclopts.App(
    name="install",
    help="Install SecureMCP servers in various clients and formats.",
)

project_app.help = "Manage SecureMCP projects"
tasks_app.help = "Manage SecureMCP background tasks using Docket"

dev_app.command(
    _wrap_async_command(fastmcp_inspector_command, patch_runtime=True),
    name="inspector",
)
dev_app.command(
    _wrap_async_command(
        fastmcp_apps_command,
        patch_dev_apps=True,
    ),
    name="apps",
)

install_app.command(
    _wrap_async_command(fastmcp_claude_code_command, patch_install=True),
    name="claude-code",
)
install_app.command(
    _wrap_async_command(fastmcp_claude_desktop_command, patch_install=True),
    name="claude-desktop",
)
install_app.command(
    _wrap_async_command(fastmcp_cursor_command, patch_install=True),
    name="cursor",
)
install_app.command(
    _wrap_async_command(fastmcp_gemini_cli_command, patch_install=True),
    name="gemini-cli",
)
install_app.command(
    _wrap_async_command(fastmcp_goose_command, patch_install=True),
    name="goose",
)
install_app.command(
    _wrap_async_command(fastmcp_mcp_json_command, patch_install=True),
    name="mcp-json",
)
install_app.command(
    _wrap_async_command(fastmcp_stdio_command, patch_install=True),
    name="stdio",
)


@app.command
def version(
    *,
    copy: Annotated[
        bool,
        cyclopts.Parameter("--copy", help="Copy version information to clipboard"),
    ] = False,
) -> None:
    """Display version information and platform details."""
    info = {
        "SecureMCP version": securemcp.__version__,
        "Install distribution": "fastmcp",
        "MCP version": importlib.metadata.version("mcp"),
        "Python version": platform.python_version(),
        "Platform": platform.platform(),
        "SecureMCP root path": Path(securemcp.__file__ or ".").resolve().parents[1],
    }

    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold", justify="left")
    grid.add_column(style="cyan", justify="right")
    for key, value in info.items():
        grid.add_row(key + ":", str(value).replace("\n", " "))

    if copy:
        plain_console = Console(file=None, force_terminal=False, legacy_windows=False)
        with plain_console.capture() as capture:
            plain_console.print(grid)
        pyperclip.copy(capture.get())
        console.print("[green]OK[/green] Version information copied to clipboard")
        return

    console.print(grid)


app.command(_wrap_async_command(run_command, patch_runtime=True), name="run")
app.command(_wrap_async_command(inspect_command), name="inspect")
app.command(dev_app)
app.command(project_app)
app.command(install_app)
app.command(tasks_app)
app.command(_wrap_async_command(fastmcp_list_command, patch_client=True), name="list")
app.command(_wrap_async_command(fastmcp_call_command, patch_client=True), name="call")
app.command(_wrap_async_command(fastmcp_discover_command), name="discover")
app.command(
    _wrap_async_command(
        fastmcp_generate_cli_command,
        patch_client=True,
        patch_generate=True,
    ),
    name="generate-cli",
)
app.command(auth_app)


if __name__ == "__main__":
    app()
