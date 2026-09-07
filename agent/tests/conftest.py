"""
Shared fixtures.

The unit tests here must not touch Groq, Supabase or GitHub. Anything that
would leave the process is either stubbed or the test is marked `integration`.
That is what makes the default suite deterministic and free to run in CI.
"""

import os
import sys
from pathlib import Path

import pytest

# The app is imported as `app.*`, which requires the agent/ directory on the
# path when pytest is invoked from anywhere other than agent/ itself.
AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

# Keep tests off the production config even if a developer's .env is populated.
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture
def client():
    """FastAPI TestClient over the real application object."""
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def demo_log_signals():
    """The signals a correct LogAgent parse should surface from the demo fixture."""
    return ["TimeoutError", "connection pool exhausted"]
