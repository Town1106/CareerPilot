import datetime
import uuid

from pydantic import BaseModel, Field


class MCPStatus(BaseModel):
    provider: str
    connected: bool
    message: str


class RepoSummary(BaseModel):
    name: str
    full_name: str
    description: str | None
    language: str | None
    stargazers_count: int
    updated_at: str
    html_url: str


class RepoDetail(RepoSummary):
    topics: list[str]
    default_branch: str
    open_issues_count: int
    created_at: str


class CommitItem(BaseModel):
    sha: str
    message: str
    author: str
    date: str


class FileContent(BaseModel):
    path: str
    content: str
    size: int


class RepoList(BaseModel):
    repos: list[RepoSummary]


class CommitList(BaseModel):
    commits: list[CommitItem]


class ImportRequest(BaseModel):
    workspace_id: uuid.UUID
    repo_full_name: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")


class CalendarEventCreate(BaseModel):
    workspace_id: uuid.UUID
    title: str
    description: str
    date: datetime.date
    duration_minutes: int
    source_task_id: str | None = None


class CalendarEventOut(BaseModel):
    id: str
    title: str
    description: str
    date: str
    duration_minutes: int
    source_task_id: str | None = None
    created_at: str
