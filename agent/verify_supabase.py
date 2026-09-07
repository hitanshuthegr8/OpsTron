"""
Verify the Supabase wiring end to end.

Reads SUPABASE_URL / SUPABASE_SERVICE_KEY from the app's own settings, so no
credential is ever typed on a command line or printed. Run:

    .venv/Scripts/python.exe verify_supabase.py
"""
import socket
import sys
from urllib.parse import urlparse

import httpx

from app.core.config.settings import settings

EXPECTED = [
    "agent_events", "alert_events", "alert_settings", "chat_messages",
    "commits", "connected_repos", "deployments", "opstronic_users",
    "rca_logs", "user_profiles", "vapi_calls",
]


def main() -> int:
    url, key = settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY
    if not url or not key:
        print("FAIL  SUPABASE_URL / SUPABASE_SERVICE_KEY not set in agent/.env")
        return 1

    shape = "JWT (legacy)" if key.count(".") == 2 else (
        "sb_secret_ (current)" if key.startswith("sb_secret_") else "unrecognised"
    )
    if key.startswith("sb_publishable_"):
        print("FAIL  that is the PUBLISHABLE key. The backend bypasses RLS and "
              "needs the SECRET key.")
        return 1
    print(f"key shape : {shape}")

    host = urlparse(url).hostname
    try:
        socket.gethostbyname(host)
        print(f"dns       : {host} resolves")
    except OSError as exc:
        print(f"FAIL  {host} does not resolve ({exc}). Wrong or deleted project.")
        return 1

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    missing, ok = [], []
    for table in EXPECTED:
        r = httpx.get(f"{url}/rest/v1/{table}",
                      params={"select": "*", "limit": 1},
                      headers=headers, timeout=30)
        if r.status_code == 200:
            ok.append(table)
        elif r.status_code in (401, 403):
            print(f"FAIL  auth rejected on {table}: {r.status_code} {r.text[:120]}")
            return 1
        else:
            missing.append(f"{table} ({r.status_code})")

    print(f"tables ok : {len(ok)}/{len(EXPECTED)}")
    if missing:
        print("MISSING   : " + ", ".join(missing))
        print("\nRe-run agent/app/db/schema.sql in the Supabase SQL Editor.")
        return 1

    print("\nPASS  Supabase is wired up correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
