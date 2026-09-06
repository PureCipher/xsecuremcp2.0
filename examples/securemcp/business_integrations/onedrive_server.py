"""PureCipher OneDrive: folder and file metadata, without download URLs."""

from .common import ANNOTATIONS, graph_page, page_size, read_json, resource_id, secured
from .oauth import from_environment

TOOLS = {"onedrive_list_files", "onedrive_get_file"}
BASE = "https://graph.microsoft.com/v1.0/"
FIELDS = "id,name,size,file,folder,webUrl,lastModifiedDateTime,parentReference"


def metadata_only(data: dict) -> dict:
    allowed = set(FIELDS.split(","))
    if "value" in data:
        return {
            **{k: data[k] for k in ("@odata.nextLink", "@odata.context") if k in data},
            "value": [
                {k: v for k, v in item.items() if k in allowed}
                for item in data["value"]
            ],
        }
    return {k: v for k, v in data.items() if k in allowed}


def create_server(auth):
    server = secured("onedrive", auth, TOOLS)

    @server.tool(annotations=ANNOTATIONS)
    async def onedrive_list_files(
        folder_id: str = "root", next_link: str = "", max_results: int = 20
    ) -> dict:
        """List one folder's files and metadata in the signed-in user's drive."""
        path = (
            "me/drive/root/children"
            if folder_id == "root"
            else "me/drive/items/" + resource_id(folder_id) + "/children"
        )
        path, _ = graph_page(next_link, path)
        params = (
            None if next_link else {"$top": page_size(max_results), "$select": FIELDS}
        )
        return metadata_only(await read_json(BASE, path, params))

    @server.tool(annotations=ANNOTATIONS)
    async def onedrive_get_file(file_id: str) -> dict:
        """Get metadata and browser link for an accessible file; no content download."""
        return metadata_only(
            await read_json(
                BASE, "me/drive/items/" + resource_id(file_id), {"$select": FIELDS}
            )
        )

    return server


if __name__ == "__main__":
    create_server(from_environment("onedrive", 9115)).run(
        transport="http", host="127.0.0.1", port=9115
    )
