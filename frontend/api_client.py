import httpx


def upload_resume(base_url: str, filename: str, content: bytes, client: httpx.Client | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.Client()
    try:
        response = client.post(
            f"{base_url}/resume/upload",
            files={"file": (filename, content, "application/octet-stream")},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            client.close()


def search_jobs(base_url: str, session_id: str, preferences: dict | None, client: httpx.Client | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.Client()
    try:
        response = client.post(
            f"{base_url}/jobs/search",
            json={"session_id": session_id, "preferences": preferences},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            client.close()


def tailor_resume(base_url: str, session_id: str, job: dict, client: httpx.Client | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.Client()
    try:
        response = client.post(
            f"{base_url}/jobs/tailor",
            json={"session_id": session_id, "job": job},
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            client.close()
