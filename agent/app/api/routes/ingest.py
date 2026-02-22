"""
Error Ingestion Routes (MVP3 + MVP4 Deployment Protection)

Handles automated error ingestion from backend services.
This is the core MVP3 feature that enables automatic RCA triggering.
MVP4 adds deployment protection with GitHub Actions integration.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import time
import uuid
from datetime import datetime, timedelta

from app.models.error_models import ErrorPayload, IngestResponse, DeploymentPayload, DeploymentResponse, AgentLogPayload, AgentLogResponse
from app.core.orchestrator import RCAOrchestrator
from app.core.config.settings import settings
from app.utils.github_api import GitHubClient
from app.api.middleware.auth import GitHubWebhookAuth

logger = logging.getLogger(__name__)
router = APIRouter()

# Orchestrator instance
orchestrator = RCAOrchestrator()
github_client = GitHubClient()

# In-memory storage for RCA reports (for dashboard display)
RCA_HISTORY: List[Dict[str, Any]] = []
MAX_HISTORY_SIZE = 50

# =============================================================================
# Deployment Watcher (MVP4)
# =============================================================================

class DeploymentWatcher:
    """
    Tracks active deployments and correlates errors with recent code pushes.
    
    When GitHub Actions notifies us of a push, we enter "watch mode" for
    that commit. Any errors that occur during watch mode are automatically
    correlated with the deployment.
    """
    
    def __init__(self, watch_duration_minutes: int = 5):
        self.active_deployments: Dict[str, Dict[str, Any]] = {}
        self.watch_duration = timedelta(minutes=watch_duration_minutes)
        self.deployment_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def register_deployment(self, payload: DeploymentPayload) -> str:
        """Register a new deployment and enter watch mode."""
        deployment_id = f"deploy-{str(uuid.uuid4())[:8]}"
        now = datetime.utcnow()
        watch_until = now + self.watch_duration
        
        deployment_record = {
            "deployment_id": deployment_id,
            "commit_sha": payload.commit_sha,
            "repository": payload.repository,
            "author": payload.author,
            "message": payload.message,
            "branch": payload.branch,
            "registered_at": now.isoformat(),
            "watch_until": watch_until.isoformat(),
            "errors_during_watch": []
        }
        
        self.active_deployments[deployment_id] = deployment_record
        
        # Also store in history
        self.deployment_history.insert(0, deployment_record.copy())
        if len(self.deployment_history) > self.max_history:
            self.deployment_history.pop()
        
        logger.info(f"[DEPLOY] Registered deployment {deployment_id} for commit {payload.commit_sha[:7]}")
        logger.info(f"[DEPLOY] Watch mode active until {watch_until.isoformat()}")
        
        return deployment_id
    
    def get_active_deployment(self) -> Optional[Dict[str, Any]]:
        """Get the currently active deployment (if in watch mode)."""
        now = datetime.utcnow()
        
        # Clean up expired deployments
        expired = []
        for dep_id, dep in self.active_deployments.items():
            watch_until = datetime.fromisoformat(dep["watch_until"])
            if now > watch_until:
                expired.append(dep_id)
        
        for dep_id in expired:
            logger.info(f"[DEPLOY] Watch mode expired for {dep_id}")
            del self.active_deployments[dep_id]
        
        # Return the most recent active deployment
        if self.active_deployments:
            most_recent = max(
                self.active_deployments.values(),
                key=lambda x: x["registered_at"]
            )
            return most_recent
        
        return None
    
    def record_error_during_watch(self, deployment_id: str, error_details: Dict[str, Any]):
        """Record that an error occurred during deployment watch."""
        if deployment_id in self.active_deployments:
            self.active_deployments[deployment_id]["errors_during_watch"].append(error_details)
            logger.warning(f"[DEPLOY] Error recorded for deployment {deployment_id}")

# Global watcher instance
deployment_watcher = DeploymentWatcher(watch_duration_minutes=5)

@router.post("/ingest-error", response_model=IngestResponse)
async def ingest_error(payload: ErrorPayload):
    """
    MVP3 Automated Error Ingestion Endpoint.
    
    Receives structured error payloads from backend services and
    automatically triggers the RCA pipeline without manual uploads.
    
    This endpoint is designed to be called by:
    - Global error middleware in FastAPI/Flask backends
    - Exception handlers in microservices
    - Error capture SDKs
    
    Args:
        payload: ErrorPayload containing error details, stacktrace, and context.
        
    Returns:
        IngestResponse: Status, request_id, RCA report, and processing time.
    """
    start_time = time.time()
    request_id = payload.request_id or str(uuid.uuid4())[:8]
    
    logger.info(f"[{request_id}] [ALERT] Error ingested from service: {payload.service}")
    logger.info(f"[{request_id}] Error: {payload.error}")
    logger.info(f"[{request_id}] Environment: {payload.env}")
    
    # MVP4: Check if we're in deployment watch mode
    active_deployment = deployment_watcher.get_active_deployment()
    deployment_context = None
    
    if active_deployment:
        logger.warning(f"[{request_id}] [DEPLOY-ALERT] Error during active deployment!")
        logger.warning(f"[{request_id}] Suspect commit: {active_deployment['commit_sha'][:7]} by {active_deployment['author']}")
        
        # Fetch the commit diff for correlation
        commit_diff = await github_client.fetch_commit_diff(
            repo=active_deployment['repository'],
            commit_sha=active_deployment['commit_sha']
        )
        
        deployment_context = {
            "is_deployment_related": True,
            "deployment_id": active_deployment['deployment_id'],
            "suspect_commit": {
                "sha": active_deployment['commit_sha'][:7],
                "full_sha": active_deployment['commit_sha'],
                "author": active_deployment['author'],
                "message": active_deployment['message'],
                "branch": active_deployment['branch'],
                "deployed_at": active_deployment['registered_at']
            },
            "files_changed": commit_diff.get('files', []),
            "commit_stats": commit_diff.get('stats', {})
        }
        
        # Record error in deployment watch
        deployment_watcher.record_error_during_watch(
            active_deployment['deployment_id'],
            {"error": payload.error, "request_id": request_id, "timestamp": datetime.utcnow().isoformat()}
        )
    
    try:
        # Prepare log text from stacktrace and/or recent logs
        log_text = _prepare_log_text(payload)
        
        # If deployment context exists, add it to log text for AI analysis
        if deployment_context:
            log_text = _add_deployment_context_to_logs(log_text, deployment_context)
        
        logger.info(f"[{request_id}] Starting automated RCA pipeline...")
        
        # Build metadata with deployment context
        metadata = {
            "ingestion_mode": "automated",
            "error_timestamp": payload.timestamp,
            "environment": payload.env,
            "request_id": request_id,
            "endpoint": payload.endpoint,
            "method": payload.method,
            "user_id": payload.user_id,
            "extra": payload.extra
        }
        
        # MVP4: Include deployment context in metadata
        if deployment_context:
            metadata["deployment_context"] = deployment_context
        
        # Run the orchestrator with metadata
        result = await orchestrator.analyze(
            service=payload.service,
            repo=active_deployment['repository'] if active_deployment else settings.DEFAULT_REPO,
            log_text=log_text,
            metadata=metadata
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        # Determine status based on deployment context
        if deployment_context:
            status = "deployment_regression"
            logger.warning(f"[{request_id}] [DEPLOY-RCA] Deployment regression detected in {processing_time:.2f}ms")
        else:
            status = "analyzed"
            logger.info(f"[{request_id}] [OK] RCA completed in {processing_time:.2f}ms")
        
        # Store in history for dashboard display
        rca_record = {
            "id": request_id,
            "service": payload.service,
            "error": payload.error,
            "endpoint": payload.endpoint,
            "environment": payload.env,
            "analyzed_at": datetime.utcnow().isoformat(),
            "processing_time_ms": round(processing_time, 2),
            "rca_report": result,
            "is_deployment_related": deployment_context is not None,
            "deployment_context": deployment_context
        }
        RCA_HISTORY.insert(0, rca_record)
        
        # Trim history if too large
        if len(RCA_HISTORY) > MAX_HISTORY_SIZE:
            RCA_HISTORY.pop()
        
        return IngestResponse(
            status=status,
            request_id=request_id,
            rca_report=result,
            processing_time_ms=round(processing_time, 2)
        )
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        logger.exception(f"[{request_id}] [ERROR] RCA pipeline failed")
        
        return IngestResponse(
            status="error",
            request_id=request_id,
            rca_report={"error": str(e), "service": payload.service},
            processing_time_ms=round(processing_time, 2)
        )


def _prepare_log_text(payload: ErrorPayload) -> str:
    """
    Prepare log text for analysis from the error payload.
    
    Combines stacktrace and recent logs for comprehensive analysis.
    
    Args:
        payload: The error payload containing logs and stacktrace.
        
    Returns:
        str: Combined log text for analysis.
    """
    parts = []
    
    # Add error header
    parts.append(f"=== ERROR: {payload.error} ===")
    parts.append(f"Service: {payload.service}")
    parts.append(f"Environment: {payload.env}")
    parts.append(f"Timestamp: {payload.timestamp}")
    
    if payload.endpoint:
        parts.append(f"Endpoint: {payload.method} {payload.endpoint}")
    
    parts.append("")
    
    # Add stacktrace
    if payload.stacktrace:
        parts.append("=== STACKTRACE ===")
        parts.append(payload.stacktrace)
        parts.append("")
    
    # Add recent logs
    if payload.recent_logs:
        parts.append("=== RECENT LOGS ===")
        parts.extend(payload.recent_logs)
    
    return "\n".join(parts)


def _add_deployment_context_to_logs(log_text: str, deployment_context: Dict[str, Any]) -> str:
    """
    Add deployment context to log text for AI analysis.
    
    This helps the AI understand that the error occurred during a deployment
    and provides the specific code changes to analyze.
    """
    parts = [
        "\n\n=== DEPLOYMENT CONTEXT (ERROR DURING ACTIVE DEPLOYMENT) ===",
        f"⚠️ THIS ERROR OCCURRED WITHIN 5 MINUTES OF A CODE DEPLOYMENT",
        f"\nSUSPECT COMMIT: {deployment_context['suspect_commit']['sha']}",
        f"Author: {deployment_context['suspect_commit']['author']}",
        f"Message: {deployment_context['suspect_commit']['message']}",
        f"Branch: {deployment_context['suspect_commit']['branch']}",
        f"Deployed at: {deployment_context['suspect_commit']['deployed_at']}",
        "\n--- FILES CHANGED IN THIS COMMIT ---"
    ]
    
    for file_info in deployment_context.get('files_changed', []):
        parts.append(f"\nFile: {file_info.get('filename')} ({file_info.get('status')})")
        parts.append(f"  +{file_info.get('additions', 0)} -{file_info.get('deletions', 0)} lines")
        if file_info.get('patch'):
            parts.append(f"  Patch Preview:\n{file_info.get('patch')[:500]}")
    
    parts.append("\n=== END DEPLOYMENT CONTEXT ===")
    
    return log_text + "\n".join(parts)


# =============================================================================
# Deployment Notification Routes (MVP4)
# =============================================================================

@router.post("/notify-deployment", response_model=DeploymentResponse, dependencies=[GitHubWebhookAuth])
async def notify_deployment(request: Request):
    """
    MVP4 Deployment Notification Endpoint.
    
    Called natively by GitHub Webhooks when code is pushed. Puts OpsTron into
    "Deployment Watch Mode" for the next 5 minutes.
    """
    payload_dict = await request.json()
    
    # Check if this is a ping event
    if "zen" in payload_dict:
        logger.info("[DEPLOY] Received GitHub ping event. Webhook is working!")
        return DeploymentResponse(
            status="ping_received",
            deployment_id="ping",
            commit_sha="ping",
            watch_until="",
            message="OpsTron webhook ping received successfully."
        )

    # Parse standard GitHub Push Event
    try:
        repo_full_name = payload_dict.get("repository", {}).get("full_name", "unknown/repo")
        ref = payload_dict.get("ref", "")
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref

        logger.info(f"[DEPLOY] Push event for repo={repo_full_name} ref={ref}")
        logger.debug(f"[DEPLOY] Raw payload keys: {list(payload_dict.keys())}")

        # `head_commit` can be null for empty pushes — fall back to last commit in list
        head_commit = payload_dict.get("head_commit")
        if not head_commit:
            commits = payload_dict.get("commits", [])
            if commits:
                head_commit = commits[-1]
                logger.warning(f"[DEPLOY] head_commit was null, falling back to commits[-1]")
            else:
                # Last resort: use `after` SHA if available
                after_sha = payload_dict.get("after", "")
                if after_sha and after_sha != "0000000000000000000000000000000000000000":
                    head_commit = {
                        "id": after_sha,
                        "author": {"name": payload_dict.get("pusher", {}).get("name", "unknown")},
                        "message": "Deployment push"
                    }
                    logger.warning(f"[DEPLOY] No commits in payload, using 'after' SHA: {after_sha[:7]}")
                else:
                    raise ValueError("No head_commit, no commits, and no valid 'after' SHA found in push event.")

        commit_sha = head_commit.get("id")
        author = head_commit.get("author", {}).get("username") or head_commit.get("author", {}).get("name", "unknown")
        message = head_commit.get("message", "")

    except Exception as e:
        logger.error(f"[DEPLOY] Failed to parse GitHub webhook payload: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid GitHub push payload: {e}")

    logger.info(f"[DEPLOY] Received deployment notification for {repo_full_name}")
    logger.info(f"[DEPLOY] Commit: {commit_sha[:7]} by {author}")
    
    # Construct our internal payload model
    parsed_payload = DeploymentPayload(
        commit_sha=commit_sha,
        repository=repo_full_name,
        author=author,
        message=message,
        branch=branch
    )
    
    # Register the deployment
    deployment_id = deployment_watcher.register_deployment(parsed_payload)
    active = deployment_watcher.get_active_deployment()
    
    return DeploymentResponse(
        status="watching",
        deployment_id=deployment_id,
        commit_sha=parsed_payload.commit_sha,
        watch_until=active["watch_until"] if active else "",
        message=f"OpsTron is now watching for errors related to commit {parsed_payload.commit_sha[:7]}. Watch mode active for 5 minutes."
    )


@router.get("/deployment-status")
async def get_deployment_status():
    """
    Get current deployment watch status.
    
    Returns whether OpsTron is currently in watch mode and details
    about the active deployment being monitored.
    """
    active = deployment_watcher.get_active_deployment()
    
    if active:
        return {
            "status": "watching",
            "active_deployment": {
                "deployment_id": active["deployment_id"],
                "commit_sha": active["commit_sha"][:7],
                "author": active["author"],
                "message": active["message"],
                "registered_at": active["registered_at"],
                "watch_until": active["watch_until"],
                "errors_detected": len(active["errors_during_watch"])
            }
        }
    else:
        return {
            "status": "idle",
            "message": "No active deployment watch. Waiting for GitHub notification."
        }


@router.get("/deployment-history")
async def get_deployment_history(limit: int = 20):
    """
    Get deployment history with error correlation data.
    
    Shows recent deployments and any errors that occurred during
    their watch periods.
    """
    return {
        "total": len(deployment_watcher.deployment_history),
        "deployments": deployment_watcher.deployment_history[:limit]
    }


@router.get("/rca-history")
async def get_rca_history(limit: int = 20):
    """
    Get RCA history for dashboard display.
    
    Returns the most recent RCA reports that have been generated
    from error ingestion.
    
    Args:
        limit: Maximum number of reports to return (default 20).
        
    Returns:
        List of RCA reports with metadata.
    """
    return {
        "total": len(RCA_HISTORY),
        "reports": RCA_HISTORY[:limit]
    }


# =============================================================================
# Inbound Docker Agent Log Receiver
# =============================================================================

@router.post("/agent/logs/ingest", response_model=AgentLogResponse)
async def ingest_agent_logs(payload: AgentLogPayload):
    """
    Endpoint for the lightweight OpsTron Docker Agent.
    
    Instead of polling user environments via dangerous socket access,
    the remote agent securely POSTs streams of logs here.
    """
    start_time = time.time()
    
    logger.info(f"[DOCKER_AGENT] Received block from {payload.container_name} ({payload.container_id[:8]})")
    
    # Check if we should feed this into RCA
    # If the user is in an active deployment watch, we check logs for errors
    active_deployment = deployment_watcher.get_active_deployment()
    
    if active_deployment:
        logger.info(f"[DOCKER_AGENT] Active deployment watch found. Analyzing {payload.container_name} logs.")
        
        # Simple pre-filter: only process if there's actually an error keyword
        # In a real system, you'd use a more sophisticated heuristic or let the LLM decide
        if "error" in payload.logs.lower() or "exception" in payload.logs.lower() or "traceback" in payload.logs.lower():
            logger.warning(f"[DOCKER_AGENT] Potential error found in logs for {payload.container_name}. Triggering RCA.")
            
            simulated_payload = ErrorPayload(
                service=payload.container_name,
                error=f"Uncaught issue detected in deployment watch for {payload.container_name}",
                stacktrace="",
                recent_logs=payload.logs.splitlines(),
                env="production"
            )
            
            try:
                # Await directly so we can catch exceptions if the pipeline fails
                result = await ingest_error(simulated_payload)
                logger.info(f"[DOCKER_AGENT] RCA Pipeline completed with status: {result.status}")
            except Exception as e:
                logger.error(f"[DOCKER_AGENT] Failed to trigger RCA pipeline: {e}")
        else:
            logger.debug(f"[DOCKER_AGENT] Logs from {payload.container_name} appear healthy. Skipping RCA.")

    processing_time = (time.time() - start_time) * 1000
    
    return AgentLogResponse(status="received", message=f"Processed chunk for {payload.container_id}")
