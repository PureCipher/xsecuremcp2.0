# Business connector tool coverage

Consumer catalog version **0.4.0**, reviewed **2026-09-07**. Implementation:
`src/purecipher/consumer_business.py`. Contract tests:
`tests/test_consumer_business.py`.

This module adds **90 concrete tools** across 13 product IDs, including the
GitHub and Slack reference aliases. Existing tools in `consumer_cloud.py` retain
their names and behavior. This is practical coverage of common product
operations, not a declaration that every vendor API is implemented. There is
no live-account certification: provider requests in this test suite are mocked.

## Access and runtime behavior

Each operation uses the authenticated connection owner's credentials from the
current SecureMCP profile context. Tool registration does not grant execution
permission: connection readiness, profile/client assignments and the existing
SecureMCP controls still apply. The helper checks the current allowed tools,
connection/profile revisions and credential readiness immediately before every
provider request. These new handlers each perform one provider operation.

Read tools have `readOnlyHint=true`. Mutations have `readOnlyHint=false`,
`idempotentHint=false` and `risk:high`; replacements, deletion, sends and other
destructive operations also have `destructiveHint=true`. Every tool has an
explicit resource tag. Hints describe behavior; they are not an authorization
mechanism. A model's request is not by itself permission to send messages,
refund payments or activate external automation.

HTTP requests do not follow redirects or retry automatically. Jira, Confluence
and n8n use the existing DNS-pinned secure outbound transport for configured
HTTPS hosts. Other providers use fixed origins. Resource IDs are path-encoded;
traversal and control characters are rejected. No tool accepts an arbitrary URL
or HTTP method. Inputs and pages are bounded, JSON payloads are limited to 64 KB,
and responses are limited to 2 MiB. Larger results require narrower queries.

Provider errors are sanitized. Timeout, server failure or invalid JSON after a
mutation produces an uncertain-outcome message: users must inspect the product
before retrying. A successful 202 means accepted, not delivered or completed.
Provider credential fields, nested client secrets and Graph temporary download
URLs are removed. n8n responses deliberately omit node parameters, credential
references and execution input/output payloads.

## API versions and permissions

Existing connection keys remain valid. Additional operations require the owner
to authorize corresponding vendor permissions; the module never expands a
token's scopes. Read-only credentials can still use permitted read tools.

| Product | API contract | Additional access for the new operations |
| --- | --- | --- |
| GitHub and GitHub reference | REST, `X-GitHub-Api-Version: 2022-11-28` | Repository metadata/Contents/Issues/Pull requests read; Issues write for issue changes and comments. |
| Slack and Slack reference | Slack Web API | Conversation read/history and `users:read`; `users:read.email` for email fields; `chat:write` for bot-owned messages. |
| Notion | `Notion-Version: 2026-03-11` | Read/insert/update content capabilities; each parent database/page must be shared with the connection. |
| Jira | Jira Cloud REST v3 | Browse project and issue access; create/edit/comment/transition permissions as appropriate. |
| Atlassian / Confluence | Confluence Cloud REST v2 | Space/page visibility plus create/update/delete page rights. |
| Microsoft Outlook | Microsoft Graph v1.0, delegated `/me` | Mail.Read for full mail; Mail.ReadWrite for drafts/mail updates; Mail.Send for sending; Calendars.ReadWrite for calendar changes. |
| Microsoft OneDrive | Microsoft Graph v1.0, delegated `/me` | Files.Read for reads; Files.ReadWrite for file/folder changes. |
| Stripe | REST `/v1`, account-configured API version | Restricted key read/write permissions for the exact customer, invoice, invoice-item, subscription, payment-intent or refund resource. No Connect impersonation. |
| Hugging Face | Hub API, official SDK contract reviewed below | Read access for private/gated metadata; repository creation permission/write token for the selected namespace. |
| Apollo.io | REST `/api/v1` | Endpoint-specific saved-contact/account search/create/update rights; vendor plan limits still apply. |
| n8n | Public REST `/api/v1` | `workflow:read`, `workflow:activate`, `workflow:delete`, and execution-list access. API availability depends on the installed version/plan. |

## Inventory and provider contracts

Paths below are relative to each provider API origin. Pagination is explicit;
the runtime does not silently fetch subsequent pages or follow returned links.

### GitHub — 8 new operations per alias

Both `github_` and `github_reference_` prefixes expose this same surface. The
reference variant uses its own selected connection. Existing repository/issue
list tools remain available.

| Tool suffix | Method and path |
| --- | --- |
| `get_repository` | GET `/repos/{owner}/{repo}` |
| `get_issue` | GET `/repos/{owner}/{repo}/issues/{number}` |
| `list_pull_requests` | GET `/repos/{owner}/{repo}/pulls` |
| `get_pull_request` | GET `/repos/{owner}/{repo}/pulls/{number}` |
| `get_file` | GET `/repos/{owner}/{repo}/contents/{path}` |
| `create_issue` | POST `/repos/{owner}/{repo}/issues` |
| `update_issue` | PATCH `/repos/{owner}/{repo}/issues/{number}` |
| `add_issue_comment` | POST `/repos/{owner}/{repo}/issues/{number}/comments` |

Pull requests use bounded page numbers; `has_next_page` reports the provider's
Link header. File paths support nested files and explicit refs. Large file
downloads, merges, source writes, Actions execution and repository administration
are excluded. Issue/comment changes may notify participants. Sources:
[issues](https://docs.github.com/en/rest/issues/issues?apiVersion=2022-11-28),
[comments](https://docs.github.com/en/rest/issues/comments?apiVersion=2022-11-28),
[pull requests](https://docs.github.com/en/rest/pulls/pulls?apiVersion=2022-11-28),
[repository contents](https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28).

### Slack — 6 new operations per alias

Both `slack_` and `slack_reference_` prefixes use the following operations.
The legacy internal product ID `slack-archived` remains unchanged for persisted
reference connections; it does not declare this registry's listing archived.

| Tool suffix | Web API method |
| --- | --- |
| `get_channel` | GET `conversations.info` |
| `get_user` | GET `users.info` |
| `thread_replies` | GET `conversations.replies` |
| `post_message` | POST `chat.postMessage` |
| `update_message` | POST `chat.update` |
| `delete_message` | POST `chat.delete` |

Thread pages are capped at 15 and use response cursors. Bot-token conversation
permissions vary; some channel-thread reads need a different authorized token.
Posting supports an explicit thread timestamp. Text replacement removes rich
blocks. Explicit mentions may notify users; link/media unfurls are disabled on
new messages. Files, invitations, impersonation and workspace administration are
excluded. Sources: [thread replies](https://docs.slack.dev/reference/methods/conversations.replies/),
[post](https://docs.slack.dev/reference/methods/chat.postMessage/),
[update](https://docs.slack.dev/reference/methods/chat.update/),
[delete](https://docs.slack.dev/reference/methods/chat.delete/).

### Notion — 6 new operations

| Tool | Method and path |
| --- | --- |
| `notion_get_data_source` | GET `/v1/data_sources/{id}` |
| `notion_query_data_source` | POST `/v1/data_sources/{id}/query` (read-only) |
| `notion_create_page` | POST `/v1/pages` |
| `notion_update_page_properties` | PATCH `/v1/pages/{id}` |
| `notion_append_paragraphs` | PATCH `/v1/blocks/{id}/children` |
| `notion_set_page_trashed` | PATCH `/v1/pages/{id}` with `in_trash` |

Data-source queries accept bounded native filters/sorts and cursors. Property
objects must match the retrieved schema; page parents accept title only.
Paragraphs are plain text, capped at 100 blocks and 2,000 characters each, subject
to the total request limit. Database schema administration, arbitrary rich-block
editing, permanent deletion and file uploads are excluded. Sources:
[query](https://developers.notion.com/reference/query-a-data-source),
[create page](https://developers.notion.com/reference/post-page),
[update page](https://developers.notion.com/reference/patch-page),
[append children](https://developers.notion.com/reference/patch-block-children).

### Jira — 6 new operations

`jira_search_issues` uses POST `/rest/api/3/search/jql` with `nextPageToken`,
not the deprecated search endpoint. `jira_create_issue` POSTs `/issue`;
`jira_update_issue` PUTs `/issue/{key}`; `jira_add_comment` POSTs
`/issue/{key}/comment`; `jira_list_transitions` GETs
`/issue/{key}/transitions`; `jira_transition_issue` POSTs the selected transition
ID to the same path. The last five paths share `/rest/api/3`.

Descriptions/comments are converted from text to Atlassian Document Format.
Projects or transitions requiring additional custom fields must use Jira's own
interface; bulk operations, attachments and project/workflow administration are
excluded. Sources: [enhanced issue search](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/),
[issue operations](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/),
[comments](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-comments/).

### Confluence — 5 new operations

`confluence_list_spaces` GETs `/wiki/api/v2/spaces`;
`confluence_list_space_pages` GETs `/wiki/api/v2/spaces/{id}/pages`;
`confluence_create_page` POSTs `/wiki/api/v2/pages`;
`confluence_update_page` PUTs `/wiki/api/v2/pages/{id}`;
`confluence_delete_page` DELETEs that page. Lists accept cursors.

Creation defaults to draft. Explicit `current` publishes. Updates require the
caller to supply the next version observed from an earlier read; conflicts are
not retried. Content uses Confluence storage format. Attachments, permissions,
space administration and Data Center API compatibility are excluded. Source:
[Confluence page operations](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/).

### Outlook — 11 new operations

All paths use Microsoft Graph `/v1.0/me`:

| Tool | Method and path |
| --- | --- |
| `outlook_get_message` | GET `/messages/{id}` |
| `outlook_list_folder_messages` | GET `/mailFolders/{id}/messages` |
| `outlook_list_folders` | GET `/mailFolders` |
| `outlook_create_draft` | POST `/messages` |
| `outlook_send_draft` | POST `/messages/{id}/send` |
| `outlook_move_message` | POST `/messages/{id}/move` |
| `outlook_set_message_read` | PATCH `/messages/{id}` |
| `outlook_delete_message` | DELETE `/messages/{id}` |
| `outlook_create_event` | POST `/events` |
| `outlook_update_event` | PATCH `/events/{id}` |
| `outlook_delete_event` | DELETE `/events/{id}` |

Draft recipients are explicit and validated; sending uses the saved draft's
recipients. Lists expose native next links and accept bounded `$skip` values.
Event creation excludes attendees and accepts a transaction ID; editing/deleting
an existing meeting can notify its attendees. App-only access, delegated
cross-mailbox access, attachments, recurring-series editing and mail rules are
excluded. Sources: [drafts](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0),
[send](https://learn.microsoft.com/en-us/graph/api/message-send?view=graph-rest-1.0),
[move](https://learn.microsoft.com/en-us/graph/api/message-move?view=graph-rest-1.0),
[events](https://learn.microsoft.com/en-us/graph/api/user-post-events?view=graph-rest-1.0).

### OneDrive — 6 new operations

`onedrive_list_folder` GETs `/me/drive/items/{id}/children`;
`onedrive_search_files` GETs `/me/drive/root/search(q='...')`;
`onedrive_create_folder` POSTs to the children endpoint;
`onedrive_upload_file` PUTs `/me/drive/items/{parent}:/{name}:/content`;
`onedrive_move_or_rename` PATCHes `/me/drive/items/{id}`;
`onedrive_delete_item` DELETEs the item. All use Graph v1.0.

Search quotes are encoded; pagination accepts `$skiptoken`. Folder creation
fails on conflicts. Uploads accept at most 1 MiB of explicit base64 bytes and
replace an existing same-named file. Remote download URLs, large upload sessions,
sharing links, permission changes and cross-drive moves are excluded. Sources:
[search](https://learn.microsoft.com/en-us/graph/api/driveitem-search?view=graph-rest-1.0),
[folders](https://learn.microsoft.com/en-us/graph/api/driveitem-post-children?view=graph-rest-1.0),
[upload](https://learn.microsoft.com/en-us/graph/api/driveitem-put-content?view=graph-rest-1.0),
[update](https://learn.microsoft.com/en-us/graph/api/driveitem-update?view=graph-rest-1.0).

### Stripe — 13 new operations

| Tool | Method and `/v1` path |
| --- | --- |
| `stripe_list_customers` | GET `/customers` |
| `stripe_get_customer` | GET `/customers/{id}` |
| `stripe_create_customer` | POST `/customers` |
| `stripe_update_customer` | POST `/customers/{id}` |
| `stripe_list_products` | GET `/products` |
| `stripe_list_prices` | GET `/prices` |
| `stripe_get_invoice` | GET `/invoices/{id}` |
| `stripe_create_invoice` | POST `/invoices` |
| `stripe_add_invoice_item` | POST `/invoiceitems` |
| `stripe_list_subscriptions` | GET `/subscriptions` |
| `stripe_set_subscription_cancel_at_period_end` | POST `/subscriptions/{id}` |
| `stripe_create_payment_intent` | POST `/payment_intents` |
| `stripe_refund_payment` | POST `/refunds` |

POSTs use form encoding and require a caller-supplied idempotency key. Amounts
are explicit positive integers in the currency's smallest unit. Invoice
creation disables advancement and excludes pending items. Payment intents are
unconfirmed. Refunds move real money; period-end cancellation changes future
billing. Card data, payment confirmation, payouts, transfers, Connect accounts,
tax automation and immediate subscription cancellation are excluded. Sources:
[idempotency](https://docs.stripe.com/api/idempotent_requests),
[customers](https://docs.stripe.com/api/customers/create),
[invoices](https://docs.stripe.com/api/invoices/create),
[invoice items](https://docs.stripe.com/api/invoiceitems/create),
[payment intents](https://docs.stripe.com/api/payment_intents/create),
[refunds](https://docs.stripe.com/api/refunds/create),
[subscriptions](https://docs.stripe.com/api/subscriptions/update).

### Hugging Face — 5 new operations

`huggingface_get_model`, `huggingface_get_dataset` and `huggingface_get_space`
GET `/api/{models|datasets|spaces}/{namespace}/{repo}`.
`huggingface_search_spaces` GETs `/api/spaces` with a bounded search limit.
`huggingface_create_repository` POSTs `/api/repos/create`, defaulting to private
visibility. A Space requires an explicit SDK; no paid hardware is requested.

Metadata reads do not run models or download files. Search reports an additional
page but currently requires refining the query; cursor traversal, inference,
training jobs, file commits, repository deletion and paid compute are excluded.
Sources: [Hub API](https://huggingface.co/docs/hub/api),
[official SDK request contracts](https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/hf_api.py).

### Apollo.io — 5 new operations

`apollo_search_contacts` POSTs `/api/v1/contacts/search`;
`apollo_search_accounts` POSTs `/api/v1/accounts/search`;
`apollo_create_contact` POSTs `/api/v1/contacts`;
`apollo_update_contact` PATCHes `/api/v1/contacts/{id}`;
`apollo_create_account` POSTs `/api/v1/accounts`.

Search is limited to saved CRM contacts/accounts with page-number pagination.
Contact creation does not enable deduplication, which could overwrite an
existing record. No enrichment, paid organization search, email/phone reveal,
campaign membership or outreach is added. Sources:
[contact search](https://docs.apollo.io/reference/search-for-contacts),
[account search](https://docs.apollo.io/reference/search-for-accounts),
[create contact](https://docs.apollo.io/reference/create-a-contact),
[update contact](https://docs.apollo.io/reference/update-a-contact),
[create account](https://docs.apollo.io/reference/create-an-account).

### n8n — 5 new operations

`n8n_get_workflow` GETs `/api/v1/workflows/{id}`;
`n8n_list_executions` GETs `/api/v1/executions` with `includeData=false` and
cursor pagination; `n8n_activate_workflow` and `n8n_deactivate_workflow` POST to
`/api/v1/workflows/{id}/activate` and `/deactivate`; `n8n_delete_workflow`
DELETEs `/api/v1/workflows/{id}`.

Activation can start external side effects and requires prior inspection in
n8n. Deactivation does not promise cancellation of running jobs. These tools
manage existing workflows only; authoring arbitrary code, executing workflows
on demand, credential management and execution payload retrieval are excluded.
Sources: [official CLI endpoint implementation](https://github.com/n8n-io/n8n/blob/master/packages/%40n8n/cli/src/client.ts),
[official scope reference](https://github.com/n8n-io/n8n-docs/blob/main/docs/connect/n8n-api/authentication.md).

## Verification limits

The mocked contract suite invokes every new registered name through a local
FastMCP client, checks method/origin/path, tests pagination and meaningful
provider payloads, and exercises dangerous defaults, injection/traversal, wrong
connections, changed revisions, response limits, 202/204 handling and uncertain
mutation outcomes. Custom-host calls assert use of the secure outbound helper;
the helper's DNS/SSRF behavior is covered by its own security tests.

This does not establish live vendor compatibility, token permissions, tenant
configuration, quotas, real delivery, refunds or workflow effects. Those require
explicitly authorized account testing. Adding catalog descriptors alone must
not claim a live test passed or automatically publish a changed server.
