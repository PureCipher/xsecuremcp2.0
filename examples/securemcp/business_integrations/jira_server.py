"""PureCipher Jira: read-only issue search on a configured cloud site."""

import os

from .common import ANNOTATIONS, page_size, read_json, resource_id, secured
from .oauth import from_environment

TOOLS = {"jira_search_issues", "jira_get_issue"}


def create_server(auth, cloud_id: str):
    cloud = resource_id(cloud_id)
    base = f"https://api.atlassian.com/ex/jira/{cloud}/rest/api/3/"
    server = secured("jira", auth, TOOLS)

    @server.tool(annotations=ANNOTATIONS)
    async def jira_search_issues(
        jql: str, next_page_token: str = "", max_results: int = 20
    ) -> dict:
        """Search accessible issues using JQL on the configured Jira site."""
        if not jql.strip():
            raise ValueError("A JQL query is required")
        return await read_json(
            base,
            "search/jql",
            {
                "jql": jql,
                "nextPageToken": next_page_token,
                "maxResults": page_size(max_results),
                "fields": "summary,status,assignee,updated",
            },
        )

    @server.tool(annotations=ANNOTATIONS)
    async def jira_get_issue(issue_key: str) -> dict:
        """Read an accessible issue's summary, status and description."""
        return await read_json(
            base,
            "issue/" + resource_id(issue_key),
            {"fields": "summary,status,assignee,updated,description"},
        )

    return server


if __name__ == "__main__":
    create_server(
        from_environment("jira", 9113), os.environ.get("PURECIPHER_JIRA_CLOUD_ID", "")
    ).run(transport="http", host="127.0.0.1", port=9113)
