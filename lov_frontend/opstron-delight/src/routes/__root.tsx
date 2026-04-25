import { Outlet, Link, createRootRoute, HeadContent, Scripts } from "@tanstack/react-router";
import { useEffect } from "react";
import { initFromOAuthCallback, refreshSession, useAppState, useHydrated } from "@/lib/opstron-store";
import { TOKEN_KEY, appPath } from "@/lib/api";

import appCss from "../styles.css?url";


function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "OpsTron — Autonomous Incident Response" },
      { name: "description", content: "AI-powered root cause analysis for production incidents." },
      { property: "og:title", content: "OpsTron" },
      { property: "og:description", content: "AI-powered incident response — know what broke and why, before customers notice." },
      { property: "og:type", content: "website" },
    ],
    links: [{ rel: "stylesheet", href: appCss }],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
});

function RootShell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <HeadContent />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        {children}
        <Scripts />
      </body>
    </html>
  );
}

/**
 * Root component: captures ?token= from URL after GitHub OAuth redirect,
 * then silently refreshes the session on every page load.
 */
function RootComponent() {
  const hydrated = useHydrated();

  useEffect(() => {
    if (typeof window === "undefined") return;

    // 1. Capture token from URL if redirected from OAuth callback
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    if (urlToken) {
      // Strip the token from the URL immediately
      params.delete("token");
      const newSearch = params.toString();
      const newUrl =
        window.location.pathname + (newSearch ? `?${newSearch}` : "") + window.location.hash;
      window.history.replaceState({}, document.title, newUrl);

      // Bootstrap the session from this fresh token
      initFromOAuthCallback(urlToken).then((ok) => {
        if (ok) {
          window.location.href = appPath("/onboarding");
        } else {
          window.location.href = appPath("/login");
        }
      });
      return;
    }

    // 2. On every normal load: silently refresh session if a token exists
    const existingToken = localStorage.getItem(TOKEN_KEY);
    if (existingToken && hydrated) {
      refreshSession();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated]);

  return <Outlet />;
}
