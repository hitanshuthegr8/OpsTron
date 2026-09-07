"""
Public demo routes.

Deliberately unauthenticated: the entire point is that a visitor with no GitHub
account, no repository and no API keys can watch the RCA pipeline work.

The safety argument is structural rather than defensive. The only visitor-
supplied value that reaches the pipeline is a scenario id, and that id is used
solely as a key into the fixed `SCENARIOS` mapping. An unknown key is rejected
before anything runs. Consequently no visitor-controlled text ever becomes part
of an LLM prompt, a database write, or an outbound HTTP request — which is what
makes exposing `/analyze` itself unacceptable here, since that endpoint accepts
an arbitrary uploaded log file.

What is still spent per request is a Groq completion, so the endpoint is rate
limited by client IP.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from app.core.config.settings import settings
from app.core.runtime import orchestrator
from app.demo.scenarios import (
    DEFAULT_SCENARIO_ID,
    briefing,
    get_scenario,
    list_scenarios,
)
from app.utils.rate_limit import SlidingWindowLimiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demo", tags=["Demo"])

demo_limiter = SlidingWindowLimiter()

# Which parts of the response are fixtures and which are produced live. Returned
# with every analysis so the UI can label them and a visitor is never misled
# about what the system actually did.
PROVENANCE: Dict[str, Any] = {
    "simulated": [
        "Incident log stream",
        "Commit history",
        "Deployment metadata",
    ],
    "generated_live": [
        "Log signal extraction",
        "Runbook retrieval (vector search over the real runbook corpus)",
        "Root cause synthesis (LLM)",
        "Confidence assessment",
        "Recommended remediation",
    ],
    "note": (
        "The incident is fictional. The investigation is not: the same "
        "orchestrator that serves authenticated users produced this report "
        "when you pressed the button."
    ),
}


def _client_key(request: Request) -> str:
    """Rate-limit bucket. Honours the proxy header Render sets in front of us."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/scenarios")
async def get_scenarios() -> Dict[str, Any]:
    """List the incidents a visitor can run. No side effects, no rate limit."""
    return {
        "scenarios": list_scenarios(),
        "default": DEFAULT_SCENARIO_ID,
        "provenance": PROVENANCE,
    }


@router.get("/scenarios/{scenario_id}")
async def get_scenario_briefing(scenario_id: str) -> Dict[str, Any]:
    """
    The incident briefing: what a responder would see before investigating.

    Serves the fixture half only. Returns fast and costs nothing, so the UI can
    render the incident immediately and run the analysis as a second step.
    """
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_id}")
    return {"incident": briefing(scenario), "provenance": PROVENANCE}


@router.post("/scenarios/{scenario_id}/analyze")
async def analyze_scenario(scenario_id: str, request: Request) -> Dict[str, Any]:
    """
    Run the real RCA pipeline over a seeded incident.

    Returns the orchestrator's report verbatim alongside the provenance split,
    so the client can show which panels are fixtures and which the system just
    produced.
    """
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_id}")

    key = f"demo:{_client_key(request)}"
    if not demo_limiter.allow(key, settings.DEMO_RATE_LIMIT_PER_MINUTE):
        retry_after = demo_limiter.retry_after(key)
        raise HTTPException(
            status_code=429,
            detail=(
                "Demo rate limit reached. Each analysis is a real LLM call, so "
                f"this is capped at {settings.DEMO_RATE_LIMIT_PER_MINUTE} per minute. "
                f"Try again in {retry_after}s."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    logger.info(f"[DEMO] Running RCA for scenario={scenario_id}")
    try:
        report = await orchestrator.analyze(
            service=scenario["service"],
            repo=scenario["repo"],
            log_text=scenario["log_text"],
            metadata={
                "environment": "demo",
                "deployed_at": scenario["deployed_at"],
                "first_error_at": scenario["first_error_at"],
                "impact": scenario["impact"],
            },
            # Seeded rather than fetched: see app/demo/scenarios.py for why.
            commit_analysis_override={"commits": scenario["commits"]},
        )
    except Exception as exc:
        # Surface the failure rather than substituting a canned report. A demo
        # that silently serves a fixture when the LLM is down is indistinguishable
        # from one that never worked.
        logger.error(f"[DEMO] RCA failed for {scenario_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=(
                "The analysis pipeline is currently unavailable, so there is no "
                "report to show. This endpoint runs a live model call and does "
                "not fall back to a stored result."
            ),
        ) from exc

    return {
        "scenario_id": scenario_id,
        "incident": briefing(scenario),
        "report": report,
        "provenance": PROVENANCE,
    }
