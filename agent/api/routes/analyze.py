"""
Manual Analysis Routes (MVP2 Compatibility)

Handles manual log file uploads for RCA analysis.
Maintained for backward compatibility with MVP2 workflow.
"""

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
import logging

from orchestrator import RCAOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()

# Orchestrator instance
orchestrator = RCAOrchestrator()


@router.post("/analyze")
async def analyze_logs(
    service: str = Form(..., description="Name of the service that generated the logs"),
    repo: str = Form(..., description="GitHub repository (owner/repo)"),
    log_file: UploadFile = File(..., description="Log file to analyze (.log format)")
):
    """
    Manual Log File Upload for RCA (MVP2 Compatibility).
    
    Use this endpoint when you want to manually upload log files for analysis.
    For automated error ingestion, use POST /ingest-error instead.
    
    Args:
        service: Name of the service (e.g., "checkout-api")
        repo: GitHub repository for commit analysis (e.g., "owner/repo")
        log_file: The .log file to analyze
        
    Returns:
        dict: RCA analysis results including root cause, confidence, and recommendations.
        
    Raises:
        HTTPException: 400 for invalid file format, 500 for analysis failures.
    """
    try:
        # Validate file type
        if not log_file.filename.endswith('.log'):
            raise HTTPException(
                status_code=400, 
                detail="Only .log files accepted. Please upload a valid log file."
            )
        
        # Read and decode file content
        log_content = await log_file.read()
        log_text = log_content.decode('utf-8')
        
        logger.info(f"[MANUAL] Analyzing logs for service: {service}, repo: {repo}")
        logger.info(f"[MANUAL] Log size: {len(log_text)} bytes, {len(log_text.splitlines())} lines")
        
        # Run RCA pipeline
        result = await orchestrator.analyze(
            service=service,
            repo=repo,
            log_text=log_text
        )
        
        return result
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400, 
            detail="Log file must be UTF-8 encoded. Please check the file encoding."
        )
    except Exception as e:
        logger.exception("Manual analysis failed")
        raise HTTPException(
            status_code=500, 
            detail=f"Analysis failed: {str(e)}"
        )
