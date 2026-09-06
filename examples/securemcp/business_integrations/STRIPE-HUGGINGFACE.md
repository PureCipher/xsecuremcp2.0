# Stripe and Hugging Face — authorization pending

Both packages use SecureMCP 2.0 policy, consent, provenance, Reflexive controls and
pre-execution gating. They are read-only preparation drafts, not running endpoints.
The durable storage, enrollment and live-validation gates in README.md still apply.

## Stripe Apps OAuth

Use a Stripe App configured for OAuth, with allowed HTTPS redirect URI
`<PURECIPHER_STRIPE_BASE_URL>/auth/callback`. Configure these **read** permissions:
`connected_account_read`, `balance_read`, `payment_intent_read`, `invoice_read`.
Registering/testing/distributing the Stripe App is a separate provider setup step.
The old Stripe Connect `read_only` extension flow is not used.

Set `PURECIPHER_STRIPE_CLIENT_ID`, `PURECIPHER_STRIPE_DEVELOPER_KEY`, and
`PURECIPHER_STRIPE_BASE_URL` using secret storage. The developer credential is used
only for token exchange/refresh, with Stripe's API-key-as-Basic-username format.
Provider data requests use the authorized user's access token. OAuth scopes come
from the stored token response (`stripe_apps`); granular permissions are enforced
by the Stripe App configuration. Start with Stripe test mode during live validation.

Tools read balances, payment-intent summaries and invoice summaries. No writes,
refunds, charges, transfers, customer contact fields, hosted invoice URLs, or
payment client secrets are returned. List requests support bounded pagination.

Run `python -m examples.securemcp.business_integrations.stripe_server` after setup;
preparation port 9117, loopback only. Do not route publicly before acceptance gates.

## Hugging Face

Create an OAuth app and set `PURECIPHER_HF_CLIENT_ID`,
`PURECIPHER_HF_CLIENT_SECRET`, `PURECIPHER_HF_BASE_URL`. Callback is
`<base>/auth/callback`; requested scopes are `openid profile read-repos`.
The native Hugging Face OAuth provider validates identity and stores granted
scopes. Provider authorization remains deferred.

Tools search/read model and dataset metadata. No inference, repository mutation,
model execution, or content download endpoints are exposed. Repository paths and
pagination limits are validated; provider credentials never follow redirects.

Run `python -m examples.securemcp.business_integrations.huggingface_server` after
setup; preparation port 9118, loopback only.

## Official references

- https://docs.stripe.com/stripe-apps/api-authentication/oauth
- https://docs.stripe.com/stripe-apps/reference/permissions
- https://docs.stripe.com/api/balance/balance_retrieve
- https://docs.stripe.com/api/payment_intents/list
- https://docs.stripe.com/api/invoices/list
- https://huggingface.co/docs/hub/oauth
- https://huggingface.co/docs/hub/api
