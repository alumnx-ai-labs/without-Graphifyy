from backend.agents.resume_tailor_agent import tailor_resume
from backend.config import Settings
from backend.models import ContactInfo, JobListing, MatchResult, ResumeProfile


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
