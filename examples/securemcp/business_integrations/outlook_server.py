"""PureCipher Outlook: delegated reads of the signed-in user's mailbox/calendar."""

from .common import ANNOTATIONS, graph_page, page_size, read_json, resource_id, secured
from .oauth import from_environment

TOOLS = {"outlook_list_messages", "outlook_get_message", "outlook_list_events"}
BASE = "https://graph.microsoft.com/v1.0/"


def create_server(auth):
    server = secured("outlook", auth, TOOLS)

    @server.tool(annotations=ANNOTATIONS)
    async def outlook_list_messages(next_link: str = "", max_results: int = 20) -> dict:
        """Read a page of message summaries in the signed-in user's mailbox."""
        path, _ = graph_page(next_link, "me/messages")
        params = (
            None
            if next_link
            else {
                "$top": page_size(max_results),
                "$select": "id,subject,from,receivedDateTime,isRead",
            }
        )
        return await read_json(BASE, path, params)

    @server.tool(annotations=ANNOTATIONS)
    async def outlook_get_message(message_id: str) -> dict:
        """Read one message in the signed-in user's mailbox."""
        return await read_json(
            BASE,
            "me/messages/" + resource_id(message_id),
            {"$select": "id,subject,from,toRecipients,receivedDateTime,body"},
        )

    @server.tool(annotations=ANNOTATIONS)
    async def outlook_list_events(next_link: str = "", max_results: int = 20) -> dict:
        """Read a page of events in the signed-in user's default calendar."""
        path, _ = graph_page(next_link, "me/events")
        params = (
            None
            if next_link
            else {
                "$top": page_size(max_results),
                "$select": "id,subject,start,end,location",
            }
        )
        return await read_json(BASE, path, params)

    return server


if __name__ == "__main__":
    create_server(from_environment("outlook", 9114)).run(
        transport="http", host="127.0.0.1", port=9114
    )
