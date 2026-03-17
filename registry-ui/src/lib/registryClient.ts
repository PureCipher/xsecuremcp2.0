import { cookies } from "next/headers";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

export type RegistryPayload = Record<string, unknown>;
export type PolicyConfig = Record<string, unknown>;

export type RegistryErrorResponse = {
  error?: string;
  status?: number;
};

export type RegistrySessionInfo = {
  username?: string;
  role?: string;
  display_name?: string;
  expires_at?: string;
  can_submit?: boolean;
  can_review?: boolean;
  can_admin?: boolean;
};

export type RegistrySessionResponse = {
  auth_enabled?: boolean;
  session?: RegistrySessionInfo | null;
};

export type RegistryDataFlow = {
  source?: string;
  destination?: string;
  classification?: string;
  description?: string;
};

export type RegistryManifestSummary = {
  data_flows?: RegistryDataFlow[];
};

export type RegistryToolListing = {
  tool_name: string;
  display_name?: string;
  description?: string;
  categories?: string[];
  certification_level?: string;
  publisher_id?: string;
  version?: string;
  author?: string;
  manifest?: RegistryManifestSummary | null;
};

export type RegistryToolCatalogResponse = RegistryErrorResponse & {
  count?: number;
  tools?: RegistryToolListing[];
  minimum_certification?: string;
  generated_at?: string;
};

export type InstallRecipe = {
  recipe_id: string;
  title?: string;
  content?: string;
};

export type InstallRecipesResponse = RegistryErrorResponse & {
  tool_name?: string;
  recipes?: InstallRecipe[];
};

export type ToolVerificationDetail = {
  signature_valid?: boolean;
  manifest_match?: boolean;
  issues?: string[];
};

export type ToolVerificationResponse = RegistryErrorResponse & {
  verification?: ToolVerificationDetail;
};

export type PublisherTrustScore = {
  overall?: number;
};

export type PublisherSummary = {
  publisher_id: string;
  display_name?: string;
  summary?: string;
  description?: string;
  tool_count?: number;
  verified_tool_count?: number;
  trust_score?: PublisherTrustScore | null;
};

export type PublisherDirectoryResponse = RegistryErrorResponse & {
  count?: number;
  publishers?: PublisherSummary[];
  generated_at?: string;
};

export type PublisherProfileResponse = RegistryErrorResponse & {
  summary?: PublisherSummary;
  listings?: RegistryToolListing[];
};

export type ReviewLogEntry = {
  action?: string;
  moderator_id?: string;
  reason?: string;
};

export type ReviewQueueItem = {
  listing_id: string;
  display_name?: string;
  tool_name: string;
  version?: string;
  certification_level?: string;
  description?: string;
  moderation_log?: ReviewLogEntry[];
  available_actions?: string[];
};

export type ReviewQueueResponse = RegistryErrorResponse & {
  sections?: Record<string, ReviewQueueItem[]>;
};

export type RegistryHealthResponse = RegistryErrorResponse & {
  status?: string;
  minimum_certification?: string;
  require_moderation?: boolean;
  auth_enabled?: boolean;
  issuer_id?: string;
  registered_tools?: number;
  verified_tools?: number;
  pending_review?: number;
  timestamp?: string;
  server?: string;
};

export type PolicyProviderItem = {
  index: number;
  type: string;
  policy_id?: string | null;
  policy_version?: string | null;
  editable: boolean;
  summary: string;
  config: PolicyConfig;
};

export type PolicyVersionItem = {
  version_id: string;
  version_number: number;
  description?: string;
  author?: string;
  created_at?: string;
};

export type PolicyGovernanceSummary = {
  enabled?: boolean;
  proposal_count?: number;
  pending_count?: number;
  require_simulation?: boolean;
  require_approval?: boolean;
};

export type PolicyVersioningSummary = {
  enabled?: boolean;
  policy_set_id?: string;
  version_count?: number;
  current_version?: number | null;
};

export type PolicyState = RegistryErrorResponse & {
  evaluation_count?: number;
  deny_count?: number;
  fail_closed?: boolean;
  allow_hot_swap?: boolean;
  provider_count?: number;
  providers?: PolicyProviderItem[];
  has_audit_log?: boolean;
  versioning?: PolicyVersioningSummary | null;
  governance?: PolicyGovernanceSummary | null;
  generated_at?: string;
};

export type PolicyVersionsResponse = RegistryErrorResponse & {
  policy_set_id?: string;
  version_count?: number;
  current_version?: number | null;
  versions?: PolicyVersionItem[];
  generated_at?: string;
};

export type PolicyVersionDiffResponse = RegistryErrorResponse & {
  v1?: number;
  v2?: number;
  diff?: Record<string, unknown>;
};

export type PolicySchemaFieldMap = Record<string, string>;

export type PolicySchemaFieldSpec = {
  label?: string;
  type?: string;
  description?: string;
  required?: boolean;
  default?: unknown;
  placeholder?: string;
  example?: unknown;
  enum?: string[];
  minimum?: number;
  maximum?: number;
};

export type PolicySchemaType = {
  description?: string;
  aliases?: string[];
  fields?: PolicySchemaFieldMap;
  extra_fields?: PolicySchemaFieldMap;
  field_specs?: Record<string, PolicySchemaFieldSpec>;
  starter_config?: PolicyConfig;
};

export type PolicySchemaResponse = RegistryErrorResponse & {
  description?: string;
  policy_types?: Record<string, PolicySchemaType>;
  compositions?: Record<string, PolicySchemaType>;
  common_fields?: PolicySchemaFieldMap;
  common_field_specs?: Record<string, PolicySchemaFieldSpec>;
};

export type PolicyPlugin = {
  type_key: string;
  display_name: string;
  description: string;
  jurisdiction: string | null;
  category: string;
  version: string;
  starter_config: PolicyConfig;
};

export type PolicyPluginsResponse = {
  plugins: PolicyPlugin[];
  count: number;
};

export type PolicyValidationFinding = {
  severity?: string;
  message?: string;
  path?: string;
  code?: string;
};

export type PolicyValidationSummary = {
  valid?: boolean;
  error_count?: number;
  warning_count?: number;
  findings?: PolicyValidationFinding[];
};

export type PolicyProposalEvent = {
  event?: string;
  actor?: string;
  note?: string;
  created_at?: string;
};

export type PolicyProposalItem = {
  proposal_id?: string;
  action?: string;
  author?: string;
  description?: string;
  metadata?: RegistryPayload;
  base_version_number?: number | null;
  live_version_number?: number | null;
  is_stale?: boolean;
  assigned_reviewer?: string | null;
  status?: string;
  created_at?: string;
  approved_by?: string | null;
  approved_at?: string | null;
  deployed_at?: string | null;
  rejection_reason?: string | null;
  target_index?: number | null;
  new_provider_type?: string;
  replacement_provider_count?: number;
  validation?: PolicyValidationSummary;
  provider?: PolicyProviderItem;
  provider_set?: PolicyProviderItem[];
  simulation?: PolicySimulationReport;
  decision_trail?: PolicyProposalEvent[];
};

export type PolicyGovernanceResponse = RegistryErrorResponse & {
  total_proposals?: number;
  pending_count?: number;
  require_simulation?: boolean;
  require_approval?: boolean;
  current_version?: number | null;
  stale_count?: number;
  proposals?: PolicyProposalItem[];
  generated_at?: string;
};

export type PolicySimulationScenarioResult = {
  resource_id?: string;
  action?: string;
  actor_id?: string;
  label?: string;
  decision?: string;
  reason?: string;
  policy_id?: string;
  error?: string | null;
};

export type PolicySimulationReport = {
  total?: number;
  allowed?: number;
  denied?: number;
  deferred?: number;
  errors?: number;
  created_at?: string;
  results?: PolicySimulationScenarioResult[];
};

export type PolicySimulationScenario = {
  label?: string;
  resource_id?: string;
  action?: string;
  actor_id?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
};

export type PolicyManagementResponse = RegistryErrorResponse & {
  policy?: PolicyState;
  versions?: PolicyVersionsResponse;
  schema?: PolicySchemaResponse;
  governance?: PolicyGovernanceResponse;
  bundles?: PolicyBundlesResponse;
  packs?: PolicyPacksResponse;
  analytics?: PolicyAnalyticsResponse;
  environments?: PolicyEnvironmentResponse;
  promotions?: PolicyPromotionsResponse;
  simulation_defaults?: PolicySimulationScenario[];
  generated_at?: string;
};

export type PolicySnapshot = {
  format?: string;
  providers?: PolicyConfig[];
  metadata?: Record<string, unknown>;
  captured_at?: string;
};

export type PolicyExportResponse = RegistryErrorResponse & {
  kind?: string;
  version_number?: number | null;
  snapshot?: PolicySnapshot;
  suggested_filename?: string;
  generated_at?: string;
};

export type PolicyImportResponse = RegistryErrorResponse & {
  status?: string;
  summary?: {
    created?: number;
    added?: number;
    changed?: number;
    removed?: number;
    imported_provider_count?: number;
    current_provider_count?: number;
  };
  proposal?: PolicyProposalItem;
  governance?: PolicyGovernanceResponse;
  validation?: PolicyValidationSummary;
};

export type PolicyBundleItem = {
  bundle_id: string;
  title?: string;
  summary?: string;
  description?: string;
  risk_posture?: string;
  recommended_environments?: string[];
  tags?: string[];
  provider_count?: number;
  provider_summaries?: string[];
  providers?: PolicyConfig[];
};

export type PolicyBundlesResponse = RegistryErrorResponse & {
  count?: number;
  bundles?: PolicyBundleItem[];
  generated_at?: string;
};

export type PolicyPackRevision = {
  revision_id?: string;
  revision_number?: number;
  created_at?: string;
  author?: string;
  note?: string;
};

export type PolicyPackItem = {
  pack_id: string;
  title?: string;
  summary?: string;
  description?: string;
  owner?: string;
  visibility?: string;
  tags?: string[];
  recommended_environments?: string[];
  provider_count?: number;
  provider_summaries?: string[];
  snapshot?: PolicySnapshot;
  created_at?: string;
  updated_at?: string;
  revision_count?: number;
  current_revision_number?: number;
  revisions?: PolicyPackRevision[];
};

export type PolicyPacksResponse = RegistryErrorResponse & {
  count?: number;
  packs?: PolicyPackItem[];
  generated_at?: string;
};

export type PolicyEnvironmentProfile = {
  environment_id: string;
  title?: string;
  description?: string;
  goals?: string[];
  required_controls?: string[];
  warnings?: string[];
  capture_count?: number;
  current_version_number?: number | null;
  current_provider_count?: number | null;
  current_source_label?: string;
  captured_at?: string;
  captured_by?: string;
  last_capture_note?: string;
  last_promotion?: PolicyPromotionItem | null;
};

export type PolicyEnvironmentResponse = RegistryErrorResponse & {
  count?: number;
  environments?: PolicyEnvironmentProfile[];
  generated_at?: string;
};

export type PolicyPromotionEvent = {
  event?: string;
  actor?: string;
  note?: string;
  created_at?: string;
};

export type PolicyPromotionItem = {
  promotion_id?: string;
  proposal_id?: string;
  source_environment?: string;
  target_environment?: string;
  source_version_number?: number | null;
  target_version_number?: number | null;
  deployed_version_number?: number | null;
  status?: string;
  created_at?: string;
  created_by?: string;
  note?: string;
  completed_at?: string;
  decision_trail?: PolicyPromotionEvent[];
};

export type PolicyPromotionsResponse = RegistryErrorResponse & {
  count?: number;
  promotions?: PolicyPromotionItem[];
  generated_at?: string;
};

export type PolicyRiskItem = {
  level?: string;
  title?: string;
  detail?: string;
};

export type PolicyAnalyticsResponse = RegistryErrorResponse & {
  overview?: {
    provider_count?: number;
    evaluation_count?: number;
    deny_count?: number;
    current_version?: number | null;
    pending_proposals?: number;
    stale_proposals?: number;
  };
  blocked?: {
    audit?: RegistryPayload;
    recent_denials?: RegistryPayload[];
    monitor?: RegistryPayload;
    alerts?: RegistryPayload[];
  };
  changes?: {
    latest_version_from?: number | null;
    latest_version_to?: number | null;
    latest_version_summary?: RegistryPayload | null;
    recent_deployments?: PolicyProposalItem[];
  };
  history?: {
    snapshots?: RegistryPayload[];
    sample_count?: number;
    deltas?: RegistryPayload;
    recent_promotions?: PolicyPromotionItem[];
  };
  risks?: PolicyRiskItem[];
  generated_at?: string;
};

export type PolicyMigrationPreviewResponse = RegistryErrorResponse & {
  source?: {
    label?: string;
    version_number?: number | null;
    provider_count?: number;
  };
  target?: {
    label?: string;
    version_number?: number | null;
    provider_count?: number;
  };
  environment?: PolicyEnvironmentProfile;
  summary?: RegistryPayload;
  recommendations?: string[];
  risks?: PolicyRiskItem[];
  suggested_snapshot?: PolicySnapshot;
  generated_at?: string;
};

function backendBase() {
  return process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
}

async function parseJson<T>(response: Response): Promise<T | null> {
  return (await response.json().catch(() => null)) as T | null;
}

async function backendFetch(path: string, init?: RequestInit) {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get("purecipher_registry_token");

  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");

  if (sessionCookie) {
    headers.set("cookie", `${sessionCookie.name}=${sessionCookie.value}`);
  }

  const response = await fetch(`${backendBase()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  return response;
}

export async function getRegistrySession(): Promise<RegistrySessionResponse | null> {
  const response = await backendFetch("/registry/session");
  if (!response.ok) {
    return null;
  }
  return parseJson<RegistrySessionResponse>(response);
}

export async function listVerifiedTools(): Promise<RegistryToolCatalogResponse | null> {
  const response = await backendFetch("/registry/tools");
  if (!response.ok) {
    return null;
  }
  return parseJson<RegistryToolCatalogResponse>(response);
}

export async function getToolDetail(toolName: string): Promise<RegistryToolListing | RegistryErrorResponse | null> {
  const response = await backendFetch(`/registry/tools/${encodeURIComponent(toolName)}`);
  return parseJson<RegistryToolListing | RegistryErrorResponse>(response);
}

export async function getInstallRecipes(toolName: string): Promise<InstallRecipesResponse | null> {
  const response = await backendFetch(`/registry/install/${encodeURIComponent(toolName)}`);
  return parseJson<InstallRecipesResponse>(response);
}

export async function listPublishers(): Promise<PublisherDirectoryResponse | null> {
  const response = await backendFetch("/registry/publishers");
  return parseJson<PublisherDirectoryResponse>(response);
}

export async function getPublisherProfile(
  publisherId: string,
): Promise<PublisherProfileResponse | null> {
  const response = await backendFetch(`/registry/publishers/${encodeURIComponent(publisherId)}`);
  return parseJson<PublisherProfileResponse>(response);
}

export async function getReviewQueue(): Promise<ReviewQueueResponse | null> {
  const response = await backendFetch("/registry/review/submissions");
  return parseJson<ReviewQueueResponse>(response);
}

export async function requirePublisherRole(): Promise<{ allowed: boolean; role: string | null }> {
  const session = await getRegistrySession();
  const role = session?.session?.role ?? null;
  const allowed = role === "publisher" || role === "reviewer" || role === "admin";
  return { allowed, role };
}

export async function requirePolicyRole(): Promise<{ allowed: boolean; role: string | null }> {
  const session = await getRegistrySession();
  const role = session?.session?.role ?? null;
  const allowed = role === "reviewer" || role === "admin";
  return { allowed, role };
}

export async function getRegistryHealth(): Promise<RegistryHealthResponse | null> {
  const response = await backendFetch("/registry/health");
  if (!response.ok) {
    return null;
  }
  return parseJson<RegistryHealthResponse>(response);
}

export async function getPolicyManagement(): Promise<PolicyManagementResponse | null> {
  const response = await backendFetch("/registry/policy");
  return parseJson<PolicyManagementResponse>(response);
}

export async function getPolicyVersions(): Promise<PolicyVersionsResponse | null> {
  const response = await backendFetch("/registry/policy/versions");
  return parseJson<PolicyVersionsResponse>(response);
}

export async function listPolicyPlugins(
  jurisdiction?: string,
): Promise<PolicyPluginsResponse | null> {
  const params = new URLSearchParams();
  if (jurisdiction) params.set("jurisdiction", jurisdiction);
  const qs = params.toString();
  const response = await backendFetch(
    `/registry/policy/plugins${qs ? `?${qs}` : ""}`,
  );
  return parseJson<PolicyPluginsResponse>(response);
}

export async function verifyTool(toolName: string): Promise<ToolVerificationResponse | null> {
  const response = await backendFetch("/registry/verify", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ tool_name: toolName }),
  });
  return parseJson<ToolVerificationResponse>(response);
}

// ── Provenance API ──────────────────────────────────────────────

export type ProvenanceRecord = {
  record_id: string;
  action: string;
  actor_id: string;
  resource_id: string;
  timestamp: string;
  input_hash: string;
  output_hash: string;
  metadata: Record<string, unknown>;
  previous_hash: string;
  contract_id: string;
  session_id: string;
};

export type ProvenanceQueryResponse = {
  total_records: number;
  returned: number;
  records: ProvenanceRecord[];
  generated_at: string;
};

export type ProvenanceChainStatus = {
  ledger_id: string;
  record_count: number;
  chain_valid: boolean;
  tree_valid: boolean;
  root_hash: string;
  chain_digest: string;
  scheme: {
    scheme: string;
    leaf_count: number;
    root_hash: string;
    tree_valid: boolean;
    anchor_count?: number;
    anchors_valid?: boolean;
    records_since_anchor?: number;
    anchor_interval?: number;
    latest_anchor?: Record<string, unknown> | null;
  };
  generated_at: string;
};

export type ProvenanceProofResponse = {
  bundle?: {
    record: Record<string, unknown>;
    merkle_proof: {
      leaf_hash: string;
      proof_hashes: string[];
      directions: string[];
      root_hash: string;
    };
    chain_context: {
      predecessor_hash: string;
      successor_hash: string;
    };
    ledger_state: {
      root_hash: string;
      record_count: number;
    };
    exported_at: string;
  };
  status?: string;
  error?: string;
};

export type ProvenanceActionType = {
  value: string;
  name: string;
};

export type ProvenanceActionsResponse = {
  actions: ProvenanceActionType[];
};

export type ProvenanceVerifyResult = {
  valid: boolean;
  checks: Record<string, boolean>;
  record_id: string;
  details: string;
};

export type ProvenanceExportResponse = {
  format: string;
  exported_at: string;
  record_count: number;
  merkle_root: string;
  chain_digest: string;
  records: Array<Record<string, unknown>>;
};

export async function getProvenanceRecords(
  params?: { resource?: string; actor?: string; action?: string; limit?: number },
): Promise<ProvenanceQueryResponse | null> {
  const qs = new URLSearchParams();
  if (params?.resource) qs.set("resource", params.resource);
  if (params?.actor) qs.set("actor", params.actor);
  if (params?.action) qs.set("action", params.action);
  if (params?.limit) qs.set("limit", String(params.limit));
  const q = qs.toString();
  const response = await backendFetch(
    `/security/provenance${q ? `?${q}` : ""}`,
  );
  return parseJson<ProvenanceQueryResponse>(response);
}

export async function getProvenanceChainStatus(): Promise<ProvenanceChainStatus | null> {
  const response = await backendFetch("/security/provenance/chain-status");
  return parseJson<ProvenanceChainStatus>(response);
}

export async function getProvenanceActions(): Promise<ProvenanceActionsResponse | null> {
  const response = await backendFetch("/security/provenance/actions");
  return parseJson<ProvenanceActionsResponse>(response);
}

export async function getProvenanceProof(
  recordId: string,
): Promise<ProvenanceProofResponse | null> {
  const response = await backendFetch(
    `/security/provenance/proof/${encodeURIComponent(recordId)}`,
  );
  return parseJson<ProvenanceProofResponse>(response);
}

export async function getProvenanceExport(): Promise<ProvenanceExportResponse | null> {
  const response = await backendFetch("/security/provenance/export");
  return parseJson<ProvenanceExportResponse>(response);
}

export async function verifyProvenanceBundle(
  bundle: Record<string, unknown>,
): Promise<ProvenanceVerifyResult | null> {
  const response = await backendFetch("/security/provenance/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bundle),
  });
  return parseJson<ProvenanceVerifyResult>(response);
}
