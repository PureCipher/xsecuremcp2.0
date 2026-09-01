# PR for xregistry — listing detail crashes when registry auth is disabled

> This file lives in the xsecuremcp2.0 demo folder for convenience, but the change
> it describes belongs to the **xregistry** repo. Use the commands at the bottom to
> branch, commit, and open the PR there.

## Suggested branch
`fix/listing-detail-auth-disabled`

## Suggested commit message
```
Fix listing detail 404/500 when registry auth is disabled

🤖 Generated with Claude Code
```

## PR title
`Fix listing detail page when registry auth is disabled`

## PR body

When the backend runs with auth disabled (`PURECIPHER_ENABLE_AUTH=false`), `/registry/session`
returns `auth_enabled: false` and `session: null`. The listing detail page treated a null
session as unauthenticated and bailed with `notFound()`, so **every** `/registry/listings/<name>`
page returned 404 even though the catalog list rendered fine. Removing that early return surfaced
a second crash: the page later read `sessionPayload.session.can_admin` directly, throwing
`Cannot read properties of null (reading 'can_admin')` (HTTP 500).

This gates the session requirement on `auth_enabled` (the layout already redirects to login for
the auth-on, unauthenticated case) and reads `can_admin` defensively. Detail pages now render in
both auth modes; the deregister control still only appears for admins.

```tsx
// before
const sessionPayload = await getRegistrySession();
if (!sessionPayload?.session) {
  return notFound();
}
// ...
const canAdmin = sessionPayload.session.can_admin === true;

// after
const sessionPayload = await getRegistrySession();
// Only require a session when auth is actually enabled.
if (sessionPayload?.auth_enabled && !sessionPayload.session) {
  return notFound();
}
// ...
const canAdmin = sessionPayload?.session?.can_admin === true;
```

Files changed: `src/app/registry/listings/[toolName]/page.tsx`

---

## Commands (run on your machine, where git works)

```bash
cd path/to/xregistry
git checkout -b fix/listing-detail-auth-disabled
git add "src/app/registry/listings/[toolName]/page.tsx"
git commit -m "Fix listing detail 404/500 when registry auth is disabled

🤖 Generated with Claude Code"
git push -u origin fix/listing-detail-auth-disabled

# then open the PR (gh CLI), or use the compare URL git prints:
gh pr create --title "Fix listing detail page when registry auth is disabled" \
  --body-file demo/xregistry_PR_listing_detail_fix.md   # trim to the PR body section
# or: https://github.com/PureCipher/xregistry/compare/fix/listing-detail-auth-disabled?expand=1
```
