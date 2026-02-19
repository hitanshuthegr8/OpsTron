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
        return rca_report

