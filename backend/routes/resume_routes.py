import base64

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from backend.config import Settings, get_settings
from backend.parsing.profile_extractor import extract_profile
from backend.parsing.resume_parser import extract_resume_text, is_docx_well_formed
from backend.storage.session_store import SessionStore
from backend.tools.docx_renderer import render_profile_to_docx

router = APIRouter(prefix="/resume")


def get_session_store() -> SessionStore:
    settings = get_settings()
    return SessionStore(base_dir=settings.data_dir)


def get_settings_dep() -> Settings:
    return get_settings()


@router.post("/upload")
async def upload_resume(
    file: UploadFile,
    store: SessionStore = Depends(get_session_store),
    settings: Settings = Depends(get_settings_dep),
):
    content = await file.read()
    try:
        resume_text = extract_resume_text(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    is_editable = file.filename.lower().endswith(".docx") and is_docx_well_formed(content)
    profile = extract_profile(resume_text, settings)

    session_id = store.create_session()
    store.save_upload(session_id, file.filename, content)
    store.save_profile(session_id, profile)
    store.save_original_docx_flag(session_id, is_editable)

    first_version_bytes = content if is_editable else render_profile_to_docx(profile)

    return {
        "session_id": session_id,
        "profile": profile.model_dump(),
        "first_version_docx_base64": base64.b64encode(first_version_bytes).decode("ascii"),
    }
