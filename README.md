<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:4facfe,100:00f2fe&height=200&section=header&text=OpsTron&fontSize=90&fontAlignY=38&desc=Your%20AI-Powered%20DevOps%20Companion&descAlignY=55&descAlign=62" width="100%" />

[![Typing SVG](https://readme-typing-svg.herokuapp.com?font=Fira+Code&weight=600&size=24&pause=1000&color=00F2FE&center=true&vCenter=true&width=600&lines=Catch+deployment+regressions;Automate+Root+Cause+Analysis;Resolve+incidents+with+AI;Ship+code+with+confidence)](https://git.io/typing-svg)

**Supercharge your incident response with LLM-powered telemetry, predictive analysis, and automated runbook matching.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

<br />

## 🌟 Why OpsTron?

Modern microservices are complex, and pinpointing the exact codebase change that caused a production outage can take hours. **OpsTron cuts that time down to seconds.** 

By ingesting real-time application logs, analyzing your latest Git commits, and querying your internal runbooks, OpsTron's orchestrator synthesizes an exact explanation of *what broke*, *why it broke*, and *how to fix it*. 

---

## ✨ Core Features

<table>
  <tr>
    <td width="50%">
      <h3>🛡️ Deployment Protection</h3>
      <p>Seamlessly integrates with GitHub Actions via secure HMAC webhooks. OpsTron automatically enters "Watch Mode" during a deployment to catch immediate regressions.</p>
    </td>
    <td width="50%">
      <h3>🧠 AI Root Cause Analysis</h3>
      <p>Uses state-of-the-art LLMs (Groq/Gemini/Ollama) to parse dense stack traces, abstract syntax trees, and commit diffs to synthesize human-readable solutions.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🐳 Autonomous Log Ingestion</h3>
      <p>Utilize the lightweight <code>opstron_forwarder</code> sidecar to stream isolated Docker container logs directly into the analysis engine with intelligent Regex pre-filtering.</p>
    </td>
    <td width="50%">
      <h3>📞 Critical Voice Alerts</h3>
      <p>When a deployment drops the database, emails aren't enough. OpsTron integrates with Twilio TwiML to physically call on-call engineers for critical regressions.</p>
    </td>
  </tr>
</table>

---

## 🏗️ High-Level Architecture

<div align="center">

```mermaid
graph TD
    %% Styling
    classDef external fill:#1e1e1e,stroke:#333,stroke-width:2px,color:#fff;
    classDef core fill:#00f2fe,stroke:#00a3cc,stroke-width:2px,color:#000;
    classDef agent fill:#4facfe,stroke:#2b8ace,stroke-width:2px,color:#fff;
    classDef db fill:#ff9a9e,stroke:#cc7377,stroke-width:2px,color:#000;

    %% Nodes
    GH([GitHub Actions CI/CD]) ::: external
    APP([Production Docker Apps]) ::: external
    
    API[FastAPI Gateway] ::: core
    ORCH{RCA Orchestrator} ::: core
    
    A1[Log Agent (Regex Pre-filter)] ::: agent
    A2[Commit Agent (Git Diff)] ::: agent
    A3[Runbook Agent (RAG)] ::: agent
    A4[Synthesizer Agent (LLM)] ::: agent
    
    VDB[(ChromaDB)] ::: db
    LLM([Groq / Gemini API]) ::: external
    UI([React Dashboard]) ::: external
    PHONE([Twilio Voice Alert]) ::: external

    %% Edges
    GH -- "HMAC Webhook" --> API
    APP -- "POST /agent/logs" --> API
    
    API --> ORCH
    
    ORCH --> A1
    ORCH --> A2
    ORCH --> A3
    
    A3 <--> VDB
    
    A1 --> A4
    A2 --> A4
    A3 --> A4
    
    A4 <--> LLM
    A4 --> ORCH
    
    ORCH --> UI
    ORCH -- "If Critical" --> PHONE
```

</div>

---

## 🚀 Quickstart Guide

Get OpsTron running locally in under 60 seconds.

### 1. Clone & Install
```bash
git clone https://github.com/hitanshuthegr8/OpsTron.git
cd OpsTron/agent
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
Rename `.env.example` to `.env` and fill in your details. At an absolute minimum, you need an LLM API key.
```env
# Get a free fast key from console.groq.com
GEMINI_API_KEY="your_groq_or_gemini_key"
```

### 3. Launch the Core
```bash
python main.py
```
*OpsTron is now listening on port `8001`.*

---

## 🔒 Securing Your Deployments (GitHub Actions)

To enable Deployment Protection, you need to tell GitHub to securely ping OpsTron when a push happens.

1. Generate a secure secret: `openssl rand -hex 32`
2. Add this secret to your `agent/.env` as `WEBHOOK_SECRET="your_secret"`.
3. In your GitHub Repository, go to **Settings > Secrets and variables > Actions**.
4. Add `OPSTRON_WEBHOOK_SECRET` (the secret from step 1).
5. Add `OPSTRON_BACKEND_URL` (the public URL/ngrok of your `main.py` server).

The included workflow (`.github/workflows/opstron_notify.yml`) will now automatically arm the defense grid on every push!

---

## 🐳 Ingesting Docker Logs

You don't need to expose your Docker daemon. OpsTron uses a secure push-based model.

Run the lightweight forwarder script alongside your production apps:
```bash
# Set environment variables for the target container
export OPSTRON_URL="http://your-opstron-server:8001"
export CONTAINER_NAME="my-crashing-backend"

# Start the forwarder
python agent/opstron_forwarder.py
```
*The forwarder uses lightweight Regex pre-filtering locally so it doesn't saturate your network sending non-error logs.*

---

## 🌐 API Reference

| Method | Endpoint | Description | Security |
|--------|----------|-------------|----------|
| `GET` | `/health` | Core system pulse check | None |
| `POST` | `/analyze-commit` | Manually triage a specific SHA | GitHub Auth |
| `POST` | `/notify-deployment`| CI/CD Webhook Entrypoint | HMAC-SHA256 |
| `POST` | `/agent/logs/ingest`| Outbound agent streaming | Service API Key |
| `GET` | `/auth/github/login`| Entrypoint for user dashboard session | OAuth2 |

---

<div align="center">
  <h3>Built with ❤️ by the OpsTron Team</h3>
  <p>If you like this project, consider giving it a ⭐ on GitHub!</p>
</div>
