
from copy_text import fill, get_copy


def test_copy_json_endpoint(client):
    res = client.get("/api/copy")
    assert res.status_code == 200
    data = res.get_json()
    assert "brand" in data
    assert data["brand"]["programName"]
    assert "notifyEmail" in data
    assert "login" in data
    assert data["classification"]["text"] == "UNCLASSIFIED"
    assert data["classification"]["color"] == "#007A33"


def test_demo_login_off_hides_hints(client, monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN", "0")
    res = client.get("/api/copy")
    assert res.status_code == 200
    data = res.get_json()
    assert data["demoLogin"] is False
    assert "hintAuthorizedPassword" not in (data.get("login") or {})


def test_demo_login_flag(client, monkeypatch):
    expected = {"1": True, "yes": True, "true": True, "0": False}
    for raw, flag in expected.items():
        monkeypatch.setenv("DEMO_LOGIN", raw)
        res = client.get("/api/copy")
        assert res.status_code == 200
        assert res.get_json()["demoLogin"] is flag


def test_fill_replaces_placeholders():
    assert fill("Hello {name}", name="Viper") == "Hello Viper"
    assert fill("{x}", x=None) == ""


def test_get_copy_has_brand():
    data = get_copy(force=True)
    assert "brand" in data
    assert "programName" in data["brand"]
