"""
Regression tests for the two measured claims.

These pin behaviour that was previously recorded only as prose in LEARNINGS.md,
which meant the numbers could drift without anything failing.

The retrieval benchmark is marked `integration`: it builds a real vector store.
The dedup tests are pure and run in the default suite.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.dedup import AlertCooldown, EventDeduplicator
from app.models.event_models import EnrichedEvent

BENCHMARKS = Path(__file__).resolve().parent.parent / "benchmarks"


def _event(container: str, service: str) -> EnrichedEvent:
    return EnrichedEvent(
        type="container_crash",
        github_id="gh-1",
        service_name=service,
        container_id=container,
        container_name=service,
        reason="crashloop",
        exit_code="1",
    )


class TestDedupWindow:
    def test_window_is_fixed_not_sliding(self):
        """
        Regression: `is_duplicate` used to stamp the timestamp on every call,
        including duplicates. That turned the 60s fixed window into a sliding
        one that never expired, so a continuous crashloop admitted exactly one
        event ever and the cooldown layer below was unreachable.
        """
        clock = {"t": 0.0}
        dedup = EventDeduplicator(window_seconds=60)
        admitted = 0

        with patch("app.core.dedup.time.time", lambda: clock["t"]):
            # One event every 2s for 200s — well inside the window each time.
            for offset in range(0, 200, 2):
                clock["t"] = float(offset)
                if not dedup.is_duplicate(_event("c1", "svc")):
                    admitted += 1

        # 200s / 60s window => admissions at t=0, 60, 120, 180
        assert admitted == 4, (
            f"expected one admission per 60s window, got {admitted}. "
            "If this is 1, the window is sliding again."
        )

    def test_distinct_containers_do_not_suppress_each_other(self):
        dedup = EventDeduplicator(window_seconds=60)
        assert dedup.is_duplicate(_event("c1", "svc")) is False
        assert dedup.is_duplicate(_event("c2", "svc")) is False

    def test_identical_event_inside_window_is_suppressed(self):
        clock = {"t": 0.0}
        dedup = EventDeduplicator(window_seconds=60)
        with patch("app.core.dedup.time.time", lambda: clock["t"]):
            assert dedup.is_duplicate(_event("c1", "svc")) is False
            clock["t"] = 30.0
            assert dedup.is_duplicate(_event("c1", "svc")) is True


class TestCooldownIsReachable:
    def test_cooldown_limits_pages_for_a_service(self):
        """The layer that only matters once dedup admits more than one event."""
        clock = {"t": 0.0}
        cooldown = AlertCooldown(window_seconds=300)
        pages = 0

        with patch("app.core.dedup.time.time", lambda: clock["t"]):
            for offset in (0, 60, 120, 180, 400):
                clock["t"] = float(offset)
                if cooldown.can_alert("gh-1", "svc"):
                    cooldown.record_alert("gh-1", "svc")
                    pages += 1

        # t=0 pages; 60/120/180 are inside the 300s window; 400 pages again.
        assert pages == 2


class TestSuppressionRatio:
    def test_crashloop_load_collapses_as_measured(self):
        """Pins the ratio quoted publicly. 3 containers, 220s, 2.7s interval."""
        clock = {"t": 0.0}
        dedup = EventDeduplicator(window_seconds=60)
        cooldown = AlertCooldown(window_seconds=300)
        raw = admitted = paged = 0

        with patch("app.core.dedup.time.time", lambda: clock["t"]):
            t = 0.0
            while t < 220:
                for i in range(3):
                    clock["t"] = t
                    raw += 1
                    ev = _event(f"c{i}", f"svc-{i}")
                    if dedup.is_duplicate(ev):
                        continue
                    admitted += 1
                    if cooldown.can_alert("gh-1", ev.service_name):
                        cooldown.record_alert("gh-1", ev.service_name)
                        paged += 1
                t += 2.7

        assert raw == 246
        assert admitted == 12, f"suppression drifted: {raw} -> {admitted}"
        assert paged == 3, "one page per service over a 300s cooldown"
        assert raw / admitted > 20


@pytest.mark.integration
class TestRetrievalBenchmark:
    """Builds a real vector store. Run with: pytest -m integration"""

    @pytest.mark.asyncio
    async def test_precision_at_1_holds(self):
        from app.core.agents.runbook_agent import RunbookAgent
        from app.db.load_runbooks import load_runbooks

        spec = json.loads((BENCHMARKS / "runbook_queries.json").read_text(encoding="utf-8"))
        load_runbooks()
        agent = RunbookAgent()

        hits = 0
        for q in spec["queries"]:
            results = await agent.search([q["query"]])
            top = results[0]["title"].strip().lower().replace(" ", "_") if results else ""
            if top == q["expected"]:
                hits += 1

        # Pins the published figure. Raise it when retrieval genuinely improves;
        # do not lower it to make a regression pass.
        assert hits >= 8, f"precision@1 regressed to {hits}/{len(spec['queries'])}"
