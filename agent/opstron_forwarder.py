#!/usr/bin/env python3
"""
OpsTron Log Forwarding Agent v4.0

WHAT CHANGED FROM v3:
  ✅ Label filtering   — only monitors containers you opt-in with opstron.monitor=true
  ✅ Delta logging     — tracks last-seen timestamp per container, sends NEW lines only
  ✅ Docker events     — instant crash/OOM/kill detection via event stream (no polling)
  ✅ Heartbeat         — agent reports liveness to backend every 60 seconds
  ✅ Exponential retry — backs off on network failures instead of hammering the backend

HOW TO OPT A CONTAINER IN:
  Add this label to any container you want OpsTron to watch:
    labels:
      opstron.monitor: "true"

  Or via docker run:
    docker run --label opstron.monitor=true ...

USAGE:
  export OPSTRON_API_KEY="your-key-from-opstron-dashboard"
  export OPSTRON_BACKEND_URL="https://opstron.onrender.com"
  python3 opstron_forwarder.py

ENVIRONMENT VARIABLES:
  OPSTRON_API_KEY      (required) Your unique agent key from the OpsTron dashboard
  OPSTRON_BACKEND_URL  (required) Base URL of the OpsTron backend (no trailing slash)
  OPSTRON_POLL_SECS    (optional) How often to poll for new logs, default 30
  OPSTRON_LABEL        (optional) Label to filter on, default opstron.monitor=true

SECURITY NOTE:
  This script is entirely read-only. It only calls container.logs() and
  listens to the Docker events stream. It cannot stop, restart, or modify
  any container in any way.
"""

import os
import sys
import time
import json
import socket
import logging
import threading
from datetime import datetime, timezone

import requests
import docker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY      = os.environ.get("OPSTRON_API_KEY", "").strip()
BACKEND_URL  = os.environ.get("OPSTRON_BACKEND_URL", "https://opstron.onrender.com").rstrip("/")
POLL_SECS    = int(os.environ.get("OPSTRON_POLL_SECS", "30"))
MONITOR_LABEL = os.environ.get("OPSTRON_LABEL", "opstron.monitor")
AGENT_VERSION = "4.0.0"
HOSTNAME      = socket.gethostname()

INGEST_URL    = f"{BACKEND_URL}/agent/logs/ingest"
EVENT_URL     = f"{BACKEND_URL}/agent/events"
HEARTBEAT_URL = f"{BACKEND_URL}/agent/heartbeat"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("opstron-agent")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
    }


def _post(url: str, payload: dict, timeout: int = 8) -> bool:
    """POST JSON to backend. Returns True on success."""
    return _post_status(url, payload, timeout) == 200


def _post_status(url: str, payload: dict, timeout: int = 8) -> int:
    """POST JSON to backend. Returns HTTP status code, or 0 on network failure."""
    try:
        r = requests.post(url, json=payload, headers=_headers(), timeout=timeout)
        if r.status_code == 200:
            return r.status_code
        logger.warning(f"Backend returned {r.status_code} for {url}: {r.text[:120]}")
        return r.status_code
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout posting to {url}")
        return 0
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection error posting to {url}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error posting to {url}: {e}")
        return 0


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------
def send_heartbeat(docker_client: docker.DockerClient):
    """Tell the backend this agent is alive."""
    try:
        monitored = [
            c.name
            for c in docker_client.containers.list()
            if c.labels.get(MONITOR_LABEL) == "true"
        ]
    except Exception:
        monitored = []

    payload = {
        "agent_version": AGENT_VERSION,
        "hostname": HOSTNAME,
        "monitored_containers": monitored,
    }
    ok = _post(HEARTBEAT_URL, payload)
    if ok:
        logger.info(f"💓 Heartbeat sent | watching {len(monitored)} containers: {monitored}")
    else:
        logger.warning("💓 Heartbeat failed — backend unreachable?")


def heartbeat_loop(docker_client: docker.DockerClient, interval_secs: int = 60):
    """Run heartbeats on a background thread every `interval_secs` seconds."""
    while True:
        time.sleep(interval_secs)
        send_heartbeat(docker_client)


# ---------------------------------------------------------------------------
# Delta log polling
# ---------------------------------------------------------------------------
# Maps container_id → ISO timestamp of last log line we sent
_last_seen: dict[str, str] = {}


def get_monitored_containers(docker_client: docker.DockerClient) -> list:
    """Return only containers that have opted in with the monitor label."""
    try:
        return docker_client.containers.list(
            filters={"label": f"{MONITOR_LABEL}=true"}
        )
    except Exception as e:
        logger.error(f"Failed to list containers: {e}")
        return []


def poll_logs(docker_client: docker.DockerClient):
    """
    For each monitored container, fetch ONLY new log lines since last poll.
    Uses `since` parameter to avoid re-sending the same lines.
    """
    containers = get_monitored_containers(docker_client)

    if not containers:
        logger.debug("No containers with opstron.monitor=true found. Waiting...")
        return

    for container in containers:
        cid  = container.id
        name = container.name

        # First time we see this container: grab last 50 lines as bootstrap
        since = _last_seen.get(cid)
        try:
            if since:
                # Only new lines since last successful poll
                raw_logs = container.logs(
                    since=datetime.fromisoformat(since).replace(tzinfo=timezone.utc),
                    timestamps=True,
                ).decode("utf-8", errors="ignore")
            else:
                # Bootstrap: grab last 50 lines
                raw_logs = container.logs(
                    tail=50,
                    timestamps=True,
                ).decode("utf-8", errors="ignore")

            lines = [l for l in raw_logs.splitlines() if l.strip()]
            if not lines:
                continue

            # Update the since pointer to the timestamp of the last line
            # Docker timestamp format: 2024-01-15T12:00:00.000000000Z <log>
            last_line = lines[-1]
            if " " in last_line:
                ts_part = last_line.split(" ")[0]
                # Trim nanoseconds to microseconds (Python only handles 6 digits)
                ts_trimmed = ts_part[:26] + "Z" if len(ts_part) > 26 else ts_part
                try:
                    _last_seen[cid] = ts_trimmed.replace("Z", "+00:00")
                except Exception:
                    _last_seen[cid] = datetime.utcnow().isoformat()
            else:
                _last_seen[cid] = datetime.utcnow().isoformat()

            # Strip timestamps from lines before sending
            clean_lines = []
            for line in lines:
                parts = line.split(" ", 1)
                clean_lines.append(parts[1] if len(parts) == 2 else line)

            logs_text = "\n".join(clean_lines)

            payload = {
                "container_id": cid[:12],
                "container_name": name,
                "logs": logs_text,
                "timestamp": datetime.utcnow().isoformat(),
            }

            ok = _post(INGEST_URL, payload)
            if ok:
                logger.info(f"📤 {name}: sent {len(clean_lines)} new lines")
            else:
                # Don't advance the pointer — retry same window next poll
                _last_seen.pop(cid, None)

        except Exception as e:
            logger.warning(f"Error reading logs from {name}: {e}")


# ---------------------------------------------------------------------------
# Docker Events stream (instant crash detection)
# ---------------------------------------------------------------------------
CRASH_EVENTS = {"die", "oom", "kill", "stop"}


def _legacy_watch_events(docker_client: docker.DockerClient):
    """
    Listen to Docker event stream. When a monitored container crashes/OOMs/dies,
    immediately flush its last 100 lines to the backend so RCA can start right away.
    Runs forever on a background thread.
    """
    logger.info("👁️  Docker events stream started (watching for crashes/OOMs...)")
    while True:
        try:
            for event in docker_client.events(
                decode=True,
                filters={"type": "container", "label": f"{MONITOR_LABEL}=true"},
            ):
                action = event.get("Action", "")
                if action not in CRASH_EVENTS:
                    continue

                cid   = event.get("id", "")[:12]
                attrs = event.get("Actor", {}).get("Attributes", {})
                name  = attrs.get("name", cid)
                exit_code = attrs.get("exitCode", "?")

                logger.warning(f"🚨 CRASH DETECTED: {name} | event={action} | exit={exit_code}")

                # Flush last 100 lines immediately — don't wait for next poll
                try:
                    container = docker_client.containers.get(cid)
                    crash_logs = container.logs(tail=100).decode("utf-8", errors="ignore")
                except Exception:
                    crash_logs = f"[opstron] Container {name} exited with code {exit_code}. Could not retrieve logs."

                payload = {
                    "container_id": cid,
                    "container_name": name,
                    "logs": crash_logs,
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": action,
                    "exit_code": exit_code,
                }

                ok = _post(INGEST_URL, payload)
                if ok:
                    logger.info(f"🚨 Crash logs for {name} forwarded to backend → RCA triggered")
                else:
                    logger.error(f"Failed to forward crash logs for {name}")

                # Reset delta pointer so next poll bootstraps fresh
                _last_seen.pop(cid, None)

        except Exception as e:
            logger.error(f"Events stream error: {e}. Reconnecting in 5s...")
            time.sleep(5)


def _event_reason(action: str, exit_code: str) -> str:
    if action == "oom":
        return "oom"
    if action == "kill":
        return "sigkill"
    if action == "die":
        return "exit_zero" if str(exit_code) == "0" else "exit_nonzero"
    if action == "stop":
        return "stopped"
    return action or "unknown"


def watch_events(docker_client: docker.DockerClient):
    """
    Listen to Docker event stream and send structured crash events to the backend.
    This definition intentionally supersedes the legacy log-only implementation
    above while keeping the old code nearby during the transition.
    """
    logger.info("Docker events stream started (watching for crashes/OOMs...)")
    while True:
        try:
            for event in docker_client.events(
                decode=True,
                filters={"type": "container", "label": f"{MONITOR_LABEL}=true"},
            ):
                action = event.get("Action", "")
                if action not in CRASH_EVENTS:
                    continue

                cid = event.get("id", "")[:12]
                attrs = event.get("Actor", {}).get("Attributes", {})
                name = attrs.get("name", cid)
                exit_code = attrs.get("exitCode", "?")

                logger.warning(f"CRASH DETECTED: {name} | event={action} | exit={exit_code}")

                restart_count = 0
                image_hash = ""
                try:
                    container = docker_client.containers.get(cid)
                    container.reload()
                    restart_count = container.attrs.get("RestartCount", 0)
                    image_hash = container.attrs.get("Image", "")
                    crash_logs = container.logs(tail=100).decode("utf-8", errors="ignore")
                except Exception:
                    crash_logs = f"[opstron] Container {name} exited with code {exit_code}. Could not retrieve logs."

                payload = {
                    "type": "container_crash",
                    "source": "agent",
                    "container_id": cid,
                    "container_name": name,
                    "timestamp": datetime.utcnow().isoformat(),
                    "exit_code": exit_code,
                    "reason": _event_reason(action, exit_code),
                    "image_hash": image_hash,
                    "restart_count": restart_count,
                    "logs": crash_logs,
                    "metadata": {
                        "event_action": action,
                        "hostname": HOSTNAME,
                    },
                }

                status = _post_status(EVENT_URL, payload)
                if status == 200:
                    logger.info(f"Structured crash event for {name} forwarded to backend")
                elif status == 404:
                    logger.warning("Backend does not support /agent/events yet. Falling back to log ingest.")
                    fallback_payload = {
                        "container_id": cid,
                        "container_name": name,
                        "logs": crash_logs,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    if _post(INGEST_URL, fallback_payload):
                        logger.info(f"Crash logs for {name} forwarded to legacy backend")
                    else:
                        logger.error(f"Failed to forward crash logs for {name}")
                else:
                    logger.error(f"Failed to forward structured crash event for {name}")

                _last_seen.pop(cid, None)

        except Exception as e:
            logger.error(f"Events stream error: {e}. Reconnecting in 5s...")
            time.sleep(5)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not API_KEY:
        logger.error("FATAL: OPSTRON_API_KEY is not set.")
        logger.error("Get your key from the OpsTron dashboard after logging in.")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info(f"  OpsTron Agent v{AGENT_VERSION}")
    logger.info(f"  Host    : {HOSTNAME}")
    logger.info(f"  Backend : {BACKEND_URL}")
    logger.info(f"  Filter  : label {MONITOR_LABEL}=true")
    logger.info(f"  Poll    : every {POLL_SECS}s (delta only)")
    logger.info("=" * 60)

    # Connect to Docker
    try:
        docker_client = docker.from_env()
        docker_client.ping()
        logger.info("✅ Connected to Docker socket")
    except Exception as e:
        logger.error(f"FATAL: Cannot connect to Docker socket: {e}")
        logger.error("Make sure to mount: -v /var/run/docker.sock:/var/run/docker.sock:ro")
        sys.exit(1)

    # Startup heartbeat
    send_heartbeat(docker_client)

    # Background: Docker events stream (crash detection)
    events_thread = threading.Thread(
        target=watch_events, args=(docker_client,), daemon=True, name="events-watcher"
    )
    events_thread.start()

    # Background: heartbeat every 60 seconds
    hb_thread = threading.Thread(
        target=heartbeat_loop, args=(docker_client,), daemon=True, name="heartbeat"
    )
    hb_thread.start()

    # Main loop: delta log polling
    logger.info(f"🔄 Starting delta log poll every {POLL_SECS}s...")
    consecutive_failures = 0

    while True:
        try:
            poll_logs(docker_client)
            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            wait = min(60, 5 * consecutive_failures)  # exponential-ish backoff, max 60s
            logger.error(f"Poll error ({consecutive_failures}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
            continue

        time.sleep(POLL_SECS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("OpsTron Agent shutting down gracefully.")
        sys.exit(0)
