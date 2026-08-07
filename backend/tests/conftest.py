import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.main import app
from app.rag.store import close_client

TEST_DB = Path(__file__).resolve().parent / ".pytest-careerpilot.db"
test_engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB}", poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_db() -> AsyncIterator[AsyncSession]:
    async with TestSession() as session:
        yield session


async def reset_database() -> None:
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
def clean_database() -> Iterator[None]:
    asyncio.run(reset_database())
    yield


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_engine() -> Iterator[None]:
    yield
    close_client()
    asyncio.run(test_engine.dispose())
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = override_db
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def test_session_factory():
    return TestSession
