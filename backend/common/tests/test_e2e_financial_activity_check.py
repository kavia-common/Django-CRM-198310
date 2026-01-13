"""
CI-focused test for the custom Django management command `e2e_financial_activity_check`.

This test is intentionally "black box":
- runs DB setup in a deterministic SQLite context
- invokes the management command
- asserts the command completes successfully and prints expected summary markers

It is meant to fail on regressions in:
- migrations
- admin-only financial endpoint behavior/redaction
- activity log creation and admin activity log API pagination/filtering
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings


@pytest.mark.django_db(transaction=True)
def test_e2e_financial_activity_check_command_succeeds_and_prints_summary_markers():
    """
    Run the management command and assert:
    - no exception is raised
    - expected summary section exists
    - all checks report OK (no FAIL markers)

    Notes:
    - Django's test client uses HTTP_HOST='testserver'. We must allow it via ALLOWED_HOSTS.
    - The `activity` app currently has no migrations; under SQLite we must ensure its tables are created.
      We do that by running `migrate --run-syncdb` before invoking the command.
    """
    # Ensure 'testserver' host is accepted in this test run.
    allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []))
    if "testserver" not in allowed_hosts:
        allowed_hosts.append("testserver")

    # Use in-memory SQLite for speed; the command itself runs migrations, but we also need --run-syncdb
    # so tables for apps without migrations (e.g. activity_log) are created.
    with override_settings(ALLOWED_HOSTS=allowed_hosts):
        # Create tables for unmigrated apps (activity) + apply migrations for migrated apps.
        call_command("migrate", "--noinput", "--run-syncdb", verbosity=0)

        out = StringIO()
        err = StringIO()

        # Invoke the E2E command. Any internal failures call SystemExit(1) or raise AssertionError.
        call_command(
            "e2e_financial_activity_check",
            stdout=out,
            stderr=err,
            verbosity=0,
        )

    stdout = out.getvalue()
    stderr = err.getvalue()

    # High-signal markers emitted by the command.
    assert "E2E verification results" in stdout, f"Missing summary header. stdout={stdout} stderr={stderr}"

    # Ensure all expected check names appear (guards against command being stubbed or exiting early).
    expected_checks = [
        "migrations:",
        "seed_users_orgs:",
        "seed_account_financial:",
        "financial_admin_get_patch:",
        "financial_user_forbidden_isolation:",
        "activity_logs_present_sanitized:",
        "admin_activity_logs_api:",
    ]
    for marker in expected_checks:
        assert marker in stdout, f"Missing marker {marker!r}. stdout={stdout} stderr={stderr}"

    # Hard fail on any reported FAIL line.
    assert "FAIL" not in stdout, f"Command reported failure(s). stdout={stdout} stderr={stderr}"
