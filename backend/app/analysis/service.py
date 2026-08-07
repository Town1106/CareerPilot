import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import ConsistencyReport, ProjectFact
from app.analysis.schemas import FactOut, ReportOut
from app.documents.models import Document, DocumentChunk, DocumentVersion
from app.mcp.github_client import get_github_client
from app.rag.gateway import AIServiceError, structured_chat
from app.workspaces.models import Workspace

EXTRACT_SYSTEM = (
    "你是技术项目分析专家。从 GitHub 仓库信息中提取结构化事实。"
    "输出必须是严格的 JSON 对象，不要包含任何其他文本。"
)

EXTRACT_PROMPT = """分析以下 GitHub 仓库信息，提取结构化事实：

仓库名：{repo}
描述：{description}
语言：{language}
README 摘要：{readme}
近期提交：{commits}

请输出 JSON：
{{
  "tech_stack": ["技术1", "技术2", ...],
  "summary": "一句话项目概述",
  "role": "推断的仓库所有者在这个项目中的角色（如：全栈开发、后端负责人、个人项目作者）",
  "complexity": "low/medium/high"
}}"""

CHECK_SYSTEM = (
    "你是简历一致性校验专家。比对 GitHub 项目事实与简历中声称的经验，"
    "找出匹配项、缺失项和矛盾项。输出必须是严格的 JSON 对象。"
)

CHECK_PROMPT = """请比对以下信息，输出一致性报告。

【GitHub 项目事实】
{project_facts}

【简历内容】
{resume}

请输出 JSON：
{{
  "matched_items": [
    {{"item": "匹配的技术/项目", "source": "来源"}}
  ],
  "missing_in_resume": [
    {{"item": "简历中缺失的项目或技术", "evidence": "GitHub证据"}}
  ],
  "conflicts": [
    {{"claim": "简历声称", "reality": "GitHub实际情况", "severity": "high/medium/low"}}
  ],
  "overall_score": 85
}}

overall_score 是 0-100 的整数，表示简历与 GitHub 项目的一致性程度。"""


async def extract_facts(
    db: AsyncSession, workspace_id: uuid.UUID, repo_full_name: str
) -> FactOut:
    client = get_github_client()
    if not client.connected:
        raise RuntimeError("GitHub 未连接")
    owner_id = await db.scalar(select(Workspace.user_id).where(Workspace.id == workspace_id))
    try:
        client.require_owner(str(owner_id))
    except PermissionError as error:
        raise RuntimeError(str(error)) from error

    owner, repo = repo_full_name.split("/")
    repo_data = await client.get_repo(owner, repo)
    readme_b64 = await client.get_readme(owner, repo)
    commits_data = await client.list_commits(owner, repo, per_page=5)

    import base64
    readme_text = ""
    if readme_b64:
        try:
            readme_text = base64.b64decode(readme_b64).decode("utf-8", errors="replace")[:3000]
        except (ValueError, UnicodeDecodeError):
            pass

    commit_lines = [
        c["commit"]["message"].split("\n")[0]
        for c in commits_data if "commit" in c
    ][:5]

    prompt = EXTRACT_PROMPT.format(
        repo=repo_full_name,
        description=repo_data.get("description", ""),
        language=repo_data.get("language", "N/A"),
        readme=readme_text[:2000],
        commits="\n".join(commit_lines),
    )

    try:
        result = await structured_chat(EXTRACT_SYSTEM, prompt)
    except AIServiceError as e:
        raise RuntimeError(f"AI 分析失败: {e}") from e

    tech_stack = result.get("tech_stack", [])
    if not isinstance(tech_stack, list):
        tech_stack = []
    facts = ProjectFact(
        workspace_id=workspace_id,
        repo_full_name=repo_full_name,
        extracted_tech_stack=[str(item)[:120] for item in tech_stack[:50]],
        extracted_summary=result.get("summary", ""),
        extracted_role=result.get("role", ""),
        commit_count=len(commits_data),
    )
    db.add(facts)
    await db.commit()
    await db.refresh(facts)
    return FactOut.model_validate(facts)


async def list_facts(
    db: AsyncSession, workspace_id: uuid.UUID
) -> list[FactOut]:
    rows = (
        await db.scalars(
            select(ProjectFact)
            .where(ProjectFact.workspace_id == workspace_id)
            .order_by(ProjectFact.created_at.desc())
        )
    ).all()
    return [FactOut.model_validate(r) for r in rows]


async def check_consistency(
    db: AsyncSession, workspace_id: uuid.UUID, repo_full_name: str
) -> ReportOut:
    fact = await db.scalar(
        select(ProjectFact).where(
            ProjectFact.workspace_id == workspace_id,
            ProjectFact.repo_full_name == repo_full_name,
        )
    )
    if not fact:
        raise RuntimeError("请先提取项目事实")

    # 获取简历内容
    rows = (
        await db.execute(
            select(DocumentChunk, Document, DocumentVersion)
            .join(DocumentVersion, DocumentVersion.id == DocumentChunk.version_id)
            .join(Document, Document.active_version_id == DocumentVersion.id)
            .where(
                Document.workspace_id == workspace_id,
                Document.category == "resume",
                DocumentVersion.status == "indexed",
            )
            .order_by(DocumentChunk.position)
            .limit(20)
        )
    ).all()
    resume_text = "\n\n".join(chunk.content[:500] for chunk, _, _ in rows) if rows else "（未上传简历）"

    project_facts = json.dumps({
        "tech_stack": fact.extracted_tech_stack,
        "summary": fact.extracted_summary,
        "role": fact.extracted_role,
    }, ensure_ascii=False, indent=2)

    prompt = CHECK_PROMPT.format(
        project_facts=project_facts,
        resume=resume_text[:3000],
    )

    try:
        result = await structured_chat(CHECK_SYSTEM, prompt)
    except AIServiceError as e:
        raise RuntimeError(f"AI 分析失败: {e}") from e

    matched = result.get("matched_items", [])
    missing = result.get("missing_in_resume", [])
    conflicts = result.get("conflicts", [])
    try:
        overall_score = min(100, max(0, float(result.get("overall_score", 0))))
    except (TypeError, ValueError):
        overall_score = 0
    report = ConsistencyReport(
        workspace_id=workspace_id,
        repo_full_name=repo_full_name,
        matched_items=matched if isinstance(matched, list) else [],
        missing_in_resume=missing if isinstance(missing, list) else [],
        conflicts=conflicts if isinstance(conflicts, list) else [],
        overall_score=overall_score,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return ReportOut.model_validate(report)


async def list_reports(
    db: AsyncSession, workspace_id: uuid.UUID
) -> list[ReportOut]:
    rows = (
        await db.scalars(
            select(ConsistencyReport)
            .where(ConsistencyReport.workspace_id == workspace_id)
            .order_by(ConsistencyReport.created_at.desc())
        )
    ).all()
    return [ReportOut.model_validate(r) for r in rows]
