/**
 * Presentation pieces for the public demo.
 *
 * Everything here renders data the backend measured or an agent returned.
 * Nothing on this page is generated in the browser — in particular the step
 * durations are timed around the real `await` server-side, which is why a stage
 * can legitimately read "instant".
 */

import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  FileText,
  GitCommit,
  Search,
} from "lucide-react";
import type { DemoIncident, DemoStep } from "@/lib/api";

const STEP_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  logs: FileText,
  commits: GitCommit,
  runbooks: Search,
  synthesis: Activity,
};

/** Turn a step's real fields into label/value pairs. Only shows what is present. */
function stepDetail(step: DemoStep): Array<[string, string[]]> {
  const out: Array<[string, string[]]> = [];
  if (step.signals?.length) out.push(["Signals found", step.signals]);
  if (step.key_errors?.length) out.push(["Key errors", step.key_errors]);
  if (step.stack_traces) out.push(["Stack traces", [`${step.stack_traces} extracted`]]);
  if (step.count !== undefined) out.push(["Commits", [`${step.count} analysed`]]);
  if (step.source)
    out.push(["Source", [step.source === "supplied" ? "seeded fixture" : "GitHub API"]]);
  if (step.query_signals?.length) out.push(["Search query", step.query_signals]);
  if (step.matches?.length) out.push(["Runbooks matched", step.matches]);
  if (step.confidence) out.push(["Confidence", [step.confidence]]);
  if (step.actions !== undefined) out.push(["Actions produced", [`${step.actions}`]]);
  return out;
}

/** One pipeline stage, expandable to show what that agent actually returned. */
export function StepRow({ step }: { step: DemoStep }) {
  const [open, setOpen] = useState(false);
  const Icon = STEP_ICON[step.step] ?? FileText;
  const detail = stepDetail(step);

  return (
    <div className="rounded-lg border border-border bg-background/60">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-muted/40"
      >
        <CheckCircle2 className="size-4 shrink-0 text-primary" />
        <Icon className="size-4 shrink-0 text-muted-foreground" />
        <span className="flex-1">{step.label}</span>
        <span className="font-mono text-xs text-muted-foreground">
          {step.duration_ms === 0 ? "instant" : `${(step.duration_ms / 1000).toFixed(2)}s`}
        </span>
        <ChevronDown
          className={`size-4 shrink-0 text-muted-foreground transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <div className="border-t border-border px-4 py-3">
          {detail.length === 0 ? (
            <p className="text-xs text-muted-foreground">No additional detail for this step.</p>
          ) : (
            <dl className="grid gap-2">
              {detail.map(([k, values]) => (
                <div key={k} className="grid gap-1 sm:grid-cols-[140px_1fr] sm:gap-3">
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {k}
                  </dt>
                  <dd className="flex flex-wrap gap-1.5">
                    {values.map((item) => (
                      <span
                        key={item}
                        className="rounded border border-border bg-muted/50 px-2 py-0.5 font-mono text-[11px]"
                      >
                        {item}
                      </span>
                    ))}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}
    </div>
  );
}

/** A commit as a card, with the gap to the first error computed, not asserted. */
export function CommitCard({
  commit,
  deployedAt,
  firstErrorAt,
  suspect,
}: {
  commit: DemoIncident["commits"][number];
  deployedAt: string;
  firstErrorAt: string;
  suspect: boolean;
}) {
  const gapMin = Math.round(
    (new Date(firstErrorAt).getTime() - new Date(deployedAt).getTime()) / 60000,
  );

  return (
    <div
      className={`rounded-lg border p-4 ${
        suspect ? "border-destructive/40 bg-destructive/5" : "border-border bg-background/60"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <GitCommit className="size-4 text-muted-foreground" />
        <code className="font-mono text-xs font-semibold">{commit.sha}</code>
        <span className="text-xs text-muted-foreground">{commit.author}</span>
        {suspect && (
          <span className="ml-auto rounded-full border border-destructive/40 bg-destructive/10 px-2 py-0.5 text-[11px] font-medium text-destructive">
            prime suspect
          </span>
        )}
      </div>

      <p className="mt-2 text-sm">{commit.message}</p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {commit.files_changed.map((f) => (
          <span
            key={f}
            className="rounded border border-border bg-muted/50 px-2 py-0.5 font-mono text-[11px] text-muted-foreground"
          >
            {f}
          </span>
        ))}
      </div>

      {suspect && (
        <div className="mt-3 flex items-center gap-2 text-xs text-destructive">
          <AlertTriangle className="size-3.5 shrink-0" />
          Deployed {gapMin} minutes before the first error
        </div>
      )}
    </div>
  );
}

/** The error lines pulled out of the log stream. */
export function LogCard({ log }: { log: string }) {
  const errorLines = log
    .split("\n")
    .filter((l) => l.includes("ERROR") || l.includes("CRIT"))
    .slice(0, 6);

  return (
    <div className="rounded-lg border border-border bg-background/60 p-4">
      <div className="flex items-center gap-2">
        <FileText className="size-4 text-muted-foreground" />
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Production logs
        </span>
      </div>

      <pre className="mt-3 overflow-x-auto font-mono text-[11px] leading-relaxed">
        {errorLines.join("\n")}
      </pre>

      <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
        <AlertTriangle className="size-3.5 shrink-0" />
        Repeating failure on the same endpoint, beginning after the deploy
      </div>
    </div>
  );
}

/** Runbooks the vector search actually returned, in rank order. */
export function RunbookCard({ matches }: { matches: string[] }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-4">
      <div className="flex items-center gap-2">
        <BookOpen className="size-4 text-muted-foreground" />
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Runbooks retrieved
        </span>
      </div>

      <div className="mt-3 grid gap-2">
        {matches.map((m, i) => (
          <div key={m} className="flex items-center gap-2 text-sm">
            <span className="grid size-5 shrink-0 place-items-center rounded bg-muted text-[11px] font-semibold text-muted-foreground">
              {i + 1}
            </span>
            {m}
          </div>
        ))}
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Ranked by vector similarity over the real runbook corpus — including matches the model then
        judged less relevant.
      </p>
    </div>
  );
}
