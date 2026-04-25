import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import {
  LayoutDashboard,
  AlertTriangle,
  BookOpen,
  Settings,
  LogOut,
  Activity,
} from "lucide-react";
import { useAppState, logout, useHydrated } from "@/lib/opstron-store";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard, section: "overview" as const },
  { to: "/dashboard", label: "Incidents", icon: AlertTriangle, section: "incidents" as const },
  { to: "/dashboard", label: "Runbooks", icon: BookOpen, section: "runbooks" as const },
  { to: "/dashboard", label: "Test Errors", icon: Activity, section: "test" as const },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const state = useAppState();
  const navigate = useNavigate();
  const hydrated = useHydrated();
  const location = useLocation();

  useEffect(() => {
    if (!hydrated) return;
    if (!state.user) navigate({ to: "/login" });
    else if (!state.setupComplete && location.pathname !== "/onboarding") navigate({ to: "/onboarding" });
  }, [hydrated, state.user, state.setupComplete, location.pathname, navigate]);

  if (!hydrated || !state.user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      {/* Sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
        <div className="flex h-16 items-center gap-2 border-b border-sidebar-border px-5">
          <div className="grid size-8 place-items-center rounded-md bg-[image:var(--gradient-primary)] text-primary-foreground shadow-[var(--shadow-glow)]">
            <Activity className="size-4" />
          </div>
          <div className="text-base font-semibold tracking-tight">OpsTron</div>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {nav.map((item) => {
            const active = location.pathname === item.to;
            return (
              <Link
                key={item.label}
                to={item.to}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  active && "bg-sidebar-accent text-sidebar-accent-foreground",
                )}
              >
                <item.icon className="size-4" />
                {item.label}
              </Link>
            );
          })}
          <Link
            to="/settings"
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              location.pathname === "/settings" && "bg-sidebar-accent text-sidebar-accent-foreground",
            )}
          >
            <Settings className="size-4" />
            Settings
          </Link>
        </nav>
        <div className="border-t border-sidebar-border p-3">
          <div className="flex items-center gap-3 rounded-md p-2">
            <img src={state.user.avatarUrl} alt="" className="size-8 rounded-full bg-muted" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{state.user.name}</div>
              <div className="truncate text-xs text-muted-foreground">@{state.user.username}</div>
            </div>
            <button
              onClick={() => {
                logout();
                navigate({ to: "/login" });
              }}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
              aria-label="Sign out"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-sidebar-border bg-sidebar md:hidden">
        {[...nav.slice(0, 3), { to: "/settings", label: "Settings", icon: Settings }].map((item) => {
          const active = location.pathname === item.to;
          return (
            <Link
              key={item.label}
              to={item.to}
              className={cn(
                "flex flex-1 flex-col items-center gap-1 py-2 text-[11px] text-sidebar-foreground/70",
                active && "text-primary",
              )}
            >
              <item.icon className="size-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <main className="min-w-0 flex-1 pb-16 md:pb-0">
        {children}
      </main>
    </div>
  );
}