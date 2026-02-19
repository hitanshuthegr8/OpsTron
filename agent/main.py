"""
OpsTron Agent - Main Application Entry Point

This is the AI-powered Root Cause Analysis (RCA) agent that automatically
analyzes runtime errors and provides actionable insights.

Features:
- Automated error ingestion (MVP3)
- Manual log file upload (MVP2)
- GitHub commit analysis
- Runbook matching
- AI-powered synthesis

Author: OpsTron Team
Version: 3.0.0
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Application Factory.
    
    Creates and configures the FastAPI application with all routes,
    middleware, and event handlers.
    
    Returns:
        FastAPI: Configured application instance.
    """
    
    app = FastAPI(
        title="OpsTron RCA Agent",
        description="""
        ## AI-Powered Root Cause Analysis System
        
        OpsTron automatically analyzes runtime errors and provides actionable insights.
        
        ### Features
        - **Automated Error Ingestion**: Backend services POST errors to `/ingest-error`
        - **Manual Log Upload**: Upload `.log` files to `/analyze`
        - **GitHub Integration**: Analyze recent commits for context
        - **Runbook Matching**: Find relevant runbooks for the error
        - **AI Synthesis**: Generate comprehensive RCA reports
        
        ### Quick Start
        1. Configure GitHub: `POST /config/github`
        2. Trigger an error in your backend
        3. View RCA report in response or dashboard
        """,
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routes
    _register_routes(app)
    
    # Register event handlers
    _register_events(app)
    
    return app


def _register_routes(app: FastAPI):
    """Register all API routes."""
    from app.api import api_router
    app.include_router(api_router)


def _register_events(app: FastAPI):
    """Register startup and shutdown events."""
    
    @app.on_event("startup")
    async def startup_event():
        logger.info("=" * 60)
        logger.info("OpsTron RCA Agent Starting...")
        logger.info("=" * 60)
        logger.info(f"Version: 3.0.0")
        logger.info(f"Docs: http://localhost:8001/docs")
        logger.info("=" * 60)
    
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("OpsTron RCA Agent Shutting Down...")


# Create application instance
app = create_app()


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
