from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
import uuid
from orchestrator import RCAOrchestrator
from schemas import ErrorPayload, IngestResponse
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Agentic RCA System",
    version="3.0.0",
    description="MVP3 - Automated Error Ingestion & Root Cause Analysis"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = RCAOrchestrator()


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "mode": "automated_ingestion",
        "agents": ["log", "commit", "runbook", "synthesizer"],
        "endpoints": {
            "ingest": "POST /ingest-error (automated)",
            "analyze": "POST /analyze (manual upload)"
        }
    }


# ============================================================
# MVP3: AUTOMATED ERROR INGESTION ENDPOINT
# ============================================================
@app.post("/ingest-error", response_model=IngestResponse)
async def ingest_error(payload: ErrorPayload):
    """
    🚀 MVP3 Automated Error Ingestion
    
    Receives structured error payloads from backend services.
    Automatically triggers the RCA pipeline without manual uploads.
    
    This endpoint is designed to be called by:
    - Global error middleware in FastAPI/Flask backends
    - Exception handlers in microservices
    - Error capture SDKs
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
            repo=settings.DEFAULT_REPO,  # Use default repo from settings
            log_text=log_text,
            metadata={
                "error_message": payload.error,
                "timestamp": payload.timestamp,
                "environment": payload.env,
                "endpoint": payload.endpoint,
                "method": payload.method,
                "user_id": payload.user_id,
                "request_id": request_id,
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
    """
    parts = []
    
    # Add error header
    parts.append(f"=== ERROR CAPTURED AT {payload.timestamp} ===")
    parts.append(f"Service: {payload.service}")
    parts.append(f"Environment: {payload.env}")
    
    if payload.endpoint:
        parts.append(f"Endpoint: {payload.method or 'UNKNOWN'} {payload.endpoint}")
    
    parts.append(f"\n=== ERROR MESSAGE ===")
    parts.append(payload.error)
    
    # Add stacktrace if available
    if payload.stacktrace:
        parts.append(f"\n=== STACK TRACE ===")
        parts.append(payload.stacktrace)
    
    # Add recent logs if available
    if payload.recent_logs:
        parts.append(f"\n=== RECENT LOGS ===")
        parts.append(payload.recent_logs)
    
    parts.append("\n=== END OF ERROR CAPTURE ===")
    
    return "\n".join(parts)


# ============================================================
# MVP2: MANUAL UPLOAD ENDPOINT (BACKWARD COMPATIBLE)
# ============================================================
@app.post("/analyze")
async def analyze(
    service: str = Form(...),
    repo: str = Form(...),
    log_file: UploadFile = File(...)
):
    """
    Manual log file upload for RCA (MVP2 compatibility).
    Use /ingest-error for automated ingestion.
    """
    try:
        if not log_file.filename.endswith('.log'):
            raise HTTPException(status_code=400, detail="Only .log files accepted")
        
        log_content = await log_file.read()
        log_text = log_content.decode('utf-8')
        
        logger.info(f"[MANUAL] Analyzing logs for service: {service}, repo: {repo}")
        logger.info(f"[MANUAL] Log size: {len(log_text)} bytes")
        
        result = await orchestrator.analyze(
            service=service,
            repo=repo,
            log_text=log_text
        )
        
        return result
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Log file must be UTF-8 encoded")
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
