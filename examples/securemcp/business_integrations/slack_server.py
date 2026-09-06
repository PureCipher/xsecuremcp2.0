"""PureCipher Slack: user OAuth and explicit public-channel allowlist."""

import os

from .common import ANNOTATIONS, page_size, read_json, secured
from .oauth import from_environment

TOOLS = {"slack_channel_history"}


def create_server(auth, channels: set[str]):
    if not channels:
        raise ValueError("Explicit channel allowlist is required")
    server = secured("slack", auth, TOOLS)

    @server.tool(annotations=ANNOTATIONS)
    async def slack_channel_history(
        channel_id: str, cursor: str = "", limit: int = 15
    ) -> dict:
        """Read one page of history in an explicitly allowed public channel."""
        if channel_id not in channels:
            raise ValueError("Channel is not allowed")
        return await read_json(
            "https://slack.com/api/",
            "conversations.history",
            {"channel": channel_id, "cursor": cursor, "limit": page_size(limit)},
        )

    return server


if __name__ == "__main__":
    create_server(
        from_environment("slack", 9112),
        {
            c.strip()
            for c in os.environ.get("PURECIPHER_SLACK_CHANNELS", "").split(",")
            if c.strip()
        },
    ).run(transport="http", host="127.0.0.1", port=9112)
