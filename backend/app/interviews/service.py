import json
from collections import Counter

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utc_now
from app.interviews.models import (
    CompetencyMemory,
    InterviewScore,
    InterviewSession,
    InterviewTurn,
)
from app.interviews.schemas import (
    AnswerAssessment,
    InterviewOut,
    InterviewReportResult,
    QuestionResult,
    ScoreOut,
    TurnOut,
)
from app.jobs.models import Competency, JobDescription, JobRequirement
from app.jobs.service import normalize_competency
from app.rag import gateway
from app.rag.gateway import AIServiceError

COVERAGE_PRIORITY = {"conflict": 0, "uncovered": 0, "partial": 1, "covered": 2}


class InterviewStateError(RuntimeError):
    pass


async def requirement_rows(
    db: AsyncSession, session: InterviewSession
) -> list[tuple[JobRequirement, Competency]]:
    rows = (
        await db.execute(
            select(JobRequirement, Competency)
            .join(Competency, Competency.id == JobRequirement.competency_id)
            .where(JobRequirement.job_description_id == session.job_description_id)
        )
    ).all()
    return sorted(
        rows,
        key=lambda row: (COVERAGE_PRIORITY[row[0].coverage], -row[0].importance),
    )


async def generate_question(
    requirement: JobRequirement,
    competency: Competency,
    interview_type: str,
    previous_questions: list[str],
) -> str:
    payload = await gateway.structured_chat(
        (
            "你是严格但友好的模拟面试官。返回 JSON 对象，字段只有 question。"
            "一次只问一个问题，不提供答案、提示、评分标准或多段子问题。"
            "问题必须考察指定能力，并结合岗位要求和候选人当前证据状态。"
        ),
        json.dumps(
            {
                "interview_type": interview_type,
                "competency": competency.canonical_name,
                "job_requirement": requirement.raw_evidence,
                "current_evidence_status": requirement.coverage,
                "evidence_summary": requirement.explanation,
                "avoid_repeating": previous_questions[-5:],
            },
            ensure_ascii=False,
        ),
    )
    try:
        return QuestionResult.model_validate(payload).question
    except ValidationError as error:
        raise AIServiceError("面试问题未通过结构校验") from error


async def assess_answer(turn: InterviewTurn, answer: str) -> AnswerAssessment:
    payload = await gateway.structured_chat(
        (
            "你是模拟面试流程控制器。只在回答含糊、缺少关键原理或项目细节时追问。"
            "返回 JSON：quality(0-100)、should_follow_up、observation、follow_up_question。"
            "追问必须只有一个问题且不能泄露参考答案；不追问时 follow_up_question 为 null。"
        ),
        json.dumps(
            {
                "competency": turn.competency_name,
                "question": turn.question,
                "answer": answer,
            },
            ensure_ascii=False,
        ),
    )
    try:
        return AnswerAssessment.model_validate(payload)
    except ValidationError as error:
        raise AIServiceError("回答判断未通过结构校验") from error


async def build_report(turns: list[InterviewTurn]) -> InterviewReportResult:
    answered = [turn for turn in turns if turn.answer]
    payload = await gateway.structured_chat(
        (
            "你是独立面试评分官，只根据候选人的实际回答评分，不推断未说出的知识。"
            "返回 JSON：overall_score、summary、strengths、issues、competency_scores。"
            "competency_scores 每项包含 competency、score、rubric、evidence、strengths、issues、suggestion。"
            "evidence 必须引用回答序号并概括原话；评分标准、优点、问题和建议必须具体。"
        ),
        json.dumps(
            {
                "allowed_competencies": list(
                    dict.fromkeys(turn.competency_name for turn in answered)
                ),
                "answers": [
                    {
                        "sequence": turn.sequence,
                        "competency": turn.competency_name,
                        "question": turn.question,
                        "answer": turn.answer,
                    }
                    for turn in answered
                ],
            },
            ensure_ascii=False,
        ),
    )
    try:
        return InterviewReportResult.model_validate(payload)
    except ValidationError as error:
        raise AIServiceError("面试报告未通过结构校验") from error


async def get_interview(db: AsyncSession, session: InterviewSession) -> InterviewOut:
    job = (
        await db.scalar(
            select(JobDescription).where(JobDescription.id == session.job_description_id)
        )
        if session.job_description_id
        else None
    )
    turns = list(
        (
            await db.scalars(
                select(InterviewTurn)
                .where(InterviewTurn.session_id == session.id)
                .order_by(InterviewTurn.sequence)
            )
        ).all()
    )
    scores = list(
        (
            await db.scalars(
                select(InterviewScore)
                .where(InterviewScore.session_id == session.id)
                .order_by(InterviewScore.score)
            )
        ).all()
    )
    return InterviewOut(
        id=session.id,
        workspace_id=session.workspace_id,
        job_description_id=session.job_description_id,
        job_name=f"{job.company} · {job.title}" if job else None,
        interview_type=session.interview_type,
        question_limit=session.question_limit,
        status=session.status,
        overall_score=session.overall_score,
        report_summary=session.report_summary,
        report_strengths=json.loads(session.report_strengths or "[]"),
        report_issues=json.loads(session.report_issues or "[]"),
        error=session.error,
        started_at=session.started_at,
        completed_at=session.completed_at,
        created_at=session.created_at,
        turns=[TurnOut.model_validate(turn) for turn in turns],
        scores=[
            ScoreOut(
                id=score.id,
                competency_name=score.competency_name,
                score=score.score,
                rubric=score.rubric,
                evidence=json.loads(score.evidence),
                strengths=json.loads(score.strengths),
                issues=json.loads(score.issues),
                suggestion=score.suggestion,
            )
            for score in scores
        ],
    )


async def start_interview(db: AsyncSession, session: InterviewSession) -> InterviewOut:
    if session.status == "in_progress":
        return await get_interview(db, session)
    if session.status != "draft":
        raise InterviewStateError("该面试不能重新开始")
    rows = await requirement_rows(db, session)
    if not rows:
        raise InterviewStateError("目标岗位尚未完成能力分析")
    requirement, competency = rows[0]
    question = await generate_question(requirement, competency, session.interview_type, [])
    db.add(
        InterviewTurn(
            session_id=session.id,
            competency_id=competency.id,
            competency_name=competency.canonical_name,
            sequence=1,
            question=question,
        )
    )
    session.status = "in_progress"
    session.started_at = utc_now()
    session.error = None
    await db.commit()
    return await get_interview(db, session)


async def finalize_interview(db: AsyncSession, session: InterviewSession) -> InterviewOut:
    turns = list(
        (
            await db.scalars(
                select(InterviewTurn)
                .where(InterviewTurn.session_id == session.id)
                .order_by(InterviewTurn.sequence)
            )
        ).all()
    )
    if not any(turn.answer for turn in turns):
        raise InterviewStateError("至少回答一道题后才能结束面试")
    report = await build_report(turns)
    allowed = {normalize_competency(turn.competency_name) for turn in turns if turn.answer}
    seen = set()
    valid_scores = []
    for score in report.competency_scores:
        name = normalize_competency(score.competency)
        if name in allowed and name not in seen:
            seen.add(name)
            valid_scores.append((name, score))
    if not valid_scores:
        raise AIServiceError("面试报告没有可用的能力评分")

    session.status = "completed"
    session.overall_score = report.overall_score
    session.report_summary = report.summary
    session.report_strengths = json.dumps(report.strengths, ensure_ascii=False)
    session.report_issues = json.dumps(report.issues, ensure_ascii=False)
    session.completed_at = utc_now()
    for name, score in valid_scores:
        competency = await db.scalar(
            select(Competency).where(
                Competency.workspace_id == session.workspace_id,
                Competency.canonical_name == name,
            )
        )
        db.add(
            InterviewScore(
                session_id=session.id,
                competency_id=competency.id if competency else None,
                competency_name=name,
                score=score.score,
                rubric=score.rubric,
                evidence=json.dumps(score.evidence, ensure_ascii=False),
                strengths=json.dumps(score.strengths, ensure_ascii=False),
                issues=json.dumps(score.issues, ensure_ascii=False),
                suggestion=score.suggestion,
            )
        )
        memory = await db.scalar(
            select(CompetencyMemory).where(
                CompetencyMemory.workspace_id == session.workspace_id,
                CompetencyMemory.competency_name == name,
            )
        )
        evidence_summary = "；".join(score.evidence + score.issues + [score.suggestion])
        if memory:
            memory.mastery_score = round((memory.mastery_score + score.score) / 2, 1)
            memory.confidence = min(1, round(memory.confidence + 0.2, 2))
            memory.source_session_id = session.id
            memory.evidence_summary = evidence_summary
            memory.error_count += int(score.score < 60)
            memory.confirmed = False
        else:
            db.add(
                CompetencyMemory(
                    workspace_id=session.workspace_id,
                    competency_id=competency.id if competency else None,
                    source_session_id=session.id,
                    competency_name=name,
                    mastery_score=score.score,
                    confidence=0.6,
                    evidence_summary=evidence_summary,
                    error_count=int(score.score < 60),
                )
            )
    await db.commit()
    return await get_interview(db, session)


async def submit_answer(db: AsyncSession, session: InterviewSession, answer: str) -> InterviewOut:
    if session.status != "in_progress":
        raise InterviewStateError("该面试当前不能提交回答")
    turns = list(
        (
            await db.scalars(
                select(InterviewTurn)
                .where(InterviewTurn.session_id == session.id)
                .order_by(InterviewTurn.sequence)
            )
        ).all()
    )
    current = turns[-1]
    if current.answer:
        raise InterviewStateError("当前没有待回答的问题")
    assessment = await assess_answer(current, answer)
    current.answer = answer.strip()
    current.private_observation = assessment.observation
    current.answered_at = utc_now()
    if len(turns) >= session.question_limit:
        return await finalize_interview(db, session)

    if assessment.should_follow_up and not current.is_follow_up:
        db.add(
            InterviewTurn(
                session_id=session.id,
                competency_id=current.competency_id,
                competency_name=current.competency_name,
                sequence=len(turns) + 1,
                question=assessment.follow_up_question,
                is_follow_up=True,
            )
        )
    else:
        rows = await requirement_rows(db, session)
        counts = Counter(turn.competency_name for turn in turns)
        requirement, competency = min(
            rows,
            key=lambda row: counts[row[1].canonical_name],
        )
        question = await generate_question(
            requirement,
            competency,
            session.interview_type,
            [turn.question for turn in turns],
        )
        db.add(
            InterviewTurn(
                session_id=session.id,
                competency_id=competency.id,
                competency_name=competency.canonical_name,
                sequence=len(turns) + 1,
                question=question,
            )
        )
    await db.commit()
    return await get_interview(db, session)
