from pydantic import BaseModel


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