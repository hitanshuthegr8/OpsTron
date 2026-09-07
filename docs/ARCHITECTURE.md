# Architecture

How OpsTron is put together, and why. For setup see the [README](../README.md).

## The core idea

Everything routes through one function:

```python
RCAOrchestrator.analyze(service, repo, log_text, metadata, commit_analysis_override=None)
```

Four agents run over an incident, and a synthesizer combines their output into a structured report. Every entry point — the manual upload, the automated ingest, the CI/CD webhook, the public demo — reaches the same function. That is deliberate: there is exactly one implementation of "what OpsTron does", so a demo cannot drift from the product.

```
             ┌─────────────────────────────────────────┐
   entry     │  /analyze   /ingest-error   /demo/...   │
   points    └──────────────────┬──────────────────────┘
                                │
                     RCAOrchestrator.analyze()
                                │
            ┌───────────────┬───┴───────┬───────────────┐
            ▼               ▼           ▼               │
       LogAgent       CommitAgent   RunbookAgent        │
       (signals)      (GitHub API)  (ChromaDB RAG)      │
            └───────────────┴───────────┘               │
                            ▼                           │
                    SynthesizerAgent  ◄─────────────────┘
                       (Groq LLM)
                            ▼
                    structured RCA report
```

## The four agents

| Agent | Input | Output | Failure behaviour |
|---|---|---|---|
| `LogAgent` | raw log text | error signals, stack frames | **fatal** — no signals, no analysis |
| `CommitAgent` | repo name | recent commits + changed files | **non-fatal** — empty commits, weaker RCA |
| `RunbookAgent` | error signals | matching runbook excerpts | **non-fatal** — empty results |
| `SynthesizerAgent` | all of the above | the report | **fatal** — nothing to return |

The fatal/non-fatal split is the interesting decision. Commits and runbooks are *context*: without them the model produces a thinner but still useful answer. Logs and synthesis are *load-bearing*: without either there is no report at all, and returning a degraded one would be lying about confidence.

Steps 1–3 are independent and currently run **sequentially**. Making them concurrent is a genuine open improvement (see [Known gaps](#known-gaps)).

## Request paths

**Authenticated product.** Docker forwarder → `/agent/logs/ingest` (service API key) → dedup and severity → orchestrator → Supabase → dashboard, and a Twilio call if severity crosses the threshold.

**CI/CD.** GitHub Actions → `/notify-deployment` (HMAC-SHA256) → watch window opens → errors during the window are marked deployment-related.

**Public demo.** Browser → `/demo/scenarios/{id}/analyze` (no auth, rate limited) → seeded fixture → orchestrator → report.

## The demo boundary

The demo is the only unauthenticated surface that costs money, so its design is deliberate.

`/analyze` also runs without auth, but accepts an **arbitrary uploaded log file**. Exposing that from a public page would put attacker-controlled text into an LLM prompt and hand out unbounded model spend. The demo instead accepts only a **scenario id**, used solely as a key into a fixed server-side mapping:

```python
scenario = get_scenario(scenario_id)   # dict lookup
if scenario is None:
    raise HTTPException(404)           # nothing has run yet
```

No visitor-controlled text reaches a prompt, a database write, or an outbound request. That is a boundary by *construction* — there is no filter to keep ahead of an adversary.

**Honesty.** The incident is a fixture; the analysis is genuinely produced on request by the same orchestrator. Every response carries a `provenance` object naming which half is which, rendered above the fold. A pipeline failure returns **503** rather than a stored report, because a demo that silently serves a fixture when the pipeline is down is indistinguishable from one that never worked.

`commit_analysis_override` exists for one reason: live commits from this repository would attribute real OpsTron commits to a fictional checkout-api bug — incoherent, and wrong as evidence. Production paths pass nothing and are unaffected.

## Data stores

**Supabase (Postgres)** — users, sessions, incidents, deployments, agent events, alert settings. The backend uses the **service key** and bypasses RLS; the browser never sees it. Absent config, the app runs **stateless**: analysis works, nothing persists. This is what makes one-env-var setup possible.

**ChromaDB (vectors)** — the runbook corpus, embedded and searched by similarity. Indexed **at startup**, not at build time, because the deployment filesystem is ephemeral and a build-time index would not survive a restart.

## Configuration

The backend reads config at **runtime** from `agent/.env` or the environment. The frontend bakes `VITE_BACKEND_URL` in at **build** time. That asymmetry matters: a backend URL change needs a frontend *rebuild*, not a restart — and getting it wrong silently ships a bundle pointing at the wrong server.

Two settings behaviours worth knowing:

- `cors_origins()` always includes `FRONTEND_URL` **and** any `CORS_ALLOWED_ORIGINS`. They are additive, not alternatives — the OAuth callback redirects to `FRONTEND_URL`, so dropping it would refuse the origin the app sends users back to.
- `cors_origin_regex()` allows any localhost port outside production, because Vite silently falls back to another port when its default is taken.

## Trust boundaries

| From | To | Mechanism |
|---|---|---|
| Browser | backend | session token (GitHub OAuth) |
| Docker forwarder | backend | per-user service API key |
| GitHub Actions | backend | HMAC-SHA256 signature |
| Anonymous visitor | `/demo/*` | none — fixed enum input, rate limited |
| Backend | Supabase | service key (bypasses RLS) |
| Backend | GitHub / Groq | API tokens |

The forwarder **pushes** logs outward rather than the server pulling them. Pulling would require exposing the Docker socket to the backend, which is effectively remote code execution on the monitored host. The forwarder also regex-filters at the edge so only error lines cross the network.

## Testing

`agent/tests/` — 26 deterministic tests, no network. `pytest -m integration` opts into 1 test that makes a real Groq call. The split is enforced by `addopts = -m "not integration"` in `pytest.ini`, because a default suite must not make billed, non-deterministic calls.

Against LLM output, tests assert **structure and constraints** — `confidence in {low, medium, high}` — never exact text.

## Known gaps

Honest list of what is not done:

- **Sequential pipeline.** Steps 1–3 could run concurrently; roughly 3–4s of the ~10s latency is avoidable.
- **Shallow health check.** `/health` reports healthy when Supabase is unreachable.
- **In-memory rate limiting.** Per process, so the effective limit is `limit × instances`.
- **No build identity.** No endpoint exposes the running commit SHA, which made a wrong-deployment mix-up much harder to diagnose than it should have been.
- **No tracing or metrics.** Logs only.
- **Single demo scenario.** One good one beats five mediocre ones, but more breadth would show more.
