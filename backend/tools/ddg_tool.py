from duckduckgo_search import DDGS

from backend.models import JobListing
from backend.tools.jsearch_tool import JobSourceError


def search_jobs_ddg(query: str, searcher=None) -> list[JobListing]:
    searcher = searcher or DDGS()
    try:
        results = searcher.text(f"{query} job posting", max_results=10)
    except Exception as exc:
        raise JobSourceError(f"DuckDuckGo search failed: {exc}") from exc

    return [
        JobListing(
            title=item.get("title", ""),
            company="",
            description=item.get("body", ""),
            apply_link=item.get("href"),
            source="duckduckgo",
        )
        for item in results
    ]
