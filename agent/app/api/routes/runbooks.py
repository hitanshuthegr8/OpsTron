"""
Runbook management routes.
"""

import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.middleware.auth import GitHubAuth
from app.db.chroma_store.vector_store import ChromaStore
from app.utils.security import redact_text

router = APIRouter(prefix="/runbooks")

RUNBOOK_DIR = Path(__file__).resolve().parents[4] / "runbooks_uploaded"
MAX_RUNBOOK_BYTES = 512_000


class RunbookFromRCARequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    service: str = Field(default="", max_length=120)
    repo: str = Field(default="", max_length=240)
    rca_summary: str = Field(..., min_length=10)
    root_cause: str = ""
    recommended_actions: list[str] = Field(default_factory=list)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "runbook"


def _scope_slug(*, github_id: str, title: str, repo: str = "", service: str = "") -> str:
    scope = service.strip() or repo.strip().replace("/", "-") or title
    return _safe_slug(f"{github_id}-{scope}-ops-runbook")


def _canonical_title(*, title: str, repo: str = "", service: str = "") -> str:
    if service.strip():
        return f"{service.strip()} Operations Runbook"
    if repo.strip():
        return f"{repo.strip()} Operations Runbook"
    return title


def _base_runbook(*, title: str, repo: str = "", service: str = "") -> str:
    scoped_title = _canonical_title(title=title, repo=repo, service=service)
    return f"""# {scoped_title}

## Scope
Service: {service or "Any"}
Repository: {repo or "Any"}

## Detection Signals
- Container exits, restarts, OOM events, or log lines containing errors, exceptions, tracebacks, fatal signals, or panics.
- Deployment correlation is stronger when the incident happens soon after a GitHub push webhook.
- Treat repeated failures within a short window as a likely service incident, not a one-off log line.

## First Response
1. Confirm the affected service/container is still running.
2. Check the most recent OpsTron RCA report for root cause, confidence, and deployment correlation.
3. Inspect the last 100 container log lines around the first error.
4. If the incident followed a deployment, compare the failing code path with the pushed commit.
5. Decide whether to roll back, hotfix, or keep observing based on severity and customer impact.

## Triage Checklist
- Verify the failing endpoint, job, or startup path.
- Identify the first error, not only follow-on stack traces.
- Check environment variables, database connectivity, external API credentials, and network timeouts.
- Look for crash loops, OOM kills, missing files, port binding failures, and dependency import errors.
- Confirm whether the error started after the latest deployment.

## Immediate Mitigation
- Roll back the latest deployment when the error is high severity and clearly deployment-related.
- Restart the service only when the failure is transient and restart is known to be safe.
- Disable the affected feature path if a narrow feature flag or route-level mitigation exists.
- Escalate to the service owner if customer-facing impact continues after mitigation.

## Permanent Fix Guidance
- Add a regression test that reproduces the failing path.
- Add startup validation for required environment variables and external dependencies.
- Improve structured logging around the failing endpoint or background job.
- Update this runbook with the confirmed root cause and fix after the incident.
"""


def _append_section(existing: str, heading: str, body: str) -> str:
    timestamp = datetime.utcnow().isoformat()
    return f"{existing.rstrip()}\n\n## {heading} - {timestamp}\n{body.strip()}\n"


def _write_and_index(
    *,
    github_id: str,
    title: str,
    content: str,
    repo: str = "",
    service: str = "",
    append_heading: str = "",
    base_content: str = "",
) -> dict:
    RUNBOOK_DIR.mkdir(parents=True, exist_ok=True)
    runbook_id = _scope_slug(github_id=github_id, title=title, repo=repo, service=service)
    filename = f"{runbook_id}.md"
    path = RUNBOOK_DIR / filename

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    clean_content = redact_text(content)
    if existing and append_heading:
        final_content = _append_section(existing, append_heading, clean_content)
        updated = True
    elif existing:
        final_content = _append_section(existing, "Runbook Update", clean_content)
        updated = True
    else:
        final_content = redact_text(base_content) if base_content else clean_content
        updated = False

    path.write_text(final_content, encoding="utf-8")

    ChromaStore().add_documents([
        {
            "id": runbook_id,
            "filename": filename,
            "title": _canonical_title(title=title, repo=repo, service=service),
            "content": final_content,
            "github_id": github_id,
            "repo": repo,
            "service": service,
        }
    ])

    return {
        "id": runbook_id,
        "filename": filename,
        "title": _canonical_title(title=title, repo=repo, service=service),
        "indexed": True,
        "updated": updated,
    }


@router.post("/upload")
async def upload_runbook(
    file: UploadFile = File(...),
    repo: str = Form(default=""),
    service: str = Form(default=""),
    user: dict = GitHubAuth,
):
    if not file.filename or not file.filename.endswith((".md", ".txt")):
        raise HTTPException(status_code=400, detail="Upload a .md or .txt runbook")

    raw = await file.read()
    if len(raw) > MAX_RUNBOOK_BYTES:
        raise HTTPException(status_code=413, detail="Runbook file is too large")

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Runbook must be UTF-8 encoded")

    title = Path(file.filename).stem.replace("_", " ").replace("-", " ").title()
    initial_content = f"""{_base_runbook(title=title, repo=repo, service=service)}

## User Supplied Runbook Context
{content}
"""
    result = _write_and_index(
        github_id=user["github_id"],
        title=title,
        content=content,
        repo=repo,
        service=service,
        append_heading="User Supplied Runbook Context",
        base_content=initial_content,
    )
    return {"status": "indexed", "runbook": result}


@router.post("/from-rca")
async def create_runbook_from_rca(payload: RunbookFromRCARequest, user: dict = GitHubAuth):
    actions = "\n".join(f"{idx + 1}. {action}" for idx, action in enumerate(payload.recommended_actions))
    update = f"""### RCA Summary
{payload.rca_summary}

### Root Cause
{payload.root_cause or "Unknown"}

### Remediation
{actions or "1. Investigate the linked RCA and add concrete remediation steps."}
"""
    initial_content = f"{_base_runbook(title=payload.title, repo=payload.repo, service=payload.service)}\n\n## RCA Learning\n{update}"
    result = _write_and_index(
        github_id=user["github_id"],
        title=payload.title,
        content=update,
        repo=payload.repo,
        service=payload.service,
        append_heading=f"RCA Learning: {payload.title}",
        base_content=initial_content,
    )
    return {"status": "indexed", "runbook": result}
