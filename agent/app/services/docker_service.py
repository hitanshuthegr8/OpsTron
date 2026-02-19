import docker
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DockerService:
    """
    Service for interacting with Docker containers.
    Used for 'Option 2' log fetching where the agent pulls logs directly.
    """
    
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.client = None

    def fetch_container_logs(self, container_id: str, tail: int = 100) -> str:
        """
        Fetch the last N lines of logs from a specific container.
        """
        if not self.client:
            return "Docker client not initialized."
            
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, stdout=True, stderr=True)
            return logs.decode('utf-8')
        except docker.errors.NotFound:
            return f"Container {container_id} not found."
        except Exception as e:
            logger.error(f"Error fetching logs for container {container_id}: {e}")
            return f"Error fetching logs: {str(e)}"

    def get_container_id_by_name(self, name: str) -> Optional[str]:
        """
        Find a container ID by its name or part of its name.
        """
        if not self.client:
            return None
            
        try:
            containers = self.client.containers.list(all=True)
            for container in containers:
                if name in container.name:
                    return container.id
            return None
        except Exception as e:
            logger.error(f"Error searching for container {name}: {e}")
            return None
