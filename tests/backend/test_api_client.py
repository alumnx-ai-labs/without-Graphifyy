import httpx

from frontend.api_client import search_jobs, tailor_resume, upload_resume


def test_upload_resume_posts_multipart_file():
    def handler(request):
        assert request.url.path == "/resume/upload"
        return httpx.Response(200, json={"session_id": "abc", "profile": {}, "first_version_docx_base64": ""})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = upload_resume("http://backend", "resume.docx", b"content", client=client)

    assert result["session_id"] == "abc"


def test_search_jobs_posts_json_body():
    captured = {}

    def handler(request):
        captured["body"] = request.read()
        return httpx.Response(200, json={"jobs": [], "suggestions": [], "clarification_question": None})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = search_jobs("http://backend", "session-1", {"location": "Remote"}, client=client)

    assert b"session-1" in captured["body"]
    assert result["jobs"] == []


def test_tailor_resume_posts_json_body():
    def handler(request):
        return httpx.Response(200, json={"docx_base64": "", "final_score": 90, "rounds": 1, "notes": ""})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = tailor_resume("http://backend", "session-1", {"title": "Engineer"}, client=client)

    assert result["final_score"] == 90
