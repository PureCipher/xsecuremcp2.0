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
  bootstrap_required?: boolean;
  setup_url?: string | null;
  session?: RegistrySessionInfo | null;
};

export type RegistryUserPreferences = {
  notifications?: {
    publishUpdates?: boolean;
    reviewQueue?: boolean;
    policyChanges?: boolean;
    securityAlerts?: boolean;
  };
  workspace?: {
    defaultLandingPage?: string;
    density?: "comfortable" | "compact";
  };
  publisher?: {
    defaultCertification?: "basic" | "standard" | "advanced";
    openMineFirst?: boolean;
  };
  reviewer?: {
    defaultLane?: "pending" | "approved" | "rejected";
    highRiskFirst?: boolean;
  };
  admin?: {
    defaultAdminView?: "health" | "policy" | "settings";
    requireConfirmations?: boolean;
  };
};

export type RegistryUserPreferencesResponse = RegistryErrorResponse & {
  username?: string;
  preferences?: RegistryUserPreferences;
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

export type RegistryUpstreamRef = {
  channel?: string;
  identifier?: string;
  version?: string;
  pinned_hash?: string;
  source_url?: string;
  metadata?: Record<string, unknown>;
};

export type RegistryToolListing = {
  listing_id?: string;
  status?: string;
  tool_name: string;
  display_name?: string;
  description?: string;
  categories?: string[];
  certification_level?: string;
  publisher_id?: string;
  version?: string;
  author?: string;
  manifest?: RegistryManifestSummary | RegistryPayload | null;
  metadata?: RegistryPayload;
  // Curator-attestation fields. Present only on listings produced by
  // the third-party onboarding flow (`/registry/onboard`).
  attestation_kind?: "author" | "curator" | string;
  curator_id?: string;
  hosting_mode?: "catalog" | "proxy" | string;
  upstream_ref?: RegistryUpstreamRef | null;
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
  // ``listing_count`` is the canonical count emitted by the registry
  // backend (number of *published* listings that belong to the
  // publisher). ``tool_count`` / ``verified_tool_count`` are kept as
  // optional aliases in case other surfaces emit one of those names.
  listing_count?: number;
  tool_count?: number;
  verified_tool_count?: number;
  trust_score?: PublisherTrustScore | null;
};

export type PublisherDirectoryResponse = RegistryErrorResponse & {
  count?: number;
  publishers?: PublisherSummary[];
  generated_at?: string;
};

// The backend emits the publisher summary FLAT at the top level
// (publisher_id, display_name, listing_count, etc.) plus a
// ``listings`` array of full tool listings — see
// ``PublisherProfile.to_dict`` in src/purecipher/models.py. The
// response shape is the union of those fields.
export type PublisherProfileResponse = RegistryErrorResponse &
  Partial<PublisherSummary> & {
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
  trust_score?: number | null;
  description?: string;
  moderation_log?: ReviewLogEntry[];
  available_actions?: string[];
};

export type ReviewQueueResponse = RegistryErrorResponse & {
  counts?: Record<string, number>;
  sections?: Record<string, ReviewQueueItem[]>;
};

export type MyListingsResponse = RegistryErrorResponse & {
  count?: number;
  tools?: RegistryToolListing[];
  generated_at?: string;
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

export async function getRegistryUserPreferences(): Promise<RegistryUserPreferencesResponse | null> {
  const response = await backendFetch("/registry/me/preferences");
  if (!response.ok) {
    return null;
  }
  return parseJson<RegistryUserPreferencesResponse>(response);
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

export type ToolVersionItem = {
  version: string;
  published_at?: string;
  changelog?: string;
  yanked?: boolean;
  yank_reason?: string;
  manifest_digest?: string;
  attestation_id?: string;
};

export type ToolVersionsResponse = RegistryErrorResponse & {
  tool_name?: string;
  listing_id?: string;
  current_version?: string;
  status?: string;
  version_count?: number;
  versions?: ToolVersionItem[];
  generated_at?: string;
};

export async function getToolVersions(toolName: string): Promise<ToolVersionsResponse | null> {
  const response = await backendFetch(
    `/registry/tools/${encodeURIComponent(toolName)}/versions`,
  );
  return parseJson<ToolVersionsResponse>(response);
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

// ── Server governance — Policy Kernel ───────────────────────────
//
// Iteration 1 of the MCP-Server profile's Governance tab. Replaces
// the previous "Policy Kernel: inherited (stub)" placeholder with a
// real, derived view of how policy applies to each of the
// publisher's listings. See ``PureCipherRegistry
// .get_server_policy_governance`` in src/purecipher/registry.py for
// the canonical contract.

export type ServerRegistryPolicyBlock = {
  available: boolean;
  error?: string;
  policy_set_id?: string | null;
  current_version?: number | null;
  version_count?: number | null;
  fail_closed?: boolean | null;
  allow_hot_swap?: boolean | null;
  provider_count?: number | null;
  evaluation_count?: number | null;
  deny_count?: number | null;
};

export type ServerPolicyProvider = {
  type: string;
  policy_id?: string;
  fail_closed?: boolean;
  allowed_count?: number;
  allowed_sample?: string[];
};

// ``binding_source`` is the canonical field describing what gates
// calls to a tool:
//
// - ``inherited``       — no listing-specific policy at the registry
//                         layer (catalog-only listings, or proxy
//                         listings without a curator-vouched tool
//                         surface).
// - ``proxy_allowlist`` — proxy-mode curator listing whose
//                         AllowlistPolicy gates calls against the
//                         curator-vouched tool surface.
export type ServerPolicyBindingSource = "inherited" | "proxy_allowlist";

export type ServerPolicyToolBinding = {
  listing_id: string;
  tool_name: string;
  display_name?: string;
  hosting_mode?: "catalog" | "proxy" | string | null;
  attestation_kind?: "author" | "curator" | string | null;
  status?: string;
  binding_source: ServerPolicyBindingSource | string;
  policy_provider: ServerPolicyProvider | null;
};

export type ServerPolicyGovernanceSummary = {
  tool_count: number;
  inherited_count: number;
  overridden_count: number;
};

export type ServerPolicyGovernanceResponse = RegistryErrorResponse & {
  server_id?: string;
  registry_policy?: ServerRegistryPolicyBlock;
  per_tool_policies?: ServerPolicyToolBinding[];
  summary?: ServerPolicyGovernanceSummary;
  links?: { policy_kernel_url?: string };
  generated_at?: string;
};

export async function getServerPolicyGovernance(
  serverId: string,
): Promise<ServerPolicyGovernanceResponse | null> {
  const response = await backendFetch(
    `/registry/servers/${encodeURIComponent(serverId)}/governance/policy`,
  );
  return parseJson<ServerPolicyGovernanceResponse>(response);
}

// ── Server governance — Contract Broker ─────────────────────────
//
// Iteration 2 of the MCP-Server profile's Governance tab. Renders
// the registry's Context Broker availability + per-tool agent-
// contract bindings. See ``PureCipherRegistry
// .get_server_contract_governance`` in src/purecipher/registry.py
// for the canonical contract.

export type ServerBrokerDefaultTerm = {
  term_id?: string;
  term_type?: string;
  description?: string;
  required?: boolean;
};

export type ServerBrokerBlock = {
  available: boolean;
  reason?: string;
  broker_id?: string;
  server_id?: string;
  max_rounds?: number | null;
  contract_duration_seconds?: number | null;
  session_timeout_seconds?: number | null;
  default_term_count?: number;
  default_terms?: ServerBrokerDefaultTerm[];
  active_contract_count?: number;
  negotiation_session_count?: number;
  exchange_log_session_count?: number;
  exchange_log_entry_count?: number;
};

// ``binding_source`` for contract bindings:
//
// - ``no_contracts``    — no active contract has terms that
//                         reference this tool by name or pattern.
// - ``agent_contracts`` — at least one active contract carries a
//                         term whose constraint references this
//                         tool. ``matching_agents`` lists up to 5
//                         distinct agent_ids.
export type ServerContractBindingSource =
  | "no_contracts"
  | "agent_contracts";

export type ServerContractToolBinding = {
  listing_id: string;
  tool_name: string;
  display_name?: string;
  hosting_mode?: "catalog" | "proxy" | string | null;
  attestation_kind?: "author" | "curator" | string | null;
  status?: string;
  binding_source: ServerContractBindingSource | string;
  matching_contract_count: number;
  matching_agents: string[];
};

export type ServerContractGovernanceSummary = {
  tool_count: number;
  contracted_count: number;
  uncontracted_count: number;
};

export type ServerContractGovernanceResponse = RegistryErrorResponse & {
  server_id?: string;
  broker?: ServerBrokerBlock;
  per_tool_contracts?: ServerContractToolBinding[];
  summary?: ServerContractGovernanceSummary;
  links?: { contract_broker_url?: string };
  generated_at?: string;
};

export async function getServerContractGovernance(
  serverId: string,
): Promise<ServerContractGovernanceResponse | null> {
  const response = await backendFetch(
    `/registry/servers/${encodeURIComponent(serverId)}/governance/contracts`,
  );
  return parseJson<ServerContractGovernanceResponse>(response);
}

// ── Server governance — Consent Graph ───────────────────────────
//
// Iteration 3 of the MCP-Server profile's Governance tab. Combines
// the deterministic ``SecurityManifest.requires_consent`` signal with
// a best-effort scan of the Consent Graph for edges that reference
// each tool. See ``PureCipherRegistry.get_server_consent_governance``
// in src/purecipher/registry.py for the canonical contract.

export type ServerConsentGraphBlock = {
  available: boolean;
  reason?: string;
  graph_id?: string;
  node_count?: number;
  edge_count?: number;
  active_edge_count?: number;
  node_counts_by_type?: Record<string, number>;
  audit_entry_count?: number;
};

export type ServerConsentFederationBlock = {
  available: boolean;
  reason?: string;
  institution_id?: string;
  jurisdiction_count?: number;
  peer_count?: number;
};

// ``binding_source`` for consent bindings reflects the LISTING's
// stated posture (manifest.requires_consent), not graph activity.
// Graph grants are tracked separately on ``graph_grant_count``.
export type ServerConsentBindingSource =
  | "consent_required"
  | "consent_optional";

export type ServerConsentToolBinding = {
  listing_id: string;
  tool_name: string;
  display_name?: string;
  hosting_mode?: "catalog" | "proxy" | string | null;
  attestation_kind?: "author" | "curator" | string | null;
  status?: string;
  requires_consent: boolean;
  binding_source: ServerConsentBindingSource | string;
  graph_grant_count: number;
  grant_sources: string[];
};

export type ServerConsentGovernanceSummary = {
  tool_count: number;
  requires_consent_count: number;
  with_grants_count: number;
  without_grants_count: number;
};

export type ServerConsentGovernanceResponse = RegistryErrorResponse & {
  server_id?: string;
  consent_graph?: ServerConsentGraphBlock;
  federation?: ServerConsentFederationBlock;
  per_tool_consent?: ServerConsentToolBinding[];
  summary?: ServerConsentGovernanceSummary;
  links?: { consent_graph_url?: string };
  generated_at?: string;
};

export async function getServerConsentGovernance(
  serverId: string,
): Promise<ServerConsentGovernanceResponse | null> {
  const response = await backendFetch(
    `/registry/servers/${encodeURIComponent(serverId)}/governance/consent`,
  );
  return parseJson<ServerConsentGovernanceResponse>(response);
}

// ── Server governance — Provenance Ledger ───────────────────────
//
// Iteration 4 of the MCP-Server profile's Governance tab. Surfaces
// the registry-wide ledger plus per-tool ledger bindings (proxy
// listings get a dedicated ledger at gateway mount; catalog listings
// have no registry-attached ledger). See ``PureCipherRegistry
// .get_server_ledger_governance``.

export type ServerLedgerBlock = {
  available: boolean;
  reason?: string;
  ledger_id?: string;
  record_count?: number;
  root_hash?: string;
  latest_record_at?: string | null;
  latest_record_action?: string | null;
  latest_record_resource_id?: string | null;
  scheme_name?: string | null;
};

export type ServerLedgerBindingSource = "proxy_ledger" | "no_ledger";

export type ServerLedgerToolBinding = {
  listing_id: string;
  tool_name: string;
  display_name?: string;
  hosting_mode?: "catalog" | "proxy" | string | null;
  attestation_kind?: "author" | "curator" | string | null;
  status?: string;
  binding_source: ServerLedgerBindingSource | string;
  expected_ledger_id?: string | null;
  central_record_count: number;
  latest_central_record_at?: string | null;
  latest_central_record_action?: string | null;
};

export type ServerLedgerGovernanceSummary = {
  tool_count: number;
  with_proxy_ledger_count: number;
  with_central_records_count: number;
  total_central_records_for_tools: number;
};

export type ServerLedgerGovernanceResponse = RegistryErrorResponse & {
  server_id?: string;
  ledger?: ServerLedgerBlock;
  per_tool_ledger?: ServerLedgerToolBinding[];
  summary?: ServerLedgerGovernanceSummary;
  links?: { provenance_ledger_url?: string };
  generated_at?: string;
};

export async function getServerLedgerGovernance(
  serverId: string,
): Promise<ServerLedgerGovernanceResponse | null> {
  const response = await backendFetch(
    `/registry/servers/${encodeURIComponent(serverId)}/governance/ledger`,
  );
  return parseJson<ServerLedgerGovernanceResponse>(response);
}

// ── Server governance — Overrides ───────────────────────────────
//
// Iteration 5 of the MCP-Server profile's Governance tab. Rolls up
// operator/moderator interventions across all of a server's tools.
// See ``PureCipherRegistry.get_server_overrides_governance``.

export type ServerModerationDecision = {
  decision_id?: string;
  listing_id?: string;
  moderator_id?: string;
  action: string;
  reason?: string;
  created_at?: string;
  metadata?: Record<string, unknown>;
  // Tagged onto the cross-tool feed only.
  tool_name?: string;
  display_name?: string;
};

export type ServerOverrideToolBinding = {
  listing_id: string;
  tool_name: string;
  display_name?: string;
  hosting_mode?: "catalog" | "proxy" | string | null;
  attestation_kind?: "author" | "curator" | string | null;
  status: string;
  binding_source:
    | "moderation_pending"
    | "moderated"
    | "yanked_versions"
    | "active"
    | string;
  moderation: {
    open: boolean;
    log_entries: number;
    latest_action?: string | null;
    latest_at?: string | null;
    latest_reason?: string | null;
    latest_moderator_id?: string | null;
    log: ServerModerationDecision[];
  };
  policy_override: {
    active: boolean;
    allowed_count: number;
  };
  yanked_versions: {
    version: string;
    yanked: boolean;
    yank_reason: string;
    published_at?: string | null;
  }[];
};

export type ServerOverridesGovernanceSummary = {
  tool_count: number;
  draft_count: number;
  pending_review_count: number;
  published_count: number;
  suspended_count: number;
  deprecated_count: number;
  rejected_count: number;
  yanked_version_count: number;
  policy_override_count: number;
  open_moderation_actions: number;
};

export type ServerOverridesGovernanceResponse = RegistryErrorResponse & {
  server_id?: string;
  summary?: ServerOverridesGovernanceSummary;
  per_tool_overrides?: ServerOverrideToolBinding[];
  recent_moderation_decisions?: ServerModerationDecision[];
  links?: { moderation_queue_url?: string };
  generated_at?: string;
};

export async function getServerOverridesGovernance(
  serverId: string,
): Promise<ServerOverridesGovernanceResponse | null> {
  const response = await backendFetch(
    `/registry/servers/${encodeURIComponent(serverId)}/governance/overrides`,
  );
  return parseJson<ServerOverridesGovernanceResponse>(response);
}

// ── Server observability — Reflexive Core ───────────────────────
//
// Iteration 6: powers the Observability tab on the server profile.
// The endpoint lives at ``/observability`` (sibling to
// ``/governance/*``) because observability is its own tab. See
// ``PureCipherRegistry.get_server_observability``.

export type ServerSeverityDistribution = {
  info: number;
  low: number;
  medium: number;
  high: number;
  critical: number;
};

export type ServerAnalyzerBlock = {
  available: boolean;
  reason?: string;
  analyzer_id?: string;
  total_drift_count?: number;
  monitored_actor_count?: number;
  tracked_metric_count?: number;
  tracked_metrics?: string[];
  detector_count?: number;
  min_samples?: number;
  severity_distribution?: ServerSeverityDistribution;
  latest_drift_at?: string | null;
  latest_drift_severity?: string | null;
  latest_drift_actor_id?: string | null;
};

export type ServerObservabilityBindingSource =
  | "monitored"
  | "no_observations";

export type ServerObservabilityToolBinding = {
  listing_id: string;
  tool_name: string;
  display_name?: string;
  hosting_mode?: "catalog" | "proxy" | string | null;
  attestation_kind?: "author" | "curator" | string | null;
  status?: string;
  binding_source: ServerObservabilityBindingSource | string;
  drift_event_count: number;
  severity_distribution: ServerSeverityDistribution;
  highest_severity?: string | null;
  latest_drift_at?: string | null;
  latest_drift_severity?: string | null;
};

export type ServerDriftEvent = {
  event_id?: string;
  drift_type?: string | null;
  severity?: string | null;
  actor_id?: string;
  description?: string;
  observed_value?: number | null;
  baseline_value?: number | null;
  deviation?: number | null;
  timestamp?: string | null;
  // Tagged on by the backend when the event matched one of this
  // server's tools.
  tool_name?: string | null;
  display_name?: string | null;
};

export type ServerObservabilitySummary = {
  tool_count: number;
  monitored_count: number;
  with_high_drift_count: number;
  with_critical_drift_count: number;
};

export type ServerObservabilityResponse = RegistryErrorResponse & {
  server_id?: string;
  analyzer?: ServerAnalyzerBlock;
  per_tool_observability?: ServerObservabilityToolBinding[];
  recent_drift_events?: ServerDriftEvent[];
  summary?: ServerObservabilitySummary;
  links?: { reflexive_core_url?: string };
  generated_at?: string;
};

export async function getServerObservability(
  serverId: string,
): Promise<ServerObservabilityResponse | null> {
  const response = await backendFetch(
    `/registry/servers/${encodeURIComponent(serverId)}/observability`,
  );
  return parseJson<ServerObservabilityResponse>(response);
}

// ── Per-listing governance + observability rollup ───────────────
//
// Iteration 7: scoped to a single listing. Mirror of the
// publisher-scoped views, composed from the same projections so
// per-listing and per-publisher answers are guaranteed identical.
// See ``PureCipherRegistry.get_listing_governance``.

export type ListingPolicyBlock = {
  registry_policy: ServerRegistryPolicyBlock;
  // The plane-specific row fields (binding_source, policy_provider, ...).
  binding_source: string;
  policy_provider: ServerPolicyProvider | null;
  hosting_mode?: string | null;
  attestation_kind?: string | null;
  status?: string;
  listing_id?: string;
  tool_name?: string;
  display_name?: string;
};

export type ListingContractsBlock = {
  broker: ServerBrokerBlock;
  binding_source: string;
  matching_contract_count: number;
  matching_agents: string[];
  hosting_mode?: string | null;
  attestation_kind?: string | null;
  status?: string;
};

export type ListingConsentBlock = {
  consent_graph: ServerConsentGraphBlock;
  requires_consent: boolean;
  binding_source: string;
  graph_grant_count: number;
  grant_sources: string[];
  hosting_mode?: string | null;
  attestation_kind?: string | null;
  status?: string;
};

export type ListingLedgerBlock = {
  ledger: ServerLedgerBlock;
  binding_source: string;
  expected_ledger_id?: string | null;
  central_record_count: number;
  latest_central_record_at?: string | null;
  latest_central_record_action?: string | null;
  hosting_mode?: string | null;
  attestation_kind?: string | null;
  status?: string;
};

export type ListingOverridesBlock = {
  binding_source: string;
  status: string;
  moderation: {
    open: boolean;
    log_entries: number;
    latest_action?: string | null;
    latest_at?: string | null;
    latest_reason?: string | null;
    latest_moderator_id?: string | null;
    log: ServerModerationDecision[];
  };
  policy_override: {
    active: boolean;
    allowed_count: number;
  };
  yanked_versions: {
    version: string;
    yanked: boolean;
    yank_reason: string;
    published_at?: string | null;
  }[];
};

export type ListingObservabilityBlock = {
  analyzer: ServerAnalyzerBlock;
  binding_source: string;
  drift_event_count: number;
  severity_distribution: ServerSeverityDistribution;
  highest_severity?: string | null;
  latest_drift_at?: string | null;
  latest_drift_severity?: string | null;
};

export type ListingGovernanceResponse = RegistryErrorResponse & {
  listing_id?: string;
  tool_name?: string;
  display_name?: string;
  publisher_id?: string;
  hosting_mode?: string | null;
  attestation_kind?: string | null;
  status?: string;
  policy?: ListingPolicyBlock;
  contracts?: ListingContractsBlock;
  consent?: ListingConsentBlock;
  ledger?: ListingLedgerBlock;
  overrides?: ListingOverridesBlock;
  observability?: ListingObservabilityBlock;
  links?: {
    policy_kernel_url?: string;
    contract_broker_url?: string;
    consent_graph_url?: string;
    provenance_ledger_url?: string;
    moderation_queue_url?: string;
    reflexive_core_url?: string;
    publisher_url?: string;
  };
  generated_at?: string;
};

export async function getListingGovernance(
  toolName: string,
): Promise<ListingGovernanceResponse | null> {
  const response = await backendFetch(
    `/registry/tools/${encodeURIComponent(toolName)}/governance`,
  );
  return parseJson<ListingGovernanceResponse>(response);
}

// ── Iter 9: runtime control-plane toggles ──────────────────────
//
// Admin-only. Powers the /registry/settings/control-planes page.

export type ControlPlaneName =
  | "contracts"
  | "consent"
  | "provenance"
  | "reflexive";

export type ControlPlaneSetting = {
  plane: string;
  enabled: boolean;
  updated_at: number;
  updated_by: string;
};

export type ControlPlaneEntry = {
  plane: string;
  enabled: boolean;
  description: string;
  persisted: ControlPlaneSetting | null;
};

export type ControlPlaneStatusResponse = RegistryErrorResponse & {
  planes?: ControlPlaneEntry[];
  generated_at?: string;
};

export async function getControlPlaneStatus(): Promise<ControlPlaneStatusResponse | null> {
  const response = await backendFetch("/registry/admin/control-planes");
  return parseJson<ControlPlaneStatusResponse>(response);
}

export async function setControlPlaneEnabled(
  plane: string,
  enabled: boolean,
): Promise<ControlPlaneStatusResponse | null> {
  const response = await backendFetch(
    `/registry/admin/control-planes/${encodeURIComponent(plane)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    },
  );
  return parseJson<ControlPlaneStatusResponse>(response);
}

// ── Iter 10: MCP client identities ────────────────────────────
//
// Backs the /registry/clients directory + per-client detail pages.
// Each client has a stable slug that flows through every plane as
// the request's `actor_id` (see ClientActorResolverMiddleware on
// the backend), so per-client governance can roll up real
// telemetry rather than synthetic placeholders.

export type RegistryClientKind =
  | "agent"
  | "service"
  | "framework"
  | "tooling"
  | "other";

export type RegistryClientSummary = {
  client_id: string;
  slug: string;
  display_name: string;
  description: string;
  intended_use: string;
  kind: RegistryClientKind | string;
  owner_publisher_id: string;
  status: "active" | "suspended" | string;
  suspended_reason: string;
  created_at: number;
  updated_at: number;
  metadata: Record<string, unknown>;
};

export type RegistryClientTokenSummary = {
  token_id: string;
  client_id: string;
  name: string;
  secret_prefix: string;
  created_by: string;
  created_at: number;
  revoked_at: number | null;
  last_used_at: number | null;
  active: boolean;
};

export type RegistryClientListResponse = RegistryErrorResponse & {
  items?: RegistryClientSummary[];
  count?: number;
  kinds?: string[];
};

export type RegistryClientDetailResponse = RegistryErrorResponse & {
  client?: RegistryClientSummary;
  tokens?: RegistryClientTokenSummary[];
};

export type RegistryClientCreatePayload = {
  display_name: string;
  slug?: string;
  description?: string;
  intended_use?: string;
  kind?: RegistryClientKind;
  owner_publisher_id?: string;
  issue_initial_token?: boolean;
  token_name?: string;
  metadata?: Record<string, unknown>;
};

export type RegistryClientCreateResponse = RegistryErrorResponse & {
  client?: RegistryClientSummary;
  token?: RegistryClientTokenSummary | null;
  // Plain bearer secret. Server returns it exactly once; UI must
  // surface it to the operator and never persist it.
  secret?: string | null;
};

export type RegistryClientUpdatePayload = {
  display_name?: string;
  description?: string;
  intended_use?: string;
  kind?: RegistryClientKind;
  metadata?: Record<string, unknown>;
};

export type RegistryClientMutationResponse = RegistryErrorResponse & {
  client?: RegistryClientSummary;
};

export type RegistryClientTokensResponse = RegistryErrorResponse & {
  client_id?: string;
  items?: RegistryClientTokenSummary[];
  count?: number;
};

export type RegistryClientIssueTokenResponse = RegistryErrorResponse & {
  token?: RegistryClientTokenSummary;
  // Plain bearer secret. One-shot — see note above.
  secret?: string;
};

export type RegistryClientTokenMutationResponse = RegistryErrorResponse & {
  token?: RegistryClientTokenSummary;
};

// ── Per-client governance projection ──────────────────────────

export type ClientGovernanceContractRow = {
  contract_id?: string;
  server_id?: string;
  session_id?: string;
  status?: string;
  created_at?: string | null;
  expires_at?: string | null;
};

export type ClientGovernanceConsentRow = {
  edge_id?: string;
  source_id?: string;
  target_id?: string;
  scopes?: string[];
  status?: string;
  delegatable?: boolean;
};

export type ClientGovernanceLedgerRow = {
  record_id?: string;
  action?: string;
  resource_id?: string;
  timestamp?: string | null;
  contract_id?: string | null;
};

export type ClientGovernanceDriftRow = {
  event_id?: string;
  drift_type?: string;
  severity?: string;
  observed_value?: unknown;
  baseline_value?: unknown;
  deviation?: unknown;
  timestamp?: string | null;
};

export type ClientGovernanceBaseline = {
  metric_name: string;
  mean?: unknown;
  stddev?: unknown;
  samples?: unknown;
};

export type ClientGovernanceResponse = RegistryErrorResponse & {
  client_id?: string;
  slug?: string;
  display_name?: string;
  kind?: string;
  owner_publisher_id?: string;
  status?: string;
  suspended_reason?: string;
  intended_use?: string;
  description?: string;
  created_at?: number;
  updated_at?: number;
  policy?: {
    registry_policy?: Record<string, unknown>;
    actor_history?: null;
    note?: string;
  };
  contracts?: {
    broker?: Record<string, unknown>;
    active_count?: number;
    active_contracts?: ClientGovernanceContractRow[];
  };
  consent?: {
    consent_graph?: Record<string, unknown>;
    outgoing_count?: number;
    incoming_count?: number;
    edges_from?: ClientGovernanceConsentRow[];
    edges_to?: ClientGovernanceConsentRow[];
  };
  ledger?: {
    ledger?: Record<string, unknown>;
    record_count?: number;
    recent_records?: ClientGovernanceLedgerRow[];
  };
  reflexive?: {
    analyzer?: Record<string, unknown>;
    drift_event_count?: number;
    severity_distribution?: Record<string, number>;
    recent_drifts?: ClientGovernanceDriftRow[];
    baselines?: Record<string, ClientGovernanceBaseline>;
  };
  tokens?: {
    total?: number;
    active?: number;
    revoked?: number;
    items?: RegistryClientTokenSummary[];
  };
  links?: Record<string, string>;
  generated_at?: string;
};

export async function listRegistryClients(): Promise<RegistryClientListResponse | null> {
  const response = await backendFetch("/registry/clients");
  return parseJson<RegistryClientListResponse>(response);
}

export async function getRegistryClient(
  clientIdOrSlug: string,
): Promise<RegistryClientDetailResponse | null> {
  const response = await backendFetch(
    `/registry/clients/${encodeURIComponent(clientIdOrSlug)}`,
  );
  return parseJson<RegistryClientDetailResponse>(response);
}

export async function createRegistryClient(
  payload: RegistryClientCreatePayload,
): Promise<RegistryClientCreateResponse | null> {
  const response = await backendFetch("/registry/clients", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson<RegistryClientCreateResponse>(response);
}

export async function updateRegistryClient(
  clientIdOrSlug: string,
  patch: RegistryClientUpdatePayload,
): Promise<RegistryClientMutationResponse | null> {
  const response = await backendFetch(
    `/registry/clients/${encodeURIComponent(clientIdOrSlug)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    },
  );
  return parseJson<RegistryClientMutationResponse>(response);
}

export async function suspendRegistryClient(
  clientIdOrSlug: string,
  reason?: string,
): Promise<RegistryClientMutationResponse | null> {
  const response = await backendFetch(
    `/registry/clients/${encodeURIComponent(clientIdOrSlug)}/suspend`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason ?? "" }),
    },
  );
  return parseJson<RegistryClientMutationResponse>(response);
}

export async function unsuspendRegistryClient(
  clientIdOrSlug: string,
): Promise<RegistryClientMutationResponse | null> {
  const response = await backendFetch(
    `/registry/clients/${encodeURIComponent(clientIdOrSlug)}/unsuspend`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
  return parseJson<RegistryClientMutationResponse>(response);
}

export async function listRegistryClientTokens(
  clientIdOrSlug: string,
): Promise<RegistryClientTokensResponse | null> {
  const response = await backendFetch(
    `/registry/clients/${encodeURIComponent(clientIdOrSlug)}/tokens`,
  );
  return parseJson<RegistryClientTokensResponse>(response);
}

export async function issueRegistryClientToken(
  clientIdOrSlug: string,
  name: string,
): Promise<RegistryClientIssueTokenResponse | null> {
  const response = await backendFetch(
    `/registry/clients/${encodeURIComponent(clientIdOrSlug)}/tokens`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    },
  );
  return parseJson<RegistryClientIssueTokenResponse>(response);
}

export async function revokeRegistryClientToken(
  clientIdOrSlug: string,
  tokenId: string,
): Promise<RegistryClientTokenMutationResponse | null> {
  const response = await backendFetch(
    `/registry/clients/${encodeURIComponent(clientIdOrSlug)}` +
      `/tokens/${encodeURIComponent(tokenId)}`,
    {
      method: "DELETE",
    },
  );
  return parseJson<RegistryClientTokenMutationResponse>(response);
}

export async function getRegistryClientGovernance(
  clientIdOrSlug: string,
): Promise<ClientGovernanceResponse | null> {
  const response = await backendFetch(
    `/registry/clients/${encodeURIComponent(clientIdOrSlug)}/governance`,
  );
  return parseJson<ClientGovernanceResponse>(response);
}

export async function getReviewQueue(): Promise<ReviewQueueResponse | null> {
  const response = await backendFetch("/registry/review/submissions");
  return parseJson<ReviewQueueResponse>(response);
}

export async function getMyListings(): Promise<MyListingsResponse | null> {
  const response = await backendFetch("/registry/me/listings");
  return parseJson<MyListingsResponse>(response);
}

/** Publish console: publishers and admins only (reviewers use moderation, not this flow). */
export function sessionMayUsePublishConsole(
  authEnabled: boolean,
  role: string | null | undefined,
): boolean {
  if (!authEnabled) {
    return true;
  }
  return role === "publisher";
}

export async function requirePublisherRole(): Promise<{ allowed: boolean; role: string | null }> {
  const payload = await getRegistrySession();
  if (!payload) {
    return { allowed: false, role: null };
  }
  if (payload.auth_enabled === false) {
    return { allowed: true, role: null };
  }
  const role = payload.session?.role ?? null;
  const allowed = sessionMayUsePublishConsole(true, role);
  return { allowed, role };
}

export async function requirePolicyRole(): Promise<{ allowed: boolean; role: string | null }> {
  const payload = await getRegistrySession();
  if (!payload) {
    return { allowed: false, role: null };
  }
  if (payload.auth_enabled === false) {
    return { allowed: true, role: null };
  }
  const role = payload.session?.role ?? null;
  const allowed = role === "reviewer" || role === "admin";
  return { allowed, role };
}

/** Moderation queue, provenance ledger, and similar governance surfaces. */
export async function requireReviewerRole(): Promise<{ allowed: boolean; role: string | null }> {
  const payload = await getRegistrySession();
  if (!payload) {
    return { allowed: false, role: null };
  }
  if (payload.auth_enabled === false) {
    return { allowed: true, role: null };
  }
  const role = payload.session?.role ?? null;
  const allowed = role === "reviewer" || role === "admin";
  return { allowed, role };
}

/** Contracts broker, federated consent, reflexive core (platform operations). */
export async function requireAdminRole(): Promise<{ allowed: boolean; role: string | null }> {
  const payload = await getRegistrySession();
  if (!payload) {
    return { allowed: false, role: null };
  }
  if (payload.auth_enabled === false) {
    return { allowed: true, role: null };
  }
  const role = payload.session?.role ?? null;
  const allowed = role === "admin";
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
  record_count?: number;
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
      record_count?: number;
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

// ── Contracts API ────────────────────────────────────────────

export type ContractTermData = {
  term_id: string;
  term_type: string;
  description: string;
  constraint: Record<string, unknown>;
  required: boolean;
  metadata?: Record<string, unknown>;
};

export type ContractData = {
  contract_id: string;
  server_id: string;
  agent_id: string;
  status: string;
  terms: ContractTermData[];
  signatures: Record<string, string>;
  created_at: string;
  expires_at?: string;
  session_id?: string;
};

export type NegotiateContractResponse = {
  request_id: string;
  session_id: string;
  status: string;
  reason: string;
  contract?: ContractData;
  counter_terms?: ContractTermData[];
};

export type ContractDetailResponse = {
  contract: ContractData;
  signatures: Record<string, string>;
  is_valid: boolean;
  is_mutually_signed: boolean;
  error?: string;
};

export type ContractListResponse = {
  agent_id: string;
  contracts: ContractData[];
  count: number;
};

export type ExchangeLogEntry = {
  entry_id?: string;
  session_id: string;
  direction: string;
  message_type: string;
  payload: Record<string, unknown>;
  timestamp: string;
  hash?: string;
  previous_hash?: string;
};

export type ExchangeLogResponse = {
  session_id: string | null;
  entries: ExchangeLogEntry[];
  count: number;
};

export type ExchangeChainVerifyResponse = {
  session_id: string;
  valid: boolean;
  entry_count: number;
  entries: ExchangeLogEntry[];
};

export async function negotiateContract(
  body: Record<string, unknown>,
): Promise<NegotiateContractResponse | null> {
  const response = await backendFetch("/security/contracts/negotiate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<NegotiateContractResponse>(response);
}

export async function getContractDetails(
  contractId: string,
): Promise<ContractDetailResponse | null> {
  const response = await backendFetch(
    `/security/contracts/${encodeURIComponent(contractId)}`,
  );
  return parseJson<ContractDetailResponse>(response);
}

export async function listContracts(
  agentId?: string,
): Promise<ContractListResponse | null> {
  const qs = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
  const response = await backendFetch(`/security/contracts${qs}`);
  return parseJson<ContractListResponse>(response);
}

export async function signContract(
  contractId: string,
  signatureBody: Record<string, unknown>,
): Promise<Record<string, unknown> | null> {
  const response = await backendFetch(
    `/security/contracts/${encodeURIComponent(contractId)}/sign`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(signatureBody),
    },
  );
  return parseJson<Record<string, unknown>>(response);
}

export async function revokeContract(
  contractId: string,
  reason?: string,
): Promise<Record<string, unknown> | null> {
  const response = await backendFetch(
    `/security/contracts/${encodeURIComponent(contractId)}/revoke`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason || "" }),
    },
  );
  return parseJson<Record<string, unknown>>(response);
}

export async function getExchangeLog(
  sessionId?: string,
): Promise<ExchangeLogResponse | null> {
  const qs = sessionId
    ? `?session_id=${encodeURIComponent(sessionId)}`
    : "";
  const response = await backendFetch(`/security/contracts/exchange-log${qs}`);
  return parseJson<ExchangeLogResponse>(response);
}

export async function verifyExchangeChain(
  sessionId: string,
): Promise<ExchangeChainVerifyResponse | null> {
  const response = await backendFetch(
    `/security/contracts/exchange-log/${encodeURIComponent(sessionId)}/verify`,
  );
  return parseJson<ExchangeChainVerifyResponse>(response);
}

// ── Federated Consent API ────────────────────────────────────

export type JurisdictionResult = {
  jurisdiction_code: string;
  satisfied: boolean;
  required_scopes: string[];
  satisfied_scopes: string[];
  missing_scopes: string[];
  applicable_regulations: string[];
  reason: string;
};

export type ConsentAccessRights = {
  agent_id: string;
  resource_id: string;
  allowed_scopes: string[];
  jurisdiction_constraints: Record<string, string[]>;
  conditions: string[];
  grant_sources: string[];
  expires_at?: string | null;
};

export type ConsentEvaluationResponse = {
  granted: boolean;
  reason: string;
  local_decision: { granted: boolean; reason: string };
  jurisdiction_results: Record<string, JurisdictionResult>;
  peer_decisions: Record<string, { granted: boolean; reason: string }>;
  access_rights: ConsentAccessRights | null;
  evaluated_at: string;
};

export type JurisdictionPolicy = {
  jurisdiction_id: string;
  jurisdiction_code: string;
  applicable_regulations: string[];
  required_consent_scopes: string[];
  requires_explicit_consent: boolean;
  data_residency_required: boolean;
};

export type JurisdictionListResponse = {
  jurisdictions: Record<string, JurisdictionPolicy>;
  count: number;
};

export type InstitutionListResponse = {
  institutions: Record<string, { jurisdiction_code: string }>;
  count: number;
};

export async function evaluateFederatedConsent(
  body: Record<string, unknown>,
): Promise<ConsentEvaluationResponse | null> {
  const response = await backendFetch("/security/consent/federated/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<ConsentEvaluationResponse>(response);
}

export async function getAccessRights(
  agentId: string,
  resourceId: string,
): Promise<ConsentAccessRights | null> {
  const response = await backendFetch(
    `/security/consent/federated/access-rights/${encodeURIComponent(agentId)}/${encodeURIComponent(resourceId)}`,
  );
  return parseJson<ConsentAccessRights>(response);
}

export async function listJurisdictions(): Promise<JurisdictionListResponse | null> {
  const response = await backendFetch("/security/consent/federated/jurisdictions");
  return parseJson<JurisdictionListResponse>(response);
}

export async function listInstitutions(): Promise<InstitutionListResponse | null> {
  const response = await backendFetch("/security/consent/federated/institutions");
  return parseJson<InstitutionListResponse>(response);
}

export async function propagateConsent(
  edgeId: string,
  targetPeers?: string[],
): Promise<Record<string, unknown> | null> {
  const response = await backendFetch("/security/consent/federated/propagate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ edge_id: edgeId, target_peers: targetPeers }),
  });
  return parseJson<Record<string, unknown>>(response);
}

// ── Reflexive Introspection API ─────────────────────────────

export type IntrospectionResponse = {
  actor_id: string;
  threat_score: number;
  threat_level: string;
  drift_summary: Record<string, number>;
  active_escalations: string[];
  compliance_status: string;
  verdict: string;
  should_halt: boolean;
  should_require_confirmation: boolean;
  constraints: string[];
  assessed_at: string;
};

export type VerdictResponse = {
  actor_id: string;
  operation: string;
  verdict: string;
};

export type ThreatLevelResponse = {
  actor_id: string;
  threat_level: string;
  threat_score: number;
};

export type ConstraintsResponse = {
  actor_id: string;
  constraints: string[];
  count: number;
};

export type AccountabilityEntry = {
  type: string;
  actor_id: string;
  threat_score?: number;
  threat_level?: string;
  compliance_status?: string;
  verdict?: string;
  constraints?: string[];
  timestamp?: string;
  binding_id?: string;
  operation_id?: string;
  assessed_at?: string;
  bound_at?: string;
};

export type AccountabilityResponse = {
  entries: AccountabilityEntry[];
  count: number;
};

export async function getIntrospection(
  actorId: string,
): Promise<IntrospectionResponse | null> {
  const response = await backendFetch(
    `/security/reflexive/introspect/${encodeURIComponent(actorId)}`,
  );
  return parseJson<IntrospectionResponse>(response);
}

export async function getVerdict(
  actorId: string,
  operation: string,
): Promise<VerdictResponse | null> {
  const response = await backendFetch(
    `/security/reflexive/verdict/${encodeURIComponent(actorId)}/${encodeURIComponent(operation)}`,
  );
  return parseJson<VerdictResponse>(response);
}

export async function getThreatLevel(
  actorId: string,
): Promise<ThreatLevelResponse | null> {
  const response = await backendFetch(
    `/security/reflexive/threat-level/${encodeURIComponent(actorId)}`,
  );
  return parseJson<ThreatLevelResponse>(response);
}

export async function getActorConstraints(
  actorId: string,
): Promise<ConstraintsResponse | null> {
  const response = await backendFetch(
    `/security/reflexive/constraints/${encodeURIComponent(actorId)}`,
  );
  return parseJson<ConstraintsResponse>(response);
}

export async function getAccountabilityLog(
  actorId?: string,
  limit?: number,
): Promise<AccountabilityResponse | null> {
  const qs = new URLSearchParams();
  if (actorId) qs.set("actor_id", actorId);
  if (limit) qs.set("limit", String(limit));
  const q = qs.toString();
  const response = await backendFetch(
    `/security/reflexive/accountability${q ? `?${q}` : ""}`,
  );
  return parseJson<AccountabilityResponse>(response);
}

// ── Federation & CRL API ────────────────────────────────────

export type FederationPeer = {
  peer_id: string;
  endpoint: string;
  status: string;
  trust_score: number;
  last_seen: string;
  metadata: Record<string, unknown>;
};

export type FederationStatusResponse = {
  peers: FederationPeer[];
  peer_count: number;
  federation_id: string;
  status: string;
  error?: string;
};

export type RevocationEntry = {
  tool_name: string;
  reason: string;
  revoked_at: string;
  revoked_by: string;
};

export type RevocationsResponse = {
  entries: RevocationEntry[];
  count: number;
  error?: string;
};

export async function getFederationStatus(): Promise<FederationStatusResponse | null> {
  const response = await backendFetch("/security/federation");
  return parseJson<FederationStatusResponse>(response);
}

export async function getRevocations(): Promise<RevocationsResponse | null> {
  const response = await backendFetch("/security/revocations");
  return parseJson<RevocationsResponse>(response);
}

// ── Security Health API ─────────────────────────────────────

export type SecurityHealthResponse = {
  status: string;
  components: Record<string, string>;
  component_count: number;
  timestamp: string;
};

export async function getSecurityHealth(): Promise<SecurityHealthResponse | null> {
  const response = await backendFetch("/security/health");
  return parseJson<SecurityHealthResponse>(response);
}
