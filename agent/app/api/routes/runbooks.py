"""
Runbook management routes.
"""

import re
import uuid
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


def _write_and_index(*, github_id: str, title: str, content: str, repo: str = "", service: str = "") -> dict:
    RUNBOOK_DIR.mkdir(parents=True, exist_ok=True)
    runbook_id = f"{github_id}-{uuid.uuid4().hex[:10]}"
    filename = f"{_safe_slug(title)}-{runbook_id}.md"
    clean_content = redact_text(content)
    (RUNBOOK_DIR / filename).write_text(clean_content, encoding="utf-8")

    ChromaStore().add_documents([
        {
            "id": runbook_id,
            "filename": filename,
            "title": title,
            "content": clean_content,
            "github_id": github_id,
            "repo": repo,
            "service": service,
        }
    ])

    return {"id": runbook_id, "filename": filename, "title": title, "indexed": True}


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
    result = _write_and_index(
        github_id=user["github_id"],
        title=title,
        content=content,
        repo=repo,
        service=service,
    )
    return {"status": "indexed", "runbook": result}


@router.post("/from-rca")
async def create_runbook_from_rca(payload: RunbookFromRCARequest, user: dict = GitHubAuth):
    actions = "\n".join(f"{idx + 1}. {action}" for idx, action in enumerate(payload.recommended_actions))
    content = f"""# {payload.title}

## Scope
Service: {payload.service or "Any"}
Repository: {payload.repo or "Any"}

## RCA Summary
{payload.rca_summary}

## Root Cause
{payload.root_cause or "Unknown"}

## Remediation
{actions or "1. Investigate the linked RCA and add concrete remediation steps."}
"""
    result = _write_and_index(
        github_id=user["github_id"],
        title=payload.title,
        content=content,
        repo=payload.repo,
        service=payload.service,
    )
    return {"status": "indexed", "runbook": result}
