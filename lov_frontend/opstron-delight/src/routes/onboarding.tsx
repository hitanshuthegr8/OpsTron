import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, useCallback } from "react";
import {
  GitBranch,
  Container,
  PhoneCall,
  Check,
  ChevronRight,
  ChevronLeft,
  Activity,
  Search,
  Copy,
  CheckCheck,
  RefreshCw,
  Lock,
  Globe,
  Star,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import {
  completeOnboarding,
  useAppState,
  useHydrated,
  type OnboardingData,
  type Severity,
} from "@/lib/opstron-store";
import {
  fetchRepos,
  installWebhook,
  fetchAgentStatus,
  AGENT_KEY,
  BACKEND,
  type Repo,
} from "@/lib/api";

export const Route = createFileRoute("/onboarding")({
  head: () => ({
    meta: [
      { title: "Set up OpsTron — Connect repo, agent, and alerts" },
      { name: "description", content: "Three-step setup: connect a repo, install the Docker agent, and configure paging." },
    ],
  }),
  component: OnboardingPage,
});

const steps = [
  { id: 1, title: "Connect repository", icon: GitBranch },
  { id: 2, title: "Docker agent", icon: Container },
  { id: 3, title: "Alerts & paging", icon: PhoneCall },
];

// ─────────────────────────────────────────────────────────────────────────────
function OnboardingPage() {
  const navigate = useNavigate();
  const state = useAppState();
  const hydrated = useHydrated();
  const [step, setStep] = useState(1);
  const [data, setData] = useState<OnboardingData>({
    repo: "",
    connectedRepoOwner: "",
    connectedRepoName: "",
    voiceAlerts: true,
    phone: "",
    threshold: "high",
    cooldownMinutes: 15,
    slackWebhook: "",
    onCallEmail: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!hydrated) return;
    if (!state.user) navigate({ to: "/login" });
    else if (state.setupComplete) navigate({ to: "/dashboard" });
  }, [hydrated, state.user, state.setupComplete, navigate]);

  if (!hydrated || !state.user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const set = <K extends keyof OnboardingData>(k: K, v: OnboardingData[K]) =>
    setData((d) => ({ ...d, [k]: v }));

  const validate = (s: number) => {
    const e: Record<string, string> = {};
    if (s === 1 && !data.connectedRepoOwner) e.repo = "Please select and connect a repository first.";
    if (s === 3) {
      if (data.voiceAlerts && !/^\+?[\d\s\-()]{7,}$/.test(data.phone)) {
        e.phone = "Enter a valid phone number (e.g. +1 555 010 1234)";
      }
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const next = () => {
    if (!validate(step)) return;
    if (step < 3) setStep(step + 1);
    else finish();
  };
  const back = () => setStep((s) => Math.max(1, s - 1));

  const finish = async () => {
    if (!validate(3)) return;
    setSubmitting(true);
    await new Promise((r) => setTimeout(r, 400));
    completeOnboarding(data);
    navigate({ to: "/dashboard" });
  };

  return (
    <div className="relative min-h-screen px-4 py-10 sm:px-8">
      <div className="pointer-events-none absolute inset-0 -z-10 [background:var(--gradient-glow)]" />

      <div className="mx-auto max-w-3xl">
        {/* Logo */}
        <div className="mb-8 flex items-center gap-2">
          <div className="grid size-8 place-items-center rounded-md bg-[image:var(--gradient-primary)] text-primary-foreground shadow-[var(--shadow-glow)]">
            <Activity className="size-4" />
          </div>
          <span className="text-base font-semibold tracking-tight">OpsTron setup</span>
        </div>

        {/* Stepper */}
        <ol className="mb-8 flex items-center gap-2">
          {steps.map((s, i) => {
            const active = step === s.id;
            const done = step > s.id;
            return (
              <li key={s.id} className="flex flex-1 items-center gap-2">
                <div
                  className={cn(
                    "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium",
                    active && "border-primary bg-primary/10 text-primary",
                    done && "border-success/30 bg-success/10 text-success",
                    !active && !done && "border-border text-muted-foreground",
                  )}
                >
                  {done ? <Check className="size-3.5" /> : <s.icon className="size-3.5" />}
                  <span className="hidden sm:inline">{s.title}</span>
                  <span className="sm:hidden">Step {s.id}</span>
                </div>
                {i < steps.length - 1 && <div className="h-px flex-1 bg-border" />}
              </li>
            );
          })}
        </ol>

        {/* Card */}
        <div className="rounded-xl border border-border bg-card/60 p-6 shadow-[var(--shadow-elegant)] backdrop-blur sm:p-8">
          {step === 1 && (
            <StepRepo data={data} set={set} errors={errors} apiKey={state.user.agentApiKey} />
          )}
          {step === 2 && (
            <StepDocker apiKey={state.user.agentApiKey} />
          )}
          {step === 3 && (
            <StepAlerts data={data} set={set} errors={errors} />
          )}

          {/* Footer nav */}
          <div className="mt-8 flex items-center justify-between border-t border-border pt-5">
            <Button variant="ghost" onClick={back} disabled={step === 1}>
              <ChevronLeft className="size-4" /> Back
            </Button>
            <Button onClick={next} disabled={submitting} className="min-w-36">
              {submitting ? (
                <span className="size-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
              ) : step === 3 ? (
                "Finish setup"
              ) : (
                <>Continue <ChevronRight className="size-4" /></>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Step 1: Real Repo Picker ─────────────────────────────────────────────────
function StepRepo({
  data,
  set,
  errors,
  apiKey,
}: {
  data: OnboardingData;
  set: <K extends keyof OnboardingData>(k: K, v: OnboardingData[K]) => void;
  errors: Record<string, string>;
  apiKey: string;
}) {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Repo | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(!!data.connectedRepoOwner);
  const [webhookUrl, setWebhookUrl] = useState("");

  const loadRepos = useCallback(async () => {
    setLoading(true);
    setFetchError("");
    try {
      const r = await fetchRepos();
      setRepos(r);
    } catch (e: unknown) {
      setFetchError((e as Error).message ?? "Failed to load repositories");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRepos(); }, [loadRepos]);

  const filtered = repos.filter((r) =>
    !query || r.full_name.toLowerCase().includes(query.toLowerCase()),
  );

  const handleConnect = async () => {
    if (!selected) return;
    setConnecting(true);
    try {
      await installWebhook(selected.owner, selected.name, webhookUrl || undefined);
      set("repo", selected.full_name);
      set("connectedRepoOwner", selected.owner);
      set("connectedRepoName", selected.name);
      setConnected(true);
    } catch (e: unknown) {
      setFetchError((e as Error).message ?? "Webhook installation failed");
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div className="space-y-5">
      <Header
        title="Connect a repository"
        desc="OpsTron watches for pushes to your repo. Select one and we'll install the webhook automatically."
      />

      {/* Repo search + list */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search repositories…"
            className="pl-8"
          />
        </div>

        <div className="max-h-72 overflow-y-auto rounded-lg border border-border divide-y divide-border">
          {loading && (
            <div className="flex items-center justify-center gap-3 py-8 text-sm text-muted-foreground">
              <span className="size-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              Loading your repositories…
            </div>
          )}
          {!loading && fetchError && (
            <div className="py-8 text-center text-sm text-destructive">{fetchError}</div>
          )}
          {!loading && !fetchError && filtered.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">No repositories found.</div>
          )}
          {!loading && filtered.map((r) => (
            <button
              key={r.id}
              onClick={() => { setSelected(r); setConnected(false); }}
              className={cn(
                "flex w-full items-center gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-accent/30",
                selected?.id === r.id && "bg-primary/10",
              )}
            >
              {r.private ? (
                <Lock className="size-4 shrink-0 text-muted-foreground" />
              ) : (
                <Globe className="size-4 shrink-0 text-muted-foreground" />
              )}
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{r.full_name}</div>
                {r.description && (
                  <div className="text-xs text-muted-foreground truncate">{r.description}</div>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                {r.language && <span>{r.language}</span>}
                {r.stars > 0 && (
                  <span className="flex items-center gap-0.5">
                    <Star className="size-3" />{r.stars}
                  </span>
                )}
                {selected?.id === r.id && <Check className="size-4 text-primary" />}
              </div>
            </button>
          ))}
        </div>

        {/* Refresh */}
        <Button variant="outline" size="sm" onClick={loadRepos} className="gap-2">
          <RefreshCw className="size-3.5" /> Refresh list
        </Button>
      </div>

      {/* Optional webhook URL override */}
      <div className="space-y-1.5">
        <Label className="text-sm">Backend public URL <span className="text-muted-foreground">(optional)</span></Label>
        <Input
          value={webhookUrl}
          onChange={(e) => setWebhookUrl(e.target.value)}
          placeholder="https://opstron.onrender.com  (leave blank to use default)"
        />
        <p className="text-[11px] text-muted-foreground">
          GitHub needs to reach your backend. Leave blank to use the default Render URL.
        </p>
      </div>

      {/* Connect button */}
      {selected && !connected && (
        <Button onClick={handleConnect} disabled={connecting} className="w-full">
          {connecting ? (
            <span className="size-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
          ) : (
            <>Install webhook for <strong className="ml-1">{selected.full_name}</strong></>
          )}
        </Button>
      )}

      {/* Success banner */}
      {connected && (
        <div className="flex items-center gap-3 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success">
          <CheckCheck className="size-4 shrink-0" />
          <div>
            <div className="font-medium">Webhook installed!</div>
            <div className="text-xs text-muted-foreground mt-0.5">{data.repo} — OpsTron will receive every push event.</div>
          </div>
        </div>
      )}

      {errors.repo && <p className="text-xs text-destructive">{errors.repo}</p>}
    </div>
  );
}

// ─── Step 2: Docker Agent Setup ───────────────────────────────────────────────
function StepDocker({ apiKey }: { apiKey: string }) {
  const [copiedCompose, setCopiedCompose] = useState(false);
  const [copiedRun, setCopiedRun] = useState(false);
  const [agentStatus, setAgentStatus] = useState<"waiting" | "connected">("waiting");

  // Poll for agent connection every 4 seconds
  useEffect(() => {
    const agentKey = typeof window !== "undefined"
      ? (localStorage.getItem(AGENT_KEY) ?? apiKey)
      : apiKey;

    const poll = async () => {
      const status = await fetchAgentStatus();
      if (status?.status === "connected" || status?.agent_connected === true) {
        setAgentStatus("connected");
      }
    };

    const timer = setInterval(poll, 4000);
    poll(); // immediate first check
    return () => clearInterval(timer);
  }, [apiKey]);

  const composeSnippet = `  opstron-agent:
    image: opstron/agent:latest
    restart: unless-stopped
    environment:
      OPSTRON_API_KEY: "${apiKey}"
      OPSTRON_BACKEND_URL: "${BACKEND}"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

  # Label any container you want OpsTron to watch:
  your-app:
    image: your-app:latest
    labels:
      opstron.monitor: "true"`;

  const runSnippet = `docker run -d \\
  -e OPSTRON_API_KEY="${apiKey}" \\
  -e OPSTRON_BACKEND_URL="${BACKEND}" \\
  -v /var/run/docker.sock:/var/run/docker.sock:ro \\
  --name opstron-agent \\
  --restart unless-stopped \\
  opstron/agent:latest`;

  const copy = async (text: string, which: "compose" | "run") => {
    await navigator.clipboard.writeText(text);
    if (which === "compose") { setCopiedCompose(true); setTimeout(() => setCopiedCompose(false), 2000); }
    else { setCopiedRun(true); setTimeout(() => setCopiedRun(false), 2000); }
  };

  return (
    <div className="space-y-6">
      <Header
        title="Install the Docker agent"
        desc="A lightweight sidecar that streams container errors to OpsTron's AI engine in real-time. Zero inbound traffic, zero code changes."
      />

      {/* Agent status */}
      <div className={cn(
        "flex items-center gap-3 rounded-lg border px-4 py-3 text-sm transition-colors",
        agentStatus === "connected"
          ? "border-success/30 bg-success/10 text-success"
          : "border-border bg-muted/30 text-muted-foreground",
      )}>
        <span className={cn(
          "size-2 rounded-full",
          agentStatus === "connected" ? "bg-success" : "animate-pulse bg-warning",
        )} />
        {agentStatus === "connected"
          ? "Agent connected! You can continue."
          : "Waiting for agent ping… (auto-detects when your container starts)"}
      </div>

      {/* Docker Compose */}
      <div className="space-y-2">
        <div className="text-sm font-medium">🐳 Docker Compose <span className="text-muted-foreground font-normal">(recommended)</span></div>
        <p className="text-xs text-muted-foreground">Add to your <code className="rounded bg-muted px-1 py-0.5">docker-compose.yml</code></p>
        <div className="relative rounded-lg border border-border bg-[#0d1117] p-4">
          <pre className="overflow-x-auto text-xs leading-relaxed text-[#94a3b8]">{composeSnippet}</pre>
          <button
            onClick={() => copy(composeSnippet, "compose")}
            className="absolute right-3 top-3 flex items-center gap-1.5 rounded-md border border-border bg-card/80 px-2 py-1 text-xs text-muted-foreground transition hover:text-foreground"
          >
            {copiedCompose ? <><CheckCheck className="size-3.5 text-success" /> Copied!</> : <><Copy className="size-3.5" /> Copy</>}
          </button>
        </div>
      </div>

      {/* Single docker run */}
      <div className="space-y-2">
        <div className="text-sm font-medium">🖥️ Or a single Docker command</div>
        <div className="relative rounded-lg border border-border bg-[#0d1117] p-4">
          <pre className="overflow-x-auto text-xs leading-relaxed text-[#94a3b8]">{runSnippet}</pre>
          <button
            onClick={() => copy(runSnippet, "run")}
            className="absolute right-3 top-3 flex items-center gap-1.5 rounded-md border border-border bg-card/80 px-2 py-1 text-xs text-muted-foreground transition hover:text-foreground"
          >
            {copiedRun ? <><CheckCheck className="size-3.5 text-success" /> Copied!</> : <><Copy className="size-3.5" /> Copy</>}
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          Then opt containers in: <code className="rounded bg-muted px-1 py-0.5">docker run --label opstron.monitor=true your-app</code>
        </p>
      </div>

      <p className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-xs text-muted-foreground">
        💡 You can skip this step and set up the agent later. The dashboard will prompt you to connect.
      </p>
    </div>
  );
}

// ─── Step 3: Alerts & Paging ──────────────────────────────────────────────────
function StepAlerts({
  data,
  set,
  errors,
}: {
  data: OnboardingData;
  set: <K extends keyof OnboardingData>(k: K, v: OnboardingData[K]) => void;
  errors: Record<string, string>;
}) {
  return (
    <div className="space-y-6">
      <Header title="Alerts & paging" desc="Decide who gets called, when, and how often." />

      {/* Voice alert toggle */}
      <div className="flex items-center justify-between rounded-lg border border-border bg-background/50 p-4">
        <div>
          <div className="text-sm font-medium">Voice alerts</div>
          <div className="text-xs text-muted-foreground">Call on-call when severity crosses threshold.</div>
        </div>
        <Switch checked={data.voiceAlerts} onCheckedChange={(v) => set("voiceAlerts", v)} />
      </div>

      {data.voiceAlerts && (
        <Field label="On-call phone number" error={errors.phone}>
          <Input
            placeholder="+1 555 010 1234"
            value={data.phone}
            onChange={(e) => set("phone", e.target.value)}
          />
        </Field>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Severity threshold">
          <Select value={data.threshold} onValueChange={(v) => set("threshold", v as Severity)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="critical">Critical only</SelectItem>
              <SelectItem value="high">High and above</SelectItem>
              <SelectItem value="medium">Medium and above</SelectItem>
              <SelectItem value="low">Everything</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Cooldown (minutes)">
          <Input
            type="number"
            min={1}
            value={data.cooldownMinutes}
            onChange={(e) => set("cooldownMinutes", Number(e.target.value) || 0)}
          />
        </Field>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Slack webhook (optional)">
          <Input
            placeholder="https://hooks.slack.com/services/…"
            value={data.slackWebhook}
            onChange={(e) => set("slackWebhook", e.target.value)}
          />
          <p className="mt-1 text-[11px] text-muted-foreground">Coming soon — saved for later.</p>
        </Field>
        <Field label="On-call email (optional)">
          <Input
            type="email"
            placeholder="oncall@acme.com"
            value={data.onCallEmail}
            onChange={(e) => set("onCallEmail", e.target.value)}
          />
          <p className="mt-1 text-[11px] text-muted-foreground">Coming soon — saved for later.</p>
        </Field>
      </div>
    </div>
  );
}

// ─── Shared sub-components ────────────────────────────────────────────────────
function Header({ title, desc }: { title: string; desc: string }) {
  return (
    <div>
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{desc}</p>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <Label className="mb-1.5 block text-sm">{label}</Label>
      {children}
      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
    </div>
  );
}