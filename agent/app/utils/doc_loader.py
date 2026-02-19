import os
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class DocumentLoader:
    @staticmethod
    def load_markdown_files(directory: str) -> List[Dict[str, str]]:
        documents = []
        
        if not os.path.exists(directory):
            logger.warning(f"Directory not found: {directory}")
            return documents
        
        for filename in os.listdir(directory):
            if filename.endswith('.md'):
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        documents.append({
                            "filename": filename,
                            "title": filename.replace('.md', '').replace('_', ' ').title(),
                            "content": content
                        })
                        logger.info(f"Loaded {filename}")
                except Exception as e:
                    logger.error(f"Failed to load {filename}: {str(e)}")
        
        return documents
