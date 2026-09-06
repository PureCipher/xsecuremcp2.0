"""PureCipher GitHub: explicitly selected repositories, read-only tools."""

import os

from .common import ANNOTATIONS, page_size, read_json, resource_id, secured
from .oauth import from_environment

TOOLS = {"github_list_issues", "github_list_pull_requests", "github_get_issue"}


def create_server(auth, repositories: set[str]):
    if not repositories:
        raise ValueError("Explicit repository allowlist is required")
    allowed = {r.lower() for r in repositories}
    server = secured("github", auth, TOOLS)

    def repo_path(owner, repo):
        if f"{owner}/{repo}".lower() not in allowed:
            raise ValueError("Repository is not allowed")
        return f"repos/{resource_id(owner)}/{resource_id(repo)}/"

    @server.tool(annotations=ANNOTATIONS)
    async def github_list_issues(
        owner: str, repo: str, page: int = 1, per_page: int = 20
    ) -> dict:
        """List issues (including pull requests) in an allowed repository."""
        if page < 1:
            raise ValueError("Page must be positive")
        return await read_json(
            "https://api.github.com/",
            repo_path(owner, repo) + "issues",
            {"state": "all", "page": page, "per_page": page_size(per_page)},
        )

    @server.tool(annotations=ANNOTATIONS)
    async def github_list_pull_requests(
        owner: str, repo: str, page: int = 1, per_page: int = 20
    ) -> dict:
        """List pull requests in an allowed repository."""
        if page < 1:
            raise ValueError("Page must be positive")
        return await read_json(
            "https://api.github.com/",
            repo_path(owner, repo) + "pulls",
            {"state": "all", "page": page, "per_page": page_size(per_page)},
        )

    @server.tool(annotations=ANNOTATIONS)
    async def github_get_issue(owner: str, repo: str, issue_number: int) -> dict:
        """Read an issue's details in an allowed repository."""
        if issue_number < 1:
            raise ValueError("Issue number must be positive")
        return await read_json(
            "https://api.github.com/", repo_path(owner, repo) + f"issues/{issue_number}"
        )

    return server


if __name__ == "__main__":
    create_server(
        from_environment("github", 9111),
        {
            r.strip()
            for r in os.environ.get("PURECIPHER_GITHUB_REPOSITORIES", "").split(",")
            if r.strip()
        },
    ).run(transport="http", host="127.0.0.1", port=9111)
