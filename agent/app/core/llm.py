from langchain_core.messages import HumanMessage
from app.core.config.settings import settings
import logging
import json
import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "hf.co/microsoft/Phi-3-mini-4k-instruct-gguf"  # Microsoft Phi-3 model


class LLMClient:
    def __init__(self):
        logger.info("Using Groq API for LLM")
        self.use_ollama = False
        self.model = self._init_groq()
    
    def _check_ollama(self) -> bool:
        # User requested to use Groq explicitly instead of Ollama
        return False
    
    def _init_groq(self):
        """Initialize Groq via LangChain."""
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model_name="llama-3.3-70b-versatile",  # Fast and smart Groq model
                api_key=settings.GROQ_API_KEY, # Needs to be added to settings
                temperature=0,
                max_tokens=4000
            )
        except Exception as e:
            logger.error(f"Failed to init Groq: {e}")
            raise
    
    async def invoke(self, system_prompt: str, user_prompt: str) -> str:
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        return await self._invoke_groq(combined_prompt)
    
    async def _invoke_groq(self, prompt: str) -> str:
        """Call Groq API via LangChain."""
        messages = [HumanMessage(content=prompt)]
        try:
            response = await self.model.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Groq invocation failed: {e}")
            raise
    
    async def _invoke_gemini(self, prompt: str) -> str:
        """Call Gemini via LangChain."""
        messages = [HumanMessage(content=prompt)]
        try:
            response = await self.model.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Gemini invocation failed: {e}")
            raise
    
    async def invoke_structured(self, system_prompt: str, user_prompt: str) -> dict:
        response_text = await self.invoke(system_prompt, user_prompt)
        
        try:
            # Extract JSON from response
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            else:
                # Try to find JSON object directly
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = response_text[start:end]
                else:
                    json_str = response_text.strip()
            
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.error(f"Response text: {response_text[:500]}...")
            raise ValueError("LLM did not return valid JSON")


