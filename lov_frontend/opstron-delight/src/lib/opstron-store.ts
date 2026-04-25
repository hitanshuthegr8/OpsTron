import { useEffect, useState, useSyncExternalStore } from "react";
import {
  clearAuth,
  fetchMe,
  AGENT_KEY,
  setToken,
  TOKEN_KEY,
  type BackendUser,
  type RCAReport,
} from "./api";

// ---- Types ----
export type Severity = "critical" | "high" | "medium" | "low";
export type IncidentStatus = "open" | "acknowledged" | "resolved";

export interface Incident {
  id: string;
  ticketId: string;
  service: string;
  message: string;
  severity: Severity;
  status: IncidentStatus;
  detectedAt: number;
}

export interface OnboardingData {
  repo: string;
  connectedRepoOwner: string;
  connectedRepoName: string;
  voiceAlerts: boolean;
  phone: string;
  threshold: Severity;
  cooldownMinutes: number;
  slackWebhook: string;
  onCallEmail: string;
}

export interface User {
  id: string;
  name: string;
  username: string;
  email: string;
  avatarUrl: string;
  agentApiKey: string;
}

export interface AppState {
  user: User | null;
  token: string;
  apiKey: string;
  setupComplete: boolean;
  onboarding: OnboardingData;
  incidents: Incident[];
  rcaReports: RCAReport[];
  agentConnected: boolean;
  backendOnline: boolean;
}

const KEY = "opstron:state:v2";

const defaultOnboarding: OnboardingData = {
  repo: "",
  connectedRepoOwner: "",
  connectedRepoName: "",
  voiceAlerts: true,
  phone: "",
  threshold: "high",
  cooldownMinutes: 15,
  slackWebhook: "",
  onCallEmail: "",
};

const defaultState: AppState = {
  user: null,
  token: "",
  apiKey: "",
  setupComplete: false,
  onboarding: defaultOnboarding,
  incidents: [],
  rcaReports: [],
  agentConnected: false,
  backendOnline: false,
};

let state: AppState = defaultState;
let listeners = new Set<() => void>();
let hydrated = false;

function load(): AppState {
  if (typeof window === "undefined") return defaultState;
  try {
    // Token always comes from localStorage directly (set by OAuth callback handler)
    const token = localStorage.getItem(TOKEN_KEY) ?? "";
    const raw = localStorage.getItem(KEY);
    const parsed: Partial<AppState> = raw ? (JSON.parse(raw) as AppState) : {};
    return {
      ...defaultState,
      ...parsed,
      token,
      onboarding: { ...defaultOnboarding, ...(parsed.onboarding ?? {}) },
    };
  } catch {
    return defaultState;
  }
}

function persist() {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY, JSON.stringify(state));
}

function emit() {
  listeners.forEach((l) => l());
}

export function setState(
  patch: Partial<AppState> | ((s: AppState) => Partial<AppState>),
) {
  const next = typeof patch === "function" ? patch(state) : patch;
  state = { ...state, ...next };
  persist();
  emit();
}

export function getState(): AppState {
  return state;
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function useAppState(): AppState {
  useEffect(() => {
    if (!hydrated) {
      state = load();
      hydrated = true;
      emit();
    }
  }, []);
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => defaultState,
  );
}

// ---- Actions ----

/**
 * Called after GitHub OAuth redirects back with ?token=...
 * Persists the token, fetches real user from /auth/me, updates state.
 */
export async function initFromOAuthCallback(token: string): Promise<boolean> {
  setToken(token);
  const backendUser = await fetchMe();
  if (!backendUser) return false;

  const user: User = {
    id: backendUser.github_id,
    name: backendUser.name ?? backendUser.login,
    username: backendUser.login,
    email: backendUser.email ?? "",
    avatarUrl: backendUser.avatar_url,
    agentApiKey: backendUser.agent_api_key,
  };

  // Persist agent API key so polling works
  if (typeof window !== "undefined") {
    localStorage.setItem(AGENT_KEY, backendUser.agent_api_key);
  }

  setState({ user, token, apiKey: backendUser.agent_api_key, setupComplete: false });
  return true;
}

/**
 * Called on every page load if a token already exists in localStorage.
 * Re-validates the session and refreshes the user object.
 */
export async function refreshSession(): Promise<boolean> {
  const token = typeof window !== "undefined"
    ? (localStorage.getItem(TOKEN_KEY) ?? "")
    : "";
  if (!token) return false;

  const backendUser = await fetchMe();
  if (!backendUser) return false;

  const user: User = {
    id: backendUser.github_id,
    name: backendUser.name ?? backendUser.login,
    username: backendUser.login,
    email: backendUser.email ?? "",
    avatarUrl: backendUser.avatar_url,
    agentApiKey: backendUser.agent_api_key,
  };

  if (typeof window !== "undefined") {
    localStorage.setItem(AGENT_KEY, backendUser.agent_api_key);
  }

  setState({ user, token, apiKey: backendUser.agent_api_key });
  return true;
}

export function logout() {
  clearAuth();
  if (typeof window !== "undefined") localStorage.removeItem(KEY);
  state = { ...defaultState };
  hydrated = false;
  persist();
  emit();
}

export function regenerateApiKey() {
  // TODO: Implement actual backend call to rotate API key
  console.warn("regenerateApiKey is currently a stub and does not generate a new key.");
  return getState().apiKey;
}

export function completeOnboarding(data: OnboardingData) {
  setState({ onboarding: data, setupComplete: true });
}

export function setRCAReports(reports: RCAReport[]) {
  setState({ rcaReports: reports });
}

export function setAgentStatus(connected: boolean, backendOnline: boolean) {
  setState({ agentConnected: connected, backendOnline });
}

export function addTestIncident(input: {
  service: string;
  message: string;
  severity: Severity;
}) {
  const inc: Incident = {
    id: `inc_${Date.now()}`,
    ticketId: `SLT-${Math.floor(1500 + Math.random() * 500)}`,
    service: input.service,
    message: input.message,
    severity: input.severity,
    status: "open",
    detectedAt: Date.now(),
  };
  setState((s) => ({ incidents: [inc, ...s.incidents] }));
}

export function setIncidentStatus(id: string, status: IncidentStatus) {
  setState((s) => ({
    incidents: s.incidents.map((i) => (i.id === id ? { ...i, status } : i)),
  }));
}

export function wipeAccount() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(AGENT_KEY);
  }
  state = { ...defaultState };
  hydrated = false;
  persist();
  emit();
}

// ---- Helpers ----
export function relativeTime(ts: number): string {
  const diff = Math.max(0, Date.now() - ts);
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export function useHydrated() {
  const [h, setH] = useState(false);
  useEffect(() => setH(true), []);
  return h;
}

// Re-export RCAReport type for consumers
export type { RCAReport } from "./api";