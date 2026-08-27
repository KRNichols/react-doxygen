from classification import banner


def _clear_class_env(monkeypatch):
    for name in (
        "CLASSIFICATION",
        "CLASSIFICATION_TEXT",
        "CLASSIFICATION_CUSTOM_TEXT",
        "CLASSIFICATION_CUSTOM_COLOR",
    ):
        monkeypatch.delenv(name, raising=False)


def test_default_unclassified_white_ink(monkeypatch):
    _clear_class_env(monkeypatch)
    data = banner()
    assert data["level"] == "unclassified"
    assert data["text"] == "UNCLASSIFIED"
    assert data["color"] == "#007A33"
    assert data["ink"] == "#FFFFFF"
    assert data["disclaimer"] == "Label only. Not an authorization to operate."


def test_dropdown_options_including_top_secret_black_ink(monkeypatch):
    _clear_class_env(monkeypatch)
    expected = {
        "UNCLASSIFIED": ("unclassified", "UNCLASSIFIED", "#007A33", "#FFFFFF"),
        "CUI": ("cui", "CUI", "#502B85", "#FFFFFF"),
        "CONFIDENTIAL": ("confidential", "CONFIDENTIAL", "#0033A0", "#FFFFFF"),
        "SECRET": ("secret", "SECRET", "#C8102E", "#FFFFFF"),
        "TOP SECRET": ("top_secret", "TOP SECRET", "#FF8C00", "#000000"),
        "ITAR": ("itar", "CUI//SP-EXPT", "#1B4D3E", "#FFFFFF"),
    }
    for raw, (level, text, color, ink) in expected.items():
        monkeypatch.setenv("CLASSIFICATION", raw)
        data = banner()
        assert data["level"] == level
        assert data["text"] == text
        assert data["color"] == color
        assert data["ink"] == ink


def test_custom_fce83a_black_ink(monkeypatch):
    _clear_class_env(monkeypatch)
    monkeypatch.setenv("CLASSIFICATION", "CUSTOM")
    monkeypatch.setenv("CLASSIFICATION_CUSTOM_TEXT", "DEMO MARKING")
    monkeypatch.setenv("CLASSIFICATION_CUSTOM_COLOR", "FCE83A")
    data = banner()
    assert data["level"] == "custom"
    assert data["text"] == "DEMO MARKING"
    assert data["color"] == "#FCE83A"
    assert data["ink"] == "#000000"


def test_secret_text_override(monkeypatch):
    _clear_class_env(monkeypatch)
    monkeypatch.setenv("CLASSIFICATION", "SECRET")
    monkeypatch.setenv("CLASSIFICATION_TEXT", "SECRET//REL TO USA")
    data = banner()
    assert data["level"] == "secret"
    assert data["text"] == "SECRET//REL TO USA"
    assert data["color"] == "#C8102E"
    assert data["ink"] == "#FFFFFF"


def test_unknown_falls_back_unclassified(monkeypatch):
    _clear_class_env(monkeypatch)
    monkeypatch.setenv("CLASSIFICATION", "not-a-real-marking")
    data = banner()
    assert data["level"] == "unclassified"
    assert data["text"] == "UNCLASSIFIED"
    assert data["color"] == "#007A33"
    assert data["ink"] == "#FFFFFF"


def test_api_copy_includes_classification(client, monkeypatch):
    _clear_class_env(monkeypatch)
    res = client.get("/api/copy")
    assert res.status_code == 200
    data = res.get_json()
    assert data["classification"]["level"] == "unclassified"
    assert data["classification"]["text"] == "UNCLASSIFIED"
    assert data["classification"]["color"] == "#007A33"
    assert data["classification"]["ink"] == "#FFFFFF"
    assert data["classification"]["disclaimer"] == (
        "Label only. Not an authorization to operate."
    )
