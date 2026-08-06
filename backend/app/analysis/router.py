import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.schemas import (
    CheckRequest,
    ExtractRequest,
    FactListOut,
    ReportListOut,
)
from app.analysis.service import (
    check_consistency,
    extract_facts,
    list_facts,
    list_reports,
)
from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.database import get_db

router = APIRouter(tags=["analysis"])
logger = logging.getLogger(__name__)


async def _workspace(user: User, db: AsyncSession):
    ws = await user.get_owned_workspace(db)
    if not ws:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return ws


@router.post("/api/v1/analysis/extract-facts")
async def extract_facts_endpoint(
    body: ExtractRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ws = await _workspace(user, db)
    try:
        fact = await extract_facts(db, ws.id, body.repo_full_name)
        return fact.model_dump(mode="json")
    except RuntimeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e


@router.get("/api/v1/analysis/facts", response_model=FactListOut)
async def list_facts_endpoint(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> FactListOut:
    ws = await _workspace(user, db)
    facts = await list_facts(db, ws.id)
    return FactListOut(facts=facts)


@router.post("/api/v1/analysis/check-consistency")
async def check_consistency_endpoint(
    body: CheckRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ws = await _workspace(user, db)
    try:
        report = await check_consistency(db, ws.id, body.repo_full_name)
        return report.model_dump(mode="json")
    except RuntimeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e


@router.get("/api/v1/analysis/reports", response_model=ReportListOut)
async def list_reports_endpoint(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportListOut:
    ws = await _workspace(user, db)
    reports = await list_reports(db, ws.id)
    return ReportListOut(reports=reports)