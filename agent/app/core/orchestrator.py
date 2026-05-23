"""
RCA Orchestrator

Runs the 4-step Root Cause Analysis pipeline for every error:

  Step 1 — LogAgent:        Extract error signals from raw log text (via LLM).
  Step 2 — CommitAgent:     Fetch recent commits from GitHub for context.
  Step 3 — RunbookAgent:    Search the runbook vector store for matching docs.
  Step 4 — SynthesizerAgent: Combine all signals into a structured RCA report (via LLM).

After synthesis, alert routing is handled by EventEngine so phone calls are
deduped and cooldown-controlled in one place.

Usage:
    orchestrator = RCAOrchestrator()
    report = await orchestrator.analyze(service, repo, log_text, metadata)
"""

import logging
from typing import Dict, Any, Optional

from app.core.agents.log_agent import LogAgent
from app.core.agents.commit_agent import CommitAgent
from app.core.agents.runbook_agent import RunbookAgent
from app.core.agents.synthesizer_agent import SynthesizerAgent

logger = logging.getLogger(__name__)


class RCAOrchestrator:
    def __init__(self):
        self.log_agent = LogAgent()
        self.commit_agent = CommitAgent()
        self.runbook_agent = RunbookAgent()
        self.synthesizer_agent = SynthesizerAgent()

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

        return rca_report
