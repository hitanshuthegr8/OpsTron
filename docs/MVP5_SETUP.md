# OpsTron MVP5 - Setup Guide

## 🎯 What We've Implemented

### Phase 1: Foundation ✅
- [x] Supabase client integration (`db/supabase_client.py`)
- [x] Database schema (`db/schema.sql`)
- [x] JWT Authentication middleware (`api/middleware/auth.py`)
- [x] Auth routes - register, login, logout, profile (`api/routes/auth.py`)
- [x] Updated settings for new environment variables

---

## 🚀 Setup Steps

### Step 1: Update Your .env File

Copy your Supabase keys to your `.env` file:

```bash
cd agent/config
# Edit .env and add:
```

```env
# Supabase (from your dashboard)
SUPABASE_URL=https://xsztdqdtqkmpqczqyzdu.supabase.co
SUPABASE_ANON_KEY=your_publishable_key_here    # Copy full key from Supabase
SUPABASE_SERVICE_KEY=your_secret_key_here       # Copy full key from Supabase

# Service API Key (for GitHub Actions)
SERVICE_API_KEY=OpsTron2024SecureKey123456789   # Any random 32+ char string
```

### Step 2: Create Database Tables

1. Go to **Supabase Dashboard** → **SQL Editor** → **New Query**
2. Copy the contents of `agent/db/schema.sql`
3. Paste and click **Run**
4. You should see "Success" for each table creation

### Step 3: Update GitHub Secret

Add the service API key to GitHub:

1. Go to: https://github.com/hitanshuthegr8/OpsTron/settings/secrets/actions
2. Edit `OPSTRON_URL` or add new secret: `OPSTRON_API_KEY`
3. Value: Same as `SERVICE_API_KEY` in your .env

### Step 4: Update GitHub Action Workflow

Edit `.github/workflows/opstron_notify.yml` to include the API key:

```yaml
- name: Notify OpsTron Agent
  run: |
    curl -X POST "${{ secrets.OPSTRON_URL }}/notify-deployment" \
      -H "Authorization: Bearer ${{ secrets.OPSTRON_API_KEY }}" \
      -H "Content-Type: application/json" \
      -d '{...}'
```

### Step 5: Restart Agent

```bash
cd agent
python main.py
```

---

## 📋 API Endpoints Available

### Authentication (New!)
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/register` | POST | None | Create new user |
| `/auth/login` | POST | None | Login, get JWT |
| `/auth/logout` | POST | JWT | Logout |
| `/auth/me` | GET | JWT | Get current user |
| `/auth/me` | PUT | JWT | Update profile |
| `/auth/refresh` | POST | None | Refresh JWT token |

### Deployment (Existing + Protected)
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/notify-deployment` | POST | API Key | GitHub Actions calls this |
| `/analyze-commit` | POST | API Key | Analyze branch push |
| `/deployment-status` | GET | None | Check watch status |
| `/rca-history` | GET | None | View RCA logs |

---

## 🔜 Next Steps to Implement

### Phase 2: GitHub Integration
- [ ] Split GitHub Actions into 2 workflows
- [ ] Create `/analyze-commit` endpoint
- [ ] Add service auth to deployment routes

### Phase 3: VAPI Integration
- [ ] Create VAPI account
- [ ] Add `/vapi/trigger-call` endpoint
- [ ] Add `/vapi/webhook` for transcripts
- [ ] Auto-call on critical errors

### Phase 4: Chatbot
- [ ] Create `/chat` endpoint
- [ ] Add context retrieval (RCA, commits, transcripts)
- [ ] Chat UI in frontend

---

## 🧪 Test Authentication

```bash
# Register a new user
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123", "full_name": "Test User"}'

# Login
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'

# Use the returned access_token for authenticated requests
curl http://localhost:8001/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 📁 Files Created/Modified

### New Files:
- `agent/db/supabase_client.py` - Supabase client wrapper
- `agent/db/schema.sql` - Database schema (run in Supabase)
- `agent/api/middleware/auth.py` - JWT verification
- `agent/api/middleware/__init__.py` - Middleware package
- `agent/api/routes/auth.py` - Auth endpoints

### Modified Files:
- `agent/config/settings.py` - Added Supabase/VAPI config
- `agent/config/.env.example` - Updated template
- `agent/api/__init__.py` - Added auth router
- `agent/api/routes/__init__.py` - Added auth import
