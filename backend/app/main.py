import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analysis.router import router as analysis_router
from app.auth.router import router as auth_router
from app.core.config import FRONTEND_ORIGIN
from app.core.database import SessionFactory
from app.documents.router import router as document_router
from app.interviews.router import router as interview_router
from app.jobs.router import router as job_router
from app.mcp.router import router as mcp_router
from app.plans.router import router as plan_router
from app.rag.router import router as rag_router
from app.rag.store import close_client
from app.skills.registry import get_registry
from app.skills.router import router as skills_router
from app.tools.registry import get_tool_registry
from app.tools.router import router as tools_router
from app.traces.router import router as traces_router
from app.workspaces.router import router as workspace_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    registry = get_registry()
    registry.reload()
    tool_registry = get_tool_registry()
    tool_registry.reload()
    try:
        async with SessionFactory() as db:
            await registry.sync_to_db(db)
            await tool_registry.sync_to_db(db)
            await db.commit()
    except Exception:
        logger.warning("Sync skipped (table may not exist yet)", exc_info=True)
    yield
    close_client()


app = FastAPI(title="CareerPilot API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analysis_router)
app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(document_router)
app.include_router(rag_router)
app.include_router(job_router)
app.include_router(mcp_router)
app.include_router(interview_router)
app.include_router(plan_router)
app.include_router(skills_router)
app.include_router(tools_router)
app.include_router(traces_router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
