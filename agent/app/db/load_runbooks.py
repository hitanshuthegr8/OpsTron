import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.chroma_store.vector_store import ChromaStore
from app.utils.doc_loader import DocumentLoader
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_runbooks():
    runbooks_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'runbooks'
    )
    
    logger.info(f"Loading runbooks from: {runbooks_dir}")
    
    loader = DocumentLoader()
    documents = loader.load_markdown_files(runbooks_dir)
    
    if not documents:
        logger.error("No runbook documents found!")
        return
    
    store = ChromaStore()
    store.add_documents(documents)
    
    logger.info(f"Successfully loaded {len(documents)} runbooks into ChromaDB")


if __name__ == "__main__":
    load_runbooks()
