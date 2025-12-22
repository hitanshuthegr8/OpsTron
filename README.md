# MVP2 - Agentic Root Cause Analysis System

Production-ready agentic system for analyzing backend failures through log upload, commit correlation, and runbook search.

## Architecture

**Log-Upload Model**: Users manually upload logs. System does NOT access infrastructure.

### Components

1. **Backend Service** (`backend/`): Demo FastAPI service that generates realistic errors
2. **Agent API** (`agent/`): FastAPI server exposing `/analyze` endpoint
3. **Agentic Pipeline**:
   - **LogAgent**: Extracts error signals from uploaded logs
   - **CommitAgent**: Fetches recent GitHub commits
   - **RunbookAgent**: Searches vector store for relevant fixes
   - **SynthesizerAgent**: Uses Gemini to generate RCA report

## Project Structure

```
mvp2/
├── backend/                    # Demo backend service
│   ├── app.py                 # FastAPI service with error scenarios
│   ├── requirements.txt       # Backend dependencies
│   └── Dockerfile            # Container configuration
│
├── agent/                     # Agentic RCA system
│   ├── main.py               # FastAPI API server
│   ├── orchestrator.py       # Multi-agent coordinator
│   ├── llm.py                # LLM client wrapper
│   ├── requirements.txt      # Agent dependencies
│   │
│   ├── agents/               # Individual agents
│   │   ├── log_agent.py      # Log analysis
│   │   ├── commit_agent.py   # GitHub commit fetching
│   │   ├── runbook_agent.py  # Vector search
│   │   └── synthesizer_agent.py  # RCA synthesis
│   │
│   ├── tools/                # Utility tools
│   │   ├── github_api.py     # GitHub API client
│   │   ├── log_parser.py     # Log parsing utilities
│   │   ├── doc_loader.py     # Document loader
│   │   └── utils.py          # Helper functions
│   │
│   ├── db/                   # Database layer
│   │   ├── chroma_store/
│   │   │   └── vector_store.py  # ChromaDB interface
│   │   └── load_runbooks.py  # Runbook loader script
│   │
│   └── config/               # Configuration
│       ├── settings.py       # Settings management
│       └── .env.example      # Environment template
│
└── runbooks/                 # Troubleshooting documentation
    ├── db_deadlock.md
    ├── api_timeout.md
    └── service_down.md
```

## Setup Instructions

### 1. Backend Service Setup

```bash
cd backend
pip install -r requirements.txt
python app.py
```

The backend will run on `http://localhost:8000`

### 2. Agent System Setup

```bash
cd agent

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp config/.env.example config/.env
# Edit config/.env and add your API keys:
# - ANTHROPIC_API_KEY
# - GITHUB_TOKEN

# Load runbooks into ChromaDB
cd db
python load_runbooks.py
cd ..

# Start the agent API
python main.py
```

The agent API will run on `http://localhost:8001`

## Usage

### 1. Generate Sample Logs

Make requests to the backend service to generate error logs:

```bash
curl -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "cart_items": ["item1", "item2"],
    "payment_method": "credit_card"
  }'
```

Check `backend/backend.log` for generated error logs.

### 2. Analyze Logs

Upload the log file to the agent API:

```bash
curl -X POST http://localhost:8001/analyze \
  -F "service=payment-service" \
  -F "repo=your-org/your-repo" \
  -F "log_file=@backend/backend.log"
```

### 3. Review RCA Report

The API will return a comprehensive JSON report:

```json
{
  "service": "payment-service",
  "root_cause": "Database deadlock in payment processing",
  "confidence": "high",
  "contributing_factors": [
    "Concurrent transactions on order table",
    "Missing index on order_id column"
  ],
  "evidence": {
    "logs": "ERROR: Deadlock found when trying to get lock",
    "commits": "Recent commit modified transaction ordering",
    "runbooks": "Database Deadlock Resolution runbook matched"
  },
  "recommended_actions": [
    "Add index on orders.order_id",
    "Implement retry logic with exponential backoff",
    "Review transaction ordering in recent commits"
  ],
  "timeline": "Deadlock occurred during high-concurrency checkout",
  "analyzed_at": "2025-12-18T20:31:11.123456"
}
```

## API Endpoints

### Backend Service

- `GET /health` - Health check
- `POST /checkout` - Simulate checkout (generates errors)

### Agent API

- `GET /health` - Health check with agent status
- `POST /analyze` - Analyze logs and generate RCA
  - Form fields:
    - `service` (string): Service name
    - `repo` (string): GitHub repository (e.g., "owner/repo")
    - `log_file` (file): Log file (.log extension required)

## Technology Stack

- **Framework**: FastAPI
- **LLM**: Google Gemini 2.0 Flash (via LangChain)
- **Vector DB**: ChromaDB
- **GitHub API**: aiohttp
- **Configuration**: Pydantic Settings

## Key Features

✅ **Multi-Agent Architecture**: Specialized agents for different analysis tasks  
✅ **LLM-Powered Analysis**: Gemini for intelligent log interpretation  
✅ **Vector Search**: Semantic search over runbook documentation  
✅ **GitHub Integration**: Correlates errors with recent code changes  
✅ **Structured Output**: JSON-formatted RCA reports  
✅ **Async Processing**: Non-blocking API operations  

## Development Notes

- The backend service randomly generates different error types (timeout, deadlock, null pointer)
- Runbooks are loaded into ChromaDB for semantic search
- The system uses a 4-step pipeline: Log Analysis → Commit Fetch → Runbook Search → Synthesis
- All agents are orchestrated sequentially for comprehensive analysis

## Environment Variables

Required in `agent/config/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GITHUB_TOKEN=your_github_token_here
CHROMA_PERSIST_DIR=./db/chroma_data
```

## License

MIT License
