# 🚀 Exact Commands - Copy & Paste Ready

## Initial Setup (One-Time Only)

### 1️⃣ Setup Backend
```powershell
# Navigate to project
cd c:\Users\HP\Desktop\Secret\Project\mvp2\backend

# Create virtual environment
python -m venv venv

# Activate venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Deactivate for now
deactivate
```

### 2️⃣ Setup Agent
```powershell
# Navigate to agent directory
cd c:\Users\HP\Desktop\Secret\Project\mvp2\agent

# Create virtual environment
python -m venv venv

# Activate venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy config\.env.example config\.env

# ⚠️ IMPORTANT: Edit config\.env and add your API keys:
# GEMINI_API_KEY=AIzaSy...
# GITHUB_TOKEN=ghp_...
```

### 3️⃣ Load Runbooks
```powershell
# Make sure you're in agent directory with venv activated
cd db
python load_runbooks.py
cd ..

# Deactivate for now
deactivate
```

---

## Running the System (Every Time)

### Terminal 1: Backend Service
```powershell
cd c:\Users\HP\Desktop\Secret\Project\mvp2\backend
venv\Scripts\activate
python app.py
```
**Expected Output**: `Uvicorn running on http://0.0.0.0:8000`

---

### Terminal 2: Agent API
```powershell
cd c:\Users\HP\Desktop\Secret\Project\mvp2\agent
venv\Scripts\activate
python main.py
```
**Expected Output**: `Uvicorn running on http://0.0.0.0:8001`

---

## Testing the System

### 🚀 MVP3: Automated Error Ingestion (NEW!)
```powershell
# Trigger a test error - automatically analyzed by agent!
curl http://localhost:8000/trigger-error

# Or trigger checkout errors (random success/failure)
curl -X POST http://localhost:8000/checkout -H "Content-Type: application/json" -d "{\"user_id\": \"user123\", \"cart_items\": [\"item1\"], \"payment_method\": \"credit_card\"}"

# View recent logs buffer
curl http://localhost:8000/logs

# Check agent health (now shows MVP3 mode)
curl http://localhost:8001/health
```

### 📝 MVP2: Manual Log Analysis (Still Works!)
```powershell
cd c:\Users\HP\Desktop\Secret\Project\mvp2

# Generate some error logs first
curl -X POST http://localhost:8000/checkout -H "Content-Type: application/json" -d "{\"user_id\": \"user123\", \"cart_items\": [\"item1\"], \"payment_method\": \"credit_card\"}"

# Manually analyze the log file
curl -X POST http://localhost:8001/analyze -F "service=payment-service" -F "repo=fastapi/fastapi" -F "log_file=@backend/backend.log"
```

### 🔧 Direct Ingest Test (MVP3)
```powershell
# Manually send an error payload to agent
curl -X POST http://localhost:8001/ingest-error -H "Content-Type: application/json" -d "{\"service\": \"test-api\", \"error\": \"KeyError: test\", \"stacktrace\": \"Traceback...\", \"env\": \"local\"}"
```

---

## Quick Commands Reference

| Action | Command |
|--------|---------|
| **Activate backend venv** | `cd backend` → `venv\Scripts\activate` |
| **Activate agent venv** | `cd agent` → `venv\Scripts\activate` |
| **Deactivate venv** | `deactivate` |
| **Check if venv active** | Look for `(venv)` in prompt |
| **Test backend health** | `curl http://localhost:8000/health` |
| **Test agent health** | `curl http://localhost:8001/health` |
| **View backend logs** | `type backend\backend.log` |
| **View log buffer (MVP3)** | `curl http://localhost:8000/logs` |
| **Trigger test error (MVP3)** | `curl http://localhost:8000/trigger-error` |
| **Reload runbooks** | `cd agent\db` → `python load_runbooks.py` |


---

## 🛑 Troubleshooting

**Problem**: `python: command not found`
- **Fix**: Use `py` instead of `python`

**Problem**: `venv\Scripts\activate` doesn't work
- **Fix**: Try `venv\Scripts\Activate.ps1` (PowerShell) or `venv\Scripts\activate.bat` (CMD)

**Problem**: Script execution disabled
- **Fix**: Run PowerShell as Admin and execute:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

**Problem**: Port already in use
- **Fix**: Kill the process:
  ```powershell
  # Find process on port 8000 or 8001
  netstat -ano | findstr :8000
  # Kill it (replace PID with actual process ID)
  taskkill /PID <PID> /F
  ```

**Problem**: Module not found errors
- **Fix**: Make sure venv is activated (you should see `(venv)` in prompt)

---

## 📋 Checklist Before Running

- [ ] Backend venv created and activated
- [ ] Agent venv created and activated
- [ ] Dependencies installed in both venvs
- [ ] `agent/config/.env` file exists with valid API keys
- [ ] Runbooks loaded into ChromaDB
- [ ] Both services running (ports 8000 and 8001)

---

## 🎯 Quick Start (After Initial Setup)

```powershell
# Terminal 1
cd c:\Users\HP\Desktop\Secret\Project\mvp2\backend
venv\Scripts\activate
python app.py

# Terminal 2 (new window)
cd c:\Users\HP\Desktop\Secret\Project\mvp2\agent
venv\Scripts\activate
python main.py

# Done! System is running 🚀
```
