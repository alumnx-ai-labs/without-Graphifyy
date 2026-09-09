import base64
import io

from docx import Document
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import app
from backend.models import ContactInfo, ResumeProfile
from backend.routes.resume_routes import get_session_store, get_settings_dep
from backend.storage.session_store import SessionStore


def _docx_bytes(paragraphs):
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_resume_returns_session_and_profile(tmp_path, monkeypatch):
    store = SessionStore(base_dir=str(tmp_path))
    settings = Settings(google_api_key="x", rapidapi_key="x", firecrawl_api_key="x")

    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_settings_dep] = lambda: settings

    fake_profile = ResumeProfile(contact=ContactInfo(name="Jane Doe"), summary="Backend engineer")
    monkeypatch.setattr(
        "backend.routes.resume_routes.extract_profile", lambda text, settings, llm=None: fake_profile
    )

    client = TestClient(app)
    docx_content = _docx_bytes([f"line {i}" for i in range(10)])

    response = client.post(
        "/resume/upload",
        files={"file": ("resume.docx", docx_content, "application/octet-stream")},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "session_id" in body
    assert body["profile"]["contact"]["name"] == "Jane Doe"
    decoded = base64.b64decode(body["first_version_docx_base64"])
    assert len(decoded) > 0

    loaded_profile = store.load_profile(body["session_id"])
    assert loaded_profile == fake_profile
    assert store.is_original_docx_editable(body["session_id"]) is True


def test_upload_resume_rejects_unsupported_file_type(tmp_path):
    store = SessionStore(base_dir=str(tmp_path))
    settings = Settings(google_api_key="x", rapidapi_key="x", firecrawl_api_key="x")
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_settings_dep] = lambda: settings

    client = TestClient(app)
    response = client.post(
        "/resume/upload",
        files={"file": ("resume.xyz", b"garbage", "application/octet-stream")},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
