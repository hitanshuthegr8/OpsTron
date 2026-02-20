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
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run the full RCA pipeline.
        
        Args:
            service: Service name that had the error
            repo: GitHub repository to check for commits  
            log_text: Log content to analyze
            metadata: Optional metadata from MVP3 error ingestion (error context, env, etc.)
        """
        logger.info("Starting RCA pipeline")
        
        # Step 1: Extract log signals
        logger.info("Step 1: Analyzing logs")
        log_analysis = await self.log_agent.analyze(log_text)
        
        # Step 2: Fetch recent commits
        logger.info("Step 2: Fetching commits")
        commit_analysis = await self.commit_agent.analyze(repo)
        
        # Step 3: Search runbooks
        logger.info("Step 3: Searching runbooks")
        error_signals = log_analysis.get('error_signals', [])
        runbook_results = await self.runbook_agent.search(error_signals)
        
        # Step 4: Synthesize RCA
        logger.info("Step 4: Synthesizing root cause analysis")
        rca_report = await self.synthesizer_agent.synthesize(
            service=service,
            log_analysis=log_analysis,
            commit_analysis=commit_analysis,
            runbook_results=runbook_results,
            metadata=metadata  # MVP3: Pass metadata for enhanced context
        )
        
        logger.info("RCA pipeline completed")
        
        # Step 5: Proactive Alerting
        # If the synthesizer determined this was definitely caused by the recent deployment
        if rca_report.get("is_deployment_caused", False) or rca_report.get("is_deployment_regression", False):
            logger.warning(f"CRITICAL ALARM: Deployment regression confirmed in {service}. Triggering voice alert.")
            
            # Construct a brief, clear script for the text-to-speech voice
            suspect_commit = rca_report.get("suspect_commit", {}).get("sha", "Unknown")
            root_cause = rca_report.get("root_cause", "An unknown error")
            
            alert_message = (
                f"Hello. This is an Ops Tron emergency alert. "
                f"A critical error has been detected in the {service} service "
                f"immediately following commit {suspect_commit}. "
                f"The AI analysis indicates the root cause is: {root_cause}. "
                f"Please check your dashboard immediately."
            )
            
            # Fire the call in the background so we don't block the API response
            asyncio.create_task(self._trigger_voice_alert(alert_message))
        
        return rca_report
        
    async def _trigger_voice_alert(self, message: str):
        """Helper to run the synchronous Twilio call in an async background task."""
        try:
            # Twilio's client is currently synchronous, so we offload it
            await asyncio.to_thread(self.twilio_service.send_voice_alert, message)
        except Exception as e:
            logger.error(f"Background voice alert task failed: {e}")

