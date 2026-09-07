"""
Tests for configuration and the authentication boundary.

These cover the settings logic that has actually broken this project — CORS
origins silently dropping FRONTEND_URL, and production refusing to start
without its required secrets — plus a check that the demo did not accidentally
open up the authenticated product.
"""

import pytest

from app.core.config.settings import Settings


class TestCorsOrigins:
    def test_frontend_url_is_trusted_even_when_an_allowlist_is_configured(self):
        # Regression: cors_origins() used `configured or [frontend]`, so setting
        # CORS_ALLOWED_ORIGINS silently dropped FRONTEND_URL — the exact origin
        # the OAuth callback redirects the browser back to.
        s = Settings(
            ENVIRONMENT="production",
            CORS_ALLOWED_ORIGINS="https://example.com",
            FRONTEND_URL="https://hitanshuthegr8.github.io/OpsTron",
        )
        origins = s.cors_origins()
        assert "https://example.com" in origins
        assert "https://hitanshuthegr8.github.io" in origins

    def test_origin_is_normalised_to_scheme_and_host(self):
        # A CORS origin has no path; leaving one on would never match a browser's
        # Origin header.
        s = Settings(ENVIRONMENT="production", FRONTEND_URL="https://x.github.io/OpsTron/")
        assert s.cors_origins() == ["https://x.github.io"]

    def test_localhost_is_allowed_in_development_only(self):
        dev = Settings(ENVIRONMENT="development", FRONTEND_URL="http://localhost:8080")
        assert any("localhost" in o for o in dev.cors_origins())

        prod = Settings(ENVIRONMENT="production", FRONTEND_URL="https://x.github.io")
        assert not any("localhost" in o for o in prod.cors_origins())

    def test_dev_origin_regex_matches_any_localhost_port_but_prod_has_none(self):
        import re

        dev = Settings(ENVIRONMENT="development")
        pattern = dev.cors_origin_regex()
        assert pattern is not None
        # Vite silently moves to another port when its default is taken; the
        # regex exists so that does not break every API call.
        for origin in ["http://localhost:8080", "http://localhost:8081", "http://127.0.0.1:5173"]:
            assert re.fullmatch(pattern, origin), origin
        assert re.fullmatch(pattern, "https://evil.example") is None

        assert Settings(ENVIRONMENT="production").cors_origin_regex() is None


class TestProductionStartupValidation:
    def test_production_refuses_to_start_without_required_secrets(self):
        s = Settings(ENVIRONMENT="production", SUPABASE_URL="", SUPABASE_SERVICE_KEY="", WEBHOOK_SECRET="")
        with pytest.raises(RuntimeError) as exc:
            s.validate_startup()
        assert "SUPABASE_URL" in str(exc.value)

    def test_production_refuses_insecure_webhooks(self):
        s = Settings(
            ENVIRONMENT="production",
            SUPABASE_URL="https://x.supabase.co",
            SUPABASE_SERVICE_KEY="k",
            WEBHOOK_SECRET="s",
            ALLOW_INSECURE_WEBHOOKS=True,
        )
        with pytest.raises(RuntimeError):
            s.validate_startup()

    def test_development_does_not_validate(self):
        Settings(ENVIRONMENT="development").validate_startup()  # must not raise


class TestAuthBoundaryStillHolds:
    """The demo is public. The product must not have become public with it."""

    @pytest.mark.parametrize("path", ["/rca-history", "/deployment-history", "/auth/me"])
    def test_authenticated_endpoints_still_reject_anonymous_callers(self, client, path):
        assert client.get(path).status_code in (401, 403)

    def test_runbook_upload_is_not_anonymous(self, client):
        # Writes to the shared vector store; must never be open.
        assert client.post("/runbooks/upload").status_code in (401, 403, 422)
