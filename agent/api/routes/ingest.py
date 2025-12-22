"""
Error Ingestion Routes (MVP3)

Handles automated error ingestion from backend services.
This is the core MVP3 feature that enables automatic RCA triggering.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import time
import uuid

from schemas import ErrorPayload, IngestResponse
from orchestrator import RCAOrchestrator
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Orchestrator instance
orchestrator = RCAOrchestrator()


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
    
    try:
        # Prepare log text from stacktrace and/or recent logs
        log_text = _prepare_log_text(payload)
        
        logger.info(f"[{request_id}] Starting automated RCA pipeline...")
        
        # Run the orchestrator with metadata
        result = await orchestrator.analyze(
            service=payload.service,
            repo=settings.DEFAULT_REPO,
            log_text=log_text,
            metadata={
                "ingestion_mode": "automated",
                "error_timestamp": payload.timestamp,
                "environment": payload.env,
                "request_id": request_id,
                "endpoint": payload.endpoint,
                "method": payload.method,
                "user_id": payload.user_id,
                "extra": payload.extra
            }
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        logger.info(f"[{request_id}] [OK] RCA completed in {processing_time:.2f}ms")
        
        return IngestResponse(
            status="analyzed",
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
