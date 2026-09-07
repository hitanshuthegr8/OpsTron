# 🚀 MVP3 - Automated Error Ingestion

## Overview

MVP3 upgrades the Agentic RCA System from manual log uploads to **automated error ingestion**. When a runtime error occurs in your backend service, it's automatically captured and sent to the agent for immediate root cause analysis.

```
┌─────────────────────────────────────────────────────────────────┐
│                        MVP3 ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Backend Service                    Agent System               │
│   ┌─────────────────┐               ┌─────────────────┐        │
│   │                 │               │                 │        │
│   │  API Request    │               │  /ingest-error  │        │
│   │       ↓         │               │       ↓         │        │
│   │  Error Occurs   │──── POST ────▶│  Orchestrator   │        │
│   │       ↓         │   (auto)      │       ↓         │        │
│   │  Middleware     │               │   LogAgent      │        │
│   │   Captures      │               │   CommitAgent   │        │
│   │       ↓         │               │   RunbookAgent  │        │
│   │  Log Buffer     │               │       ↓         │        │
│   │  (last 200)     │               │  Synthesizer    │        │
│   │                 │               │       ↓         │        │
│   └─────────────────┘               │  RCA Report     │        │
│                                     └─────────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## What's New in MVP3

| Feature | MVP2 | MVP3 |
|---------|------|------|
| Log ingestion | Manual upload | **Automatic** |
| Error trigger | User action | **Runtime error** |
| Backend changes | None | Required (middleware) |
| Real-time | ❌ | ✅ |
| Production feel | Medium | **High** |

## Quick Start

### 1. Start the Agent (Terminal 1)
```powershell
cd agent
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8001
```

### 2. Start the Backend (Terminal 2)
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install httpx  # New dependency for MVP3
uvicorn app:app --reload --port 8000
```

### 3. Trigger an Error
```powershell
# Easy way - use the test endpoint
curl http://localhost:8000/trigger-error

# Or trigger a checkout error
curl -X POST http://localhost:8000/checkout `
  -H "Content-Type: application/json" `
  -d '{"user_id":"u123","cart_items":["item1"],"payment_method":"card"}'
```

### 4. Watch the Magic! 🎉
- Backend catches the error automatically
- Sends structured payload to agent
- Agent runs full RCA pipeline
- Returns root cause analysis

## New Endpoints

### Agent: POST `/ingest-error`
Receives structured error payloads for automated analysis.

**Request Body:**
```json
{
  "service": "checkout-api",
  "error": "KeyError: 'amount'",
  "stacktrace": "Traceback (most recent call last)...",
  "recent_logs": "2024-12-22 10:00:01 INFO: Checkout initiated...",
  "timestamp": "2024-12-22T10:00:02.123456",
  "env": "local",
  "endpoint": "/checkout",
  "method": "POST",
  "user_id": "u123",
  "request_id": "abc12345"
}
```

**Response:**
```json
{
  "status": "analyzed",
  "request_id": "abc12345",
  "rca_report": {
    "root_cause": "Missing 'amount' field in payment payload",
    "confidence": "high",
    "recommended_actions": [...],
    ...
  },
  "processing_time_ms": 2340.5
}
```

### Backend: GET `/trigger-error`
Debug endpoint to test the error ingestion pipeline.

### Backend: GET `/logs`
View the recent log buffer (useful for debugging).

## How It Works

### 1. Global Error Middleware
The backend has a middleware that catches ALL unhandled exceptions:

```python
@app.middleware("http")
async def error_capture_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        # Report to agent (fire and forget)
        asyncio.create_task(
            error_reporter.report(error=e, request=request)
        )
        raise
```

### 2. Log Buffering
The last 200 log lines are kept in memory and sent with error reports:

```python
class LogBuffer:
    def __init__(self, maxlen=200):
        self._buffer = deque(maxlen=maxlen)
    
    def get_recent(self, count=200) -> str:
        return "\n".join(list(self._buffer)[-count:])
```

### 3. Error Reporter
Automatically formats and sends errors to the agent:

```python
class ErrorReporter:
    async def report(self, error, request=None):
        payload = {
            "service": self.service_name,
            "error": f"{type(error).__name__}: {str(error)}",
            "stacktrace": traceback.format_exc(),
            "recent_logs": log_buffer.get_recent(200),
            ...
        }
        await client.post(f"{self.agent_url}/ingest-error", json=payload)
```

## Configuration

### Backend Environment Variables
```bash
AGENT_URL=http://localhost:8001      # Agent API URL
SERVICE_NAME=checkout-api            # Your service name
ENVIRONMENT=local                    # local/staging/production
```

### Agent Configuration (config/.env)
```bash
DEFAULT_REPO=owner/repo              # Default repo for commit analysis
```

## Error Payload Schema

```python
class ErrorPayload(BaseModel):
    service: str          # Required: Service name
    error: str            # Required: Error message
    stacktrace: str       # Stack trace
    recent_logs: str      # Recent log lines
    timestamp: str        # ISO timestamp
    env: str              # Environment
    request_id: str       # Request ID for tracing
    user_id: str          # Affected user
    endpoint: str         # API endpoint that failed
    method: str           # HTTP method
    extra: dict           # Additional context
```

## MVP3 vs Sentry/Datadog

This is exactly how production error tracking tools started! MVP3 demonstrates:

- ✅ Automatic error capture
- ✅ Structured payloads
- ✅ Context preservation (logs, stack traces)
- ✅ Real-time analysis
- ✅ No manual intervention

## What's Next (MVP4 Preview)

- Prometheus alerts integration
- Loki log aggregation
- Kubernetes events
- Auto rollback suggestions
- PR risk prediction
- Slack/PagerDuty notifications
