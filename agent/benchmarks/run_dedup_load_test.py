"""
Dedup + cooldown load test — how much noise the pipeline actually suppresses.

Run:
    cd agent
    .venv/Scripts/python.exe benchmarks/run_dedup_load_test.py

Simulates three containers in a crashloop emitting events over a fixed window,
pushes them through the real `EventDeduplicator` and `AlertCooldown`, and reports
how many survive each stage.

The clock is driven by a deterministic fake rather than `sleep`, so the run takes
milliseconds and produces the same answer every time. That matters: a suppression
ratio measured against wall-clock timing would drift with machine load, and a
number you cannot reproduce is not a measurement.

The ratio is a function of the input rate and the window sizes, not a property of
the code alone. The parameters below are stated explicitly so the number can be
read in context.
"""

import sys
from itertools import count
from pathlib import Path
from unittest.mock import patch

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

from app.core.dedup import AlertCooldown, EventDeduplicator  # noqa: E402
from app.models.event_models import EnrichedEvent  # noqa: E402

# --- Scenario parameters (stated, not hidden) -----------------------------
CONTAINERS = 3          # three services crashlooping simultaneously
DURATION_SECONDS = 220  # length of the incident
EVENT_INTERVAL = 2.7    # seconds between emissions per container
DEDUP_WINDOW = 60       # EventDeduplicator default
COOLDOWN_WINDOW = 300   # AlertCooldown default
USER = "gh-1"


def build_stream():
    """One event per container per interval, as a crashloop would produce."""
    stream = []
    t = 0.0
    while t < DURATION_SECONDS:
        for i in range(CONTAINERS):
            stream.append((
                t,
                EnrichedEvent(
                    type="container_crash",
                    github_id=USER,
                    service_name=f"svc-{i}",
                    container_id=f"c{i}",
                    container_name=f"svc-{i}",
                    reason="crashloop",
                    exit_code="1",
                    restart_count=1,
                ),
            ))
        t += EVENT_INTERVAL
    return stream


def main() -> int:
    stream = build_stream()
    clock = {"t": 0.0}

    dedup = EventDeduplicator(window_seconds=DEDUP_WINDOW)
    cooldown = AlertCooldown(window_seconds=COOLDOWN_WINDOW)

    survived_dedup = 0
    alerts_sent = 0

    # Both components read time.time() internally; drive it deterministically.
    with patch("app.core.dedup.time.time", lambda: clock["t"]):
        for offset, event in stream:
            clock["t"] = offset
            if dedup.is_duplicate(event):
                continue
            survived_dedup += 1
            if cooldown.can_alert(USER, event.service_name):
                cooldown.record_alert(USER, event.service_name)
                alerts_sent += 1

    raw = len(stream)
    print("Scenario")
    print(f"  containers            : {CONTAINERS} crashlooping")
    print(f"  duration              : {DURATION_SECONDS}s")
    print(f"  emission interval     : {EVENT_INTERVAL}s per container")
    print(f"  dedup window          : {DEDUP_WINDOW}s")
    print(f"  cooldown window       : {COOLDOWN_WINDOW}s per service")
    print()
    print("Result")
    print(f"  raw events emitted    : {raw}")
    print(f"  reached the RCA layer : {survived_dedup}")
    print(f"  pages actually sent   : {alerts_sent}")
    print()
    print(f"  dedup ratio           : {raw / survived_dedup:.1f}:1 "
          f"({100 * (1 - survived_dedup / raw):.1f}% suppressed)")
    print(f"  raw -> page ratio     : {raw / alerts_sent:.1f}:1 "
          f"({100 * (1 - alerts_sent / raw):.1f}% suppressed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
