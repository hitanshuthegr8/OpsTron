"""
MVP3 Demo Backend Service
Demonstrates automated error ingestion to the RCA Agent.

Features:
- Global error capture middleware
- Log buffering (last 200 lines)
- Structured logging with context
- Automatic error reporting to agent
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import sys
import os
import traceback
import httpx
import uuid
import asyncio
from datetime import datetime
from collections import deque
from contextlib import asynccontextmanager

# ============================================================
# CONFIGURATION
# ============================================================
AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8001")
SERVICE_NAME = os.getenv("SERVICE_NAME", "checkout-api")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
LOG_BUFFER_SIZE = 200


# ============================================================
# LOG BUFFERING SYSTEM (MVP3 Feature)
# ============================================================
class LogBuffer:
    """Thread-safe circular buffer for recent logs."""
    
    def __init__(self, maxlen: int = 200):
        self._buffer = deque(maxlen=maxlen)
    
    def add(self, log_line: str):
        timestamp = datetime.utcnow().isoformat()
        self._buffer.append(f"[{timestamp}] {log_line}")
    
    def get_recent(self, count: int = 200) -> str:
        """Get the last N log lines as a single string."""
        logs = list(self._buffer)[-count:]
        return "\n".join(logs)
    
    def clear(self):
        self._buffer.clear()


# Global log buffer instance
log_buffer = LogBuffer(maxlen=LOG_BUFFER_SIZE)


# ============================================================
# STRUCTURED LOGGING HANDLER (MVP3 Feature)
# ============================================================
class BufferedLogHandler(logging.Handler):
    """Custom handler that captures logs to the buffer."""
    
    def emit(self, record):
        try:
            msg = self.format(record)
            log_buffer.add(msg)
        except Exception:
            self.handleError(record)


# Setup logging with buffering
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('backend.log'),
        BufferedLogHandler()  # MVP3: Add to buffer
    ]
)

logger = logging.getLogger(__name__)


# ============================================================
# ERROR REPORTER (MVP3 Core Feature)
# ============================================================
class ErrorReporter:
    """Reports errors to the RCA Agent automatically."""
    
    def __init__(self, agent_url: str, service_name: str, environment: str):
        self.agent_url = agent_url
        self.service_name = service_name
        self.environment = environment
        self._client = None
    
    async def _get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def report(
        self,
        error: Exception,
        request: Request = None,
        user_id: str = None,
        extra: dict = None
    ):
        """
        Report an error to the RCA Agent.
        This is called automatically by the middleware.
        """
        request_id = str(uuid.uuid4())[:8]
        
        # Build error payload
        payload = {
            "service": self.service_name,
            "error": f"{type(error).__name__}: {str(error)}",
            "stacktrace": traceback.format_exc(),
            "recent_logs": log_buffer.get_recent(200),
            "timestamp": datetime.utcnow().isoformat(),
            "env": self.environment,
            "request_id": request_id,
            "user_id": user_id,
            "extra": extra or {}
        }
        
        # Add request context if available
        if request:
            payload["endpoint"] = str(request.url.path)
            payload["method"] = request.method
            
            # Try to extract user_id from request if not provided
            if not user_id:
                # Could be from headers, auth token, etc.
                payload["user_id"] = request.headers.get("X-User-ID")
        
        logger.info(f"[{request_id}] [SEND] Sending error to agent: {self.agent_url}/ingest-error")
        logger.debug(f"[{request_id}] Payload: {payload}")
        
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.agent_url}/ingest-error",
                json=payload,
                timeout=5.0
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"[{request_id}] [OK] Agent RCA completed: {result.get('status')}")
                return result
            else:
                logger.warning(f"[{request_id}] [WARN] Agent returned status {response.status_code}")
                return None
                
        except httpx.ConnectError:
            logger.warning(f"[{request_id}] [WARN] Could not connect to agent at {self.agent_url}")
            logger.warning("Make sure the agent is running on port 8001")
            return None
        except Exception as e:
            logger.error(f"[{request_id}] [ERROR] Failed to report error: {str(e)}")
            return None


# Global error reporter instance
error_reporter = ErrorReporter(
    agent_url=AGENT_URL,
    service_name=SERVICE_NAME,
    environment=ENVIRONMENT
)


# ============================================================
# FASTAPI APP SETUP
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle."""
    logger.info(f"[STARTUP] {SERVICE_NAME} starting up...")
    logger.info(f"Agent URL: {AGENT_URL}")
    logger.info(f"Environment: {ENVIRONMENT}")
    yield
    await error_reporter.close()
    logger.info(f"[SHUTDOWN] {SERVICE_NAME} shutting down...")


app = FastAPI(
    title="Demo Backend Service (MVP3)",
    version="3.0.0",
    description="Demonstrates automated error ingestion to RCA Agent",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# GLOBAL ERROR CAPTURE MIDDLEWARE (MVP3 Core Feature)
# ============================================================
@app.middleware("http")
async def error_capture_middleware(request: Request, call_next):
    """
    Global error capture middleware.
    Catches ALL unhandled exceptions and reports them to the agent.
    
    This is the heart of MVP3 - no manual error handling needed!
    """
    request_id = str(uuid.uuid4())[:8]
    
    # Log request start
    logger.info(f"[{request_id}] [IN] {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        
        # Log successful response
        logger.info(f"[{request_id}] [OUT] Response: {response.status_code}")
        return response
        
    except Exception as e:
        # Log the error
        logger.error(f"[{request_id}] [ALERT] Unhandled error: {type(e).__name__}: {str(e)}")
        
        # Report to agent (fire and forget - don't block the response)
        asyncio.create_task(
            error_reporter.report(error=e, request=request)
        )
        
        # Re-raise to let FastAPI handle the response
        raise


# ============================================================
# REQUEST MODELS
# ============================================================
class CheckoutRequest(BaseModel):
    user_id: str
    cart_items: list[str]
    payment_method: str


class PaymentRequest(BaseModel):
    order_id: str
    amount: float
    currency: str = "USD"


# ============================================================
# API ENDPOINTS
# ============================================================
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": "3.0.0",
        "mode": "mvp3_auto_ingestion",
        "agent_url": AGENT_URL,
        "environment": ENVIRONMENT,
        "log_buffer_size": len(log_buffer._buffer),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/logs")
async def get_recent_logs(count: int = 50):
    """Debug endpoint to view recent logs."""
    return {
        "logs": log_buffer.get_recent(count),
        "buffer_size": len(log_buffer._buffer)
    }


@app.post("/checkout")
async def checkout(request: CheckoutRequest):
    """
    Demo checkout endpoint with intentional failures.
    Errors are automatically captured by the middleware!
    """
    logger.info(f"Checkout initiated for user {request.user_id}")
    logger.info(f"Cart items: {request.cart_items}")
    logger.info(f"Payment method: {request.payment_method}")
    
    # Simulate some processing logs
    logger.info("Validating cart items...")
    logger.info("Checking inventory levels...")
    logger.info("Connecting to payment service...")
    
    # Intentional failure scenarios (for demo)
    import random
    failure_type = random.choice(['timeout', 'deadlock', 'null_pointer', 'success'])
    
    if failure_type == 'timeout':
        logger.error("Payment service connection timeout after 30s")
        logger.error("Stack trace: PaymentServiceException at line 42")
        raise HTTPException(status_code=504, detail="Payment service timeout")
    
    elif failure_type == 'deadlock':
        logger.error("Database deadlock detected")
        logger.error("ERROR: Deadlock found when trying to get lock; try restarting transaction")
        logger.error("Query: UPDATE orders SET status='completed' WHERE order_id=12345")
        raise HTTPException(status_code=500, detail="Database deadlock")
    
    elif failure_type == 'null_pointer':
        # This will be caught by the middleware as an unhandled exception
        logger.error("NullPointerException: Cannot read property 'amount' of null")
        raise KeyError("amount")  # Simulates a real unhandled error
    
    else:
        logger.info("Payment processed successfully")
        logger.info("Order created with ID: ORD-12345")
        return {
            "status": "success",
            "order_id": f"ORD-{uuid.uuid4().hex[:8].upper()}",
            "message": "Checkout completed successfully"
        }


@app.post("/payment/process")
async def process_payment(request: PaymentRequest):
    """Another demo endpoint with potential failures."""
    logger.info(f"Processing payment for order {request.order_id}")
    logger.info(f"Amount: {request.amount} {request.currency}")
    
    # Simulate various errors
    import random
    if random.random() < 0.5:
        logger.error("Payment gateway returned error code 503")
        logger.error("Retry attempt 1 of 3 failed")
        logger.error("Retry attempt 2 of 3 failed")
        raise HTTPException(status_code=503, detail="Payment gateway unavailable")
    
    return {
        "status": "approved",
        "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
        "amount": request.amount
    }


@app.get("/trigger-error")
async def trigger_error():
    """
    Debug endpoint to manually trigger an error.
    Useful for testing the error ingestion pipeline.
    """
    logger.info("Manual error trigger requested")
    logger.info("This is a test log line before the error")
    logger.warning("Something seems wrong...")
    logger.error("About to raise an intentional error!")
    
    # This unhandled exception will be caught by the middleware
    raise ValueError("This is a test error for MVP3 demonstration")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

