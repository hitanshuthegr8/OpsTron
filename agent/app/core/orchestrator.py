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
import time
from typing import Any, Callable, Dict, Optional

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
        commit_analysis_override: Optional[Dict[str, Any]] = None,
        on_step: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Run the full RCA pipeline and return a structured report.

        Args:
            service:  Name of the service that errored (e.g. "checkout-api").
            repo:     GitHub repo to pull recent commits from (e.g. "owner/repo").
            log_text: Raw log content to analyze.
            metadata: Optional dict with extra context (env, endpoint, deployment info).
            commit_analysis_override: Supply commit data directly instead of
                fetching it from GitHub. Used by the demo, where live commits
                from an unrelated repository would be incoherent evidence. When
                None (every production path) the CommitAgent runs as before.
            on_step: Called after each stage with its name, measured duration and
                real output. Lets a caller surface what each agent actually found
                instead of guessing at progress. Production paths pass nothing and
                pay nothing.

        Returns:
            dict: Structured RCA report from the SynthesizerAgent.
        """
        logger.info("Starting RCA pipeline")
        metadata = metadata or {}

        def _emit(name: str, started: float, summary: Dict[str, Any]) -> None:
            if on_step is None:
                return
            on_step({
                "step": name,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                **summary,
            })

        github_token = str(metadata.pop("_github_token", "") or "")

        # Step 1: Extract error signals from logs
        logger.info("Step 1: Analyzing logs")
        _t = time.perf_counter()
        try:
            log_analysis = await self.log_agent.analyze(log_text)
            _emit("logs", _t, {
                "label": "Parsed the log stream",
                "signals": log_analysis.get("error_signals", []),
                "key_errors": log_analysis.get("key_errors", [])[:4],
                "stack_traces": len(log_analysis.get("stack_traces", []) or []),
            })
        except Exception as e:
            logger.error(f"LogAgent failed: {e}", exc_info=True)
            raise

        # Step 2: Fetch recent commits (failure is non-fatal — returns empty commits)
        if commit_analysis_override is not None:
            logger.info("Step 2: Using supplied commit data (skipping GitHub fetch)")
            commit_analysis = commit_analysis_override
            _emit("commits", time.perf_counter(), {
                "label": "Correlated recent deployments",
                "count": len(commit_analysis.get("commits", [])),
                "source": "supplied",
            })
        else:
            logger.info("Step 2: Fetching commits")
            _t = time.perf_counter()
            try:
                commit_analysis = await self.commit_agent.analyze(repo, github_token=github_token)
                _emit("commits", _t, {
                    "label": "Fetched recent commits",
                    "count": len(commit_analysis.get("commits", [])),
                    "source": "github",
                })
            except Exception as e:
                logger.error(f"CommitAgent failed: {e}", exc_info=True)
                commit_analysis = {"error": str(e), "commits": []}

        # Step 3: Search runbooks for relevant procedures
        logger.info("Step 3: Searching runbooks")
        try:
            error_signals = log_analysis.get("error_signals", [])
            _t = time.perf_counter()
            runbook_results = await self.runbook_agent.search(error_signals)
            _emit("runbooks", _t, {
                "label": "Searched the runbook corpus",
                "matches": [r.get("title") for r in runbook_results],
                "query_signals": error_signals,
            })
        except Exception as e:
            logger.error(f"RunbookAgent failed: {e}", exc_info=True)
            runbook_results = []

        # Step 4: Synthesize everything into a final RCA report
        logger.info("Step 4: Synthesizing root cause analysis")
        try:
            _t = time.perf_counter()
            rca_report = await self.synthesizer_agent.synthesize(
                service=service,
                log_analysis=log_analysis,
                commit_analysis=commit_analysis,
                runbook_results=runbook_results,
                metadata=metadata,
            )
            _emit("synthesis", _t, {
                "label": "Synthesised the root cause",
                "confidence": rca_report.get("confidence"),
                "actions": len(rca_report.get("recommended_actions", []) or []),
            })
        except Exception as e:
            logger.error(f"SynthesizerAgent failed: {e}", exc_info=True)
            raise

        logger.info("RCA pipeline completed")

        return rca_report
