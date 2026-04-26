"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Chip, Divider, TextField, Typography } from "@mui/material";

type SessionSummary = {
  username?: string;
  role?: string;
  display_name?: string;
  expires_at?: string;
} | null;

type AccountActivityItem = {
  id: number;
  created_at: string;
  event_kind: string;
  title: string;
  detail?: string;
};

type SessionItem = {
  session_id: string;
  created_at?: string;
  expires_at?: string;
  revoked_at?: string | null;
  active?: boolean;
};

type ApiTokenItem = {
  token_id: string;
  name: string;
  token_hint?: string;
  created_at?: string;
  last_used_at?: string | null;
  revoked_at?: string | null;
  active?: boolean;
};

export function AccountSecurityPanel({
  authEnabled,
  session,
}: {
  authEnabled: boolean;
  session: SessionSummary;
}) {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activity, setActivity] = useState<AccountActivityItem[]>([]);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activityLoading, setActivityLoading] = useState(false);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState("");
  const [tokens, setTokens] = useState<ApiTokenItem[]>([]);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [tokenName, setTokenName] = useState("");
  const [createdToken, setCreatedToken] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadActivity() {
      if (!authEnabled || !session) {
        setActivity([]);
        return;
      }
      setActivityLoading(true);
      setActivityError(null);
      try {
        const response = await fetch("/api/me/activity?limit=6", { cache: "no-store" });
        const payload = (await response.json().catch(() => ({}))) as {
          items?: AccountActivityItem[];
          error?: string;
        };
        if (!response.ok) {
          throw new Error(payload.error ?? `Activity unavailable (${response.status})`);
        }
        if (!cancelled) setActivity(Array.isArray(payload.items) ? payload.items : []);
      } catch (err) {
        if (!cancelled) {
          setActivity([]);
          setActivityError(err instanceof Error ? err.message : "Could not load account activity.");
        }
      } finally {
        if (!cancelled) setActivityLoading(false);
      }
    }

    void loadActivity();
    return () => {
      cancelled = true;
    };
  }, [authEnabled, session]);

  useEffect(() => {
    let cancelled = false;
    async function loadSecurityState() {
      if (!authEnabled || !session) {
        setSessions([]);
        setTokens([]);
        return;
      }
      const [sessionResponse, tokenResponse] = await Promise.all([
        fetch("/api/me/sessions", { cache: "no-store" }),
        fetch("/api/me/tokens", { cache: "no-store" }),
      ]);
      const sessionPayload = (await sessionResponse.json().catch(() => ({}))) as {
        current_session_id?: string;
        items?: SessionItem[];
      };
      const tokenPayload = (await tokenResponse.json().catch(() => ({}))) as {
        items?: ApiTokenItem[];
      };
      if (!cancelled) {
        setCurrentSessionId(sessionPayload.current_session_id ?? "");
        setSessions(Array.isArray(sessionPayload.items) ? sessionPayload.items : []);
        setTokens(Array.isArray(tokenPayload.items) ? tokenPayload.items : []);
      }
    }

    void loadSecurityState();
    return () => {
      cancelled = true;
    };
  }, [authEnabled, session]);

  async function signOut() {
    setSigningOut(true);
    setError(null);
    try {
      const response = await fetch("/api/logout", { method: "POST" });
      if (!response.ok) {
        throw new Error(`Logout failed (${response.status})`);
      }
      router.push("/login");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign out.");
      setSigningOut(false);
    }
  }

  async function changePassword() {
    setError(null);
    setPasswordMessage(null);
    const response = await fetch("/api/me/password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    const payload = (await response.json().catch(() => ({}))) as { error?: string };
    if (!response.ok) {
      setError(payload.error ?? `Password change failed (${response.status})`);
      return;
    }
    setCurrentPassword("");
    setNewPassword("");
    setPasswordMessage("Password changed. Please sign in again with the new password.");
    router.push("/login");
    router.refresh();
  }

  async function createToken() {
    setError(null);
    setCreatedToken(null);
    const response = await fetch("/api/me/tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: tokenName }),
    });
    const payload = (await response.json().catch(() => ({}))) as {
      token?: string;
      token_record?: ApiTokenItem;
      error?: string;
    };
    if (!response.ok || !payload.token) {
      setError(payload.error ?? `Token creation failed (${response.status})`);
      return;
    }
    setCreatedToken(payload.token);
    setTokenName("");
    if (payload.token_record) setTokens((current) => [payload.token_record!, ...current]);
  }

  async function revokeToken(tokenId: string) {
    await fetch(`/api/me/tokens/${encodeURIComponent(tokenId)}`, { method: "DELETE" });
    setTokens((current) => current.map((token) => token.token_id === tokenId ? { ...token, active: false, revoked_at: new Date().toISOString() } : token));
  }

  async function revokeSession(sessionId: string) {
    await fetch(`/api/me/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
    setSessions((current) => current.map((item) => item.session_id === sessionId ? { ...item, active: false, revoked_at: new Date().toISOString() } : item));
    if (sessionId === currentSessionId) {
      router.push("/login");
      router.refresh();
    }
  }

  const displayName = session?.display_name ?? session?.username ?? "Guest";
  const roleLabel = session?.role ? titleCase(session.role) : authEnabled ? "Guest" : "Open local registry";

  return (
    <Card variant="outlined" component="section" sx={{ overflow: "hidden" }}>
      <CardContent sx={{ p: 0 }}>
        <Box
          sx={{
            p: { xs: 2, md: 2.5 },
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            justifyContent: "space-between",
            gap: 2,
          }}
        >
          <Box sx={{ display: "grid", gap: 0.6, maxWidth: 720 }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              Account security
            </Typography>
            <Typography sx={{ fontSize: 16, fontWeight: 850, color: "var(--app-fg)" }}>
              Password, sessions, and access keys
            </Typography>
            <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
              Current session details, password changes, API tokens, session revocation, and account activity are live.
            </Typography>
          </Box>
          <Chip
            label={authEnabled ? "Auth enabled" : "Auth disabled"}
            sx={{ alignSelf: { xs: "flex-start", md: "center" }, bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 800 }}
          />
        </Box>

        <Divider />

        <Box sx={{ p: { xs: 2, md: 2.5 }, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", lg: "1.1fr 0.9fr" } }}>
          <Box
            sx={{
              p: 2,
              borderRadius: 3,
              border: "1px solid var(--app-border)",
              bgcolor: "var(--app-control-bg)",
              display: "grid",
              gap: 1.5,
            }}
          >
            <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1.5 }}>
              <Box>
                <Typography sx={{ fontSize: 14, fontWeight: 850, color: "var(--app-fg)" }}>
                  Current browser session
                </Typography>
                <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
                  {authEnabled && !session ? "No signed-in registry user." : `${displayName} / ${roleLabel}`}
                </Typography>
              </Box>
              <Chip size="small" label="Available" sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 800 }} />
            </Box>

            <Box sx={{ display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              <SessionField label="Username" value={session?.username ?? (authEnabled ? "Not signed in" : "Local mode")} />
              <SessionField label="Role" value={roleLabel} />
              <SessionField label="Expires" value={formatExpiry(session?.expires_at)} />
              <SessionField label="Scope" value={authEnabled ? "Registry JWT cookie" : "Unauthenticated local access"} />
            </Box>

            <Box sx={{ p: 1.5, borderRadius: 2.5, bgcolor: "var(--app-surface)", border: "1px solid var(--app-border)" }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1.5, alignItems: "center" }}>
                <Typography sx={{ fontSize: 13, fontWeight: 850, color: "var(--app-fg)" }}>
                  Recent account activity
                </Typography>
                <Chip size="small" label="Server backed" sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontSize: 10, fontWeight: 800 }} />
              </Box>

              {activityError ? (
                <Alert severity="info" sx={{ mt: 1.25, borderRadius: 2 }}>
                  {activityError}
                </Alert>
              ) : null}

              {!activityError && activityLoading ? (
                <Typography sx={{ mt: 1.25, fontSize: 12, color: "var(--app-muted)" }}>
                  Loading account activity...
                </Typography>
              ) : null}

              {!activityError && !activityLoading && activity.length === 0 ? (
                <Typography sx={{ mt: 1.25, fontSize: 12, color: "var(--app-muted)" }}>
                  No activity recorded yet. Sign in or out to start the trail.
                </Typography>
              ) : null}

              {activity.length > 0 ? (
                <Box component="ul" sx={{ mt: 1.25, display: "grid", gap: 0.75, p: 0, m: 0, listStyle: "none" }}>
                  {activity.map((item) => (
                    <Box component="li" key={`${item.id}-${item.created_at}`} sx={{ display: "grid", gap: 0.25 }}>
                      <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                        {item.title}
                      </Typography>
                      <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                        {formatExpiry(item.created_at)}
                        {item.detail ? ` - ${item.detail}` : ""}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              ) : null}
            </Box>

            {error ? (
              <Typography sx={{ fontSize: 12, color: "#b91c1c" }}>{error}</Typography>
            ) : null}
            {passwordMessage ? (
              <Alert severity="success" sx={{ borderRadius: 2 }}>
                {passwordMessage}
              </Alert>
            ) : null}

            {authEnabled && session ? (
              <Box sx={{ p: 1.5, borderRadius: 2.5, bgcolor: "var(--app-surface)", border: "1px solid var(--app-border)", display: "grid", gap: 1.25 }}>
                <Typography sx={{ fontSize: 13, fontWeight: 850, color: "var(--app-fg)" }}>
                  Change password
                </Typography>
                <Box sx={{ display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                  <TextField
                    label="Current password"
                    type="password"
                    size="small"
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                  />
                  <TextField
                    label="New password"
                    type="password"
                    size="small"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                  />
                </Box>
                <Button
                  variant="outlined"
                  onClick={() => void changePassword()}
                  disabled={!currentPassword || newPassword.length < 8}
                  sx={{ justifySelf: "start" }}
                >
                  Update password
                </Button>
              </Box>
            ) : null}

            {authEnabled && session ? (
              <Box sx={{ p: 1.5, borderRadius: 2.5, bgcolor: "var(--app-surface)", border: "1px solid var(--app-border)", display: "grid", gap: 1.25 }}>
                <Typography sx={{ fontSize: 13, fontWeight: 850, color: "var(--app-fg)" }}>
                  Active sessions
                </Typography>
                {sessions.length === 0 ? (
                  <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                    No tracked sessions yet.
                  </Typography>
                ) : (
                  <Box component="ul" sx={{ display: "grid", gap: 0.75, p: 0, m: 0, listStyle: "none" }}>
                    {sessions.slice(0, 5).map((item) => (
                      <Box component="li" key={item.session_id} sx={{ display: "flex", justifyContent: "space-between", gap: 1.5 }}>
                        <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                          {item.session_id === currentSessionId ? "Current session" : "Registry session"} / {item.active ? "active" : "revoked"}
                        </Typography>
                        {item.active ? (
                          <Button size="small" variant="text" onClick={() => void revokeSession(item.session_id)}>
                            Revoke
                          </Button>
                        ) : null}
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>
            ) : null}

            {authEnabled && session ? (
              <Box sx={{ p: 1.5, borderRadius: 2.5, bgcolor: "var(--app-surface)", border: "1px solid var(--app-border)", display: "grid", gap: 1.25 }}>
                <Typography sx={{ fontSize: 13, fontWeight: 850, color: "var(--app-fg)" }}>
                  Personal API tokens
                </Typography>
                <Box sx={{ display: "flex", gap: 1, flexDirection: { xs: "column", sm: "row" } }}>
                  <TextField
                    label="Token name"
                    size="small"
                    value={tokenName}
                    onChange={(event) => setTokenName(event.target.value)}
                    sx={{ flex: 1 }}
                  />
                  <Button variant="outlined" onClick={() => void createToken()}>
                    Create token
                  </Button>
                </Box>
                {createdToken ? (
                  <Alert severity="success" sx={{ borderRadius: 2 }}>
                    Copy this token now. It will not be shown again: <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", wordBreak: "break-all" }}>{createdToken}</Box>
                  </Alert>
                ) : null}
                {tokens.length === 0 ? (
                  <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                    No personal API tokens yet.
                  </Typography>
                ) : (
                  <Box component="ul" sx={{ display: "grid", gap: 0.75, p: 0, m: 0, listStyle: "none" }}>
                    {tokens.slice(0, 5).map((token) => (
                      <Box component="li" key={token.token_id} sx={{ display: "flex", justifyContent: "space-between", gap: 1.5 }}>
                        <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                          {token.name} / {token.active ? token.token_hint : "revoked"}
                        </Typography>
                        {token.active ? (
                          <Button size="small" variant="text" onClick={() => void revokeToken(token.token_id)}>
                            Revoke
                          </Button>
                        ) : null}
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>
            ) : null}

            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              {authEnabled && session ? (
                <Button variant="contained" onClick={signOut} disabled={signingOut}>
                  {signingOut ? "Signing out..." : "Sign out current session"}
                </Button>
              ) : (
                <Button variant="outlined" onClick={() => router.push("/login")}>
                  Sign in
                </Button>
              )}
            </Box>
          </Box>

          <Box sx={{ display: "grid", gap: 1.25 }}>
            <SecurityCapability title="Change password" reason="Passwords are stored as PBKDF2 hashes in the registry account store." status="Available" />
            <SecurityCapability title="Password reset" reason="Users can change known passwords now. Email-style reset delivery is still future work." status="Partly available" />
            <SecurityCapability title="Active sessions" reason="JWT sessions are tracked server-side and can be revoked from settings." status="Available" />
            <SecurityCapability title="Personal API tokens" reason="Tokens are shown once, stored hashed, and can be revoked." status="Available" />
            <SecurityCapability title="Notification preferences" reason="In-app notification preferences are server-synced. Email delivery choices still need delivery-channel support." status="Partly available" />
            <SecurityCapability title="Audit activity" reason="Login and logout activity is now persisted for the current registry account." status="Available" />
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

function SessionField({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ p: 1.25, borderRadius: 2.5, bgcolor: "var(--app-surface)", border: "1px solid var(--app-border)" }}>
      <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--app-muted)" }}>
        {label}
      </Typography>
      <Typography sx={{ mt: 0.5, fontSize: 12, fontWeight: 700, color: "var(--app-fg)", wordBreak: "break-word" }}>
        {value}
      </Typography>
    </Box>
  );
}

function SecurityCapability({
  title,
  reason,
  status = "Backend required",
}: {
  title: string;
  reason: string;
  status?: string;
}) {
  return (
    <Box sx={{ p: 1.5, borderRadius: 2.5, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)" }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1.5 }}>
        <Typography sx={{ fontSize: 13, fontWeight: 850, color: "var(--app-fg)" }}>
          {title}
        </Typography>
        <Chip size="small" label={status} sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontSize: 10, fontWeight: 800 }} />
      </Box>
      <Typography sx={{ mt: 0.75, fontSize: 12, lineHeight: 1.55, color: "var(--app-muted)" }}>
        {reason}
      </Typography>
    </Box>
  );
}

function formatExpiry(value?: string) {
  if (!value) return "No expiry reported";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function titleCase(value: string) {
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
