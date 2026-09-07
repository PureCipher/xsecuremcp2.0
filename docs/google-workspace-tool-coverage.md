# Google Workspace tool coverage

Implementation: Google Workspace consumer adapters, reviewed 2026-09-07 against the official REST references below. This is common product operation coverage, **not the complete Google API surface**. Gmail's 26 operations are documented separately in `gmail-tool-coverage.md`.

| Product | Registered tools | Read operations | Change operations |
| --- | ---: | --- | --- |
| Google Docs (API v1) | 7 | Read documents, optionally including tabs | Create documents; insert, append, replace, delete and format text |
| Google Tasks (API v1) | 12 | List/read task lists and tasks | Create, rename and delete lists; create, edit, complete/reopen, delete and move tasks; clear completed tasks |
| Google Calendar (API v3) | 13 | List/read calendars and events, expand recurring instances, query availability | Create, edit, delete and move events; create, edit and delete secondary calendars |
| Google Drive (API v3) | 15 | Search/read metadata, folder contents and revisions; download binary files and export Workspace documents | Upload/create files and folders; replace content, edit metadata, move, copy, trash, restore and permanently delete files |
| **Total (excluding Gmail)** | **47** | **17** | **30** |

Seven pre-existing tool names and their original positional parameters remain supported: `docs_get_document`, `tasks_list_tasklists`, `tasks_list_tasks`, `calendar_list_calendars`, `calendar_list_events`, `drive_search_files`, and `drive_get_file`. New optional arguments extend existing reads. Drive's existing metadata tools still do not return file contents. File search and folder listing include accessible shared-drive items and preserve Google's `incompleteSearch` flag so partial discovery is visible; this does not change account permissions.

## Permissions and persistence

The user's saved `access_mode` belongs to their private, encrypted product connection. Older connections without this field continue in `read_only`. New modes do not silently widen old OAuth grants. The selected mode determines requested OAuth scopes; both the selected mode and the granted scopes must permit each selected tool.

| Product | Default mode and scope suffix | Additional modes and scope suffixes |
| --- | --- | --- |
| Docs | `read_only`: `documents.readonly` | `edit_documents`: `documents` |
| Tasks | `read_only`: `tasks.readonly` | `manage_tasks`: `tasks` |
| Calendar | `read_only`: `calendar.readonly` | `manage_events`: `calendar.readonly` + `calendar.events`; `manage_calendars`: `calendar` |
| Drive | `read_only` (Metadata only): `drive.metadata.readonly` | `read_files`: `drive.readonly`; `manage_files`: `drive` |

All scope suffixes have prefix `https://www.googleapis.com/auth/`. Drive metadata-only mode cannot download or export file content. Calendar event-management mode cannot create, change or delete calendars. Provider-granted broader scopes cannot bypass these local mode boundaries.

Mode changes discard the previous encrypted OAuth grant and require authorization again. Name-only changes keep a valid grant. OAuth state binds the owner, connection revision, requested scopes and mode; callback and refresh validate that binding. Connection views expose only mode and scope information, never tokens. Refresh of a legacy read-only grant continues to work when Google omits unchanged scopes in its refresh response.

Tools are available only through the existing authenticated SecureMCP profile path. Exact tool selection, connection ownership, profile activity, client assignment, applicable consent/approval, contracts and policies remain in force. Adding new tools does not select or approve them for an existing profile. Read-only policy packs continue to block changes; tool annotations do not substitute for policy enforcement.

## Provider behavior and boundaries

- Docs text edits require the current `revisionId` from `docs_get_document`, and submit `writeControl.requiredRevisionId`. This prevents applying stale offsets after another writer edits the document. Positions are UTF-16 indices. New documents are created empty; a client reads the new revision before inserting content.
- Calendar update/delete tools require an exact ETag and send `If-Match`. A stale ETag returns a conflict without a retry. Event creation, updates, deletion and moves require an explicit `send_updates` choice. Attendees are explicit email addresses and replacing that field replaces the full list. Google may send some emails even with `none`; that option may impair synchronization to external calendars. Event deletion with a recurring series ID deletes the series.
- Tasks due dates represent dates, not reminder times. Empty/unspecified edit fields are left unchanged; `clear_due_date` explicitly clears a due date. Clearing completed tasks hides them from the usual list; they remain retrievable with `show_hidden`. Deleting an assigned task can also delete its source task in Docs or Chat. Delete tools require an explicit confirmation argument.
- Drive content upload/download/export is limited to **5 MiB** per call. Uploads accept standard base64, never caller-supplied URLs or local paths. Downloads stream from fixed Google origins and stop at the limit; redirects are not followed. Binary file downloads and Workspace-format exports use their distinct API methods. Metadata listing uses bounded pages (at most 100 records). Moving files changes parent folders and can change inherited access. Permanent deletion bypasses trash and requires an explicit confirmation argument.
- Drive content replacement, Tasks mutations and Calendar moves do not claim optimistic concurrency protection. Their tool descriptions disclose relevant last-write behavior. No automatic retries occur. Network failures and provider 5xx errors for changes report an unknown outcome and instruct the client to inspect the resource before retrying.
- All outbound calls use fixed Google API origins, an owner-bound OAuth token and bounded timeouts. Provider error bodies are withheld from MCP responses. JSON response size is capped at 10 MiB. Profile/connection revision and tool authorization are rechecked before each provider call.

## Deliberate exclusions

Docs does not expose arbitrary batch requests, document deletion, tables/images, comments, named ranges, suggestion approval, or document sharing. Deleting a document uses Drive and requires that separate connection and selected tool.

Tasks does not expose assignment creation, recurring reminders, bulk arbitrary edits, or cross-list task migration.

Calendar does not expose ACL changes, calendar sharing/subscription management, arbitrary recurrence creation, attachment uploads, conferencing creation, calendars.clear, bulk import, or push notification channels. Existing recurring events and individual instances can be read; explicit IDs determine what is changed.

Drive does not expose permission/sharing changes, external URL fetches, resumable/large uploads, revision deletion, shared-drive administration, labels, arbitrary search-field expansion, or native Docs/Sheets/Slides content edits. Google Drive API capabilities, upstream account permissions and organizational restrictions still apply.

These tools have been exercised through local MCP and mocked Google HTTP, including every registered method/path, payload models, field bounds, explicit notifications, ETags/revisions, upload encoding, download caps, redacted failures, no retries, and missing authorization denials. OAuth tests cover all modes, legacy refresh, changed permissions and inadequate grants. **No real user's Google account was authorized and no live Google business operation was executed during this implementation.** Provider OAuth application configuration and user authorization remain prerequisites for live acceptance testing.

## Official sources

- [Google Docs batchUpdate and revision controls](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate)
- [Google Docs request models and tab locations](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request)
- [Google Tasks resource fields, due-date and assigned-task behavior](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks)
- [Google Tasks insertion and scope](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/insert)
- [Google Tasks move](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/move)
- [Calendar event creation and attendee notification behavior](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert)
- [Calendar conditional modification with ETags](https://developers.google.com/workspace/calendar/api/guides/version-resources)
- [Calendar metadata patch and scope](https://developers.google.com/workspace/calendar/api/v3/reference/calendars/patch)
- [Drive downloads and exports](https://developers.google.com/workspace/drive/api/guides/manage-downloads)
- [Drive multipart upload](https://developers.google.com/workspace/drive/api/guides/manage-uploads)
- [Drive file update, upload and parent changes](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/update)
- [Drive revision metadata listing and scopes](https://developers.google.com/workspace/drive/api/reference/rest/v3/revisions/list)
- [Drive listing, shared-drive flags and incomplete search results](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list)
