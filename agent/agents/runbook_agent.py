import logging
from typing import Dict, Any, List
from db.chroma_store.vector_store import ChromaStore

logger = logging.getLogger(__name__)


class RunbookAgent:
    def __init__(self):
        self.store = ChromaStore()
    
    async def search(self, error_signals: List[str]) -> List[Dict[str, Any]]:
        if not error_signals:
            return []
        
        try:
            query = " ".join(error_signals)
            results = await self.store.search(query, top_k=3)
            
            logger.info(f"Found {len(results)} relevant runbooks")
            return results
            
        except Exception as e:
            logger.error(f"Runbook search failed: {str(e)}")
            return []
