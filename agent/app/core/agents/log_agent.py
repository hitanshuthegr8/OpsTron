import logging
import re
from typing import Dict, Any, List
from app.core.llm import LLMClient

logger = logging.getLogger(__name__)

class LogAgent:
    def __init__(self):
        self.llm = LLMClient()
        
    def _pre_filter_logs(self, log_text: str, context_lines: int = 5) -> str:
        lines = log_text.splitlines()
        if len(lines) < 20:
            return log_text
            
        error_pattern = re.compile(r'(?i)(error|exception|stacktrace|fatal|panic|traceback|warn)')
        keep_indices = set()
        
        for idx, line in enumerate(lines):
            if error_pattern.search(line):
                start_idx = max(0, idx - context_lines)
                end_idx = min(len(lines), idx + context_lines + 1)
                for i in range(start_idx, end_idx):
                    keep_indices.add(i)
                    
        if not keep_indices:
            return "\n".join(lines[:10] + ["...[snip]..."] + lines[-10:])
            
        filtered_lines = []
        sorted_indices = sorted(list(keep_indices))
        
        last_idx = -2
        for idx in sorted_indices:
            if idx > last_idx + 1 and last_idx != -2:
                filtered_lines.append("... [filtered non-error logs] ...")
            filtered_lines.append(lines[idx])
            last_idx = idx
            
        filtered_text = "\n".join(filtered_lines)
        logger.info(f"Log pre-filtering reduced size from {len(log_text)} to {len(filtered_text)} chars")
        return filtered_text

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

        # Pre-filter logs to save tokens
        filtered_log_text = self._pre_filter_logs(log_text)

        user_prompt = f"""Analyze these logs and extract error signals:

{filtered_log_text}

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
