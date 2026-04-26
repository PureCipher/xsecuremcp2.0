"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from "@mui/material";

type RegistryAccount = {
  username: string;
  role: string;
  display_name: string;
  source?: string;
  created_at?: string;
  updated_at?: string;
  disabled_at?: string | null;
  active?: boolean;
};

type UsersResponse = {
  users?: RegistryAccount[];
  roles?: string[];
  counts?: Record<string, number>;
  error?: string;
};

const DEFAULT_ROLES = ["viewer", "publisher", "reviewer", "admin"];

export function UserRoleManagementPanel() {
  const [users, setUsers] = useState<RegistryAccount[]>([]);
  const [roles, setRoles] = useState<string[]>(DEFAULT_ROLES);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [form, setForm] = useState({
    username: "",
    displayName: "",
    role: "publisher",
    password: "",
  });
  const [passwords, setPasswords] = useState<Record<string, string>>({});

  async function loadUsers() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/admin/users", { cache: "no-store" });
      const payload = (await response.json().catch(() => ({}))) as UsersResponse;
      if (!response.ok) {
        throw new Error(payload.error ?? `Users unavailable (${response.status})`);
      }
      setUsers(Array.isArray(payload.users) ? payload.users : []);
      setRoles(Array.isArray(payload.roles) && payload.roles.length ? payload.roles : DEFAULT_ROLES);
      setCounts(payload.counts ?? {});
    } catch (err) {
      setUsers([]);
      setError(err instanceof Error ? err.message : "Could not load users.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadUsers();
  }, []);

  const activeAdmins = useMemo(
    () => users.filter((user) => user.role === "admin" && user.active !== false).length,
    [users],
  );

  async function createUser() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch("/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: form.username,
          display_name: form.displayName,
          role: form.role,
          password: form.password,
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as UsersResponse & {
        user?: RegistryAccount;
      };
      if (!response.ok || !payload.user) {
        throw new Error(payload.error ?? `Create failed (${response.status})`);
      }
      setForm({ username: "", displayName: "", role: "publisher", password: "" });
      setMessage(`Created ${payload.user.username}.`);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create user.");
    } finally {
      setSaving(false);
    }
  }

  async function updateUser(username: string, body: Record<string, unknown>) {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch(`/api/admin/users/${encodeURIComponent(username)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await response.json().catch(() => ({}))) as UsersResponse & {
        user?: RegistryAccount;
      };
      if (!response.ok || !payload.user) {
        throw new Error(payload.error ?? `Update failed (${response.status})`);
      }
      setMessage(`Updated ${username}.`);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update user.");
    } finally {
      setSaving(false);
    }
  }

  async function resetPassword(username: string) {
    const newPassword = passwords[username] ?? "";
    if (newPassword.length < 8) {
      setError("Password resets require at least 8 characters.");
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch(`/api/admin/users/${encodeURIComponent(username)}/password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: newPassword }),
      });
      const payload = (await response.json().catch(() => ({}))) as { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? `Password reset failed (${response.status})`);
      }
      setPasswords((current) => ({ ...current, [username]: "" }));
      setMessage(`Password reset for ${username}; existing sessions and tokens were revoked.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset password.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card variant="outlined" component="section" sx={{ overflow: "hidden" }}>
      <CardContent sx={{ p: 0 }}>
        <Box sx={{ p: { xs: 2.5, md: 3 }, display: "flex", flexDirection: { xs: "column", md: "row" }, justifyContent: "space-between", gap: 2 }}>
          <Box sx={{ display: "grid", gap: 0.75, maxWidth: 780 }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              Admin console
            </Typography>
            <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
              Users and role management
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              Create publisher, reviewer, viewer, and admin accounts; change roles; disable access; and reset passwords.
            </Typography>
          </Box>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignSelf: { xs: "flex-start", md: "center" } }}>
            <Chip label={`${counts.active ?? 0} active`} sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 800 }} />
            <Chip label={`${activeAdmins} admins`} sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 800 }} />
          </Box>
        </Box>

        <Divider />

        <Box sx={{ p: { xs: 2, md: 2.5 }, display: "grid", gap: 2 }}>
          {error ? <Alert severity="error">{error}</Alert> : null}
          {message ? <Alert severity="success">{message}</Alert> : null}

          <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr 160px 1fr auto" }, alignItems: "center" }}>
            <TextField label="Username" size="small" value={form.username} onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))} />
            <TextField label="Display name" size="small" value={form.displayName} onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))} />
            <FormControl size="small">
              <InputLabel id="new-user-role-label">Role</InputLabel>
              <Select labelId="new-user-role-label" label="Role" value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value }))}>
                {roles.map((role) => (
                  <MenuItem key={role} value={role}>
                    {titleCase(role)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField label="Temporary password" type="password" size="small" value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} />
            <Button variant="contained" disabled={saving || !form.username || form.password.length < 8} onClick={() => void createUser()}>
              Create user
            </Button>
          </Box>

          {loading ? (
            <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
              Loading users...
            </Typography>
          ) : null}

          {!loading && users.length === 0 ? (
            <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
              No registry accounts found.
            </Typography>
          ) : null}

          <Box sx={{ display: "grid", gap: 1.25 }}>
            {users.map((user) => (
              <Box key={user.username} sx={{ p: 1.5, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)", display: "grid", gap: 1.25 }}>
                <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1.5 }}>
                  <Box>
                    <Typography sx={{ fontSize: 14, fontWeight: 850, color: "var(--app-fg)" }}>
                      {user.display_name || user.username}
                    </Typography>
                    <Typography sx={{ mt: 0.35, fontSize: 12, color: "var(--app-muted)" }}>
                      {user.username} / {user.source ?? "local"} / {user.active === false ? "disabled" : "active"}
                    </Typography>
                  </Box>
                  <Chip size="small" label={titleCase(user.role)} sx={{ bgcolor: user.role === "admin" ? "var(--app-control-active-bg)" : "var(--app-surface)", color: "var(--app-muted)", fontWeight: 800 }} />
                </Box>

                <Box sx={{ display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", md: "1fr 160px auto auto" }, alignItems: "center" }}>
                  <TextField
                    label="Display name"
                    size="small"
                    defaultValue={user.display_name}
                    onBlur={(event) => {
                      if (event.target.value !== user.display_name) void updateUser(user.username, { display_name: event.target.value });
                    }}
                  />
                  <FormControl size="small">
                    <InputLabel id={`${user.username}-role-label`}>Role</InputLabel>
                    <Select
                      labelId={`${user.username}-role-label`}
                      label="Role"
                      value={user.role}
                      disabled={saving || user.active === false}
                      onChange={(event) => void updateUser(user.username, { role: event.target.value })}
                    >
                      {roles.map((role) => (
                        <MenuItem key={role} value={role}>
                          {titleCase(role)}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <Button variant="outlined" disabled={saving} onClick={() => void updateUser(user.username, { disabled: user.active !== false })}>
                    {user.active === false ? "Enable" : "Disable"}
                  </Button>
                  <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                    Updated {formatDate(user.updated_at)}
                  </Typography>
                </Box>

                <Box sx={{ display: "flex", gap: 1, flexDirection: { xs: "column", sm: "row" }, alignItems: { xs: "stretch", sm: "center" } }}>
                  <TextField
                    label="New password"
                    type="password"
                    size="small"
                    value={passwords[user.username] ?? ""}
                    onChange={(event) => setPasswords((current) => ({ ...current, [user.username]: event.target.value }))}
                    sx={{ flex: 1 }}
                  />
                  <Button variant="outlined" disabled={saving || (passwords[user.username] ?? "").length < 8} onClick={() => void resetPassword(user.username)}>
                    Reset password
                  </Button>
                </Box>
              </Box>
            ))}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

function titleCase(value: string) {
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDate(value?: string) {
  if (!value) return "never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}
