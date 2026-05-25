import logging
from typing import List, Dict, Any
from app.core.config.settings import settings

logger = logging.getLogger(__name__)

# Lazy-load chromadb — it crashes on import with NumPy 2.x
# The app starts cleanly and RunbookAgent returns empty results if unavailable
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except Exception as e:
    chromadb = None
    CHROMADB_AVAILABLE = False
    logger.warning(f"ChromaDB unavailable (runbook search disabled): {e}")

class ChromaStore:
    def __init__(self):
        self._available = CHROMADB_AVAILABLE
        self.collection = None

        if not self._available:
            logger.warning("ChromaStore initialised in degraded mode — no runbook search")
            return

        try:
            self.client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            self.collection_name = "runbooks"
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}")
            self._available = False
            return

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
        if not self._available or self.collection is None:
            logger.warning("Skipping runbook indexing because ChromaDB is unavailable")
            return

        ids = []
        texts = []
        metadatas = []
        
        for doc in documents:
            doc_id = doc.get('id') or doc['filename']
            ids.append(doc_id)
            texts.append(doc['content'])
            metadatas.append({
                "title": doc['title'],
                "filename": doc['filename'],
                "github_id": doc.get("github_id", ""),
                "repo": doc.get("repo", ""),
                "service": doc.get("service", ""),
            })
        
        self.collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
        logger.info(f"Added {len(documents)} documents to ChromaDB")
    
    async def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not self._available or self.collection is None:
            return []   # graceful degradation

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
