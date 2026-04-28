# OpsTron Goated Flow Explanation

This document explains the full OpsTron journey from the user's first login all the way to:

- onboarding
- the commands the user runs
- what happens during normal monitoring
- what happens on deployment
- what happens when logs contain errors
- what happens when a container crashes or restarts
- what happens when the backend or agent restarts

It is written to give both:

- a product/user-flow view
- a technical/code-path view

The main code paths referenced here are:

- [agent/main.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/main.py)
- [agent/app/api/routes/auth.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/api/routes/auth.py)
- [agent/app/api/routes/ingest.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/api/routes/ingest.py)
- [agent/app/core/orchestrator.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/orchestrator.py)
- [agent/app/core/event_engine.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/event_engine.py)
- [agent/app/core/watch_manager.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/watch_manager.py)
- [agent/app/api/middleware/auth.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/api/middleware/auth.py)
- [agent/app/db/supabase_client.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/db/supabase_client.py)
- [agent/opstron_forwarder.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/opstron_forwarder.py)
- [lov_frontend/opstron-delight/src/routes/__root.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/__root.tsx)
- [lov_frontend/opstron-delight/src/routes/login.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/login.tsx)
- [lov_frontend/opstron-delight/src/routes/onboarding.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/onboarding.tsx)
- [lov_frontend/opstron-delight/src/routes/dashboard.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/dashboard.tsx)
- [lov_frontend/opstron-delight/src/lib/opstron-store.ts](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/lib/opstron-store.ts)
- [lov_frontend/opstron-delight/src/lib/api.ts](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/lib/api.ts)

---

## 1. Big Picture

OpsTron is made of two major parts:

1. Frontend dashboard
   - React + TanStack Router
   - handles login, onboarding, dashboard, settings

2. Backend RCA engine
   - FastAPI
   - receives deployment signals and runtime/container signals
   - correlates them
   - runs RCA
   - stores history in Supabase
   - optionally triggers voice alerts

There is also a third important piece:

3. Docker agent / forwarder
   - runs near the user's containers
   - watches opted-in containers
   - sends heartbeats
   - sends logs
   - sends structured crash events

So the real system shape is:

`User -> Frontend -> FastAPI backend <- Docker agent <- User's containers`

and also:

`GitHub push -> GitHub webhook -> FastAPI backend`

---

## 2. Core User Journey

The user journey is:

1. User opens the frontend.
2. If not logged in, user is sent to login.
3. User clicks GitHub login.
4. GitHub redirects back with a session token.
5. Frontend stores the token and fetches user info.
6. User is sent to onboarding.
7. User connects a GitHub repo.
8. User copies Docker agent setup commands/snippets.
9. User runs the agent near their containers.
10. Agent starts sending heartbeat and log/crash events.
11. User finishes alert settings.
12. User reaches dashboard.
13. During later deploys, GitHub push webhook puts OpsTron into watch mode.
14. If errors/crashes happen, OpsTron correlates them to that watch window.
15. RCA is generated, stored, and possibly escalated by phone.

---

## 3. Frontend Boot Flow

### 3.1 App entry and route decision

Frontend root route logic lives in [__root.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/__root.tsx).

What it does on load:

1. Check if the URL contains `?token=...`
2. If yes:
   - remove the token from the URL immediately
   - call `initFromOAuthCallback(token)`
   - redirect to `/onboarding` on success
   - redirect to `/login` on failure
3. If no fresh token is in the URL:
   - check localStorage for an existing session token
   - call `refreshSession()` if present

This is the first important design choice:

- the backend creates the session
- the frontend stores and reuses the session token
- on refresh, the frontend tries to silently restore the user session

### 3.2 Redirect rules

The app basically uses these rules:

- no user -> `/login`
- logged in but setup incomplete -> `/onboarding`
- logged in and setup complete -> `/dashboard`

This behavior is spread across:

- [index.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/index.tsx)
- [login.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/login.tsx)
- [onboarding.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/onboarding.tsx)
- [AppShell.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/components/AppShell.tsx)

---

## 4. Login Flow in Detail

### 4.1 What the user sees

On [login.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/login.tsx), the user clicks "Continue with GitHub".

That triggers:

- `redirectToGitHubOAuth()`
- browser navigates to backend `/auth/github/login`

### 4.2 Backend GitHub OAuth start

Backend route:

- [auth.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/api/routes/auth.py) -> `GET /auth/github/login`

This route:

1. checks `GITHUB_CLIENT_ID`
2. builds GitHub authorize URL
3. requests scopes:
   - `read:user`
   - `user:email`
   - `repo`
4. redirects the browser to GitHub

### 4.3 GitHub callback

After user authorizes, GitHub redirects to:

- `GET /auth/github/callback?code=...`

Backend callback flow:

1. exchange code for GitHub access token
2. call GitHub `/user`
3. get GitHub profile
4. look up existing OpsTron user in Supabase
5. reuse old `agent_api_key` if the user already exists
6. create a new OpsTron session token
7. persist:
   - user
   - GitHub token
   - session token
   - agent API key
8. redirect browser to frontend with:
   - `/?token=<session_token>`

### 4.4 Why reusing `agent_api_key` matters

This is subtle and important.

If the API key changed every login, any already-running Docker agent would break immediately.

So the backend intentionally tries to reuse the old `agent_api_key` from Supabase when the same GitHub user logs in again.

That behavior lives in:

- [auth.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/api/routes/auth.py)
- [supabase_client.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/db/supabase_client.py)

### 4.5 Session storage model

There are two session layers:

1. in-memory session cache
   - `active_sessions` in [auth.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/api/middleware/auth.py)

2. persistent session storage
   - `session_token` stored in Supabase

Why both:

- in-memory is fast
- DB fallback survives backend restarts or multi-worker setups

When a request comes in with `Authorization: Bearer ...`, backend auth flow is:

1. check in-memory session map
2. if missing, query Supabase by session token
3. rebuild in-memory cache
4. continue

That is the main crash-safe session recovery behavior.

---

## 5. Onboarding Flow

Onboarding is implemented in [onboarding.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/onboarding.tsx).

There are three steps:

1. Connect repository
2. Install Docker agent
3. Configure alerts

### 5.1 Step 1: Connect repository

Frontend calls:

- `GET /integrations/repos`
- `POST /integrations/install-webhook`

These are implemented in:

- [integrations.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/api/routes/integrations.py)

#### Repo list flow

1. frontend calls `/integrations/repos`
2. backend pulls GitHub access token from the authenticated session
3. backend calls GitHub `/user/repos`
4. backend reshapes the repo list for the frontend
5. frontend shows searchable repo picker

#### Webhook install flow

When the user selects a repo and clicks connect:

1. frontend sends owner, repo, service name, webhook URL
2. backend checks whether a webhook with the same URL already exists
3. if it exists:
   - return existing hook info
   - still persist repo connection in Supabase
4. if it does not exist:
   - backend creates GitHub webhook for `push` events
   - persists connected repo in Supabase

Supabase stores connected repos so later deployment webhooks can be mapped to the right user/service.

### 5.2 Step 2: Install Docker agent

This is the part where the user gets commands/snippets.

The UI shows:

- a `docker-compose` snippet
- a `docker run` snippet

The key values injected into those snippets are:

- `OPSTRON_API_KEY`
- `OPSTRON_BACKEND_URL`

The frontend gets the key from the authenticated user object returned by `/auth/me`.

The monitored service must opt in with:

```yaml
labels:
  opstron.monitor: "true"
```

or:

```bash
docker run --label opstron.monitor=true ...
```

This label matters because the agent only watches containers with that label.

### 5.3 Step 3: Alerts and paging

Frontend collects:

- phone number
- severity threshold
- cooldown minutes
- optional slack/email placeholders

Important current behavior:

- this step is mostly frontend-state driven right now
- `completeOnboarding()` stores the data in frontend local state/localStorage
- it is not fully wired into backend-side alert policy enforcement yet

So the UI already supports a product flow for alerts, but not every setting here is currently enforced by backend logic.

That is worth knowing if you are thinking in terms of "what the product promises" vs "what the backend actually uses today".

---

## 6. What Commands the User Actually Runs

From the user's perspective, the critical commands are the agent setup commands.

### 6.1 Docker Compose path

The user adds something like:

```yaml
opstron-agent:
  image: opstron/agent:latest
  restart: unless-stopped
  environment:
    OPSTRON_API_KEY: "..."
    OPSTRON_BACKEND_URL: "https://..."
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
```

And on their app service:

```yaml
labels:
  opstron.monitor: "true"
```

### 6.2 Single container path

The user runs something like:

```bash
docker run -d \
  -e OPSTRON_API_KEY="..." \
  -e OPSTRON_BACKEND_URL="..." \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  --name opstron-agent \
  --restart unless-stopped \
  opstron/agent:latest
```

Then they ensure their application container has:

```bash
--label opstron.monitor=true
```

### 6.3 Why the Docker socket is mounted

The agent needs read access to:

- list containers
- read logs
- inspect restart count/image hash
- subscribe to Docker events

It does not use this to mutate containers. The code is intentionally read-only in [opstron_forwarder.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/opstron_forwarder.py).

---

## 7. What Happens Right After Agent Starts

This flow is implemented in [opstron_forwarder.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/opstron_forwarder.py).

### 7.1 Startup sequence

When the agent process starts:

1. read environment variables
   - `OPSTRON_API_KEY`
   - `OPSTRON_BACKEND_URL`
   - optional poll interval/label settings
2. connect to Docker via `docker.from_env()`
3. send initial heartbeat
4. start background Docker event watcher thread
5. start background heartbeat thread
6. enter main polling loop for delta logs

### 7.2 Initial heartbeat

The heartbeat is sent to:

- `POST /agent/heartbeat`

Payload includes:

- agent version
- hostname
- list of monitored containers

Backend route updates:

- in-memory heartbeat cache
- Supabase heartbeat fields on the user row

This is how the dashboard later shows whether the agent is online.

### 7.3 Dashboard polling for agent status

Frontend dashboard and onboarding poll:

- `/agent/status`
- `/agent/status/by-session`

Backend checks:

1. in-memory heartbeat cache
2. if missing, Supabase heartbeat
3. if last seen is older than 90 seconds, mark agent offline

So "connected/offline" is freshness-based, not just "has ever connected".

---

## 8. Normal Monitoring Flow

Once the agent is running, there are two parallel monitoring mechanisms.

### 8.1 Delta log polling

The agent periodically:

1. lists only containers with `opstron.monitor=true`
2. for each container:
   - fetch only new log lines since the last successful send
   - or bootstrap with last 50 lines if first time seen
3. strip Docker timestamps
4. send logs to:
   - `POST /agent/logs/ingest`

The `_last_seen` map in the agent ensures it does not resend the same log window repeatedly.

If the POST fails, the agent removes the cursor so the window can be retried later.

### 8.2 Docker event streaming

In parallel, the agent subscribes to Docker events and watches for:

- `die`
- `oom`
- `kill`
- `stop`

When such an event happens:

1. it treats it as a crash-like incident
2. it fetches:
   - last 100 lines of logs
   - restart count
   - image hash
3. it builds a structured event
4. it posts to:
   - `POST /agent/events`

If `/agent/events` is not available, it can fall back to legacy log ingest.

This means OpsTron has:

- slow-path continuous visibility through log polling
- fast-path immediate visibility through Docker event stream

---

## 9. Deployment Flow

This is the GitHub webhook flow.

### 9.1 Trigger

When the connected repo receives a push:

- GitHub sends a webhook to `/notify-deployment`

Route lives in [ingest.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/api/routes/ingest.py).

### 9.2 Webhook authentication

If `WEBHOOK_SECRET` is configured:

1. backend reads `X-Hub-Signature-256`
2. computes HMAC SHA-256 over raw request body
3. compares using constant-time comparison

If no webhook secret is configured, backend allows the request with a warning. That is useful for local testing but weaker for production.

### 9.3 Deployment registration

After parsing the push payload, backend:

1. extracts repository, branch, commit SHA, author, message
2. looks up connected repo records in Supabase
3. determines the service name(s) to watch
4. creates deployment records in Supabase
5. starts watch mode per user/service in `WatchModeManager`
6. emits a structured `deployment_detected` event into `EventEngine`
7. also keeps the older in-memory `DeploymentWatcher` warmed for legacy `/ingest-error` flow

This is a key architectural point:

- the codebase is currently in a hybrid state
- old deployment correlation code still exists
- newer service-scoped watch mode also exists

### 9.4 What watch mode means

Watch mode is basically a short-lived suspicion window.

It means:

- "a deployment just happened"
- "if bad events happen for this service soon after, they may be regressions"

The newer watch mode is managed by [watch_manager.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/watch_manager.py).

Each watch contains:

- GitHub user id
- service name
- commit SHA
- repository
- author
- branch
- image hash
- start time
- expiry time

By default, duration is about 5 minutes.

---

## 10. Error Flow: Log Error Path

This is what happens when the agent sends logs to `/agent/logs/ingest`.

### 10.1 Backend receives log chunk

Route:

- `POST /agent/logs/ingest`

Backend:

1. logs that it received a block from a container
2. checks whether logs contain error signals
   - `error`
   - `exception`
   - `traceback`
   - `fatal`
   - `panic`
   - `segmentation fault`
3. if no signal:
   - logs are treated as healthy/noisy background
   - no RCA triggered
4. if signal exists:
   - backend creates a structured `log_error` event
   - forwards it to `event_engine.process(...)`

So `/agent/logs/ingest` is really a translator:

- raw logs in
- maybe structured event out

### 10.2 Event engine enrichment

In [event_engine.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/event_engine.py), the event is enriched:

1. normalize service name
2. normalize timestamp
3. attach `github_id`
4. classify severity
   - `log_error` starts as `medium`

### 10.3 Correlation with deployment watch

Then the engine asks `WatchModeManager`:

- is there an active watch for this user/service?

If yes:

1. event is marked deployment-related
2. confidence score is computed
3. reasons are recorded
4. for `log_error` during active watch:
   - severity is bumped to `high`

Confidence is based on factors such as:

- image hash changed
- event happened within 2 minutes of deploy
- non-zero exit code
- OOM signal
- service match

### 10.4 Deduplication

Before RCA, event dedup may suppress duplicates.

Dedup key is effectively:

`github_id + container_id + event_type + reason`

If the same event repeats within the dedup window, it can be suppressed.

This prevents alert storms from identical repeated signals.

### 10.5 RCA routing decision

For `log_error`:

- if there is an active watch, RCA is triggered
- if there is no watch, current behavior is more conservative and may just store the event

This is important:

OpsTron currently treats deployment-time errors as especially worthy of RCA escalation.

### 10.6 RCA execution

If RCA is triggered:

1. EventEngine calls the shared orchestrator
2. repo comes from watch context if available
3. log text comes from event logs or fallback event summary
4. metadata includes:
   - event id
   - event type
   - severity
   - correlation context
   - any carried metadata

Then the RCA pipeline runs.

---

## 11. Error Flow: Crash / Restart / OOM Path

This is the more urgent path.

### 11.1 Agent detects crash-like event

The agent Docker event watcher sees `die`, `oom`, `kill`, or `stop`.

It posts a structured event to:

- `POST /agent/events`

Payload includes:

- type: `container_crash`
- container id
- container name
- timestamp
- exit code
- reason
- image hash
- restart count
- last 100 lines of logs

### 11.2 Backend event processing

Route:

- `/agent/events`

Backend directly passes the payload to `EventEngine.process(...)`.

### 11.3 Severity classification

Crash events are treated much more aggressively:

- `container_crash`
  - `critical` if exit code is non-zero
  - `high` if exit code is zero
- `container_restart` with restart count > 3
  - `critical`

### 11.4 Watch correlation

Same watch-mode lookup happens.

If the crash happens during a deployment watch for that service:

- confidence likely increases
- reasons explain why OpsTron thinks this is deployment-related

### 11.5 RCA trigger

For `container_crash`:

- RCA is always triggered

If it is also correlated to an active watch and confidence is high enough:

- phone alert may also be triggered

### 11.6 Phone alert gating

Voice alert only happens if all of these are true:

1. route logic decides the event is severe enough
2. event has active watch and sufficient confidence
3. cooldown allows it
4. agent is not stale
5. Twilio is configured correctly

Phone alert is generated by:

- [twilio_service.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/services/twilio_service.py)

The message spoken on the call is based on the RCA root cause summary.

### 11.7 Cooldown

Cooldown is service-scoped per user:

`user_id + service_name`

This avoids calling the same person repeatedly for the same flapping service.

---

## 12. Legacy Error Flow: `/ingest-error`

There is an older, still-active API:

- `POST /ingest-error`

This route is important because:

- the frontend "test error" path still uses it
- some older integrations may still use it

### 12.1 What it accepts

Structured payload like:

- service
- error
- stacktrace
- recent logs
- env
- request metadata

### 12.2 What it does

1. generates request id
2. checks older `DeploymentWatcher` state
3. if active deployment exists:
   - fetches commit diff from GitHub
   - appends deployment context into the log text
   - tags metadata as deployment-related
4. builds synthetic log text from:
   - error header
   - stacktrace
   - recent logs
5. runs orchestrator directly
6. stores RCA result in memory history
7. stores RCA log in Supabase

So this path bypasses the newer event engine and goes straight to orchestrator.

This is why the project currently has two incident-processing styles:

1. legacy direct-ingest path
2. newer event-driven path

---

## 13. RCA Pipeline in Technical Detail

The RCA pipeline lives in [orchestrator.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/orchestrator.py).

It runs four agents.

### 13.1 Step 1: LogAgent

File:

- [log_agent.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/agents/log_agent.py)

Behavior:

1. pre-filters logs to keep error-heavy regions
2. if logs are long, it keeps lines near error patterns
3. sends filtered logs to LLM
4. expects JSON with:
   - error signals
   - stack traces
   - key errors
   - patterns

This is token-saving and tries to avoid sending huge useless logs to the model.

### 13.2 Step 2: CommitAgent

File:

- [commit_agent.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/agents/commit_agent.py)

Behavior:

1. call GitHub API for recent commits
2. summarize:
   - sha
   - message
   - author
   - date
   - changed files count

If commit fetch fails, the pipeline continues with an empty commit set.

### 13.3 Step 3: RunbookAgent

File:

- [runbook_agent.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/agents/runbook_agent.py)

Behavior:

1. join error signals into a query
2. query Chroma vector store
3. return top matching runbook snippets

Runbook search degrades gracefully if Chroma is unavailable.

### 13.4 Step 4: SynthesizerAgent

File:

- [synthesizer_agent.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/agents/synthesizer_agent.py)

Behavior:

1. decide whether this is standard RCA or deployment-regression RCA
2. build prompt from:
   - service
   - metadata
   - log analysis
   - recent commits
   - runbook matches
3. call LLM
4. expect structured JSON report

There are two prompt styles:

- standard incident prompt
- deployment regression prompt

The deployment regression prompt is more opinionated and asks for:

- suspect code change
- rollback recommendation
- exact change correlation

### 13.5 LLM backend

All model calls go through [llm.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/llm.py).

Current implementation:

- LangChain `ChatGroq`
- model: `llama-3.3-70b-versatile`

The wrapper:

1. invokes the model
2. tries to strip markdown code fences
3. parses JSON response
4. errors if invalid JSON

So the entire system heavily depends on the model returning usable JSON.

---

## 14. Persistence Model

Persistence is wrapped in [supabase_client.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/db/supabase_client.py).

Supabase is used for:

- users
- session tokens
- connected repos
- deployments
- RCA logs
- structured agent events
- heartbeats

### 14.1 Why persistence matters

Without persistence, these things would be lost on restart:

- user session recovery
- repo connection mapping
- agent online status history
- recent deployment watch context
- RCA history

### 14.2 Where memory is still used

Some state still exists in memory:

- `active_sessions`
- `api_key_to_user`
- `_heartbeats`
- `DeploymentWatcher.active_deployments`
- `WatchModeManager._watches`
- event dedup cache
- alert cooldown cache

This means the system is partly persistent and partly ephemeral.

The code often tries to compensate for this with DB fallback reads.

---

## 15. What Happens on Restart

This is one of the most important sections.

There are multiple kinds of restart.

### 15.1 Frontend browser refresh

If the user refreshes the page:

1. frontend localStorage still has session token
2. root route calls `refreshSession()`
3. backend `/auth/me` validates the bearer token
4. frontend restores user object
5. route logic returns user to onboarding or dashboard

This is usually smooth.

### 15.2 Backend process restart

When backend restarts:

Lost immediately from memory:

- in-memory sessions
- API key cache
- in-memory watch state
- in-memory heartbeat cache
- dedup history
- cooldown state
- in-memory RCA history

Recovered through DB fallback:

- sessions via `get_session_by_token`
- API key ownership via `get_user_by_api_key`
- heartbeat via `get_heartbeat`
- active deployments via `get_active_deployment_db`
- RCA history via `get_rca_logs`

Not perfectly recovered:

- dedup window
- cooldown timers
- any purely in-memory watch state not represented well enough in DB

So backend restarts are partly survivable, but not everything is preserved.

### 15.3 Docker agent restart

When the agent restarts:

1. `_last_seen` log cursor map is reset
2. it reconnects to Docker
3. sends startup heartbeat
4. restarts event watcher thread
5. restarts heartbeat thread
6. resumes polling logs

Effect:

- dashboard should show it as connected again after heartbeat
- first polling cycle may bootstrap with recent logs again
- duplicate suppression is mostly handled on backend side if needed

### 15.4 Application container restart

If the user's app container restarts and it is monitored:

1. Docker emits event like `die` or `stop`
2. agent captures it
3. agent sends structured crash event
4. backend may trigger RCA
5. if restart count grows and patterns continue, severity may rise

### 15.5 OpsTron losing watch mode during restart

This is a subtle issue.

If backend restarts during a deployment watch:

- in-memory watch state is lost

Recovery path:

- backend queries recent deployment rows from Supabase
- rebuilds short-lived watch entries

That recovery exists in both:

- old `DeploymentWatcher` fallback
- new `WatchModeManager` fallback

So the code tries hard not to forget "a deployment just happened" just because the backend restarted.

---

## 16. User Dashboard Flow After Setup

On the dashboard, the main flows are:

### 16.1 Refresh behavior

Dashboard refresh action calls:

- `fetchRCAHistory()`
- `fetchAgentStatus()`
- `checkHealth()`

It then updates frontend store with:

- RCA reports
- agent connected flag
- backend online flag

### 16.2 RCA reports shown to user

RCA history comes from:

- `GET /rca-history`

Backend prefers:

1. Supabase reports
2. fallback to in-memory history

The frontend expands each RCA report to show:

- service
- confidence
- root cause
- recommendations
- deployment commit context if present
- raw stacktrace/details

### 16.3 Test error flow

Dashboard has a "Test errors" section.

When user submits a test incident:

1. frontend sends synthetic payload to `/ingest-error`
2. frontend also adds a local fake incident row for immediate UI feedback
3. backend runs the legacy direct RCA path

So the test UI is a hybrid:

- real backend ingestion
- local UI incident simulation

---

## 17. Important Technical Observations

### 17.1 The system is mid-migration

There are clearly two eras of architecture living together:

1. older direct-ingest RCA system
2. newer event-driven deployment-aware system

That is not inherently bad, but it matters for understanding behavior.

### 17.2 User alert settings are not fully backend-enforced yet

The onboarding/settings UI captures rich policy data, but backend alert decisions are still more hardcoded than that UI suggests.

### 17.3 There is good resilience work already

The code already has strong fallback ideas:

- session reconstruction from DB
- API key lookup from DB
- heartbeat persistence
- deployment watch recovery from DB
- graceful Chroma degradation

### 17.4 Some operational state is still ephemeral

These still reset on backend restart:

- dedup memory
- cooldown memory
- some short-lived watch state

This can slightly change behavior immediately after a restart.

---

## 18. End-to-End Flow Summary

If you want the shortest possible "movie" of the whole system, it is this:

1. User logs in with GitHub.
2. Backend creates/reuses user, API key, and session.
3. Frontend stores token and sends user to onboarding.
4. User connects repo, which installs GitHub push webhook.
5. User runs Docker agent with OpsTron API key.
6. Agent sends heartbeat and starts watching opted-in containers.
7. Dashboard starts showing agent status and RCA history.
8. On every deploy, GitHub push creates a short watch window for the mapped service.
9. If logs show errors or the container crashes during that watch:
   - event enters backend
   - backend correlates it with deploy context
   - backend dedups noise
   - backend runs RCA pipeline
   - backend stores the result
   - backend may trigger voice alert if severe enough
10. User opens dashboard and sees root cause, related deploy, and recommended actions.

---

## 19. Where to Read Next in Code

If you want to continue understanding the codebase in the best order, read these next:

1. [agent/app/api/routes/auth.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/api/routes/auth.py)
2. [lov_frontend/opstron-delight/src/routes/__root.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/__root.tsx)
3. [lov_frontend/opstron-delight/src/routes/onboarding.tsx](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/lov_frontend/opstron-delight/src/routes/onboarding.tsx)
4. [agent/opstron_forwarder.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/opstron_forwarder.py)
5. [agent/app/api/routes/ingest.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/api/routes/ingest.py)
6. [agent/app/core/event_engine.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/event_engine.py)
7. [agent/app/core/orchestrator.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/core/orchestrator.py)
8. [agent/app/db/supabase_client.py](C:/Users/HP/Desktop/Secret/Project/OpsTron/OpsTron/agent/app/db/supabase_client.py)

That order follows the real runtime flow pretty well.

