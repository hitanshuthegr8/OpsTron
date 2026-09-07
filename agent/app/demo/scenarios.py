"""
Seeded incident scenarios for the public demo.

WHAT IS SIMULATED AND WHAT IS NOT
---------------------------------
Everything in this module is fixture data: the log text, the commit history and
the deployment metadata describe an incident that never happened, in a service
that does not exist.

Everything *downstream* of it is the real system. The demo endpoint feeds these
fixtures to the same `RCAOrchestrator` the authenticated product uses, so the
log analysis, the runbook retrieval (a real ChromaDB similarity search over the
real runbooks in `runbooks/`) and the root-cause synthesis (a real Groq call)
are generated live, on request, exactly as they would be for a production
incident.

That split is deliberate and is surfaced to the client in the API response, so a
visitor can tell which half of the screen is a fixture and which half is the
system working. Do not blur it: a demo that fabricates the RCA and presents it
as system output is a lie, not a demo.

WHY THE COMMITS ARE SEEDED TOO
------------------------------
`CommitAgent` normally fetches live commits from a GitHub repo. Pointing it at
this project's own repository would attribute real OpsTron commits ("fix(schema):
make schema.sql re-runnable") to a checkout-api connection-pool bug — evidence
that reads as incoherent and, worse, wrong. Seeding the commit history keeps the
narrative honest and self-consistent, and is labelled as simulated like the rest.
"""

from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------
# Scenario 1 — deployment regression exhausting a database connection pool
# --------------------------------------------------------------------------
# The story this tells, end to end:
#   a deploy lowers the pool ceiling and adds an un-awaited retry
#   -> latency rises under normal traffic
#   -> connections are held longer than the acquire timeout
#   -> the pool saturates and requests queue
#   -> checkout starts returning 500s on the payment path
# Every signal the pipeline needs is present in the log text: an explicit
# exception type, a stack frame naming the file, the pool size and waiter count,
# and the user-facing symptom.

_POOL_EXHAUSTION_LOG = """\
2026-03-11 14:02:03 INFO  checkout-api v4.11.0 started (pid 1, workers=4)
2026-03-11 14:02:03 INFO  db pool initialised min=2 max=10 acquire_timeout=2s
2026-03-11 14:08:41 INFO  checkout-api 200 POST /v1/charge 142ms
2026-03-11 14:11:07 WARN  db pool acquire slow: waited 1180ms (in_use=9/10 waiters=3)
2026-03-11 14:11:52 WARN  db pool acquire slow: waited 1840ms (in_use=10/10 waiters=11)
2026-03-11 14:12:14 ERROR Traceback (most recent call last):
  File "/app/checkout/payment.py", line 88, in charge_card
    conn = await pool.acquire(timeout=2)
  File "/app/db/pool.py", line 41, in acquire
    raise TimeoutError("connection pool exhausted (size=10, waiters=37)")
TimeoutError: connection pool exhausted (size=10, waiters=37)
2026-03-11 14:12:14 ERROR checkout-api 500 POST /v1/charge upstream_db timeout req_id=7c1f9ae2
2026-03-11 14:12:15 ERROR checkout-api 500 POST /v1/charge upstream_db timeout req_id=b42d1f08
2026-03-11 14:12:18 WARN  retry storm detected: 214 retries in 30s on /v1/charge
2026-03-11 14:12:31 ERROR Traceback (most recent call last):
  File "/app/checkout/payment.py", line 88, in charge_card
    conn = await pool.acquire(timeout=2)
  File "/app/db/pool.py", line 41, in acquire
    raise TimeoutError("connection pool exhausted (size=10, waiters=52)")
TimeoutError: connection pool exhausted (size=10, waiters=52)
2026-03-11 14:12:33 ERROR checkout-api 500 POST /v1/charge upstream_db timeout req_id=9de0c714
2026-03-11 14:13:02 CRIT  error_rate=38.4% over 60s window (baseline 0.2%)
"""

_POOL_EXHAUSTION_COMMITS: List[Dict[str, Any]] = [
    {
        "sha": "a7f3c21",
        "author": "priya.n",
        "date": "2026-03-11T13:54:00Z",
        "message": "perf(db): cap pool at 10 and add retry on acquire timeout",
        "files_changed": ["db/pool.py", "checkout/payment.py", "config/database.yaml"],
        "additions": 34,
        "deletions": 11,
    },
    {
        "sha": "5b18e90",
        "author": "marcus.l",
        "date": "2026-03-11T11:20:00Z",
        "message": "chore(deps): bump httpx 0.27 -> 0.28",
        "files_changed": ["requirements.txt"],
        "additions": 1,
        "deletions": 1,
    },
    {
        "sha": "c904ad5",
        "author": "priya.n",
        "date": "2026-03-10T16:47:00Z",
        "message": "test(checkout): cover partial-refund rounding",
        "files_changed": ["tests/test_refunds.py"],
        "additions": 88,
        "deletions": 0,
    },
]


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "pool-exhaustion": {
        "id": "pool-exhaustion",
        "title": "Checkout failures after a deploy",
        "summary": (
            "Twelve minutes after v4.11.0 shipped, checkout-api began returning "
            "500s on the payment endpoint and the error rate climbed from 0.2% "
            "to 38%."
        ),
        "service": "checkout-api",
        "repo": "acme/checkout-api",
        "severity": "critical",
        "deployed_at": "2026-03-11T13:58:00Z",
        "first_error_at": "2026-03-11T14:12:14Z",
        "impact": "38.4% of payment requests failing",
        "log_text": _POOL_EXHAUSTION_LOG,
        "commits": _POOL_EXHAUSTION_COMMITS,
        # What a visitor should be able to work out for themselves before the
        # RCA appears. Shown in the UI as the incident briefing.
        "signals": [
            "TimeoutError: connection pool exhausted (size=10, waiters=52)",
            "Error rate 38.4% over 60s (baseline 0.2%)",
            "Deploy v4.11.0 landed 14 minutes before the first error",
        ],
    },
}

DEFAULT_SCENARIO_ID = "pool-exhaustion"


def list_scenarios() -> List[Dict[str, Any]]:
    """Public metadata for every scenario, without the bulky log text."""
    return [
        {
            "id": s["id"],
            "title": s["title"],
            "summary": s["summary"],
            "service": s["service"],
            "severity": s["severity"],
            "impact": s["impact"],
            "is_default": s["id"] == DEFAULT_SCENARIO_ID,
        }
        for s in SCENARIOS.values()
    ]


def get_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    """
    Look a scenario up by id.

    The caller must treat a None return as "unknown id" and refuse the request.
    This dict lookup is the security boundary for the whole demo surface: the
    only visitor-supplied value that reaches the RCA pipeline is a key into this
    fixed mapping, so no attacker-controlled text can ever become part of an LLM
    prompt or an outbound request.
    """
    return SCENARIOS.get(scenario_id)


def briefing(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """The 'what happened' panel — fixture data, no analysis."""
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "summary": scenario["summary"],
        "service": scenario["service"],
        "repo": scenario["repo"],
        "severity": scenario["severity"],
        "deployed_at": scenario["deployed_at"],
        "first_error_at": scenario["first_error_at"],
        "impact": scenario["impact"],
        "signals": scenario["signals"],
        "log_excerpt": scenario["log_text"],
        "commits": scenario["commits"],
    }
