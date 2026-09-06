"""Product-specific consumer settings from reviewed adapter and upstream definitions."""

from typing import Any

PRODUCT_SCHEMAS: dict[str, dict[str, Any]] = {
    "google-calendar": {
        "id": "google-calendar",
        "title": "Google Calendar",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
        "instructions": [
            "Save this connection, then choose Authorize Google to connect your own account.",
            "The publisher configures the OAuth app. You do not provide its client ID or client secret.",
            "Review the read-only permissions below. Disconnect removes this registry connection’s grant.",
        ],
        "source": "https://developers.google.com/identity/protocols/oauth2/web-server",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "google-drive": {
        "id": "google-drive",
        "title": "Google Drive",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["https://www.googleapis.com/auth/drive.metadata.readonly"],
        "instructions": [
            "Save this connection, then choose Authorize Google to connect your own account.",
            "The publisher configures the OAuth app. You do not provide its client ID or client secret.",
            "Review the read-only permissions below. Disconnect removes this registry connection’s grant.",
        ],
        "source": "https://developers.google.com/identity/protocols/oauth2/web-server",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "google-gmail": {
        "id": "google-gmail",
        "title": "Gmail",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        "instructions": [
            "Save this connection, then choose Authorize Google to connect your own account.",
            "The publisher configures the OAuth app. You do not provide its client ID or client secret.",
            "Review the read-only permissions below. Disconnect removes this registry connection’s grant.",
        ],
        "source": "https://developers.google.com/identity/protocols/oauth2/web-server",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "google-docs": {
        "id": "google-docs",
        "title": "Google Docs",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["https://www.googleapis.com/auth/documents.readonly"],
        "instructions": [
            "Save this connection, then choose Authorize Google to connect your own account.",
            "The publisher configures the OAuth app. You do not provide its client ID or client secret.",
            "Review the read-only permissions below. Disconnect removes this registry connection’s grant.",
        ],
        "source": "https://developers.google.com/identity/protocols/oauth2/web-server",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "google-tasks": {
        "id": "google-tasks",
        "title": "Google Tasks",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["https://www.googleapis.com/auth/tasks.readonly"],
        "instructions": [
            "Save this connection, then choose Authorize Google to connect your own account.",
            "The publisher configures the OAuth app. You do not provide its client ID or client secret.",
            "Review the read-only permissions below. Disconnect removes this registry connection’s grant.",
        ],
        "source": "https://developers.google.com/identity/protocols/oauth2/web-server",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "puppeteer": {
        "id": "puppeteer",
        "title": "Puppeteer",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Archived upstream: maintenance review required. Isolated browser, "
            "destination allowlist and per-user sessions.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/modelcontextprotocol/servers",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/puppeteer/server.yaml",
        "audience": "consumer",
    },
    "stripe": {
        "id": "stripe",
        "title": "Stripe",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["stripe_apps"],
        "instructions": [
            "Authorize your own Stripe account from your MCP client when the "
            "server is available.",
            "The publisher configures the OAuth application. You do not need its "
            "client ID or client secret.",
            "The permissions below are requested by this server. Saving a "
            "connection does not grant them; you must complete the provider "
            "consent flow.",
        ],
        "source": "https://docs.stripe.com/stripe-apps/api-authentication/oauth",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "redis": {
        "id": "redis",
        "title": "Redis",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "REDIS_PWD",
                "label": "Redis Pwd",
                "type": "secret",
                "required": True,
                "env": "REDIS_PWD",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "param:host",
                "label": "Host",
                "type": "text",
                "required": True,
                "help": "",
            },
            {
                "key": "param:port",
                "label": "Port",
                "type": "number",
                "required": False,
                "help": "",
            },
            {
                "key": "param:username",
                "label": "Username",
                "type": "text",
                "required": False,
                "help": "",
            },
            {
                "key": "param:ssl",
                "label": "Ssl",
                "type": "boolean",
                "required": False,
                "help": "",
            },
            {
                "key": "param:ca_path",
                "label": "Ca Path",
                "type": "text",
                "required": False,
                "help": "",
            },
            {
                "key": "param:ssl_keyfile",
                "label": "Ssl Keyfile",
                "type": "text",
                "required": False,
                "help": "",
            },
            {
                "key": "param:ssl_certfile",
                "label": "Ssl Certfile",
                "type": "text",
                "required": False,
                "help": "",
            },
            {
                "key": "param:cert_reqs",
                "label": "Cert Reqs",
                "type": "text",
                "required": False,
                "help": "",
            },
            {
                "key": "param:ca_certs",
                "label": "Ca Certs",
                "type": "text",
                "required": False,
                "help": "",
            },
            {
                "key": "param:cluster_mode",
                "label": "Cluster Mode",
                "type": "boolean",
                "required": False,
                "help": "",
            },
        ],
        "scopes": [],
        "instructions": [
            "Dedicated Redis ACL user and key prefixes; block administrative and "
            "destructive commands.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/redis/mcp-redis",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/redis/server.yaml",
        "audience": "consumer",
    },
    "youtube-transcripts": {
        "id": "youtube-transcripts",
        "title": "YouTube Transcripts",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Restricted YouTube egress, transcript availability and usage review.",
            "These settings belong to your account. A profile can "
            "select this connection for its assigned clients. Saving "
            "does not deploy or activate the server.",
        ],
        "source": "https://github.com/jkawamoto/mcp-youtube-transcript",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/youtube_transcript/server.yaml",
        "audience": "consumer",
    },
    "cloudwatch": {
        "id": "cloudwatch",
        "title": "Amazon CloudWatch",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "param:aws_region",
                "label": "Aws Region",
                "type": "text",
                "required": False,
                "help": "",
            },
            {
                "key": "param:aws_profile",
                "label": "Aws Profile",
                "type": "text",
                "required": False,
                "help": "",
            },
        ],
        "scopes": [],
        "instructions": [
            "Scoped read-only AWS role, region/account/log-group allowlists "
            "and query-cost limits.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/awslabs/mcp",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/awslabs-cloudwatch/server.yaml",
        "audience": "consumer",
    },
    "dynatrace": {
        "id": "dynatrace",
        "title": "Dynatrace",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "OAUTH_CLIENT_ID",
                "label": "Oauth Client Id",
                "type": "secret",
                "required": True,
                "env": "OAUTH_CLIENT_ID",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "OAUTH_CLIENT_SECRET",
                "label": "Oauth Client Secret",
                "type": "secret",
                "required": True,
                "env": "OAUTH_CLIENT_SECRET",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "param:url",
                "label": "Url",
                "type": "text",
                "required": False,
                "help": "",
            },
        ],
        "scopes": [],
        "instructions": [
            "Dynatrace environment and scoped OAuth credentials; read-only "
            "tool allowlist.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/dynatrace-oss/dynatrace-mcp",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/dynatrace-mcp-server/server.yaml",
        "audience": "consumer",
    },
    "aws-documentation": {
        "id": "aws-documentation",
        "title": "AWS Documentation",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "AWS documentation-only egress and bounded retrieval; no "
            "AWS account credentials required for documentation reads.",
            "These settings belong to your account. A profile can "
            "select this connection for its assigned clients. Saving "
            "does not deploy or activate the server.",
        ],
        "source": "https://github.com/awslabs/mcp",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/aws-documentation/server.yaml",
        "audience": "consumer",
    },
    "clickhouse": {
        "id": "clickhouse",
        "title": "ClickHouse",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "CLICKHOUSE_PASSWORD",
                "label": "Clickhouse Password",
                "type": "secret",
                "required": True,
                "env": "CLICKHOUSE_PASSWORD",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "param:host",
                "label": "Host",
                "type": "text",
                "required": True,
                "help": "",
            },
            {
                "key": "param:port",
                "label": "Port",
                "type": "number",
                "required": False,
                "help": "",
            },
            {
                "key": "param:user",
                "label": "User",
                "type": "text",
                "required": True,
                "help": "",
            },
            {
                "key": "param:secure",
                "label": "Secure",
                "type": "boolean",
                "required": False,
                "help": "",
            },
            {
                "key": "param:verify",
                "label": "Verify",
                "type": "boolean",
                "required": False,
                "help": "",
            },
            {
                "key": "param:connect_timeout",
                "label": "Connect Timeout",
                "type": "number",
                "required": False,
                "help": "",
            },
            {
                "key": "param:send_receive_timeout",
                "label": "Send Receive Timeout",
                "type": "number",
                "required": False,
                "help": "",
            },
        ],
        "scopes": [],
        "instructions": [
            "Read-only database account, restricted databases and query "
            "limits; block external table functions via database settings.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/ClickHouse/mcp-clickhouse",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/clickhouse/server.yaml",
        "audience": "consumer",
    },
    "ast-grep": {
        "id": "ast-grep",
        "title": "ast-grep",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "param:path",
                "label": "Path",
                "type": "text",
                "required": True,
                "help": "",
            }
        ],
        "scopes": [],
        "instructions": [
            "Dedicated code directory and read-only structural search; "
            "rewriting requires explicit approval.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/dgageot/mcp-ast-grep",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/ast-grep/server.yaml",
        "audience": "consumer",
    },
    "slack": {
        "id": "slack",
        "title": "Slack",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["channels:read", "channels:history"],
        "instructions": [
            "Authorize your own Slack account from your MCP client when the server "
            "is available.",
            "The publisher configures the OAuth application. You do not need its "
            "client ID or client secret.",
            "The permissions below are requested by this server. Saving a "
            "connection does not grant them; you must complete the provider "
            "consent flow.",
        ],
        "source": "https://api.slack.com/authentication/oauth-v2",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "github": {
        "id": "github",
        "title": "GitHub",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["read:user"],
        "instructions": [
            "Authorize your own GitHub account from your MCP client when the "
            "server is available.",
            "The publisher configures the OAuth application. You do not need its "
            "client ID or client secret.",
            "The permissions below are requested by this server. Saving a "
            "connection does not grant them; you must complete the provider "
            "consent flow.",
        ],
        "source": "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "apollo": {
        "id": "apollo",
        "title": "Apollo.io",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["read_user_profile", "mixed_people_api_search"],
        "instructions": [
            "Authorize your own Apollo.io account from your MCP client when the "
            "server is available.",
            "The publisher configures the OAuth application. You do not need its "
            "client ID or client secret.",
            "The permissions below are requested by this server. Saving a "
            "connection does not grant them; you must complete the provider "
            "consent flow.",
        ],
        "source": "https://docs.apollo.io/docs/use-oauth-20-authorization-flow-to-access-apollo-user-information-partners",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "nodejs-sandbox": {
        "id": "nodejs-sandbox",
        "title": "Node.js Sandbox",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Disposable unprivileged containers with CPU/memory/time "
            "limits and restricted egress. Never expose the production "
            "Docker socket.",
            "These settings belong to your account. A profile can select "
            "this connection for its assigned clients. Saving does not "
            "deploy or activate the server.",
        ],
        "source": "https://github.com/alfonsograziano/node-code-sandbox-mcp",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/node-code-sandbox/server.yaml",
        "audience": "consumer",
    },
    "notion": {
        "id": "notion",
        "title": "Notion",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "INTERNAL_INTEGRATION_TOKEN",
                "label": "Internal Integration Token",
                "type": "secret",
                "required": True,
                "env": "INTERNAL_INTEGRATION_TOKEN",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            }
        ],
        "scopes": [],
        "instructions": [
            "Notion workspace authorization, allowed pages and databases, review "
            "read/write scopes.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/makenotion/notion-mcp-server",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/notion/server.yaml",
        "audience": "consumer",
    },
    "kubernetes": {
        "id": "kubernetes",
        "title": "Kubernetes",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "param:config_path",
                "label": "Config Path",
                "type": "text",
                "required": True,
                "help": "the path to the host .kube/config",
            }
        ],
        "scopes": [],
        "instructions": [
            "Dedicated namespace and read-only RBAC; no cluster-admin, "
            "secrets access, exec or mutation by default.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/Flux159/mcp-server-kubernetes",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/kubernetes/server.yaml",
        "audience": "consumer",
    },
    "huggingface": {
        "id": "huggingface",
        "title": "Hugging Face",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["openid", "profile", "read-repos"],
        "instructions": [
            "Authorize your own Hugging Face account from your MCP client "
            "when the server is available.",
            "The publisher configures the OAuth application. You do not need "
            "its client ID or client secret.",
            "The permissions below are requested by this server. Saving a "
            "connection does not grant them; you must complete the provider "
            "consent flow.",
        ],
        "source": "https://huggingface.co/docs/hub/oauth",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "git": {
        "id": "git",
        "title": "Git (Reference)",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "param:paths",
                "label": "Paths",
                "type": "lines",
                "required": True,
                "help": "",
            }
        ],
        "scopes": [],
        "instructions": [
            "Dedicated repository checkout; path restrictions and explicit approval "
            "for mutations or remote pushes.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or activate "
            "the server.",
        ],
        "source": "https://github.com/modelcontextprotocol/servers",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/git/server.yaml",
        "audience": "consumer",
    },
    "n8n": {
        "id": "n8n",
        "title": "n8n",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "N8N_API_KEY",
                "label": "N8N Api Key",
                "type": "secret",
                "required": True,
                "env": "N8N_API_KEY",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "param:api_url",
                "label": "Api Url",
                "type": "text",
                "required": True,
                "help": "The URL of your n8n instance (use http://host.docker.internal:5678 "
                "for local instances)",
            },
        ],
        "scopes": [],
        "instructions": [
            "Dedicated workspace/API credential, workflow allowlist and approval "
            "before execution or updates.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or activate "
            "the server.",
        ],
        "source": "https://github.com/czlonkowski/n8n-mcp",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/n8n/server.yaml",
        "audience": "consumer",
    },
    "sequential-thinking": {
        "id": "sequential-thinking",
        "title": "Sequential Thinking (Reference)",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Per-session state isolation and bounded input/history sizes.",
            "These settings belong to your account. A profile can "
            "select this connection for its assigned clients. Saving "
            "does not deploy or activate the server.",
        ],
        "source": "https://github.com/modelcontextprotocol/servers",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/sequentialthinking/server.yaml",
        "audience": "consumer",
    },
    "playwright": {
        "id": "playwright",
        "title": "Playwright",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Isolated browser, destination allowlist, no host mounts, "
            "reviewed actions and per-user sessions.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/microsoft/playwright-mcp",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/playwright/server.yaml",
        "audience": "consumer",
    },
    "duckduckgo": {
        "id": "duckduckgo",
        "title": "Private Web Search",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Restricted search egress; review provider terms and rate limits.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/nickclyde/duckduckgo-mcp-server",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/duckduckgo/server.yaml",
        "audience": "consumer",
    },
    "fetch": {
        "id": "fetch",
        "title": "Fetch (Reference)",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Egress allowlist including redirect and DNS-rebinding defenses; block "
            "private and metadata addresses.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/modelcontextprotocol/servers",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/fetch/server.yaml",
        "audience": "consumer",
    },
    "atlassian": {
        "id": "atlassian",
        "title": "Atlassian",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "CONFLUENCE_API_TOKEN",
                "label": "Confluence Api Token",
                "type": "secret",
                "required": False,
                "env": "CONFLUENCE_API_TOKEN",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "CONFLUENCE_PERSONAL_TOKEN",
                "label": "Confluence Personal Token",
                "type": "secret",
                "required": False,
                "env": "CONFLUENCE_PERSONAL_TOKEN",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "JIRA_API_TOKEN",
                "label": "Jira Api Token",
                "type": "secret",
                "required": False,
                "env": "JIRA_API_TOKEN",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "JIRA_PERSONAL_TOKEN",
                "label": "Jira Personal Token",
                "type": "secret",
                "required": False,
                "env": "JIRA_PERSONAL_TOKEN",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "param:confluence.url",
                "label": "Confluence · Url",
                "type": "text",
                "required": True,
                "help": "",
            },
            {
                "key": "param:confluence.username",
                "label": "Confluence · Username",
                "type": "text",
                "required": False,
                "help": "",
            },
            {
                "key": "param:jira.url",
                "label": "Jira · Url",
                "type": "text",
                "required": True,
                "help": "",
            },
            {
                "key": "param:jira.username",
                "label": "Jira · Username",
                "type": "text",
                "required": False,
                "help": "",
            },
        ],
        "scopes": [],
        "instructions": [
            "Confluence/Jira site authorization and project/page scope; "
            "separate from the existing Jira integration.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/sooperset/mcp-atlassian",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/atlassian/server.yaml",
        "audience": "consumer",
    },
    "arxiv": {
        "id": "arxiv",
        "title": "ArXiv",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "param:storage_path",
                "label": "Storage Path",
                "type": "text",
                "required": True,
                "help": "Directory path where downloaded papers will be stored",
            }
        ],
        "scopes": [],
        "instructions": [
            "Bounded searches/downloads, dedicated storage, network restrictions "
            "and PDF parsing sandbox.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/jasonleinart/arxiv-mcp-server",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/arxiv-mcp-server/server.yaml",
        "audience": "consumer",
    },
    "brave-search": {
        "id": "brave-search",
        "title": "Brave Search",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "BRAVE_API_KEY",
                "label": "Brave Api Key",
                "type": "secret",
                "required": True,
                "env": "BRAVE_API_KEY",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            }
        ],
        "scopes": [],
        "instructions": [
            "Brave Search API key and request budget/rate limits.",
            "These settings belong to your account. A profile can select "
            "this connection for its assigned clients. Saving does not "
            "deploy or activate the server.",
        ],
        "source": "https://github.com/brave/brave-search-mcp-server",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/brave/server.yaml",
        "audience": "consumer",
    },
    "firecrawl": {
        "id": "firecrawl",
        "title": "Firecrawl",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "FIRECRAWL_API_KEY",
                "label": "Firecrawl Api Key",
                "type": "secret",
                "required": True,
                "env": "FIRECRAWL_API_KEY",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "param:credit_critical_threshold",
                "label": "Credit Critical Threshold",
                "type": "number",
                "required": False,
                "help": "",
            },
            {
                "key": "param:credit_warning_threshold",
                "label": "Credit Warning Threshold",
                "type": "number",
                "required": False,
                "help": "",
            },
            {
                "key": "param:retry_backoff_factor",
                "label": "Retry Backoff Factor",
                "type": "number",
                "required": False,
                "help": "",
            },
            {
                "key": "param:retry_delay",
                "label": "Retry Delay",
                "type": "number",
                "required": False,
                "help": "",
            },
            {
                "key": "param:retry_max",
                "label": "Retry Max",
                "type": "number",
                "required": False,
                "help": "",
            },
            {
                "key": "param:retry_max_delay",
                "label": "Retry Max Delay",
                "type": "number",
                "required": False,
                "help": "",
            },
            {
                "key": "param:url",
                "label": "Url",
                "type": "text",
                "required": False,
                "help": "",
            },
        ],
        "scopes": [],
        "instructions": [
            "API key, destination restrictions, crawl/page limits and credit budget.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/mendableai/firecrawl-mcp-server",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/firecrawl/server.yaml",
        "audience": "consumer",
    },
    "desktop-commander": {
        "id": "desktop-commander",
        "title": "Desktop Commander",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "param:paths",
                "label": "Paths",
                "type": "lines",
                "required": True,
                "help": "List of directories that Desktop Commander can access",
            }
        ],
        "scopes": [],
        "instructions": [
            "Dedicated sandbox with no host home or secrets; explicit "
            "command and filesystem policies. Never grant production "
            "host shell access.",
            "These settings belong to your account. A profile can "
            "select this connection for its assigned clients. Saving "
            "does not deploy or activate the server.",
        ],
        "source": "https://github.com/wonderwhy-er/DesktopCommanderMCP",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/desktop-commander/server.yaml",
        "audience": "consumer",
    },
    "mongodb": {
        "id": "mongodb",
        "title": "MongoDB",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "MDB_MCP_CONNECTION_STRING",
                "label": "Mdb Mcp Connection String",
                "type": "secret",
                "required": True,
                "env": "MDB_MCP_CONNECTION_STRING",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            }
        ],
        "scopes": [],
        "instructions": [
            "Least-privilege database account, database/collection allowlists, "
            "bounded read-only queries before permitting writes.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/mongodb-js/mongodb-mcp-server",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/mongodb/server.yaml",
        "audience": "consumer",
    },
    "sonarqube": {
        "id": "sonarqube",
        "title": "SonarQube",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "SONARQUBE_TOKEN",
                "label": "Sonarqube Token",
                "type": "secret",
                "required": True,
                "env": "SONARQUBE_TOKEN",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "param:url",
                "label": "Url",
                "type": "text",
                "required": False,
                "help": "URL of the SonarQube instance, to provide only for SonarQube "
                "Server or Community Build",
            },
            {
                "key": "param:org",
                "label": "Org",
                "type": "text",
                "required": False,
                "help": "Organization key for SonarQube Cloud, not required for "
                "SonarQube Server or Community Build",
            },
        ],
        "scopes": [],
        "instructions": [
            "SonarQube site and least-privilege user token; read-only tool allowlist.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/SonarSource/sonarqube-mcp-server",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/sonarqube/server.yaml",
        "audience": "consumer",
    },
    "aws-core": {
        "id": "aws-core",
        "title": "AWS Core",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Review delegated AWS server selection and IAM permissions. No "
            "implicit server installation or privileged account access.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/awslabs/mcp",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/aws-core-mcp-server/server.yaml",
        "audience": "consumer",
    },
    "markitdown": {
        "id": "markitdown",
        "title": "Markitdown",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "param:paths",
                "label": "Paths",
                "type": "lines",
                "required": True,
                "help": "",
            }
        ],
        "scopes": [],
        "instructions": [
            "Sandbox document conversion, input size/type limits, no "
            "arbitrary file paths or unrestricted URL fetches.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/microsoft/markitdown",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/markitdown/server.yaml",
        "audience": "consumer",
    },
    "time": {
        "id": "time",
        "title": "Time (Reference)",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Reviewed timezone tools; no provider credentials required.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/modelcontextprotocol/servers",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/time/server.yaml",
        "audience": "consumer",
    },
    "obsidian": {
        "id": "obsidian",
        "title": "Obsidian",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "OBSIDIAN_API_KEY",
                "label": "Obsidian Api Key",
                "type": "secret",
                "required": True,
                "env": "OBSIDIAN_API_KEY",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            }
        ],
        "scopes": [],
        "instructions": [
            "Dedicated vault and scoped REST credential; restrict paths and "
            "review note writes separately.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/docker/mcp-obsidian",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/obsidian/server.yaml",
        "audience": "consumer",
    },
    "memory": {
        "id": "memory",
        "title": "Memory (Reference)",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Dedicated persistent volume and tenant isolation; explicit consent "
            "for memory mutations.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/modelcontextprotocol/servers",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/memory/server.yaml",
        "audience": "consumer",
    },
    "onedrive": {
        "id": "onedrive",
        "title": "Microsoft OneDrive",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["User.Read", "Files.Read", "offline_access"],
        "instructions": [
            "Authorize your own Microsoft OneDrive account from your MCP client "
            "when the server is available.",
            "The publisher configures the OAuth application. You do not need "
            "its client ID or client secret.",
            "The permissions below are requested by this server. Saving a "
            "connection does not grant them; you must complete the provider "
            "consent flow.",
        ],
        "source": "https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "slack-archived": {
        "id": "slack-archived",
        "title": "Slack (Reference)",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "SLACK_BOT_TOKEN",
                "label": "Slack Bot Token",
                "type": "secret",
                "required": True,
                "env": "SLACK_BOT_TOKEN",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "param:team_id",
                "label": "Team Id",
                "type": "text",
                "required": True,
                "help": "",
            },
            {
                "key": "param:channel_ids",
                "label": "Channel Ids",
                "type": "text",
                "required": False,
                "help": "",
            },
        ],
        "scopes": [],
        "instructions": [
            "Archived upstream: maintenance review required. Prefer the "
            "existing PureCipher Slack OAuth integration.",
            "These settings belong to your account. A profile can select "
            "this connection for its assigned clients. Saving does not "
            "deploy or activate the server.",
        ],
        "source": "https://github.com/modelcontextprotocol/servers",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/slack/server.yaml",
        "audience": "consumer",
    },
    "wikipedia": {
        "id": "wikipedia",
        "title": "Wikipedia",
        "version": 1,
        "kind": "upstream",
        "fields": [],
        "scopes": [],
        "instructions": [
            "Bounded query sizes and Wikipedia-only egress; retrieved content "
            "is untrusted.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/Rudra-ravi/wikipedia-mcp",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/wikipedia-mcp/server.yaml",
        "audience": "consumer",
    },
    "outlook": {
        "id": "outlook",
        "title": "Microsoft Outlook",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["User.Read", "Mail.Read", "Calendars.Read", "offline_access"],
        "instructions": [
            "Authorize your own Microsoft Outlook account from your MCP client "
            "when the server is available.",
            "The publisher configures the OAuth application. You do not need its "
            "client ID or client secret.",
            "The permissions below are requested by this server. Saving a "
            "connection does not grant them; you must complete the provider "
            "consent flow.",
        ],
        "source": "https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "filesystem": {
        "id": "filesystem",
        "title": "Filesystem (Reference)",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "param:paths",
                "label": "Paths",
                "type": "lines",
                "required": True,
                "help": "",
            }
        ],
        "scopes": [],
        "instructions": [
            "Dedicated read-only directory mounts; no host home, secrets or "
            "Docker socket; no network.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/modelcontextprotocol/servers",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/filesystem/server.yaml",
        "audience": "consumer",
    },
    "jira": {
        "id": "jira",
        "title": "Jira",
        "version": 1,
        "kind": "oauth",
        "fields": [],
        "scopes": ["read:me", "read:jira-work", "offline_access"],
        "instructions": [
            "Authorize your own Jira account from your MCP client when the server "
            "is available.",
            "The publisher configures the OAuth application. You do not need its "
            "client ID or client secret.",
            "The permissions below are requested by this server. Saving a "
            "connection does not grant them; you must complete the provider consent "
            "flow.",
        ],
        "source": "https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/",
        "runtime_supported": False,
        "audience": "consumer",
    },
    "grafana": {
        "id": "grafana",
        "title": "Grafana",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "GRAFANA_API_KEY",
                "label": "Grafana Api Key",
                "type": "secret",
                "required": True,
                "env": "GRAFANA_API_KEY",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "param:url",
                "label": "Url",
                "type": "text",
                "required": True,
                "help": "",
            },
        ],
        "scopes": [],
        "instructions": [
            "Grafana URL and least-privilege service account; read-only tool "
            "allowlist.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/grafana/mcp-grafana",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/grafana/server.yaml",
        "audience": "consumer",
    },
    "docker-hub": {
        "id": "docker-hub",
        "title": "Docker Hub",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "HUB_PAT_TOKEN",
                "label": "Hub Pat Token",
                "type": "secret",
                "required": True,
                "env": "HUB_PAT_TOKEN",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            },
            {
                "key": "param:username",
                "label": "Username",
                "type": "text",
                "required": True,
                "help": "",
            },
        ],
        "scopes": [],
        "instructions": [
            "Scoped Docker Hub token; repository allowlist and explicit "
            "approval for mutations.",
            "These settings belong to your account. A profile can select this "
            "connection for its assigned clients. Saving does not deploy or "
            "activate the server.",
        ],
        "source": "https://github.com/docker/hub-mcp",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/dockerhub/server.yaml",
        "audience": "consumer",
    },
    "github-reference": {
        "id": "github-reference",
        "title": "GitHub (Reference)",
        "version": 1,
        "kind": "upstream",
        "fields": [
            {
                "key": "GITHUB_PERSONAL_ACCESS_TOKEN",
                "label": "Github Personal Access Token",
                "type": "secret",
                "required": True,
                "env": "GITHUB_PERSONAL_ACCESS_TOKEN",
                "help": "Stored encrypted. Leave blank to keep the saved value.",
            }
        ],
        "scopes": [],
        "instructions": [
            "Upstream catalog marks this reference archived. Review "
            "maintenance; prefer the existing PureCipher GitHub "
            "integration.",
            "These settings belong to your account. A profile can "
            "select this connection for its assigned clients. Saving "
            "does not deploy or activate the server.",
        ],
        "source": "https://github.com/modelcontextprotocol/servers",
        "runtime_supported": False,
        "catalog_source": "https://raw.githubusercontent.com/docker/mcp-registry/main/servers/github/server.yaml",
        "audience": "consumer",
    },
}
