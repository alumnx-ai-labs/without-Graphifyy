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
