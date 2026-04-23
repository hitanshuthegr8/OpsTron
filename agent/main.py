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
from contextlib import asynccontextmanager
import logging
import sys
import os

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

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # --- Startup ---
        logger.info("=" * 60)
        logger.info("OpsTron RCA Agent Starting...")
        logger.info(f"Version: 3.0.0")
        logger.info(f"Docs available at /docs")
        logger.info("=" * 60)
        yield
        # --- Shutdown ---
        logger.info("OpsTron RCA Agent Shutting Down...")

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
        """,
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI):
    """Register all API routes."""
    from app.api import api_router
    app.include_router(api_router)


# Create application instance
app = create_app()


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    import uvicorn

    # Railway injects PORT env var. Fall back to 8001 for local dev.
    port = int(os.environ.get("PORT", 8001))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=(port == 8001),   # reload only in local dev
        log_level="info"
    )
