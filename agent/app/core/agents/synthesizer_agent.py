import logging
from typing import Dict, Any, Optional
from app.core.llm import LLMClient
from datetime import datetime

logger = logging.getLogger(__name__)


class SynthesizerAgent:
    def __init__(self):
        self.llm = LLMClient()
    
    async def synthesize(
        self,
        service: str,
        log_analysis: Dict[str, Any],
        commit_analysis: Dict[str, Any],
        runbook_results: list,
        metadata: Optional[Dict[str, Any]] = None  # MVP3: Optional error metadata
    ) -> Dict[str, Any]:
        
        # MVP4: Check if this is a deployment-related error
        is_deployment_related = metadata and metadata.get("deployment_context")
        
        if is_deployment_related:
            system_prompt = self._get_deployment_system_prompt()
        else:
            system_prompt = self._get_standard_system_prompt()

        # Build user prompt with optional metadata (MVP3 enhancement)
        metadata_section = ""
        if metadata:
            metadata_section = f"""
ERROR CONTEXT (AUTOMATED CAPTURE):
{self._format_metadata(metadata)}
"""

        user_prompt = f"""Service: {service}
{metadata_section}
LOG ANALYSIS:
{self._format_log_analysis(log_analysis)}

RECENT COMMITS:
{self._format_commits(commit_analysis)}

RUNBOOK MATCHES:
{self._format_runbooks(runbook_results)}

Provide root cause analysis in JSON format."""

        try:
            result = await self.llm.invoke_structured(system_prompt, user_prompt)
            result["service"] = service
            result["analyzed_at"] = datetime.utcnow().isoformat()
            
            # MVP3: Add ingestion metadata to report
            if metadata:
                result["ingestion_mode"] = "automated"
                result["error_timestamp"] = metadata.get("timestamp")
                result["environment"] = metadata.get("environment")
                result["request_id"] = metadata.get("request_id")
                
                # MVP4: Add deployment context
                if is_deployment_related:
                    result["is_deployment_regression"] = True
                    result["suspect_commit"] = metadata["deployment_context"].get("suspect_commit")
            else:
                result["ingestion_mode"] = "manual"
            
            logger.info(f"RCA completed with {result.get('confidence', 'unknown')} confidence")
            return result
            
        except Exception as e:
            logger.error(f"Synthesis failed: {str(e)}")
            return {
                "service": service,
                "root_cause": "analysis_failed",
                "confidence": "low",
                "error": str(e),
                "analyzed_at": datetime.utcnow().isoformat(),
                "ingestion_mode": "automated" if metadata else "manual"
            }
    
    def _format_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format MVP3 error metadata for the prompt."""
        lines = []
        if metadata.get("error_message"):
            lines.append(f"Error: {metadata['error_message']}")
        if metadata.get("timestamp"):
            lines.append(f"Timestamp: {metadata['timestamp']}")
        if metadata.get("environment"):
            lines.append(f"Environment: {metadata['environment']}")
        if metadata.get("endpoint"):
            lines.append(f"Endpoint: {metadata.get('method', 'UNKNOWN')} {metadata['endpoint']}")
        if metadata.get("user_id"):
            lines.append(f"Affected User: {metadata['user_id']}")
        if metadata.get("request_id"):
            lines.append(f"Request ID: {metadata['request_id']}")
        return "\n".join(lines) if lines else "No additional context"
    
    def _format_log_analysis(self, analysis: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"Error Signals: {', '.join(analysis.get('error_signals', []))}")
        lines.append(f"Key Errors: {', '.join(analysis.get('key_errors', []))}")
        lines.append(f"Patterns: {', '.join(analysis.get('patterns', []))}")
        return "\n".join(lines)
    
    def _format_commits(self, analysis: Dict[str, Any]) -> str:
        commits = analysis.get('commits', [])
        if not commits:
            return "No commits available"
        
        lines = []
        for commit in commits[:5]:
            lines.append(f"- {commit['sha']}: {commit['message']} ({commit['author']})")
        return "\n".join(lines)
    
    def _format_runbooks(self, results: list) -> str:
        if not results:
            return "No matching runbooks"
        
        lines = []
        for result in results:
            lines.append(f"- {result.get('title', 'Untitled')}: {result.get('snippet', '')[:200]}")
        return "\n".join(lines)
    
    def _get_standard_system_prompt(self) -> str:
        """Standard RCA prompt for runtime errors."""
        return """You are a senior SRE conducting root cause analysis.

Synthesize all evidence to determine:
1. Root cause of the failure
2. Contributing factors
3. Recommended fixes
4. Confidence level

Be precise, technical, and actionable. Cite specific log lines, commits, or runbook sections.

Return ONLY valid JSON:
{
    "root_cause": "primary cause",
    "confidence": "high|medium|low",
    "contributing_factors": ["factor1", "factor2"],
    "evidence": {
        "logs": "key log evidence",
        "commits": "relevant commits",
        "runbooks": "applicable runbooks"
    },
    "recommended_actions": ["action1", "action2"],
    "timeline": "estimated sequence of events"
}"""
    
    def _get_deployment_system_prompt(self) -> str:
        """Specialized prompt for deployment regression analysis (MVP4)."""
        return """You are a senior SRE analyzing a DEPLOYMENT REGRESSION.

⚠️ CRITICAL: This error occurred within 5 minutes of a code deployment.

Your primary task is to:
1. Analyze the COMMIT DIFF to find the exact code change that caused the failure
2. Compare the stacktrace with the modified files and lines
3. Determine if this is definitely caused by the deployment or coincidental
4. Provide a clear ROLLBACK RECOMMENDATION

Be extremely precise. Reference specific:
- File names and line numbers from the commit diff
- Error messages that match the changed code
- The exact code change that introduced the bug

Return ONLY valid JSON:
{
    "root_cause": "Specific code change that caused the failure",
    "is_deployment_caused": true/false,
    "confidence": "high|medium|low",
    "suspect_code_change": {
        "file": "filename.py",
        "line_range": "42-48",
        "description": "What was changed"
    },
    "error_correlation": "How the error relates to the code change",
    "contributing_factors": ["factor1", "factor2"],
    "evidence": {
        "logs": "key log evidence",
        "diff": "relevant code changes",
        "runbooks": "applicable runbooks"
    },
    "recommended_actions": [
        "IMMEDIATE: action",
        "ROLLBACK: git revert command or steps",
        "FIX: how to fix the issue"
    ],
    "rollback_recommendation": {
        "should_rollback": true/false,
        "urgency": "critical|high|medium|low",
        "command": "git revert <sha> or other rollback steps"
    }
}"""

