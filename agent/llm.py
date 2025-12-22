from langchain_core.messages import HumanMessage
from config.settings import settings
import logging
import json
import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "hf.co/microsoft/Phi-3-mini-4k-instruct-gguf"  # Microsoft Phi-3 model


class LLMClient:
    def __init__(self):
        self.use_ollama = self._check_ollama()
        if self.use_ollama:
            logger.info(f"Using Ollama with {OLLAMA_MODEL} model (local)")
        else:
            logger.info("Using Gemini (cloud API)")
            self.model = self._init_gemini()
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is running locally."""
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{OLLAMA_URL}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "").split(":")[0] for m in models]
                    if OLLAMA_MODEL in model_names or any(OLLAMA_MODEL in n for n in model_names):
                        return True
                    logger.warning(f"Ollama running but {OLLAMA_MODEL} not found. Available: {model_names}")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
        return False
    
    def _init_gemini(self):
        """Fallback to Gemini if Ollama unavailable."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-exp",
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0,
                max_tokens=4000
            )
        except Exception as e:
            logger.error(f"Failed to init Gemini: {e}")
            raise
    
    async def invoke(self, system_prompt: str, user_prompt: str) -> str:
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        if self.use_ollama:
            return await self._invoke_ollama(combined_prompt)
        else:
            return await self._invoke_gemini(combined_prompt)
    
    async def _invoke_ollama(self, prompt: str) -> str:
        """Call Ollama API directly."""
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min timeout for local LLM
            try:
                response = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
            except Exception as e:
                logger.error(f"Ollama invocation failed: {e}")
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


