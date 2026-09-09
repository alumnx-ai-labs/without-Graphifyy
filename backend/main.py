from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.job_routes import router as job_router
from backend.routes.resume_routes import router as resume_router

app = FastAPI(title="Job Search Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)
app.include_router(job_router)


@app.get("/health")
def health():
    return {"status": "ok"}
