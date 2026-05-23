import { createFileRoute, Navigate } from "@tanstack/react-router";
import { useAppState, useHydrated } from "@/lib/opstronic-store";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "OpsTronic — Autonomous incident response for production systems" },
      {
        name: "description",
        content:
          "OpsTronic monitors your services, classifies critical incidents, and pages the right humans before customers notice.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  const hydrated = useHydrated();
  const state = useAppState();
  if (!hydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }
  if (!state.user) return <Navigate to="/login" />;
  if (!state.setupComplete) return <Navigate to="/onboarding" />;
  return <Navigate to="/dashboard" />;
}
