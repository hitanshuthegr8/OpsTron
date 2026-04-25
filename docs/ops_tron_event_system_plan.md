# OpsTron Event System — Complete Implementation Plan

## 1. SYSTEM OVERVIEW

### Architecture

```
┌─────────────────┐     POST /agent/events      ┌──────────────────────────────┐
│  Docker Agent    │ ──────────────────────────▶  │  FastAPI Backend              │
│  (per server)    │     POST /agent/heartbeat    │                              │
│                  │ ──────────────────────────▶  │  ┌────────────────────────┐  │
└─────────────────┘                               │  │    Event Engine         │  │
                                                  │  │  enrich → classify →   │  │
┌─────────────────┐     POST /notify-deployment   │  │  correlate → dedup →   │  │
│  GitHub Webhook  │ ──────────────────────────▶  │  │  cooldown → route      │  │
└─────────────────┘                               │  └──────────┬─────────────┘  │
                                                  │             │                │
┌─────────────────┐     POST /ingest-error        │    ┌────────┴────────┐       │
│  SDK/Middleware  │ ──────────────────────────▶  │    │   Router         │       │
└─────────────────┘                               │    ├─ phone call      │       │
                                                  │    ├─ RCA pipeline    │       │
                                                  │    ├─ dashboard store │       │
                                                  │    └─────────────────┘       │
                                                  │             │                │
                                                  │    ┌────────▼────────┐       │
                                                  │    │   Supabase      │       │
                                                  │    │   (repos)       │       │
                                                  │    └─────────────────┘       │
                                                  └──────────────────────────────┘
```

### Data Flow

```
Agent detects Docker event (die/oom/restart)
  → Agent sends structured payload to POST /agent/events
  → Backend enriches: adds event_id, source, service_name, normalized timestamp
  → Backend classifies: assigns severity (critical/high/medium/low)
  → Backend correlates: checks watch_mode[service] for active deployment window
  → Backend deduplicates: checks container_id + event_type + reason within 60s
  → Backend checks cooldown: max 1 phone alert per user+service per 5 min
  → Backend routes:
      crash + watch + confidence > 60  → phone call + RCA + store
      crash (no watch)                 → RCA + store
      log_error + watch               → RCA + store
      log_error (no watch)            → store only
      health_unhealthy                → store only
```

---

## 2. PHASED IMPLEMENTATION PLAN

### Phase 1: Data Models & Event Schema (3 tasks, ~60 min)

#### Task 1.1: Create event_models.py
- **Goal**: Define strict Pydantic models for all event types
- **Input**: System requirement #2 (explicit event schema)
- **Output**: `app/models/event_models.py`
- **Steps**:
  1. Create `EventType` as `Literal["container_crash","container_restart","container_start","health_unhealthy","deployment_detected"]`
  2. Create `EventSource` as `Literal["agent","webhook","manual"]`
  3. Create `AgentEventPayload` with: type, source, container_id, container_name, timestamp, exit_code, reason, image_hash, restart_count, logs, metadata
  4. Create `EnrichedEvent` extending payload with: event_id (uuid), service_name, severity, correlation dict, confidence score
  5. Create `AgentEventResponse` with: status, message, event_id, rca_triggered, confidence, reasons list
  6. Create `ConfidenceResult` with: score (int 0-100), reasons (list of strings)

#### Task 1.2: Create watch mode model
- **Goal**: Define data structures for service-scoped watch mode
- **Input**: System requirement #4
- **Output**: Types in `event_models.py`
- **Steps**:
  1. Create `WatchEntry` with: service_name, commit_sha, repository, author, branch, image_hash, started_at, expires_at, source (webhook/agent)
  2. Create `WatchStatus` response model: service_name, is_active, time_remaining_seconds, commit_sha, triggered_by

#### Task 1.3: Update schema.sql with agent_events table
- **Goal**: Add persistent storage for structured events
- **Input**: System requirement #11 (traceability)
- **Output**: Updated `app/db/schema.sql`
- **Steps**:
  1. Create `agent_events` table: id, event_id (unique text), github_id, type, source, service_name, container_id, container_name, exit_code, reason, restart_count, severity, confidence, rca_triggered, correlation (jsonb), metadata (jsonb), created_at
  2. Add indexes on: github_id, type, service_name, created_at DESC, event_id
  3. Grant service_role access
  4. Enable RLS

---

### Phase 2: Event Engine Core (5 tasks, ~150 min)

#### Task 2.1: Create dedup.py
- **Goal**: Build deduplication and alert cooldown
- **Input**: System requirements #5 and #6
- **Output**: `app/core/dedup.py`
- **Steps**:
  1. Create `EventDeduplicator` class with `_seen: Dict[str, float]` mapping `"{container_id}:{type}:{reason}" → timestamp`
  2. Implement `is_duplicate(event) → bool` — returns True if same composite key seen within 60s
  3. Implement `_cleanup()` to prune keys older than 120s (called lazily)
  4. Create `AlertCooldown` class with `_last_alert: Dict[str, float]` mapping `"{user_id}:{service_name}" → timestamp`
  5. Implement `can_alert(user_id, service) → bool` — True if no alert sent for this user+service in last 300s
  6. Implement `record_alert(user_id, service)` — stamps the time

#### Task 2.2: Create watch_manager.py
- **Goal**: Build service-scoped watch mode manager
- **Input**: System requirement #4
- **Output**: `app/core/watch_manager.py`
- **Steps**:
  1. Create `WatchModeManager` class with `_watches: Dict[str, WatchEntry]` keyed by service_name
  2. Implement `start_watch(service, commit_sha, repo, author, branch, source, image_hash, duration_minutes=5)`
  3. Implement `get_watch(service) → Optional[WatchEntry]` — returns None if expired, cleans up expired entries
  4. Implement `reinforce_watch(service, extra_minutes=2)` — extends existing watch window
  5. Implement `get_all_active() → List[WatchEntry]` — for dashboard display
  6. Add DB fallback: on `get_watch()` miss, query `deployments` table for recent `status='watching'` rows (same as current DeploymentWatcher fallback logic)

#### Task 2.3: Create event_engine.py — enrichment + classification
- **Goal**: Build the first two pipeline stages
- **Input**: System requirements #1, #7, #8
- **Output**: `app/core/event_engine.py` (partial)
- **Steps**:
  1. Create `EventEngine` class with __init__ taking watch_manager, dedup, cooldown
  2. Implement `_enrich(event: AgentEventPayload, user_id: str) → EnrichedEvent`:
     - Generate `event_id` via `uuid4()`
     - Set `source` from payload (default "agent")
     - Map `container_name` → `service_name` (strip prefixes like project name)
     - Normalize timestamp to UTC ISO format
     - Copy all fields from payload into EnrichedEvent
  3. Implement `_classify(event: EnrichedEvent) → str` returning severity:
     - `container_crash` + exit_code != "0" → "critical"
     - `container_restart` + restart_count > 3 → "critical" (crash loop)
     - `container_crash` + exit_code == "0" → "high" (graceful stop)
     - `health_unhealthy` → "warning"
     - `container_start` → "info"
     - `deployment_detected` → "info"

#### Task 2.4: Create event_engine.py — correlation + confidence
- **Goal**: Build correlation and confidence scoring
- **Input**: System requirement #7
- **Output**: Continue `app/core/event_engine.py`
- **Steps**:
  1. Implement `_correlate(event: EnrichedEvent, user_id: str) → Optional[dict]`:
     - Call `watch_manager.get_watch(event.service_name)`
     - If no active watch → return None
     - Otherwise compute confidence via `_compute_confidence(event, watch)`
  2. Implement `_compute_confidence(event, watch) → ConfidenceResult`:
     - Start score = 0, reasons = []
     - If `watch.image_hash != event.image_hash` and both non-empty: +40, append "Image changed since deployment"
     - If crash within 120s of watch start: +30, append "Crash within 2 min of deploy"
     - If `exit_code` not in ("", "0"): +20, append "Non-zero exit code"
     - If `reason == "oom"`: +10, append "Out of memory signal"
     - Return ConfidenceResult(score=score, reasons=reasons)
  3. Store correlation result on enriched event: `{is_regression: score > 50, confidence: score, reasons: [...], watch: {...}}`

#### Task 2.5: Create event_engine.py — dedup, cooldown, routing
- **Goal**: Build the final three pipeline stages + the main `process()` method
- **Input**: System requirements #5, #6, #8, #9, #10
- **Output**: Complete `app/core/event_engine.py`
- **Steps**:
  1. Implement the public `async process(event, user_id) → EventResult` method that calls all 6 stages in strict order: enrich → classify → correlate → dedup → cooldown → route
  2. After correlate, call `dedup.is_duplicate(enriched)` — if True, return status="suppressed"
  3. In route stage, implement the routing rules:
     - crash + watch + confidence > 60 → trigger RCA, check cooldown for phone call
     - crash (no watch or low confidence) → trigger RCA only
     - container_restart + count > 3 → trigger RCA (crash loop)
     - health_unhealthy → store to DB only
     - container_start → store to DB only
  4. For phone call routing: call `cooldown.can_alert(user_id, service)` — if False, skip call but still run RCA
  5. Add agent-down guard: if event type is crash but last heartbeat for this user is > 90s old, log warning "Agent may be offline — suppressing crash event to prevent false positive"
  6. Persist event to `agent_events` table via incident_repo
  7. Return EventResult with status, event_id, rca_triggered, confidence, reasons

---

### Phase 3: Route Splitting (4 tasks, ~120 min)

#### Task 3.1: Create routes/agent.py
- **Goal**: Move all agent endpoints from ingest.py to dedicated file
- **Input**: Current ingest.py lines 529-712
- **Output**: `app/api/routes/agent.py` (~200 lines)
- **Steps**:
  1. Create new file with router = APIRouter()
  2. Move `HeartbeatPayload`, `_heartbeats` dict, `_resolve_heartbeat()` helper
  3. Move `POST /agent/heartbeat` handler
  4. Move `GET /agent/status` handler
  5. Move `GET /agent/status/by-session` handler
  6. Move `POST /agent/logs/ingest` handler — refactor to internally convert log payloads into `log_error` events and feed into EventEngine when errors detected
  7. Add new `POST /agent/events` handler — receives `AgentEventPayload`, calls `EventEngine.process()`, returns `AgentEventResponse`
  8. Import EventEngine, instantiate as module-level singleton

#### Task 3.2: Create routes/deployments.py
- **Goal**: Move all deployment endpoints from ingest.py
- **Input**: Current ingest.py lines 35-503
- **Output**: `app/api/routes/deployments.py` (~200 lines)
- **Steps**:
  1. Create new file with router
  2. Import WatchModeManager, instantiate as module-level singleton
  3. Move `POST /notify-deployment` — refactor to use WatchModeManager.start_watch() instead of DeploymentWatcher
  4. Also create a `deployment_detected` event via EventEngine when webhook arrives
  5. Move `GET /deployment-status` — use WatchModeManager.get_all_active()
  6. Move `GET /deployment-history` — query deployments table
  7. Delete the old `DeploymentWatcher` class entirely

#### Task 3.3: Rename ingest.py → errors.py
- **Goal**: Slim down to only error ingestion and RCA history
- **Input**: Current ingest.py lines 141-527
- **Output**: `app/api/routes/errors.py` (~200 lines)
- **Steps**:
  1. Rename file
  2. Keep `POST /ingest-error` — refactor to use WatchModeManager instead of DeploymentWatcher
  3. Keep `GET /rca-history`
  4. Keep helper functions `_prepare_log_text()` and `_add_deployment_context_to_logs()`
  5. Keep `RCA_HISTORY` in-memory list and `orchestrator` instance
  6. Remove everything else (already moved to agent.py and deployments.py)

#### Task 3.4: Update router registration
- **Goal**: Wire new route modules into the app
- **Input**: `app/api/__init__.py` and `app/api/routes/__init__.py`
- **Output**: Updated both files
- **Steps**:
  1. In `routes/__init__.py`: add imports for agent, deployments, errors; remove ingest
  2. In `api/__init__.py`: register new routers with proper tags:
     - `agent.router` → tags=["Docker Agent"]
     - `deployments.router` → tags=["Deployments"]
     - `errors.router` → tags=["Error Ingestion"]
  3. Remove `ingest.router` registration
  4. Verify: `python -c "from app.api import api_router"`

---

### Phase 4: Repository Pattern (4 tasks, ~90 min)

#### Task 4.1: Create base repo + user_repo.py
- **Goal**: Extract user-related DB methods
- **Output**: `app/db/repos/user_repo.py`
- **Steps**:
  1. Create `app/db/repos/__init__.py`
  2. Create `BaseRepo` class that takes a Supabase client in __init__
  3. Create `UserRepo(BaseRepo)` with methods: `upsert_user`, `get_user_by_api_key`, `get_user_by_github_id`, `save_session_token`, `get_session_by_token`, `upsert_heartbeat`, `get_heartbeat`
  4. Copy method bodies verbatim from `supabase_client.py`

#### Task 4.2: Create incident_repo.py
- **Goal**: Extract incident/RCA/event DB methods
- **Output**: `app/db/repos/incident_repo.py`
- **Steps**:
  1. Create `IncidentRepo(BaseRepo)` with: `create_rca_log`, `get_rca_logs`, `get_rca_by_deployment`, `create_event` (NEW — inserts into agent_events table), `create_vapi_call`, `update_vapi_call`, `get_vapi_calls`
  2. `create_event()` takes an EnrichedEvent and persists to agent_events table

#### Task 4.3: Create deployment_repo.py + repo_repo.py
- **Goal**: Extract remaining DB methods
- **Output**: `app/db/repos/deployment_repo.py`, `app/db/repos/repo_repo.py`
- **Steps**:
  1. `DeploymentRepo(BaseRepo)`: `create_deployment`, `update_deployment`, `get_deployment`, `get_recent_deployments`, `get_active_deployment_db`
  2. `RepoRepo(BaseRepo)`: `upsert_repo`
  3. Also move `create_commit`, `get_commit_by_sha`, `get_recent_commits` into deployment_repo (they're deployment-related context)

#### Task 4.4: Refactor supabase_client.py into facade
- **Goal**: Make Database class delegate to repos
- **Output**: Slim `app/db/supabase_client.py` (~80 lines)
- **Steps**:
  1. Import all 4 repos
  2. Database.__init__: create repo instances with shared client
  3. Add delegation methods so `db.upsert_user()` calls `self._users.upsert_user()`
  4. This preserves all existing `from app.db.supabase_client import db` imports
  5. Delete chat_messages methods (move to incident_repo if needed, or drop if unused)

---

### Phase 5: Agent Upgrade + Wiring (2 tasks, ~45 min)

#### Task 5.1: Upgrade opstron_forwarder.py
- **Goal**: Send structured events to /agent/events for crashes
- **Output**: Updated `opstron_forwarder.py`
- **Steps**:
  1. Add `EVENT_URL = f"{BACKEND_URL}/agent/events"` constant
  2. In `watch_events()` crash handler (line 265), change payload to structured format: type="container_crash", reason inferred from action (die→exit, oom→oom, kill→sigkill), include restart_count from `container.attrs.get("RestartCount", 0)`
  3. POST to EVENT_URL instead of INGEST_URL for crash events
  4. Keep the regular `poll_logs()` loop posting to INGEST_URL unchanged (backward compat)
  5. Add a try/except: if /agent/events returns 404 (old backend), fall back to INGEST_URL

#### Task 5.2: Update main.py
- **Goal**: Clean up entry point
- **Output**: Updated `main.py`
- **Steps**:
  1. Remove stale MVP labels from docstring
  2. Verify lifespan startup/shutdown still works
  3. Run full import check

---

## 3. API CONTRACTS

### POST /agent/events

```
Request:
{
  "type": "container_crash",          // REQUIRED: EventType enum
  "source": "agent",                  // REQUIRED: "agent" | "webhook" | "manual"
  "container_id": "a1b2c3d4e5f6",    // REQUIRED
  "container_name": "checkout-api",   // REQUIRED
  "timestamp": "2026-04-26T...",      // REQUIRED: ISO 8601
  "exit_code": "137",                 // optional
  "reason": "oom",                    // optional: oom, sigkill, exit_nonzero
  "image_hash": "sha256:abc...",      // optional
  "restart_count": 2,                 // optional, default 0
  "logs": "last 100 lines...",        // optional: for RCA context
  "metadata": {}                      // optional: free-form
}

Response (200):
{
  "status": "rca_triggered",          // received | rca_triggered | suppressed | stored
  "message": "Crash detected during active watch mode. RCA triggered.",
  "event_id": "evt-a1b2c3d4",
  "rca_triggered": true,
  "confidence": 80,
  "reasons": ["Image changed since deployment", "Crash within 2 min of deploy"]
}

Auth: X-API-Key header (AgentKeyAuth)
```

### POST /agent/heartbeat

```
Request:
{
  "agent_version": "4.0.0",
  "hostname": "prod-server-1",
  "monitored_containers": ["checkout-api", "payment-service"]
}

Response (200):
{
  "status": "ok",
  "message": "Heartbeat received"
}

Auth: X-API-Key header
```

### POST /notify-deployment

```
Request: Raw GitHub Push Event webhook payload (JSON)
  Key fields extracted:
  - repository.full_name
  - head_commit.id (SHA)
  - head_commit.author.username
  - head_commit.message
  - ref (branch)

Response (200):
{
  "status": "watching",
  "deployment_id": "deploy-a1b2c3d4",
  "commit_sha": "abc1234...",
  "watch_until": "2026-04-26T01:10:00Z",
  "services_watched": ["checkout-api"],    // NEW: which services are in watch mode
  "message": "Watch mode active for 5 minutes."
}

Auth: X-Hub-Signature-256 HMAC (GitHubWebhookAuth)
```

---

## 4. DATA MODELS

### EnrichedEvent (internal, after enrichment)

| Field | Type | Source |
|---|---|---|
| event_id | str (uuid) | Generated by engine |
| type | EventType | From payload |
| source | EventSource | From payload |
| service_name | str | Mapped from container_name |
| container_id | str | From payload |
| container_name | str | From payload |
| timestamp | str (ISO) | Normalized from payload |
| exit_code | str | From payload |
| reason | str | From payload |
| image_hash | str | From payload |
| restart_count | int | From payload |
| logs | str | From payload |
| severity | str | Set by classify stage |
| correlation | dict or None | Set by correlate stage |
| confidence | ConfidenceResult or None | Set by correlate stage |

### WatchEntry (in-memory + DB backed)

| Field | Type |
|---|---|
| service_name | str |
| commit_sha | str |
| repository | str |
| author | str |
| branch | str |
| image_hash | str |
| started_at | datetime |
| expires_at | datetime |
| source | "webhook" or "agent" |

### agent_events (DB table)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | auto |
| event_id | TEXT UNIQUE | from enrichment |
| github_id | TEXT FK | user who owns the agent |
| type | TEXT | event type |
| source | TEXT | agent/webhook/manual |
| service_name | TEXT | mapped from container |
| container_id | TEXT | |
| container_name | TEXT | |
| exit_code | TEXT | |
| reason | TEXT | |
| restart_count | INT | |
| severity | TEXT | critical/high/medium/low |
| confidence | INT | 0-100 |
| rca_triggered | BOOL | |
| correlation | JSONB | watch context if any |
| metadata | JSONB | |
| created_at | TIMESTAMPTZ | |

---

## 5. EVENT ENGINE DESIGN

### Pipeline (strict order, no skipping)

```
process(raw_event, user_id)
  │
  ├─ 1. ENRICH
  │   • Generate event_id (uuid4)
  │   • Set source (default "agent")
  │   • Map container_name → service_name
  │   • Normalize timestamp to UTC
  │   • Attach container metadata
  │
  ├─ 2. CLASSIFY
  │   • container_crash + exit != 0     → severity: critical
  │   • container_restart + count > 3   → severity: critical
  │   • container_crash + exit == 0     → severity: high
  │   • health_unhealthy               → severity: warning
  │   • container_start                → severity: info
  │
  ├─ 3. CORRELATE
  │   • Check watch_manager.get_watch(service_name)
  │   • If active watch → compute confidence score:
  │       image_changed:        +40
  │       crash_within_2min:    +30
  │       exit_code_nonzero:    +20
  │       oom_signal:           +10
  │   • Return {is_regression, confidence, reasons[]}
  │
  ├─ 4. DEDUPLICATE
  │   • Key = container_id:type:reason
  │   • If same key seen within 60s → return "suppressed"
  │
  ├─ 5. COOLDOWN (alerts only)
  │   • Key = user_id:service_name
  │   • If phone alert sent within 300s → skip phone, still run RCA
  │   • Dashboard/log alerts are NEVER blocked
  │
  └─ 6. ROUTE
      • crash + watch + confidence > 60 → RCA + phone + store
      • crash + watch + confidence ≤ 60 → RCA + store
      • crash (no watch)               → RCA + store
      • restart count > 3              → RCA + store
      • health_unhealthy               → store only
      • container_start                → store only
      • log_error + watch              → RCA + store
      • log_error (no watch)           → store only
```

---

## 6. EDGE CASES

| # | Scenario | Expected Behavior |
|---|---|---|
| 1 | Container crash-loops (10 crashes in 30s) | Dedup suppresses after first. Only 1 RCA triggered. |
| 2 | Agent disconnects, containers keep running | Heartbeat timeout → mark agent "offline". No false crash alerts. |
| 3 | Two services deploy simultaneously | Each gets its own watch entry. Independent correlation. |
| 4 | GitHub webhook arrives but agent is not running | Watch mode starts. If no crash events arrive, watch expires silently. |
| 5 | Backend restarts during active watch mode | WatchManager falls back to deployments table in Supabase. Watch is recovered. |
| 6 | Same crash event sent by both log polling AND event stream | Dedup catches it — same container_id + type within 60s. |
| 7 | OOM kill with exit code 137 | Classified as critical. Confidence +10 for OOM reason. Phone call if in watch mode. |
| 8 | Graceful container stop (exit 0) during watch | Severity = high (not critical). Confidence lower. RCA runs but no phone call. |
| 9 | Old agent (v4.0) sends to /agent/logs/ingest | Backward compat handler converts to log_error event, feeds into engine. |
| 10 | LLM (Groq) is down when RCA is triggered | Orchestrator catches exception, returns partial report with error field. Event still stored. |
| 11 | User gets phone call, container recovers, crashes again in 3 min | Cooldown blocks second phone call (5 min window). RCA still runs. Dashboard updated. |
| 12 | Webhook payload has no head_commit (empty push) | Existing fallback logic: try commits[-1], then `after` SHA. If all fail, 400 error. |

---

## 7. FAILURE HANDLING

### Agent Disconnects
- Heartbeat stops arriving (normally every 60s)
- After 90s: `get_agent_status` returns `status: "offline"`
- **Guard**: If a crash event arrives but last heartbeat > 90s old, log warning and suppress to prevent false positives from stale/delayed events

### Duplicate Events
- `EventDeduplicator` uses composite key `container_id:type:reason`
- Window: 60 seconds
- Lazy cleanup: keys older than 120s pruned on next check
- Result: second identical event returns `status: "suppressed"`

### Backend Restarts
- **Watch mode**: `WatchModeManager.get_watch()` falls back to Supabase `deployments` table (query for `status='watching'` in last 5 min)
- **Sessions**: `verify_github_session()` already falls back to Supabase `opstron_users.session_token`
- **Heartbeats**: `_resolve_heartbeat()` already falls back to Supabase `opstron_users.agent_*` columns
- **Dedup/cooldown state**: Lost on restart. Acceptable — worst case is one extra RCA or one extra phone call

### LLM Fails
- `RCAOrchestrator.analyze()` catches exceptions in each agent step
- `SynthesizerAgent` returns a partial report with `root_cause: "analysis_failed"`, `confidence: "low"`
- The event is still persisted to `agent_events` with `rca_triggered: true`
- Dashboard shows the incident even without a complete RCA

---

## 8. WHAT NOT TO BUILD

| Feature | Why Skip |
|---|---|
| Kubernetes event support | Docker-only for MVP. K8s is a separate integration layer. |
| Redis for dedup/cooldown | In-memory dicts are fine for single-worker deployment. Add Redis when scaling to multiple workers. |
| Real-time WebSocket push to frontend | Polling is sufficient. Add SSE/WS when latency matters. |
| Multi-tenant data isolation (RLS per user) | Service key bypasses RLS already. Add per-user RLS when onboarding external teams. |
| Custom alert channels (Slack, PagerDuty) | Phone + dashboard is MVP. Slack is Phase 2. |
| Event replay/backfill | Store events for audit, but don't build replay tooling yet. |
| Container health check polling from agent | Docker's native healthcheck handles this. Agent just reads the state. |
| CI/CD pipeline integration (Jenkins, GitLab) | GitHub webhooks only for MVP. |
| Agent auto-update mechanism | Users manually pull new Docker image for now. |
| Custom dedup windows per user | Fixed 60s window for all. Configurable later. |
