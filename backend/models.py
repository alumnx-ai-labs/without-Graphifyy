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
