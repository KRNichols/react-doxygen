from signup_mail import validate_signup


def test_signup_writes_mailbox(client, mailbox):
    res = client.post(
        "/api/auth/signup",
        json={
            "name": "Test Pilot",
            "email": "test.pilot@example.com",
            "organization": "Demo",
        },
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["mocked"] is True
    files = list(mailbox.glob("*.eml"))
    assert files
    raw = files[0].read_text(encoding="utf-8", errors="replace")
    assert "test.pilot@example.com" in raw
    listed = client.get("/api/auth/signup/mailbox")
    assert listed.status_code == 200
    payload = listed.get_json()
    assert payload["mocked"] is True
    assert payload["messages"]
    assert any("test.pilot@example.com" in str(item) for item in payload["messages"])


def test_signup_rejects_empty(client):
    res = client.post("/api/auth/signup", json={"name": "", "email": ""})
    assert res.status_code == 400


def test_validate_signup_requires_json():
    applicant, err = validate_signup(None)
    assert applicant is None
    assert err
