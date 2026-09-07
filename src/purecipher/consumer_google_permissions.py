"""Explicit Google product permission modes and per-tool OAuth checks."""

from typing import Any

GMAIL_READONLY = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_COMPOSE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
GMAIL_MODIFY = "https://www.googleapis.com/auth/gmail.modify"
GMAIL_LABELS = "https://www.googleapis.com/auth/gmail.labels"

GMAIL_OAUTH_MODES = [
    {
        "id": "read_only",
        "label": "Read only",
        "description": "Read messages, threads, labels, drafts, attachments and history. No changes or sending.",
        "scopes": [GMAIL_READONLY],
    },
    {
        "id": "draft_and_send",
        "label": "Read, draft and send",
        "description": "Read your mailbox, create and manage drafts, and send messages. Sending requires a selected, approved tool.",
        "scopes": [GMAIL_READONLY, GMAIL_COMPOSE],
    },
    {
        "id": "manage_mail",
        "label": "Manage mail",
        "description": "Read, draft and send messages; manage labels and move mail to or from trash. Permanent message deletion is not provided.",
        "scopes": [GMAIL_MODIFY],
    },
]
GMAIL_READ_TOOLS = frozenset(
    {
        "gmail_profile",
        "gmail_list_messages",
        "gmail_get_message",
        "gmail_get_attachment",
        "gmail_list_threads",
        "gmail_get_thread",
        "gmail_list_labels",
        "gmail_get_label",
        "gmail_list_drafts",
        "gmail_get_draft",
        "gmail_list_history",
    }
)
GMAIL_COMPOSE_TOOLS = frozenset(
    {
        "gmail_create_draft",
        "gmail_update_draft",
        "gmail_delete_draft",
        "gmail_send_draft",
        "gmail_send_message",
        "gmail_reply_message",
    }
)
GMAIL_MANAGE_TOOLS = frozenset(
    {
        "gmail_create_label",
        "gmail_update_label",
        "gmail_delete_label",
        "gmail_modify_message_labels",
        "gmail_trash_message",
        "gmail_untrash_message",
        "gmail_modify_thread_labels",
        "gmail_trash_thread",
        "gmail_untrash_thread",
    }
)


def gmail_access_mode(values: dict[str, Any]) -> str:
    mode = values.get("access_mode") or "read_only"
    if not isinstance(mode, str) or mode not in {
        item["id"] for item in GMAIL_OAUTH_MODES
    }:
        raise ValueError("Choose a supported Gmail access mode")
    return mode


def required_scopes(product: str, values: dict[str, Any]) -> set[str]:
    if product in GOOGLE_OAUTH_MODES:
        mode = google_access_mode(product, values)
        return set(
            next(
                item["scopes"]
                for item in GOOGLE_OAUTH_MODES[product]
                if item["id"] == mode
            )
        )
    from purecipher.product_schemas import PRODUCT_SCHEMAS

    return set(PRODUCT_SCHEMAS[product]["scopes"])


def validate_tool_scope(grant: dict[str, Any], tool_name: str) -> None:
    """Require both the user's selected mode and a provider-granted scope."""
    mode = gmail_access_mode({"access_mode": grant.get("access_mode")})
    scopes = grant.get("scope", "")
    granted = set(scopes.split()) if isinstance(scopes, str) else set()
    if tool_name in GMAIL_READ_TOOLS:
        alternatives = {GMAIL_READONLY, GMAIL_MODIFY}
    elif tool_name in GMAIL_COMPOSE_TOOLS:
        if mode == "read_only":
            raise ValueError(
                "This Gmail tool requires a draft-and-send or manage-mail connection"
            )
        alternatives = {GMAIL_COMPOSE, GMAIL_MODIFY}
        if tool_name in {"gmail_send_message", "gmail_reply_message"}:
            alternatives.add(GMAIL_SEND)
    elif tool_name in GMAIL_MANAGE_TOOLS:
        if mode != "manage_mail":
            raise ValueError("This Gmail tool requires a manage-mail connection")
        alternatives = {GMAIL_MODIFY}
        if tool_name in {
            "gmail_create_label",
            "gmail_update_label",
            "gmail_delete_label",
        }:
            alternatives.add(GMAIL_LABELS)
    else:
        raise ValueError("Unknown Gmail tool permission")
    if not granted.intersection(alternatives):
        raise ValueError(
            "Google has not granted permission for this Gmail tool; reconnect your account"
        )


# The default scopes deliberately retain the grants used by older connections.
_SCOPE = "https://www.googleapis.com/auth/"
DOCS_READONLY, DOCS_WRITE = _SCOPE + "documents.readonly", _SCOPE + "documents"
TASKS_READONLY, TASKS_WRITE = _SCOPE + "tasks.readonly", _SCOPE + "tasks"
CALENDAR_READONLY = _SCOPE + "calendar.readonly"
CALENDAR_EVENTS, CALENDAR_WRITE = _SCOPE + "calendar.events", _SCOPE + "calendar"
DRIVE_METADATA = _SCOPE + "drive.metadata.readonly"
DRIVE_READONLY, DRIVE_WRITE = _SCOPE + "drive.readonly", _SCOPE + "drive"


def _mode(mode_id, label, description, *scopes):
    return {
        "id": mode_id,
        "label": label,
        "description": description,
        "scopes": list(scopes),
    }


GOOGLE_OAUTH_MODES = {
    "google-gmail": GMAIL_OAUTH_MODES,
    "google-docs": [
        _mode(
            "read_only",
            "Read only",
            "Read documents without making changes.",
            DOCS_READONLY,
        ),
        _mode(
            "edit_documents",
            "Create and edit documents",
            "Create documents and edit text with revision checks. Only approved tools can run.",
            DOCS_WRITE,
        ),
    ],
    "google-tasks": [
        _mode(
            "read_only",
            "Read only",
            "Read task lists and tasks without changing them.",
            TASKS_READONLY,
        ),
        _mode(
            "manage_tasks",
            "Manage tasks and lists",
            "Create, edit, complete, move and delete tasks and task lists.",
            TASKS_WRITE,
        ),
    ],
    "google-calendar": [
        _mode(
            "read_only",
            "Read only",
            "Read calendars, events and availability without changes or invitations.",
            CALENDAR_READONLY,
        ),
        _mode(
            "manage_events",
            "Manage events",
            "Read calendars and create, edit or delete events. Event tools explicitly choose attendee notifications.",
            CALENDAR_READONLY,
            CALENDAR_EVENTS,
        ),
        _mode(
            "manage_calendars",
            "Manage events and calendars",
            "Also create, edit and delete secondary calendars. Deleting a calendar removes its events.",
            CALENDAR_WRITE,
        ),
    ],
    "google-drive": [
        _mode(
            "read_only",
            "Metadata only",
            "Search and read file metadata. File contents are not accessible in this mode.",
            DRIVE_METADATA,
        ),
        _mode(
            "read_files",
            "Read file contents",
            "Read metadata, download files and export Google documents, without making changes.",
            DRIVE_READONLY,
        ),
        _mode(
            "manage_files",
            "Manage files",
            "Read, create, upload, move, copy, trash and delete accessible files. Sharing permissions are not exposed as tools.",
            DRIVE_WRITE,
        ),
    ],
}

GOOGLE_READ_TOOLS = {
    "google-docs": frozenset({"docs_get_document"}),
    "google-tasks": frozenset(
        {
            "tasks_list_tasklists",
            "tasks_list_tasks",
            "tasks_get_tasklist",
            "tasks_get_task",
        }
    ),
    "google-calendar": frozenset(
        {
            "calendar_list_calendars",
            "calendar_list_events",
            "calendar_get_calendar",
            "calendar_get_event",
            "calendar_list_event_instances",
            "calendar_free_busy",
        }
    ),
    "google-drive": frozenset(
        {
            "drive_search_files",
            "drive_get_file",
            "drive_list_folder_files",
            "drive_list_revisions",
        }
    ),
}
GOOGLE_WRITE_TOOLS = {
    "google-docs": frozenset(
        {
            "docs_create_document",
            "docs_insert_text",
            "docs_append_text",
            "docs_replace_text",
            "docs_delete_text",
            "docs_format_text",
        }
    ),
    "google-tasks": frozenset(
        {
            "tasks_create_tasklist",
            "tasks_update_tasklist",
            "tasks_delete_tasklist",
            "tasks_create_task",
            "tasks_update_task",
            "tasks_delete_task",
            "tasks_move_task",
            "tasks_clear_completed",
        }
    ),
    "google-calendar": frozenset(
        {
            "calendar_create_event",
            "calendar_update_event",
            "calendar_delete_event",
            "calendar_move_event",
        }
    ),
    "google-drive": frozenset(
        {
            "drive_create_file",
            "drive_create_folder",
            "drive_update_file_content",
            "drive_update_file_metadata",
            "drive_move_file",
            "drive_copy_file",
            "drive_trash_file",
            "drive_restore_file",
            "drive_delete_file",
        }
    ),
}
DRIVE_CONTENT_TOOLS = frozenset({"drive_download_file", "drive_export_file"})
CALENDAR_ADMIN_TOOLS = frozenset(
    {"calendar_create_calendar", "calendar_update_calendar", "calendar_delete_calendar"}
)


def google_access_mode(product: str, values: dict[str, Any]) -> str:
    if product == "google-gmail":
        return gmail_access_mode(values)
    mode = values.get("access_mode") or "read_only"
    if not isinstance(mode, str) or mode not in {
        entry["id"] for entry in GOOGLE_OAUTH_MODES[product]
    }:
        raise ValueError("Choose a supported Google product access mode")
    return mode


# Preserve the original Gmail-only validator's public behavior.
_validate_gmail_tool_scope = validate_tool_scope


def validate_google_tool_scope(
    product: str, grant: dict[str, Any], tool_name: str
) -> None:
    if product == "google-gmail":
        _validate_gmail_tool_scope(grant, tool_name)
        return
    mode = google_access_mode(product, {"access_mode": grant.get("access_mode")})
    scope_value = grant.get("scope", "")
    granted = set(scope_value.split()) if isinstance(scope_value, str) else set()
    if tool_name in GOOGLE_READ_TOOLS.get(product, ()):
        alternatives = {
            "google-docs": {DOCS_READONLY, DOCS_WRITE},
            "google-tasks": {TASKS_READONLY, TASKS_WRITE},
            "google-calendar": {CALENDAR_READONLY, CALENDAR_WRITE},
            "google-drive": {DRIVE_METADATA, DRIVE_READONLY, DRIVE_WRITE},
        }[product]
    elif product == "google-drive" and tool_name in DRIVE_CONTENT_TOOLS:
        if mode not in {"read_files", "manage_files"}:
            raise ValueError(
                "This Drive tool requires read-files or manage-files access"
            )
        alternatives = {DRIVE_READONLY, DRIVE_WRITE}
    elif product == "google-calendar" and tool_name in CALENDAR_ADMIN_TOOLS:
        if mode != "manage_calendars":
            raise ValueError("This Calendar tool requires manage-calendars access")
        alternatives = {CALENDAR_WRITE}
    elif tool_name in GOOGLE_WRITE_TOOLS.get(product, ()):
        allowed_modes, alternatives = {
            "google-docs": ({"edit_documents"}, {DOCS_WRITE}),
            "google-tasks": ({"manage_tasks"}, {TASKS_WRITE}),
            "google-calendar": (
                {"manage_events", "manage_calendars"},
                {CALENDAR_EVENTS, CALENDAR_WRITE},
            ),
            "google-drive": ({"manage_files"}, {DRIVE_WRITE}),
        }[product]
        if mode not in allowed_modes:
            raise ValueError(
                "This Google tool requires a connection mode that permits changes"
            )
    else:
        raise ValueError("Unknown Google product tool permission")
    if not granted.intersection(alternatives):
        raise ValueError(
            "Google has not granted permission for this tool; reconnect your account"
        )
