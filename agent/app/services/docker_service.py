import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DockerService:
    """
    Service for interacting with Docker containers.
    
    [DEPRECATED ARCHITECTURE - v3.0]
    We no longer support or recommend pulling logs via remote Docker daemon socket
    access due to extreme security vulnerabilities.
    
    [NEW ARCHITECTURE]
    Users should now deploy the OpsTron lightweight container on their cluster.
    That local container securely streams logs *outbound* to our `/agent/logs/ingest`
    endpoint using the user's `OPSTRON_API_KEY`.
    """
    
    def __init__(self):
        logger.warning("DockerService pull architecture is deprecated. Please migrate to the OpsTron outbound log streaming agent.")
        self.client = None

    def fetch_container_logs(self, container_id: str, tail: int = 100) -> str:
        """
        [DEPRECATED] Fetch the last N lines of logs directly.
        """
        logger.error(f"Attempted to pull logs for {container_id} using deprecated architecture. This is disabled for security reasons.")
        return "ERROR: Direct container polling is disabled. Please configure the OpsTron outbound streaming agent on your server."

    def get_container_id_by_name(self, name: str) -> Optional[str]:
        """
        [DEPRECATED] Search for container IDs.
        """
        return None
