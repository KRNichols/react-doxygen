from classification import banner
from doxygen import sanitize_html


def test_mock_idp_forbidden_when_demo_login_off(client, monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN", "0")
    res = client.get("/api/auth/mock/okta")
    assert res.status_code == 403
    posted = client.post(
        "/api/auth/mock/okta",
        json={"email": "f18.pilot@boeing.com", "password": "HornetReady1"},
    )
    assert posted.status_code == 403


def test_get_logout_does_not_clear_session(client):
    login = client.post(
        "/api/auth/mock/okta",
        json={"email": "f18.pilot@boeing.com", "password": "HornetReady1"},
    )
    assert login.status_code == 200
    res = client.get("/api/auth/logout")
    assert res.status_code in (404, 405)
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["email"] == "f18.pilot@boeing.com"


def test_callback_without_matching_state_is_400(client):
    res = client.get("/api/auth/callback", query_string={"code": "abc", "state": "nope"})
    assert res.status_code == 400


def test_health_security_headers(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "script-src" in res.headers.get("Content-Security-Policy", "")


def test_custom_color_not_a_color_is_333333(monkeypatch):
    monkeypatch.delenv("CLASSIFICATION_TEXT", raising=False)
    monkeypatch.setenv("CLASSIFICATION", "CUSTOM")
    monkeypatch.setenv("CLASSIFICATION_CUSTOM_COLOR", "not-a-color")
    assert banner()["color"] == "#333333"


def test_sanitize_html_drops_onclick_javascript_script():
    raw = (
        '<p onclick="alert(1)">'
        '<a href="javascript:alert(1)">x</a>'
        "<script>alert(1)</script>"
        "ok</p>"
    )
    out = sanitize_html(raw)
    text = out.decode("utf-8") if isinstance(out, (bytes, bytearray)) else out
    assert "onclick" not in text
    assert "javascript:" not in text
    assert "<script" not in text.lower()
