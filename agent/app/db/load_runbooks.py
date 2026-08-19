import sys
import os
# Add the `agent/` directory to sys.path so `app.*` imports resolve
# when this script is run directly.
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.db.chroma_store.vector_store import ChromaStore
from app.utils.doc_loader import DocumentLoader
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _find_runbooks_dir() -> str:
    """
    Locate the runbooks directory.

    Checks `agent/runbooks` first, then the repository root, so the loader
    works regardless of which level the runbooks are kept at.
    """
    db_dir = os.path.dirname(os.path.abspath(__file__))
    agent_dir = os.path.dirname(os.path.dirname(db_dir))
    repo_dir = os.path.dirname(agent_dir)

    for candidate in (
        os.path.join(agent_dir, "runbooks"),
        os.path.join(repo_dir, "runbooks"),
    ):
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(agent_dir, "runbooks")


def load_runbooks():
    runbooks_dir = _find_runbooks_dir()
    
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
