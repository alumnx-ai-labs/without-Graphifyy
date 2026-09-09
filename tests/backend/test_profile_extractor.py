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
