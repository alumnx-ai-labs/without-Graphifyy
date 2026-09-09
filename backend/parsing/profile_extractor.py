from langchain_google_genai import ChatGoogleGenerativeAI

from backend.config import Settings
from backend.models import ResumeProfile

EXTRACTION_PROMPT = """You extract structured resume data. Read the resume \
text below and populate every field you can find. Never invent \
information that is not present in the text; leave fields empty or null \
if the resume does not state them.

RESUME TEXT:
{resume_text}
"""


def extract_profile(resume_text: str, settings: Settings, llm=None) -> ResumeProfile:
    if llm is None:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model, google_api_key=settings.google_api_key
        )
    structured_llm = llm.with_structured_output(ResumeProfile)
    prompt = EXTRACTION_PROMPT.format(resume_text=resume_text)
    return structured_llm.invoke(prompt)
