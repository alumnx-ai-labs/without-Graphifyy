import httpx
import pytest

from backend.config import Settings
from backend.tools.firecrawl_tool import scrape_job_page
from backend.tools.jsearch_tool import JobSourceError


def _settings():
    return Settings(google_api_key="x", rapidapi_key="x", firecrawl_api_key="test-fc-key")


def test_scrape_job_page_returns_markdown():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-fc-key"
        return httpx.Response(200, json={"data": {"markdown": "# Backend Engineer\nFull JD text..."}})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    markdown = scrape_job_page("https://example.com/jobs/1", _settings(), client=client)

    assert "Backend Engineer" in markdown


def test_scrape_job_page_raises_job_source_error_on_http_failure():
    def handler(request):
        return httpx.Response(502, json={"error": "bad gateway"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(JobSourceError):
        scrape_job_page("https://example.com/jobs/1", _settings(), client=client)
