"""Flask test client fixtures for the portal API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["OKTA_ISSUER"] = ""
os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET", "test-secret")

import pytest
from app import app


@pytest.fixture
def mailbox(tmp_path, monkeypatch):
    """
    What: Point signup_mail.MAILBOX at a per-test temporary directory.
    Why: Tests must not write applicant .eml files into the real mailbox.
    Who: Signup and mailbox listing tests via the client fixture.
    Where: Isolated tmp_path/mailbox for the duration of one test.
    How: mkdir then monkeypatch the MAILBOX Path used by send_signup_notice.
    """
    box = tmp_path / "mailbox"
    box.mkdir()
    import signup_mail

    monkeypatch.setattr(signup_mail, "MAILBOX", box)
    return box


@pytest.fixture
def client(mailbox, monkeypatch):
    """
    What: In-process Flask test client with an isolated mailbox.
    Why: Portal API tests must use the Flask client, not a live HTTP server.
    Who: Every test that takes a client argument.
    Where: app.test_client after TESTING=True.
    How: Turn DEMO_LOGIN on for the suite, then yield the client inside a context so the session cookie stays in-process.
    """
    monkeypatch.setenv("DEMO_LOGIN", "1")
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def login(client, email, password):
    """
    What: POST demo credentials to the mock IdP as JSON.
    Why: Granted and denied tests share one login hop.
    Who: Auth and docs tests that need a session cookie.
    Where: POST /api/auth/mock/okta with Accept application/json.
    How: Send {email, password} and return the Flask response.
    """
    return client.post(
        "/api/auth/mock/okta",
        json={"email": email, "password": password},
        headers={"Accept": "application/json"},
    )
