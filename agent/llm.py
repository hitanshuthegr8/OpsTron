from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from config.settings import settings
import logging
import json

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0,
            max_tokens=4000
        )
    
    async def invoke(self, system_prompt: str, user_prompt: str) -> str:
        # Gemini handles system prompts differently - combine them
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        messages = [
            HumanMessage(content=combined_prompt)
        ]
        
        try:
            response = await self.model.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM invocation failed: {str(e)}")
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
                json_str = response_text.strip()
            
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.error(f"Response text: {response_text}")
            raise ValueError("LLM did not return valid JSON")
