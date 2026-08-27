
from copy_text import fill, get_copy


def test_copy_json_endpoint(client):
    res = client.get("/api/copy")
    assert res.status_code == 200
    data = res.get_json()
    assert "brand" in data
    assert data["brand"]["programName"]
    assert "notifyEmail" in data
    assert "login" in data


def test_fill_replaces_placeholders():
    assert fill("Hello {name}", name="Viper") == "Hello Viper"
    assert fill("{x}", x=None) == ""


def test_get_copy_has_brand():
    data = get_copy(force=True)
    assert "brand" in data
    assert "programName" in data["brand"]
