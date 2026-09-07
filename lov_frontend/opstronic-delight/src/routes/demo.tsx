import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileText,
  GitCommit,
  Loader2,
  Search,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  fetchDemoIncident,
  runDemoAnalysis,
  type DemoAnalysis,
  type DemoIncident,
  type DemoProvenance,
} from "@/lib/api";

export const Route = createFileRoute("/demo")({
  head: () => ({
    meta: [
      { title: "OpsTron — Live incident demo" },
      {
        name: "description",
        content:
          "Watch OpsTron investigate a production incident: evidence, root cause, and remediation, generated live.",
      },
    ],
  }),
  component: DemoPage,
});

const SCENARIO_ID = "pool-exhaustion";

/**
 * The investigation steps shown while the request is in flight.
 *
 * These mirror the four stages the orchestrator actually runs
 * (LogAgent -> CommitAgent -> RunbookAgent -> SynthesizerAgent). They are a
 * progress indication, not a live trace: the backend returns one response at
 * the end rather than streaming per-stage events, so the timings here are
 * indicative. Labelled as such in the UI so nothing is overstated.
 */
const STAGES = [
  { label: "Parsing log stream for error signals", icon: FileText },
  { label: "Correlating with recent deployments", icon: GitCommit },
  { label: "Searching runbooks for matching procedures", icon: Search },
  { label: "Synthesising root cause analysis", icon: Activity },
];

function DemoPage() {
  const [incident, setIncident] = useState<DemoIncident | null>(null);
  const [provenance, setProvenance] = useState<DemoProvenance | null>(null);
  const [analysis, setAnalysis] = useState<DemoAnalysis | null>(null);
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    fetchDemoIncident(SCENARIO_ID)
      .then((d) => {
        setIncident(d.incident);
        setProvenance(d.provenance);
      })
      .catch((e) => setLoadError(e.message));
  }, []);

  // Advance the stage indicator while the single request is in flight.
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 2200);
    return () => clearInterval(t);
  }, [running]);

  const run = useCallback(async () => {
    setRunning(true);
    setError("");
    setAnalysis(null);
    setStage(0);
    try {
      setAnalysis(await runDemoAnalysis(SCENARIO_ID));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setRunning(false);
    }
  }, []);

  if (loadError) {
    return (
      <Shell>
        <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
          Could not reach the OpsTron backend: {loadError}
        </div>
      </Shell>
    );
  }

  if (!incident) {
    return (
      <Shell>
        <div className="flex items-center gap-3 py-24 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading incident…
        </div>
      </Shell>
    );
  }

  const report = analysis?.report;

  return (
    <Shell>
      <ProvenanceBanner provenance={provenance} />

      {/* 1. WHAT HAPPENED */}
      <Section
        step="01"
        title="The incident"
        subtitle="What went wrong"
        icon={AlertTriangle}
        tone="destructive"
      >
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="destructive">{incident.severity.toUpperCase()}</Pill>
          <Pill>{incident.service}</Pill>
          <Pill>{incident.impact}</Pill>
        </div>
        <p className="mt-4 text-sm text-muted-foreground">{incident.summary}</p>

        <div className="mt-5 grid gap-2">
          {incident.signals.map((s) => (
            <div
              key={s}
              className="rounded-lg border border-border bg-muted/40 px-3 py-2 font-mono text-xs"
            >
              {s}
            </div>
          ))}
        </div>

        <details className="mt-5 group">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
            View raw log stream
          </summary>
          <pre className="mt-3 max-h-72 overflow-auto rounded-lg border border-border bg-background/80 p-4 text-[11px] leading-relaxed">
            {incident.log_excerpt}
          </pre>
        </details>
      </Section>

      {/* 2. INVESTIGATION */}
      <Section step="02" title="Investigation" subtitle="What OpsTron does with it" icon={Search}>
        {!analysis && !running && (
          <>
            <p className="text-sm text-muted-foreground">
              OpsTron runs four agents over this incident: it extracts error signals from the logs,
              correlates them with recent commits, retrieves matching runbooks by vector search, and
              synthesises a root cause. Nothing below this point is pre-written — press the button
              and the model produces it now.
            </p>
            <Button onClick={run} size="lg" className="mt-6 gap-2">
              Run the investigation <ArrowRight className="size-4" />
            </Button>
            <p className="mt-3 text-xs text-muted-foreground">
              Takes about 10 seconds. No sign-in, no setup.
            </p>
          </>
        )}

        {running && (
          <div className="grid gap-3">
            {STAGES.map((s, i) => {
              const Icon = s.icon;
              const done = i < stage;
              const active = i === stage;
              return (
                <div
                  key={s.label}
                  className={`flex items-center gap-3 rounded-lg border px-4 py-3 text-sm transition-colors ${
                    active
                      ? "border-primary/50 bg-primary/5"
                      : done
                        ? "border-border bg-muted/30 text-muted-foreground"
                        : "border-border/60 text-muted-foreground/60"
                  }`}
                >
                  {done ? (
                    <CheckCircle2 className="size-4 text-primary" />
                  ) : active ? (
                    <Loader2 className="size-4 animate-spin text-primary" />
                  ) : (
                    <Icon className="size-4" />
                  )}
                  {s.label}
                </div>
              );
            })}
            <p className="mt-1 text-xs text-muted-foreground">
              Stage indicator reflects the pipeline's four agents; the backend returns one response
              when synthesis completes.
            </p>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
            <Button variant="outline" size="sm" onClick={run} className="ml-3">
              Retry
            </Button>
          </div>
        )}

        {analysis && !running && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <CheckCircle2 className="size-4 text-primary" />
            Investigation complete — four agents ran over the incident above.
            <Button variant="ghost" size="sm" onClick={run} className="ml-auto">
              Run again
            </Button>
          </div>
        )}
      </Section>

      {report && (
        <>
          {/* 3. EVIDENCE */}
          <Section step="03" title="Evidence" subtitle="What it found" icon={FileText}>
            <div className="grid gap-3">
              <Evidence label="From the logs" body={report.evidence?.logs} />
              <Evidence label="From the commit history" body={report.evidence?.commits} />
              <Evidence label="From the runbooks" body={report.evidence?.runbooks} />
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              Runbook matches come from a vector search over the real runbook corpus in this
              repository — not from the incident fixture.
            </p>
          </Section>

          {/* 4 + 5. ROOT CAUSE + CONFIDENCE */}
          <Section step="04" title="Root cause" subtitle="What it concluded" icon={Activity}>
            <div className="flex flex-wrap items-center gap-2">
              <ConfidenceBadge value={report.confidence} />
            </div>
            <p className="mt-4 text-[15px] leading-relaxed">{report.root_cause}</p>

            {!!report.contributing_factors?.length && (
              <div className="mt-6">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Contributing factors
                </h4>
                <ul className="mt-3 grid gap-2">
                  {report.contributing_factors.map((f) => (
                    <li key={f} className="flex gap-2 text-sm text-muted-foreground">
                      <span className="mt-[7px] size-1 shrink-0 rounded-full bg-muted-foreground" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {report.timeline && (
              <div className="mt-6">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Timeline
                </h4>
                <p className="mt-2 text-sm text-muted-foreground">{report.timeline}</p>
              </div>
            )}
          </Section>

          {/* 6. RESOLUTION */}
          <Section
            step="05"
            title="Recommended resolution"
            subtitle="What to do next"
            icon={Wrench}
          >
            <ol className="grid gap-3">
              {(report.recommended_actions ?? []).map((a, i) => (
                <li key={a} className="flex gap-3 rounded-lg border border-border bg-card/40 p-4">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                    {i + 1}
                  </span>
                  <span className="text-sm">{a}</span>
                </li>
              ))}
            </ol>
          </Section>

          <div className="rounded-xl border border-border bg-card/40 p-6">
            <h3 className="text-sm font-semibold">That is the whole loop.</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              In production the log stream arrives from a Docker sidecar instead of a fixture, and
              the commit history is fetched live from your repository. Everything after that — the
              four agents, the retrieval, the synthesis — is what you just watched.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Button asChild variant="outline">
                <a
                  href="https://github.com/hitanshuthegr8/OpsTron"
                  target="_blank"
                  rel="noreferrer"
                >
                  Read the code
                </a>
              </Button>
              <Button asChild variant="ghost">
                <Link to="/login">Sign in with GitHub</Link>
              </Button>
            </div>
          </div>
        </>
      )}
    </Shell>
  );
}

/* ── layout ─────────────────────────────────────────────────────────────── */

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Link to="/login" className="flex items-center gap-2">
            <div className="grid size-8 place-items-center rounded-md bg-[image:var(--gradient-primary)] text-primary-foreground shadow-[var(--shadow-glow)]">
              <Activity className="size-4" />
            </div>
            <span className="font-semibold tracking-tight">OpsTron</span>
          </Link>
          <span className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
            Live demo
          </span>
        </div>
      </header>
      <div className="mx-auto grid max-w-3xl gap-8 px-6 py-10">{children}</div>
    </main>
  );
}

function ProvenanceBanner({ provenance }: { provenance: DemoProvenance | null }) {
  if (!provenance) return null;
  return (
    <div className="rounded-xl border border-border bg-muted/30 p-5">
      <div className="flex items-center gap-2 text-sm font-medium">
        <ShieldCheck className="size-4 text-primary" />
        What&apos;s real here
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Simulated
          </div>
          <ul className="mt-2 grid gap-1 text-xs text-muted-foreground">
            {provenance.simulated.map((x) => (
              <li key={x}>· {x}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-primary">
            Generated live
          </div>
          <ul className="mt-2 grid gap-1 text-xs text-muted-foreground">
            {provenance.generated_live.map((x) => (
              <li key={x}>· {x}</li>
            ))}
          </ul>
        </div>
      </div>
      <p className="mt-4 text-xs text-muted-foreground">{provenance.note}</p>
    </div>
  );
}

function Section({
  step,
  title,
  subtitle,
  icon: Icon,
  tone,
  children,
}: {
  step: string;
  title: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  tone?: "destructive";
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card/60 p-6 shadow-[var(--shadow-elegant)] backdrop-blur">
      <div className="flex items-center gap-3">
        <div
          className={`grid size-9 place-items-center rounded-md ${
            tone === "destructive"
              ? "bg-destructive/10 text-destructive"
              : "bg-primary/10 text-primary"
          }`}
        >
          <Icon className="size-4" />
        </div>
        <div>
          <div className="text-[11px] font-medium tracking-widest text-muted-foreground">
            {step}
          </div>
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        </div>
        <span className="ml-auto text-xs text-muted-foreground">{subtitle}</span>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Evidence({ label, body }: { label: string; body?: string }) {
  if (!body) return null;
  return (
    <div className="rounded-lg border border-border bg-background/60 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <pre className="mt-2 whitespace-pre-wrap font-mono text-xs leading-relaxed">{body}</pre>
    </div>
  );
}

function ConfidenceBadge({ value }: { value?: string }) {
  const v = (value ?? "unknown").toLowerCase();
  const tone =
    v === "high"
      ? "border-primary/40 bg-primary/10 text-primary"
      : v === "medium"
        ? "border-amber-500/40 bg-amber-500/10 text-amber-500"
        : "border-border bg-muted text-muted-foreground";
  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-medium ${tone}`}>
      Confidence: {v}
    </span>
  );
}

function Pill({ children, tone }: { children: React.ReactNode; tone?: "destructive" }) {
  return (
    <span
      className={`rounded-full border px-3 py-1 text-xs font-medium ${
        tone === "destructive"
          ? "border-destructive/40 bg-destructive/10 text-destructive"
          : "border-border bg-muted/50 text-muted-foreground"
      }`}
    >
      {children}
    </span>
  );
}
