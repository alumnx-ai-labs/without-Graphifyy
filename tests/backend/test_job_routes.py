import base64

from fastapi.testclient import TestClient

from backend.agents.resume_tailor_agent import TailorResult
from backend.config import Settings
from backend.main import app
from backend.models import ContactInfo, JobListing, JobSearchResult, RankedJob, ResumeProfile
from backend.routes.resume_routes import get_session_store, get_settings_dep
from backend.storage.session_store import SessionStore


def _store_with_profile(tmp_path):
    store = SessionStore(base_dir=str(tmp_path))
    session_id = store.create_session()
    profile = ResumeProfile(contact=ContactInfo(name="Jane Doe"), summary="Backend engineer")
    store.save_profile(session_id, profile)
    return store, session_id, profile


def test_search_jobs_route_returns_job_search_result(tmp_path, monkeypatch):
    store, session_id, profile = _store_with_profile(tmp_path)
    settings = Settings(google_api_key="x", rapidapi_key="x", firecrawl_api_key="x")
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_settings_dep] = lambda: settings

    fake_result = JobSearchResult(
        jobs=[
            RankedJob(
                job=JobListing(title="Backend Engineer", company="Acme", description="...", source="jsearch"),
                match_score=88,
                rationale="Good fit",
            )
        ],
        suggestions=["Quantify impact"],
    )
    monkeypatch.setattr(
        "backend.routes.job_routes.run_job_search",
        lambda profile, settings, preferences=None: fake_result,
    )

    client = TestClient(app)
    response = client.post("/jobs/search", json={"session_id": session_id, "preferences": None})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["jobs"][0]["match_score"] == 88
    assert body["suggestions"] == ["Quantify impact"]


def test_tailor_resume_route_returns_tailor_result(tmp_path, monkeypatch):
    store, session_id, profile = _store_with_profile(tmp_path)
    store.save_original_docx_flag(session_id, False)
    settings = Settings(google_api_key="x", rapidapi_key="x", firecrawl_api_key="x")
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_settings_dep] = lambda: settings

    fake_tailor_result = TailorResult(
        docx_bytes=b"final-docx-bytes", final_score=97, rounds=2, notes="Strong match"
    )
    monkeypatch.setattr(
        "backend.routes.job_routes.tailor_resume",
        lambda profile, job, settings, original_docx_bytes, is_original_editable: fake_tailor_result,
    )

    job_payload = {
        "title": "Backend Engineer",
        "company": "Acme",
        "description": "Python, SQL",
        "source": "jsearch",
    }
    client = TestClient(app)
    response = client.post(
        "/jobs/tailor", json={"session_id": session_id, "job": job_payload}
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["final_score"] == 97
    assert body["rounds"] == 2
    assert base64.b64decode(body["docx_base64"]) == b"final-docx-bytes"
