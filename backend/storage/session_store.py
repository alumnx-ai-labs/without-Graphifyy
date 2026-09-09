import json
import os
import uuid

from backend.models import ResumeProfile


class SessionStore:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _session_dir(self, session_id: str) -> str:
        path = os.path.join(self.base_dir, session_id)
        os.makedirs(path, exist_ok=True)
        return path

    def create_session(self) -> str:
        session_id = uuid.uuid4().hex
        self._session_dir(session_id)
        return session_id

    def save_upload(self, session_id: str, filename: str, content: bytes) -> None:
        session_dir = self._session_dir(session_id)
        with open(os.path.join(session_dir, "upload_meta.json"), "w") as f:
            json.dump({"filename": filename}, f)
        with open(os.path.join(session_dir, "upload_content"), "wb") as f:
            f.write(content)

    def load_upload(self, session_id: str) -> tuple[str, bytes]:
        session_dir = self._session_dir(session_id)
        with open(os.path.join(session_dir, "upload_meta.json")) as f:
            meta = json.load(f)
        with open(os.path.join(session_dir, "upload_content"), "rb") as f:
            content = f.read()
        return meta["filename"], content

    def save_profile(self, session_id: str, profile: ResumeProfile) -> None:
        session_dir = self._session_dir(session_id)
        with open(os.path.join(session_dir, "profile.json"), "w") as f:
            f.write(profile.model_dump_json())

    def load_profile(self, session_id: str) -> ResumeProfile:
        session_dir = self._session_dir(session_id)
        with open(os.path.join(session_dir, "profile.json")) as f:
            return ResumeProfile.model_validate_json(f.read())

    def save_original_docx_flag(self, session_id: str, is_editable: bool) -> None:
        session_dir = self._session_dir(session_id)
        with open(os.path.join(session_dir, "docx_editable.json"), "w") as f:
            json.dump({"is_editable": is_editable}, f)

    def is_original_docx_editable(self, session_id: str) -> bool:
        session_dir = self._session_dir(session_id)
        with open(os.path.join(session_dir, "docx_editable.json")) as f:
            return json.load(f)["is_editable"]

    def save_resume_version(self, session_id: str, job_id: str, docx_bytes: bytes) -> str:
        session_dir = self._session_dir(session_id)
        versions_dir = os.path.join(session_dir, "versions")
        os.makedirs(versions_dir, exist_ok=True)
        version_id = uuid.uuid4().hex
        path = os.path.join(versions_dir, f"{job_id}__{version_id}.docx")
        with open(path, "wb") as f:
            f.write(docx_bytes)
        return path

    def list_versions(self, session_id: str) -> list[str]:
        session_dir = self._session_dir(session_id)
        versions_dir = os.path.join(session_dir, "versions")
        if not os.path.isdir(versions_dir):
            return []
        return [os.path.join(versions_dir, name) for name in sorted(os.listdir(versions_dir))]
