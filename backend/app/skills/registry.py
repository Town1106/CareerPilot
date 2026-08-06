import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.skills.models import SkillDefinition

logger = logging.getLogger(__name__)

MANIFESTS_DIR = Path(__file__).resolve().parent / "manifests"


class SkillRegistry:
    """扫描并加载 Skill Manifest，提供查询接口。"""

    def __init__(self) -> None:
        self._skills: dict[str, dict[str, Any]] = {}

    def reload(self) -> int:
        """重新扫描 manifests 目录，返回成功加载的数量。"""
        self._skills.clear()
        if not MANIFESTS_DIR.is_dir():
            logger.warning("Skill manifests directory not found: %s", MANIFESTS_DIR)
            return 0

        count = 0
        for manifest_file in sorted(MANIFESTS_DIR.rglob("manifest.yaml")):
            skill_dir = manifest_file.parent
            skill_name = skill_dir.name
            try:
                raw = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    logger.warning("Invalid manifest format in %s", manifest_file)
                    continue
                manifest = self._validate(raw, skill_name)
                manifest["_path"] = str(manifest_file.relative_to(MANIFESTS_DIR.parent))
                self._skills[skill_name] = manifest
                count += 1
            except Exception:
                logger.exception("Failed to load skill manifest %s", manifest_file)
        logger.info("Loaded %d skill(s)", count)
        return count

    async def sync_to_db(self, db: AsyncSession) -> int:
        """将内存中的 Skill 同步到 skill_definitions 表，返回新增数量。"""
        added = 0
        for name, manifest in self._skills.items():
            existing = await db.scalar(
                select(SkillDefinition).where(SkillDefinition.name == name)
            )
            if existing is None:
                db.add(
                    SkillDefinition(
                        name=manifest["name"],
                        version=manifest["version"],
                        description=manifest["description"],
                        manifest_path=manifest["_path"],
                        risk_level=manifest["risk_level"],
                    )
                )
                added += 1
        if added:
            await db.flush()
            logger.info("Synced %d new skill(s) to database", added)
        return added

    def get(self, name: str) -> dict[str, Any] | None:
        return self._skills.get(name)

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._skills.values())

    @staticmethod
    def _validate(raw: dict[str, Any], name: str) -> dict[str, Any]:
        required = ["name", "version", "description", "triggers", "risk_level"]
        for field in required:
            if field not in raw:
                raise ValueError(f"Skill '{name}' missing required field: {field}")
        if raw["name"] != name:
            raise ValueError(
                f"Skill manifest name '{raw['name']}' does not match directory '{name}'"
            )
        return {
            "name": raw["name"],
            "version": raw["version"],
            "description": raw["description"],
            "triggers": raw.get("triggers", []),
            "required_inputs": raw.get("required_inputs", []),
            "allowed_tools": raw.get("allowed_tools", []),
            "risk_level": raw["risk_level"],
        }


_skill_registry = SkillRegistry()


def get_registry() -> SkillRegistry:
    return _skill_registry