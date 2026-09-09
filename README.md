# Job Search & Resume Tailoring Agent

Upload a resume, find matching jobs, and get a tailored resume rewritten toward a
specific listing — without inventing any skill, employer, or date that isn't
already in the original.

## How it works

1. **Upload** (`POST /resume/upload`) — the resume (`.pdf`, `.docx`, or `.txt`) is
   parsed to text and turned into a structured profile by Gemini. A session is
   created to hold the profile and the original file.
2. **Search** (`POST /jobs/search`) — job listings are pulled from JSearch
   (RapidAPI) and DuckDuckGo, scraped for full descriptions where needed, and
   ranked by how well each matches the resume.
3. **Tailor** (`POST /jobs/tailor`) — for a chosen job, the resume is scored
   against the listing and revised in rounds (up to 3, or until a 95+ match
   score) to surface truthful, already-present keywords the job is looking for.
   The result is rendered back out as a `.docx`.

## Stack

- **Backend:** FastAPI, LangChain + `langchain-google-genai` (Gemini 2.0 Flash),
  `pypdf`, `python-docx`
- **Frontend:** Streamlit
- **Storage:** flat files under `data/sessions/<session_id>/` — no database

## Project layout

```
backend/
├── routes/    # resume_routes.py, job_routes.py
├── agents/    # job_search_agent.py, resume_tailor_agent.py
├── parsing/   # resume text extraction, profile extraction
├── tools/     # job search sources, match scoring, docx render/edit
└── storage/   # session persistence
frontend/      # Streamlit UI
tests/backend/ # mirrors backend/
```

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in GOOGLE_API_KEY, RAPIDAPI_KEY, FIRECRAWL_API_KEY

uvicorn backend.main:app --reload
streamlit run frontend/app.py
```

Run tests with:

```bash
pytest
```

## Configuration

Set in `.env` (see `.env.example`):

| Variable | Required | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | yes | Gemini access for extraction, scoring, and revision |
| `GEMINI_MODEL` | no (default `gemini-2.0-flash`) | Model used for all Gemini calls |
| `RAPIDAPI_KEY` | yes | JSearch job listings |
| `FIRECRAWL_API_KEY` | yes | Scraping job posting pages |
| `DATA_DIR` | no (default `./data/sessions`) | Session storage location |

#
