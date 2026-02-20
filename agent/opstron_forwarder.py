#!/usr/bin/env python3
"""
OpsTron Lightweight Log Forwarding Agent (v3.0)

This script is designed to run securely on the user's infrastructure.
It connects to the local Docker socket and streams logs *outbound* to the
OpsTron backend, ensuring OpsTron never requires inbound remote access.

⚠️ PRODUCTION SECURITY WARNING ⚠️
Mounting `/var/run/docker.sock` provides full access to the Docker daemon.
While acceptable for development or isolated college projects, in a strict
production environment, this forwarder should be run:
  1. Using a read-only Docker socket proxy (e.g., Tecnativa/docker-socket-proxy)
  2. With restricted IAM/RBAC roles if running in Kubernetes.

*Guarantee: This script is entirely read-only. It only executes `container.logs()`.
It does not and cannot mutate, stop, or delete containers.*

Usage:
    export OPSTRON_API_KEY="your_secure_key"
    export OPSTRON_BACKEND_URL="https://api.opstron.io/agent/logs/ingest"
    python3 opstron_forwarder.py
"""

import os
import sys
import time
import json
import logging
import requests
import docker
from datetime import datetime

# Configuration
API_KEY = os.environ.get("OPSTRON_API_KEY")
BACKEND_URL = os.environ.get("OPSTRON_BACKEND_URL", "http://host.docker.internal:8001/agent/logs/ingest")
POLL_INTERVAL = int(os.environ.get("OPSTRON_POLL_INTERVAL", "5"))

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OpsTron-Forwarder")

def main():
    if not API_KEY:
        logger.error("FATAL: OPSTRON_API_KEY environment variable is not set.")
        sys.exit(1)

    try:
        client = docker.from_env()
        logger.info("Successfully connected to local Docker socket.")
    except Exception as e:
        logger.error(f"FATAL: Could not connect to Docker socket. Ensure you have permissions or mapped /var/run/docker.sock. Error: {e}")
        sys.exit(1)

    logger.info(f"OpsTron Forwarder active. Streaming logs to {BACKEND_URL} every {POLL_INTERVAL} seconds...")

    # We poll the last N lines every interval.
    while True:
        try:
            containers = client.containers.list()
            for container in containers:
                try:
                    # STRICTLY READ-ONLY OPERATION
                    # We grab a small tail of logs and ignore encoding errors to prevent crashes
                    logs = container.logs(tail=50).decode('utf-8', errors='ignore')
                    
                    if not logs.strip():
                        continue
                        
                    payload = {
                        "container_id": container.id,
                        "container_name": container.name,
                        "logs": logs,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    headers = {
                        "Content-Type": "application/json",
                        "X-API-Key": API_KEY  # Authenticate with the backend
                    }
                    
                    response = requests.post(BACKEND_URL, json=payload, headers=headers, timeout=5)
                    
                    if response.status_code != 200:
                        logger.warning(f"Failed to forward logs for {container.name}. Status: {response.status_code}")
                        
                except Exception as container_err:
                    logger.warning(f"Error reading logs from {container.name}: {container_err}")
                    
        except requests.exceptions.RequestException as req_err:
             logger.error(f"Network error communicating with backend: {req_err}")
        except Exception as e:
            logger.error(f"Critical error during polling cycle: {e}")
            
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("OpsTron Forwarder shutting down gracefully.")
        sys.exit(0)
