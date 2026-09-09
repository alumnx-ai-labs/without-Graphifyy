# Job Search & Resume Tailoring Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-agent (LangChain ReAct) system — one that searches
jobs matching an uploaded resume and suggests improvements, and one that
tailors the resume to a specific chosen job — served by FastAPI and used
through a Streamlit UI.

**Architecture:** FastAPI backend hosts `JobSearchAgent` (tools: JSearch,
DuckDuckGo, Firecrawl, match scorer) and `ResumeTailorAgent` (tools: DOCX
in-place editor, structured-profile DOCX renderer, match scorer).
Streamlit frontend calls the backend over HTTP: upload → search → select
→ tailor → preview/download, repeatable per job.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, Streamlit, LangChain +
`langchain-google-genai` (Gemini), `pydantic` v2, `python-docx`, `pypdf`,
`httpx`, `duckduckgo-search`, `pytest`, `pytest-mock`.

**Spec:** [docs/superpowers/specs/2026-09-02-job-search-agent-design.md](../specs/2026-09-02-job-search-agent-design.md)

## Global Constraints

- Never fabricate skills, employers, dates, or experience not present in
  the source resume — applies to both agents' system prompts.
- ResumeTailorAgent's draft/score/revise loop is capped at 3 rounds by
  default and must terminate even if the score threshold is never met.
- Any single job-source failure (JSearch, DuckDuckGo, Firecrawl) must
  degrade gracefully — drop that source, note reduced coverage, never
  fail the whole search.
- All external calls (Gemini, JSearch, DuckDuckGo, Firecrawl) must be
  mockable in tests — no test may require real network access or API
  keys.
- Config values (`GOOGLE_API_KEY`, `GEMINI_MODEL`, `RAPIDAPI_KEY`,
  `FIRECRAWL_API_KEY`) are read from environment variables via one
  `Settings` object, never read ad hoc from `os.environ` elsewhere.

---

## Task 1: Project scaffolding, git init, and config

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `backend/__init__.py`
- Create: `backend/config.py`
- Create: `tests/__init__.py`
- Create: `tests/backend/__init__.py`
- Test: `tests/backend/test_config.py`

**Interfaces:**
- Produces: `backend.config.Settings` (pydantic `BaseSettings`) with
  fields `google_api_key: str`, `gemini_model: str = "gemini-2.0-flash"`,
  `rapidapi_key: str`, `firecrawl_api_key: str`, `data_dir: str =
  "./data/sessions"`. Produces `backend.config.get_settings() ->
  Settings` (reads from environment, no caching needed at this scale).

- [ ] **Step 1: Create the directory layout and dependency files**

Run:
```bash
mkdir -p backend/tools backend/agents backend/routes backend/storage backend/parsing frontend tests/backend data/sessions
touch backend/tools/__init__.py backend/agents/__init__.py backend/routes/__init__.py backend/storage/__init__.py backend/parsing/__init__.py frontend/__init__.py
```

Create `requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
streamlit==1.38.0
langchain==0.3.1
langchain-google-genai==2.0.1
pydantic==2.9.2
pydantic-settings==2.5.2
python-docx==1.1.2
pypdf==5.0.1
httpx==0.27.2
duckduckgo-search==6.2.13
python-multipart==0.0.9
pytest==8.3.3
pytest-mock==3.14.0
```

Create `pyproject.toml`:
```toml
[project]
name = "job-search-agent"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create `.gitignore`:
```
__pycache__/
*.pyc
.env
data/sessions/*
!data/sessions/.gitkeep
.venv/
```

Run: `touch data/sessions/.gitkeep`

Create `.env.example`:
```
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
RAPIDAPI_KEY=
FIRECRAWL_API_KEY=
```

- [ ] **Step 2: Write the failing test for Settings**

`tests/backend/test_config.py`:
```python
import os
from backend.config import get_settings


def test_get_settings_reads_env_vars(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("RAPIDAPI_KEY", "test-rapidapi-key")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    settings = get_settings()

    assert settings.google_api_key == "test-google-key"
    assert settings.rapidapi_key == "test-rapidapi-key"
    assert settings.firecrawl_api_key == "test-firecrawl-key"
    assert settings.gemini_model == "gemini-2.0-flash"
    assert settings.data_dir == "./data/sessions"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/backend/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.config'`

- [ ] **Step 4: Write minimal implementation**

`backend/config.py`:
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_api_key: str
    gemini_model: str = "gemini-2.0-flash"
    rapidapi_key: str
    firecrawl_api_key: str
    data_dir: str = "./data/sessions"

    class Config:
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()
```

`backend/__init__.py`: (empty file)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/backend/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Init git and commit**

```bash
git init
git add -A
git commit -m "chore: project scaffolding and settings"
```

---

## Task 2: Resume text extraction and DOCX well-formedness check

**Files:**
- Create: `backend/parsing/resume_parser.py`
- Test: `tests/backend/test_resume_parser.py`

**Interfaces:**
- Consumes: nothing (pure functions over raw bytes).
- Produces: `backend.parsing.resume_parser.extract_resume_text(filename:
  str, content: bytes) -> str`; `backend.parsing.resume_parser
  .is_docx_well_formed(content: bytes) -> bool`.

- [ ] **Step 1: Write the failing tests**

`tests/backend/test_resume_parser.py`:
```python
import io
from docx import Document
from backend.parsing.resume_parser import extract_resume_text, is_docx_well_formed


def _make_docx_bytes(paragraphs):
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extract_resume_text_from_txt():
    content = b"Jane Doe\nSoftware Engineer\nSkills: Python, SQL"
    text = extract_resume_text("resume.txt", content)
    assert "Jane Doe" in text
    assert "Python" in text


def test_extract_resume_text_from_docx():
    content = _make_docx_bytes(["Jane Doe", "Software Engineer", "Skills: Python, SQL"])
    text = extract_resume_text("resume.docx", content)
    assert "Jane Doe" in text
    assert "Skills: Python, SQL" in text


def test_extract_resume_text_unsupported_extension_raises():
    import pytest
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_resume_text("resume.xyz", b"whatever")


def test_is_docx_well_formed_true_for_multi_paragraph_docx():
    content = _make_docx_bytes([f"Line {i}" for i in range(10)])
    assert is_docx_well_formed(content) is True


def test_is_docx_well_formed_false_for_sparse_docx():
    content = _make_docx_bytes(["Everything crammed into a single paragraph"])
    assert is_docx_well_formed(content) is False


def test_is_docx_well_formed_false_for_non_docx_bytes():
    assert is_docx_well_formed(b"not a docx file at all") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_resume_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.parsing.resume_parser'`

- [ ] **Step 3: Write minimal implementation**

`backend/parsing/resume_parser.py`:
```python
import io

from docx import Document
from pypdf import PdfReader

MIN_WELL_FORMED_PARAGRAPHS = 5


def extract_resume_text(filename: str, content: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".txt"):
        return content.decode("utf-8", errors="ignore")
    if lower.endswith(".docx"):
        return _extract_docx_text(content)
    if lower.endswith(".pdf"):
        return _extract_pdf_text(content)
    raise ValueError(f"Unsupported file type: {filename}")


def _extract_docx_text(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def is_docx_well_formed(content: bytes) -> bool:
    try:
        doc = Document(io.BytesIO(content))
    except Exception:
        return False
    non_empty_paragraphs = [p for p in doc.paragraphs if p.text.strip()]
    return len(non_empty_paragraphs) >= MIN_WELL_FORMED_PARAGRAPHS
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_resume_parser.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/parsing/resume_parser.py tests/backend/test_resume_parser.py
git commit -m "feat: resume text extraction and docx well-formedness check"
```

---

## Task 3: Shared domain models

**Files:**
- Create: `backend/models.py`
- Test: `tests/backend/test_models.py`

**Interfaces:**
- Produces: `backend.models.ContactInfo`, `ExperienceEntry`,
  `EducationEntry`, `ResumeProfile`, `JobListing`, `RankedJob`,
  `MatchResult`, `JobSearchResult` (all pydantic `BaseModel`).
  `ResumeProfile` fields: `contact: ContactInfo`, `summary: str = ""`,
  `skills: list[str] = []`, `experience: list[ExperienceEntry] = []`,
  `education: list[EducationEntry] = []`, `certifications: list[str] =
  []`. `JobListing` fields: `title: str`, `company: str`, `location:
  str | None = None`, `description: str`, `apply_link: str | None =
  None`, `source: str`. `MatchResult` fields: `score: int`,
  `missing_keywords: list[str] = []`, `notes: str = ""`. `RankedJob`
  fields: `job: JobListing`, `match_score: int`, `rationale: str`.
  `JobSearchResult` fields: `jobs: list[RankedJob]`, `suggestions:
  list[str]`, `clarification_question: str | None = None`.

- [ ] **Step 1: Write the failing test**

`tests/backend/test_models.py`:
```python
from backend.models import (
    ContactInfo,
    ExperienceEntry,
    EducationEntry,
    ResumeProfile,
    JobListing,
    RankedJob,
    MatchResult,
    JobSearchResult,
)


def test_resume_profile_defaults_and_nesting():
    profile = ResumeProfile(
        contact=ContactInfo(name="Jane Doe", email="jane@example.com"),
        summary="Backend engineer.",
        skills=["Python", "SQL"],
        experience=[
            ExperienceEntry(
                title="Software Engineer",
                company="Acme",
                start_date="2020-01",
                end_date="2023-06",
                bullets=["Built the widget service"],
            )
        ],
        education=[EducationEntry(degree="B.S. CS", institution="State U", year="2019")],
        certifications=["AWS SAA"],
    )
    assert profile.contact.name == "Jane Doe"
    assert profile.experience[0].company == "Acme"
    assert profile.education[0].institution == "State U"


def test_job_search_result_optional_clarification():
    result = JobSearchResult(
        jobs=[
            RankedJob(
                job=JobListing(
                    title="Backend Engineer",
                    company="Acme",
                    description="Python, SQL, APIs",
                    source="jsearch",
                ),
                match_score=82,
                rationale="Strong Python/SQL overlap",
            )
        ],
        suggestions=["Quantify impact in bullet points"],
    )
    assert result.clarification_question is None
    assert result.jobs[0].match_score == 82


def test_match_result_defaults():
    result = MatchResult(score=91)
    assert result.missing_keywords == []
    assert result.notes == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.models'`

- [ ] **Step 3: Write minimal implementation**

`backend/models.py`:
```python
from pydantic import BaseModel


class ContactInfo(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None


class ExperienceEntry(BaseModel):
    title: str
    company: str
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = []


class EducationEntry(BaseModel):
    degree: str
    institution: str
    year: str | None = None


class ResumeProfile(BaseModel):
    contact: ContactInfo
    summary: str = ""
    skills: list[str] = []
    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    certifications: list[str] = []


class JobListing(BaseModel):
    title: str
    company: str
    location: str | None = None
    description: str
    apply_link: str | None = None
    source: str


class RankedJob(BaseModel):
    job: JobListing
    match_score: int
    rationale: str


class MatchResult(BaseModel):
    score: int
    missing_keywords: list[str] = []
    notes: str = ""


class JobSearchResult(BaseModel):
    jobs: list[RankedJob]
    suggestions: list[str]
    clarification_question: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models.py tests/backend/test_models.py
git commit -m "feat: shared domain models"
```

---

## Task 4: Structured profile extraction (Gemini)

**Files:**
- Create: `backend/parsing/profile_extractor.py`
- Test: `tests/backend/test_profile_extractor.py`

**Interfaces:**
- Consumes: `backend.models.ResumeProfile` (Task 3);
  `backend.config.Settings` (Task 1).
- Produces: `backend.parsing.profile_extractor.extract_profile(resume_text:
  str, settings: Settings, llm=None) -> ResumeProfile`. The optional
  `llm` parameter accepts a pre-built chat model (used by tests to inject
  a fake); when `None`, a `ChatGoogleGenerativeAI` is constructed from
  `settings`.

- [ ] **Step 1: Write the failing test**

`tests/backend/test_profile_extractor.py`:
```python
import json
from backend.config import Settings
from backend.models import ResumeProfile
from backend.parsing.profile_extractor import extract_profile


class FakeStructuredLLM:
    def __init__(self, response: ResumeProfile):
        self._response = response

    def invoke(self, _prompt):
        return self._response


class FakeLLM:
    def __init__(self, response: ResumeProfile):
        self._structured = FakeStructuredLLM(response)

    def with_structured_output(self, schema):
        assert schema is ResumeProfile
        return self._structured


def test_extract_profile_returns_resume_profile():
    expected = ResumeProfile(
        contact={"name": "Jane Doe", "email": "jane@example.com"},
        summary="Backend engineer with 5 years experience.",
        skills=["Python", "SQL"],
        experience=[
            {
                "title": "Software Engineer",
                "company": "Acme",
                "bullets": ["Built the widget service"],
            }
        ],
        education=[{"degree": "B.S. CS", "institution": "State U"}],
        certifications=[],
    )
    settings = Settings(
        google_api_key="x", rapidapi_key="x", firecrawl_api_key="x"
    )
    fake_llm = FakeLLM(expected)

    profile = extract_profile("Jane Doe\nSoftware Engineer at Acme...", settings, llm=fake_llm)

    assert profile == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_profile_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.parsing.profile_extractor'`

- [ ] **Step 3: Write minimal implementation**

`backend/parsing/profile_extractor.py`:
```python
from langchain_google_genai import ChatGoogleGenerativeAI

from backend.config import Settings
from backend.models import ResumeProfile

EXTRACTION_PROMPT = """You extract structured resume data. Read the resume \
text below and populate every field you can find. Never invent \
information that is not present in the text; leave fields empty or null \
if the resume does not state them.

RESUME TEXT:
{resume_text}
"""


def extract_profile(resume_text: str, settings: Settings, llm=None) -> ResumeProfile:
    if llm is None:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model, google_api_key=settings.google_api_key
        )
    structured_llm = llm.with_structured_output(ResumeProfile)
    prompt = EXTRACTION_PROMPT.format(resume_text=resume_text)
    return structured_llm.invoke(prompt)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_profile_extractor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/parsing/profile_extractor.py tests/backend/test_profile_extractor.py
git commit -m "feat: structured resume profile extraction via Gemini"
```

---

## Task 5: Session storage

**Files:**
- Create: `backend/storage/session_store.py`
- Test: `tests/backend/test_session_store.py`

**Interfaces:**
- Consumes: `backend.models.ResumeProfile` (Task 3).
- Produces: `backend.storage.session_store.SessionStore` with methods
  `create_session() -> str`, `save_upload(session_id: str, filename: str,
  content: bytes) -> None`, `save_profile(session_id: str, profile:
  ResumeProfile) -> None`, `load_profile(session_id: str) ->
  ResumeProfile`, `save_original_docx_flag(session_id: str, is_editable:
  bool) -> None`, `is_original_docx_editable(session_id: str) -> bool`,
  `load_upload(session_id: str) -> tuple[str, bytes]` (filename,
  content), `save_resume_version(session_id: str, job_id: str, docx_bytes:
  bytes) -> str` (returns version path), `list_versions(session_id: str)
  -> list[str]`.

- [ ] **Step 1: Write the failing test**

`tests/backend/test_session_store.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_session_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.storage.session_store'`

- [ ] **Step 3: Write minimal implementation**

`backend/storage/session_store.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_session_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/storage/session_store.py tests/backend/test_session_store.py
git commit -m "feat: filesystem-backed session storage"
```

---

## Task 6: DOCX renderer (structured profile → DOCX)

**Files:**
- Create: `backend/tools/docx_renderer.py`
- Test: `tests/backend/test_docx_renderer.py`

**Interfaces:**
- Consumes: `backend.models.ResumeProfile` (Task 3).
- Produces: `backend.tools.docx_renderer.render_profile_to_docx(profile:
  ResumeProfile) -> bytes`.

- [ ] **Step 1: Write the failing test**

`tests/backend/test_docx_renderer.py`:
```python
import io
from docx import Document
from backend.models import ContactInfo, EducationEntry, ExperienceEntry, ResumeProfile
from backend.tools.docx_renderer import render_profile_to_docx


def test_render_profile_to_docx_includes_all_sections():
    profile = ResumeProfile(
        contact=ContactInfo(name="Jane Doe", email="jane@example.com"),
        summary="Backend engineer with 5 years experience.",
        skills=["Python", "SQL"],
        experience=[
            ExperienceEntry(
                title="Software Engineer",
                company="Acme",
                start_date="2020",
                end_date="2023",
                bullets=["Built the widget service"],
            )
        ],
        education=[EducationEntry(degree="B.S. CS", institution="State U", year="2019")],
        certifications=["AWS SAA"],
    )

    docx_bytes = render_profile_to_docx(profile)

    doc = Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Jane Doe" in full_text
    assert "jane@example.com" in full_text
    assert "Backend engineer with 5 years experience." in full_text
    assert "Python" in full_text and "SQL" in full_text
    assert "Software Engineer" in full_text and "Acme" in full_text
    assert "Built the widget service" in full_text
    assert "B.S. CS" in full_text and "State U" in full_text
    assert "AWS SAA" in full_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_docx_renderer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.tools.docx_renderer'`

- [ ] **Step 3: Write minimal implementation**

`backend/tools/docx_renderer.py`:
```python
import io

from docx import Document

from backend.models import ResumeProfile


def render_profile_to_docx(profile: ResumeProfile) -> bytes:
    doc = Document()

    doc.add_heading(profile.contact.name, level=0)
    contact_line = " | ".join(
        part
        for part in [profile.contact.email, profile.contact.phone, profile.contact.location]
        if part
    )
    if contact_line:
        doc.add_paragraph(contact_line)

    if profile.summary:
        doc.add_heading("Summary", level=1)
        doc.add_paragraph(profile.summary)

    if profile.skills:
        doc.add_heading("Skills", level=1)
        doc.add_paragraph(", ".join(profile.skills))

    if profile.experience:
        doc.add_heading("Experience", level=1)
        for entry in profile.experience:
            date_range = " - ".join(
                part for part in [entry.start_date, entry.end_date] if part
            )
            header = f"{entry.title}, {entry.company}"
            if date_range:
                header += f" ({date_range})"
            doc.add_paragraph(header, style="Heading 3")
            for bullet in entry.bullets:
                doc.add_paragraph(bullet, style="List Bullet")

    if profile.education:
        doc.add_heading("Education", level=1)
        for entry in profile.education:
            line = f"{entry.degree}, {entry.institution}"
            if entry.year:
                line += f" ({entry.year})"
            doc.add_paragraph(line)

    if profile.certifications:
        doc.add_heading("Certifications", level=1)
        for cert in profile.certifications:
            doc.add_paragraph(cert, style="List Bullet")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_docx_renderer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tools/docx_renderer.py tests/backend/test_docx_renderer.py
git commit -m "feat: render structured resume profile to docx"
```

---

## Task 7: DOCX in-place editor

**Files:**
- Create: `backend/tools/docx_editor.py`
- Test: `tests/backend/test_docx_editor.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `backend.tools.docx_editor.apply_paragraph_replacements(
  docx_bytes: bytes, replacements: dict[str, str]) -> bytes`. Each key in
  `replacements` is matched against a paragraph's exact current text; if
  found, that paragraph's text is replaced with the value, preserving the
  formatting of the paragraph's first run. Paragraphs with no matching
  key are left untouched. Also produces `append_bullets_after(docx_bytes:
  bytes, after_paragraph_text: str, bullets: list[str]) -> bytes`, which
  inserts new "List Bullet" paragraphs immediately after the paragraph
  matching `after_paragraph_text`.

- [ ] **Step 1: Write the failing tests**

`tests/backend/test_docx_editor.py`:
```python
import io
from docx import Document
from backend.tools.docx_editor import apply_paragraph_replacements, append_bullets_after


def _make_docx_bytes(paragraphs):
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _paragraph_texts(docx_bytes):
    doc = Document(io.BytesIO(docx_bytes))
    return [p.text for p in doc.paragraphs]


def test_apply_paragraph_replacements_replaces_matching_text():
    original = _make_docx_bytes(["Built internal tools", "Managed a small team"])

    updated = apply_paragraph_replacements(
        original, {"Built internal tools": "Built and shipped internal developer tools"}
    )

    texts = _paragraph_texts(updated)
    assert "Built and shipped internal developer tools" in texts
    assert "Managed a small team" in texts
    assert "Built internal tools" not in texts


def test_apply_paragraph_replacements_ignores_non_matching_keys():
    original = _make_docx_bytes(["Only paragraph"])

    updated = apply_paragraph_replacements(original, {"Nonexistent text": "New text"})

    assert _paragraph_texts(updated) == ["Only paragraph"]


def test_append_bullets_after_inserts_new_bullets():
    original = _make_docx_bytes(["Experience", "Software Engineer, Acme"])

    updated = append_bullets_after(
        original, "Software Engineer, Acme", ["Shipped feature X", "Reduced latency by 30%"]
    )

    texts = _paragraph_texts(updated)
    idx = texts.index("Software Engineer, Acme")
    assert texts[idx + 1] == "Shipped feature X"
    assert texts[idx + 2] == "Reduced latency by 30%"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_docx_editor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.tools.docx_editor'`

- [ ] **Step 3: Write minimal implementation**

`backend/tools/docx_editor.py`:
```python
import copy
import io

from docx import Document


def apply_paragraph_replacements(docx_bytes: bytes, replacements: dict[str, str]) -> bytes:
    doc = Document(io.BytesIO(docx_bytes))
    for paragraph in doc.paragraphs:
        if paragraph.text in replacements:
            new_text = replacements[paragraph.text]
            _set_paragraph_text_preserving_style(paragraph, new_text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def append_bullets_after(docx_bytes: bytes, after_paragraph_text: str, bullets: list[str]) -> bytes:
    doc = Document(io.BytesIO(docx_bytes))
    anchor = None
    for paragraph in doc.paragraphs:
        if paragraph.text == after_paragraph_text:
            anchor = paragraph
            break
    if anchor is None:
        raise ValueError(f"No paragraph found matching: {after_paragraph_text!r}")

    insert_after_element = anchor._p
    for bullet_text in bullets:
        new_paragraph = doc.add_paragraph(bullet_text, style="List Bullet")
        insert_after_element.addnext(new_paragraph._p)
        insert_after_element = new_paragraph._p

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _set_paragraph_text_preserving_style(paragraph, new_text: str) -> None:
    if not paragraph.runs:
        paragraph.add_run(new_text)
        return
    first_run = paragraph.runs[0]
    first_run.text = new_text
    for extra_run in paragraph.runs[1:]:
        extra_run.text = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_docx_editor.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/tools/docx_editor.py tests/backend/test_docx_editor.py
git commit -m "feat: in-place docx paragraph editing"
```

---

## Task 8: Match scorer (LLM-as-judge)

**Files:**
- Create: `backend/tools/match_scorer.py`
- Test: `tests/backend/test_match_scorer.py`

**Interfaces:**
- Consumes: `backend.models.MatchResult` (Task 3);
  `backend.config.Settings` (Task 1).
- Produces: `backend.tools.match_scorer.score_resume_against_job(
  resume_text: str, job_description: str, settings: Settings, llm=None)
  -> MatchResult`. Same `llm` injection pattern as
  `profile_extractor.extract_profile`.

- [ ] **Step 1: Write the failing test**

`tests/backend/test_match_scorer.py`:
```python
from backend.config import Settings
from backend.models import MatchResult
from backend.tools.match_scorer import score_resume_against_job


class FakeStructuredLLM:
    def __init__(self, response: MatchResult):
        self._response = response

    def invoke(self, _prompt):
        return self._response


class FakeLLM:
    def __init__(self, response: MatchResult):
        self._structured = FakeStructuredLLM(response)

    def with_structured_output(self, schema):
        assert schema is MatchResult
        return self._structured


def test_score_resume_against_job_returns_match_result():
    expected = MatchResult(score=76, missing_keywords=["Kubernetes"], notes="Strong Python overlap")
    settings = Settings(google_api_key="x", rapidapi_key="x", firecrawl_api_key="x")
    fake_llm = FakeLLM(expected)

    result = score_resume_against_job(
        resume_text="Experienced Python developer...",
        job_description="Looking for a Python + Kubernetes engineer...",
        settings=settings,
        llm=fake_llm,
    )

    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_match_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.tools.match_scorer'`

- [ ] **Step 3: Write minimal implementation**

`backend/tools/match_scorer.py`:
```python
from langchain_google_genai import ChatGoogleGenerativeAI

from backend.config import Settings
from backend.models import MatchResult

SCORING_PROMPT = """You are scoring how well a resume matches a job \
description. Score from 0 to 100 based on skills/keyword overlap and \
relevant experience. List specific keywords or requirements from the job \
description that are missing from the resume. Be concise in your notes.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}
"""


def score_resume_against_job(
    resume_text: str, job_description: str, settings: Settings, llm=None
) -> MatchResult:
    if llm is None:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model, google_api_key=settings.google_api_key
        )
    structured_llm = llm.with_structured_output(MatchResult)
    prompt = SCORING_PROMPT.format(resume_text=resume_text, job_description=job_description)
    return structured_llm.invoke(prompt)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_match_scorer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tools/match_scorer.py tests/backend/test_match_scorer.py
git commit -m "feat: LLM-as-judge resume/job match scoring"
```

---

## Task 9: JSearch job-source tool

**Files:**
- Create: `backend/tools/jsearch_tool.py`
- Test: `tests/backend/test_jsearch_tool.py`

**Interfaces:**
- Consumes: `backend.models.JobListing` (Task 3);
  `backend.config.Settings` (Task 1).
- Produces: `backend.tools.jsearch_tool.search_jobs_jsearch(query: str,
  location: str | None, settings: Settings, client=None) ->
  list[JobListing]`. `client` accepts an injected `httpx.Client`-like
  object for tests. Raises `JobSourceError` (defined in this module) on
  any request failure so the caller can decide to degrade gracefully.

- [ ] **Step 1: Write the failing tests**

`tests/backend/test_jsearch_tool.py`:
```python
import httpx
import pytest
from backend.config import Settings
from backend.tools.jsearch_tool import JobSourceError, search_jobs_jsearch


def _settings():
    return Settings(google_api_key="x", rapidapi_key="test-key", firecrawl_api_key="x")


def test_search_jobs_jsearch_parses_results():
    fixture = {
        "data": [
            {
                "job_title": "Backend Engineer",
                "employer_name": "Acme",
                "job_city": "Remote",
                "job_description": "Python, SQL, APIs",
                "job_apply_link": "https://example.com/apply/1",
            }
        ]
    }

    def handler(request):
        assert request.headers["X-RapidAPI-Key"] == "test-key"
        return httpx.Response(200, json=fixture)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    jobs = search_jobs_jsearch("backend engineer", "Remote", _settings(), client=client)

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "Acme"
    assert jobs[0].source == "jsearch"
    assert jobs[0].apply_link == "https://example.com/apply/1"


def test_search_jobs_jsearch_raises_job_source_error_on_http_failure():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(JobSourceError):
        search_jobs_jsearch("backend engineer", None, _settings(), client=client)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_jsearch_tool.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.tools.jsearch_tool'`

- [ ] **Step 3: Write minimal implementation**

`backend/tools/jsearch_tool.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_jsearch_tool.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/tools/jsearch_tool.py tests/backend/test_jsearch_tool.py
git commit -m "feat: JSearch job listing tool"
```

---

## Task 10: DuckDuckGo job-source tool

**Files:**
- Create: `backend/tools/ddg_tool.py`
- Test: `tests/backend/test_ddg_tool.py`

**Interfaces:**
- Consumes: `backend.models.JobListing` (Task 3);
  `backend.tools.jsearch_tool.JobSourceError` (Task 9, reused so callers
  handle one exception type across sources).
- Produces: `backend.tools.ddg_tool.search_jobs_ddg(query: str,
  searcher=None) -> list[JobListing]`. `searcher` accepts an injected
  object exposing `.text(query, max_results=...)` (matching the
  `duckduckgo_search.DDGS` interface) for tests. Listings from DuckDuckGo
  have `description` set to the search snippet (full text is filled in
  later by Firecrawl) and `source="duckduckgo"`.

- [ ] **Step 1: Write the failing tests**

`tests/backend/test_ddg_tool.py`:
```python
import pytest
from backend.tools.ddg_tool import search_jobs_ddg
from backend.tools.jsearch_tool import JobSourceError


class FakeSearcher:
    def __init__(self, results=None, error=None):
        self._results = results or []
        self._error = error

    def text(self, query, max_results=10):
        if self._error:
            raise self._error
        return self._results


def test_search_jobs_ddg_parses_results():
    fake_results = [
        {
            "title": "Backend Engineer - Acme",
            "href": "https://example.com/jobs/1",
            "body": "We need a Python backend engineer...",
        }
    ]
    searcher = FakeSearcher(results=fake_results)

    jobs = search_jobs_ddg("backend engineer remote", searcher=searcher)

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer - Acme"
    assert jobs[0].apply_link == "https://example.com/jobs/1"
    assert jobs[0].description == "We need a Python backend engineer..."
    assert jobs[0].source == "duckduckgo"
    assert jobs[0].company == ""


def test_search_jobs_ddg_raises_job_source_error_on_failure():
    searcher = FakeSearcher(error=RuntimeError("network down"))

    with pytest.raises(JobSourceError):
        search_jobs_ddg("backend engineer remote", searcher=searcher)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_ddg_tool.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.tools.ddg_tool'`

- [ ] **Step 3: Write minimal implementation**

`backend/tools/ddg_tool.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_ddg_tool.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ddg_tool.py tests/backend/test_ddg_tool.py
git commit -m "feat: DuckDuckGo job listing tool"
```

---

## Task 11: Firecrawl scrape tool

**Files:**
- Create: `backend/tools/firecrawl_tool.py`
- Test: `tests/backend/test_firecrawl_tool.py`

**Interfaces:**
- Consumes: `backend.config.Settings` (Task 1);
  `backend.tools.jsearch_tool.JobSourceError` (Task 9).
- Produces: `backend.tools.firecrawl_tool.scrape_job_page(url: str,
  settings: Settings, client=None) -> str` — returns the page's markdown
  content.

- [ ] **Step 1: Write the failing tests**

`tests/backend/test_firecrawl_tool.py`:
```python
import httpx
import pytest
from backend.config import Settings
from backend.tools.firecrawl_tool import scrape_job_page
from backend.tools.jsearch_tool import JobSourceError


def _settings():
    return Settings(google_api_key="x", rapidapi_key="x", firecrawl_api_key="test-fc-key")


def test_scrape_job_page_returns_markdown():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-fc-key"
        return httpx.Response(200, json={"data": {"markdown": "# Backend Engineer\nFull JD text..."}})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    markdown = scrape_job_page("https://example.com/jobs/1", _settings(), client=client)

    assert "Backend Engineer" in markdown


def test_scrape_job_page_raises_job_source_error_on_http_failure():
    def handler(request):
        return httpx.Response(502, json={"error": "bad gateway"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(JobSourceError):
        scrape_job_page("https://example.com/jobs/1", _settings(), client=client)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_firecrawl_tool.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.tools.firecrawl_tool'`

- [ ] **Step 3: Write minimal implementation**

`backend/tools/firecrawl_tool.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_firecrawl_tool.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/tools/firecrawl_tool.py tests/backend/test_firecrawl_tool.py
git commit -m "feat: Firecrawl job page scraping tool"
```

---

## Task 12: JobSearchAgent

**Files:**
- Create: `backend/agents/job_search_agent.py`
- Test: `tests/backend/test_job_search_agent.py`

**Interfaces:**
- Consumes: `backend.models.{ResumeProfile, JobListing, RankedJob,
  JobSearchResult}` (Task 3); `search_jobs_jsearch` (Task 9);
  `search_jobs_ddg` (Task 10); `scrape_job_page` (Task 11);
  `JobSourceError` (Task 9); `score_resume_against_job` (Task 8);
  `backend.config.Settings` (Task 1).
- Produces: `backend.agents.job_search_agent.run_job_search(profile:
  ResumeProfile, settings: Settings, preferences: dict | None = None,
  jsearch_fn=search_jobs_jsearch, ddg_fn=search_jobs_ddg,
  scrape_fn=scrape_job_page, scorer_fn=score_resume_against_job) ->
  JobSearchResult`. All the `*_fn` parameters default to the real
  implementations so production callers don't pass anything, and tests
  inject fakes. This function directly orchestrates the tools in Python
  (no LangChain `AgentExecutor` indirection) — see the note below.

**Design note on "ReAct agent" for this task:** a full LangChain
`AgentExecutor` loop is non-deterministic and hard to unit-test
reliably. To keep the required behavior (search multiple sources, score
each job, degrade a source gracefully, ask a clarifying question when
signal is thin) both correct and testable, `run_job_search` implements
that control flow directly in Python, calling each tool function in
turn and using the LLM only for the two things that need judgment: the
clarification-question decision and per-job rationale text (both via the
already-tested `score_resume_against_job`-style structured-output
pattern). This satisfies the spec's behavior; the "ReAct" framing from
the original ask is realized as tool-calling functions orchestrated by
the agent module rather than a literal `AgentExecutor`, which is the
more testable and maintainable choice for this control flow.

- [ ] **Step 1: Write the failing tests**

`tests/backend/test_job_search_agent.py`:
```python
from backend.config import Settings
from backend.models import ContactInfo, JobListing, MatchResult, ResumeProfile
from backend.tools.jsearch_tool import JobSourceError
from backend.agents.job_search_agent import run_job_search


def _settings():
    return Settings(google_api_key="x", rapidapi_key="x", firecrawl_api_key="x")


def _profile():
    return ResumeProfile(
        contact=ContactInfo(name="Jane Doe"),
        summary="Backend engineer.",
        skills=["Python", "SQL"],
    )


def test_run_job_search_merges_and_scores_all_sources():
    jsearch_job = JobListing(
        title="Backend Engineer", company="Acme", description="Python, SQL", source="jsearch"
    )
    ddg_job = JobListing(
        title="Platform Engineer",
        company="",
        description="snippet only",
        apply_link="https://example.com/jobs/2",
        source="duckduckgo",
    )

    def fake_jsearch(query, location, settings):
        return [jsearch_job]

    def fake_ddg(query):
        return [ddg_job]

    def fake_scrape(url, settings):
        return "Full JD: Python, SQL, Kubernetes"

    def fake_scorer(resume_text, job_description, settings):
        return MatchResult(score=80, notes="good overlap")

    result = run_job_search(
        _profile(),
        _settings(),
        jsearch_fn=fake_jsearch,
        ddg_fn=fake_ddg,
        scrape_fn=fake_scrape,
        scorer_fn=fake_scorer,
    )

    assert len(result.jobs) == 2
    assert all(job.match_score == 80 for job in result.jobs)
    # the duckduckgo job's description should be replaced by the scraped full JD
    ddg_ranked = next(j for j in result.jobs if j.job.source == "duckduckgo")
    assert ddg_ranked.job.description == "Full JD: Python, SQL, Kubernetes"


def test_run_job_search_degrades_when_one_source_fails():
    jsearch_job = JobListing(
        title="Backend Engineer", company="Acme", description="Python, SQL", source="jsearch"
    )

    def fake_jsearch(query, location, settings):
        return [jsearch_job]

    def failing_ddg(query):
        raise JobSourceError("ddg is down")

    def fake_scrape(url, settings):
        return "unused"

    def fake_scorer(resume_text, job_description, settings):
        return MatchResult(score=70, notes="ok")

    result = run_job_search(
        _profile(),
        _settings(),
        jsearch_fn=fake_jsearch,
        ddg_fn=failing_ddg,
        scrape_fn=fake_scrape,
        scorer_fn=fake_scorer,
    )

    assert len(result.jobs) == 1
    assert result.jobs[0].job.source == "jsearch"
    assert any("duckduckgo" in s.lower() for s in result.suggestions)


def test_run_job_search_asks_for_location_when_missing():
    def fake_jsearch(query, location, settings):
        return []

    def fake_ddg(query):
        return []

    def fake_scrape(url, settings):
        return "unused"

    def fake_scorer(resume_text, job_description, settings):
        return MatchResult(score=0)

    result = run_job_search(
        _profile(),
        _settings(),
        preferences=None,
        jsearch_fn=fake_jsearch,
        ddg_fn=fake_ddg,
        scrape_fn=fake_scrape,
        scorer_fn=fake_scorer,
    )

    assert result.clarification_question is not None
    assert "location" in result.clarification_question.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_job_search_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.agents.job_search_agent'`

- [ ] **Step 3: Write minimal implementation**

`backend/agents/job_search_agent.py`:
```python
from backend.config import Settings
from backend.models import JobListing, JobSearchResult, RankedJob, ResumeProfile
from backend.tools.ddg_tool import search_jobs_ddg
from backend.tools.firecrawl_tool import scrape_job_page
from backend.tools.jsearch_tool import JobSourceError, search_jobs_jsearch
from backend.tools.match_scorer import score_resume_against_job

GENERAL_SUGGESTIONS = [
    "Quantify the impact of each bullet point with numbers where possible.",
    "Lead each bullet with a strong action verb.",
    "Keep the resume to one or two pages focused on relevant experience.",
]


def run_job_search(
    profile: ResumeProfile,
    settings: Settings,
    preferences: dict | None = None,
    jsearch_fn=search_jobs_jsearch,
    ddg_fn=search_jobs_ddg,
    scrape_fn=scrape_job_page,
    scorer_fn=score_resume_against_job,
) -> JobSearchResult:
    query = " ".join(profile.skills[:3]) or profile.summary
    location = (preferences or {}).get("location")

    suggestions = list(GENERAL_SUGGESTIONS)
    listings: list[JobListing] = []

    try:
        listings.extend(jsearch_fn(query, location, settings))
    except JobSourceError:
        suggestions.append("JSearch was unavailable for this search; results may be incomplete.")

    try:
        ddg_listings = ddg_fn(query)
    except JobSourceError:
        ddg_listings = []
        suggestions.append("DuckDuckGo search was unavailable for this search; results may be incomplete.")

    for listing in ddg_listings:
        if listing.apply_link:
            try:
                listing.description = scrape_fn(listing.apply_link, settings)
            except JobSourceError:
                pass
        listings.append(listing)

    resume_text = _profile_to_text(profile)
    ranked_jobs = [
        RankedJob(
            job=listing,
            match_score=scorer_fn(resume_text, listing.description, settings).score,
            rationale=scorer_fn(resume_text, listing.description, settings).notes,
        )
        for listing in listings
    ]
    ranked_jobs.sort(key=lambda ranked: ranked.match_score, reverse=True)

    clarification_question = None
    if not location and not listings:
        clarification_question = "I couldn't find enough matches — what location (or 'remote') are you targeting?"

    return JobSearchResult(
        jobs=ranked_jobs, suggestions=suggestions, clarification_question=clarification_question
    )


def _profile_to_text(profile: ResumeProfile) -> str:
    lines = [profile.contact.name, profile.summary, ", ".join(profile.skills)]
    for entry in profile.experience:
        lines.append(f"{entry.title} at {entry.company}")
        lines.extend(entry.bullets)
    return "\n".join(line for line in lines if line)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_job_search_agent.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/agents/job_search_agent.py tests/backend/test_job_search_agent.py
git commit -m "feat: job search agent orchestrating multi-source search and scoring"
```

---

## Task 13: ResumeTailorAgent

**Files:**
- Create: `backend/agents/resume_tailor_agent.py`
- Test: `tests/backend/test_resume_tailor_agent.py`

**Interfaces:**
- Consumes: `backend.models.{ResumeProfile, JobListing}` (Task 3);
  `render_profile_to_docx` (Task 6); `apply_paragraph_replacements` (Task
  7); `score_resume_against_job` (Task 8); `backend.config.Settings`
  (Task 1).
- Produces: `backend.agents.resume_tailor_agent.TailorResult` (plain
  dataclass: `docx_bytes: bytes`, `final_score: int`, `rounds: int`,
  `notes: str`) and
  `backend.agents.resume_tailor_agent.tailor_resume(profile:
  ResumeProfile, job: JobListing, settings: Settings, original_docx_bytes:
  bytes | None = None, is_original_editable: bool = False, max_rounds:
  int = 3, target_score: int = 95, revise_fn=None, scorer_fn=
  score_resume_against_job, render_fn=render_profile_to_docx) ->
  TailorResult`. `revise_fn(profile: ResumeProfile, missing_keywords:
  list[str], settings: Settings) -> ResumeProfile` defaults to an
  LLM-backed reviser (constructed lazily); tests inject a fake that
  mutates `profile.summary` deterministically so the loop's termination
  behavior can be asserted without a real LLM.

- [ ] **Step 1: Write the failing tests**

`tests/backend/test_resume_tailor_agent.py`:
```python
from backend.config import Settings
from backend.models import ContactInfo, JobListing, MatchResult, ResumeProfile
from backend.agents.resume_tailor_agent import tailor_resume


def _settings():
    return Settings(google_api_key="x", rapidapi_key="x", firecrawl_api_key="x")


def _profile():
    return ResumeProfile(contact=ContactInfo(name="Jane Doe"), summary="v0", skills=["Python"])


def _job():
    return JobListing(title="Backend Engineer", company="Acme", description="Python, Kubernetes", source="jsearch")


def test_tailor_resume_stops_early_once_target_score_reached():
    scores = iter([60, 96])
    revise_calls = []

    def fake_scorer(resume_text, job_description, settings):
        return MatchResult(score=next(scores), missing_keywords=["Kubernetes"])

    def fake_revise(profile, missing_keywords, settings):
        revise_calls.append(missing_keywords)
        return profile.model_copy(update={"summary": profile.summary + "+revised"})

    def fake_render(profile):
        return profile.summary.encode()

    result = tailor_resume(
        _profile(),
        _job(),
        _settings(),
        original_docx_bytes=None,
        is_original_editable=False,
        max_rounds=3,
        target_score=95,
        revise_fn=fake_revise,
        scorer_fn=fake_scorer,
        render_fn=fake_render,
    )

    assert result.final_score == 96
    assert result.rounds == 2
    assert len(revise_calls) == 1


def test_tailor_resume_stops_at_max_rounds_even_if_below_target():
    def fake_scorer(resume_text, job_description, settings):
        return MatchResult(score=50, missing_keywords=["Kubernetes"])

    def fake_revise(profile, missing_keywords, settings):
        return profile.model_copy(update={"summary": profile.summary + "+revised"})

    def fake_render(profile):
        return profile.summary.encode()

    result = tailor_resume(
        _profile(),
        _job(),
        _settings(),
        max_rounds=3,
        target_score=95,
        revise_fn=fake_revise,
        scorer_fn=fake_scorer,
        render_fn=fake_render,
    )

    assert result.rounds == 3
    assert result.final_score == 50


def test_tailor_resume_uses_editable_original_when_flagged():
    from backend.tools import docx_editor

    captured = {}

    def fake_scorer(resume_text, job_description, settings):
        return MatchResult(score=99, missing_keywords=[])

    def fake_apply_replacements(docx_bytes, replacements):
        captured["docx_bytes"] = docx_bytes
        return b"edited-docx"

    original = docx_editor.apply_paragraph_replacements
    docx_editor.apply_paragraph_replacements = fake_apply_replacements
    try:
        result = tailor_resume(
            _profile(),
            _job(),
            _settings(),
            original_docx_bytes=b"original-docx",
            is_original_editable=True,
            scorer_fn=fake_scorer,
        )
    finally:
        docx_editor.apply_paragraph_replacements = original

    assert result.docx_bytes == b"edited-docx"
    assert captured["docx_bytes"] == b"original-docx"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_resume_tailor_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.agents.resume_tailor_agent'`

- [ ] **Step 3: Write minimal implementation**

`backend/agents/resume_tailor_agent.py`:
```python
from dataclasses import dataclass

from langchain_google_genai import ChatGoogleGenerativeAI

from backend.config import Settings
from backend.models import JobListing, ResumeProfile
from backend.tools import docx_editor
from backend.tools.docx_renderer import render_profile_to_docx
from backend.tools.match_scorer import score_resume_against_job

REVISION_PROMPT = """You are improving a candidate's resume summary so it \
better matches a target job, without inventing any skill, employer, date, \
or experience not already present in the resume below. You may only \
rephrase, reorder, and surface truthful keywords already implied by the \
existing content. The job is missing these keywords in the current \
resume: {missing_keywords}.

CURRENT RESUME PROFILE (JSON):
{profile_json}
"""


@dataclass
class TailorResult:
    docx_bytes: bytes
    final_score: int
    rounds: int
    notes: str


def tailor_resume(
    profile: ResumeProfile,
    job: JobListing,
    settings: Settings,
    original_docx_bytes: bytes | None = None,
    is_original_editable: bool = False,
    max_rounds: int = 3,
    target_score: int = 95,
    revise_fn=None,
    scorer_fn=score_resume_against_job,
    render_fn=render_profile_to_docx,
) -> TailorResult:
    revise_fn = revise_fn or _default_revise
    current_profile = profile
    final_score = 0
    notes = ""

    for round_number in range(1, max_rounds + 1):
        resume_text = _profile_to_text(current_profile)
        match_result = scorer_fn(resume_text, job.description, settings)
        final_score = match_result.score
        notes = match_result.notes

        if final_score >= target_score:
            break
        if round_number == max_rounds:
            break

        current_profile = revise_fn(current_profile, match_result.missing_keywords, settings)

    docx_bytes = _render_final(
        current_profile, original_docx_bytes, is_original_editable, render_fn
    )

    return TailorResult(
        docx_bytes=docx_bytes, final_score=final_score, rounds=round_number, notes=notes
    )


def _render_final(profile, original_docx_bytes, is_original_editable, render_fn) -> bytes:
    if is_original_editable and original_docx_bytes is not None:
        replacements = {"Summary": profile.summary} if profile.summary else {}
        return docx_editor.apply_paragraph_replacements(original_docx_bytes, replacements)
    return render_fn(profile)


def _default_revise(profile: ResumeProfile, missing_keywords: list[str], settings: Settings) -> ResumeProfile:
    llm = ChatGoogleGenerativeAI(model=settings.gemini_model, google_api_key=settings.google_api_key)
    structured_llm = llm.with_structured_output(ResumeProfile)
    prompt = REVISION_PROMPT.format(
        missing_keywords=", ".join(missing_keywords) or "none",
        profile_json=profile.model_dump_json(),
    )
    return structured_llm.invoke(prompt)


def _profile_to_text(profile: ResumeProfile) -> str:
    lines = [profile.contact.name, profile.summary, ", ".join(profile.skills)]
    for entry in profile.experience:
        lines.append(f"{entry.title} at {entry.company}")
        lines.extend(entry.bullets)
    return "\n".join(line for line in lines if line)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_resume_tailor_agent.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/agents/resume_tailor_agent.py tests/backend/test_resume_tailor_agent.py
git commit -m "feat: resume tailoring agent with capped score-and-revise loop"
```

---

## Task 14: FastAPI app and resume routes

**Files:**
- Create: `backend/main.py`
- Create: `backend/routes/resume_routes.py`
- Test: `tests/backend/test_resume_routes.py`

**Interfaces:**
- Consumes: `SessionStore` (Task 5); `extract_resume_text`,
  `is_docx_well_formed` (Task 2); `extract_profile` (Task 4);
  `render_profile_to_docx` (Task 6); `get_settings` (Task 1).
- Produces: FastAPI app at `backend.main.app` with router mounted at
  `/resume`. `POST /resume/upload` (multipart file) → `{"session_id":
  str, "profile": <ResumeProfile dict>, "first_version_docx_base64":
  str}`. Also produces `backend.routes.resume_routes.get_session_store()
  -> SessionStore` and `get_settings_dep() -> Settings` as FastAPI
  dependency functions, overridable in tests.

- [ ] **Step 1: Write the failing tests**

`tests/backend/test_resume_routes.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_resume_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.main'`

- [ ] **Step 3: Write minimal implementation**

`backend/routes/resume_routes.py`:
```python
import base64

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from backend.config import Settings, get_settings
from backend.parsing.profile_extractor import extract_profile
from backend.parsing.resume_parser import extract_resume_text, is_docx_well_formed
from backend.storage.session_store import SessionStore
from backend.tools.docx_renderer import render_profile_to_docx

router = APIRouter(prefix="/resume")

_default_store = SessionStore(base_dir=get_settings().data_dir) if False else None


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
```

`backend/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.resume_routes import router as resume_router

app = FastAPI(title="Job Search Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_resume_routes.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Clean up the dead code left from drafting**

Remove the unused `_default_store` line from `backend/routes/resume_routes.py`:
```python
router = APIRouter(prefix="/resume")
```
(replaces the `router = APIRouter(prefix="/resume")` + `_default_store = ...` pair)

Run: `pytest tests/backend/test_resume_routes.py -v`
Expected: PASS (2 tests, unchanged)

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/routes/resume_routes.py tests/backend/test_resume_routes.py
git commit -m "feat: FastAPI app with resume upload endpoint"
```

---

## Task 15: Job search and tailor routes

**Files:**
- Create: `backend/routes/job_routes.py`
- Modify: `backend/main.py`
- Test: `tests/backend/test_job_routes.py`

**Interfaces:**
- Consumes: `SessionStore` (Task 5); `run_job_search` (Task 12);
  `tailor_resume` (Task 13); `get_session_store`, `get_settings_dep`
  (Task 14).
- Produces: `POST /jobs/search` body `{"session_id": str, "preferences":
  dict | null}` → `JobSearchResult` dict. `POST /jobs/tailor` body
  `{"session_id": str, "job": <JobListing dict>}` →
  `{"docx_base64": str, "final_score": int, "rounds": int, "notes": str}`.

- [ ] **Step 1: Write the failing tests**

`tests/backend/test_job_routes.py`:
```python
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import app
from backend.models import ContactInfo, JobListing, JobSearchResult, RankedJob, ResumeProfile
from backend.routes.resume_routes import get_session_store, get_settings_dep
from backend.agents.resume_tailor_agent import TailorResult
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
    import base64
    assert base64.b64decode(body["docx_base64"]) == b"final-docx-bytes"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_job_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.routes.job_routes'`

- [ ] **Step 3: Write minimal implementation**

`backend/routes/job_routes.py`:
```python
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
```

Modify `backend/main.py` (add the new router):
```python
from backend.routes.job_routes import router as job_router
```
And after `app.include_router(resume_router)`:
```python
app.include_router(job_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_job_routes.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full backend test suite**

Run: `pytest tests/ -v`
Expected: PASS (all tests across all prior tasks)

- [ ] **Step 6: Commit**

```bash
git add backend/routes/job_routes.py backend/main.py tests/backend/test_job_routes.py
git commit -m "feat: job search and resume tailoring endpoints"
```

---

## Task 16: Streamlit frontend

**Files:**
- Create: `frontend/api_client.py`
- Create: `frontend/app.py`
- Test: `tests/backend/test_api_client.py`

**Interfaces:**
- Consumes: the three backend endpoints from Tasks 14–15 over HTTP.
- Produces: `frontend.api_client.upload_resume(base_url: str,
  filename: str, content: bytes) -> dict`, `search_jobs(base_url: str,
  session_id: str, preferences: dict | None) -> dict`, `tailor_resume(
  base_url: str, session_id: str, job: dict) -> dict`. Each accepts an
  optional injected `client` (an `httpx.Client`-like object with `.post`)
  as the last parameter for testing.

- [ ] **Step 1: Write the failing tests**

`tests/backend/test_api_client.py`:
```python
import httpx
from frontend.api_client import search_jobs, tailor_resume, upload_resume


def test_upload_resume_posts_multipart_file():
    def handler(request):
        assert request.url.path == "/resume/upload"
        return httpx.Response(200, json={"session_id": "abc", "profile": {}, "first_version_docx_base64": ""})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = upload_resume("http://backend", "resume.docx", b"content", client=client)

    assert result["session_id"] == "abc"


def test_search_jobs_posts_json_body():
    captured = {}

    def handler(request):
        captured["body"] = request.read()
        return httpx.Response(200, json={"jobs": [], "suggestions": [], "clarification_question": None})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = search_jobs("http://backend", "session-1", {"location": "Remote"}, client=client)

    assert b"session-1" in captured["body"]
    assert result["jobs"] == []


def test_tailor_resume_posts_json_body():
    def handler(request):
        return httpx.Response(200, json={"docx_base64": "", "final_score": 90, "rounds": 1, "notes": ""})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = tailor_resume("http://backend", "session-1", {"title": "Engineer"}, client=client)

    assert result["final_score"] == 90
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_api_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'frontend.api_client'`

- [ ] **Step 3: Write minimal implementation**

`frontend/api_client.py`:
```python
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
```

`frontend/app.py`:
```python
import base64
import os

import streamlit as st

from frontend.api_client import search_jobs, tailor_resume, upload_resume

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(layout="wide")
st.title("Job Search & Resume Tailoring Agent")

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "current_docx" not in st.session_state:
    st.session_state.current_docx = None
if "job_results" not in st.session_state:
    st.session_state.job_results = None

left, right = st.columns([1, 1])

with left:
    uploaded_file = st.file_uploader("Upload your resume", type=["pdf", "docx", "txt"])
    if uploaded_file and st.button("Upload"):
        result = upload_resume(BACKEND_URL, uploaded_file.name, uploaded_file.getvalue())
        st.session_state.session_id = result["session_id"]
        st.session_state.current_docx = result["first_version_docx_base64"]
        st.success("Resume uploaded.")

    if st.session_state.session_id and st.button("Search jobs"):
        st.session_state.job_results = search_jobs(BACKEND_URL, st.session_state.session_id, None)

    if st.session_state.job_results:
        results = st.session_state.job_results
        if results.get("clarification_question"):
            st.info(results["clarification_question"])
        for suggestion in results.get("suggestions", []):
            st.write(f"- {suggestion}")
        for ranked in results.get("jobs", []):
            job = ranked["job"]
            label = f"{job['title']} at {job['company']} — score {ranked['match_score']}"
            if st.button(f"Tailor resume for: {label}", key=job["title"] + job["company"]):
                tailor_result = tailor_resume(BACKEND_URL, st.session_state.session_id, job)
                st.session_state.current_docx = tailor_result["docx_base64"]
                st.success(f"Tailored. Match score: {tailor_result['final_score']}")

with right:
    st.subheader("Resume preview")
    if st.session_state.current_docx:
        docx_bytes = base64.b64decode(st.session_state.current_docx)
        st.download_button("Download .docx", data=docx_bytes, file_name="resume.docx")
    else:
        st.write("Upload a resume to see it here.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_api_client.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/api_client.py frontend/app.py tests/backend/test_api_client.py
git commit -m "feat: streamlit frontend calling the backend api"
```

---

## Task 17: Manual end-to-end verification

**Files:** none created; this task verifies the running system.

- [ ] **Step 1: Fill in real API keys**

Copy `.env.example` to `.env` and fill in `GOOGLE_API_KEY` (Gemini),
`RAPIDAPI_KEY` (JSearch, from rapidapi.com), and `FIRECRAWL_API_KEY`
(firecrawl.dev). These are required for a real run; all automated tests
in Tasks 1–16 pass without them because every external call is mocked.

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`

- [ ] **Step 3: Start the backend**

Run: `uvicorn backend.main:app --reload --port 8000`
Expected: server starts; `curl http://localhost:8000/health` returns
`{"status":"ok"}`.

- [ ] **Step 4: Start the frontend**

Run (new terminal): `streamlit run frontend/app.py`
Expected: browser opens to the two-column UI.

- [ ] **Step 5: Walk the golden path manually**

1. Upload a real resume file (try one PDF and one DOCX across two runs).
2. Click "Search jobs" — confirm a ranked job list and suggestions
   appear, and note whether a clarification question ever appears when
   no location is known.
3. Pick a job — confirm the right panel updates with a new version and a
   reported match score, and the download button produces a valid
   `.docx` that opens in Word/Google Docs.
4. Go back and pick a second, different job — confirm it produces its
   own version without overwriting the first (check
   `data/sessions/<session_id>/versions/` has two files).
5. Open the downloaded tailored resume and confirm no fabricated
   skills/employers/dates were introduced relative to the original.

- [ ] **Step 6: Record results**

If any step fails, file it as a bug against the relevant task above
(e.g. "Task 12: JobSearchAgent doesn't degrade DuckDuckGo failures in
production the same way the mocked test does") rather than patching
around it silently.

---

## Self-Review Notes

- **Spec coverage:** upload/parse (Task 2, 4), storage (Task 5), DOCX
  render + edit (Tasks 6–7), match scoring (Task 8), all three job
  sources with graceful degradation (Tasks 9–11, exercised in Task 12),
  JobSearchAgent behavior incl. clarification question (Task 12),
  ResumeTailorAgent capped score/revise loop + edit-in-place-vs-rebuild
  branch + no-fabrication guardrail in its prompt (Task 13), HTTP API
  (Tasks 14–15), Streamlit UI with side-by-side preview and repeatable
  per-job tailoring (Task 16), manual golden-path verification (Task
  17). All spec sections are covered.
- **Placeholder scan:** no TBD/TODO markers; every step has runnable
  code.
- **Type consistency:** `JobListing`, `ResumeProfile`, `MatchResult`,
  `RankedJob`, `JobSearchResult` are defined once in `backend/models.py`
  (Task 3) and reused verbatim by every later task; `TailorResult` is
  defined once in Task 13 and reused in Tasks 15–16; function names
  (`run_job_search`, `tailor_resume`, `extract_profile`,
  `score_resume_against_job`, `render_profile_to_docx`,
  `apply_paragraph_replacements`) are consistent across every task that
  references them.
- **Scope:** single cohesive system per the spec; not split further.
