# Job Search & Resume Tailoring Agent — Design

## Goal

Given a user's resume (any common format), find matching jobs and produce
a resume tailored to a specific job the user picks — maximizing a
measurable match score against that job's description, without
fabricating experience the candidate doesn't have.

## Non-goals

- No guarantee of interview callbacks — "100% match" is treated as
  "maximize the measurable match score," not a promise about hiring
  outcomes.
- No user accounts / auth / multi-tenant persistence. Single-user,
  session-scoped, filesystem storage is sufficient for v1.
- No fabrication of skills, employers, dates, or experience not present
  in the source resume, even to raise the score.

## Architecture

- **Backend:** FastAPI (Python). Hosts two LangChain ReAct agents and
  exposes HTTP endpoints for resume upload, job search, and resume
  tailoring.
- **Frontend:** Streamlit. Two-column layout — left: chat-style controls
  (upload, job list, clarifying questions); right: live resume preview
  (rendered from the current DOCX version) plus a download button.
- **LLM:** Google Gemini via `langchain-google-genai`, used by both
  agents and by the shared match-scoring tool.
- **Job data sources:** JSearch (RapidAPI) for structured listings,
  DuckDuckGo search for supplementary discovery, Firecrawl to scrape
  full job-description text from URLs found via search.

## Components

### Agent 1 — JobSearchAgent (ReAct)

Tools: JSearch search, DuckDuckGo search, Firecrawl scrape, match scorer.

Given a structured resume profile (and optional user preferences like
location/salary), it searches across sources, scores each candidate job
against the profile, and returns a ranked list with per-job rationale,
plus a list of general (job-independent) resume improvement suggestions.
It may ask the user one clarifying question (e.g. desired location) when
it judges the profile lacks enough signal — this is optional per run, not
forced every turn.

### Agent 2 — ResumeTailorAgent (ReAct, the "skill")

Tools: DOCX in-place editor, structured-profile-to-DOCX renderer, match
scorer (shared with Agent 1).

Invoked once the user selects a specific job from Agent 1's list. Each
selection is independent — the user can tailor for multiple jobs across a
session, and each produces its own saved version.

Edit path:
- If the original upload is a well-formed DOCX, edit it in place
  (preserve the user's template/styling).
- Otherwise (PDF, plain text, or a DOCX judged poorly structured),
  rebuild a clean DOCX from the structured profile.

Loop: draft an edit → score it against the job description via the match
scorer → if below a target threshold and rounds remain, revise again,
addressing the scorer's flagged gaps. Hard-capped at a small fixed number
of rounds (default 3) so it terminates regardless of score. Returns the
best-scoring version reached.

**Guardrail (applies to both agents' prompts):** never invent skills,
employers, dates, or experience absent from the source resume. Only
rephrase, reorder, emphasize, and surface truthful keywords already
implied by existing content.

## Data flow

1. User uploads a resume (any format) via Streamlit → `POST
   /resume/upload`.
2. Backend extracts raw text (PDF/DOCX/plain text parsers), judges
   whether the original DOCX (if any) is well-formed enough to edit in
   place, and has Gemini extract a structured `ResumeProfile`. A session
   is created; the upload, extracted text, and profile are persisted
   under a per-session filesystem directory.
3. Streamlit calls `POST /jobs/search` with the session id (and any
   stated preferences). JobSearchAgent runs and returns ranked jobs +
   general suggestions (+ an optional clarifying question, surfaced as a
   chat prompt).
4. User selects a job → `POST /resume/tailor` with session id + the
   chosen job. ResumeTailorAgent runs its draft/score/revise loop and
   returns a new DOCX version, its final score, and how many rounds it
   took. The version is saved under the session, keyed by job, without
   overwriting prior versions.
5. Streamlit's right panel re-renders to show the new version and offers
   a download. The user may return to the job list and repeat step 4 for
   a different job at any time.

## Error handling

- Corrupt or unsupported uploads produce a clear error surfaced in the
  chat UI; the backend never crashes on bad input.
- If any single job source (JSearch, DuckDuckGo, or Firecrawl) fails or
  times out, JobSearchAgent drops that source, notes reduced coverage in
  its response, and continues with the remaining sources rather than
  failing the whole search.
- The tailoring loop has both a round cap and a wall-clock timeout.

## Testing strategy

- Unit tests for parsing (PDF/DOCX/plain text → text), structured-profile
  extraction, DOCX rendering/editing, and match scoring — all against
  fixture resumes/JDs, with the LLM and external HTTP calls mocked.
- Unit tests per job-source tool (JSearch, DuckDuckGo, Firecrawl) against
  mocked HTTP responses, including the failure/degrade path.
- Agent-level tests with the underlying LLM and tools mocked, asserting
  the agents assemble and parse their structured outputs correctly and
  that the tailoring loop respects the round cap and score threshold.
- FastAPI route tests via `TestClient` with the agents monkeypatched.
- Manual end-to-end walkthrough through the actual Streamlit UI for the
  golden path (upload → search → select → tailor → download) before
  calling the feature done.

## Configuration

Environment variables (see `.env.example`): `GOOGLE_API_KEY` (Gemini),
`GEMINI_MODEL` (default `gemini-2.0-flash`), `RAPIDAPI_KEY` (JSearch),
`FIRECRAWL_API_KEY`.
