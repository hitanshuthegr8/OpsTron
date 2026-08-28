/**
 * OpsTron Backend API Client
 * Configure VITE_BACKEND_URL in GitHub Pages/Render deployment settings.
 */

export const BACKEND = import.meta.env.VITE_BACKEND_URL || "";
const APP_BASE = import.meta.env.PROD ? "/OpsTron" : "";

// An empty BACKEND makes every request relative to whatever host is serving the
// app. On GitHub Pages that silently sends `${BACKEND}/auth/github/login` to
// <user>.github.io/auth/github/login, which renders GitHub's own 404 rather than
// any error this app can show. Fail loudly instead of shipping that quietly.
if (!BACKEND && typeof window !== "undefined" && import.meta.env.PROD) {
  console.error(
    "[OpsTron] VITE_BACKEND_URL was not set at build time. API calls will " +
      `resolve against ${window.location.origin} and fail. Set the ` +
      "OPSTRON_BACKEND_URL repository secret and re-run the deploy workflow.",
  );
}

// ─── Auth token helpers ────────────────────────────────────────────────────
export const TOKEN_KEY = "ops_token";
export const AGENT_KEY = "ops_agent_key";
// Persisted app state (includes the cached user). Declared here so clearAuth
// can drop it too -- a cached user outliving its token sends the login route
// into a redirect loop.
export const STATE_KEY = "opstronic:state:v2";

export function appPath(path: string): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${APP_BASE}${cleanPath}`;
}

export function getToken(): string {
  return typeof window !== "undefined"
    ? (localStorage.getItem(TOKEN_KEY) ?? "")
    : "";
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(AGENT_KEY);
  localStorage.removeItem("ops_connected_repo");
  // Drop the cached user as well. Without this the session looks dead to the
  // API but alive to the router, which bounces /login -> /onboarding forever.
  localStorage.removeItem(STATE_KEY);
}

// ─── Base fetch helper ─────────────────────────────────────────────────────
async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BACKEND}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });

  if (res.status === 401) {
    clearAuth();
    window.location.href = appPath("/login");
    throw new Error("Session expired");
  }

  if (!res.ok) {
    // FastAPI reports errors as {"detail": "..."} — surface that message
    // directly instead of dumping raw JSON at the user.
    const raw = await res.text().catch(() => "");
    let message = raw || res.statusText;
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed?.detail === "string") {
        message = parsed.detail;
      } else if (Array.isArray(parsed?.detail)) {
        // Pydantic validation errors come back as a list of objects
        message = parsed.detail
          .map((d: { loc?: unknown[]; msg?: string }) =>
            `${(d.loc ?? []).join(".")}: ${d.msg ?? "invalid"}`,
          )
          .join("; ");
      }
    } catch {
      // not JSON — keep the raw text
    }
    throw new Error(message);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ─── Types ─────────────────────────────────────────────────────────────────
export interface BackendUser {
  github_id: string;
  login: string;
  name: string | null;
  avatar_url: string;
  email: string | null;
  agent_api_key: string;
}

export interface MeResponse {
  authenticated: boolean;
  user: BackendUser;
}

export interface Repo {
  id: number;
  owner: string;
  name: string;
  full_name: string;
  description: string | null;
  private: boolean;
  language: string | null;
  stars: number;
}

export interface RCAReport {
  id: string | number;
  service: string;
  error: string;
  raw_error?: string;
  environment?: string;
  env?: string;
  analyzed_at?: string;
  created_at?: string;
  processing_time_ms?: number;
  is_deployment_related?: boolean;
  deployment_context?: {
    commit_sha?: string;
    author?: string;
    branch?: string;
    commit_msg?: string;
    message?: string;
    changed_files?: Array<
      string | { filename?: string; name?: string; status?: string; additions?: number; deletions?: number }
    >;
  };
  rca_report?: {
    root_cause?: string;
    summary?: string;
    confidence?: string;
    confidence_score?: number;
    contributing_factors?: unknown[];
    evidence?: Record<string, unknown>;
    suspect_code_change?: Record<string, unknown>;
    rollback_recommendation?: Record<string, unknown>;
    recommended_actions?: string[];
    recommendations?: string[];
    error_signals?: string[];
    signals?: string[];
    error_correlation?: string;
    ingestion_mode?: string;
    timeline?: string;
  };
}

export interface AgentStatusResponse {
  status: string;
  agent_connected?: boolean;
  monitored_containers?: string[];
  hostname?: string;
}

export interface AlertSettingsPayload {
  voice_alerts_enabled: boolean;
  phone_number: string;
  severity_threshold: "low" | "medium" | "high" | "critical";
  cooldown_minutes: number;
  slack_webhook?: string;
  on_call_email?: string;
}

export interface AlertSettingsResponse {
  settings: AlertSettingsPayload & {
    last_voice_alert_at?: string | null;
  };
}

// ─── Auth ──────────────────────────────────────────────────────────────────

/** Redirect browser to GitHub OAuth (backend handles the redirect) */
export function redirectToGitHubOAuth() {
  window.location.href = `${BACKEND}/auth/github/login`;
}

/** Fetch the current user's profile. Returns null if not logged in. */
export async function fetchMe(): Promise<BackendUser | null> {
  try {
    const data = await apiFetch<MeResponse>("/auth/me");
    return data.user;
  } catch {
    return null;
  }
}

/** Logout – best-effort POST then clear local storage */
export async function logoutFromBackend(): Promise<void> {
  try {
    await apiFetch<void>("/auth/logout", { method: "POST" });
  } catch {
    /* best-effort */
  }
  clearAuth();
}

// ─── Repos ────────────────────────────────────────────────────────────────
export async function fetchRepos(): Promise<Repo[]> {
  const data = await apiFetch<{ repos: Repo[] }>("/integrations/repos");
  return data.repos ?? [];
}

export async function installWebhook(
  owner: string,
  repo: string,
  serviceName: string,
  webhookUrl?: string,
): Promise<{ message: string; webhook_id?: number }> {
  return apiFetch("/integrations/install-webhook", {
    method: "POST",
    body: JSON.stringify({
      owner,
      repo,
      webhook_url: webhookUrl ?? `${BACKEND}/notify-deployment`,
      service_name: serviceName,
    }),
  });
}

export async function saveAlertSettings(payload: AlertSettingsPayload): Promise<void> {
  await apiFetch("/settings/alerts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchAlertSettings(): Promise<AlertSettingsPayload | null> {
  try {
    const data = await apiFetch<AlertSettingsResponse>("/settings/alerts");
    return data.settings;
  } catch {
    return null;
  }
}

export async function rotateAgentApiKey(): Promise<string> {
  const data = await apiFetch<{ agent_api_key: string }>("/auth/agent-key/rotate", {
    method: "POST",
  });
  localStorage.setItem(AGENT_KEY, data.agent_api_key);
  return data.agent_api_key;
}

export async function uploadRunbook(file: File, repo = "", service = ""): Promise<{ filename: string; title: string }> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  form.append("repo", repo);
  form.append("service", service);

  const res = await fetch(`${BACKEND}/runbooks/upload`, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: form,
  });

  if (res.status === 401) {
    clearAuth();
    window.location.href = appPath("/login");
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText);
    throw new Error(err);
  }

  const data = await res.json();
  return data.runbook;
}

// ─── Agent ────────────────────────────────────────────────────────────────
export async function fetchAgentStatus(): Promise<AgentStatusResponse | null> {
  const agentKey = typeof window !== "undefined"
    ? (localStorage.getItem(AGENT_KEY) ?? "")
    : "";
  if (!agentKey) return null;
  try {
    const res = await fetch(`${BACKEND}/agent/status`, {
      headers: { "X-API-Key": agentKey },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ─── RCA History ──────────────────────────────────────────────────────────
export async function fetchRCAHistory(): Promise<RCAReport[]> {
  try {
    const data = await apiFetch<{ reports: RCAReport[] }>("/rca-history");
    return data.reports ?? [];
  } catch {
    return [];
  }
}

// ─── Log Ingestion (Test Error) ───────────────────────────────────────────
export interface IngestPayload {
  service: string;
  logs: string;
  severity?: string;
  env?: string;
}

export async function ingestTestLog(payload: IngestPayload): Promise<void> {
  const agentKey = typeof window !== "undefined"
    ? (localStorage.getItem(AGENT_KEY) ?? "")
    : "";
  if (!agentKey) throw new Error("Missing agent API key");
  const errorPayload = {
    service: payload.service,
    error: payload.logs,
    stacktrace: "",
    recent_logs: payload.logs.split("\n").filter(Boolean),
    env: payload.env || "production",
    extra: {
      source: "lov_frontend_test",
      severity: payload.severity || "high",
    },
  };
  await apiFetch("/ingest-error", {
    method: "POST",
    headers: {
      "X-API-Key": agentKey,
    },
    body: JSON.stringify(errorPayload),
  });
}

// ─── Health ───────────────────────────────────────────────────────────────
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
