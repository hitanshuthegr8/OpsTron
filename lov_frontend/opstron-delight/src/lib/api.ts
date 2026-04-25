/**
 * OpsTron Backend API Client
 * All calls go to the deployed FastAPI backend on Render.
 */

export const BACKEND = import.meta.env.VITE_BACKEND_URL || "https://opstron.onrender.com";

// ─── Auth token helpers ────────────────────────────────────────────────────
export const TOKEN_KEY = "ops_token";
export const AGENT_KEY = "ops_agent_key";

function appPath(path: string): string {
  const base = import.meta.env.BASE_URL || "/";
  const cleanBase = base.endsWith("/") ? base.slice(0, -1) : base;
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${cleanBase}${cleanPath}`;
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
    const err = await res.text().catch(() => res.statusText);
    throw new Error(err);
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
    recommended_actions?: string[];
    recommendations?: string[];
    error_signals?: string[];
    signals?: string[];
  };
}

export interface AgentStatusResponse {
  status: string;
  agent_connected?: boolean;
  monitored_containers?: string[];
  hostname?: string;
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
  webhookUrl?: string,
): Promise<{ message: string; webhook_id?: number }> {
  return apiFetch("/integrations/install-webhook", {
    method: "POST",
    body: JSON.stringify({
      owner,
      repo,
      webhook_url: webhookUrl ?? `${BACKEND}/notify-deployment`,
    }),
  });
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
