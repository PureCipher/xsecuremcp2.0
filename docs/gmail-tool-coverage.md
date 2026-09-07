# Gmail SecureMCP tool coverage — 0.4.0

The Gmail connector provides 26 named mailbox tools through the consumer's assigned SecureMCP profile. This expands the previous three-tool read-only surface. It covers reading, composing, sending, labels, trash/restoration, and mailbox history. It is **partial Gmail API coverage**, not an implementation of every Gmail endpoint.

The provider API is **Gmail API v1**. Official Google documentation was reviewed **2026-09-07**. The upstream API version and this connector's `0.4.0` version are separate. The implementation lives in `src/purecipher/consumer_gmail.py`; access-mode and scope checks live in `src/purecipher/consumer_google_permissions.py`. Descriptor registration remains part of `register_consumer_tools` in `src/purecipher/consumer_runtime.py`.

The source of truth for tool names, descriptions, input schemas, and annotations is the registered runtime. `examples/securemcp/consumer_runtime/generate.py` produces the submission artifact from that registration. This document describes the intended product boundary and the provider semantics; it is not a live account verification report.

## Choose access for your own account

The publisher owns the Google OAuth application. Each end user authorizes their own Google account and chooses a Gmail connection in their profile. They do not supply the publisher's OAuth client secret.

| Connection mode | Requested Gmail scopes | Tools permitted by the mode |
| --- | --- | --- |
| `read_only` — Read only | `https://www.googleapis.com/auth/gmail.readonly` | The 11 reading tools below |
| `draft_and_send` — Read, draft and send | `gmail.readonly` and `gmail.compose`, with the same scope URL prefix | Reading plus the 6 drafting/sending tools |
| `manage_mail` — Manage mail | `gmail.modify`, with the same scope URL prefix | All 26 tools, including label and trash operations |

Read only is the default, including existing connections without an explicit mode. Changing modes requires account authorization again. A tool call must satisfy both the connection's selected mode and the actual Google-granted scopes. Changing metadata alone does not grant OAuth permission. The application's selected profile tools and access approval remain additional restrictions; receiving a broad Google grant does not select or approve tools automatically.

Google's scope boundaries do not exactly match every product action. For example, `gmail.compose` allows draft management and sending, while `gmail.send` allows direct sending but is not sufficient for `drafts.send`. Applying labels to messages requires `gmail.modify`; `gmail.labels` covers label definitions. The connector's modes are deliberate product boundaries on top of Google's permissions. It does not request `https://mail.google.com/`, which Google reserves for use cases needing immediate permanent message/thread deletion. See [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes), [message send](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send), [draft send](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/send), and [message modification](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/modify).

## Tool inventory and endpoint mapping

Paths below are relative to `https://gmail.googleapis.com/gmail/v1/users/me`. The fixed `me` path binds requests to the authorized account. No tool accepts another mailbox owner or an arbitrary provider URL.

### Reading — 11 tools

| MCP tool | Provider operation | Result/use |
| --- | --- | --- |
| `gmail_profile` | [GET `/profile`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/getProfile) | Mailbox identity, message/thread totals, current history ID |
| `gmail_list_messages` | [GET `/messages`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list) | Search/filter message IDs and obtain the next page token |
| `gmail_get_message` | [GET `/messages/{id}`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get) | Retrieve a selected message with its supported format |
| `gmail_get_attachment` | [GET `/messages/{messageId}/attachments/{id}`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages.attachments/get) | Retrieve one message attachment |
| `gmail_list_threads` | [GET `/threads`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/list) | Search/filter conversations |
| `gmail_get_thread` | [GET `/threads/{id}`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/get) | Retrieve the messages within a conversation |
| `gmail_list_labels` | [GET `/labels`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.labels/list) | Discover system and custom label IDs/names |
| `gmail_get_label` | [GET `/labels/{id}`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.labels/get) | Retrieve one label and its details |
| `gmail_list_drafts` | [GET `/drafts`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/list) | Search/list saved drafts |
| `gmail_get_draft` | [GET `/drafts/{id}`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/get) | Retrieve a draft's current message |
| `gmail_list_history` | [GET `/history`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list) | Page through mailbox changes after a known history ID |

Message listing returns IDs, not complete email bodies. Search and pagination remain explicit so a single request does not silently enumerate an entire mailbox. Google permits up to 500 results per list call; the connector may impose a lower limit, as recorded in each tool's schema and runtime validation. Message search supports Gmail query syntax and an intersection of supplied label IDs. `includeSpamTrash` is a separate choice. See [message listing](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list).

Message and draft retrieval support `full`, `metadata`, `minimal`, and `raw`; thread retrieval supports `full`, `metadata`, and `minimal` only. The body in `raw` format is base64url encoded. Gmail's `metadata` scope cannot retrieve full/raw content and cannot perform message/thread `q` searches; the connector uses the read-only scope for its reading mode. See [message formats](https://developers.google.com/workspace/gmail/api/reference/rest/v1/Format) and [thread formats](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/get).

MIME parts can contain data inline or reference a separate attachment. The attachment body supplies base64url data and decoded byte size. Clients must not assume every part is text or treat an empty multipart container as a missing message. See [MessagePartBody](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages.attachments).

History is incremental provider data, not a permanent SecureMCP audit ledger. `startHistoryId` must come from a prior provider result; IDs are not contiguous. An expired/invalid ID can return HTTP 404 and require the client to start a fresh synchronization. The connector does not start a background sync or store synchronization cursors automatically. See [history listing](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list).

### Drafting and sending — 6 tools

| MCP tool | Provider operation | Effect |
| --- | --- | --- |
| `gmail_create_draft` | [POST `/drafts`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/create) | Create an unsent draft |
| `gmail_update_draft` | [PUT `/drafts/{id}`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/update) | Replace all content of a saved draft |
| `gmail_delete_draft` | [DELETE `/drafts/{id}`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/delete) | Permanently delete that draft |
| `gmail_send_draft` | [POST `/drafts/send`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/send) | Send an existing draft to its recipients |
| `gmail_send_message` | [POST `/messages/send`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send) | Send a newly composed email |
| `gmail_reply_message` | [GET original message](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get), then [POST `/messages/send`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send) | Send a reply with the original conversation's headers |

Gmail expects RFC-compliant MIME serialized into a base64url `raw` value. Direct send uses a message resource; draft creation/replacement nests that message under `message`. The runtime constructs MIME from its structured tool arguments. Uploaded attachment content is part of the MIME message rather than a separate unbounded server-side URL fetch. See [Google's sending guide](https://developers.google.com/workspace/gmail/api/guides/sending).

Draft replacement is not a field patch: omitted prior body content or attachments are not implicitly retained. A draft's ID is stable, but its underlying message ID changes when content is replaced. Sending deletes the draft and returns a new sent message. A client must distinguish draft IDs from message IDs. See [draft lifecycle](https://developers.google.com/workspace/gmail/api/guides/drafts).

A reply needs the original thread ID, RFC-compliant `References` and `In-Reply-To` headers, and a matching subject. A thread ID alone does not establish reply threading. See [threading requirements](https://developers.google.com/workspace/gmail/api/guides/threads).

Sending has an external effect. Registry publication, account verification, and MCP discovery never send a message. A provider response containing a sent-message ID records Gmail accepting the operation; it does not prove delivery to every recipient. If a send request fails ambiguously after transmission, clients should inspect their sent mail before retrying to avoid duplicates.

### Mail organization — 9 tools

| MCP tool | Provider operation | Effect |
| --- | --- | --- |
| `gmail_create_label` | [POST `/labels`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.labels/create) | Create a custom label |
| `gmail_update_label` | [PATCH `/labels/{id}`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.labels/patch) | Change supported label properties |
| `gmail_delete_label` | [DELETE `/labels/{id}`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.labels/delete) | Delete a label and its associations |
| `gmail_modify_message_labels` | [POST `/messages/{id}/modify`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/modify) | Add/remove labels on one message |
| `gmail_modify_thread_labels` | [POST `/threads/{id}/modify`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/modify) | Add/remove labels on existing messages in a thread |
| `gmail_trash_message` | [POST `/messages/{id}/trash`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/trash) | Move one message to Trash |
| `gmail_untrash_message` | [POST `/messages/{id}/untrash`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/untrash) | Restore one message from Trash |
| `gmail_trash_thread` | [POST `/threads/{id}/trash`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/trash) | Move a thread's messages to Trash |
| `gmail_untrash_thread` | [POST `/threads/{id}/untrash`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/untrash) | Restore a thread's messages from Trash |

Label mutation uses `addLabelIds` and `removeLabelIds`, with Google's limit of 100 each per operation. System label names are reserved. Draft messages cannot receive ordinary labels. Thread label changes affect existing messages; new replies do not automatically inherit them. See [message modification](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/modify), [thread modification](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/modify), and [label semantics](https://developers.google.com/workspace/gmail/api/guides/labels).

Trash/restoration is distinct from permanent deletion. Deleting a label removes its associations and does not delete the associated messages. Deleting a draft is permanent. Tool descriptions and annotations must retain these distinctions so a client can present the actual effect.

## SecureMCP publication and persistence

The Gmail server manifest is version `0.4.0`, declares both read and write resource access, and is not globally idempotent. The full prepared consumer catalog now uses version `0.4.0`; see `catalog-tool-coverage.md` for every product. The generated Gmail descriptor records `tool_coverage` with the provider API version, review date, source URLs, current registered tool count, and exclusions. Runtime annotations accompany each tool when registration provides them.

`source_sha256` identifies the Gmail runtime module. `bundle_sha256` covers every `consumer_*.py` module, including the shared runtime and Google permission helper. These hashes associate the artifact with code; they are not proof of deployment, independent certification, or a successful Google account test.

Generation writes a local submission artifact only. It does not publish a new listing, approve a revision, expand an existing profile's selected tools, change account credentials, or activate a profile. The normal publisher/reviewer process and current SecureMCP controls remain required. A catalog definition is separate from the tools available to an individual MCP client through its approved profile.

Persisted listing metadata preserves the generated inventory after publication through the normal registry storage path. It never contains consumer OAuth tokens. Consumer credentials belong to the owner's connection, and access-mode changes do not retroactively authorize a broader scope. Generated metadata keeps `live_tested: false` until a separately documented real-account validation establishes what was tested.

## Coverage limits and validation

This version excludes account settings, forwarding, filters, delegates, send-as administration, S/MIME, organization-wide classification administration, permanent message/thread deletion, bulk mutations, message import/insertion, push watches, and automatic background synchronization. It provides mailbox product operations, not account administration or external business workflows. No Google-account administration scope or arbitrary provider HTTP tool is supplied.

Local automated validation can establish descriptor/schema registration, request construction, permission denial, OAuth-mode handling, payload bounds, and provider-error handling against controlled fixtures. It cannot establish that a real account granted authorization, that its Workspace administrator permits the app, that its quota is sufficient, or that a sent email is delivered. Release notes must report executed checks separately from the following live-account acceptance checklist:

1. Authorize a dedicated test account with Read only; verify real search, retrieval, labels, drafts, attachments, and history, and confirm a write is denied.
2. Switch to Read, draft and send; confirm reauthorization, create and retrieve a test draft, replace it, and send only to an explicitly chosen test recipient.
3. Verify reply threading, Unicode content, and a small harmless attachment with that recipient.
4. Switch to Manage mail; use a test label and test messages to exercise label changes, trash, and restore. Exercise permanent draft deletion only on a disposable test draft.
5. Remove a tool from the approved profile or disconnect the account and verify the associated runtime call is denied.

This checklist does not itself execute operations or assert that they have passed.

## Next Google product increments

Gmail's expansion does not change the other Google connectors' tool counts or grant requirements. Each product needs its own registered schemas, access modes, source-linked coverage record, provider fixtures, and separate live-account acceptance checks before claiming runtime validation.

| Next product | Proposed bounded increment | Official API reference |
| --- | --- | --- |
| Google Docs | Read/create documents and explicit edits, with revision-aware validation and a separate grant for writes | [Docs API v1](https://developers.google.com/workspace/docs/api/reference/rest) |
| Google Tasks | Task-list discovery and task create/update/complete/move/delete operations, with clear destructive effects | [Tasks API v1](https://developers.google.com/workspace/tasks/reference/rest) |
| Google Calendar | Calendar/event discovery, availability queries, and explicit event create/update/cancel operations with attendee effects visible | [Calendar API v3](https://developers.google.com/workspace/calendar/api/v3/reference) |
| Google Drive | File search/read/download/export followed by bounded create/update/move operations; sharing changes require separate consideration | [Drive API v3](https://developers.google.com/workspace/drive/api/reference/rest/v3) |

These are proposed next increments, not tools claimed as implemented by Gmail version `0.4.0`.
