import pytest

from backend.models import ContactInfo, ResumeProfile
from backend.storage.session_store import SessionStore


@pytest.fixture
def store(tmp_path):
    return SessionStore(base_dir=str(tmp_path))


def test_create_session_returns_unique_ids(store):
    id_a = store.create_session()
    id_b = store.create_session()
    assert id_a != id_b


def test_save_and_load_upload_roundtrip(store):
    session_id = store.create_session()
    store.save_upload(session_id, "resume.pdf", b"pdf-bytes")

    filename, content = store.load_upload(session_id)

    assert filename == "resume.pdf"
    assert content == b"pdf-bytes"


def test_save_and_load_profile_roundtrip(store):
    session_id = store.create_session()
    profile = ResumeProfile(contact=ContactInfo(name="Jane Doe"))
    store.save_profile(session_id, profile)

    loaded = store.load_profile(session_id)

    assert loaded == profile


def test_original_docx_editable_flag_roundtrip(store):
    session_id = store.create_session()
    store.save_original_docx_flag(session_id, True)
    assert store.is_original_docx_editable(session_id) is True

    store.save_original_docx_flag(session_id, False)
    assert store.is_original_docx_editable(session_id) is False


def test_save_resume_version_and_list_versions(store):
    session_id = store.create_session()
    path_one = store.save_resume_version(session_id, "job-1", b"docx-bytes-v1")
    path_two = store.save_resume_version(session_id, "job-2", b"docx-bytes-v2")

    versions = store.list_versions(session_id)

    assert path_one != path_two
    assert len(versions) == 2
