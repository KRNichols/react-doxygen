def test_bad_password_is_401(client):
    res = client.post(
        "/api/auth/mock/okta",
        json={"email": "f18.pilot@boeing.com", "password": "wrong-password"},
    )
    assert res.status_code == 401
    body = res.get_json()
    assert "error" in body


def test_granted_login_is_200(client):
    res = client.post(
        "/api/auth/mock/okta",
        json={"email": "f18.pilot@boeing.com", "password": "HornetReady1"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["clearance"] == "granted"
    assert data["email"] == "f18.pilot@boeing.com"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["clearance"] == "granted"


def test_denied_login_completes_with_session(client):
    res = client.post(
        "/api/auth/mock/okta",
        json={"email": "visitor@example.com", "password": "NoClearance"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["clearance"] == "denied"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["clearance"] == "denied"
    assert me.get_json()["email"] == "visitor@example.com"


def test_me_without_session_is_401(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["idp"] == "mock"


def test_logout_clears_session(client):
    client.post(
        "/api/auth/mock/okta",
        json={"email": "f18.pilot@boeing.com", "password": "HornetReady1"},
    )
    res = client.post("/api/auth/logout", headers={"Accept": "application/json"})
    assert res.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
