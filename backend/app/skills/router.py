from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.database import get_db
from app.skills.models import SkillDefinition
from app.skills.registry import get_registry
from app.skills.schemas import SkillDetailOut, SkillListOut, SkillOut

router = APIRouter(tags=["skills"])


@router.get("/api/v1/skills", response_model=SkillListOut)
async def list_skills(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SkillListOut:
    rows = list((await db.scalars(select(SkillDefinition).order_by(SkillDefinition.name))).all())
    return SkillListOut(skills=[SkillOut.model_validate(r) for r in rows])


@router.get("/api/v1/skills/{name}", response_model=SkillDetailOut)
async def get_skill(
    name: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SkillDetailOut:
    row = await db.scalar(select(SkillDefinition).where(SkillDefinition.name == name))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    registry = get_registry()
    manifest = registry.get(name)
    triggers: list[str] = []
    required_inputs: list[str] = []
    allowed_tools: list[str] = []
    if manifest:
        triggers = manifest.get("triggers", [])
        required_inputs = manifest.get("required_inputs", [])
        allowed_tools = manifest.get("allowed_tools", [])
    return SkillDetailOut(
        id=row.id,
        name=row.name,
        version=row.version,
        description=row.description,
        manifest_path=row.manifest_path,
        risk_level=row.risk_level,
        status=row.status,
        created_at=row.created_at,
        triggers=triggers,
        required_inputs=required_inputs,
        allowed_tools=allowed_tools,
    )