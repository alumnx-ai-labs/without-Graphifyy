import io

import pytest
from docx import Document

from backend.parsing.resume_parser import extract_resume_text, is_docx_well_formed


def _make_docx_bytes(paragraphs):
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extract_resume_text_from_txt():
    content = b"Jane Doe\nSoftware Engineer\nSkills: Python, SQL"
    text = extract_resume_text("resume.txt", content)
    assert "Jane Doe" in text
    assert "Python" in text


def test_extract_resume_text_from_docx():
    content = _make_docx_bytes(["Jane Doe", "Software Engineer", "Skills: Python, SQL"])
    text = extract_resume_text("resume.docx", content)
    assert "Jane Doe" in text
    assert "Skills: Python, SQL" in text


def test_extract_resume_text_unsupported_extension_raises():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_resume_text("resume.xyz", b"whatever")


def test_is_docx_well_formed_true_for_multi_paragraph_docx():
    content = _make_docx_bytes([f"Line {i}" for i in range(10)])
    assert is_docx_well_formed(content) is True


def test_is_docx_well_formed_false_for_sparse_docx():
    content = _make_docx_bytes(["Everything crammed into a single paragraph"])
    assert is_docx_well_formed(content) is False


def test_is_docx_well_formed_false_for_non_docx_bytes():
    assert is_docx_well_formed(b"not a docx file at all") is False
