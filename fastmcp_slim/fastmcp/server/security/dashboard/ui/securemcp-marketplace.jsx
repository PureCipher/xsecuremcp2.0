import { useState, useEffect, useMemo } from "react";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import {
  Shield, CheckCircle, XCircle, Package, Star, Download, Search,
  Filter, ChevronRight, ExternalLink, Globe, Code, Lock, Zap,
  Database, MessageSquare, Eye, Settings, TrendingUp, Award,
  Tag, Clock, User, ThumbsUp, BarChart2, Grid3X3, List,
} from "lucide-react";

// ── Demo Data (fallback when no liveData is provided) ──────────
// To wire to the Python backend, generate JSON via:
//   from fastmcp.server.security.gateway.marketplace_bridge import MarketplaceDataBridge
//   bridge = MarketplaceDataBridge(marketplace=mp, trust_registry=registry)
//   data = bridge.export()
// Then pass `data` as the `liveData` prop to SecureMCPMarketplace.

const DEMO_STATS = {
  total_listings: 56,
  published: 48,
  certified: 34,
  total_installs: 3847,
  total_reviews: 142,
  categories: 9,
};

const DEMO_CATEGORIES = [
  { name: "Data Access", value: 12, key: "data_access", color: "#6366f1" },
  { name: "Network", value: 9, key: "network", color: "#a78bfa" },
  { name: "AI / ML", value: 8, key: "ai_ml", color: "#f59e0b" },
  { name: "Database", value: 7, key: "database", color: "#ec4899" },
  { name: "Search", value: 5, key: "search", color: "#3b82f6" },
  { name: "File System", value: 4, key: "file_system", color: "#8b5cf6" },
  { name: "Auth", value: 3, key: "authentication", color: "#14b8a6" },
  { name: "Monitoring", value: 2, key: "monitoring", color: "#f97316" },
  { name: "Utility", value: 4, key: "utility", color: "#6b7280" },
];

const DEMO_FEATURED = [
  {
    id: "f1", name: "api-gateway", display_name: "API Gateway", version: "3.2.1",
    author: "securecorp", description: "High-performance API gateway with rate limiting, auth, and request transformation for MCP tool chains.",
    categories: ["network"], category_labels: ["Network"], status: "published",
    is_certified: true, certification_level: "enhanced", trust_score: 0.96,
    rating: 4.8, rating_label: "4.8", review_count: 28, install_count: 456,
    active_installs: 312, tags: ["gateway", "api", "proxy"], license: "MIT",
    homepage_url: "https://example.com", source_url: "https://github.com/example",
    updated_relative: "2h ago",
  },
  {
    id: "f2", name: "vector-search", display_name: "Vector Search", version: "2.0.0",
    author: "aitools", description: "Semantic vector search over documents, embeddings, and knowledge bases with HNSW indexing.",
    categories: ["search", "ai_ml"], category_labels: ["Search", "AI / ML"], status: "published",
    is_certified: true, certification_level: "comprehensive", trust_score: 0.94,
    rating: 4.7, rating_label: "4.7", review_count: 19, install_count: 334,
    active_installs: 267, tags: ["vector", "search", "embeddings"], license: "Apache-2.0",
    homepage_url: "", source_url: "", updated_relative: "5h ago",
  },
  {
    id: "f3", name: "pg-connector", display_name: "PostgreSQL Connector", version: "4.1.0",
    author: "dataops", description: "Direct PostgreSQL access with parameterized queries, connection pooling, and schema introspection.",
    categories: ["database"], category_labels: ["Database"], status: "published",
    is_certified: true, certification_level: "basic", trust_score: 0.92,
    rating: 4.6, rating_label: "4.6", review_count: 22, install_count: 289,
    active_installs: 201, tags: ["postgres", "sql", "database"], license: "MIT",
    homepage_url: "", source_url: "", updated_relative: "1d ago",
  },
  {
    id: "f4", name: "file-processor", display_name: "File Processor", version: "1.5.2",
    author: "filetools", description: "Parse, transform, and convert files across 50+ formats including PDF, DOCX, CSV, and JSON.",
    categories: ["file_system"], category_labels: ["File System"], status: "published",
    is_certified: true, certification_level: "enhanced", trust_score: 0.91,
    rating: 4.5, rating_label: "4.5", review_count: 15, install_count: 245,
    active_installs: 178, tags: ["files", "parser", "converter"], license: "MIT",
    homepage_url: "", source_url: "", updated_relative: "3d ago",
  },
  {
    id: "f5", name: "ml-pipeline", display_name: "ML Pipeline", version: "2.3.0",
    author: "mlops", description: "End-to-end ML pipeline orchestration with experiment tracking, model registry, and deployment hooks.",
    categories: ["ai_ml"], category_labels: ["AI / ML"], status: "published",
    is_certified: true, certification_level: "enhanced", trust_score: 0.89,
    rating: 4.4, rating_label: "4.4", review_count: 11, install_count: 198,
    active_installs: 156, tags: ["ml", "pipeline", "training"], license: "Apache-2.0",
    homepage_url: "", source_url: "", updated_relative: "1w ago",
  },
  {
    id: "f6", name: "auth-handler", display_name: "Auth Handler", version: "1.2.0",
    author: "secteam", description: "OAuth 2.0, OIDC, and API key authentication middleware with token management and RBAC.",
    categories: ["authentication"], category_labels: ["Auth"], status: "published",
    is_certified: false, certification_level: "uncertified", trust_score: 0.85,
    rating: 4.1, rating_label: "4.1", review_count: 8, install_count: 134,
    active_installs: 98, tags: ["auth", "oauth", "security"], license: "MIT",
    homepage_url: "", source_url: "", updated_relative: "2w ago",
  },
];

const DEMO_LISTINGS = [
  ...DEMO_FEATURED,
  {
    id: "l7", name: "log-monitor", display_name: "Log Monitor", version: "1.0.3",
    author: "obstools", description: "Real-time log aggregation, alerting, and anomaly detection for MCP tool deployments.",
    categories: ["monitoring"], category_labels: ["Monitoring"], status: "published",
    is_certified: true, certification_level: "basic", trust_score: 0.87,
    rating: 4.2, rating_label: "4.2", review_count: 6, install_count: 89,
    active_installs: 67, tags: ["logs", "monitoring", "alerts"], license: "MIT",
    homepage_url: "", source_url: "", updated_relative: "3d ago",
  },
  {
    id: "l8", name: "data-fetcher", display_name: "Data Fetcher", version: "2.1.0",
    author: "dataops", description: "HTTP data fetcher with caching, retry logic, rate limiting, and response transformation.",
    categories: ["data_access", "network"], category_labels: ["Data Access", "Network"], status: "published",
    is_certified: true, certification_level: "enhanced", trust_score: 0.93,
    rating: 4.7, rating_label: "4.7", review_count: 24, install_count: 367,
    active_installs: 289, tags: ["http", "fetch", "api"], license: "MIT",
    homepage_url: "", source_url: "", updated_relative: "6h ago",
  },
  {
    id: "l9", name: "code-sandbox", display_name: "Code Sandbox", version: "0.9.1",
    author: "devtools", description: "Isolated code execution environment with timeout controls and resource limits for untrusted code.",
    categories: ["code_execution"], category_labels: ["Code Execution"], status: "published",
    is_certified: false, certification_level: "uncertified", trust_score: 0.78,
    rating: 3.9, rating_label: "3.9", review_count: 5, install_count: 67,
    active_installs: 45, tags: ["sandbox", "code", "execution"], license: "Apache-2.0",
    homepage_url: "", source_url: "", updated_relative: "1w ago",
  },
  {
    id: "l10", name: "smtp-sender", display_name: "SMTP Sender", version: "1.1.0",
    author: "commstools", description: "Send emails via SMTP with template support, attachments, and delivery tracking.",
    categories: ["communication"], category_labels: ["Communication"], status: "published",
    is_certified: true, certification_level: "basic", trust_score: 0.86,
    rating: 4.0, rating_label: "4.0", review_count: 7, install_count: 112,
    active_installs: 84, tags: ["email", "smtp", "notifications"], license: "MIT",
    homepage_url: "", source_url: "", updated_relative: "5d ago",
  },
];

// ── Data resolver ──────────────────────────────────────────────

function useMarketplaceData(liveData) {
  return {
    stats: liveData?.stats || DEMO_STATS,
    featured: liveData?.featured || DEMO_FEATURED,
    listings: liveData?.listings || DEMO_LISTINGS,
    categories: liveData?.categories || DEMO_CATEGORIES,
    isLive: !!liveData,
  };
}

// ── Utility Components ─────────────────────────────────────────

function Badge({ children, variant = "default" }) {
  const styles = {
    default: "bg-gray-100 text-gray-700",
    success: "bg-emerald-50 text-emerald-700 border border-emerald-200",
    warning: "bg-amber-50 text-amber-700 border border-amber-200",
    danger: "bg-red-50 text-red-700 border border-red-200",
    info: "bg-indigo-50 text-indigo-700 border border-indigo-200",
    purple: "bg-violet-50 text-violet-700 border border-violet-200",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${styles[variant]}`}>
      {children}
    </span>
  );
}

function StarRating({ rating, size = 14 }) {
  const full = Math.floor(rating);
  const half = rating - full >= 0.5;
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          size={size}
          className={i < full ? "text-amber-400 fill-amber-400" : half && i === full ? "text-amber-400 fill-amber-200" : "text-gray-200"}
        />
      ))}
    </div>
  );
}

function TrustRing({ score, size = 40 }) {
  const r = (size - 5) / 2;
  const c = 2 * Math.PI * r;
  const o = c - score * c;
  const color = score >= 0.85 ? "#10b981" : score >= 0.6 ? "#f59e0b" : "#ef4444";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#f3f4f6" strokeWidth="3" />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={o} transform={`rotate(-90 ${size/2} ${size/2})`} />
      <text x={size/2} y={size/2 + 4} textAnchor="middle" fill="#111827" fontSize="10" fontWeight="600">
        {(score * 100).toFixed(0)}
      </text>
    </svg>
  );
}

function CertBadge({ level, certified }) {
  if (!certified) return <Badge variant="default">Uncertified</Badge>;
  const colors = {
    basic: "warning",
    enhanced: "info",
    comprehensive: "success",
    critical: "purple",
  };
  return (
    <Badge variant={colors[level] || "success"}>
      <Award size={10} className="mr-1" />
      {level.charAt(0).toUpperCase() + level.slice(1)}
    </Badge>
  );
}

function CategoryIcon({ category, size = 16 }) {
  const icons = {
    data_access: Database,
    file_system: Code,
    network: Globe,
    code_execution: Zap,
    ai_ml: TrendingUp,
    communication: MessageSquare,
    search: Search,
    database: Database,
    authentication: Lock,
    monitoring: Eye,
    utility: Settings,
    other: Package,
  };
  const Icon = icons[category] || Package;
  return <Icon size={size} />;
}

function MetricPill({ icon: Icon, value, label }) {
  return (
    <div className="flex items-center gap-1.5 text-xs text-gray-500">
      <Icon size={12} />
      <span className="font-medium text-gray-700">{value}</span>
      <span>{label}</span>
    </div>
  );
}

// ── Tool Card ──────────────────────────────────────────────────

function ToolCard({ tool, variant = "grid", onSelect }) {
  if (variant === "list") {
    return (
      <div
        onClick={() => onSelect?.(tool)}
        className="flex items-center gap-4 p-4 bg-white rounded-xl border border-gray-200 hover:border-indigo-300 hover:shadow-md transition-all cursor-pointer group"
      >
        <div className="p-2.5 rounded-xl bg-indigo-50 group-hover:bg-indigo-100 transition-colors">
          <CategoryIcon category={tool.categories?.[0]} size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-gray-900">{tool.display_name}</span>
            <span className="text-xs text-gray-400">v{tool.version}</span>
            <CertBadge level={tool.certification_level} certified={tool.is_certified} />
          </div>
          <p className="text-sm text-gray-500 mt-0.5 truncate">{tool.description}</p>
          <div className="flex items-center gap-4 mt-1.5">
            <div className="flex items-center gap-1">
              <StarRating rating={tool.rating} size={12} />
              <span className="text-xs text-gray-500">({tool.review_count})</span>
            </div>
            <MetricPill icon={Download} value={tool.install_count.toLocaleString()} label="installs" />
            <MetricPill icon={User} value={tool.author} label="" />
          </div>
        </div>
        <TrustRing score={tool.trust_score} />
        <ChevronRight size={16} className="text-gray-300 group-hover:text-indigo-400" />
      </div>
    );
  }

  return (
    <div
      onClick={() => onSelect?.(tool)}
      className="flex flex-col bg-white rounded-xl border border-gray-200 hover:border-indigo-300 hover:shadow-md transition-all cursor-pointer group overflow-hidden"
    >
      <div className="p-5 flex-1">
        <div className="flex items-start justify-between mb-3">
          <div className="p-2 rounded-xl bg-indigo-50 group-hover:bg-indigo-100 transition-colors">
            <CategoryIcon category={tool.categories?.[0]} size={20} />
          </div>
          <TrustRing score={tool.trust_score} size={36} />
        </div>
        <div className="flex items-center gap-2 mb-1">
          <h3 className="font-semibold text-gray-900 text-sm">{tool.display_name}</h3>
          <span className="text-xs text-gray-400">v{tool.version}</span>
        </div>
        <p className="text-xs text-gray-500 leading-relaxed line-clamp-2 mb-3">{tool.description}</p>
        <div className="flex flex-wrap gap-1.5 mb-3">
          {tool.category_labels?.map((label) => (
            <span key={label} className="px-1.5 py-0.5 bg-gray-50 text-gray-500 rounded text-xs">{label}</span>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <StarRating rating={tool.rating} size={12} />
          <span className="text-xs text-gray-500">{tool.rating_label}</span>
          <span className="text-xs text-gray-300">({tool.review_count})</span>
        </div>
      </div>
      <div className="px-5 py-3 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MetricPill icon={Download} value={tool.install_count.toLocaleString()} label="" />
          <MetricPill icon={User} value={tool.author} label="" />
        </div>
        <CertBadge level={tool.certification_level} certified={tool.is_certified} />
      </div>
    </div>
  );
}

// ── Detail Panel ───────────────────────────────────────────────

function DetailPanel({ tool, onClose }) {
  if (!tool) return null;

  return (
    <div className="fixed inset-0 bg-black/30 z-50 flex justify-end" onClick={onClose}>
      <div
        className="w-full max-w-lg bg-white shadow-2xl overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-50">
              <CategoryIcon category={tool.categories?.[0]} size={22} />
            </div>
            <div>
              <h2 className="font-bold text-gray-900">{tool.display_name}</h2>
              <span className="text-xs text-gray-400">by {tool.author} &middot; v{tool.version}</span>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600">
            <XCircle size={20} />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Action buttons */}
          <div className="flex gap-3">
            <button className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white font-medium rounded-xl hover:bg-indigo-700 transition-colors text-sm">
              <Download size={16} />
              Install Tool
            </button>
            {tool.source_url && (
              <a href={tool.source_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2.5 border border-gray-200 text-gray-700 font-medium rounded-xl hover:bg-gray-50 transition-colors text-sm">
                <Code size={16} />
                Source
              </a>
            )}
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-4 gap-3">
            <div className="text-center p-3 rounded-xl bg-gray-50">
              <div className="text-lg font-bold text-gray-900">{(tool.trust_score * 100).toFixed(0)}</div>
              <div className="text-xs text-gray-500">Trust</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-gray-50">
              <div className="text-lg font-bold text-gray-900">{tool.rating_label}</div>
              <div className="text-xs text-gray-500">Rating</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-gray-50">
              <div className="text-lg font-bold text-gray-900">{tool.install_count.toLocaleString()}</div>
              <div className="text-xs text-gray-500">Installs</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-gray-50">
              <div className="text-lg font-bold text-gray-900">{tool.review_count}</div>
              <div className="text-xs text-gray-500">Reviews</div>
            </div>
          </div>

          {/* Description */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-2">About</h3>
            <p className="text-sm text-gray-600 leading-relaxed">{tool.description}</p>
          </div>

          {/* Certification */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-2">Security</h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                <span className="text-sm text-gray-600">Certification</span>
                <CertBadge level={tool.certification_level} certified={tool.is_certified} />
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                <span className="text-sm text-gray-600">Trust Score</span>
                <TrustRing score={tool.trust_score} size={32} />
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                <span className="text-sm text-gray-600">License</span>
                <span className="text-sm font-medium text-gray-700">{tool.license || "Not specified"}</span>
              </div>
            </div>
          </div>

          {/* Categories & Tags */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-2">Categories & Tags</h3>
            <div className="flex flex-wrap gap-1.5">
              {tool.category_labels?.map((label) => (
                <span key={label} className="px-2 py-1 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-medium">{label}</span>
              ))}
              {tool.tags?.map((tag) => (
                <span key={tag} className="px-2 py-1 bg-gray-100 text-gray-600 rounded-lg text-xs">
                  <Tag size={10} className="inline mr-1" />{tag}
                </span>
              ))}
            </div>
          </div>

          {/* Metadata */}
          <div className="pt-4 border-t border-gray-100">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-gray-400">Active installs</span>
                <div className="font-medium text-gray-700">{tool.active_installs?.toLocaleString() || "—"}</div>
              </div>
              <div>
                <span className="text-gray-400">Updated</span>
                <div className="font-medium text-gray-700">{tool.updated_relative}</div>
              </div>
              <div>
                <span className="text-gray-400">Status</span>
                <div className="font-medium text-gray-700 capitalize">{tool.status}</div>
              </div>
              <div>
                <span className="text-gray-400">Tool Name</span>
                <div className="font-medium text-gray-700 font-mono">{tool.name}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Marketplace ───────────────────────────────────────────

export default function SecureMCPMarketplace({ liveData = null }) {
  const data = useMarketplaceData(liveData);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [viewMode, setViewMode] = useState("grid");
  const [selectedTool, setSelectedTool] = useState(null);
  const [sortBy, setSortBy] = useState("relevance");

  const filteredListings = useMemo(() => {
    let results = data.listings;

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      results = results.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.display_name.toLowerCase().includes(q) ||
          t.description.toLowerCase().includes(q) ||
          t.tags?.some((tag) => tag.toLowerCase().includes(q))
      );
    }

    if (selectedCategory !== "all") {
      results = results.filter((t) => t.categories?.includes(selectedCategory));
    }

    if (sortBy === "rating") {
      results = [...results].sort((a, b) => b.rating - a.rating);
    } else if (sortBy === "installs") {
      results = [...results].sort((a, b) => b.install_count - a.install_count);
    } else if (sortBy === "trust") {
      results = [...results].sort((a, b) => b.trust_score - a.trust_score);
    } else if (sortBy === "newest") {
      results = [...results].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    }

    return results;
  }, [data.listings, searchQuery, selectedCategory, sortBy]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Header ──────────────────────────────────────────── */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-violet-600 rounded-lg">
              <Package size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 leading-tight">SecureMCP Marketplace</h1>
              <p className="text-xs text-gray-500">Discover, install, and trust verified MCP tools</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search tools, categories, tags..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent w-72"
              />
            </div>
            {data.isLive && (
              <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-lg text-xs font-medium border border-emerald-200">LIVE</span>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* ── Stats Banner ──────────────────────────────────── */}
        <div className="mb-6 bg-gradient-to-r from-violet-600 via-violet-500 to-purple-500 rounded-2xl p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold">Tool Marketplace</h2>
              <p className="text-violet-200 text-sm mt-1">
                {data.stats.published} published tools across {data.stats.categories} categories
              </p>
            </div>
            <div className="flex items-center gap-8">
              <div className="text-center">
                <div className="text-3xl font-bold">{data.stats.published}</div>
                <div className="text-xs text-violet-200">Published</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">{data.stats.certified}</div>
                <div className="text-xs text-violet-200">Certified</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">{data.stats.total_installs.toLocaleString()}</div>
                <div className="text-xs text-violet-200">Installs</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">{data.stats.total_reviews}</div>
                <div className="text-xs text-violet-200">Reviews</div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Featured Tools ────────────────────────────────── */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={18} className="text-violet-600" />
            <h2 className="text-base font-semibold text-gray-900">Featured Tools</h2>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {data.featured.slice(0, 3).map((tool) => (
              <ToolCard key={tool.id} tool={tool} variant="grid" onSelect={setSelectedTool} />
            ))}
          </div>
        </div>

        {/* ── Main Content: Categories + Listings ───────────── */}
        <div className="grid grid-cols-4 gap-6">
          {/* Sidebar: Categories */}
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Categories</h3>
              <div className="space-y-1">
                <button
                  onClick={() => setSelectedCategory("all")}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                    selectedCategory === "all" ? "bg-violet-50 text-violet-700 font-medium" : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  <span>All Tools</span>
                  <span className="text-xs text-gray-400">{data.stats.published}</span>
                </button>
                {data.categories.map((cat) => (
                  <button
                    key={cat.key}
                    onClick={() => setSelectedCategory(cat.key)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                      selectedCategory === cat.key ? "bg-violet-50 text-violet-700 font-medium" : "text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: cat.color }} />
                      <span>{cat.name}</span>
                    </div>
                    <span className="text-xs text-gray-400">{cat.value}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Category Chart */}
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Distribution</h3>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={data.categories} cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={2} dataKey="value">
                    {data.categories.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Install Leaders */}
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Top by Installs</h3>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={data.listings.slice(0, 5).sort((a, b) => b.install_count - a.install_count)} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 10, fill: "#9ca3af" }} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: "#9ca3af" }} width={80} />
                  <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 12 }} />
                  <Bar dataKey="install_count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Main listing area */}
          <div className="col-span-3">
            {/* Toolbar */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">
                  {filteredListings.length} tool{filteredListings.length !== 1 ? "s" : ""}
                  {selectedCategory !== "all" && (
                    <span className="ml-1 text-violet-600 font-medium">
                      in {data.categories.find((c) => c.key === selectedCategory)?.name}
                    </span>
                  )}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 text-gray-600 focus:outline-none focus:ring-1 focus:ring-violet-500"
                >
                  <option value="relevance">Sort: Relevance</option>
                  <option value="trust">Sort: Trust Score</option>
                  <option value="rating">Sort: Rating</option>
                  <option value="installs">Sort: Installs</option>
                  <option value="newest">Sort: Newest</option>
                </select>
                <div className="flex border border-gray-200 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setViewMode("grid")}
                    className={`p-1.5 ${viewMode === "grid" ? "bg-violet-50 text-violet-600" : "text-gray-400 hover:text-gray-600"}`}
                  >
                    <Grid3X3 size={16} />
                  </button>
                  <button
                    onClick={() => setViewMode("list")}
                    className={`p-1.5 ${viewMode === "list" ? "bg-violet-50 text-violet-600" : "text-gray-400 hover:text-gray-600"}`}
                  >
                    <List size={16} />
                  </button>
                </div>
              </div>
            </div>

            {/* Listings */}
            {viewMode === "grid" ? (
              <div className="grid grid-cols-3 gap-4">
                {filteredListings.map((tool) => (
                  <ToolCard key={tool.id} tool={tool} variant="grid" onSelect={setSelectedTool} />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {filteredListings.map((tool) => (
                  <ToolCard key={tool.id} tool={tool} variant="list" onSelect={setSelectedTool} />
                ))}
              </div>
            )}

            {filteredListings.length === 0 && (
              <div className="text-center py-16">
                <Package size={40} className="mx-auto text-gray-300 mb-3" />
                <h3 className="text-base font-medium text-gray-700">No tools found</h3>
                <p className="text-sm text-gray-400 mt-1">Try adjusting your search or filters</p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* ── Footer ──────────────────────────────────────────── */}
      <footer className="border-t border-gray-200 bg-white mt-8">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between text-xs text-gray-400">
          <span>SecureMCP Marketplace v2.0 &middot; PureCipher</span>
          <span>{data.stats.total_listings} listings &middot; {data.stats.total_installs.toLocaleString()} total installs</span>
        </div>
      </footer>

      {/* ── Detail Slide-over ───────────────────────────────── */}
      {selectedTool && <DetailPanel tool={selectedTool} onClose={() => setSelectedTool(null)} />}
    </div>
  );
}
