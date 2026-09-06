# Consumer-owned product connections

`/registry/profiles` → **My connections** offers 48 product-specific consumer setup definitions. Definitions come from the prepared adapters and the referenced upstream catalog specifications. Definitions are setup templates, not a claim that a server is deployed.

A connection belongs to the authenticated end user, not the publisher. The publisher still owns its listing and OAuth application configuration. OAuth consumers must not supply publisher app IDs or app secrets. API-key products collect the consumer's own credentials.

## Storage and access

The existing PostgreSQL workspace table stores `product_connection` records. All settings are Fernet-encrypted using a domain-separated key derived from the registry signing key; decrypted content binds owner, product and record ID. Losing/changing the signing key makes existing credentials unreadable. Back up that key separately from the database.

Authenticated GET/POST `/registry/workspace/connections` and owner-only PUT/DELETE `/registry/workspace/connections/{id}` expose redacted values and credential-presence flags, never secret values. Empty secret fields preserve stored values. `clear_secrets` explicitly removes them. Revisions reject stale writes. Public listing metadata, generic profiles, and publishers cannot read the encrypted connection material.

Profiles may choose `connection_id` for a selected server. The backend checks owner and exact product association; only the PureCipher product listing can use its corresponding definition. Removing a connection invalidates that selection. Assigned clients will be the scope of use once runtime support exists.

## Deliberate readiness boundary

Saved settings are not forwarded to upstream runtimes yet. Profiles with these connections remain blocked rather than falling back to shared publisher credentials. OAuth connections remain `authorization_pending`. Other connections report `settings_saved` or `settings_incomplete`, never connected or tested. Completing per-user runtime credential injection and OAuth delegation is required before these preparation adapters can operate through profiles. Secrets are never injected into process-wide environment variables.
