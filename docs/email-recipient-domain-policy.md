# Email recipient domain policy

`EmailRecipientDomainPolicy` prevents matching MCP tools from sending email to
domains outside an operator-controlled allowlist. It parses every mailbox before
making a decision; it does not apply a suffix check to the original argument.

```python
from fastmcp.server.security.config import PolicyConfig, SecurityConfig
from fastmcp.server.security.policy import EmailRecipientDomainPolicy
from securemcp import SecureMCP

recipient_policy = EmailRecipientDomainPolicy(
    allowed_domains={"acme.com"},
    tool_patterns={"send_email", "gmail_send_*"},
    argument_paths=("to", "cc", "bcc", "content.to", "content.cc"),
    allow_subdomains=False,
)

server = SecureMCP(
    "internal-mail",
    security=SecurityConfig(
        policy=PolicyConfig(providers=[recipient_policy]),
    ),
)
```

The same rule can be managed as declarative policy:

```yaml
type: email_recipient_domains
policy_id: internal-mail-recipients
version: 1.0.0
allowed_domains:
  - acme.com
tool_patterns:
  - send_email
  - gmail_send_*
argument_paths:
  - to
  - cc
  - bcc
  - content.to
  - content.cc
  - content.bcc
allow_subdomains: false
require_recipient: true
max_recipients: 100
```

## Enforcement behavior

- Recipient fields may be a mailbox string, a comma-separated mailbox list, or
  a JSON list of mailbox strings.
- Every parsed address must use an allowed domain. A mixed value such as
  `outside@example.net, user@acme.com` is denied.
- Newlines, control characters, malformed separators, header-like text, empty
  addresses, address groups/comments, non-string list members, and ambiguous
  mailbox syntax are denied.
  Each comma-delimited segment must independently parse to one mailbox, which
  prevents parser differences with downstream mailers that split on commas.
- Dotted argument paths resolve nested JSON objects without evaluating
  attributes or user-controlled code.
- Domain comparison is case-insensitive, IDNA-normalized, and label-boundary
  aware. `evilacme.com` never matches `acme.com`.
- Subdomains are denied unless `allow_subdomains` is explicitly enabled.
- Missing recipients are denied by default. Set `require_recipient: false` only
  for operations where an empty recipient set is intentionally safe.
- Calls exceeding `max_recipients` are denied before tool execution.

Nonmatching tools and non-execution operations remain unaffected. Policy denial
reasons may include rejected domain names for operator diagnostics, but never
include full recipient addresses or message content.
