from copy_text import get_copy
from signup_mail import list_mailbox, validate_signup


def test_login_authorize_redirect(client):
    res = client.get("/api/auth/login")
    assert res.status_code in (302, 303)
    assert "/api/auth/mock/okta" in res.headers.get("Location", "")


def test_mock_okta_get_json(client):
    res = client.get("/api/auth/mock/okta", headers={"Accept": "application/json"})
    assert res.status_code == 200
    assert res.get_json()["idp"] == "mock"


def test_signup_config(client):
    res = client.get("/api/auth/signup/config")
    assert res.status_code == 200
    assert "notifyEmail" in res.get_json()


def test_signup_mailbox_dev(client, mailbox):
    res = client.get("/api/auth/signup/mailbox")
    assert res.status_code == 200
    data = res.get_json()
    assert data["mocked"] is True
    assert "messages" in data


def test_copy_env_overlay(monkeypatch):
    monkeypatch.setenv("COPY_LOGIN_TITLE", "Overlay Title")
    data = get_copy(force=True)
    assert data["login"]["title"] == "Overlay Title"
    monkeypatch.delenv("COPY_LOGIN_TITLE", raising=False)
    get_copy(force=True)


def test_validate_signup_bad_email():
    applicant, err = validate_signup({"name": "A", "email": "not-an-email"})
    assert applicant is None
    assert err


def test_list_mailbox_empty(mailbox):
    assert list_mailbox() == []
