from backend.agents.job_search_agent import run_job_search
from backend.config import Settings
from backend.models import ContactInfo, JobListing, MatchResult, ResumeProfile
from backend.tools.jsearch_tool import JobSourceError


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
