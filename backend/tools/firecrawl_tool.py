import httpx

from backend.config import Settings
from backend.tools.jsearch_tool import JobSourceError

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"


def scrape_job_page(url: str, settings: Settings, client: httpx.Client | None = None) -> str:
    owns_client = client is None
    client = client or httpx.Client()
    try:
        response = client.post(
            FIRECRAWL_URL,
            json={"url": url, "formats": ["markdown"]},
            headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"},
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JobSourceError(f"Firecrawl request failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    return response.json()["data"]["markdown"]
