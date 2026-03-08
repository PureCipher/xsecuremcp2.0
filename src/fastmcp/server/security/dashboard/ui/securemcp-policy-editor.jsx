import { useState, useEffect, useCallback } from "react";
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Shield, Plus, Trash2, Play, Eye, ChevronDown, ChevronRight, AlertTriangle, CheckCircle, XCircle, Clock, Search, Filter, Download, RefreshCw, Settings, FileText, Layers, Lock, Unlock } from "lucide-react";

// ── Demo Data ─────────────────────────────────────────────────────

const DEMO_PROVIDERS = [
  { type: "AllowlistPolicy", policy_id: "allowlist-prod", version: "1.2.0" },
  { type: "DenylistPolicy", policy_id: "denylist-blocked", version: "1.0.0" },
  { type: "RoleBasedPolicy", policy_id: "rbac-main", version: "2.1.0" },
  { type: "RateLimitPolicy", policy_id: "rate-limit-default", version: "1.0.0" },
];

const DEMO_AUDIT_ENTRIES = [
  { actor_id: "agent-1", action: "call_tool", resource_id: "weather-lookup", decision: "allow", reason: "Matched allowlist pattern 'weather-*'", policy_id: "allowlist-prod", timestamp: "2026-03-08T10:30:00Z", elapsed_ms: 0.4 },
  { actor_id: "agent-2", action: "call_tool", resource_id: "admin-panel", decision: "deny", reason: "Resource in denylist", policy_id: "denylist-blocked", timestamp: "2026-03-08T10:29:55Z", elapsed_ms: 0.2 },
  { actor_id: "agent-1", action: "read_resource", resource_id: "config://db", decision: "allow", reason: "Role 'operator' has read access", policy_id: "rbac-main", timestamp: "2026-03-08T10:29:50Z", elapsed_ms: 0.6 },
  { actor_id: "agent-3", action: "call_tool", resource_id: "data-export", decision: "deny", reason: "Rate limit exceeded (5/min)", policy_id: "rate-limit-default", timestamp: "2026-03-08T10:29:45Z", elapsed_ms: 0.1 },
  { actor_id: "agent-1", action: "call_tool", resource_id: "file-reader", decision: "allow", reason: "Matched allowlist pattern 'file-*'", policy_id: "allowlist-prod", timestamp: "2026-03-08T10:29:40Z", elapsed_ms: 0.3 },
  { actor_id: "agent-2", action: "get_prompt", resource_id: "system-prompt", decision: "deny", reason: "Resource in denylist", policy_id: "denylist-blocked", timestamp: "2026-03-08T10:29:35Z", elapsed_ms: 0.2 },
];

const DEMO_STATS = {
  entries_in_log: 1247,
  total_recorded: 5832,
  total_allowed: 4589,
  total_denied: 1243,
  current_allow: 823,
  current_deny: 389,
  current_defer: 35,
  unique_actors: 12,
  unique_resources: 67,
  deny_rate: 0.312,
  top_denied_resources: [
    { resource_id: "admin-panel", count: 142 },
    { resource_id: "data-export", count: 89 },
    { resource_id: "system-config", count: 67 },
    { resource_id: "file-writer", count: 45 },
    { resource_id: "network-scan", count: 31 },
  ],
};

const DEMO_SIMULATION_RESULT = {
  total: 4,
  allowed: 2,
  denied: 2,
  results: [
    { resource_id: "safe-tool", decision: "allow", reason: "Matched allowlist", label: "Safe tool access" },
    { resource_id: "admin-panel", decision: "deny", reason: "In denylist", label: "Admin access attempt" },
    { resource_id: "weather-api", decision: "allow", reason: "Matched allowlist pattern", label: "Weather API" },
    { resource_id: "blocked-tool", decision: "deny", reason: "Matched deny pattern 'blocked-*'", label: "Blocked tool" },
  ],
};

const DEMO_SCHEMA = {
  policy_types: [
    { type: "allowlist", description: "Allow specific resources by pattern", fields: ["allowed"] },
    { type: "denylist", description: "Deny specific resources by pattern", fields: ["denied"] },
    { type: "role_based", description: "Role-based access control", fields: ["role_permissions"] },
    { type: "rate_limit", description: "Rate limiting per actor", fields: ["max_requests", "window_seconds"] },
    { type: "time_based", description: "Time-window access control", fields: ["allowed_hours_start", "allowed_hours_end"] },
    { type: "attribute_based", description: "Attribute-based access control", fields: ["metadata_conditions"] },
    { type: "resource_scoped", description: "Per-resource policy mapping", fields: ["policies"] },
  ],
  compositions: ["all_of", "any_of", "first_match", "not"],
};

// ── Color palette ──────────────────────────────────────────────────

const COLORS = {
  allow: "#10b981",
  deny: "#ef4444",
  defer: "#f59e0b",
  primary: "#6366f1",
  secondary: "#8b5cf6",
  bg: "#0f172a",
  card: "#1e293b",
  cardHover: "#334155",
  border: "#334155",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  textDim: "#64748b",
};

// ── Utility Components ─────────────────────────────────────────────

const Badge = ({ children, color = COLORS.primary, small = false }) => (
  <span style={{
    display: "inline-flex", alignItems: "center", gap: 4,
    padding: small ? "1px 6px" : "2px 8px",
    borderRadius: 9999,
    fontSize: small ? 10 : 11,
    fontWeight: 600,
    background: `${color}22`,
    color: color,
    border: `1px solid ${color}44`,
  }}>{children}</span>
);

const Card = ({ children, style = {} }) => (
  <div style={{
    background: COLORS.card,
    borderRadius: 12,
    border: `1px solid ${COLORS.border}`,
    padding: 20,
    ...style,
  }}>{children}</div>
);

const Button = ({ children, onClick, variant = "primary", small = false, disabled = false, icon: Icon }) => {
  const variants = {
    primary: { bg: COLORS.primary, color: "#fff" },
    danger: { bg: COLORS.deny, color: "#fff" },
    ghost: { bg: "transparent", color: COLORS.textMuted, border: `1px solid ${COLORS.border}` },
    success: { bg: COLORS.allow, color: "#fff" },
  };
  const v = variants[variant] || variants.primary;
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: small ? "4px 10px" : "8px 16px",
        borderRadius: 8,
        fontSize: small ? 12 : 13,
        fontWeight: 600,
        background: v.bg,
        color: v.color,
        border: v.border || "none",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "all 0.15s ease",
      }}
    >
      {Icon && <Icon size={small ? 12 : 14} />}
      {children}
    </button>
  );
};

const SectionHeader = ({ icon: Icon, title, subtitle, action }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      {Icon && <Icon size={18} style={{ color: COLORS.primary }} />}
      <div>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: COLORS.text }}>{title}</h3>
        {subtitle && <p style={{ margin: "2px 0 0", fontSize: 12, color: COLORS.textMuted }}>{subtitle}</p>}
      </div>
    </div>
    {action}
  </div>
);

// ── Tab Navigation ─────────────────────────────────────────────────

const TabNav = ({ tabs, active, onChange }) => (
  <div style={{ display: "flex", gap: 2, background: COLORS.bg, borderRadius: 10, padding: 3, marginBottom: 20 }}>
    {tabs.map(t => (
      <button
        key={t.id}
        onClick={() => onChange(t.id)}
        style={{
          flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          padding: "8px 16px", borderRadius: 8, border: "none", cursor: "pointer",
          fontSize: 13, fontWeight: 600, transition: "all 0.15s ease",
          background: active === t.id ? COLORS.primary : "transparent",
          color: active === t.id ? "#fff" : COLORS.textMuted,
        }}
      >
        {t.icon && <t.icon size={14} />}
        {t.label}
      </button>
    ))}
  </div>
);

// ── Provider List ──────────────────────────────────────────────────

const ProviderList = ({ providers, onRemove }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
    {providers.map((p, i) => (
      <div key={i} style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "12px 16px", borderRadius: 8, background: COLORS.bg,
        border: `1px solid ${COLORS.border}`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
            background: `${COLORS.primary}22`, color: COLORS.primary,
          }}>
            <Shield size={16} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: COLORS.text }}>{p.type}</div>
            <div style={{ fontSize: 11, color: COLORS.textMuted }}>{p.policy_id || "auto"}</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Badge small>{`v${p.version || "1.0"}`}</Badge>
          <button onClick={() => onRemove(i)} style={{
            background: "none", border: "none", cursor: "pointer", color: COLORS.textDim,
            padding: 4, borderRadius: 4,
          }}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    ))}
    {providers.length === 0 && (
      <div style={{ padding: 24, textAlign: "center", color: COLORS.textDim, fontSize: 13 }}>
        No policy providers configured. Add one to get started.
      </div>
    )}
  </div>
);

// ── Policy Builder ─────────────────────────────────────────────────

const PolicyBuilder = ({ schema, onAdd }) => {
  const [selectedType, setSelectedType] = useState("");
  const [policyId, setPolicyId] = useState("");
  const [patterns, setPatterns] = useState("");
  const [expanded, setExpanded] = useState(false);

  const handleAdd = () => {
    if (!selectedType) return;
    const policy = {
      type: selectedType,
      policy_id: policyId || `${selectedType}-${Date.now()}`,
    };
    if (selectedType === "allowlist") {
      policy.allowed = patterns.split(",").map(s => s.trim()).filter(Boolean);
    } else if (selectedType === "denylist") {
      policy.denied = patterns.split(",").map(s => s.trim()).filter(Boolean);
    }
    onAdd(policy);
    setSelectedType("");
    setPolicyId("");
    setPatterns("");
    setExpanded(false);
  };

  if (!expanded) {
    return (
      <Button onClick={() => setExpanded(true)} variant="ghost" icon={Plus}>
        Add Policy Provider
      </Button>
    );
  }

  return (
    <Card style={{ background: COLORS.bg, border: `1px solid ${COLORS.primary}44` }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: COLORS.text }}>Add Policy Provider</div>
        <select
          value={selectedType}
          onChange={e => setSelectedType(e.target.value)}
          style={{
            padding: "8px 12px", borderRadius: 8, border: `1px solid ${COLORS.border}`,
            background: COLORS.card, color: COLORS.text, fontSize: 13,
          }}
        >
          <option value="">Select policy type...</option>
          {(schema?.policy_types || DEMO_SCHEMA.policy_types).map(t => (
            <option key={t.type} value={t.type}>{t.type} — {t.description}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Policy ID (optional)"
          value={policyId}
          onChange={e => setPolicyId(e.target.value)}
          style={{
            padding: "8px 12px", borderRadius: 8, border: `1px solid ${COLORS.border}`,
            background: COLORS.card, color: COLORS.text, fontSize: 13,
          }}
        />
        {(selectedType === "allowlist" || selectedType === "denylist") && (
          <input
            type="text"
            placeholder="Patterns (comma-separated, e.g. safe-*, weather-*)"
            value={patterns}
            onChange={e => setPatterns(e.target.value)}
            style={{
              padding: "8px 12px", borderRadius: 8, border: `1px solid ${COLORS.border}`,
              background: COLORS.card, color: COLORS.text, fontSize: 13,
            }}
          />
        )}
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={handleAdd} icon={Plus} disabled={!selectedType}>Add</Button>
          <Button onClick={() => setExpanded(false)} variant="ghost">Cancel</Button>
        </div>
      </div>
    </Card>
  );
};

// ── Audit Log Table ────────────────────────────────────────────────

const AuditTable = ({ entries, onFilter }) => {
  const [filter, setFilter] = useState("");

  const filtered = entries.filter(e =>
    !filter || e.resource_id.includes(filter) || e.actor_id?.includes(filter) || e.decision.includes(filter)
  );

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <div style={{ flex: 1, position: "relative" }}>
          <Search size={14} style={{ position: "absolute", left: 10, top: 10, color: COLORS.textDim }} />
          <input
            type="text"
            placeholder="Filter by resource, actor, or decision..."
            value={filter}
            onChange={e => setFilter(e.target.value)}
            style={{
              width: "100%", padding: "8px 12px 8px 32px", borderRadius: 8,
              border: `1px solid ${COLORS.border}`, background: COLORS.bg,
              color: COLORS.text, fontSize: 12, boxSizing: "border-box",
            }}
          />
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${COLORS.border}` }}>
              {["Decision", "Actor", "Action", "Resource", "Reason", "Policy", "Time"].map(h => (
                <th key={h} style={{ padding: "8px 10px", textAlign: "left", color: COLORS.textDim, fontWeight: 600, fontSize: 11 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 20).map((e, i) => (
              <tr key={i} style={{ borderBottom: `1px solid ${COLORS.border}22` }}>
                <td style={{ padding: "8px 10px" }}>
                  <Badge color={e.decision === "allow" ? COLORS.allow : e.decision === "deny" ? COLORS.deny : COLORS.defer} small>
                    {e.decision === "allow" ? <CheckCircle size={10} /> : e.decision === "deny" ? <XCircle size={10} /> : <Clock size={10} />}
                    {e.decision.toUpperCase()}
                  </Badge>
                </td>
                <td style={{ padding: "8px 10px", color: COLORS.text, fontFamily: "monospace", fontSize: 11 }}>{e.actor_id || "—"}</td>
                <td style={{ padding: "8px 10px", color: COLORS.textMuted }}>{e.action}</td>
                <td style={{ padding: "8px 10px", color: COLORS.text, fontFamily: "monospace", fontSize: 11 }}>{e.resource_id}</td>
                <td style={{ padding: "8px 10px", color: COLORS.textMuted, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.reason}</td>
                <td style={{ padding: "8px 10px", color: COLORS.textDim, fontSize: 11 }}>{e.policy_id}</td>
                <td style={{ padding: "8px 10px", color: COLORS.textDim, fontSize: 11, whiteSpace: "nowrap" }}>
                  {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length === 0 && (
        <div style={{ padding: 24, textAlign: "center", color: COLORS.textDim, fontSize: 13 }}>
          No audit entries match your filter.
        </div>
      )}
    </div>
  );
};

// ── Simulation Panel ───────────────────────────────────────────────

const SimulationPanel = ({ onSimulate, result }) => {
  const [scenarios, setScenarios] = useState([
    { resource_id: "", action: "call_tool", actor_id: "sim-actor", label: "" },
  ]);

  const addScenario = () => {
    setScenarios([...scenarios, { resource_id: "", action: "call_tool", actor_id: "sim-actor", label: "" }]);
  };

  const removeScenario = (idx) => {
    setScenarios(scenarios.filter((_, i) => i !== idx));
  };

  const updateScenario = (idx, field, value) => {
    const updated = [...scenarios];
    updated[idx] = { ...updated[idx], [field]: value };
    setScenarios(updated);
  };

  const runSimulation = () => {
    const valid = scenarios.filter(s => s.resource_id.trim());
    if (valid.length > 0) onSimulate(valid);
  };

  const simResult = result || DEMO_SIMULATION_RESULT;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {scenarios.map((s, i) => (
          <div key={i} style={{
            display: "flex", gap: 8, alignItems: "center",
            padding: 10, borderRadius: 8, background: COLORS.bg,
            border: `1px solid ${COLORS.border}`,
          }}>
            <input
              placeholder="Resource ID *"
              value={s.resource_id}
              onChange={e => updateScenario(i, "resource_id", e.target.value)}
              style={{
                flex: 2, padding: "6px 10px", borderRadius: 6,
                border: `1px solid ${COLORS.border}`, background: COLORS.card,
                color: COLORS.text, fontSize: 12,
              }}
            />
            <select
              value={s.action}
              onChange={e => updateScenario(i, "action", e.target.value)}
              style={{
                flex: 1, padding: "6px 10px", borderRadius: 6,
                border: `1px solid ${COLORS.border}`, background: COLORS.card,
                color: COLORS.text, fontSize: 12,
              }}
            >
              <option value="call_tool">call_tool</option>
              <option value="read_resource">read_resource</option>
              <option value="get_prompt">get_prompt</option>
              <option value="list_tools">list_tools</option>
            </select>
            <input
              placeholder="Label"
              value={s.label}
              onChange={e => updateScenario(i, "label", e.target.value)}
              style={{
                flex: 1, padding: "6px 10px", borderRadius: 6,
                border: `1px solid ${COLORS.border}`, background: COLORS.card,
                color: COLORS.text, fontSize: 12,
              }}
            />
            <button onClick={() => removeScenario(i)} style={{
              background: "none", border: "none", cursor: "pointer", color: COLORS.textDim, padding: 4,
            }}>
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <Button onClick={addScenario} variant="ghost" small icon={Plus}>Add Scenario</Button>
        <Button onClick={runSimulation} small icon={Play}>Run Simulation</Button>
      </div>

      {simResult && simResult.results && (
        <Card style={{ background: COLORS.bg }}>
          <div style={{ display: "flex", gap: 16, marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: COLORS.textMuted }}>
              Total: <span style={{ color: COLORS.text, fontWeight: 700 }}>{simResult.total}</span>
            </div>
            <div style={{ fontSize: 12, color: COLORS.allow }}>
              Allowed: <span style={{ fontWeight: 700 }}>{simResult.allowed}</span>
            </div>
            <div style={{ fontSize: 12, color: COLORS.deny }}>
              Denied: <span style={{ fontWeight: 700 }}>{simResult.denied}</span>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {simResult.results.map((r, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "6px 10px", borderRadius: 6,
                background: r.decision === "allow" ? `${COLORS.allow}11` : `${COLORS.deny}11`,
                border: `1px solid ${r.decision === "allow" ? COLORS.allow : COLORS.deny}22`,
              }}>
                {r.decision === "allow" ? <CheckCircle size={12} style={{ color: COLORS.allow }} /> : <XCircle size={12} style={{ color: COLORS.deny }} />}
                <span style={{ fontSize: 12, color: COLORS.text, fontFamily: "monospace" }}>{r.resource_id}</span>
                {r.label && <span style={{ fontSize: 11, color: COLORS.textDim }}>({r.label})</span>}
                <span style={{ fontSize: 11, color: COLORS.textMuted, marginLeft: "auto" }}>{r.reason}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};

// ── Statistics Dashboard ───────────────────────────────────────────

const StatsPanel = ({ stats }) => {
  const s = stats || DEMO_STATS;
  const decisionData = [
    { name: "Allow", value: s.current_allow, color: COLORS.allow },
    { name: "Deny", value: s.current_deny, color: COLORS.deny },
    { name: "Defer", value: s.current_defer, color: COLORS.defer },
  ];
  const topDenied = (s.top_denied_resources || []).map(r => ({
    name: r.resource_id.length > 18 ? r.resource_id.slice(0, 18) + "..." : r.resource_id,
    count: r.count,
  }));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <Card>
        <div style={{ fontSize: 12, fontWeight: 600, color: COLORS.textMuted, marginBottom: 12 }}>Decision Distribution</div>
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie data={decisionData} dataKey="value" cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={3}>
              {decisionData.map((d, i) => <Cell key={i} fill={d.color} />)}
            </Pie>
            <Tooltip contentStyle={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 12, color: COLORS.text }} />
          </PieChart>
        </ResponsiveContainer>
        <div style={{ display: "flex", justifyContent: "center", gap: 16, marginTop: 8 }}>
          {decisionData.map(d => (
            <div key={d.name} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: d.color }} />
              <span style={{ color: COLORS.textMuted }}>{d.name}: {d.value}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <div style={{ fontSize: 12, fontWeight: 600, color: COLORS.textMuted, marginBottom: 12 }}>Top Denied Resources</div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={topDenied} layout="vertical" margin={{ left: 10, right: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.border} />
            <XAxis type="number" tick={{ fontSize: 10, fill: COLORS.textDim }} />
            <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 10, fill: COLORS.textMuted }} />
            <Tooltip contentStyle={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 12, color: COLORS.text }} />
            <Bar dataKey="count" fill={COLORS.deny} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card style={{ gridColumn: "1 / -1" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 16 }}>
          {[
            { label: "Total Evaluated", value: s.total_recorded, icon: Eye },
            { label: "Total Allowed", value: s.total_allowed, icon: CheckCircle, color: COLORS.allow },
            { label: "Total Denied", value: s.total_denied, icon: XCircle, color: COLORS.deny },
            { label: "Unique Actors", value: s.unique_actors, icon: Shield },
            { label: "Deny Rate", value: `${(s.deny_rate * 100).toFixed(1)}%`, icon: AlertTriangle, color: COLORS.deny },
          ].map((m, i) => (
            <div key={i} style={{ textAlign: "center", padding: 8 }}>
              <m.icon size={18} style={{ color: m.color || COLORS.primary, marginBottom: 4 }} />
              <div style={{ fontSize: 20, fontWeight: 800, color: m.color || COLORS.text }}>{typeof m.value === "number" ? m.value.toLocaleString() : m.value}</div>
              <div style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 2 }}>{m.label}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

// ── JSON Editor ────────────────────────────────────────────────────

const JSONPolicyEditor = ({ schema, onLoad }) => {
  const [jsonText, setJsonText] = useState(JSON.stringify({
    composition: "all_of",
    policies: [
      { type: "allowlist", allowed: ["safe-*", "weather-*"] },
      { type: "denylist", denied: ["admin-*", "system-*"] },
    ],
  }, null, 2));
  const [error, setError] = useState(null);

  const handleLoad = () => {
    try {
      const parsed = JSON.parse(jsonText);
      setError(null);
      onLoad(parsed);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: COLORS.text }}>Declarative Policy (JSON)</div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={handleLoad} small icon={FileText}>Load Policy</Button>
          <Button onClick={() => {
            const blob = new Blob([jsonText], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "policy.json";
            a.click();
          }} small variant="ghost" icon={Download}>Export</Button>
        </div>
      </div>
      <textarea
        value={jsonText}
        onChange={e => { setJsonText(e.target.value); setError(null); }}
        spellCheck={false}
        style={{
          width: "100%", minHeight: 300, padding: 16, borderRadius: 8,
          border: `1px solid ${error ? COLORS.deny : COLORS.border}`,
          background: COLORS.bg, color: COLORS.text,
          fontFamily: "monospace", fontSize: 12, lineHeight: 1.5,
          resize: "vertical", boxSizing: "border-box",
        }}
      />
      {error && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, color: COLORS.deny, fontSize: 12 }}>
          <AlertTriangle size={12} /> {error}
        </div>
      )}
      <div style={{ fontSize: 11, color: COLORS.textDim }}>
        Supported types: {(schema?.policy_types || DEMO_SCHEMA.policy_types).map(t => t.type).join(", ")}
        <br />
        Compositions: {(schema?.compositions || DEMO_SCHEMA.compositions).join(", ")}
      </div>
    </div>
  );
};

// ── Main Component ─────────────────────────────────────────────────

export default function SecureMCPPolicyEditor({ liveData = null, apiBase = "/security" }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [providers, setProviders] = useState(liveData?.providers || DEMO_PROVIDERS);
  const [auditEntries, setAuditEntries] = useState(liveData?.audit?.entries || DEMO_AUDIT_ENTRIES);
  const [stats, setStats] = useState(liveData?.stats || DEMO_STATS);
  const [schema, setSchema] = useState(liveData?.schema || DEMO_SCHEMA);
  const [simResult, setSimResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!apiBase) return;
    setLoading(true);
    try {
      const [statusRes, auditRes, statsRes, schemaRes] = await Promise.allSettled([
        fetch(`${apiBase}/policy`).then(r => r.json()),
        fetch(`${apiBase}/policy/audit?limit=50`).then(r => r.json()),
        fetch(`${apiBase}/policy/audit/stats`).then(r => r.json()),
        fetch(`${apiBase}/policy/schema`).then(r => r.json()),
      ]);
      if (statusRes.status === "fulfilled" && !statusRes.value.error) setProviders(statusRes.value.providers || []);
      if (auditRes.status === "fulfilled" && !auditRes.value.error) setAuditEntries(auditRes.value.entries || []);
      if (statsRes.status === "fulfilled" && !statsRes.value.error) setStats(statsRes.value);
      if (schemaRes.status === "fulfilled" && !schemaRes.value.error) setSchema(schemaRes.value);
    } catch (e) {
      console.warn("Failed to fetch policy data:", e);
    }
    setLoading(false);
  }, [apiBase]);

  useEffect(() => {
    if (liveData) return;
    fetchData();
  }, [fetchData, liveData]);

  const handleSimulate = async (scenarios) => {
    try {
      const res = await fetch(`${apiBase}/policy/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenarios }),
      });
      const data = await res.json();
      setSimResult(data);
    } catch (e) {
      setSimResult(DEMO_SIMULATION_RESULT);
    }
  };

  const handleRemoveProvider = (idx) => {
    setProviders(providers.filter((_, i) => i !== idx));
  };

  const handleAddPolicy = (policy) => {
    setProviders([...providers, { type: policy.type, policy_id: policy.policy_id, version: "1.0" }]);
  };

  const handleLoadDeclarative = (config) => {
    console.log("Loading declarative policy:", config);
    // In a real implementation, POST to /security/policy/load
  };

  const tabs = [
    { id: "overview", label: "Overview", icon: Eye },
    { id: "providers", label: "Providers", icon: Layers },
    { id: "audit", label: "Audit Log", icon: FileText },
    { id: "simulate", label: "Simulate", icon: Play },
    { id: "editor", label: "Editor", icon: Settings },
  ];

  return (
    <div style={{
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      background: COLORS.bg, color: COLORS.text, minHeight: "100vh", padding: 24,
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center",
            background: `linear-gradient(135deg, ${COLORS.primary}, ${COLORS.secondary})`,
          }}>
            <Shield size={22} style={{ color: "#fff" }} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, letterSpacing: -0.5 }}>Policy Editor</h1>
            <p style={{ margin: 0, fontSize: 12, color: COLORS.textMuted }}>SecureMCP Policy Management Console</p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={fetchData} variant="ghost" small icon={RefreshCw} disabled={loading}>
            {loading ? "Loading..." : "Refresh"}
          </Button>
        </div>
      </div>

      <TabNav tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <StatsPanel stats={stats} />
      )}

      {/* Providers Tab */}
      {activeTab === "providers" && (
        <Card>
          <SectionHeader
            icon={Layers}
            title="Policy Providers"
            subtitle={`${providers.length} active provider${providers.length !== 1 ? "s" : ""} in evaluation chain`}
          />
          <ProviderList providers={providers} onRemove={handleRemoveProvider} />
          <div style={{ marginTop: 16 }}>
            <PolicyBuilder schema={schema} onAdd={handleAddPolicy} />
          </div>
        </Card>
      )}

      {/* Audit Tab */}
      {activeTab === "audit" && (
        <Card>
          <SectionHeader
            icon={FileText}
            title="Policy Audit Log"
            subtitle="Complete record of all policy decisions"
            action={
              <Button onClick={() => {
                const blob = new Blob([JSON.stringify(auditEntries, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "audit-log.json";
                a.click();
              }} variant="ghost" small icon={Download}>Export</Button>
            }
          />
          <AuditTable entries={auditEntries} />
        </Card>
      )}

      {/* Simulate Tab */}
      {activeTab === "simulate" && (
        <Card>
          <SectionHeader
            icon={Play}
            title="Policy Simulation"
            subtitle="Test scenarios against the current policy engine without side effects"
          />
          <SimulationPanel onSimulate={handleSimulate} result={simResult} />
        </Card>
      )}

      {/* Editor Tab */}
      {activeTab === "editor" && (
        <Card>
          <SectionHeader
            icon={Settings}
            title="Declarative Policy Editor"
            subtitle="Write or import policies as JSON/YAML configuration"
          />
          <JSONPolicyEditor schema={schema} onLoad={handleLoadDeclarative} />
        </Card>
      )}
    </div>
  );
}
