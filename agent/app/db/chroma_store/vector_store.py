import chromadb
from chromadb.config import Settings
import logging
from typing import List, Dict, Any
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class ChromaStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection_name = "runbooks"
        self._ensure_collection()
    
    def _ensure_collection(self):
        try:
            self.collection = self.client.get_collection(self.collection_name)
            logger.info(f"Loaded existing collection: {self.collection_name}")
        except Exception:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Runbook documents for RCA"}
            )
            logger.info(f"Created new collection: {self.collection_name}")
    
    def add_documents(self, documents: List[Dict[str, str]]):
        ids = []
        texts = []
        metadatas = []
        
        for doc in documents:
            doc_id = doc['filename']
            ids.append(doc_id)
            texts.append(doc['content'])
            metadatas.append({
                "title": doc['title'],
                "filename": doc['filename']
            })
        
        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
        logger.info(f"Added {len(documents)} documents to ChromaDB")
    
    async def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                formatted_results.append({
                    "title": results['metadatas'][0][i].get('title', 'Untitled'),
                    "filename": results['metadatas'][0][i].get('filename', ''),
                    "snippet": doc[:500],
                    "full_content": doc
                })
        
        return formatted_results
