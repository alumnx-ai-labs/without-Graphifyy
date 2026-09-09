import httpx
import pytest

from backend.config import Settings
from backend.tools.jsearch_tool import JobSourceError, search_jobs_jsearch


def _settings():
    return Settings(google_api_key="x", rapidapi_key="test-key", firecrawl_api_key="x")


def test_search_jobs_jsearch_parses_results():
    fixture = {
        "data": [
            {
                "job_title": "Backend Engineer",
                "employer_name": "Acme",
                "job_city": "Remote",
                "job_description": "Python, SQL, APIs",
                "job_apply_link": "https://example.com/apply/1",
            }
        ]
    }

    def handler(request):
        assert request.headers["X-RapidAPI-Key"] == "test-key"
        return httpx.Response(200, json=fixture)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    jobs = search_jobs_jsearch("backend engineer", "Remote", _settings(), client=client)

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "Acme"
    assert jobs[0].source == "jsearch"
    assert jobs[0].apply_link == "https://example.com/apply/1"


def test_search_jobs_jsearch_raises_job_source_error_on_http_failure():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(JobSourceError):
        search_jobs_jsearch("backend engineer", None, _settings(), client=client)
