from backend.config import get_settings


def test_get_settings_reads_env_vars(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("RAPIDAPI_KEY", "test-rapidapi-key")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    settings = get_settings()

    assert settings.google_api_key == "test-google-key"
    assert settings.rapidapi_key == "test-rapidapi-key"
    assert settings.firecrawl_api_key == "test-firecrawl-key"
    assert settings.gemini_model == "gemini-2.0-flash"
    assert settings.data_dir == "./data/sessions"
