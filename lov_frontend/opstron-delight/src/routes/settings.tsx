import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Copy, Eye, EyeOff, RefreshCw, Save, Trash2 } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  completeOnboarding,
  logout,
  regenerateApiKey,
  useAppState,
  wipeAccount,
  type Severity,
} from "@/lib/opstron-store";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — OpsTron" },
      { name: "description", content: "Manage your profile, alerting rules, integrations, API keys and account." },
    ],
  }),
  component: () => (
    <AppShell>
      <SettingsPage />
    </AppShell>
  ),
});

type Tab = "profile" | "alerts" | "integrations" | "danger";

function SettingsPage() {
  const [tab, setTab] = useState<Tab>("profile");
  return (
    <div className="px-5 py-6 sm:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Configure how OpsTron behaves for your team.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[200px_1fr]">
        <nav className="flex flex-row gap-1 overflow-x-auto rounded-lg border border-border bg-card/40 p-1 lg:flex-col">
          {(["profile", "alerts", "integrations", "danger"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "rounded-md px-3 py-2 text-left text-sm font-medium capitalize text-muted-foreground transition-colors hover:text-foreground",
                tab === t && "bg-background text-foreground shadow-sm",
                t === "danger" && tab === t && "text-destructive",
              )}
            >
              {t === "danger" ? "Danger zone" : t}
            </button>
          ))}
        </nav>

        <div className="space-y-6">
          {tab === "profile" && <Profile />}
          {tab === "alerts" && <Alerts />}
          {tab === "integrations" && <Integrations />}
          {tab === "danger" && <Danger />}
        </div>
      </div>
    </div>
  );
}

function Card({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-card/60 shadow-[var(--shadow-elegant)]">
      <div className="border-b border-border px-6 py-4">
        <div className="text-sm font-semibold">{title}</div>
        {desc && <div className="text-xs text-muted-foreground">{desc}</div>}
      </div>
      <div className="p-6">{children}</div>
    </section>
  );
}

function Profile() {
  const state = useAppState();
  if (!state.user) return null;
  return (
    <Card title="Profile" desc="Synced from GitHub. Read-only.">
      <div className="flex items-center gap-4">
        <img src={state.user.avatarUrl} alt="" className="size-16 rounded-full bg-muted" />
        <div>
          <div className="text-base font-medium">{state.user.name}</div>
          <div className="text-sm text-muted-foreground">@{state.user.username}</div>
          <div className="text-sm text-muted-foreground">{state.user.email}</div>
        </div>
      </div>
    </Card>
  );
}

function Alerts() {
  const state = useAppState();
  const [data, setData] = useState(state.onboarding);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => setData(state.onboarding), [state.onboarding]);

  const save = async () => {
    setSaving(true);
    await new Promise((r) => setTimeout(r, 500));
    completeOnboarding(data);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <Card title="Alerts & paging" desc="Threshold, cadence, and channels.">
      <div className="space-y-5">
        <div className="flex items-center justify-between rounded-lg border border-border bg-background/50 p-4">
          <div>
            <div className="text-sm font-medium">Voice alerts</div>
            <div className="text-xs text-muted-foreground">Call on-call when severity crosses threshold.</div>
          </div>
          <Switch checked={data.voiceAlerts} onCheckedChange={(v) => setData({ ...data, voiceAlerts: v })} />
        </div>

        {data.voiceAlerts && (
          <div>
            <Label className="mb-1.5 block text-sm">On-call phone</Label>
            <Input value={data.phone} onChange={(e) => setData({ ...data, phone: e.target.value })} placeholder="+1 555 010 1234" />
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label className="mb-1.5 block text-sm">Severity threshold</Label>
            <Select value={data.threshold} onValueChange={(v) => setData({ ...data, threshold: v as Severity })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="critical">Critical only</SelectItem>
                <SelectItem value="high">High and above</SelectItem>
                <SelectItem value="medium">Medium and above</SelectItem>
                <SelectItem value="low">Everything</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="mb-1.5 block text-sm">Cooldown (minutes)</Label>
            <Input type="number" min={1} value={data.cooldownMinutes} onChange={(e) => setData({ ...data, cooldownMinutes: Number(e.target.value) || 0 })} />
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <Button onClick={save} disabled={saving} className="min-w-32">
            {saving ? <span className="size-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" /> : <><Save className="size-4" /> Save changes</>}
          </Button>
          {saved && <span className="text-sm text-success">Saved.</span>}
        </div>
      </div>
    </Card>
  );
}

function Integrations() {
  const state = useAppState();
  const [show, setShow] = useState(false);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(state.apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="space-y-6">
      <Card title="API key" desc="Use this to authenticate the OpsTron agent on your hosts.">
        <div className="flex items-center gap-2">
          <div className="flex-1 rounded-md border border-border bg-background px-3 py-2 font-mono text-sm">
            {show ? state.apiKey : "•".repeat(Math.min(40, state.apiKey.length))}
          </div>
          <Button variant="outline" size="icon" onClick={() => setShow((v) => !v)} aria-label="Toggle visibility">
            {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </Button>
          <Button variant="outline" size="icon" onClick={copy} aria-label="Copy">
            <Copy className="size-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={() => { if (confirm("Regenerate API key? The previous key will stop working.")) regenerateApiKey(); }}>
            <RefreshCw className="size-4" /> Regenerate
          </Button>
        </div>
        {copied && <p className="mt-2 text-xs text-success">Copied to clipboard.</p>}
      </Card>

      <Card title="Channels" desc="Where OpsTron sends notifications.">
        <div className="space-y-4">
          <Row name="Slack" value={state.onboarding.slackWebhook} placeholder="No webhook configured" />
          <Row name="Email" value={state.onboarding.onCallEmail} placeholder="No email configured" />
          <Row name="PagerDuty" value="" placeholder="Coming soon" comingSoon />
        </div>
      </Card>
    </div>
  );
}

function Row({ name, value, placeholder, comingSoon }: { name: string; value: string; placeholder: string; comingSoon?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 pb-3 last:border-0 last:pb-0">
      <div>
        <div className="text-sm font-medium">{name}</div>
        <div className="truncate text-xs text-muted-foreground">{value || placeholder}</div>
      </div>
      <Button variant="outline" size="sm" disabled={comingSoon}>{comingSoon ? "Coming soon" : value ? "Edit" : "Connect"}</Button>
    </div>
  );
}

function Danger() {
  const navigate = useNavigate();
  const [text, setText] = useState("");

  const wipe = () => {
    wipeAccount();
    logout();
    navigate({ to: "/login" });
  };

  return (
    <section className="rounded-xl border border-destructive/40 bg-destructive/5">
      <div className="border-b border-destructive/30 px-6 py-4">
        <div className="text-sm font-semibold text-destructive">Danger zone</div>
        <div className="text-xs text-muted-foreground">These actions cannot be undone.</div>
      </div>
      <div className="space-y-4 p-6">
        <p className="text-sm">
          Type <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">DELETE</code> to wipe your OpsTron account, integrations, and incident history.
        </p>
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="DELETE" />
        <Button variant="destructive" disabled={text !== "DELETE"} onClick={wipe}>
          <Trash2 className="size-4" /> Permanently delete account
        </Button>
      </div>
    </section>
  );
}