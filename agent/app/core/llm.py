"""
LLM Client — Groq via LangChain

All AI inference in OpsTron goes through this single client.
Currently uses Groq's `llama-3.3-70b-versatile` model for speed and quality.

To swap models: change `model_name` in `_init_groq()`.
To add a new provider: add a new `_init_<provider>()` method and call it in `__init__`.
"""

import logging
import json
from langchain_core.messages import HumanMessage
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around LangChain ChatGroq."""

    def __init__(self):
        self.model = self._init_groq()

    def _init_groq(self):
        """Initialize Groq via LangChain."""
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model_name="llama-3.3-70b-versatile",
                api_key=settings.GROQ_API_KEY,
                temperature=0,
                max_tokens=4000,
            )
        except Exception as e:
            logger.error(f"Failed to init Groq LLM: {e}")
            raise

    async def invoke(self, system_prompt: str, user_prompt: str) -> str:
        """Send a free-form prompt and return the raw text response."""
        combined = f"{system_prompt}\n\n{user_prompt}"
        messages = [HumanMessage(content=combined)]
        try:
            response = await self.model.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Groq invocation failed: {e}")
            raise

    async def invoke_structured(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Send a prompt that expects a JSON response.

        Strips markdown code fences if present, then parses JSON.
        Raises ValueError if the model doesn't return valid JSON.
        """
        response_text = await self.invoke(system_prompt, user_prompt)

        try:
            # Strip optional ```json ... ``` or ``` ... ``` fences
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            else:
                # Attempt to grab the first top-level JSON object
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_str = response_text[start:end] if start != -1 and end > start else response_text.strip()

            return json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}")
            logger.error(f"Raw response (first 500 chars): {response_text[:500]}")
            raise ValueError("LLM did not return valid JSON")
