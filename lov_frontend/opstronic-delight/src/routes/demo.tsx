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
import { CommitCard, LogCard, RunbookCard, StepRow } from "@/components/demo-parts";

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

function DemoPage() {
  const [incident, setIncident] = useState<DemoIncident | null>(null);
  const [provenance, setProvenance] = useState<DemoProvenance | null>(null);
  const [analysis, setAnalysis] = useState<DemoAnalysis | null>(null);
  const [running, setRunning] = useState(false);
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

  const run = useCallback(async () => {
    setRunning(true);
    setError("");
    setAnalysis(null);
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
  // Taken from the measured runbooks step rather than parsed out of the
  // model's prose, so the cards show exactly what retrieval returned.
  const runbookMatches = analysis?.steps.find((s) => s.step === "runbooks")?.matches ?? [];

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
          <div className="flex items-center gap-3 rounded-lg border border-primary/50 bg-primary/5 px-4 py-4 text-sm">
            <Loader2 className="size-4 animate-spin text-primary" />
            Running the pipeline — four agents over the incident above.
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
          <div className="grid gap-2">
            {analysis.steps.map((s) => (
              <StepRow key={s.step} step={s} />
            ))}
            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              <CheckCircle2 className="size-3.5 text-primary" />
              Four agents, {(analysis.total_duration_ms / 1000).toFixed(1)}s total. Every duration
              above was measured server-side during this run.
              <Button variant="ghost" size="sm" onClick={run} className="ml-auto">
                Run again
              </Button>
            </div>
          </div>
        )}
      </Section>

      {report && (
        <>
          {/* 3. EVIDENCE */}
          <Section step="03" title="Evidence" subtitle="What it found" icon={FileText}>
            <div className="grid gap-3">
              <LogCard log={incident.log_excerpt} />

              {incident.commits.map((c) => (
                <CommitCard
                  key={c.sha}
                  commit={c}
                  deployedAt={incident.deployed_at}
                  firstErrorAt={incident.first_error_at}
                  // The suspect marker follows the model's conclusion rather than
                  // a hardcoded sha, so a different verdict relabels the card.
                  suspect={(report.root_cause ?? "").includes(c.sha)}
                />
              ))}

              {!!runbookMatches.length && <RunbookCard matches={runbookMatches} />}
            </div>

            <details className="mt-4">
              <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
                Show the raw evidence the model was given
              </summary>
              <div className="mt-3 grid gap-3">
                <Evidence label="From the logs" body={report.evidence?.logs} />
                <Evidence label="From the commit history" body={report.evidence?.commits} />
                <Evidence label="From the runbooks" body={report.evidence?.runbooks} />
              </div>
            </details>
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
      {/* A faint top glow keeps a flat monochrome page from reading as dead. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-[image:var(--gradient-glow)]"
      />

      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Link to="/login" className="group flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-md bg-[image:var(--gradient-primary)] text-primary-foreground">
              <Activity className="size-4" />
            </div>
            <span className="font-semibold tracking-tight">OpsTron</span>
          </Link>
          <span className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
            <span className="relative flex size-1.5">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-foreground opacity-60" />
              <span className="relative inline-flex size-1.5 rounded-full bg-foreground" />
            </span>
            Live demo
          </span>
        </div>
      </header>

      <div className="relative mx-auto grid max-w-3xl gap-6 px-6 py-12">{children}</div>
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
    // The left rail plus the numeral turns five stacked cards into a visible
    // sequence, which is the whole point of the page: one thing leads to the next.
    <section className="relative rounded-xl border border-border bg-card/60 shadow-[var(--shadow-elegant)] backdrop-blur">
      <div
        aria-hidden
        className={`absolute inset-y-0 left-0 w-px ${
          tone === "destructive" ? "bg-foreground/50" : "bg-border"
        }`}
      />
      <div className="flex items-start gap-4 border-b border-border px-6 py-4">
        <div
          className={`grid size-9 shrink-0 place-items-center rounded-md border ${
            tone === "destructive"
              ? "border-foreground/30 bg-foreground/10 text-foreground"
              : "border-border bg-muted/60 text-muted-foreground"
          }`}
        >
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[11px] tracking-widest text-muted-foreground">
              {step}
            </span>
            <h2 className="truncate text-base font-semibold tracking-tight">{title}</h2>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      <div className="px-6 py-5">{children}</div>
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

/**
 * Confidence, expressed in a monochrome palette.
 *
 * With no hue available, the three levels are separated by contrast: high is
 * solid white on black, medium is outlined, low is dim. Filled reads as more
 * emphatic than outlined, which preserves the ranking a colour ramp would
 * normally carry. The dots repeat the level non-redundantly for anyone who
 * finds contrast alone ambiguous.
 */
function ConfidenceBadge({ value }: { value?: string }) {
  const v = (value ?? "unknown").toLowerCase();
  const filled = v === "high";
  const dots = v === "high" ? 3 : v === "medium" ? 2 : 1;

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${
        filled
          ? "border-primary bg-primary text-primary-foreground"
          : v === "medium"
            ? "border-foreground/40 text-foreground"
            : "border-border text-muted-foreground"
      }`}
    >
      <span className="flex gap-0.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`size-1.5 rounded-full ${
              i < dots
                ? filled
                  ? "bg-primary-foreground"
                  : "bg-foreground"
                : filled
                  ? "bg-primary-foreground/30"
                  : "bg-foreground/20"
            }`}
          />
        ))}
      </span>
      {v} confidence
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
