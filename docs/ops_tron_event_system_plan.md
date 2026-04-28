# OpsTron Event System - Production Implementation Plan

## 1. System Overview

OpsTron needs a structured event system so Docker crashes, deployment webhooks,
application log errors, and heartbeat state all flow through one consistent
pipeline.

The production path is:

```text
Docker Agent
  -> POST /agent/events
  -> EventEngine
  -> enrich -> classify -> correlate -> dedup -> cooldown -> route
  -> RCA pipeline, phone alert, and agent_events storage

GitHub Webhook
  -> POST /notify-deployment
  -> strict HMAC verification
  -> service mapping
  -> shared WatchModeManager
  -> deployment_detected event

Old Agent / SDK
  -> POST /agent/logs/ingest or POST /ingest-error
  -> converted to log_error event where appropriate
  -> EventEngine
```

## 2. Non-Negotiable Architecture Decisions

These decisions must be made before coding the engine. They prevent the most
likely production failures.

### 2.1 One Shared Runtime

Do not instantiate `WatchModeManager`, `EventEngine`, `EventDeduplicator`, or
`AlertCooldown` separately inside route modules.

Create one shared runtime module:

```text
app/core/runtime.py
```

It owns:

- `watch_manager`
- `event_deduplicator`
- `alert_cooldown`
- `event_engine`
- shared `orchestrator`
- shared alert service

All route modules import these same instances. This avoids the bug where
`/notify-deployment` writes a watch into one manager and `/agent/events` reads
from another empty manager.

### 2.2 Service Mapping Is Required

GitHub webhooks provide repository, branch, commit, and author. Docker events
provide container and service names. The system must define how these align.

MVP service mapping order:

1. Use explicit mapping from config or onboarding metadata:
   - `repo_full_name -> [service_name]`
   - store this in `connected_repos.service_names` or a new table later.
2. If no mapping exists, fall back to Docker agent heartbeat:
   - watched services = current `monitored_containers` for that user.
3. If still unknown, start a user-scoped repo watch, but mark confidence lower.

Do not silently assume repository name equals service name.

### 2.3 EventEngine Owns Alerts

Only `EventEngine` decides whether to trigger a phone call.

`RCAOrchestrator` should run analysis and return a report. It should not call
Twilio directly after this refactor. Otherwise one incident can produce two
phone calls.

### 2.4 Strict Webhook Security

When `WEBHOOK_SECRET` is configured, missing or invalid
`X-Hub-Signature-256` must return `401`.

Local development may allow unsigned webhooks only when `WEBHOOK_SECRET` is not
configured.

### 2.5 Persistence Comes Before Engine Routing

The engine cannot depend on repository classes that do not exist yet.

Add `agent_events` schema and a simple `db.create_event()` method before
building `EventEngine`. Later, the repository refactor can move the method into
`IncidentRepo` without changing engine behavior.

## 3. Optimal Execution Order

### Phase 0: Architecture Lock-In (~45 min)

#### Task 0.1: Create runtime.py singleton container

- Output: `app/core/runtime.py`
- Instantiate exactly one shared set of runtime services.
- Export:
  - `watch_manager`
  - `event_deduplicator`
  - `alert_cooldown`
  - `event_engine`
  - `orchestrator`
  - `twilio_service`

#### Task 0.2: Define service mapping MVP

- Output: comments/config in `watch_manager.py` and deployment route.
- Use explicit repo-to-service mapping when available.
- Fall back to current user's heartbeat `monitored_containers`.
- Persist `services_watched` in deployment metadata.

#### Task 0.3: Move alert ownership decision into the plan

- EventEngine handles phone alerts and cooldown.
- Orchestrator returns RCA only.
- Remove or disable Twilio side effect from `RCAOrchestrator.analyze()`.

#### Task 0.4: Fix webhook HMAC behavior

- If `WEBHOOK_SECRET` exists:
  - missing signature -> `401`
  - invalid signature -> `401`
- If no secret exists:
  - permit request for local dev with warning.

## 4. Phase 1: Models and Minimal Persistence (~90 min)

### Task 1.1: Create event_models.py

- Output: `app/models/event_models.py`

Create:

- `EventType = Literal["container_crash", "container_restart", "container_start", "health_unhealthy", "deployment_detected", "log_error"]`
- `EventSource = Literal["agent", "webhook", "manual", "sdk"]`
- `Severity = Literal["critical", "high", "medium", "low", "warning", "info"]`
- `AgentEventPayload`
- `EnrichedEvent`
- `AgentEventResponse`
- `ConfidenceResult`
- `EventResult`
- `WatchEntry`
- `WatchStatus`

`AgentEventPayload` fields:

- `type`
- `source = "agent"`
- `container_id`
- `container_name`
- `service_name`
- `timestamp`
- `exit_code`
- `reason`
- `image_hash`
- `restart_count`
- `logs`
- `metadata`

Allow `service_name` to be optional on input, but ensure `EnrichedEvent`
always has one after enrichment.

### Task 1.2: Add agent_events table

- Output: `app/db/schema.sql`

Create `agent_events`:

```sql
CREATE TABLE IF NOT EXISTS agent_events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_id TEXT NOT NULL UNIQUE,
  github_id TEXT NOT NULL REFERENCES opstron_users(github_id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  source TEXT NOT NULL,
  service_name TEXT NOT NULL,
  container_id TEXT,
  container_name TEXT,
  exit_code TEXT,
  reason TEXT,
  restart_count INTEGER DEFAULT 0,
  severity TEXT NOT NULL,
  confidence INTEGER DEFAULT 0,
  rca_triggered BOOLEAN DEFAULT FALSE,
  phone_alert_triggered BOOLEAN DEFAULT FALSE,
  correlation JSONB DEFAULT '{}'::jsonb,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Indexes:

- `github_id`
- `type`
- `service_name`
- `created_at DESC`
- `event_id`
- `(github_id, service_name, created_at DESC)`

Enable RLS and grant `service_role`.

### Task 1.3: Add minimal db.create_event()

- Output: `app/db/supabase_client.py`

Add a direct method on `Database`:

```python
async def create_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
    ...
```

This is intentionally before the repo refactor. `IncidentRepo.create_event()`
will replace the internals later while preserving the public `db.create_event()`
facade.

### Task 1.4: Decide severity storage

Use the broader severity set on `agent_events`:

- `critical`
- `high`
- `medium`
- `low`
- `warning`
- `info`

Do not reuse the restrictive `rca_logs.severity` check for event storage.

## 5. Phase 2: Event Engine Core (~180 min)

### Task 2.1: Create dedup.py

- Output: `app/core/dedup.py`

Create:

- `EventDeduplicator`
- `AlertCooldown`

Rules:

- Dedup key: `github_id:container_id:type:reason`
- Dedup window: 60 seconds
- Cleanup keys older than 120 seconds
- Alert key: `github_id:service_name`
- Alert cooldown: 300 seconds
- Dedup suppresses RCA and phone calls, but the suppressed event may still be
  stored for audit if desired.

### Task 2.2: Create watch_manager.py

- Output: `app/core/watch_manager.py`

Create `WatchModeManager` keyed by:

```text
github_id:service_name
```

Methods:

- `start_watch(github_id, service_name, commit_sha, repo, author, branch, source, image_hash=None, duration_minutes=5)`
- `get_watch(github_id, service_name)`
- `get_watches_for_user(github_id)`
- `get_all_active()`
- `reinforce_watch(github_id, service_name, extra_minutes=2)`
- `cleanup_expired()`

DB fallback:

- On miss, query recent `deployments` rows with `status='watching'`.
- Use persisted `services_watched` metadata where available.
- Do not return watches for another user.

### Task 2.3: Create event_engine.py - enrichment and classification

- Output: `app/core/event_engine.py`

`EventEngine.__init__` takes:

- `watch_manager`
- `dedup`
- `cooldown`
- `orchestrator`
- `alert_service`
- `db`

Enrichment:

- Generate `event_id`.
- Normalize timestamp to UTC.
- Resolve `service_name` in this order:
  1. payload `service_name`
  2. `metadata.service_name`
  3. normalized `container_name`
  4. `unknown-service`
- Attach `github_id`.

Classification:

- `container_crash` + non-zero exit -> `critical`
- `container_crash` + exit `0` -> `high`
- `container_restart` + `restart_count > 3` -> `critical`
- `log_error` during watch -> `high`
- `log_error` without watch -> `medium`
- `health_unhealthy` -> `warning`
- `container_start` -> `info`
- `deployment_detected` -> `info`

### Task 2.4: Correlation and confidence

Correlation:

- Call `watch_manager.get_watch(github_id, event.service_name)`.
- If no exact service watch exists, check user-scoped repo watch if implemented.
- Return correlation with:
  - `is_deployment_related`
  - `is_regression`
  - `confidence`
  - `reasons`
  - `watch`

Confidence scoring:

- `+40` image hash changed and both hashes are known.
- `+30` crash/log error within 2 minutes of watch start.
- `+20` non-zero exit code.
- `+10` OOM reason or exit code `137`.
- `+10` service name exactly matches explicit mapping.
- `-20` fallback repo-level watch only.

Regression threshold:

- `confidence > 60`

### Task 2.5: Routing and persistence

`process(event, user_id)` order:

1. enrich
2. classify
3. correlate
4. deduplicate
5. route
6. persist final event result

Routing:

- `container_crash` + watch + confidence > 60 -> RCA + phone if cooldown allows + store
- `container_crash` + no watch -> RCA + store
- `container_crash` + watch + confidence <= 60 -> RCA + store, no phone
- `container_restart` + restart_count > 3 -> RCA + store
- `log_error` + watch -> RCA + store
- `log_error` + no watch -> store only
- `health_unhealthy` -> store only
- `container_start` -> store only
- `deployment_detected` -> store only

Agent-down guard:

- If a crash event arrives and last heartbeat is older than 90 seconds, mark
  `metadata.agent_stale = true`.
- Do not blindly suppress all stale crash events; prefer lowering confidence or
  suppressing phone calls only. A delayed crash event can still be useful for RCA.

Phone alert:

- Check `cooldown.can_alert(user_id, service_name)`.
- If allowed, call alert service and then `record_alert`.
- If blocked, still run RCA and store event.

Persistence:

- Call `db.create_event()` with final enriched event and routing result.
- Store `rca_triggered` and `phone_alert_triggered`.

## 6. Phase 3: API Endpoint and Agent Integration (~120 min)

### Task 3.1: Add POST /agent/events

- Output: initially add to existing `ingest.py`, or directly to `routes/agent.py`
  if route splitting has already begun.

Handler:

- Auth: `AgentKeyAuth`
- Input: `AgentEventPayload`
- Calls shared `event_engine.process(payload, user_id=agent_identity["user_id"])`
- Returns `AgentEventResponse`

Do not instantiate a new engine inside the route.

### Task 3.2: Convert /agent/logs/ingest to log_error events

Current behavior must remain backward compatible.

Rules:

- Always accept old log payloads.
- If logs contain error signals (`error`, `exception`, `traceback`, `fatal`,
  `panic`, `segmentation fault`), create a `log_error` event and send it to
  `EventEngine`.
- If logs are healthy, return `received` without RCA.

### Task 3.3: Update opstron_forwarder.py

Add:

```python
EVENT_URL = f"{BACKEND_URL}/agent/events"
```

Crash event payload:

- `type = "container_crash"`
- `source = "agent"`
- `container_id`
- `container_name`
- `timestamp`
- `exit_code`
- `reason`
- `image_hash`
- `restart_count`
- `logs`
- `metadata.event_action`

Reason mapping:

- `oom` -> `oom`
- `kill` -> `sigkill`
- `die` with exit `0` -> `exit_zero`
- `die` with non-zero exit -> `exit_nonzero`
- `stop` -> `stopped`

Fallback:

- If `/agent/events` returns `404`, post the crash logs to
  `/agent/logs/ingest` for old backend compatibility.

### Task 3.4: Update /notify-deployment

Use strict HMAC verification and shared `watch_manager`.

Steps:

1. Parse GitHub push payload.
2. Resolve `github_id` or connected repo owner.
3. Resolve `services_watched` using service mapping.
4. For each service, call shared `watch_manager.start_watch(...)`.
5. Persist deployment with `services_watched`.
6. Emit `deployment_detected` event through EventEngine or store directly.

Response includes:

- `status`
- `deployment_id`
- `commit_sha`
- `watch_until`
- `services_watched`
- `message`

## 7. Phase 4: Route Split (~90 min)

After the event path works, split routes. This reduces risk because behavior is
already covered by tests.

### Task 4.1: Create routes/agent.py

Move:

- `POST /agent/events`
- `POST /agent/logs/ingest`
- `POST /agent/heartbeat`
- `GET /agent/status`
- `GET /agent/status/by-session`
- `HeartbeatPayload`
- heartbeat helper functions

Import runtime singletons from `app.core.runtime`.

### Task 4.2: Create routes/deployments.py

Move:

- `POST /notify-deployment`
- `GET /deployment-status`
- `GET /deployment-history`

Use shared `watch_manager`.

Do not instantiate `WatchModeManager` here.

### Task 4.3: Rename ingest.py to errors.py

Keep:

- `POST /ingest-error`
- `GET /rca-history`
- `_prepare_log_text()`
- `_add_deployment_context_to_logs()`

Refactor `POST /ingest-error` to create a `log_error` event when possible.

### Task 4.4: Update router registration

Update:

- `app/api/__init__.py`
- `app/api/routes/__init__.py`

Register:

- `agent.router` with `tags=["Docker Agent"]`
- `deployments.router` with `tags=["Deployments"]`
- `errors.router` with `tags=["Error Ingestion"]`

Verify:

```bash
python -c "from app.api import api_router"
```

## 8. Phase 5: Repository Refactor (~90 min)

This happens after `db.create_event()` already exists and works.

### Task 5.1: Create repos package

Create:

- `app/db/repos/__init__.py`
- `app/db/repos/base.py`
- `app/db/repos/user_repo.py`
- `app/db/repos/incident_repo.py`
- `app/db/repos/deployment_repo.py`
- `app/db/repos/repo_repo.py`

### Task 5.2: Move methods into repos

`UserRepo`:

- `upsert_user`
- `get_user_by_api_key`
- `get_user_by_github_id`
- `save_session_token`
- `get_session_by_token`
- `upsert_heartbeat`
- `get_heartbeat`

`IncidentRepo`:

- `create_rca_log`
- `get_rca_logs`
- `get_rca_by_deployment`
- `create_event`
- `create_vapi_call`
- `update_vapi_call`
- `get_vapi_calls`

`DeploymentRepo`:

- `create_deployment`
- `update_deployment`
- `get_deployment`
- `get_recent_deployments`
- `get_active_deployment_db`
- `create_commit`
- `get_commit_by_sha`
- `get_recent_commits`

`RepoRepo`:

- `upsert_repo`

### Task 5.3: Keep Database as facade

`app/db/supabase_client.py` remains the public import path:

```python
from app.db.supabase_client import db
```

`Database` delegates to repos internally.

Do not delete chat message methods unless a search confirms they are unused.

## 9. Phase 6: Tests and Verification (~120 min)

### Unit tests

Minimum tests:

- duplicate event within 60 seconds is suppressed
- same event after 60 seconds is accepted
- alert cooldown blocks second phone call within 5 minutes
- confidence score crosses threshold for deployment crash
- repo-level fallback lowers confidence
- `log_error` event is valid EventType
- stale heartbeat suppresses phone alert but stores event

### Route tests

Minimum tests:

- `/agent/events` rejects missing API key
- `/agent/events` accepts valid crash event
- `/agent/logs/ingest` converts error logs to `log_error`
- `/agent/logs/ingest` ignores healthy logs
- `/notify-deployment` rejects missing signature when secret exists
- `/notify-deployment` creates service-scoped watches

### Import checks

Run:

```bash
python -c "from app.api import api_router"
python -c "from app.core.runtime import event_engine, watch_manager"
```

## 10. API Contracts

### POST /agent/events

Auth: `X-API-Key`

Request:

```json
{
  "type": "container_crash",
  "source": "agent",
  "container_id": "a1b2c3d4e5f6",
  "container_name": "checkout-api",
  "service_name": "checkout-api",
  "timestamp": "2026-04-26T01:05:00Z",
  "exit_code": "137",
  "reason": "oom",
  "image_hash": "sha256:abc123",
  "restart_count": 2,
  "logs": "last 100 lines...",
  "metadata": {
    "event_action": "oom"
  }
}
```

Response:

```json
{
  "status": "rca_triggered",
  "message": "Crash detected during active watch mode. RCA triggered.",
  "event_id": "evt-a1b2c3d4",
  "rca_triggered": true,
  "phone_alert_triggered": true,
  "confidence": 80,
  "reasons": [
    "Image changed since deployment",
    "Crash within 2 min of deploy"
  ]
}
```

### POST /notify-deployment

Auth: `X-Hub-Signature-256` when `WEBHOOK_SECRET` exists.

Response:

```json
{
  "status": "watching",
  "deployment_id": "deploy-a1b2c3d4",
  "commit_sha": "abc1234",
  "watch_until": "2026-04-26T01:10:00Z",
  "services_watched": ["checkout-api", "worker"],
  "message": "Watch mode active for 5 minutes."
}
```

## 11. Event Engine Rules

Pipeline order:

```text
process(raw_event, user_id)
  -> enrich
  -> classify
  -> correlate
  -> deduplicate
  -> route
  -> persist
```

Routing matrix:

| Event | Watch | Confidence | Action |
|---|---:|---:|---|
| `container_crash` | yes | > 60 | RCA + phone if cooldown allows + store |
| `container_crash` | yes | <= 60 | RCA + store |
| `container_crash` | no | 0 | RCA + store |
| `container_restart` loop | any | any | RCA + store |
| `log_error` | yes | any | RCA + store |
| `log_error` | no | any | store only |
| `health_unhealthy` | any | any | store only |
| `container_start` | any | any | store only |
| `deployment_detected` | any | any | store only |

## 12. Edge Cases

| Scenario | Expected behavior |
|---|---|
| Crash loop sends 10 events in 30 seconds | First event routes, later duplicates suppressed |
| Deployment route and agent route import runtime | Both see the same watch manager state |
| Two services deploy together | One watch entry per user/service |
| Backend restarts during watch | Watch recovered from deployments table |
| Old agent posts logs only | Error logs become `log_error`; healthy logs are ignored |
| LLM fails | Event is still stored; RCA result records failure |
| Phone call already sent 3 minutes ago | Cooldown blocks phone only; RCA still runs |
| Missing webhook signature with secret configured | Request rejected with `401` |
| Repo cannot map to service | Use heartbeat fallback or lower-confidence repo watch |

## 13. What Not To Build Yet

| Feature | Why skip |
|---|---|
| Redis dedup/cooldown | In-memory is fine for single-worker MVP |
| Kubernetes events | Docker-only MVP |
| WebSocket/SSE dashboard push | Polling is enough |
| Slack/PagerDuty | Phone + dashboard first |
| Event replay tooling | Store events now, replay later |
| Custom dedup windows | Fixed 60 seconds is enough |
| Agent auto-update | Manual update for MVP |
| Jenkins/GitLab integrations | GitHub first |

## 14. Final MVP Slice

Build in this exact order:

1. Strict webhook HMAC fix.
2. `agent_events` schema.
3. `event_models.py`.
4. Minimal `db.create_event()`.
5. Shared `runtime.py`.
6. `dedup.py`.
7. `watch_manager.py`.
8. `event_engine.py`.
9. `POST /agent/events`.
10. Forwarder crash events to `/agent/events`.
11. Convert old log ingestion to `log_error`.
12. Add tests.
13. Split routes.
14. Refactor repos.

This order keeps the system implementable at every step and avoids the three
major failure modes: missing persistence, split runtime state, and broken
deployment-to-service correlation.
