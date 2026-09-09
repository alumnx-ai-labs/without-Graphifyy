import httpx

from backend.config import Settings
from backend.models import JobListing

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"


class JobSourceError(Exception):
    pass


def search_jobs_jsearch(
    query: str, location: str | None, settings: Settings, client: httpx.Client | None = None
) -> list[JobListing]:
    owns_client = client is None
    client = client or httpx.Client()
    try:
        params = {"query": f"{query} in {location}" if location else query}
        response = client.get(
            JSEARCH_URL,
            params=params,
            headers={
                "X-RapidAPI-Key": settings.rapidapi_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            },
            timeout=15.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JobSourceError(f"JSearch request failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    payload = response.json()
    return [
        JobListing(
            title=item.get("job_title", ""),
            company=item.get("employer_name", ""),
            location=item.get("job_city"),
            description=item.get("job_description", ""),
            apply_link=item.get("job_apply_link"),
            source="jsearch",
        )
        for item in payload.get("data", [])
    ]
