# Migration to Google Gemini API

## ✅ Changes Made

The system has been updated to use **Google Gemini 2.0 Flash** instead of Anthropic Claude.

### Files Modified

1. **`agent/llm.py`**
   - Changed from `ChatAnthropic` to `ChatGoogleGenerativeAI`
   - Model: `gemini-2.0-flash-exp`
   - Updated prompt handling (Gemini combines system and user prompts)

2. **`agent/config/settings.py`**
   - Changed `ANTHROPIC_API_KEY` → `GEMINI_API_KEY`

3. **`agent/config/.env.example`**
   - Updated environment variable template

4. **`agent/requirements.txt`**
   - Removed: `langchain-anthropic`, `anthropic`
   - Added: `langchain-google-genai`, `google-generativeai`

5. **Documentation**
   - Updated `README.md` and `QUICKSTART.md`

## 🔑 Getting Your Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click **"Get API Key"** or **"Create API Key"**
4. Copy your API key (starts with `AIzaSy...`)

## 📝 Setup Instructions

### 1. Update Dependencies

```bash
cd agent
pip install -r requirements.txt
```

This will install:
- `langchain-google-genai==0.0.5`
- `google-generativeai==0.3.2`

### 2. Configure Environment Variables

Create or update `agent/config/.env`:

```bash
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
CHROMA_PERSIST_DIR=./db/chroma_data
```

### 3. Test the System

```bash
# Start the agent API
cd agent
python main.py
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

## 🆚 Key Differences: Gemini vs Claude

| Feature | Claude (Anthropic) | Gemini (Google) |
|---------|-------------------|-----------------|
| **Model** | claude-sonnet-4-20250514 | gemini-2.0-flash-exp |
| **API Key Format** | `sk-ant-...` | `AIzaSy...` |
| **System Prompts** | Separate SystemMessage | Combined with user prompt |
| **Speed** | Fast | Very Fast (Flash model) |
| **Cost** | Paid (after free tier) | Free tier available |
| **Context Window** | 200K tokens | 1M tokens |

## 🎯 Why Gemini?

- ✅ **Free Tier**: Generous free quota for development
- ✅ **Fast**: Flash model optimized for speed
- ✅ **Large Context**: 1M token context window
- ✅ **Google Integration**: Easy to get started with Google account
- ✅ **Good Performance**: Excellent for structured output tasks

## 🧪 Testing

Test the LLM integration:

```bash
# Generate some logs
cd backend
python app.py

# In another terminal, make requests
curl -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "cart_items": ["item1"], "payment_method": "card"}'

# Analyze logs
cd ../agent
curl -X POST http://localhost:8001/analyze \
  -F "service=payment-service" \
  -F "repo=fastapi/fastapi" \
  -F "log_file=@../backend/backend.log"
```

## 🔧 Troubleshooting

**Error**: `google.api_core.exceptions.PermissionDenied: 403 API key not valid`
- **Fix**: Verify your Gemini API key is correct in `.env`
- Get a new key from [Google AI Studio](https://makersuite.google.com/app/apikey)

**Error**: `ImportError: cannot import name 'ChatGoogleGenerativeAI'`
- **Fix**: Reinstall dependencies: `pip install -r requirements.txt --upgrade`

**Error**: Rate limit exceeded
- **Fix**: Gemini has generous free limits, but if exceeded, wait or upgrade to paid tier

## 📊 Performance Notes

Gemini 2.0 Flash is optimized for:
- ✅ Fast response times
- ✅ Structured JSON output
- ✅ Long context understanding
- ✅ Cost-effective operations

Perfect for this RCA use case! 🚀

## 🔄 Reverting to Claude (if needed)

If you need to switch back to Claude:

1. Update `agent/requirements.txt`:
   ```
   langchain-anthropic==0.1.0
   anthropic==0.18.0
   ```

2. Update `agent/llm.py` to use `ChatAnthropic`

3. Update `agent/config/settings.py` to use `ANTHROPIC_API_KEY`

4. Reinstall dependencies: `pip install -r requirements.txt`
