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
    ranked_jobs = []
    for listing in listings:
        match_result = scorer_fn(resume_text, listing.description, settings)
        ranked_jobs.append(
            RankedJob(job=listing, match_score=match_result.score, rationale=match_result.notes)
        )
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
