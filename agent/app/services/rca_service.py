"""
RCA Service

Core business logic for Root Cause Analysis.
Provides high-level methods for error analysis.
"""

from typing import Dict, Any, Optional
import logging
from datetime import datetime

from app.core.orchestrator import RCAOrchestrator

logger = logging.getLogger(__name__)


class RCAService:
    """
    Root Cause Analysis Service.
    
    Provides high-level interface for running RCA analysis
    on error payloads or log files.
    """
    
    def __init__(self):
        self.orchestrator = RCAOrchestrator()
        self._analysis_count = 0
    
    async def analyze_error(
        self,
        service: str,
        error: str,
        stacktrace: str = "",
        recent_logs: list = None,
        repo: str = "",
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze an error and generate RCA report.
        
        Args:
            service: Name of the service that errored
            error: Error message or exception type
            stacktrace: Full stacktrace if available
            recent_logs: List of recent log lines for context
            repo: GitHub repository for commit analysis
            metadata: Additional context (env, endpoint, user_id, etc.)
            
        Returns:
            Dict containing RCA report with root cause, confidence, and recommendations.
        """
        self._analysis_count += 1
        
        # Build log text from components
        log_text = self._build_log_text(error, stacktrace, recent_logs)
        
        # Run orchestrator
        result = await self.orchestrator.analyze(
            service=service,
            repo=repo,
            log_text=log_text,
            metadata=metadata
        )
        
        return result
    
    async def analyze_log_file(
        self,
        service: str,
        log_text: str,
        repo: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze a log file and generate RCA report.
        
        Args:
            service: Name of the service
            log_text: Raw log file content
            repo: GitHub repository for commit analysis
            
        Returns:
            Dict containing RCA report.
        """
        self._analysis_count += 1
        
        return await self.orchestrator.analyze(
            service=service,
            repo=repo,
            log_text=log_text
        )
    
    def _build_log_text(
        self,
        error: str,
        stacktrace: str,
        recent_logs: list
    ) -> str:
        """Build formatted log text from error components."""
        parts = [f"ERROR: {error}"]
        
        if stacktrace:
            parts.append("\n--- STACKTRACE ---")
            parts.append(stacktrace)
        
        if recent_logs:
            parts.append("\n--- RECENT LOGS ---")
            parts.extend(recent_logs)
        
        return "\n".join(parts)
    
    @property
    def analysis_count(self) -> int:
        """Get total number of analyses performed."""
        return self._analysis_count


# Singleton instance
rca_service = RCAService()
