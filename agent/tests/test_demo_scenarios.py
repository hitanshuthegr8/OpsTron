"""
Tests for the demo fixture data and the demo endpoints.

The demo is the only unauthenticated surface that spends money (each analysis is
an LLM call), so the properties worth asserting are about its *boundary*: that
an unknown id cannot reach the pipeline, that the rate limit engages, and that
the response always states which half of it is simulated.
"""

import pytest

from app.demo.scenarios import (
    DEFAULT_SCENARIO_ID,
    SCENARIOS,
    briefing,
    get_scenario,
    list_scenarios,
)


class TestScenarioData:
    def test_default_scenario_exists(self):
        assert DEFAULT_SCENARIO_ID in SCENARIOS

    def test_every_scenario_has_the_fields_the_pipeline_reads(self):
        # orchestrator.analyze() and the demo router index these directly, so a
        # missing key is a 500 at request time rather than an import error.
        required = {
            "id", "title", "summary", "service", "repo", "severity",
            "deployed_at", "first_error_at", "impact", "log_text",
            "commits", "signals",
        }
        for sid, scenario in SCENARIOS.items():
            assert required <= scenario.keys(), f"{sid} missing {required - scenario.keys()}"

    def test_log_text_contains_the_signal_the_narrative_depends_on(self):
        # If this string disappears the LogAgent has nothing to key on and the
        # whole demo story silently degrades into a vague RCA.
        log = SCENARIOS[DEFAULT_SCENARIO_ID]["log_text"]
        assert "TimeoutError" in log
        assert "connection pool exhausted" in log

    def test_culprit_commit_is_present_and_plausible(self):
        commits = SCENARIOS[DEFAULT_SCENARIO_ID]["commits"]
        assert len(commits) >= 2, "need decoys, or blaming the only commit is trivial"
        culprit = commits[0]
        assert culprit["sha"] == "a7f3c21"
        # The culprit must touch the subsystem the logs implicate, otherwise the
        # model has no basis to connect them and the demo becomes luck.
        assert any("pool" in f for f in culprit["files_changed"])

    def test_culprit_precedes_the_first_error(self):
        s = SCENARIOS[DEFAULT_SCENARIO_ID]
        assert s["deployed_at"] < s["first_error_at"], "deploy must precede the incident"

    def test_get_scenario_rejects_unknown_ids(self):
        # This lookup is the demo's security boundary.
        assert get_scenario("nope") is None
        assert get_scenario("../../etc/passwd") is None
        assert get_scenario("") is None

    def test_list_scenarios_omits_bulky_log_text(self):
        for s in list_scenarios():
            assert "log_text" not in s

    def test_briefing_exposes_no_unexpected_keys(self):
        b = briefing(SCENARIOS[DEFAULT_SCENARIO_ID])
        assert set(b) == {
            "id", "title", "summary", "service", "repo", "severity",
            "deployed_at", "first_error_at", "impact", "signals",
            "log_excerpt", "commits",
        }


class TestDemoEndpoints:
    def test_list_endpoint_is_public(self, client):
        r = client.get("/demo/scenarios")
        assert r.status_code == 200
        body = r.json()
        assert body["default"] == DEFAULT_SCENARIO_ID
        assert len(body["scenarios"]) >= 1

    def test_briefing_endpoint_is_public(self, client):
        r = client.get(f"/demo/scenarios/{DEFAULT_SCENARIO_ID}")
        assert r.status_code == 200
        assert r.json()["incident"]["service"] == "checkout-api"

    def test_unknown_scenario_is_404_not_500(self, client):
        assert client.get("/demo/scenarios/does-not-exist").status_code == 404

    def test_unknown_scenario_analysis_is_refused_before_the_pipeline_runs(self, client):
        # A 404 here proves no LLM call was made for an unknown id. If this ever
        # returns 503 or 500 instead, the id is reaching the orchestrator and the
        # boundary has been broken.
        r = client.post("/demo/scenarios/does-not-exist/analyze")
        assert r.status_code == 404

    def test_provenance_is_always_present_and_non_empty(self, client):
        for path in ["/demo/scenarios", f"/demo/scenarios/{DEFAULT_SCENARIO_ID}"]:
            p = client.get(path).json()["provenance"]
            assert p["simulated"] and p["generated_live"]
            # A visitor must be told the incident is fictional.
            assert "fictional" in p["note"].lower()


class TestRateLimit:
    def test_limiter_blocks_past_the_configured_ceiling(self):
        from app.utils.rate_limit import SlidingWindowLimiter

        limiter = SlidingWindowLimiter()
        assert all(limiter.allow("k", 3) for _ in range(3))
        assert limiter.allow("k", 3) is False
        # Buckets are per key, so one caller cannot exhaust another's quota.
        assert limiter.allow("other", 3) is True

    def test_retry_after_is_positive_once_blocked(self):
        from app.utils.rate_limit import SlidingWindowLimiter

        limiter = SlidingWindowLimiter()
        limiter.allow("k", 1)
        assert limiter.allow("k", 1) is False
        assert limiter.retry_after("k") > 0


@pytest.mark.integration
class TestDemoPipelineIntegration:
    """Costs a real Groq call. Run with: pytest -m integration"""

    def test_analysis_returns_a_usable_report(self, client):
        r = client.post(f"/demo/scenarios/{DEFAULT_SCENARIO_ID}/analyze")
        assert r.status_code == 200, r.text
        report = r.json()["report"]
        assert report.get("root_cause")
        assert report["root_cause"] != "analysis_failed"
        assert report.get("confidence") in {"low", "medium", "high"}
        assert report.get("recommended_actions")
