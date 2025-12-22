import logging
from typing import Dict, Any, List
from llm import LLMClient

logger = logging.getLogger(__name__)


class LogAgent:
    def __init__(self):
        self.llm = LLMClient()
    
    async def analyze(self, log_text: str) -> Dict[str, Any]:
        system_prompt = """You are a log analysis expert. Extract critical information from logs.

Your task:
1. Identify all ERROR, EXCEPTION, or CRITICAL log lines
2. Extract stack traces
3. Identify timing patterns (timeouts, delays)
4. Extract database errors
5. Note any null pointer or connection issues

Return ONLY valid JSON with this structure:
{
    "error_signals": ["list of error types found"],
    "stack_traces": ["extracted stack traces"],
    "key_errors": ["most critical error messages"],
    "patterns": ["timing issues, deadlocks, etc"]
}"""

        user_prompt = f"""Analyze these logs and extract error signals:

{log_text[:8000]}

Return structured JSON only."""

        try:
            result = await self.llm.invoke_structured(system_prompt, user_prompt)
            logger.info(f"Extracted {len(result.get('error_signals', []))} error signals")
            return result
        except Exception as e:
            logger.error(f"Log analysis failed: {str(e)}")
            return {
                "error_signals": ["analysis_failed"],
                "stack_traces": [],
                "key_errors": [str(e)],
                "patterns": []
            }
