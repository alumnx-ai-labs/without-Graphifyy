import base64

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.agents.job_search_agent import run_job_search
from backend.agents.resume_tailor_agent import tailor_resume
from backend.config import Settings
from backend.models import JobListing
from backend.routes.resume_routes import get_session_store, get_settings_dep
from backend.storage.session_store import SessionStore

router = APIRouter(prefix="/jobs")


class SearchRequest(BaseModel):
    session_id: str
    preferences: dict | None = None


class TailorRequest(BaseModel):
    session_id: str
    job: JobListing


@router.post("/search")
def search_jobs(
    request: SearchRequest,
    store: SessionStore = Depends(get_session_store),
    settings: Settings = Depends(get_settings_dep),
):
    profile = store.load_profile(request.session_id)
    result = run_job_search(profile, settings, preferences=request.preferences)
    return result.model_dump()


@router.post("/tailor")
def tailor(
    request: TailorRequest,
    store: SessionStore = Depends(get_session_store),
    settings: Settings = Depends(get_settings_dep),
):
    profile = store.load_profile(request.session_id)
    is_editable = store.is_original_docx_editable(request.session_id)
    original_docx_bytes = None
    if is_editable:
        _, original_docx_bytes = store.load_upload(request.session_id)

    result = tailor_resume(
        profile,
        request.job,
        settings,
        original_docx_bytes=original_docx_bytes,
        is_original_editable=is_editable,
    )

    job_id = f"{request.job.company}-{request.job.title}".replace(" ", "_")
    store.save_resume_version(request.session_id, job_id, result.docx_bytes)

    return {
        "docx_base64": base64.b64encode(result.docx_bytes).decode("ascii"),
        "final_score": result.final_score,
        "rounds": result.rounds,
        "notes": result.notes,
    }
