import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, useMemo, useCallback } from "react";
import {
  AlertTriangle, Activity, Search, Filter, CheckCircle2,
  XCircle, Clock, TrendingUp, Upload, FileText, Send, RefreshCw,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  addTestIncident, relativeTime, setIncidentStatus, setRCAReports,
  setAgentStatus, useAppState, useHydrated,
  type IncidentStatus, type Severity, type RCAReport,
} from "@/lib/opstron-store";
import { fetchRCAHistory, fetchAgentStatus, checkHealth, ingestTestLog, AGENT_KEY } from "@/lib/api";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — OpsTron" },
      { name: "description", content: "Live incidents, RCA reports, and runbooks." },
    ],
  }),
  component: () => <AppShell><DashboardPage /></AppShell>,
});

type Section = "overview" | "incidents" | "runbooks" | "test";

function DashboardPage() {
  const navigate = useNavigate();
  const hydrated = useHydrated();
  const state = useAppState();
  const [section, setSection] = useState<Section>("overview");
  const [refreshing, setRefreshing] = useState(false);

  // Auth guard
  useEffect(() => {
    if (hydrated && !state.user) navigate({ to: "/login" });
  }, [hydrated, state.user, navigate]);

  // Load RCA reports + agent status on mount
  const refresh = useCallback(async () => {
    setRefreshing(true);
    const [reports, agentSt, backendOk] = await Promise.all([
      fetchRCAHistory(),
      fetchAgentStatus(),
      checkHealth(),
    ]);
    setRCAReports(reports);
    const connected = agentSt?.status === "connected" || agentSt?.agent_connected === true;
    setAgentStatus(connected, backendOk);
    setRefreshing(false);
  }, []);

  useEffect(() => { if (hydrated && state.user) refresh(); }, [hydrated, state.user, refresh]);

  if (!hydrated || !state.user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="px-5 py-6 sm:px-8">
      {/* Page header */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            {state.user.name ? `Welcome back, ${state.user.name.split(" ")[0]}.` : "Welcome back."}{" "}
            Live signals across your services.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className={cn(
            "flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1.5 text-xs",
            state.agentConnected ? "text-success" : "text-muted-foreground",
          )}>
            <span className={cn(
              "size-1.5 rounded-full",
              state.agentConnected ? "bg-success animate-pulse" : "bg-muted-foreground",
            )} />
            {state.agentConnected ? "Agent online" : "Agent offline"} · {state.onboarding.repo || "no repo"}
          </div>
          <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing} className="gap-2">
            <RefreshCw className={cn("size-4", refreshing && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-border bg-card/40 p-1 mb-6">
        {(["overview", "incidents", "runbooks", "test"] as Section[]).map((t) => (
          <button
            key={t}
            onClick={() => setSection(t)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground capitalize",
              section === t && "bg-background text-foreground shadow-sm",
            )}
          >
            {t === "test" ? "Test errors" : t}
          </button>
        ))}
      </div>

      {section === "overview" && <Overview onNavigate={setSection} />}
      {section === "incidents" && <Incidents />}
      {section === "runbooks" && <Runbooks />}
      {section === "test" && <TestErrors />}
    </div>
  );
}

// ─── Overview ────────────────────────────────────────────────────────────────
function Overview({ onNavigate }: { onNavigate: (s: Section) => void }) {
  const { incidents, rcaReports } = useAppState();
  const open = incidents.filter((i) => i.status !== "resolved").length;
  const critical = incidents.filter((i) => i.severity === "critical" && i.status !== "resolved").length;
  const ack = incidents.filter((i) => i.status === "acknowledged").length;

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Open incidents" value={String(open)} icon={AlertTriangle} tone="warning" />
        <Stat label="Critical" value={String(critical)} icon={XCircle} tone="destructive" />
        <Stat label="Acknowledged" value={String(ack)} icon={Clock} tone="info" />
        <Stat label="RCA Reports" value={String(rcaReports.length)} icon={TrendingUp} tone="success" />
      </div>

      {/* RCA Reports */}
      <div className="rounded-xl border border-border bg-card/60 shadow-[var(--shadow-elegant)]">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <div className="text-sm font-semibold">Recent RCA Reports</div>
            <div className="text-xs text-muted-foreground">AI-analyzed production incidents</div>
          </div>
          <Button variant="outline" size="sm" onClick={() => onNavigate("incidents")}>
            View all →
          </Button>
        </div>
        <RCAList reports={rcaReports.slice(0, 5)} />
      </div>
    </div>
  );
}

// ─── RCA List ─────────────────────────────────────────────────────────────────
function RCAList({ reports }: { reports: RCAReport[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (reports.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <div className="grid size-10 place-items-center rounded-full bg-muted text-muted-foreground">
          <Activity className="size-4" />
        </div>
        <div className="text-sm font-medium">No RCA reports yet</div>
        <div className="max-w-xs text-xs text-muted-foreground">
          Push a commit or trigger a test error. OpsTron will analyze it and show the full breakdown here.
        </div>
      </div>
    );
  }

  return (
    <div className="divide-y divide-border">
      {reports.map((r) => {
        const id = String(r.id);
        const rca = r.rca_report ?? {};
        const confidence = (rca.confidence ?? "medium").toLowerCase();
        const rootCause = rca.root_cause ?? r.error ?? "Unknown root cause";
        const actions = rca.recommended_actions ?? rca.recommendations ?? [];
        const isOpen = expanded === id;
        const confColor = confidence === "high" ? "text-success" : confidence === "medium" ? "text-warning" : "text-destructive";
        const borderColor = confidence === "high" ? "border-l-success" : confidence === "medium" ? "border-l-warning" : "border-l-destructive";

        return (
          <div key={id} className={cn("border-l-4 px-5 py-4 transition-colors hover:bg-accent/20 cursor-pointer", borderColor)}
            onClick={() => setExpanded(isOpen ? null : id)}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    ⚡ {r.service ?? "unknown-service"}
                  </span>
                  <span className={cn("text-xs font-medium", confColor)}>
                    {confidence.charAt(0).toUpperCase() + confidence.slice(1)} confidence
                  </span>
                  {r.is_deployment_related && (
                    <span className="rounded-full bg-orange-500/15 px-2 py-0.5 text-xs font-medium text-orange-400">
                      🚀 Deployment
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-sm font-medium truncate">{r.error ?? "Error"}</p>
                <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">{rootCause}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1 text-xs text-muted-foreground">
                {r.analyzed_at && <span>{relativeTime(new Date(r.analyzed_at).getTime())}</span>}
                {r.processing_time_ms && <span>⏱ {(r.processing_time_ms / 1000).toFixed(1)}s</span>}
              </div>
            </div>

            {/* Expanded detail */}
            {isOpen && (
              <div className="mt-4 space-y-3 rounded-lg border border-border bg-background/50 p-4 text-sm">
                {rca.summary && <p className="text-muted-foreground">{rca.summary}</p>}
                {actions.length > 0 && (
                  <div>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Recommended Actions
                    </div>
                    <ol className="space-y-1.5 list-decimal list-inside text-xs text-foreground">
                      {actions.map((a, i) => <li key={i}>{a}</li>)}
                    </ol>
                  </div>
                )}
                {r.deployment_context?.commit_sha && (
                  <div className="flex items-center gap-2 rounded bg-muted px-3 py-2 text-xs font-mono">
                    <span className="text-muted-foreground">commit</span>
                    <span className="text-primary">{r.deployment_context.commit_sha.slice(0, 12)}</span>
                    {r.deployment_context.author && (
                      <span className="text-muted-foreground">by {r.deployment_context.author}</span>
                    )}
                  </div>
                )}
                {(r.error || r.raw_error) && (
                  <details className="text-xs">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                      Raw stacktrace
                    </summary>
                    <pre className="mt-2 max-h-48 overflow-auto rounded bg-[#0d1117] p-3 text-[11px] text-[#94a3b8] whitespace-pre-wrap">
                      {r.raw_error ?? r.error}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Incidents ────────────────────────────────────────────────────────────────
function Incidents() {
  const { incidents } = useAppState();
  const [q, setQ] = useState("");
  const [sev, setSev] = useState<"all" | Severity>("all");
  const [status, setStatus] = useState<"all" | IncidentStatus>("all");

  const filtered = useMemo(() =>
    incidents.filter((i) => {
      if (sev !== "all" && i.severity !== sev) return false;
      if (status !== "all" && i.status !== status) return false;
      if (q && !`${i.message} ${i.service} ${i.ticketId}`.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    }), [incidents, q, sev, status]);

  return (
    <div className="rounded-xl border border-border bg-card/60 shadow-[var(--shadow-elegant)]">
      <div className="flex flex-wrap items-center gap-2 border-b border-border p-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search incidents…" className="pl-8" />
        </div>
        <Select value={sev} onValueChange={(v) => setSev(v as "all" | Severity)}>
          <SelectTrigger className="w-[140px]"><SelectValue placeholder="Severity" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All severities</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={(v) => setStatus(v as "all" | IncidentStatus)}>
          <SelectTrigger className="w-[150px]"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="acknowledged">Acknowledged</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" className="gap-2"><Filter className="size-4" /> Export</Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-[11px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-5 py-3 text-left">Service</th>
              <th className="px-5 py-3 text-left">Message</th>
              <th className="px-5 py-3 text-left">Severity</th>
              <th className="px-5 py-3 text-left">Ticket</th>
              <th className="px-5 py-3 text-left">Detected</th>
              <th className="px-5 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((i) => (
              <tr key={i.id} className="border-t border-border/60 hover:bg-accent/30">
                <td className="px-5 py-3 font-medium">{i.service}</td>
                <td className="px-5 py-3 max-w-[360px] truncate text-muted-foreground">{i.message}</td>
                <td className="px-5 py-3"><SeverityDot s={i.severity} /></td>
                <td className="px-5 py-3 font-mono text-xs text-muted-foreground">{i.ticketId}</td>
                <td className="px-5 py-3 text-muted-foreground">{relativeTime(i.detectedAt)}</td>
                <td className="px-5 py-3 text-right">
                  {i.status === "open" && (
                    <Button size="sm" variant="ghost" onClick={() => setIncidentStatus(i.id, "acknowledged")}>Acknowledge</Button>
                  )}
                  {i.status === "acknowledged" && (
                    <Button size="sm" variant="ghost" onClick={() => setIncidentStatus(i.id, "resolved")}>
                      <CheckCircle2 className="size-3.5" /> Resolve
                    </Button>
                  )}
                  {i.status === "resolved" && (
                    <span className="inline-flex items-center gap-1 text-xs text-success">
                      <CheckCircle2 className="size-3.5" /> Resolved
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-12 text-center text-sm text-muted-foreground">
                  No incidents match your filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Runbooks ──────────────────────────────────────────────────────────────────
function Runbooks() {
  const [files, setFiles] = useState<{ name: string; size: number }[]>([]);
  const [drag, setDrag] = useState(false);
  return (
    <div className="space-y-5">
      <label
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault(); setDrag(false);
          const f = Array.from(e.dataTransfer.files).map((f) => ({ name: f.name, size: f.size }));
          setFiles((prev) => [...prev, ...f]);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed bg-card/40 px-6 py-12 text-center transition-colors",
          drag ? "border-primary bg-primary/5" : "border-border hover:border-primary/50",
        )}
      >
        <input type="file" className="hidden" multiple accept=".md,.markdown,.txt,.pdf"
          onChange={(e) => {
            const f = Array.from(e.target.files ?? []).map((f) => ({ name: f.name, size: f.size }));
            setFiles((prev) => [...prev, ...f]);
          }} />
        <div className="grid size-12 place-items-center rounded-full bg-primary/10 text-primary">
          <Upload className="size-5" />
        </div>
        <div>
          <div className="text-sm font-medium">Drop runbooks here, or click to upload</div>
          <div className="text-xs text-muted-foreground">Markdown, text, or PDF · max 10 MB each</div>
        </div>
      </label>
      <div className="rounded-xl border border-border bg-card/60">
        <div className="border-b border-border px-5 py-3 text-sm font-semibold">Uploaded runbooks</div>
        {files.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <div className="text-sm font-medium text-muted-foreground">No runbooks yet</div>
            <div className="text-xs text-muted-foreground max-w-xs">OpsTron uses runbooks to suggest remediation steps during incidents.</div>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {files.map((f, i) => (
              <li key={i} className="flex items-center gap-3 px-5 py-3">
                <FileText className="size-4 text-muted-foreground" />
                <div className="flex-1 truncate text-sm">{f.name}</div>
                <div className="text-xs text-muted-foreground">{(f.size / 1024).toFixed(1)} KB</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ─── Test Errors ──────────────────────────────────────────────────────────────
function TestErrors() {
  const state = useAppState();
  const [service, setService] = useState("");
  const [message, setMessage] = useState("");
  const [severity, setSeverity] = useState<Severity>("high");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!service.trim() || !message.trim()) return;
    setSending(true);
    setError("");
    try {
      const agentKey = typeof window !== "undefined"
        ? (localStorage.getItem(AGENT_KEY) ?? state.user?.agentApiKey ?? "")
        : "";

      if (agentKey) {
        // Send to real backend
        await ingestTestLog({ service: service.trim(), logs: message.trim(), severity });
      }
      // Also add to local incidents list for immediate UI feedback
      addTestIncident({ service: service.trim(), message: message.trim(), severity });
      setSent(true);
      setService("");
      setMessage("");
      setTimeout(() => setSent(false), 3000);
    } catch (e: unknown) {
      setError((e as Error).message ?? "Failed to send test error");
    } finally {
      setSending(false);
    }
  };

  return (
    <form onSubmit={submit} className="max-w-xl space-y-5 rounded-xl border border-border bg-card/60 p-6 shadow-[var(--shadow-elegant)]">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Send a test error</h2>
        <p className="text-sm text-muted-foreground">Verify your alerting pipeline end-to-end. This sends a real payload to the AI engine.</p>
      </div>
      <div>
        <Label className="mb-1.5 block text-sm">Service name</Label>
        <Input value={service} onChange={(e) => setService(e.target.value)} placeholder="payments-api" required />
      </div>
      <div>
        <Label className="mb-1.5 block text-sm">Error message / log</Label>
        <Textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Database connection timeout after 30s…" required rows={4} />
      </div>
      <div>
        <Label className="mb-1.5 block text-sm">Severity</Label>
        <Select value={severity} onValueChange={(v) => setSeverity(v as Severity)}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={sending} className="min-w-32">
          {sending ? (
            <span className="size-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
          ) : (
            <><Send className="size-4" /> Trigger</>
          )}
        </Button>
        {sent && <span className="text-sm text-success">✓ Test incident sent to AI engine.</span>}
      </div>
    </form>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function Stat({ label, value, icon: Icon, tone }: {
  label: string; value: string;
  icon: React.ComponentType<{ className?: string }>;
  tone: "warning" | "destructive" | "info" | "success";
}) {
  const toneCls: Record<typeof tone, string> = {
    warning: "text-warning bg-warning/10",
    destructive: "text-destructive bg-destructive/10",
    info: "text-info bg-info/10",
    success: "text-success bg-success/10",
  };
  return (
    <div className="rounded-xl border border-border bg-card/60 p-5 shadow-[var(--shadow-elegant)]">
      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={cn("grid size-8 place-items-center rounded-md", toneCls[tone])}>
          <Icon className="size-4" />
        </div>
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function SeverityDot({ s }: { s: Severity }) {
  const map: Record<Severity, { color: string; label: string }> = {
    critical: { color: "bg-destructive", label: "Critical" },
    high: { color: "bg-warning", label: "High" },
    medium: { color: "bg-info", label: "Medium" },
    low: { color: "bg-success", label: "Low" },
  };
  return (
    <span className="inline-flex items-center gap-2 text-xs">
      <span className={cn("size-1.5 rounded-full", map[s].color)} />
      {map[s].label}
    </span>
  );
}