from backend.models import (
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    JobListing,
    JobSearchResult,
    MatchResult,
    RankedJob,
    ResumeProfile,
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
