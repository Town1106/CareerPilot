from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.core.config import FRONTEND_ORIGIN
from app.documents.router import router as document_router
from app.workspaces.router import router as workspace_router

app = FastAPI(title="CareerPilot API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(document_router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
