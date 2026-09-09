import pytest

from backend.tools.ddg_tool import search_jobs_ddg
from backend.tools.jsearch_tool import JobSourceError


class FakeSearcher:
    def __init__(self, results=None, error=None):
        self._results = results or []
        self._error = error

    def text(self, query, max_results=10):
        if self._error:
            raise self._error
        return self._results


def test_search_jobs_ddg_parses_results():
    fake_results = [
        {
            "title": "Backend Engineer - Acme",
            "href": "https://example.com/jobs/1",
            "body": "We need a Python backend engineer...",
        }
    ]
    searcher = FakeSearcher(results=fake_results)

    jobs = search_jobs_ddg("backend engineer remote", searcher=searcher)

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer - Acme"
    assert jobs[0].apply_link == "https://example.com/jobs/1"
    assert jobs[0].description == "We need a Python backend engineer..."
    assert jobs[0].source == "duckduckgo"
    assert jobs[0].company == ""


def test_search_jobs_ddg_raises_job_source_error_on_failure():
    searcher = FakeSearcher(error=RuntimeError("network down"))

    with pytest.raises(JobSourceError):
        search_jobs_ddg("backend engineer remote", searcher=searcher)
