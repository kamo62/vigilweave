import createClient from "openapi-fetch";

import type { components, paths } from "../types/api.generated";
import { getAuthHeaders, getCsrfToken, getRuntimeAuthConfig, setCsrfToken } from "./auth";
import { buildApiUrl, getApiBaseUrl } from "./api-url";
import { buildCurrentAppPath, buildLoginPath } from "./navigation";
import { normalizeSeverity } from "./utils";

let sessionRedirectPending = false;
let csrfFetchInFlight: Promise<string> | null = null;

function handleSessionExpiry(response: Response): void {
  if (response.status !== 401 || typeof window === "undefined") {
    return;
  }
  if (getRuntimeAuthConfig().apiKey) {
    return;
  }
  if (
    window.location.pathname === "/login" ||
    window.location.pathname === "/auth/callback" ||
    window.location.pathname === "/setup"
  ) {
    return;
  }
  if (!sessionRedirectPending) {
    sessionRedirectPending = true;
    window.location.assign(buildLoginPath({ nextPath: buildCurrentAppPath() }));
  }
}

const client = createClient<paths>({
  baseUrl: getApiBaseUrl(),
  fetch: async (request: Request) => {
    const method = request.method.toUpperCase();
    const headers = new Headers(request.headers);
    for (const [name, value] of Object.entries(getAuthHeaders())) {
      headers.set(name, value);
    }
    if (shouldAttachCsrf(method)) {
      ensureCsrfHeader(headers);
      if (!headers.get("X-CSRF-Token")) {
        const csrf = await fetchCsrfToken();
        headers.set("X-CSRF-Token", csrf);
      }
    }
    // Support cookie-based authentication (WorkOS JWT) by including credentials
    const authenticatedRequest = new Request(request, {
      headers,
      credentials: "include",
    });
    let response = await fetch(authenticatedRequest);
    if (response.status === 403 && shouldAttachCsrf(method)) {
      const csrf = await fetchCsrfToken();
      headers.set("X-CSRF-Token", csrf);
      response = await fetch(
        new Request(request, {
          headers,
          credentials: "include",
        }),
      );
    }
    handleSessionExpiry(response);
    return response;
  },
});

export type Scan = components["schemas"]["ScanPublic"];
export type ScanCreate = components["schemas"]["ScanCreate"];
export type Finding = components["schemas"]["FindingPublic"];
export type QualityMetrics = components["schemas"]["QualityMetricsResponse"];
export type RepositoryHistoryResponse =
  components["schemas"]["RepositoryHistoryResponse"];
export type CapabilityResponse = components["schemas"]["CapabilityResponse"];
export type SystemMetricsResponse =
  components["schemas"]["SystemMetricsResponse"];
export type ToolTelemetryRow = components["schemas"]["ToolTelemetryRow"];
export type PolicyProfile = components["schemas"]["PolicyProfilePublic"];
export type PolicyProfileCreate = components["schemas"]["PolicyProfileCreate"];
export type PolicyProfileUpdate = components["schemas"]["PolicyProfileUpdate"];
export type Waiver = components["schemas"]["WaiverPublic"];
export type WaiverCreate = components["schemas"]["WaiverCreate"];
export type AuditEvent = components["schemas"]["AuditEventPublic"];
export type PrismaImportRequest = components["schemas"]["PrismaImportRequest"];
export type PrismaImportResponse =
  components["schemas"]["PrismaImportResponse"];
export type SonarRulesImportRequest =
  components["schemas"]["SonarRulesImportRequest"];
export type SonarRulesImportResponse =
  components["schemas"]["SonarRulesImportResponse"];
export type ToolConfigSnapshot = components["schemas"]["ToolConfigSnapshot"];
export type ToolConfigPatch = components["schemas"]["ToolConfigPatch"];
export type ToolConfigItem = components["schemas"]["ToolConfigItem"];
export type ToolConfigCreate = components["schemas"]["ToolConfigCreate"];
export type TenantToolConfigOverride =
  components["schemas"]["TenantToolConfigOverridePublic"];
export type ProjectPublic = components["schemas"]["ProjectPublic"];
export type ProjectCreate = components["schemas"]["ProjectCreate"];
export type ProjectAggregateMetrics =
  components["schemas"]["ProjectAggregateMetrics"];
export type PortfolioPublic = components["schemas"]["PortfolioPublic"];
export type PortfolioCreate = components["schemas"]["PortfolioCreate"];
export type PortfolioUpdate = components["schemas"]["PortfolioUpdate"];
export type PortfolioDetail = components["schemas"]["PortfolioDetail"];
export type ApiKeyPublic = components["schemas"]["ApiKeyPublic"];
export type ApiKeyCreate = components["schemas"]["ApiKeyCreate"];
export type ApiKeyCreateResponse =
  components["schemas"]["ApiKeyCreateResponse"];
export type IntegrationsSetupResponse =
  components["schemas"]["IntegrationsSetupResponse"];
export type GitHubAppInstallationPublic =
  components["schemas"]["GitHubAppInstallationPublic"];
export type GitHubAppInstallLink = components["schemas"]["GitHubAppInstallLink"];
export interface GitHubAppLinkedRepoPublic {
  project_key: string;
  project_name: string;
  repo: string;
}

export interface GitHubAppInstallationReassignRequest {
  target_scm_connection_id?: number | null;
  target_github_installation_id?: number | null;
}

export interface GitHubAppInstallationReassignResponse {
  reassigned_count: number;
}
export type AzureMarketplaceOnboardRequest =
  components["schemas"]["AzureMarketplaceOnboardRequest"];
export type AzureMarketplaceOnboardResponse =
  components["schemas"]["AzureMarketplaceOnboardResponse"];
export interface CurrentUser {
  id: number;
  email: string;
  name?: string | null;
  avatar_url?: string | null;
  tenant_slug: string;
  auth_provider: "local" | "workos";
  workos_org_id?: string | null;
  role: "admin" | "member";
  platform_role: "none" | "operator";
  onboarding_completed: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface SaaSTenantLicenseRecord {
  tenant_slug: string;
  tier: "community" | "pro" | "enterprise";
  source: "default" | "override";
  assigned_by?: string | null;
  note?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  user_count: number;
}

export interface PlatformUserRecord {
  id: number;
  email: string;
  name?: string | null;
  avatar_url?: string | null;
  tenant_slug: string;
  auth_provider: "local" | "workos";
  workos_org_id?: string | null;
  role: "admin" | "member";
  platform_role: "none" | "operator";
  onboarding_completed: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface BillingPublicConfig {
  provider: "paddle";
  enabled: boolean;
  environment: "sandbox" | "production";
  client_token?: string | null;
  checkout_ready: boolean;
  pro_price_id?: string | null;
  enterprise_price_id?: string | null;
  default_success_url: string;
  webhook_url: string;
}

export interface BillingSubscriptionRecord {
  provider_subscription_id: string;
  tenant_slug?: string | null;
  plan_tier?: "community" | "pro" | "enterprise" | null;
  status?: string | null;
  collection_mode?: string | null;
  currency_code?: string | null;
  price_id?: string | null;
  next_billed_at?: string | null;
  canceled_at?: string | null;
  updated_at: string;
}

export interface TenantRecord {
  slug: string;
  display_name: string;
  billing_email?: string | null;
  deployment_mode: "saas" | "self_hosted";
  plan_tier: "community" | "pro" | "enterprise";
  billing_status: "inactive" | "active" | "trialing" | "paused" | "past_due" | "canceled" | "manual";
  workos_org_id?: string | null;
  paddle_customer_id?: string | null;
  paddle_subscription_id?: string | null;
  self_hosted_license_id?: number | null;
  self_hosted_license_key_prefix?: string | null;
  self_hosted_license_status?: string | null;
  self_hosted_last_fulfilled_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BillingPortalSessionRecord {
  customer_id: string;
  session_id: string;
  overview_url?: string | null;
  subscription_urls: Array<Record<string, unknown>>;
  created_at?: string | null;
}

export interface SelfHostedLicenseRecord {
  tenant_slug: string;
  license_id?: number | null;
  key_prefix?: string | null;
  status?: string | null;
  license_key?: string | null;
  last_fulfilled_at?: string | null;
}

export interface LocalUserSetupRequest {
  email: string;
  password: string;
  name?: string;
  tenant_slug?: string;
}

export interface LocalUserLoginRequest {
  email: string;
  password: string;
}

function assertResponse<T>(data: T | undefined, error: unknown): T {
  if (error || data === undefined) {
    throw toApiError(error, "Unexpected empty response from VigilWeave API");
  }
  return data;
}

function extractApiErrorMessage(error: unknown): string | null {
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }

  if (!error || typeof error !== "object") {
    return null;
  }

  if ("detail" in error) {
    const detail = (error as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }
  }

  if ("message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) {
      return message.trim();
    }
  }

  if ("errors" in error) {
    const errors = (error as { errors?: unknown }).errors;
    if (Array.isArray(errors)) {
      for (const item of errors) {
        const nested = extractApiErrorMessage(item);
        if (nested) {
          return nested;
        }
      }
    }
  }

  return null;
}

function toApiError(error: unknown, fallback: string): Error {
  return new Error(extractApiErrorMessage(error) ?? fallback);
}

async function buildResponseError(response: Response, fallback: string): Promise<Error> {
  const fallbackWithStatus = `${fallback} (${response.status})`;

  try {
    const payload = (await response.clone().json()) as unknown;
    return toApiError(payload, fallbackWithStatus);
  } catch {
    try {
      const text = (await response.clone().text()).trim();
      if (text) {
        return new Error(text);
      }
    } catch {
      // Ignore parsing failures and fall back to the generic response message.
    }
  }

  return new Error(fallbackWithStatus);
}

function buildAuthHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  for (const [name, value] of Object.entries(getAuthHeaders())) {
    headers.set(name, value);
  }
  return headers;
}

function ensureCsrfHeader(headers: Headers): void {
  const token = getCsrfToken();
  if (token) {
    headers.set("X-CSRF-Token", token);
  }
}

function shouldAttachCsrf(method?: string): boolean {
  return method === "POST" || method === "PATCH" || method === "PUT" || method === "DELETE";
}

async function fetchCsrfToken(): Promise<string> {
  if (csrfFetchInFlight) {
    return csrfFetchInFlight;
  }
  csrfFetchInFlight = (async () => {
    const response = await fetch(buildApiUrl("/api/v1/auth/csrf"), {
      method: "GET",
      credentials: "include",
      headers: buildAuthHeaders(),
    });
    if (!response.ok) {
      throw new Error(`Failed to get CSRF token (${response.status})`);
    }
    const payload = (await response.json()) as { csrf_token?: string };
    const token = (payload.csrf_token ?? "").trim();
    if (!token) {
      throw new Error("Failed to get CSRF token");
    }
    setCsrfToken(token);
    return token;
  })();

  try {
    return await csrfFetchInFlight;
  } finally {
    csrfFetchInFlight = null;
  }
}

async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const controller = new AbortController();
  const timeoutMs = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 30_000);
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = buildAuthHeaders(init?.headers);
    if (shouldAttachCsrf(method)) {
      ensureCsrfHeader(headers);
      if (!headers.get("X-CSRF-Token")) {
        const csrf = await fetchCsrfToken();
        headers.set("X-CSRF-Token", csrf);
      }
    }

    const response = await fetch(buildApiUrl(input), {
      ...init,
      headers,
      signal: controller.signal,
      credentials: "include",
    });
    handleSessionExpiry(response);
    if (response.status === 403 && shouldAttachCsrf(method)) {
      const csrf = await fetchCsrfToken();
      headers.set("X-CSRF-Token", csrf);
      const retry = await fetch(buildApiUrl(input), {
        ...init,
        headers,
        signal: controller.signal,
        credentials: "include",
      });
      handleSessionExpiry(retry);
      if (!retry.ok) {
        throw await buildResponseError(retry, "Request failed");
      }
      return (await retry.json()) as T;
    }
    if (!response.ok) {
      throw await buildResponseError(response, "Request failed");
    }
    return (await response.json()) as T;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function downloadFile(input: string, filename: string): Promise<void> {
  const controller = new AbortController();
  const downloadTimeoutMs = Number(
    import.meta.env.VITE_DOWNLOAD_TIMEOUT_MS ?? 120_000,
  );
  const timeoutId = setTimeout(() => controller.abort(), downloadTimeoutMs);
  try {
    const response = await fetch(buildApiUrl(input), {
      headers: buildAuthHeaders(),
      signal: controller.signal,
      credentials: "include",
    });
    handleSessionExpiry(response);
    if (!response.ok) {
      throw await buildResponseError(response, "Download failed");
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } finally {
    clearTimeout(timeoutId);
  }
}

export interface FindingFilters {
  severity?: string[];
  category?: string[];
  tool?: string[];
  review_status?: ReviewStatus[];
  include_suppressed?: boolean;
}

interface FindingQueryOptions extends FindingFilters {
  offset?: number;
  limit?: number;
}

function buildFindingQuery(filters?: FindingQueryOptions): string {
  const params = new URLSearchParams();
  for (const severity of filters?.severity ?? []) {
    params.append("severity", severity);
  }
  for (const category of filters?.category ?? []) {
    params.append("category", category);
  }
  for (const tool of filters?.tool ?? []) {
    params.append("tool", tool);
  }
  for (const reviewStatus of filters?.review_status ?? []) {
    params.append("review_status", reviewStatus);
  }
  if (filters?.include_suppressed) {
    params.set("include_suppressed", "true");
  }
  if (filters?.offset !== undefined) {
    params.set("offset", String(filters.offset));
  }
  if (filters?.limit !== undefined) {
    params.set("limit", String(filters.limit));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function fetchCapabilities(): Promise<CapabilityResponse> {
  const { data, error } = await client.GET("/api/v1/system/capabilities", {});
  return assertResponse(data, error);
}

export async function fetchBillingPublicConfig(): Promise<BillingPublicConfig> {
  return fetchJson<BillingPublicConfig>("/api/v1/billing/public-config");
}

export async function fetchCurrentTenantSubscription(): Promise<BillingSubscriptionRecord | null> {
  return fetchJson<BillingSubscriptionRecord | null>("/api/v1/billing/subscription");
}

export async function fetchCurrentTenantRecord(): Promise<TenantRecord | null> {
  return fetchJson<TenantRecord | null>("/api/v1/billing/tenant");
}

export async function createBillingPortalSession(): Promise<BillingPortalSessionRecord> {
  return fetchJson<BillingPortalSessionRecord>("/api/v1/billing/portal-session", {
    method: "POST",
  });
}

export async function fetchSelfHostedLicense(): Promise<SelfHostedLicenseRecord> {
  return fetchJson<SelfHostedLicenseRecord>("/api/v1/billing/self-hosted-license");
}

export async function updateCurrentUser(
  payload: Partial<
    Pick<CurrentUser, "name" | "avatar_url" | "onboarding_completed">
  >,
): Promise<CurrentUser> {
  return fetchJson<CurrentUser>("/api/v1/auth/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function setupLocalUser(
  payload: LocalUserSetupRequest,
): Promise<CurrentUser> {
  return fetchJson<CurrentUser>("/api/v1/auth/local/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function loginLocalUser(
  payload: LocalUserLoginRequest,
): Promise<CurrentUser> {
  return fetchJson<CurrentUser>("/api/v1/auth/local/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchSystemMetrics(): Promise<SystemMetricsResponse> {
  const { data, error } = await client.GET("/api/v1/system/metrics", {});
  return assertResponse(data, error);
}

export async function fetchToolTelemetry(): Promise<ToolTelemetryRow[]> {
  const { data, error } = await client.GET("/api/v1/system/tool-telemetry", {});
  return assertResponse(data, error);
}

export async function fetchScans(): Promise<Scan[]> {
  const { data, error } = await client.GET("/api/v1/scans/", {});
  return assertResponse(data, error);
}

export async function fetchRepositoryHistory(
  repo: string,
  limit = 100,
): Promise<RepositoryHistoryResponse> {
  const { data, error } = await client.GET("/api/v1/repositories/history", {
    params: {
      query: { repo, limit },
    },
  });
  return assertResponse(data, error);
}

export async function fetchScan(scanId: number): Promise<Scan> {
  const { data, error } = await client.GET("/api/v1/scans/{scan_id}", {
    params: {
      path: { scan_id: scanId },
    },
  });
  return assertResponse(data, error);
}

export async function fetchFindings(
  scanId: number,
  filters?: FindingFilters,
): Promise<Finding[]> {
  const batchSize = 5000;
  const findings: Finding[] = [];
  let offset = 0;

  while (true) {
    const batch = await fetchJson<Finding[]>(
      `/api/v1/scans/${scanId}/findings${buildFindingQuery({
        ...filters,
        offset,
        limit: batchSize,
      })}`,
    );
    findings.push(...batch);
    if (batch.length < batchSize) {
      break;
    }
    offset += batchSize;
  }

  return findings.map((finding) => ({
    ...finding,
    severity: normalizeSeverity(finding.severity),
  }));
}

export async function fetchQualityMetrics(
  scanId: number,
): Promise<QualityMetrics> {
  const { data, error } = await client.GET(
    "/api/v1/scans/{scan_id}/quality-metrics",
    {
      params: {
        path: { scan_id: scanId },
      },
    },
  );
  return assertResponse(data, error);
}

export async function createScan(payload: ScanCreate): Promise<Scan> {
  const { data, error } = await client.POST("/api/v1/scans/", {
    body: payload,
  });
  return assertResponse(data, error);
}

export async function fetchPolicies(): Promise<PolicyProfile[]> {
  const { data, error } = await client.GET("/api/v1/policies/", {});
  return assertResponse(data, error);
}

export async function createPolicy(
  payload: PolicyProfileCreate,
): Promise<PolicyProfile> {
  const { data, error } = await client.POST("/api/v1/policies/", {
    body: payload,
  });
  return assertResponse(data, error);
}

export async function updatePolicy(
  policyId: number,
  payload: PolicyProfileUpdate,
): Promise<PolicyProfile> {
  const { data, error } = await client.PATCH("/api/v1/policies/{policy_id}", {
    params: { path: { policy_id: policyId } },
    body: payload,
  });
  return assertResponse(data, error);
}

export async function deletePolicy(policyId: number): Promise<void> {
  const { error } = await client.DELETE("/api/v1/policies/{policy_id}", {
    params: { path: { policy_id: policyId } },
  });
  if (error) throw error;
}

export async function activatePolicy(policyId: number): Promise<PolicyProfile> {
  const { data, error } = await client.POST(
    "/api/v1/policies/{policy_id}/activate",
    {
      params: { path: { policy_id: policyId } },
    },
  );
  return assertResponse(data, error);
}

export async function fetchWaivers(): Promise<Waiver[]> {
  const { data, error } = await client.GET("/api/v1/policies/waivers", {});
  return assertResponse(data, error);
}

export async function createWaiver(payload: WaiverCreate): Promise<Waiver> {
  const { data, error } = await client.POST("/api/v1/policies/waivers", {
    body: payload,
  });
  return assertResponse(data, error);
}

export async function deactivateWaiver(waiverId: number): Promise<void> {
  const { error } = await client.DELETE(
    "/api/v1/policies/waivers/{waiver_id}",
    {
      params: { path: { waiver_id: waiverId } },
    },
  );
  if (error) throw error;
}

export async function fetchAuditEvents(): Promise<AuditEvent[]> {
  const { data, error } = await client.GET("/api/v1/policies/audit", {});
  return assertResponse(data, error);
}

export async function fetchToolConfigSnapshot(): Promise<ToolConfigSnapshot> {
  const { data, error } = await client.GET("/api/v1/tool-configs/", {});
  return assertResponse(data, error);
}

export async function patchToolConfig(
  toolId: string,
  payload: ToolConfigPatch,
): Promise<ToolConfigItem> {
  const { data, error } = await client.PATCH(
    "/api/v1/tool-configs/tools/{tool_id}",
    {
      params: {
        path: {
          tool_id: toolId,
        },
      },
      body: payload,
    },
  );
  return assertResponse(data, error);
}

export async function createTenantToolConfig(
  toolId: string,
  payload: ToolConfigCreate,
): Promise<ToolConfigItem> {
  const { data, error } = await client.PUT(
    "/api/v1/tool-configs/tenant/tools/{tool_id}",
    {
      params: { path: { tool_id: toolId } },
      body: payload,
    },
  );
  return assertResponse(data, error);
}

export async function fetchTenantToolOverrides(): Promise<
  TenantToolConfigOverride[]
> {
  const { data, error } = await client.GET(
    "/api/v1/tool-configs/tenant/overrides",
    {},
  );
  return assertResponse(data, error);
}

export async function deleteTenantToolConfig(toolId: string): Promise<void> {
  const { error } = await client.DELETE(
    "/api/v1/tool-configs/tenant/tools/{tool_id}",
    {
      params: { path: { tool_id: toolId } },
    },
  );
  if (error) throw toApiError(error, "Delete tool configuration failed");
}

export async function importPrismaFindings(
  payload: PrismaImportRequest,
): Promise<PrismaImportResponse> {
  const { data, error } = await client.POST(
    "/api/v1/integrations/prisma/import",
    {
      body: payload,
    },
  );
  return assertResponse(data, error);
}

export async function importSonarRules(
  payload: SonarRulesImportRequest,
): Promise<SonarRulesImportResponse> {
  const { data, error } = await client.POST(
    "/api/v1/integrations/sonarqube/rules/import",
    {
      body: payload,
    },
  );
  return assertResponse(data, error);
}

export async function fetchIntegrationsSetup(): Promise<IntegrationsSetupResponse> {
  const { data, error } = await client.GET("/api/v1/integrations/setup", {});
  return assertResponse(data, error);
}

export async function fetchGitHubAppInstallUrl(): Promise<GitHubAppInstallLink> {
  return fetchJson<GitHubAppInstallLink>("/api/v1/integrations/github-app/install-url");
}

export async function fetchGitHubAppInstallUrlForReturnTo(
  returnTo: string,
): Promise<GitHubAppInstallLink> {
  const query = new URLSearchParams({ return_to: returnTo }).toString();
  return fetchJson<GitHubAppInstallLink>(`/api/v1/integrations/github-app/install-url?${query}`);
}

export async function fetchGitHubAppInstallations(): Promise<GitHubAppInstallationPublic[]> {
  const { data, error } = await client.GET(
    "/api/v1/integrations/github-app/installations",
    {},
  );
  return assertResponse(data, error);
}

export async function fetchGitHubAppRepositories(
  installationId: number,
): Promise<SCMRepository[]> {
  return fetchJson<SCMRepository[]>(
    `/api/v1/integrations/github-app/installations/${installationId}/repositories`,
  );
}

export async function fetchGitHubAppLinkedRepos(
  installationId: number,
): Promise<GitHubAppLinkedRepoPublic[]> {
  return fetchJson<GitHubAppLinkedRepoPublic[]>(
    `/api/v1/integrations/github-app/installations/${installationId}/linked-repos`,
  )
}

export async function reassignGitHubAppLinkedRepos(
  installationId: number,
  payload: GitHubAppInstallationReassignRequest,
): Promise<GitHubAppInstallationReassignResponse> {
  return fetchJson<GitHubAppInstallationReassignResponse>(
    `/api/v1/integrations/github-app/installations/${installationId}/reassign`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export async function unlinkGitHubAppInstallation(
  installationId: number,
): Promise<GitHubAppInstallationPublic> {
  const { data, error } = await client.DELETE(
    "/api/v1/integrations/github-app/installations/{installation_id}",
    {
      params: { path: { installation_id: installationId } },
    },
  );
  return assertResponse(data, error);
}

export async function onboardAzureDevOpsProject(
  payload: AzureMarketplaceOnboardRequest,
): Promise<AzureMarketplaceOnboardResponse> {
  const { data, error } = await client.POST(
    "/api/v1/integrations/azure-devops/onboard-project",
    {
      body: payload,
    },
  );
  return assertResponse(data, error);
}

export async function fetchSaaSTenantLicenses(): Promise<SaaSTenantLicenseRecord[]> {
  return fetchJson<SaaSTenantLicenseRecord[]>("/api/v1/saas-admin/tenant-licenses");
}

export async function updateSaaSTenantLicense(
  tenantSlug: string,
  payload: { tier: "community" | "pro" | "enterprise"; note?: string },
): Promise<SaaSTenantLicenseRecord> {
  return fetchJson<SaaSTenantLicenseRecord>(
    `/api/v1/saas-admin/tenant-licenses/${encodeURIComponent(tenantSlug)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export async function deleteSaaSTenantLicense(tenantSlug: string): Promise<void> {
  const headers = new Headers();
  for (const [name, value] of Object.entries(getAuthHeaders())) {
    headers.set(name, value);
  }
  const csrf = getCsrfToken() || (await fetchCsrfToken());
  headers.set("X-CSRF-Token", csrf);
  const response = await fetch(
    buildApiUrl(`/api/v1/saas-admin/tenant-licenses/${encodeURIComponent(tenantSlug)}`),
    {
      method: "DELETE",
      headers,
      credentials: "include",
    },
  );
  handleSessionExpiry(response);
  if (!response.ok) {
    throw await buildResponseError(response, "Delete tenant license failed");
  }
}

export async function fetchPlatformUsers(): Promise<PlatformUserRecord[]> {
  return fetchJson<PlatformUserRecord[]>("/api/v1/saas-admin/users");
}

export async function updatePlatformUserRole(
  userId: number,
  platformRole: "none" | "operator",
): Promise<PlatformUserRecord> {
  return fetchJson<PlatformUserRecord>(
    `/api/v1/saas-admin/users/${userId}/platform-role`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform_role: platformRole }),
    },
  );
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export async function fetchProjects(): Promise<ProjectPublic[]> {
  const { data, error } = await client.GET("/api/v1/projects/", {});
  return assertResponse(data, error);
}

export async function fetchProjectMetrics(
  projectKey: string,
): Promise<ProjectAggregateMetrics> {
  const { data, error } = await client.GET("/api/v1/projects/{project_key}", {
    params: { path: { project_key: projectKey } },
  });
  return assertResponse(data, error);
}

export async function createProject(
  payload: ProjectCreate,
): Promise<ProjectPublic> {
  const { data, error } = await client.POST("/api/v1/projects/", {
    body: payload,
  });
  return assertResponse(data, error);
}

export async function deleteProject(
  projectKey: string,
  options?: { deleteScans?: boolean; projectId?: number },
): Promise<void> {
  const qs = options?.deleteScans ? "?delete_scans=true" : "";
  const targetPath = projectKey.trim()
    ? `/api/v1/projects/${encodeURIComponent(projectKey)}${qs}`
    : `/api/v1/projects/by-id/${options?.projectId ?? ""}${qs}`;
  const headers = new Headers();
  for (const [name, value] of Object.entries(getAuthHeaders())) {
    headers.set(name, value);
  }
  const csrf = getCsrfToken() || (await fetchCsrfToken());
  headers.set("X-CSRF-Token", csrf);
  const response = await fetch(
    buildApiUrl(targetPath),
    {
      method: "DELETE",
      headers,
      credentials: "include",
    },
  );
  handleSessionExpiry(response);
  if (!response.ok)
    throw new Error(`Delete project failed (${response.status})`);
}

export async function addProjectRepos(
  projectKey: string,
  repos: string[],
  options?: {
    scmConnectionId?: number
    githubInstallationId?: number
  },
): Promise<ProjectPublic> {
  return fetchJson<ProjectPublic>(
    `/api/v1/projects/${encodeURIComponent(projectKey)}/repos`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repos,
        scm_connection_id: options?.scmConnectionId ?? null,
        github_installation_id: options?.githubInstallationId ?? null,
      }),
    },
  );
}

export async function removeProjectRepo(
  projectKey: string,
  repo: string,
): Promise<ProjectPublic> {
  const encodedRepo = encodeURIComponent(repo);
  return fetchJson<ProjectPublic>(
    `/api/v1/projects/${encodeURIComponent(projectKey)}/repos?repo=${encodedRepo}`,
    {
      method: "DELETE",
    },
  );
}

// ---------------------------------------------------------------------------
// Portfolios
// ---------------------------------------------------------------------------

export async function fetchPortfolios(): Promise<PortfolioPublic[]> {
  const { data, error } = await client.GET("/api/v1/portfolios/", {});
  return assertResponse(data, error);
}

export async function fetchPortfolioDetail(
  portfolioKey: string,
): Promise<PortfolioDetail> {
  const { data, error } = await client.GET(
    "/api/v1/portfolios/{portfolio_key}",
    {
      params: { path: { portfolio_key: portfolioKey } },
    },
  );
  return assertResponse(data, error);
}

export async function createPortfolio(
  payload: PortfolioCreate,
): Promise<PortfolioPublic> {
  const { data, error } = await client.POST("/api/v1/portfolios/", {
    body: payload,
  });
  return assertResponse(data, error);
}

export async function updatePortfolio(
  portfolioKey: string,
  payload: PortfolioUpdate,
): Promise<PortfolioPublic> {
  const { data, error } = await client.PATCH(
    "/api/v1/portfolios/{portfolio_key}",
    {
      params: { path: { portfolio_key: portfolioKey } },
      body: payload,
    },
  );
  return assertResponse(data, error);
}

export async function deletePortfolio(portfolioKey: string): Promise<void> {
  const { error } = await client.DELETE("/api/v1/portfolios/{portfolio_key}", {
    params: { path: { portfolio_key: portfolioKey } },
  });
  if (error) throw error;
}

export async function addPortfolioProjects(
  portfolioKey: string,
  projectKeys: string[],
): Promise<PortfolioPublic> {
  const { data, error } = await client.POST(
    "/api/v1/portfolios/{portfolio_key}/projects",
    {
      params: { path: { portfolio_key: portfolioKey } },
      body: { project_keys: projectKeys },
    },
  );
  return assertResponse(data, error);
}

export async function removePortfolioProject(
  portfolioKey: string,
  projectKey: string,
): Promise<PortfolioPublic> {
  const { data, error } = await client.DELETE(
    "/api/v1/portfolios/{portfolio_key}/projects/{project_key}",
    {
      params: {
        path: { portfolio_key: portfolioKey, project_key: projectKey },
      },
    },
  );
  return assertResponse(data, error);
}

// ---------------------------------------------------------------------------
// API Keys
// ---------------------------------------------------------------------------

export async function fetchApiKeys(): Promise<ApiKeyPublic[]> {
  const { data, error } = await client.GET("/api/v1/auth/api-keys", {});
  return assertResponse(data, error);
}

export async function createApiKey(
  payload: ApiKeyCreate,
): Promise<ApiKeyCreateResponse> {
  const { data, error } = await client.POST("/api/v1/auth/api-keys", {
    body: payload,
  });
  return assertResponse(data, error);
}

export async function revokeApiKey(keyId: number): Promise<void> {
  const { error } = await client.DELETE("/api/v1/auth/api-keys/{key_id}", {
    params: { path: { key_id: keyId } },
  });
  if (error) throw toApiError(error, "Revoke API key failed");
}

// ---------------------------------------------------------------------------
// Finding Triage
// ---------------------------------------------------------------------------

export type ReviewStatus =
  | "open"
  | "acknowledged"
  | "false_positive"
  | "fixed"
  | "wont_fix";

export async function deleteScan(scanId: number): Promise<void> {
  const headers = new Headers();
  for (const [name, value] of Object.entries(getAuthHeaders())) {
    headers.set(name, value);
  }
  const csrf = getCsrfToken() || (await fetchCsrfToken());
  headers.set("X-CSRF-Token", csrf);
  const response = await fetch(buildApiUrl(`/api/v1/scans/${scanId}`), {
    method: "DELETE",
    headers,
    credentials: "include",
  });
  if (!response.ok) throw await buildResponseError(response, "Delete scan failed");
}

export interface FindingTriageRequest {
  review_status: ReviewStatus;
  comment?: string;
}

export async function triageFinding(
  scanId: number,
  findingId: number,
  payload: FindingTriageRequest,
): Promise<Finding> {
  const headers = new Headers({
    "Content-Type": "application/json",
  });
  for (const [name, value] of Object.entries(getAuthHeaders())) {
    headers.set(name, value);
  }
  const csrf = getCsrfToken() || (await fetchCsrfToken());
  headers.set("X-CSRF-Token", csrf);
  const response = await fetch(
    buildApiUrl(`/api/v1/scans/${scanId}/findings/${findingId}/triage`),
    {
      method: "PATCH",
      headers,
      body: JSON.stringify(payload),
      credentials: "include",
    },
  );
  if (!response.ok) throw new Error(`Triage failed (${response.status})`);
  return (await response.json()) as Finding;
}

export interface BulkTriageRequest {
  finding_ids: number[];
  review_status: ReviewStatus;
  comment?: string;
}

export interface BulkTriageResponse {
  updated: number;
  skipped: number;
}

export async function bulkTriageFindings(
  scanId: number,
  payload: BulkTriageRequest,
): Promise<BulkTriageResponse> {
  const headers = new Headers({
    "Content-Type": "application/json",
  });
  for (const [name, value] of Object.entries(getAuthHeaders())) {
    headers.set(name, value);
  }
  const csrf = getCsrfToken() || (await fetchCsrfToken());
  headers.set("X-CSRF-Token", csrf);
  const response = await fetch(
    buildApiUrl(`/api/v1/scans/${scanId}/findings/bulk-triage`),
    {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      credentials: "include",
    },
  );
  if (!response.ok) throw new Error(`Bulk triage failed (${response.status})`);
  return (await response.json()) as BulkTriageResponse;
}

export async function downloadScanReportPdf(
  scanId: number,
  filters?: FindingFilters,
): Promise<void> {
  await downloadFile(
    `/api/v1/scans/${scanId}/report/pdf${buildFindingQuery(filters)}`,
    `scan-${scanId}-report.pdf`,
  );
}

export async function downloadScanFindingsCsv(
  scanId: number,
  filters?: FindingFilters,
): Promise<void> {
  await downloadFile(
    `/api/v1/scans/${scanId}/findings/export${buildFindingQuery(filters)}`,
    `scan-${scanId}-findings.csv`,
  );
}

// ---------------------------------------------------------------------------
// SCM Connections
// ---------------------------------------------------------------------------

export type SCMProvider = "github" | "gitlab" | "bitbucket" | "azure_devops";

export interface SCMConnectionPublic {
  id: number;
  tenant_slug: string;
  name: string;
  provider: SCMProvider;
  base_url: string;
  token_masked: string;
  extra_config: Record<string, string> | null;
  is_active: boolean;
  last_tested_at: string | null;
  last_test_ok: boolean | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

export interface SCMConnectionCreate {
  name: string;
  provider: SCMProvider;
  base_url: string;
  token: string;
  extra_config?: Record<string, string> | null;
}

export interface SCMConnectionUpdate {
  name?: string;
  base_url?: string;
  token?: string;
  extra_config?: Record<string, string> | null;
  is_active?: boolean;
}

export interface SCMConnectionTestResult {
  ok: boolean;
  message: string;
  username: string | null;
}

export interface SCMOrganization {
  id: string;
  name: string;
  avatar_url: string | null;
}

export interface SCMRepository {
  id: string;
  name: string;
  full_name: string;
  clone_url: string;
  default_branch: string | null;
  description: string | null;
  language: string | null;
  is_private: boolean;
  updated_at: string | null;
}

export async function fetchSCMConnections(): Promise<SCMConnectionPublic[]> {
  return fetchJson<SCMConnectionPublic[]>("/api/v1/scm-connections/");
}

export async function createSCMConnection(
  payload: SCMConnectionCreate,
): Promise<SCMConnectionPublic> {
  return fetchJson<SCMConnectionPublic>("/api/v1/scm-connections/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateSCMConnection(
  id: number,
  payload: SCMConnectionUpdate,
): Promise<SCMConnectionPublic> {
  return fetchJson<SCMConnectionPublic>(`/api/v1/scm-connections/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteSCMConnection(id: number): Promise<void> {
  const headers = new Headers();
  for (const [name, value] of Object.entries(getAuthHeaders())) {
    headers.set(name, value);
  }
  const csrf = getCsrfToken() || (await fetchCsrfToken());
  headers.set("X-CSRF-Token", csrf);
  const response = await fetch(buildApiUrl(`/api/v1/scm-connections/${id}`), {
    method: "DELETE",
    headers,
    credentials: "include",
  });
  handleSessionExpiry(response);
  if (!response.ok) throw await buildResponseError(response, "Delete connection failed");
}

export async function testSCMConnection(
  id: number,
): Promise<SCMConnectionTestResult> {
  return fetchJson<SCMConnectionTestResult>(
    `/api/v1/scm-connections/${id}/test`,
    { method: "POST" },
  );
}

export async function fetchSCMOrganizations(
  connectionId: number,
): Promise<SCMOrganization[]> {
  return fetchJson<SCMOrganization[]>(
    `/api/v1/scm-connections/${connectionId}/organizations`,
  );
}

export async function fetchSCMRepositories(
  connectionId: number,
  org: string,
): Promise<SCMRepository[]> {
  const params = org ? `?org=${encodeURIComponent(org)}` : "";
  return fetchJson<SCMRepository[]>(
    `/api/v1/scm-connections/${connectionId}/repositories${params}`,
  );
}

export async function importSCMRepos(
  connectionId: number,
  payload: { project_key: string; repos: string[] },
): Promise<{ imported: number; skipped: number }> {
  return fetchJson<{ imported: number; skipped: number }>(
    `/api/v1/scm-connections/${connectionId}/import-repos`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}
