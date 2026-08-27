
from doxygen import mime_for, normalize_doc_path, object_key, docs_config


def test_docs_requires_auth(client):
    res = client.get("/api/docs/index.html")
    assert res.status_code == 401


def test_docs_serves_mock_html_when_granted(client):
    login = client.post(
        "/api/auth/mock/okta",
        json={"email": "f18.pilot@boeing.com", "password": "HornetReady1"},
    )
    assert login.status_code == 200
    res = client.get("/api/docs/index.html")
    assert res.status_code == 200
    body = res.data.decode("utf-8", errors="replace")
    assert "F/A-18" in body or "html" in body.lower()
    meta = client.get("/api/docs/meta")
    assert meta.status_code == 200
    assert meta.get_json()["source"] == "mock"


def test_docs_denied_session_is_403(client):
    login = client.post(
        "/api/auth/mock/okta",
        json={"email": "visitor@example.com", "password": "NoClearance"},
    )
    assert login.status_code == 200
    res = client.get("/api/docs/index.html")
    assert res.status_code == 403


def test_normalize_doc_path_rejects_traversal():
    assert normalize_doc_path("../secret.txt") is None
    assert normalize_doc_path("index.html") == "index.html"
    assert normalize_doc_path("") == "index.html"
    assert normalize_doc_path("class_radar.html") == "class_radar.html"


def test_mime_and_object_key():
    assert "html" in mime_for("index.html")
    assert object_key("index.html", "html") == "html/index.html"
    cfg = docs_config()
    assert cfg["source"] == "mock"
