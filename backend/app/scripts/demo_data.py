"""演示数据填充脚本。

用法：
    cd backend
    uv run python -m app.scripts.demo_data

生成内容：
- 演示账号：demo@careerpilot.dev / demo123
- 1 个工作空间、2 份简历文档、2 个 JD（已分析）、1 场模拟面试、1 个学习计划
"""

import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from sqlalchemy import select

from app.auth.models import User
from app.core.database import SessionFactory, utc_now
from app.documents.models import Document, DocumentChunk, DocumentVersion
from app.interviews.models import (
    CompetencyMemory,
    InterviewScore,
    InterviewSession,
    InterviewTurn,
)
from app.jobs.models import Competency, JobDescription, JobRequirement
from app.plans.models import StudyPlan, StudyTask
from app.workspaces.models import Workspace

logger = logging.getLogger(__name__)
ph = PasswordHasher()

DEMO_EMAIL = "demo@careerpilot.dev"
DEMO_PASSWORD = "demo1234"
DEMO_WS_NAME = "\u6c42\u804c\u51c6\u5907"

# ── 简历文档内容 ──

RESUME_JAVA = """# 张三 - Java 后端开发工程师

## 个人信息
- 学历：计算机科学与技术 本科
- 工作年限：3 年

## 技术栈
- 语言：Java, Python, SQL
- 框架：Spring Boot, Spring Cloud, MyBatis, JPA
- 数据库：MySQL, PostgreSQL, Redis
- 中间件：RabbitMQ, Kafka, Elasticsearch
- 容器：Docker, Kubernetes

## 项目经历

### 电商平台订单系统
- 技术栈：Spring Boot, MySQL, Redis, RabbitMQ, Kubernetes
- 负责订单核心流程开发，包括下单、支付回调、库存扣减和退款流程。
- 使用 Redis 缓存热点商品库存，减少数据库查询压力。
- 通过 RabbitMQ 实现订单状态异步流转，确保最终一致性。
- 部署在 Kubernetes 集群，水平扩展应对促销流量。
- 日均处理订单 50 万+，系统可用性 99.9%。

### 数据中台 API 网关
- 技术栈：Spring Cloud Gateway, PostgreSQL, Kafka, Docker
- 设计并实现统一 API 网关，提供认证、限流、路由和日志功能。
- 使用 PostgreSQL 存储路由配置，支持动态刷新。
- 通过 Kafka 采集 API 调用日志，实时同步到 Elasticsearch 用于监控。
- 支撑 200+ 微服务，日均调用量 1 亿+。

### 智能推荐系统
- 技术栈：Python, Flask, Redis, PostgreSQL
- 基于协同过滤和内容推荐算法，为用户提供个性化商品推荐。
- Redis 缓存用户画像和推荐结果，响应时间 < 50ms。
- PostgreSQL 存储用户行为数据，定期离线训练模型。
"""

RESUME_FRONTEND = """# 李四 - 前端开发工程师

## 个人信息
- 学历：软件工程 本科
- 工作年限：2 年

## 技术栈
- 语言：JavaScript, TypeScript, HTML, CSS
- 框架：React, Vue.js, Next.js, Ant Design
- 构建：Vite, Webpack, Babel
- 测试：Jest, React Testing Library

## 项目经历

### 企业级后台管理系统
- 技术栈：React, TypeScript, Ant Design, Vite
- 主导前端架构设计，采用 React Hooks + TypeScript 重构旧版项目。
- 使用 Ant Design Pro 组件库，实现统一的 UI 规范和交互体验。
- 基于 Vite 实现极速开发体验，HMR 响应时间 < 100ms。
- 集成 ECharts 数据可视化，支持多维度数据分析和报表导出。

### 低代码页面搭建平台
- 技术栈：React, TypeScript, Zustand, React DnD
- 实现拖拽式页面编辑器，支持 30+ 组件的自由组合和配置。
- 使用 Zustand 管理编辑器状态，支持撤销/重做操作。
- 实现组件间数据联动和事件绑定，支持复杂交互逻辑配置。
- 生成的页面性能优化，首屏加载时间 < 1.5s。
"""

# ── JD 内容 ──

JD_ALIBABA = """岗位名称：Java 后端开发工程师
公司：阿里巴巴
地点：杭州

岗位职责：
1. 负责电商平台核心业务系统的架构设计和开发，包括订单、支付、库存、物流等模块。
2. 参与系统性能优化，解决高并发场景下的技术难题，确保系统稳定性和可扩展性。
3. 制定技术方案，编写核心代码，指导初级工程师完成开发任务。
4. 参与技术评审和代码审查，推动团队技术规范和最佳实践。

任职要求：
1. 计算机相关专业本科及以上学历，3 年以上 Java 开发经验。
2. 精通 Java 语言，熟悉 JVM 原理和调优，有良好的编程习惯。
3. 熟练掌握 Spring Boot、Spring Cloud、MyBatis 等主流框架。
4. 熟悉 MySQL、Redis、Elasticsearch 等数据库和中间件。
5. 有分布式系统设计经验，熟悉消息队列（Kafka/RabbitMQ）和微服务架构。
6. 了解 Docker 和 Kubernetes，有容器化部署经验者优先。
7. 具备良好的沟通能力和团队协作精神，能承受一定工作压力。
"""

JD_BYTEDANCE = """岗位名称：后端开发工程师
公司：字节跳动
地点：北京

岗位职责：
1. 负责抖音电商后端系统的设计、开发和维护，保障系统高可用和高性能。
2. 参与微服务架构演进，推动服务拆分、治理和性能优化。
3. 设计和实现数据存储方案，包括关系型数据库和缓存策略。
4. 参与技术方案评审，输出高质量的技术文档。

任职要求：
1. 本科及以上学历，计算机相关专业，2 年以上后端开发经验。
2. 精通 Go 或 Java，熟悉常用数据结构和算法。
3. 熟悉 MySQL、Redis、消息队列等常用中间件。
4. 了解分布式系统原理，有实际项目经验。
5. 熟悉 Linux 操作系统和常用命令。
6. 有容器化和 Kubernetes 经验者优先。
7. 有电商或内容平台开发经验者优先。
"""


async def _demo_user_exists() -> bool:
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == DEMO_EMAIL))
        return user is not None


async def seed_demo_data() -> None:
    if await _demo_user_exists():
        logger.info("演示数据已存在（%s），跳过创建。", DEMO_EMAIL)
        logger.info("如需重置，请手动删除演示用户后重新运行。")
        return

    logger.info("开始创建演示数据...")

    async with SessionFactory() as db:
        # ── 1. 创建演示用户 ──
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email=DEMO_EMAIL,
            password_hash=ph.hash(DEMO_PASSWORD),
        )
        db.add(user)
        await db.flush()
        logger.info("  [1/8] 创建用户: %s / %s", DEMO_EMAIL, DEMO_PASSWORD)

        # ── 2. 创建工作空间 ──
        ws_id = uuid.uuid4()
        ws = Workspace(id=ws_id, user_id=user_id, name=DEMO_WS_NAME)
        db.add(ws)
        await db.flush()
        logger.info("  [2/8] 创建工作空间: %s", DEMO_WS_NAME)

        # ── 3. 创建简历文档（Java 后端） ──
        doc1_id = uuid.uuid4()
        doc1 = Document(
            id=doc1_id, workspace_id=ws_id,
            original_name="张三_Java后端开发工程师_简历.md",
            category="resume",
        )
        db.add(doc1)
        await db.flush()

        content1 = RESUME_JAVA.encode("utf-8")
        sha1 = hashlib.sha256(content1).hexdigest()
        ver1_id = uuid.uuid4()
        ver1 = DocumentVersion(
            id=ver1_id, document_id=doc1_id, version=1,
            original_name="张三_Java后端开发工程师_简历.md",
            stored_name="demo_java_resume.md",
            media_type="text/markdown",
            size_bytes=len(content1),
            sha256=sha1,
            status="parsed",
            chunk_count=4,
        )
        db.add(ver1)
        await db.flush()

        step = 500
        full = RESUME_JAVA
        chunks1 = [
            DocumentChunk(version_id=ver1_id, position=i, content=full[i * step:(i + 1) * step])
            for i in range((len(full) + step - 1) // step)
        ]
        db.add_all(chunks1)
        doc1.active_version_id = ver1_id
        await db.flush()
        logger.info("  [3/8] 创建简历文档: %s (%d chunks)", doc1.original_name, len(chunks1))

        # ── 4. 创建简历文档（前端） ──
        doc2_id = uuid.uuid4()
        doc2 = Document(
            id=doc2_id, workspace_id=ws_id,
            original_name="李四_前端开发工程师_简历.md",
            category="resume",
        )
        db.add(doc2)
        await db.flush()

        content2 = RESUME_FRONTEND.encode("utf-8")
        sha2 = hashlib.sha256(content2).hexdigest()
        ver2_id = uuid.uuid4()
        ver2 = DocumentVersion(
            id=ver2_id, document_id=doc2_id, version=1,
            original_name="李四_前端开发工程师_简历.md",
            stored_name="demo_frontend_resume.md",
            media_type="text/markdown",
            size_bytes=len(content2),
            sha256=sha2,
            status="parsed",
            chunk_count=3,
        )
        db.add(ver2)
        await db.flush()

        full2 = RESUME_FRONTEND
        chunks2 = [
            DocumentChunk(version_id=ver2_id, position=i, content=full2[i * step:(i + 1) * step])
            for i in range((len(full2) + step - 1) // step)
        ]
        db.add_all(chunks2)
        doc2.active_version_id = ver2_id
        await db.flush()
        logger.info("  [4/8] 创建简历文档: %s (%d chunks)", doc2.original_name, len(chunks2))

        # ── 5. 创建 JD 1：阿里巴巴 Java 后端 ──
        jd1_id = uuid.uuid4()
        jd1 = JobDescription(
            id=jd1_id, workspace_id=ws_id,
            company="阿里巴巴", title="Java 后端开发工程师",
            raw_text=JD_ALIBABA,
            status="analyzed",
            coverage_score=87.5,
            analyzed_at=utc_now(),
        )
        db.add(jd1)
        await db.flush()

        jd1_competencies = [
            ("java", "technical"), ("spring boot", "technical"), ("spring cloud", "technical"),
            ("mybatis", "technical"), ("mysql", "technical"), ("redis", "technical"),
            ("elasticsearch", "technical"), ("kafka", "technical"), ("rabbitmq", "technical"),
            ("docker", "technical"), ("kubernetes", "technical"), ("分布式系统", "technical"),
            ("微服务架构", "technical"), ("jvm 调优", "technical"), ("后端开发经验", "experience"),
        ]
        jd1_reqs = [
            ("must", 3, "covered", 0.90, "简历中明确提到 Java 技术栈和 Spring Boot 项目经验"),
            ("must", 3, "covered", 0.95, "简历中多个项目使用 Spring Boot"),
            ("preferred", 1, "covered", 0.85, "简历中数据中台项目使用 Spring Cloud Gateway"),
            ("must", 3, "covered", 0.80, "简历中提及 MyBatis"),
            ("must", 3, "covered", 0.90, "简历中电商项目使用 MySQL"),
            ("must", 3, "covered", 0.90, "简历中多个项目使用 Redis 缓存"),
            ("preferred", 1, "covered", 0.85, "简历中提及 Elasticsearch 日志监控"),
            ("preferred", 1, "covered", 0.80, "简历中提及 Kafka 采集日志"),
            ("preferred", 1, "covered", 0.80, "简历中电商项目使用 RabbitMQ"),
            ("preferred", 1, "covered", 0.85, "简历中提及 Docker"),
            ("preferred", 1, "partial", 0.60, "简历中提及 Kubernetes 部署但未详细描述"),
            ("must", 3, "partial", 0.50, "简历中电商项目有分布式经验但未展开"),
            ("must", 3, "partial", 0.55, "简历中提及微服务但未详细说明架构设计"),
            ("preferred", 1, "uncovered", 0.00, "简历中未提及 JVM 调优经验"),
            ("must", 3, "covered", 0.90, "简历中明确写明 3 年后端开发经验"),
        ]

        for i, (name, category) in enumerate(jd1_competencies):
            comp = await db.scalar(
                select(Competency).where(Competency.workspace_id == ws_id, Competency.canonical_name == name)
            )
            if not comp:
                comp = Competency(id=uuid.uuid4(), workspace_id=ws_id, canonical_name=name, category=category)
                db.add(comp)
                await db.flush()

            req_type, importance, coverage, confidence, explanation = jd1_reqs[i]
            db.add(JobRequirement(
                id=uuid.uuid4(), job_description_id=jd1_id, competency_id=comp.id,
                requirement_type=req_type, importance=importance,
                coverage=coverage, confidence=confidence, explanation=explanation,
            ))
        await db.flush()
        logger.info("  [5/8] 创建 JD: 阿里巴巴 Java 后端开发工程师 (覆盖率 87.5%%, 15 项要求)")

        # ── 6. 创建 JD 2：字节跳动后端 ──
        jd2_id = uuid.uuid4()
        jd2 = JobDescription(
            id=jd2_id, workspace_id=ws_id,
            company="字节跳动", title="后端开发工程师",
            raw_text=JD_BYTEDANCE,
            status="analyzed",
            coverage_score=72.5,
            analyzed_at=utc_now(),
        )
        db.add(jd2)
        await db.flush()

        jd2_competencies = [
            ("java", "technical"), ("mysql", "technical"), ("redis", "technical"),
            ("消息队列", "technical"), ("分布式系统", "technical"), ("kubernetes", "technical"),
            ("docker", "technical"), ("linux", "technical"), ("后端开发经验", "experience"),
            ("电商开发经验", "experience"),
        ]
        jd2_reqs = [
            ("must", 3, "covered", 0.90, "简历中明确提到 Java"),
            ("must", 3, "covered", 0.90, "简历中电商项目使用 MySQL"),
            ("must", 3, "covered", 0.90, "简历中多个项目使用 Redis"),
            ("must", 3, "partial", 0.60, "简历中提及 Kafka 和 RabbitMQ 但未详细描述消息队列设计"),
            ("preferred", 1, "partial", 0.50, "简历中电商项目有分布式经验但未展开"),
            ("preferred", 1, "partial", 0.60, "简历中提及 Kubernetes 部署但未详细描述"),
            ("preferred", 1, "covered", 0.85, "简历中提及 Docker"),
            ("preferred", 1, "uncovered", 0.00, "简历中未提及 Linux 系统管理经验"),
            ("must", 3, "covered", 0.90, "简历中明确写明 3 年后端开发经验"),
            ("preferred", 1, "covered", 0.80, "简历中电商系统项目经验"),
        ]

        for i, (name, category) in enumerate(jd2_competencies):
            comp = await db.scalar(
                select(Competency).where(Competency.workspace_id == ws_id, Competency.canonical_name == name)
            )
            if not comp:
                comp = Competency(id=uuid.uuid4(), workspace_id=ws_id, canonical_name=name, category=category)
                db.add(comp)
                await db.flush()

            req_type, importance, coverage, confidence, explanation = jd2_reqs[i]
            db.add(JobRequirement(
                id=uuid.uuid4(), job_description_id=jd2_id, competency_id=comp.id,
                requirement_type=req_type, importance=importance,
                coverage=coverage, confidence=confidence, explanation=explanation,
            ))
        await db.flush()
        logger.info("  [6/8] 创建 JD: 字节跳动 后端开发工程师 (覆盖率 72.5%%, 10 项要求)")

        # ── 7. 创建模拟面试（已完成） ──
        session_id = uuid.uuid4()
        session = InterviewSession(
            id=session_id, workspace_id=ws_id,
            job_description_id=jd1_id,
            interview_type="comprehensive",
            question_limit=3,
            question_source_mode="no_search",
            status="completed",
            overall_score=78.5,
            report_summary="面试整体表现良好，技术基础扎实，但分布式系统设计方面需要加强。",
            report_strengths="1. Java 基础扎实\n2. Spring Boot 使用熟练\n3. 有实际高并发项目经验",
            report_issues="1. 分布式事务理解不够深入\n2. Kubernetes 经验停留在使用层面",
            started_at=utc_now() - timedelta(hours=1),
            completed_at=utc_now(),
        )
        db.add(session)
        await db.flush()

        turns = [
            InterviewTurn(
                session_id=session_id, sequence=1,
                competency_name="java",
                question="请介绍一下 Java 内存模型，以及你在项目中如何进行 JVM 调优？",
                answer="Java 内存模型主要分为堆内存和栈内存。堆内存用于存储对象实例，分为年轻代和老年代。在项目中我主要通过调整堆大小和 GC 策略来优化性能。",
                follow_up_depth=0, source_type="job_gap",
            ),
            InterviewTurn(
                session_id=session_id, sequence=2,
                competency_name="分布式系统",
                question="你在电商项目中如何处理分布式事务？请举例说明。",
                answer="电商项目中我们使用消息队列实现最终一致性。比如下单后通过 RabbitMQ 异步扣减库存。分布式事务我们主要用 TCC 模式。",
                follow_up_depth=1, source_type="adaptive_follow_up",
            ),
            InterviewTurn(
                session_id=session_id, sequence=3,
                competency_name="kubernetes",
                question="你提到了 Kubernetes 部署经验，请描述一下你的部署架构和遇到的挑战。",
                answer="我们使用 Kubernetes 集群部署微服务，通过 Deployment 管理副本。主要挑战是服务发现和配置管理。",
                follow_up_depth=0, source_type="job_gap",
            ),
        ]
        db.add_all(turns)
        await db.flush()

        scores = [
            InterviewScore(session_id=session_id, competency="java", score=85.0,
                           rubric="Java 基础 JVM 内存模型 GC 调优",
                           evidence="正确描述了 Java 内存模型的基本结构，说明了堆和栈的区别"),
            InterviewScore(session_id=session_id, competency="分布式系统", score=65.0,
                           rubric="分布式事务 一致性 消息队列 TCC",
                           evidence="提到了消息队列和最终一致性，但 TCC 模式描述不够具体"),
            InterviewScore(session_id=session_id, competency="kubernetes", score=70.0,
                           rubric="Kubernetes 部署 服务发现 配置管理",
                           evidence="描述了基本部署架构，但挑战和解决方案描述较浅"),
        ]
        db.add_all(scores)
        await db.flush()

        memories = [
            CompetencyMemory(workspace_id=ws_id, competency="java", mastery_score=85.0,
                             evidence_summary="面试中 Java 基础和 Spring Boot 表现优秀", status="confirmed"),
            CompetencyMemory(workspace_id=ws_id, competency="分布式系统", mastery_score=60.0,
                             evidence_summary="分布式事务理解不够深入，TCC 模式描述不具体", status="confirmed"),
            CompetencyMemory(workspace_id=ws_id, competency="kubernetes", mastery_score=65.0,
                             evidence_summary="Kubernetes 经验停留在使用层面，缺乏深入理解", status="confirmed"),
            CompetencyMemory(workspace_id=ws_id, competency="spring boot", mastery_score=90.0,
                             evidence_summary="多个项目使用 Spring Boot，经验丰富", status="inferred"),
            CompetencyMemory(workspace_id=ws_id, competency="redis", mastery_score=80.0,
                             evidence_summary="有 Redis 缓存使用经验，理解缓存策略", status="inferred"),
        ]
        db.add_all(memories)
        await db.flush()
        logger.info("  [7/8] 创建模拟面试: 综合面试 (3 题, 总分 78.5) + 5 条能力记忆")

        # ── 8. 创建学习计划 ──
        plan_id = uuid.uuid4()
        today = datetime.now(UTC).date()
        plan = StudyPlan(
            id=plan_id, workspace_id=ws_id,
            goal="补齐分布式系统和 Kubernetes 短板，巩固 Java 基础，冲刺阿里巴巴和字节跳动面试",
            start_date=today,
            end_date=today + timedelta(days=14),
            status="active",
        )
        db.add(plan)
        await db.flush()

        tasks = [
            ("分布式系统核心概念复习", "学习 CAP 理论、BASE 理论、分布式事务方案（2PC、TCC、Saga），阅读《设计数据密集型应用》第 5-7 章。", 0, 90, 9),
            ("分布式事务实战练习", "基于 Spring Boot + RabbitMQ 实现 TCC 分布式事务 Demo，完成订单-库存-支付三阶段提交。", 1, 120, 9),
            ("Kubernetes 深入理解", "学习 Kubernetes 核心概念：Pod、Service、Deployment、ConfigMap、Secret。动手搭建本地集群，部署 Spring Boot 应用。", 2, 120, 8),
            ("JVM 调优实践", "复习 JVM 内存模型、GC 算法、常用调优参数。使用 jstat、jmap 工具分析堆内存，撰写调优报告。", 3, 90, 7),
            ("Java 并发编程", "复习 synchronized、volatile、Lock、线程池、AQS。阅读 Java 并发编程实战第 3-5 章。", 4, 60, 6),
            ("Redis 高级特性", "学习 Redis 持久化、哨兵、集群、分布式锁、布隆过滤器。动手搭建 Redis Cluster。", 5, 90, 5),
            ("系统设计面试练习", "模拟设计一个电商秒杀系统，包括架构设计、数据库设计、缓存策略、限流方案。", 6, 120, 8),
            ("Spring Cloud 微服务架构", "复习 Spring Cloud Gateway、Nacos、Sentinel、Seata。搭建完整微服务 Demo。", 7, 120, 6),
        ]
        for title, desc, days_offset, duration, priority in tasks:
            db.add(StudyTask(
                plan_id=plan_id, title=title, description=desc,
                scheduled_date=today + timedelta(days=days_offset),
                duration_minutes=duration, priority=priority, status="pending",
            ))
        await db.flush()
        logger.info("  [8/8] 创建学习计划: %s 至 %s (%d 个任务)", today, today + timedelta(days=14), len(tasks))

        await db.commit()

    logger.info("")
    logger.info("=" * 60)
    logger.info("  演示账号: %s", DEMO_EMAIL)
    logger.info("  演示密码: %s", DEMO_PASSWORD)
    logger.info("  工作空间: %s", DEMO_WS_NAME)
    logger.info("=" * 60)
    logger.info("")
    logger.info("启动前后端后，用以上账号登录即可查看演示数据。")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(seed_demo_data())


if __name__ == "__main__":
    main()