import base64
import os

import streamlit as st

from frontend.api_client import search_jobs, tailor_resume, upload_resume

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(layout="wide")
st.title("Job Search & Resume Tailoring Agent")

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "current_docx" not in st.session_state:
    st.session_state.current_docx = None
if "job_results" not in st.session_state:
    st.session_state.job_results = None

left, right = st.columns([1, 1])

with left:
    uploaded_file = st.file_uploader("Upload your resume", type=["pdf", "docx", "txt"])
    if uploaded_file and st.button("Upload"):
        result = upload_resume(BACKEND_URL, uploaded_file.name, uploaded_file.getvalue())
        st.session_state.session_id = result["session_id"]
        st.session_state.current_docx = result["first_version_docx_base64"]
        st.success("Resume uploaded.")

    if st.session_state.session_id and st.button("Search jobs"):
        st.session_state.job_results = search_jobs(BACKEND_URL, st.session_state.session_id, None)

    if st.session_state.job_results:
        results = st.session_state.job_results
        if results.get("clarification_question"):
            st.info(results["clarification_question"])
        for suggestion in results.get("suggestions", []):
            st.write(f"- {suggestion}")
        for ranked in results.get("jobs", []):
            job = ranked["job"]
            label = f"{job['title']} at {job['company']} — score {ranked['match_score']}"
            if st.button(f"Tailor resume for: {label}", key=job["title"] + job["company"]):
                tailor_result = tailor_resume(BACKEND_URL, st.session_state.session_id, job)
                st.session_state.current_docx = tailor_result["docx_base64"]
                st.success(f"Tailored. Match score: {tailor_result['final_score']}")

with right:
    st.subheader("Resume preview")
    if st.session_state.current_docx:
        docx_bytes = base64.b64decode(st.session_state.current_docx)
        st.download_button("Download .docx", data=docx_bytes, file_name="resume.docx")
    else:
        st.write("Upload a resume to see it here.")
