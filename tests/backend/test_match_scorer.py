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
