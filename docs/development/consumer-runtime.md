# Consumer runtime iteration 1

Enable `PURECIPHER_CONSUMER_RUNTIME_ENABLED=true` to register the five Google read-only integrations and Brave web search in the registry's existing SecureMCP stack. These tools require an active profile, an assigned client token, a published/verified matching listing, and a selected owner-matched product connection. The profile middleware supplies credentials in a context variable for the duration of the call and always resets it. Credentials are never put in a global environment or tool arguments. Existing consent, contract, policy, provenance and reflexive checks remain in place.

Brave connections use the consumer's encrypted `BRAVE_API_KEY`. POST `/registry/workspace/connections/{id}/verify` performs one Web Search API request (potentially billable to that account) and binds successful verification to the current settings. Changing credentials invalidates verification. Disconnect invalidates authorization immediately for new calls.

Google OAuth uses the publisher's application identity to obtain separate end-user grants. Configure:

- `PURECIPHER_GOOGLE_CLIENT_ID`: the Google Web application client ID.
- `PURECIPHER_GOOGLE_CLIENT_SECRET_FILE`: a private, mounted file containing the app secret. The inline environment alternative is supported for controlled deployments.
- `PURECIPHER_CONSUMER_OAUTH_REDIRECT_URI=https://registry.purecipher.com/api/workspace/oauth/callback`: register this exact redirect with Google.

Enable Gmail, Google Docs, Google Drive, Google Calendar and Google Tasks APIs in that application's Cloud project. End users choose their own Google account and grant only the product's requested read scope. OAuth grants and refresh tokens are encrypted under the owner-bound connection record. Authorization uses random, expiring, single-use state and PKCE; callbacks require the initiating owner session. A changed connection invalidates an in-flight authorization. Refresh writes use revision checks so disconnection wins over an in-flight refresh. Multiple workers can race refresh and return a retryable failure; no stale grant overwrites a newer revision.

POST `.../{id}/authorize` returns the Google authorization URL. GET `/registry/workspace/oauth/callback` handles the response and redirects to My connections without returning credentials. POST `.../{id}/disconnect` removes the registry's local grant/verification; it does not revoke the user's entire Google application consent. Configure ingress access logs to omit OAuth callback query strings. Google app configuration and real account authorization remain operator/user steps; fixture tests do not claim live provider validation.

The other 42 product templates still have no consumer runtime. They remain explicitly unavailable for activation. Published runtime listings retain `live_tested=false` until a user's authorization/verification is ready; profile readiness checks that individual connection rather than assuming shared publisher authorization. Published runtime definitions describe the actual registered tools, not an external MCP endpoint inspection.
