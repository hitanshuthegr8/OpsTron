"""
RCA Orchestrator

Runs the 4-step Root Cause Analysis pipeline for every error:

  Step 1 — LogAgent:        Extract error signals from raw log text (via LLM).
  Step 2 — CommitAgent:     Fetch recent commits from GitHub for context.
  Step 3 — RunbookAgent:    Search the runbook vector store for matching docs.
  Step 4 — SynthesizerAgent: Combine all signals into a structured RCA report (via LLM).

After synthesis, if the report flags a deployment regression, a voice alert is
fired in the background via Twilio (non-blocking).

Usage:
    orchestrator = RCAOrchestrator()
    report = await orchestrator.analyze(service, repo, log_text, metadata)
"""

import logging
import asyncio
from typing import Dict, Any, Optional

from app.core.agents.log_agent import LogAgent
from app.core.agents.commit_agent import CommitAgent
from app.core.agents.runbook_agent import RunbookAgent
from app.core.agents.synthesizer_agent import SynthesizerAgent
from app.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)


class RCAOrchestrator:
    def __init__(self):
        self.log_agent = LogAgent()
        self.commit_agent = CommitAgent()
        self.runbook_agent = RunbookAgent()
        self.synthesizer_agent = SynthesizerAgent()
        self.twilio_service = TwilioService()

    async def analyze(
        self,
        service: str,
        repo: str,
        log_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run the full RCA pipeline and return a structured report.

        Args:
            service:  Name of the service that errored (e.g. "checkout-api").
            repo:     GitHub repo to pull recent commits from (e.g. "owner/repo").
            log_text: Raw log content to analyze.
            metadata: Optional dict with extra context (env, endpoint, deployment info).

        Returns:
            dict: Structured RCA report from the SynthesizerAgent.
        """
        logger.info("Starting RCA pipeline")

        # Step 1: Extract error signals from logs
        logger.info("Step 1: Analyzing logs")
        try:
            log_analysis = await self.log_agent.analyze(log_text)
        except Exception as e:
            logger.error(f"LogAgent failed: {e}", exc_info=True)
            raise

        # Step 2: Fetch recent commits (failure is non-fatal — returns empty commits)
        logger.info("Step 2: Fetching commits")
        try:
            commit_analysis = await self.commit_agent.analyze(repo)
        except Exception as e:
            logger.error(f"CommitAgent failed: {e}", exc_info=True)
            commit_analysis = {"error": str(e), "commits": []}

        # Step 3: Search runbooks for relevant procedures
        logger.info("Step 3: Searching runbooks")
        try:
            error_signals = log_analysis.get("error_signals", [])
            runbook_results = await self.runbook_agent.search(error_signals)
        except Exception as e:
            logger.error(f"RunbookAgent failed: {e}", exc_info=True)
            runbook_results = []

        # Step 4: Synthesize everything into a final RCA report
        logger.info("Step 4: Synthesizing root cause analysis")
        try:
            rca_report = await self.synthesizer_agent.synthesize(
                service=service,
                log_analysis=log_analysis,
                commit_analysis=commit_analysis,
                runbook_results=runbook_results,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"SynthesizerAgent failed: {e}", exc_info=True)
            raise

        logger.info("RCA pipeline completed")

        # Fire a voice alert in the background for confirmed deployment regressions
        if rca_report.get("is_deployment_caused") or rca_report.get("is_deployment_regression"):
            logger.warning(f"Deployment regression confirmed in {service}. Triggering voice alert.")
            suspect_sha = rca_report.get("suspect_commit", {}).get("sha", "unknown")
            root_cause = rca_report.get("root_cause", "an unknown error")
            alert_message = (
                f"Hello. This is an OpsTron emergency alert. "
                f"A critical error has been detected in the {service} service "
                f"immediately following commit {suspect_sha}. "
                f"The AI analysis indicates the root cause is: {root_cause}. "
                f"Please check your dashboard immediately."
            )
            asyncio.create_task(self._trigger_voice_alert(alert_message))

        return rca_report

    async def _trigger_voice_alert(self, message: str):
        """Fire a Twilio voice call in the background (non-blocking)."""
        try:
            await asyncio.to_thread(self.twilio_service.send_voice_alert, message)
        except Exception as e:
            logger.error(f"Background voice alert failed: {e}")
