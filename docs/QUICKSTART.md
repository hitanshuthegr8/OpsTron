# Quick Start Guide - MVP2 Agentic RCA System

## ✅ Setup Checklist

### Step 1: Create Virtual Environment for Backend
```bash
# Navigate to project root
cd c:\Users\HP\Desktop\Secret\Project\mvp2

# Create virtual environment for backend
cd backend
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# You should see (venv) in your terminal prompt
```

### Step 2: Install Backend Dependencies
```bash
# Make sure you're in backend directory with venv activated
pip install -r requirements.txt
```

### Step 3: Create Virtual Environment for Agent
```bash
# Deactivate backend venv and go to agent directory
deactivate
cd ..\agent

# Create virtual environment for agent
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# You should see (venv) in your terminal prompt
```

### Step 4: Install Agent Dependencies
```bash
# Make sure you're in agent directory with venv activated
pip install -r requirements.txt
```

### Step 5: Configure Environment Variables
```bash
# Still in agent directory
# Copy the example file (Windows)
copy config\.env.example config\.env

# Edit config/.env and add your credentials:
# GEMINI_API_KEY=YOUR_GEMINI_API_KEY
# GITHUB_TOKEN=YOUR_GITHUB_TOKEN
# CHROMA_PERSIST_DIR=./db/chroma_data
```

**Note**: Open `agent/config/.env` in your editor and add your actual API keys.

### Step 6: Load Runbooks into Vector Database
```bash
# Make sure agent venv is activated and you're in agent directory
cd db
python load_runbooks.py
cd ..
```

### Step 7: Start the Backend Service (Terminal 1)
```bash
# Open a NEW terminal
cd c:\Users\HP\Desktop\Secret\Project\mvp2\backend

# Activate backend venv
venv\Scripts\activate

# Start the service
python app.py
# Should start on http://localhost:8000
```

### Step 8: Start the Agent API (Terminal 2)
```bash
# Open ANOTHER NEW terminal
cd c:\Users\HP\Desktop\Secret\Project\mvp2\agent

# Activate agent venv
venv\Scripts\activate

# Start the agent API
python main.py
# Should start on http://localhost:8001
```

## 🧪 Testing the System

### Generate Error Logs
```bash
# Make a few requests to generate errors
curl -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "cart_items": ["item1"], "payment_method": "credit_card"}'

# Repeat 3-5 times to generate different error types
```

### Analyze the Logs
```bash
curl -X POST http://localhost:8001/analyze \
  -F "service=payment-service" \
  -F "repo=fastapi/fastapi" \
  -F "log_file=@backend/backend.log"
```

## 📋 Expected Output

The analysis will return a JSON report with:
- **root_cause**: Primary failure reason
- **confidence**: high/medium/low
- **contributing_factors**: Additional issues
- **evidence**: Log excerpts, commits, runbooks
- **recommended_actions**: Fix suggestions
- **timeline**: Event sequence

## 🔍 System Architecture

```
User uploads log → LogAgent (extracts errors) 
                 → CommitAgent (fetches GitHub commits)
                 → RunbookAgent (searches vector DB)
                 → SynthesizerAgent (generates RCA with Claude)
                 → Returns comprehensive report
```

## 🛠️ Troubleshooting

**Issue**: ChromaDB collection not found
- **Fix**: Run `python db/load_runbooks.py` from agent directory

**Issue**: API key errors
- **Fix**: Verify `.env` file has valid GEMINI_API_KEY and GITHUB_TOKEN

**Issue**: Module import errors
- **Fix**: Ensure you're running from the correct directory (agent/ or backend/)

**Issue**: GitHub API rate limit
- **Fix**: Use a personal access token with higher limits

## 📚 Next Steps

1. ✅ Test with the demo backend logs
2. ✅ Try uploading your own application logs
3. ✅ Add more runbooks to the `runbooks/` directory
4. ✅ Customize agent prompts in `agents/` files
5. ✅ Build a frontend UI for easier interaction

## 🎯 Key Files to Understand

- `agent/orchestrator.py` - Coordinates the 4-agent pipeline
- `agent/llm.py` - LLM wrapper for Claude
- `agent/agents/synthesizer_agent.py` - Main RCA logic
- `backend/app.py` - Demo service with intentional errors

Happy debugging! 🚀
