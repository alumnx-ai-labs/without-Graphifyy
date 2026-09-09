import io

from docx import Document

from backend.models import ContactInfo, EducationEntry, ExperienceEntry, ResumeProfile
from backend.tools.docx_renderer import render_profile_to_docx


def test_render_profile_to_docx_includes_all_sections():
    profile = ResumeProfile(
        contact=ContactInfo(name="Jane Doe", email="jane@example.com"),
        summary="Backend engineer with 5 years experience.",
        skills=["Python", "SQL"],
        experience=[
            ExperienceEntry(
                title="Software Engineer",
                company="Acme",
                start_date="2020",
                end_date="2023",
                bullets=["Built the widget service"],
            )
        ],
        education=[EducationEntry(degree="B.S. CS", institution="State U", year="2019")],
        certifications=["AWS SAA"],
    )

    docx_bytes = render_profile_to_docx(profile)

    doc = Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Jane Doe" in full_text
    assert "jane@example.com" in full_text
    assert "Backend engineer with 5 years experience." in full_text
    assert "Python" in full_text and "SQL" in full_text
    assert "Software Engineer" in full_text and "Acme" in full_text
    assert "Built the widget service" in full_text
    assert "B.S. CS" in full_text and "State U" in full_text
    assert "AWS SAA" in full_text
