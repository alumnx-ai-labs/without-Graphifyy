from langchain_google_genai import ChatGoogleGenerativeAI

from backend.config import Settings
from backend.models import MatchResult

SCORING_PROMPT = """You are scoring how well a resume matches a job \
description. Score from 0 to 100 based on skills/keyword overlap and \
relevant experience. List specific keywords or requirements from the job \
description that are missing from the resume. Be concise in your notes.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}
"""


def score_resume_against_job(
    resume_text: str, job_description: str, settings: Settings, llm=None
) -> MatchResult:
    if llm is None:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model, google_api_key=settings.google_api_key
        )
    structured_llm = llm.with_structured_output(MatchResult)
    prompt = SCORING_PROMPT.format(resume_text=resume_text, job_description=job_description)
    return structured_llm.invoke(prompt)
