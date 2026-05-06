"""
MVP3 - Error Ingestion Schemas
Defines structured payload schemas for automated error ingestion.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ErrorPayload(BaseModel):
    """
    Structured error payload sent from backend services.
    This is the core schema for MVP3 automated error ingestion.
    """
    service: str = Field(..., description="Service name (e.g., 'checkout-api', 'payment-service')")
    error: str = Field(..., description="Error message")
    stacktrace: str = Field(default="", description="Full stack trace")
    recent_logs: Optional[str] = Field(default=None, description="Last N log lines before error")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="ISO timestamp")
    env: str = Field(default="local", description="Environment (local, staging, production)")
    
    # Optional metadata for enhanced analysis
    request_id: Optional[str] = Field(default=None, description="Unique request ID for tracing")
    user_id: Optional[str] = Field(default=None, description="User ID if available")
    endpoint: Optional[str] = Field(default=None, description="API endpoint that failed")
    method: Optional[str] = Field(default=None, description="HTTP method (GET, POST, etc.)")
    extra: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")

    class Config:
        json_schema_extra = {
            "example": {
                "service": "checkout-api",
                "error": "KeyError: 'user_id'",
                "stacktrace": "Traceback (most recent call last):\n  File \"app.py\", line 42...",
                "recent_logs": "2024-12-22 10:00:01 INFO: Checkout initiated\n2024-12-22 10:00:02 ERROR: KeyError",
                "timestamp": "2024-12-22T10:00:02.123456",
                "env": "local",
                "endpoint": "/checkout",
                "method": "POST"
            }
        }


class ErrorPayloadMinimal(BaseModel):
    """
    Minimal error payload with only required fields.
    Useful for simpler integrations.
    """
    service: str
    error: str
    stacktrace: str = ""


class IngestResponse(BaseModel):
    """Response from the /ingest-error endpoint."""
    status: str = Field(default="received", description="Status of ingestion")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracking")
    rca_report: Optional[Dict[str, Any]] = Field(default=None, description="Root cause analysis report")
    processing_time_ms: Optional[float] = Field(default=None, description="Processing time in milliseconds")
