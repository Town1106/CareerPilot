import json
import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.models import ToolDefinition, ToolPolicy

logger = logging.getLogger(__name__)

MANIFESTS_DIR = Path(__file__).resolve().parent / "manifests"


class ToolRegistry:
    """扫描并加载 Tool Manifest，管理工具与策略。"""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}

    def reload(self) -> int:
        """重新扫描 manifests 目录，返回成功加载的数量。"""
        self._tools.clear()
        if not MANIFESTS_DIR.is_dir():
            logger.warning("Tool manifests directory not found: %s", MANIFESTS_DIR)
            return 0

        count = 0
        for manifest_file in sorted(MANIFESTS_DIR.rglob("manifest.yaml")):
            tool_dir = manifest_file.parent
            tool_name = tool_dir.name
            try:
                raw = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    logger.warning("Invalid manifest format in %s", manifest_file)
                    continue
                manifest = self._validate(raw, tool_name)
                manifest["_path"] = str(manifest_file.relative_to(MANIFESTS_DIR.parent))
                self._tools[tool_name] = manifest
                count += 1
            except Exception:
                logger.exception("Failed to load tool manifest %s", manifest_file)
        logger.info("Loaded %d tool(s)", count)
        return count

    async def sync_to_db(self, db: AsyncSession) -> int:
        """将内存中的 Tool 同步到数据库，返回新增数量。"""
        added = 0
        for name, manifest in self._tools.items():
            existing = await db.scalar(
                select(ToolDefinition).where(ToolDefinition.name == name)
            )
            if existing is None:
                db.add(
                    ToolDefinition(
                        name=manifest["name"],
                        version=manifest["version"],
                        description=manifest["description"],
                        manifest_path=manifest["_path"],
                        risk_level=manifest["risk_level"],
                        input_schema=json.dumps(manifest.get("input_schema")),
                        output_schema=json.dumps(manifest.get("output_schema")),
                    )
                )
                added += 1

            # 确保策略存在
            policy = await db.scalar(
                select(ToolPolicy).where(ToolPolicy.tool_name == name)
            )
            if policy is None:
                risk = manifest["risk_level"]
                db.add(
                    ToolPolicy(
                        tool_name=name,
                        require_approval=risk != "R0",
                        approval_prompt=self._default_prompt(manifest) if risk != "R0" else None,
                    )
                )

        if added:
            await db.flush()
            logger.info("Synced %d new tool(s) to database", added)
        return added

    def get(self, name: str) -> dict[str, Any] | None:
        return self._tools.get(name)

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._tools.values())

    @staticmethod
    def _validate(raw: dict[str, Any], name: str) -> dict[str, Any]:
        required = ["name", "version", "description", "risk_level"]
        for field in required:
            if field not in raw:
                raise ValueError(f"Tool '{name}' missing required field: {field}")
        if raw["name"] != name:
            raise ValueError(f"Tool manifest name '{raw['name']}' does not match directory '{name}'")
        return {
            "name": raw["name"],
            "version": raw["version"],
            "description": raw["description"],
            "risk_level": raw["risk_level"],
            "input_schema": raw.get("input_schema"),
            "output_schema": raw.get("output_schema"),
        }

    @staticmethod
    def _default_prompt(manifest: dict[str, Any]) -> str:
        return f"Agent 请求调用工具 {manifest['name']}，请确认是否允许执行。"


_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    return _tool_registry