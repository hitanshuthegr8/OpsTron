import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Github, Activity, ShieldCheck, Zap, Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { appPath, redirectToGitHubOAuth } from "@/lib/api";
import { initFromOAuthCallback, useAppState, useHydrated } from "@/lib/opstron-store";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in to OpsTron" },
      { name: "description", content: "Sign in with GitHub to deploy autonomous monitoring across your services." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const state = useAppState();
  const hydrated = useHydrated();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [bootstrapping, setBootstrapping] = useState(false);

  // If already logged in, redirect away
  useEffect(() => {
    if (hydrated && state.user) {
      navigate({ to: state.setupComplete ? "/dashboard" : "/onboarding" });
    }
  }, [hydrated, state.user, state.setupComplete, navigate]);

  // Handle OAuth completion or error params on the login route itself.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const err = params.get("error");

    if (token) {
      setBootstrapping(true);
      setError("");
      params.delete("token");
      const newSearch = params.toString();
      const newUrl =
        window.location.pathname + (newSearch ? `?${newSearch}` : "") + window.location.hash;
      window.history.replaceState({}, document.title, newUrl);

      initFromOAuthCallback(token).then((ok) => {
        if (ok) {
          window.location.replace(appPath("/onboarding"));
        } else {
          setBootstrapping(false);
          setError("Authentication succeeded, but the app could not restore your session.");
        }
      }).catch(() => {
        setBootstrapping(false);
        setError("Authentication succeeded, but the app could not finish sign-in.");
      });
      return;
    }

    if (err) {
      setError(
        err === "access_denied"
          ? "GitHub access was denied. Please try again."
          : `Authentication failed: ${err}. Please try again.`,
      );
      // Clean URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const handleGithub = () => {
    setLoading(true);
    setError("");
    // Redirect to real GitHub OAuth via backend
    redirectToGitHubOAuth();
  };

  return (
    <div className="relative grid min-h-screen lg:grid-cols-2">
      {/* Glow background */}
      <div className="pointer-events-none absolute inset-0 -z-10 [background:var(--gradient-glow)]" />

      {/* Hero — left side (desktop only) */}
      <section className="hidden flex-col justify-between border-r border-border p-10 lg:flex">
        <div className="flex items-center gap-2">
          <div className="grid size-9 place-items-center rounded-md bg-[image:var(--gradient-primary)] text-primary-foreground shadow-[var(--shadow-glow)]">
            <Activity className="size-5" />
          </div>
          <span className="text-lg font-semibold tracking-tight">OpsTron</span>
        </div>

        <div>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight">
            Autonomous incident response for the systems you ship at 3&nbsp;AM.
          </h1>
          <p className="mt-4 max-w-md text-muted-foreground">
            OpsTron watches your Docker containers, links errors to the exact commit that broke
            production, and pages you via voice call — with a runbook attached — before customers notice.
          </p>

          <div className="mt-10 grid gap-5 max-w-md">
            <Feature icon={Bot} title="AI Root Cause Analysis" desc="GPT-4 powered error analysis across logs, commits, and runbooks." />
            <Feature icon={Zap} title="Voice paging" desc="Calls on-call engineers when severity crosses your threshold." />
            <Feature icon={ShieldCheck} title="Runbook-aware" desc="Attaches the right runbook step to every incident automatically." />
          </div>
        </div>

        <div className="text-xs text-muted-foreground">
          Built for DevOps teams who ship fast and sleep soundly.
        </div>
      </section>

      {/* Right: sign in card */}
      <section className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden mb-8 flex items-center gap-2">
            <div className="grid size-9 place-items-center rounded-md bg-[image:var(--gradient-primary)] text-primary-foreground shadow-[var(--shadow-glow)]">
              <Activity className="size-5" />
            </div>
            <span className="text-lg font-semibold tracking-tight">OpsTron</span>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight">Welcome back</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Sign in to continue to your incident dashboard.
          </p>

          <div className="mt-8 rounded-xl border border-border bg-card/60 p-6 shadow-[var(--shadow-elegant)] backdrop-blur">
            {error && (
              <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <Button
              size="lg"
              className="h-11 w-full bg-foreground text-background hover:bg-foreground/90"
              onClick={handleGithub}
              disabled={loading}
            >
              {loading ? (
                <span className="size-4 animate-spin rounded-full border-2 border-background border-t-transparent" />
              ) : (
                <Github className="size-5" />
              )}
              {loading ? "Redirecting to GitHub..." : "Continue with GitHub"}
            </Button>

            {bootstrapping && (
              <div className="mt-4 flex items-center gap-3 rounded-lg border border-border bg-background/60 px-4 py-3 text-sm text-muted-foreground">
                <span className="size-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                Finishing sign-in...
              </div>
            )}

            <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground">
              <div className="h-px flex-1 bg-border" />
              SSO &amp; email coming soon
              <div className="h-px flex-1 bg-border" />
            </div>

            <ul className="space-y-2 text-xs text-muted-foreground">
              <li className="flex items-center gap-2">
                <span className="size-1 rounded-full bg-success" />
                AI analysis of Docker container errors in seconds
              </li>
              <li className="flex items-center gap-2">
                <span className="size-1 rounded-full bg-success" />
                Automatic commit blame — know exactly what broke
              </li>
              <li className="flex items-center gap-2">
                <span className="size-1 rounded-full bg-success" />
                Voice alerts for critical production incidents
              </li>
            </ul>

            <p className="mt-5 text-center text-xs text-muted-foreground">
              By continuing you agree to our{" "}
              <a className="underline underline-offset-2 hover:text-foreground" href="#">Terms</a> and{" "}
              <a className="underline underline-offset-2 hover:text-foreground" href="#">Privacy Policy</a>.
            </p>
          </div>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            New to OpsTron? GitHub sign-in creates your account automatically.
          </p>
        </div>
      </section>
    </div>
  );
}

function Feature({
  icon: Icon,
  title,
  desc,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="grid size-9 shrink-0 place-items-center rounded-md border border-border bg-card text-primary">
        <Icon className="size-4" />
      </div>
      <div>
        <div className="text-sm font-medium">{title}</div>
        <div className="text-sm text-muted-foreground">{desc}</div>
      </div>
    </div>
  );
}
