# OpsTron GitHub Actions & Docker Integration Guide

## GitHub Actions Workflow

### What it does
Notifies your OpsTron agent every time code is pushed to your repository.
OpsTron immediately enters "Watch Mode" during a deployment to catch regressions.

### Setup Steps

1. **Generate a webhook secret** (use any long random string, or run):
   ```bash
   openssl rand -hex 32
   ```

2. **Add secrets to your GitHub repo** (Settings → Secrets and variables → Actions):
   | Secret Name | Value |
   |---|---|
   | `OPSTRON_WEBHOOK_SECRET` | The random string from step 1 |
   | `OPSTRON_BACKEND_URL` | `http://your-server:8001/notify-deployment` |

3. **Copy the workflow file** from `docs/opstron.yml` into your repo at `.github/workflows/opstron.yml`

4. Push any code — OpsTron will receive the webhook within seconds.

---

## Docker Log Forwarder

### What it does
The `opstron_forwarder.py` script runs alongside your app containers and streams error logs to OpsTron's AI engine in real-time (push-based, no inbound access needed).

### Quick Start

**Option A: Docker Compose (Recommended)**

Add to your existing `docker-compose.yml`:

```yaml
services:
  # ... your existing services ...

  opstron-forwarder:
    image: python:3.12-slim
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./opstron_forwarder.py:/app/opstron_forwarder.py
    environment:
      OPSTRON_BACKEND_URL: "http://your-opstron-server:8001/agent/logs/ingest"
      OPSTRON_API_KEY: "your_api_key_here"
    command: sh -c "pip install requests docker -q && python /app/opstron_forwarder.py"
    restart: unless-stopped
```

**Option B: Run directly on server**

```bash
# Download the forwarder
curl -O https://raw.githubusercontent.com/hitanshuthegr8/OpsTron/main/agent/opstron_forwarder.py

# Install dependencies
pip install requests docker

# Run it
export OPSTRON_BACKEND_URL="http://your-opstron-server:8001/agent/logs/ingest"
export OPSTRON_API_KEY="your_api_key_here"
python opstron_forwarder.py
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|  
| `OPSTRON_BACKEND_URL` | ✅ | URL of your OpsTron server + `/agent/logs/ingest` |
| `OPSTRON_API_KEY` | ✅ | API key for authentication |
| `OPSTRON_POLL_INTERVAL` | ❌ | How often to poll logs in seconds (default: `5`) |

### Security Notes
- The forwarder is **read-only** — it only reads logs, never modifies containers.
- Mount the Docker socket as **read-only** (`:ro` flag).
- For production, consider using [Tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy).
