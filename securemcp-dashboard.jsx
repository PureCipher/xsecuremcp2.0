import { useState, useEffect, useRef } from "react";
import { LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Shield, AlertTriangle, CheckCircle, XCircle, Activity, Lock, Eye, Zap, Server, Globe, Package, FileCheck, Clock, TrendingUp, TrendingDown, ChevronRight, RefreshCw, Bell, Search, Filter, BarChart2 } from "lucide-react";

// ── Demo Data (fallback when no live data is provided) ─────────
// To wire to the Python backend, generate JSON via:
//   from fastmcp.server.security.dashboard import DashboardDataBridge
//   bridge = DashboardDataBridge(dashboard=your_security_dashboard)
//   data = bridge.export()
// Then pass `data` as the `liveData` prop to SecureMCPDashboard.

const DEMO_TRUST_TIMELINE = [
  { time: "00:00", score: 0.82, violations: 1, checks: 34 },
  { time: "04:00", score: 0.84, violations: 0, checks: 28 },
  { time: "08:00", score: 0.86, violations: 2, checks: 67 },
  { time: "12:00", score: 0.83, violations: 3, checks: 89 },
  { time: "16:00", score: 0.87, violations: 1, checks: 72 },
  { time: "20:00", score: 0.89, violations: 0, checks: 45 },
  { time: "Now", score: 0.91, violations: 0, checks: 52 },
];

const DEMO_COMPLIANCE_DATA = [
  { name: "Access Control", score: 95, total: 8, passed: 7 },
  { name: "Audit Logging", score: 100, total: 4, passed: 4 },
  { name: "Sandboxing", score: 87, total: 6, passed: 5 },
  { name: "Certification", score: 100, total: 5, passed: 5 },
  { name: "Federation", score: 75, total: 4, passed: 3 },
  { name: "Consent", score: 100, total: 3, passed: 3 },
  { name: "Provenance", score: 100, total: 3, passed: 3 },
];

const DEMO_TOOL_CATEGORIES = [
  { name: "Data Access", value: 24, color: "#6366f1" },
  { name: "Network", value: 18, color: "#8b5cf6" },
  { name: "File System", value: 15, color: "#a78bfa" },
  { name: "AI/ML", value: 12, color: "#c4b5fd" },
  { name: "Code Exec", value: 8, color: "#ddd6fe" },
  { name: "Other", value: 6, color: "#ede9fe" },
];

const DEMO_COMPONENTS = [
  { name: "Trust Registry", status: "healthy", tools: 83, certified: 71, icon: "shield" },
  { name: "Marketplace", status: "healthy", published: 56, installs: 1247, icon: "package" },
  { name: "Federation", status: "healthy", peers: 4, activePeers: 3, icon: "globe" },
  { name: "Sandbox Runner", status: "healthy", active: 12, completed: 847, icon: "lock" },
  { name: "CRL", status: "healthy", entries: 3, emergency: 0, icon: "filecheck" },
  { name: "Compliance", status: "healthy", score: 94, checks: 33, icon: "check" },
  { name: "Event Bus", status: "healthy", events: 2341, handlers: 8, icon: "activity" },
  { name: "Provenance", status: "healthy", records: 4521, tools: 83, icon: "eye" },
];

const DEMO_TIMELINE_EVENTS = [
  { id: 1, type: "certification", title: "Tool certified: data-fetcher v2.1", severity: "info", time: "2 min ago", icon: "check" },
  { id: 2, type: "security_check", title: "Security check passed: ml-pipeline", severity: "info", time: "5 min ago", icon: "shield" },
  { id: 3, type: "violation", title: "Sandbox violation: file-writer (blocked)", severity: "warning", time: "12 min ago", icon: "alert" },
  { id: 4, type: "federation", title: "Peer synced: partner-registry-eu", severity: "info", time: "18 min ago", icon: "globe" },
  { id: 5, type: "compliance", title: "Compliance report generated: 94% score", severity: "info", time: "25 min ago", icon: "bar" },
  { id: 6, type: "revocation", title: "Tool revoked: legacy-scraper (policy violation)", severity: "critical", time: "1 hr ago", icon: "x" },
  { id: 7, type: "certification", title: "Tool certified: api-gateway v3.0", severity: "info", time: "1.5 hr ago", icon: "check" },
  { id: 8, type: "security_check", title: "Trust score updated: db-connector (0.91)", severity: "info", time: "2 hr ago", icon: "trending" },
];

const DEMO_TOP_TOOLS = [
  { name: "api-gateway", trust: 0.96, certified: true, installs: 234, rating: 4.8, status: "published" },
  { name: "data-fetcher", trust: 0.93, certified: true, installs: 189, rating: 4.7, status: "published" },
  { name: "ml-pipeline", trust: 0.91, certified: true, installs: 156, rating: 4.5, status: "published" },
  { name: "db-connector", trust: 0.89, certified: true, installs: 143, rating: 4.6, status: "published" },
  { name: "file-processor", trust: 0.87, certified: true, installs: 121, rating: 4.3, status: "published" },
  { name: "auth-handler", trust: 0.85, certified: false, installs: 98, rating: 4.1, status: "pending_review" },
];

const DEMO_HEALTH_BANNER = {
  overall_health: "healthy",
  health_label: "Healthy",
  all_operational: true,
  healthy_components: 8,
  total_components: 8,
  compliance_score: 94,
  total_tools: 83,
  avg_trust: 0.91,
  revocations: 3,
  federation_peers: 4,
};

// ── Data resolver — uses live data or falls back to demo ──────

function useData(liveData) {
  return {
    trustTimeline: liveData?.trust_timeline || DEMO_TRUST_TIMELINE,
    complianceData: liveData?.compliance_data || DEMO_COMPLIANCE_DATA,
    toolCategories: liveData?.tool_categories || DEMO_TOOL_CATEGORIES,
    components: liveData?.components || DEMO_COMPONENTS,
    timelineEvents: liveData?.timeline_events || DEMO_TIMELINE_EVENTS,
    topTools: liveData?.top_tools || DEMO_TOP_TOOLS,
    banner: liveData?.health_banner || DEMO_HEALTH_BANNER,
    isLive: !!liveData,
  };
}

// ── Utility Components ─────────────────────────────────────────

function StatusDot({ status }) {
  const colors = {
    healthy: "bg-emerald-400",
    degraded: "bg-amber-400",
    critical: "bg-red-400",
    unknown: "bg-gray-400",
  };
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${colors[status] || colors.unknown}`} />
  );
}

function Badge({ children, variant = "default" }) {
  const styles = {
    default: "bg-gray-100 text-gray-700",
    success: "bg-emerald-50 text-emerald-700 border border-emerald-200",
    warning: "bg-amber-50 text-amber-700 border border-amber-200",
    danger: "bg-red-50 text-red-700 border border-red-200",
    info: "bg-indigo-50 text-indigo-700 border border-indigo-200",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${styles[variant]}`}>
      {children}
    </span>
  );
}

function MetricCard({ icon: Icon, label, value, subtext, trend, trendValue }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="p-2 rounded-lg bg-indigo-50">
          <Icon size={20} className="text-indigo-600" />
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-xs font-medium ${trend === "up" ? "text-emerald-600" : "text-red-500"}`}>
            {trend === "up" ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            {trendValue}
          </div>
        )}
      </div>
      <div className="mt-3">
        <div className="text-2xl font-bold text-gray-900">{value}</div>
        <div className="text-sm text-gray-500 mt-0.5">{label}</div>
        {subtext && <div className="text-xs text-gray-400 mt-1">{subtext}</div>}
      </div>
    </div>
  );
}

function SectionHeader({ icon: Icon, title, action }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <Icon size={18} className="text-indigo-600" />
        <h2 className="text-base font-semibold text-gray-900">{title}</h2>
      </div>
      {action}
    </div>
  );
}

// ── Compliance Gauge ───────────────────────────────────────────

function ComplianceGauge({ score }) {
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 90 ? "#10b981" : score >= 70 ? "#f59e0b" : "#ef4444";

  return (
    <div className="flex flex-col items-center">
      <svg width="180" height="180" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r={radius} fill="none" stroke="#f3f4f6" strokeWidth="12" />
        <circle
          cx="90" cy="90" r={radius} fill="none"
          stroke={color} strokeWidth="12" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          transform="rotate(-90 90 90)"
          style={{ transition: "stroke-dashoffset 1s ease-in-out" }}
        />
        <text x="90" y="82" textAnchor="middle" className="text-3xl font-bold" fill="#111827" fontSize="32" fontWeight="700">
          {score}%
        </text>
        <text x="90" y="105" textAnchor="middle" fill="#6b7280" fontSize="12">
          Compliance
        </text>
      </svg>
    </div>
  );
}

// ── Trust Score Ring ───────────────────────────────────────────

function TrustRing({ score, size = 44 }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const o = c - score * c;
  const color = score >= 0.85 ? "#10b981" : score >= 0.6 ? "#f59e0b" : "#ef4444";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#f3f4f6" strokeWidth="3" />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={o} transform={`rotate(-90 ${size/2} ${size/2})`} />
      <text x={size/2} y={size/2 + 4} textAnchor="middle" fill="#111827" fontSize="11" fontWeight="600">
        {(score * 100).toFixed(0)}
      </text>
    </svg>
  );
}

// ── Component Icon Helper ──────────────────────────────────────

function ComponentIcon({ type, size = 16 }) {
  const icons = { shield: Shield, package: Package, globe: Globe, lock: Lock, filecheck: FileCheck, check: CheckCircle, activity: Activity, eye: Eye };
  const Icon = icons[type] || Shield;
  return <Icon size={size} />;
}

// ── Event Icon Helper ──────────────────────────────────────────

function EventIcon({ type }) {
  const map = {
    check: { icon: CheckCircle, color: "text-emerald-500 bg-emerald-50" },
    shield: { icon: Shield, color: "text-indigo-500 bg-indigo-50" },
    alert: { icon: AlertTriangle, color: "text-amber-500 bg-amber-50" },
    globe: { icon: Globe, color: "text-blue-500 bg-blue-50" },
    bar: { icon: BarChart2, color: "text-violet-500 bg-violet-50" },
    x: { icon: XCircle, color: "text-red-500 bg-red-50" },
    trending: { icon: TrendingUp, color: "text-teal-500 bg-teal-50" },
  };
  const { icon: Icon, color } = map[type] || map.shield;
  return (
    <div className={`p-1.5 rounded-lg ${color}`}>
      <Icon size={14} />
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────

export default function SecureMCPDashboard({ liveData = null }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [searchQuery, setSearchQuery] = useState("");
  const [animatedScore, setAnimatedScore] = useState(0);
  const data = useData(liveData);

  useEffect(() => {
    let frame;
    let start = null;
    const target = data.banner.compliance_score || 94;
    const duration = 1200;
    function animate(ts) {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      setAnimatedScore(Math.round(progress * target));
      if (progress < 1) frame = requestAnimationFrame(animate);
    }
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, []);

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "tools", label: "Tools" },
    { id: "compliance", label: "Compliance" },
    { id: "timeline", label: "Timeline" },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Header ──────────────────────────────────────────── */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-indigo-600 rounded-lg">
              <Shield size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 leading-tight">SecureMCP</h1>
              <p className="text-xs text-gray-500">Security Dashboard</p>
            </div>
          </div>

          <div className="flex items-center gap-6">
            {/* Tabs */}
            <nav className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    activeTab === tab.id
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>

            <div className="flex items-center gap-3">
              <div className="relative">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search tools..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent w-48"
                />
              </div>
              <button className="relative p-2 text-gray-400 hover:text-gray-600 transition-colors">
                <Bell size={18} />
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
              </button>
              <button
                onClick={() => setLastRefresh(new Date())}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                <RefreshCw size={14} />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* ── Overall Health Banner ───────────────────────────── */}
        <div className={`mb-6 bg-gradient-to-r ${
          data.banner.overall_health === "critical"
            ? "from-red-600 via-red-500 to-rose-500"
            : data.banner.overall_health === "degraded"
            ? "from-amber-600 via-amber-500 to-yellow-500"
            : "from-indigo-600 via-indigo-500 to-violet-500"
        } rounded-2xl p-6 text-white`}>
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-2.5 h-2.5 rounded-full animate-pulse ${
                  data.banner.all_operational ? "bg-emerald-400" : "bg-amber-400"
                }`} />
                <span className="text-sm font-medium text-indigo-100">
                  {data.banner.all_operational ? "All Systems Operational" : "Issues Detected"}
                </span>
                {data.isLive && (
                  <span className="ml-2 px-1.5 py-0.5 bg-white/20 rounded text-xs font-medium">LIVE</span>
                )}
              </div>
              <h2 className="text-2xl font-bold">Security Posture: {data.banner.health_label}</h2>
              <p className="text-indigo-200 text-sm mt-1">
                {data.banner.healthy_components}/{data.banner.total_components} components healthy &middot; {data.banner.compliance_score}% compliance
              </p>
            </div>
            <div className="flex items-center gap-8">
              <div className="text-center">
                <div className="text-3xl font-bold">{data.banner.total_tools}</div>
                <div className="text-xs text-indigo-200">Tools</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">{data.banner.avg_trust}</div>
                <div className="text-xs text-indigo-200">Avg Trust</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">{data.banner.revocations}</div>
                <div className="text-xs text-indigo-200">Revocations</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">{data.banner.federation_peers}</div>
                <div className="text-xs text-indigo-200">Fed Peers</div>
              </div>
            </div>
          </div>
        </div>

        {activeTab === "overview" && <OverviewTab animatedScore={animatedScore} data={data} />}
        {activeTab === "tools" && <ToolsTab searchQuery={searchQuery} data={data} />}
        {activeTab === "compliance" && <ComplianceTab animatedScore={animatedScore} data={data} />}
        {activeTab === "timeline" && <TimelineTab data={data} />}
      </main>

      {/* ── Footer ──────────────────────────────────────────── */}
      <footer className="border-t border-gray-200 bg-white mt-8">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between text-xs text-gray-400">
          <span>SecureMCP v2.0 &middot; Phase 20 &middot; PureCipher</span>
          <span>Last refresh: {lastRefresh.toLocaleTimeString()}</span>
        </div>
      </footer>
    </div>
  );
}

// ── Overview Tab ───────────────────────────────────────────────

function OverviewTab({ animatedScore, data }) {
  const certifiedCount = data.topTools.filter(t => t.certified).length;
  const totalTools = data.banner.total_tools || data.topTools.length;
  const certRate = totalTools > 0 ? ((certifiedCount / totalTools) * 100).toFixed(1) : "0";
  const violationCount = data.trustTimeline.reduce((sum, t) => sum + (t.violations || 0), 0);

  return (
    <>
      {/* Metric Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <MetricCard icon={Shield} label="Trust Score" value={data.banner.avg_trust} subtext={`Across ${totalTools} tools`} trend="up" trendValue="+0.03" />
        <MetricCard icon={CheckCircle} label="Certified Tools" value={`${certifiedCount}/${totalTools}`} subtext={`${certRate}% certification rate`} trend="up" trendValue="+2" />
        <MetricCard icon={Package} label="Published Tools" value={data.topTools.filter(t => t.status === "published").length} subtext="Via marketplace" trend="up" trendValue="+5" />
        <MetricCard icon={AlertTriangle} label="Violations (24h)" value={violationCount} subtext={violationCount === 0 ? "None detected" : "Review recommended"} trend="down" trendValue={`-${violationCount}`} />
      </div>

      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* Trust Score Timeline */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader icon={TrendingUp} title="Trust Score Trend (24h)" />
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data.trustTimeline}>
              <defs>
                <linearGradient id="trustGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <YAxis domain={[0.7, 1.0]} tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 12 }}
                formatter={(v) => [(typeof v === 'number' ? v.toFixed(2) : v), "Trust Score"]}
              />
              <Area type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2.5} fill="url(#trustGrad)" dot={{ r: 3, fill: "#6366f1" }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Compliance Gauge */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col items-center justify-center">
          <SectionHeader icon={FileCheck} title="Compliance Score" />
          <ComplianceGauge score={animatedScore} />
          <div className="mt-2 text-sm text-gray-500">
            {data.complianceData.reduce((s, c) => s + c.passed, 0)}/{data.complianceData.reduce((s, c) => s + c.total, 0)} requirements met
          </div>
          <div className="mt-1 flex gap-2">
            <Badge variant="success">{data.complianceData.reduce((s, c) => s + c.passed, 0)} Passed</Badge>
            <Badge variant="danger">{data.complianceData.reduce((s, c) => s + (c.total - c.passed), 0)} Failed</Badge>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Component Health Grid */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader icon={Server} title="Component Health" />
          <div className="grid grid-cols-2 gap-3">
            {data.components.map((comp) => (
              <div key={comp.name} className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:border-indigo-200 hover:bg-indigo-50/30 transition-all cursor-pointer">
                <div className="p-2 rounded-lg bg-gray-50">
                  <ComponentIcon type={comp.icon} size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">{comp.name}</span>
                    <StatusDot status={comp.status} />
                  </div>
                  <div className="text-xs text-gray-400 truncate">
                    {comp.tools && `${comp.tools} tools`}
                    {comp.published && `${comp.published} published`}
                    {comp.peers && `${comp.activePeers}/${comp.peers} peers`}
                    {comp.active !== undefined && comp.completed !== undefined && !comp.tools && !comp.published && !comp.peers && !comp.entries && !comp.score && !comp.events && !comp.records && `${comp.active} active`}
                    {comp.entries !== undefined && `${comp.entries} entries`}
                    {comp.score && `${comp.score}% score`}
                    {comp.events && `${comp.events.toLocaleString()} events`}
                    {comp.records && `${comp.records.toLocaleString()} records`}
                  </div>
                </div>
                <ChevronRight size={14} className="text-gray-300" />
              </div>
            ))}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader icon={Activity} title="Recent Activity" />
          <div className="space-y-3">
            {data.timelineEvents.slice(0, 6).map((event) => (
              <div key={event.id} className="flex items-start gap-2.5">
                <EventIcon type={event.icon} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-700 leading-tight">{event.title}</div>
                  <div className="text-xs text-gray-400 mt-0.5">{event.time}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ── Tools Tab ──────────────────────────────────────────────────

function ToolsTab({ searchQuery, data }) {
  const filtered = data.topTools.filter((t) =>
    t.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* Tool Distribution */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader icon={Package} title="Tool Categories" />
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={data.toolCategories}
                cx="50%" cy="50%"
                innerRadius={50} outerRadius={80}
                paddingAngle={2} dataKey="value"
              >
                {data.toolCategories.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-1 mt-2">
            {data.toolCategories.map((cat) => (
              <div key={cat.name} className="flex items-center gap-1.5 text-xs text-gray-500">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: cat.color }} />
                {cat.name} ({cat.value})
              </div>
            ))}
          </div>
        </div>

        {/* Installs Over Time */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader icon={Zap} title="Security Checks (24h)" />
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data.trustTimeline}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 12 }} />
              <Bar dataKey="checks" fill="#6366f1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="violations" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Tools Table */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <SectionHeader icon={Shield} title="Top Tools by Trust Score" />
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider pb-3 pl-2">Tool</th>
                <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wider pb-3">Trust</th>
                <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wider pb-3">Certified</th>
                <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wider pb-3">Installs</th>
                <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wider pb-3">Rating</th>
                <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wider pb-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((tool) => (
                <tr key={tool.name} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="py-3 pl-2">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 bg-indigo-50 rounded-lg">
                        <Package size={14} className="text-indigo-600" />
                      </div>
                      <span className="font-medium text-sm text-gray-900">{tool.name}</span>
                    </div>
                  </td>
                  <td className="py-3 text-center">
                    <TrustRing score={tool.trust} />
                  </td>
                  <td className="py-3 text-center">
                    {tool.certified ? (
                      <CheckCircle size={18} className="text-emerald-500 mx-auto" />
                    ) : (
                      <Clock size={18} className="text-amber-400 mx-auto" />
                    )}
                  </td>
                  <td className="py-3 text-center text-sm text-gray-600">{tool.installs.toLocaleString()}</td>
                  <td className="py-3 text-center">
                    <span className="text-sm text-gray-700">{"★".repeat(Math.round(tool.rating))}</span>
                    <span className="text-xs text-gray-400 ml-1">{tool.rating}</span>
                  </td>
                  <td className="py-3 text-center">
                    <Badge variant={tool.status === "published" ? "success" : "warning"}>
                      {tool.status === "published" ? "Published" : "In Review"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// ── Compliance Tab ─────────────────────────────────────────────

function ComplianceTab({ animatedScore, data }) {
  return (
    <div className="grid grid-cols-3 gap-6">
      {/* Compliance Breakdown */}
      <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-5">
        <SectionHeader icon={FileCheck} title="Compliance by Category" />
        <div className="space-y-4">
          {data.complianceData.map((cat) => (
            <div key={cat.name}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-gray-700">{cat.name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">{cat.passed}/{cat.total} passed</span>
                  <Badge variant={cat.score >= 90 ? "success" : cat.score >= 70 ? "warning" : "danger"}>
                    {cat.score}%
                  </Badge>
                </div>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-1000 ${
                    cat.score >= 90 ? "bg-emerald-500" : cat.score >= 70 ? "bg-amber-500" : "bg-red-500"
                  }`}
                  style={{ width: `${cat.score}%` }}
                />
              </div>
            </div>
          ))}
        </div>

        {/* Compliance History */}
        <div className="mt-6 pt-5 border-t border-gray-100">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Score History</h3>
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={[
              { date: "Mon", score: 88 },
              { date: "Tue", score: 90 },
              { date: "Wed", score: 89 },
              { date: "Thu", score: 91 },
              { date: "Fri", score: 93 },
              { date: "Sat", score: 92 },
              { date: "Sun", score: 94 },
            ]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <YAxis domain={[80, 100]} tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 12 }} />
              <Line type="monotone" dataKey="score" stroke="#10b981" strokeWidth={2} dot={{ r: 3, fill: "#10b981" }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Overall Score + Details */}
      <div className="space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col items-center">
          <ComplianceGauge score={animatedScore} />
          <div className="w-full mt-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Framework</span>
              <span className="font-medium text-gray-900">SecureMCP v1.0</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Requirements</span>
              <span className="font-medium text-gray-900">{data.complianceData.reduce((s, c) => s + c.total, 0)} total</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Passing</span>
              <span className="font-medium text-gray-900">{data.complianceData.reduce((s, c) => s + c.passed, 0)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Last Report</span>
              <span className="font-medium text-gray-900">Just now</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Open Findings</h3>
          <div className="space-y-3">
            <div className="p-3 rounded-lg bg-red-50 border border-red-100">
              <div className="flex items-center gap-2">
                <XCircle size={14} className="text-red-500" />
                <span className="text-sm font-medium text-red-700">Federation peer timeout</span>
              </div>
              <p className="text-xs text-red-600 mt-1">Peer registry-asia unreachable for 2h</p>
            </div>
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-100">
              <div className="flex items-center gap-2">
                <AlertTriangle size={14} className="text-amber-500" />
                <span className="text-sm font-medium text-amber-700">Sandbox policy gap</span>
              </div>
              <p className="text-xs text-amber-600 mt-1">2 tools missing explicit sandbox configs</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Timeline Tab ───────────────────────────────────────────────

function TimelineTab({ data }) {
  const [filter, setFilter] = useState("all");
  const types = ["all", "certification", "security_check", "violation", "federation", "compliance", "revocation"];

  const filtered = filter === "all"
    ? data.timelineEvents
    : data.timelineEvents.filter((e) => e.type === filter);

  return (
    <div className="grid grid-cols-3 gap-6">
      <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-5">
        <SectionHeader
          icon={Activity}
          title="Activity Timeline"
          action={
            <div className="flex items-center gap-1">
              <Filter size={14} className="text-gray-400" />
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="text-xs border border-gray-200 rounded-md px-2 py-1 text-gray-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {types.map((t) => (
                  <option key={t} value={t}>{t === "all" ? "All Events" : t.replace("_", " ")}</option>
                ))}
              </select>
            </div>
          }
        />
        <div className="space-y-1">
          {filtered.map((event, i) => (
            <div
              key={event.id}
              className={`flex items-start gap-3 p-3 rounded-lg transition-colors hover:bg-gray-50 ${
                event.severity === "critical" ? "bg-red-50/50" : ""
              }`}
            >
              <EventIcon type={event.icon} />
              <div className="flex-1">
                <div className="text-sm text-gray-800">{event.title}</div>
                <div className="text-xs text-gray-400 mt-0.5">{event.time}</div>
              </div>
              <Badge variant={
                event.severity === "critical" ? "danger" :
                event.severity === "warning" ? "warning" : "info"
              }>
                {event.severity}
              </Badge>
            </div>
          ))}
        </div>
      </div>

      {/* Timeline Stats */}
      <div className="space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Event Summary (24h)</h3>
          <div className="space-y-3">
            {[
              { label: "Security Checks", count: 387, color: "bg-indigo-500" },
              { label: "Certifications", count: 12, color: "bg-emerald-500" },
              { label: "Violations", count: 7, color: "bg-amber-500" },
              { label: "Federation Syncs", count: 24, color: "bg-blue-500" },
              { label: "Revocations", count: 1, color: "bg-red-500" },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${item.color}`} />
                  <span className="text-sm text-gray-600">{item.label}</span>
                </div>
                <span className="text-sm font-semibold text-gray-900">{item.count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Checks Over Time</h3>
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={data.trustTimeline}>
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#9ca3af" }} />
              <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} />
              <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 12 }} />
              <Bar dataKey="checks" fill="#6366f1" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
