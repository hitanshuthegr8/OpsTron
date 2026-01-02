# ⚡ OpsTron - AI-Powered Root Cause Analysis

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent DevOps assistant that automatically analyzes runtime errors and provides actionable insights using AI.

## Key Features

- **Automated Error Ingestion** - Backend services POST errors directly to the agent
- **AI-Powered Analysis** - Uses LLMs to understand errors and suggest fixes
- **GitHub Integration** - Analyzes recent commits for potential causes
- **Runbook Matching** - Finds relevant documentation automatically
- **Real-time Dashboard** - Monitor errors and RCA reports in browser
- **🚀 Deployment Protection (MVP4)** - Catches deployment regressions via GitHub Actions integration

---

## Project Structure

```
opstron/
├── agent/                      # RCA Agent Service (Port 8001)
│   ├── api/                    # API Layer
│   │   ├── __init__.py         # Router aggregation
│   │   └── routes/             # Route handlers
│   │       ├── health.py       # Health check endpoints
│   │       ├── ingest.py       # Error ingestion (MVP3)
│   │       ├── analyze.py      # Manual upload (MVP2)
│   │       └── github.py       # GitHub configuration
│   │
│   ├── agents/                 # AI Agent Modules
│   │   ├── log_agent.py        # Log analysis
│   │   ├── commit_agent.py     # Git commit analysis
│   │   ├── runbook_agent.py    # Runbook matching
│   │   └── synthesizer_agent.py # RCA synthesis
│   │
│   ├── services/               # Business Logic
│   │   └── rca_service.py      # RCA orchestration service
│   │
│   ├── models/                 # Data Models
│   │   └── error_models.py     # Pydantic schemas
│   │
│   ├── config/                 # Configuration
│   │   ├── settings.py         # App settings
│   │   └── .env                # Environment variables
│   │
│   ├── db/                     # Database Layer
│   │   └── chroma_store/       # Vector DB for runbooks
│   │
│   ├── tools/                  # Utilities
│   │   ├── github_api.py       # GitHub client
│   │   └── log_parser.py       # Log parsing utilities
│   │
│   ├── main.py                 # Application entry point
│   ├── orchestrator.py         # Agent orchestration
│   ├── llm.py                  # LLM client (Ollama/Gemini)
│   └── schemas.py              # Legacy schemas
│
├── demo-backend/               # Demo Backend Service (Port 8000)
│   ├── app.py                  # FastAPI demo service
│   └── requirements.txt        # Dependencies
│
├── frontend/                   # Dashboard UI (Port 3000)
│   ├── index.html              # Main HTML
│   ├── src/
│   │   ├── css/
│   │   │   └── main.css        # Styles
│   │   ├── js/
│   │   │   └── app.js          # Application logic
│   │   └── assets/             # Images, icons
│   └── server.py               # Development server
│
├── runbooks/                   # Runbook Documents
│   ├── api_timeout.md
│   ├── db_deadlock.md
│   └── service_down.md
│
└── docs/                       # Documentation
    ├── MVP3_README.md          # MVP3 features detail
    ├── QUICKSTART.md           # Getting started
    ├── COMMANDS.md             # CLI commands
    └── GEMINI_MIGRATION.md     # LLM setup guide
```

---

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/opstron.git
cd opstron
```

### 2. Start the Agent (Terminal 1)

```powershell
cd agent
.\venv\Scripts\Activate.ps1
python main.py
```

### 3. Start Demo Backend (Terminal 2)

```powershell
cd demo-backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app:app --port 8000
```

### 4. Start Frontend (Terminal 3)

```powershell
cd frontend
python server.py
```

### 5. Open Dashboard

Navigate to **http://localhost:3000**

---

## API Reference

### Agent API (Port 8001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health check |
| `/ingest-error` | POST | Automated error ingestion |
| `/analyze` | POST | Manual log file upload |
| `/config/github` | GET/POST | GitHub configuration |
| `/commits` | GET | Fetch recent commits |
| `/docs` | GET | Interactive API documentation |

### Demo Backend API (Port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Backend health check |
| `/trigger-error` | GET | Trigger test error |
| `/checkout` | POST | Demo endpoint (random errors) |
| `/logs` | GET | View log buffer |

---

## 🚀 Deployment Protection (MVP4)

OpsTron can automatically detect errors caused by recent code deployments using GitHub Actions integration.

### How It Works

1. **Developer pushes code** → GitHub Actions triggers
2. **GitHub notifies OpsTron** → Agent enters "Watch Mode" for 5 minutes
3. **If error occurs during watch** → OpsTron fetches the commit diff
4. **AI correlates error with code changes** → Provides rollback recommendation

### Setup GitHub Actions

The workflow file is already created at `.github/workflows/opstron_notify.yml`.

**Add the secret to your repository:**

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `OPSTRON_URL`
4. Value: Your OpsTron server URL (e.g., `http://your-server-ip:8001`)

### Deployment Protection API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/notify-deployment` | POST | Called by GitHub Actions on push |
| `/deployment-status` | GET | Check if watch mode is active |
| `/deployment-history` | GET | View recent deployments and errors |

### Example: Deployment Notification

```bash
# Sent automatically by GitHub Actions:
curl -X POST http://localhost:8001/notify-deployment \
  -H "Content-Type: application/json" \
  -d '{
    "commit_sha": "a1b2c3d4e5f6...",
    "repository": "hitanshuthegr8/OpsTron",
    "author": "hitanshuthegr8",
    "message": "fix: updated database logic",
    "branch": "main"
  }'
```

### Check Deployment Status

```bash
curl http://localhost:8001/deployment-status

# Response when watching:
{
  "status": "watching",
  "active_deployment": {
    "commit_sha": "a1b2c3d",
    "author": "hitanshuthegr8",
    "watch_until": "2024-01-15T10:35:00Z"
  }
}
```

---

## Configuration

### Environment Variables

Create `agent/config/.env`:

```env
# LLM Configuration
GEMINI_API_KEY=your_key_here      # For cloud LLM (optional)

# GitHub Integration
GITHUB_TOKEN=ghp_xxxxx            # Personal access token
DEFAULT_REPO=owner/repo           # Default repository

# Database
CHROMA_PERSIST_DIR=./db/chroma_store
```

### LLM Backend

OpsTron supports two LLM backends:

| Backend | Pros | Cons |
|---------|------|------|
| **Ollama (Local)** | Free, private, no rate limits | Slower, requires GPU |
| **Gemini (Cloud)** | Fast, high quality | Rate limits, API costs |

The agent automatically detects Ollama and uses it if available.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│                   (Dashboard UI - Port 3000)                 │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         AGENT                                │
│                   (RCA System - Port 8001)                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   API Layer                          │    │
│  │  /health  /ingest-error  /analyze  /config/github   │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  Orchestrator                        │    │
│  │         Coordinates all agent activities             │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│  ┌──────────┬──────────┬──────────┬──────────┐              │
│  │ LogAgent │CommitAgent│RunbookAgent│Synthesizer│          │
│  └──────────┴──────────┴──────────┴──────────┘              │
│                          │                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              LLM Client (Ollama/Gemini)             │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────┐
│                      DEMO BACKEND                            │
│                   (Test Service - Port 8000)                 │
│                                                              │
│  Error Middleware → Log Buffer → POST to /ingest-error      │
└─────────────────────────────────────────────────────────────┘
```

---

## Testing

```powershell
# Trigger a test error (automatically analyzed)
curl http://localhost:8000/trigger-error

# Check agent health
curl http://localhost:8001/health

# Configure GitHub
curl -X POST http://localhost:8001/config/github `
  -H "Content-Type: application/json" `
  -d '{"token":"ghp_xxx","repo":"owner/repo"}'

# Fetch commits
curl "http://localhost:8001/commits?limit=5"
```

---

## Technologies

- **Backend**: Python 3.12, FastAPI
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **LLM**: Ollama (Phi-3) / Google Gemini
- **Vector DB**: ChromaDB
- **HTTP Client**: httpx

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request
# test
